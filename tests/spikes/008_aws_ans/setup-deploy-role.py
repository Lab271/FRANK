#!/usr/bin/env python3
"""
FRANK Deployment Role Setup Script

Creates the standard FRANK deployment IAM role with appropriate permissions
for deploying FRANK infrastructure while maintaining security boundaries.
"""

import boto3
import json
import sys
import time
from pathlib import Path
from botocore.exceptions import ClientError

def get_account_id():
    """Get current AWS account ID"""
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        return identity['Account']
    except Exception as e:
        print(f"❌ Cannot get AWS account ID: {e}")
        sys.exit(1)

def deploy_role_stack(spike_account_id, main_account_id):
    """Deploy the FRANK deployment role using CloudFormation"""
    try:
        cfn = boto3.client('cloudformation')
        
        template_path = Path('templates/deployment-role.yaml')
        if not template_path.exists():
            print(f"❌ Template not found: {template_path}")
            print("Please run this script from the project root directory")
            sys.exit(1)
        
        # Read template
        with open(template_path, 'r') as f:
            template_body = f.read()
        
        stack_name = 'FRANK-DeploymentRole'
        
        print(f"🚀 Deploying {stack_name} stack...")
        
        # Check if stack exists
        try:
            cfn.describe_stacks(StackName=stack_name)
            stack_exists = True
            print(f"📝 Stack {stack_name} exists, updating...")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ValidationError':
                stack_exists = False
                print(f"📝 Stack {stack_name} does not exist, creating...")
            else:
                raise
        
        # Prepare parameters
        parameters = [
            {
                'ParameterKey': 'SpikeAccountId',
                'ParameterValue': spike_account_id
            },
            {
                'ParameterKey': 'MainAccountId',
                'ParameterValue': main_account_id
            },
            {
                'ParameterKey': 'ExternalId',
                'ParameterValue': 'frank-deployment-2025'
            },
            {
                'ParameterKey': 'CrossAccountExternalId', 
                'ParameterValue': 'frank-008-unique-external-id-2025'
            }
        ]
        
        # Common parameters
        common_params = {
            'StackName': stack_name,
            'TemplateBody': template_body,
            'Parameters': parameters,
            'Capabilities': ['CAPABILITY_NAMED_IAM'],
            'Tags': [
                {'Key': 'Project', 'Value': 'FRANK'},
                {'Key': 'Purpose', 'Value': 'Deployment role'},
                {'Key': 'ManagedBy', 'Value': 'CloudFormation'}
            ]
        }
        
        if stack_exists:
            # Update stack
            cf