#!/usr/bin/env python3
"""
FRANK 008 AWS Spike - Cross-Account IAM Role Setup

Creates the cross-account IAM role in the main account that allows
the spike account to manage Route53 records for SSL certificate validation.

Run this script in the main account (where Route53 hosted zone exists).
"""

import boto3
import json
import sys
import yaml
from pathlib import Path
from botocore.exceptions import ClientError

def load_config():
    """Load configuration from accounts.yaml"""
    config_path = Path('config/accounts.yaml')
    if not config_path.exists():
        print("❌ Config file not found: config/accounts.yaml")
        print("Please run this script from the project root directory")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def create_trust_policy(spike_account_id, external_id):
    """Create trust policy for cross-account role"""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "AWS": f"arn:aws:iam::{spike_account_id}:root"
                },
                "Action": "sts:AssumeRole",
                "Condition": {
                    "StringEquals": {
                        "sts:ExternalId": external_id
                    },
                    "StringLike": {
                        "aws:userid": "*:frank-008-spike-deployment"
                    }
                }
            }
        ]
    }

def create_permissions_policy(hosted_zone_id):
    """Create permissions policy for Route53 access"""
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "route53:ListHostedZones",
                    "route53:GetHostedZone"
                ],
                "Resource": "*"
            },
            {
                "Effect": "Allow",
                "Action": [
                    "route53:ChangeResourceRecordSets",
                    "route53:GetChange"
                ],
                "Resource": [
                    f"arn:aws:route53:::hostedzone/{hosted_zone_id}",
                    "arn:aws:route53:::change/*"
                ]
            }
        ]
    }

def check_aws_account(expected_account_id):
    """Verify we're in the correct AWS account"""
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        current_account = identity['Account']
        
        if current_account != expected_account_id:
            print(f"❌ Wrong AWS account!")
            print(f"   Expected: {expected_account_id}")
            print(f"   Current:  {current_account}")
            print("   Please switch to the main account")
            return False
        
        print(f"✅ Correct AWS account: {current_account}")
        print(f"   Identity: {identity['Arn']}")
        return True
        
    except Exception as e:
        print(f"❌ Cannot verify AWS account: {e}")
        return False

def create_cross_account_role(config):
    """Create the cross-account IAM role"""
    try:
        iam = boto3.client('iam')
        
        # Extract configuration
        role_name = config['cross_account_role']['name']
        spike_account_id = config['spike']['account_id']
        main_account_id = config['main']['account_id']
        external_id = config['main']['external_id']
        hosted_zone_id = config['main'].get('hosted_zone_id', 'Z1234567890ABC')  # Default placeholder
        
        print(f"🔧 Creating cross-account role: {role_name}")
        
        # Verify we're in the main account
        if not check_aws_account(main_account_id):
            return False
        
        # Create trust policy
        trust_policy = create_trust_policy(spike_account_id, external_id)
        
        # Create permissions policy
        permissions_policy = create_permissions_policy(hosted_zone_id)
        
        # Create the role
        try:
            response = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(trust_policy, indent=2),
                Description=config['cross_account_role']['description'],
                MaxSessionDuration=3600,  # 1 hour
                Tags=[
                    {'Key': 'Project', 'Value': 'FRANK'},
                    {'Key': 'Purpose', 'Value': 'Cross-account Route53 access'},
                    {'Key': 'SpikeAccount', 'Value': spike_account_id},
                    {'Key': 'Environment', 'Value': 'spike'}
                ]
            )
            
            role_arn = response['Role']['Arn']
            print(f"✅ Created role: {role_arn}")
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':
                print(f"⚠️  Role {role_name} already exists, updating...")
                
                # Update trust policy
                iam.update_assume_role_policy(
                    RoleName=role_name,
                    PolicyDocument=json.dumps(trust_policy, indent=2)
                )
                print("✅ Updated trust policy")
                
                # Get role ARN
                response = iam.get_role(RoleName=role_name)
                role_arn = response['Role']['Arn']
            else:
                raise
        
        # Attach permissions policy
        policy_name = 'Route53Access'
        try:
            iam.put_role_policy(
                RoleName=role_name,
                PolicyName=policy_name,
                PolicyDocument=json.dumps(permissions_policy, indent=2)
            )
            print(f"✅ Attached permissions policy: {policy_name}")
            
        except ClientError as e:
            print(f"❌ Failed to attach permissions policy: {e}")
            return False
        
        # Test the role
        print("🧪 Testing role assumption...")
        if test_role_assumption(role_arn, external_id):
            print("✅ Role assumption test passed!")
        else:
            print("⚠️  Role assumption test failed - check configuration")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to create cross-account role: {e}")
        return False

