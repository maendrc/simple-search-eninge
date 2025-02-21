import boto3
import os
import subprocess

DIR_PATH = os.path.dirname(os.path.realpath(__file__))

def generate_key(keyname="new_key"):
    """
    Generate a new .pem file with key pair in the same folder this file is located
    This function is not called in main because 
    """
    DIR_PATH = os.path.dirname(os.path.realpath(__file__))
    
    EC2 = boto3.client('ec2')
    key_pair = EC2.create_key_pair(KeyName=keyname)

    pem_path = os.path.join(DIR_PATH, f"{keyname}.pem")
    with open(pem_path, "w") as file:
        file.write(key_pair['KeyMaterial'])
    
    os.chmod(f"{pem_path}", 0o400)
    print(f".pem file generated at {pem_path}")


def create_security_group():
    """creating a security group called ece326-group10"""
    try:
        EC2 = boto3.client('ec2')
        return_val = EC2.create_security_group(
            GroupName='ece326-group10',
            Description='This Specific one is for Lab2'
        )
        print(f"Security Group created as {return_val['GroupId']}")
        return return_val['GroupId']
    except Exception as e:
        print(f"{e}")


def editing_group_premission(security_group_id):
    try:
        EC2 = boto3.client('ec2')
        EC2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpProtocol='icmp',
            FromPort=-1,
            ToPort=-1,
            CidrIp='0.0.0.0/0'
        )

        EC2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpProtocol='tcp',
            FromPort=22,
            ToPort=22,
            CidrIp='0.0.0.0/0'
        )

        EC2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpProtocol='tcp',
            FromPort=80,
            ToPort=80,
            CidrIp='0.0.0.0/0'
        )

        # this is for interaction beyond pinging, leaving 8080 port open
        EC2.authorize_security_group_ingress(
            GroupId=security_group_id,
            IpProtocol='tcp',
            FromPort=8080,
            ToPort=8080,
            CidrIp='0.0.0.0/0'
        )
    except Exception as e:
        print(f"{e}")


def creating_instance(secruityGroupId):
    """Create and ec2 instance and install pip/all prerequested requirement"""
    EC2 = boto3.client('ec2')

    install_script="""#!/bin/bash
    sudo apt update -y
    sudo apt install -y python3-pip
    pip3 install oauth2client
    pip3 install google-api-python-client
    pip3 install bottle
    pip3 install Beaker
    pip3 install boto3
    """

    return_val = EC2.run_instances(
        ImageId='ami-0866a3c8686eaeeba',
        MinCount=1,
        MaxCount=1,
        InstanceType='t2.micro',
        KeyName='my-key-pair',
        SecurityGroupIds=[secruityGroupId],
        UserData=install_script
    )

    instance_id = return_val['Instances'][0]['InstanceId']
    print(f"New instance ID: {instance_id}")
    return instance_id


def set_elastic_ip(instance_id, elastic_id):
    """Given an existing instance and elastic_id associated with an IP, configure this IP to this instance"""
    try:
        EC2 = boto3.client('ec2')
        return_val = EC2.associate_address(
            AllocationId=elastic_id,
            InstanceId=instance_id
        )
        return return_val
    except Exception as e:
        print(f"{e}")


def scp_frontend(instance_id):
    """
    Given instance id, scp frontend script to ec2
    This function will not run frontend automatically, as I don't see any mention of 
    this should be done in lab instruction
    """
    EC2 = boto3.client('ec2')

    return_val = EC2.describe_instances(InstanceIds=[instance_id])
    public_ip = return_val['Reservations'][0]['Instances'][0].get('PublicIpAddress')

    key_path = os.path.join(DIR_PATH, "my-key-pair.pem")
    frontend_file_path = os.path.join(DIR_PATH, "ece326_lab2_frontend.py")
    destination = f"ubuntu@{public_ip}:~"

    scp_command = ["scp", "-i", key_path, "-o", "StrictHostKeyChecking=no", frontend_file_path, destination]
    try:
        subprocess.run(scp_command, check=True)
    except Exception as e:
        print(f"{e}")


if __name__ == "__main__":
    generate_key("my-key-pair")
    new_group = create_security_group()
    editing_group_premission(new_group)

    instance_id = creating_instance(new_group)
    # set_elastic_ip(instance_id, "eipalloc-04aeba5c1d3a74725")
    scp_frontend(instance_id)