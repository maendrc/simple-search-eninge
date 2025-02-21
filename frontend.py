import json
import os
from bottle import route, run, request, redirect
from beaker.middleware import SessionMiddleware
from oauth2client.client import OAuth2WebServerFlow
from googleapiclient.discovery import build
import httplib2
from bottle import default_app

# Replace with your actual Google OAuth credentials
CLIENT_ID = 'XXX'
CLIENT_SECRET = 'XXX'
REDIRECT_URI = 'http://localhost:8080/redirect'  # Updated to include /redirect
USER_DATA_FILE = 'user_data.json'  # File to save user data

# Setup session middleware with Beaker
session_opts = {
    'session.type': 'memory',
    'session.cookie_expires': True,
    'session.auto': True
}

# Create the Bottle app
app = default_app()

# Load user data from a JSON file
def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as file:
            return json.load(file)
    return {}

# Save user data to a JSON file
def save_user_data(user_data):
    with open(USER_DATA_FILE, 'w') as file:
        json.dump(user_data, file)

# HTML templates for the pages
html_start = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>My Search Engine</title>
</head>
<body>
    <h1>🌐 Lab One Search Engine</h1>
    
    <form action="/display" method="GET">
        <label for="keywords">Enter a phrase:</label>
        <input type="text" id="keywords" name="keywords" required>
        <button type="submit">Search</button>
    </form>

    <h2>Top 10 Searched Keywords</h2>
    <table id="history">
        <tr>
            <th>Keyword</th>
            <th>Count</th>
        </tr>
        {}
    </table>

    <p>{}</p>
    <a href="/login">Login with Google</a> | <a href="/logout">Logout</a>
</body>
</html>
'''

html_status = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Search Results</title>
</head>
<body>
    <h1>🔍 Search Results for "{}"</h1> 
    
    <h2>Results</h2>
    <p>Number of keywords in the phrase: {}</p>
    <table id="results">
        <tr>
            <th>Word</th>
            <th>Count</th>
        </tr>
        {}
    </table>

    <h2>Top 10 Searched Keywords</h2>
    <table id="history">
        <tr>
            <th>Keyword</th>
            <th>Count</th>
        </tr>
        {}
    </table>

    <p>{}</p>
    <a href="/">Back to search</a> | <a href="/logout">Logout</a>
</body>
</html>
'''

# Route to the home page
@route('/')
def index():
    session = request.environ.get('beaker.session')
    logged_in = session.get('logged_in', False)
    user_email = session.get('user_email', '')
    
    # Load user data
    user_data = load_user_data()
    user_word_history = user_data.get(user_email, {}).get('word_history', {})
    
    # Display top 10 keywords if logged in, otherwise hide
    if logged_in:
        top_keywords = sorted(user_word_history.items(), key=lambda x: x[1], reverse=True)[:10]
        top_keywords_html = ''.join(f'<tr><td>{keyword}</td><td>{count}</td></tr>' for keyword, count in top_keywords)
        return html_start.format(top_keywords_html, f"Logged in as {user_email}")
    else:
        return html_start.format('', "Not logged in")

# Route to process search query
@route('/display', method='GET')
def process_query():
    session = request.environ.get('beaker.session')
    logged_in = session.get('logged_in', False)
    user_email = session.get('user_email', '')

    query = request.query.keywords.strip()
    if query:
        words = query.lower().split()
        num_words = len(words)
        
        # Update search history
        word_occurr = {}
        user_data = load_user_data()
        user_word_history = user_data.get(user_email, {}).get('word_history', {})
        
        for word in words:
            word_occurr[word] = word_occurr.get(word, 0) + 1
            if logged_in:
                user_word_history[word] = user_word_history.get(word, 0) + 1

        if logged_in:
            user_data[user_email] = {'word_history': user_word_history}
            save_user_data(user_data)  # Save updated history to file

        word_count_html = ''.join(f'<tr><td>{word}</td><td>{count}</td></tr>' for word, count in word_occurr.items())
        
        # Top 10 most searched words for the user
        top_words = sorted(user_word_history.items(), key=lambda x: x[1], reverse=True)[:10]
        top_words_html = ''.join(f'<tr><td>{keyword}</td><td>{count}</td></tr>' for keyword, count in top_words)

        return html_status.format(query, num_words, word_count_html, top_words_html, f"Logged in as {user_email}" if logged_in else "Not logged in")
    else:
        return index()  # No query input

# Route for Google OAuth login
@route('/login')
def login():
    print("Login initiated.")
    flow = OAuth2WebServerFlow(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scope=['https://www.googleapis.com/auth/userinfo.email'],
        redirect_uri=REDIRECT_URI  # Use the full redirect URI
    )
    uri = flow.step1_get_authorize_url()
    return redirect(uri)

# Redirect route for OAuth response handling
@route('/redirect')
def oauth_redirect():
    print("Entered /redirect route")  # Debugging output
    session = request.environ.get('beaker.session')
    
    code = request.query.get("code", "")
    print(f"Code received: {code}")  # Debugging output
    if not code:
        return "No code received", 400  # Handle missing code

    flow = OAuth2WebServerFlow(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        scope=['https://www.googleapis.com/auth/userinfo.email'],
        redirect_uri=REDIRECT_URI  # Match this with what you configured
    )
    credentials = flow.step2_exchange(code)
    http_auth = credentials.authorize(httplib2.Http())
    
    # Get user info from Google API
    users_service = build('oauth2', 'v2', http=http_auth)
    user_document = users_service.userinfo().get().execute()
    user_email = user_document['email']

    # Store login status and email in session
    session['logged_in'] = True
    session['user_email'] = user_email
    session.save()
    
    return redirect('/')  # Redirect back to home after login

# Logout route
@route('/logout')
def logout():
    session = request.environ.get('beaker.session')
    session.delete()
    return redirect('/')

# Run the app
app_with_sessions = SessionMiddleware(app, session_opts)
run(app=app_with_sessions, host='0.0.0.0', port=8080, debug=True)