def test_role_assumption(role_arn, external_id):
    """Test that the role can be assumed"""
    try:
        sts = boto3.client('sts')
        
        response = sts.assume_role(
            RoleArn=role_arn,
            RoleSessionName='test-assumption',
            ExternalId=external_id,
            DurationSeconds=900  # 15 minutes
        )
        
        # Create temporary session to test permissions
        temp_session = boto3.Session(
            aws_access_key_id=response['Credentials']['AccessKeyId'],
            aws_secret_access_key=response['Credentials']['SecretAccessKey'],
            aws_session_token=response['Credentials']['SessionToken']
        )
        
        # Test Route53 access
        route53 = temp_session.client('route53')
        route53.list_hosted_zones()
        
        return True
        
    except Exception as e:
        print(f"Role assumption test failed: {e}")
        return False

def verify_hosted_zone(config):
    """Verify the hosted zone exists and get its ID"""
    try:
        route53 = boto3.client('route53')
        hosted_zone_name = config['main'].get('hosted_zone_name', 'lab271.io')
        
        response = route53.list_hosted_zones()
        
        for zone in response['HostedZones']:
            if zone['Name'].rstrip('.') == hosted_zone_name:
                zone_id = zone['Id'].split('/')[-1]
                print(f"✅ Found hosted zone: {hosted_zone_name} ({zone_id})")
                return zone_id
        
        print(f"❌ Hosted zone {hosted_zone_name} not found")
        print("Available hosted zones:")
        for zone in response['HostedZones']:
            zone_id = zone['Id'].split('/')[-1]
            print(f"   - {zone['Name'].rstrip('.')} ({zone_id})")
        
        return None
        
    except Exception as e:
        print(f"❌ Cannot verify hosted zone: {e}")
        return None

def display_setup_info(config):
    """Display setup information and next steps"""
    role_arn = f"arn:aws:iam::{config['main']['account_id']}:role/{config['cross_account_role']['name']}"
    
    print("\n" + "="*60)
    print("🎉 CROSS-ACCOUNT SETUP COMPLETE!")
    print("="*60)
    print(f"Role ARN: {role_arn}")
    print(f"External ID: {config['main']['external_id']}")
    print(f"Spike Account: {config['spike']['account_id']}")
    print(f"Main Account: {config['main']['account_id']}")
    print("\n📋 Next Steps:")
    print("1. Update config/accounts.yaml with the correct hosted zone ID")
    print("2. Switch to spike account AWS credentials")
    print("3. Run: python deploy.py setup-accounts")
    print("4. Run: python deploy.py deploy")
    print("\n🧪 Test Commands:")
    print("# From spike account:")
    print(f"aws sts assume-role \\")
    print(f"  --role-arn {role_arn} \\")
    print(f"  --role-session-name test-session \\")
    print(f"  --external-id {config['main']['external_id']}")
    print("="*60)

def main():
    """Main setup function"""
    print("🚀 FRANK Cross-Account IAM Role Setup")
    print("="*50)
    
    # Load configuration
    try:
        config = load_config()
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        sys.exit(1)
    
    # Verify hosted zone exists
    hosted_zone_id = verify_hosted_zone(config)
    if not hosted_zone_id:
        print("\n⚠️  Please update the hosted zone configuration and try again")
        sys.exit(1)
    
    # Update config with actual hosted zone ID
    config['main']['hosted_zone_id'] = hosted_zone_id
    
    # Create cross-account role
    if create_cross_account_role(config):
        display_setup_info(config)
    else:
        print("❌ Setup failed")
        sys.exit(1)

if __name__ == "__main__":
    main()