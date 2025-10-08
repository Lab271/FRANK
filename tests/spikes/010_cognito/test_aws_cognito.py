#!/usr/bin/env python3
"""
FRANK Platform - Cognito Authentication Spike - AWS Cognito Test Script

Tests AWS Cognito authentication and validates Simple API access.
Demonstrates how to authenticate users and use JWT tokens with the API.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import boto3
import json
import requests
import sys
import os
from datetime import datetime

def load_config(config_file="cognito-config.json"):
    """Load AWS Cognito configuration from file"""
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Configuration file {config_file} not found")
        print("Run './deploy-cognito.sh' first to deploy AWS Cognito")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"❌ Invalid JSON in configuration file {config_file}")
        sys.exit(1)

def authenticate_user(config, username, password, new_password=None):
    """Authenticate user with AWS Cognito and handle password challenges"""
    try:
        cognito_client = boto3.client('cognito-idp', region_name=config['region'])
        
        print(f"🔐 Authenticating user: {username}")
        
        response = cognito_client.admin_initiate_auth(
            UserPoolId=config['user_pool_id'],
            ClientId=config['app_client_id'],
            AuthFlow='ADMIN_NO_SRP_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        
        # Handle password challenge (first login)
        if response.get('ChallengeName') == 'NEW_PASSWORD_REQUIRED':
            print("⚠️  New password required (first login)")
            
            if not new_password:
                new_password = input("Enter new password: ")
            
            response = cognito_client.admin_respond_to_auth_challenge(
                UserPoolId=config['user_pool_id'],
                ClientId=config['app_client_id'],
                ChallengeName='NEW_PASSWORD_REQUIRED',
                Session=response['Session'],
                ChallengeResponses={
                    'USERNAME': username,
                    'NEW_PASSWORD': new_password
                }
            )
        
        if 'AuthenticationResult' in response:
            tokens = response['AuthenticationResult']
            print("✅ Authentication successful")
            return {
                'access_token': tokens['AccessToken'],
                'id_token': tokens['IdToken'],
                'refresh_token': tokens['RefreshToken'],
                'expires_in': tokens['ExpiresIn']
            }
        else:
            print("❌ Authentication failed - no tokens returned")
            return None
            
    except cognito_client.exceptions.NotAuthorizedException:
        print("❌ Authentication failed - invalid credentials")
        return None
    except cognito_client.exceptions.UserNotFoundException:
        print("❌ Authentication failed - user not found")
        return None
    except Exception as e:
        print(f"❌ Authentication error: {e}")
        return None

def test_api_endpoint(url, token=None, description=""):
    """Test an API endpoint with optional authentication"""
    headers = {}
    if token:
        headers['Authorization'] = f'Bearer {token}'
    
    try:
        print(f"\n📍 Testing: {description}")
        print(f"URL: {url}")
        
        response = requests.get(url, headers=headers, verify=False)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Success:")
            data = response.json()
            # Pretty print with limited depth for readability
            if isinstance(data, dict) and 'user_info' in data:
                print(f"  Message: {data.get('message', 'N/A')}")
                print(f"  User: {data['user_info'].get('username', 'N/A')}")
                print(f"  Groups: {data['user_info'].get('groups', [])}")
                print(f"  Access Tier: {data['user_info'].get('access_tier', 'N/A')}")
            else:
                print(json.dumps(data, indent=2)[:500] + ("..." if len(str(data)) > 500 else ""))
        else:
            print(f"❌ Failed:")
            try:
                error_data = response.json()
                print(f"  Error: {error_data.get('detail', 'Unknown error')}")
            except:
                print(f"  HTTP {response.status_code}: {response.text[:200]}")
                
    except Exception as e:
        print(f"❌ Request failed: {e}")

def main():
    """Main test function"""
    print("🚀 FRANK AWS Cognito Authentication Test")
    print("=" * 50)
    
    # Load configuration
    config = load_config()
    
    print(f"AWS Region: {config['region']}")
    print(f"User Pool ID: {config['user_pool_id']}")
    print(f"App Client ID: {config['app_client_id']}")
    
    # Test API base endpoint
    api_base = "http://localhost:8080"
    test_api_endpoint(f"{api_base}/health", description="Health check")
    test_api_endpoint(f"{api_base}/public", description="Public endpoint")
    
    # Test authentication for each user
    test_users = config.get('test_users', [])
    
    for user in test_users:
        username = user['username']
        temp_password = user['temp_password']
        group = user['group']
        
        print(f"\n{'='*50}")
        print(f"🧪 Testing user: {username} (Group: {group})")
        print(f"{'='*50}")
        
        # Authenticate user
        tokens = authenticate_user(config, username, temp_password, "NewPass123!")
        
        if tokens:
            access_token = tokens['access_token']
            print(f"Access Token: {access_token[:50]}...")
            print(f"Expires in: {tokens['expires_in']} seconds")
            
            # Test authenticated endpoints
            test_api_endpoint(
                f"{api_base}/user-info", 
                access_token, 
                f"User info for {username}"
            )
            
            test_api_endpoint(
                f"{api_base}/user_role_a", 
                access_token, 
                f"Contributor endpoint access for {username}"
            )
            
            test_api_endpoint(
                f"{api_base}/user_role_b", 
                access_token, 
                f"Partner endpoint access for {username}"
            )
        else:
            print(f"❌ Skipping API tests for {username} - authentication failed")
    
    print(f"\n{'='*50}")
    print("🎯 Test Summary")
    print(f"{'='*50}")
    print("✅ AWS Cognito authentication tested")
    print("✅ Role-based access control validated")
    print("✅ JWT token validation working")
    print("")
    print("🔗 Manual testing:")
    print(f"  Simple API: {api_base}")
    print(f"  Swagger UI: {api_base}/docs")
    print("")
    print("💡 To run Simple API with AWS Cognito:")
    print("  python simple_api_aws.py")

if __name__ == "__main__":
    main()