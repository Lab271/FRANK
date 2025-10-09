#!/usr/bin/env python3
"""
FRANK Platform - Token Generation Guide and Examples

Shows how to get authentication tokens for different user types in both 
Mock Cognito and AWS Cognito scenarios.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import requests
import json
import boto3
import sys
from typing import Optional

# Configuration
MOCK_COGNITO_URL = "http://localhost:8100"

def get_mock_cognito_token(username: str, password: str = "TempPass123!") -> Optional[str]:
    """
    Get a JWT token from Mock Cognito service for any user.
    
    Available users in Mock Cognito:
    - testuser_observer (observer group)
    - testuser_contributor (contributor group)  
    - testuser_partner (partner group)
    - testuser_core_member (core_member group)
    """
    print(f"🔐 Getting token for {username} from Mock Cognito...")
    
    try:
        response = requests.post(
            f"{MOCK_COGNITO_URL}/auth/login",
            json={"username": username, "password": password},
            timeout=10
        )
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data["access_token"]
            print(f"✅ Token obtained successfully")
            print(f"   Token (first 50 chars): {access_token[:50]}...")
            
            # Show user info from token
            user_info_response = requests.get(
                f"{MOCK_COGNITO_URL}/auth/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10
            )
            
            if user_info_response.status_code == 200:
                user_info = user_info_response.json()
                print(f"   Username: {user_info.get('username')}")
                print(f"   Groups: {user_info.get('cognito:groups', [])}")
                print(f"   Email: {user_info.get('email')}")
            
            return access_token
        else:
            print(f"❌ Failed to get token: {response.status_code}")
            print(f"   Error: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        return None

def get_aws_cognito_token(username: str, password: str, user_pool_id: str, client_id: str, region: str = "eu-central-1") -> Optional[str]:
    """
    Get a JWT token from AWS Cognito using boto3.
    
    Note: This requires that the user exists in your AWS Cognito User Pool
    and has the appropriate group membership.
    """
    print(f"🔐 Getting token for {username} from AWS Cognito...")
    
    try:
        # Initialize Cognito client
        cognito_client = boto3.client('cognito-idp', region_name=region)
        
        # Authenticate user and get tokens
        response = cognito_client.admin_initiate_auth(
            UserPoolId=user_pool_id,
            ClientId=client_id,
            AuthFlow='ADMIN_NO_SRP_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )
        
        if 'AuthenticationResult' in response:
            auth_result = response['AuthenticationResult']
            access_token = auth_result['AccessToken']
            
            print(f"✅ Token obtained successfully")
            print(f"   Token (first 50 chars): {access_token[:50]}...")
            
            # Get user info
            user_response = cognito_client.get_user(AccessToken=access_token)
            user_attrs = {attr['Name']: attr['Value'] for attr in user_response['UserAttributes']}
            
            # Get user groups
            groups_response = cognito_client.admin_list_groups_for_user(
                UserPoolId=user_pool_id,
                Username=username
            )
            groups = [group['GroupName'] for group in groups_response['Groups']]
            
            print(f"   Username: {user_response['Username']}")
            print(f"   Groups: {groups}")
            print(f"   Email: {user_attrs.get('email', 'Not set')}")
            
            return access_token
        else:
            print(f"❌ Authentication failed: No AuthenticationResult in response")
            return None
            
    except Exception as e:
        print(f"❌ AWS Cognito error: {e}")
        return None

def test_token_with_api(token: str, endpoint: str = "http://localhost:8000") -> None:
    """Test the token against different API endpoints"""
    print(f"\n🧪 Testing token against API endpoints...")
    
    endpoints_to_test = [
        ("/user-info", "User Info"),
        ("/observer", "Observer Endpoint"),
        ("/contributor", "Contributor Endpoint"), 
        ("/partner", "Partner Endpoint"),
        ("/core_member", "Core Member Endpoint")
    ]
    
    for path, description in endpoints_to_test:
        try:
            response = requests.get(
                f"{endpoint}{path}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                access_tier = data.get('user_info', {}).get('access_tier') or data.get('access_tier')
                print(f"✅ {description}: SUCCESS (Access Tier: {access_tier})")
            elif response.status_code == 403:
                print(f"🚫 {description}: FORBIDDEN (insufficient permissions)")
            elif response.status_code == 401:
                print(f"🔒 {description}: UNAUTHORIZED (invalid token)")
            else:
                print(f"❌ {description}: ERROR ({response.status_code})")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ {description}: NETWORK ERROR ({e})")

def main():
    """Main demonstration function"""
    print("🚀 FRANK Platform - Token Generation Guide")
    print("=" * 60)
    
    # Check if Mock Cognito is running
    try:
        health_response = requests.get(f"{MOCK_COGNITO_URL}/health", timeout=5)
        if health_response.status_code == 200:
            print("✅ Mock Cognito service is running")
            mock_available = True
        else:
            print("❌ Mock Cognito service is not responding correctly")
            mock_available = False
    except requests.exceptions.RequestException:
        print("❌ Mock Cognito service is not running")
        mock_available = False
    
    if mock_available:
        print(f"\n📋 Available Mock Cognito Users:")
        users = [
            ("testuser_observer", "observer", "Observer level access"),
            ("testuser_contributor", "contributor", "Contributor level access"),
            ("testuser_partner", "partner", "Partner level access"),
            ("testuser_core_member", "core_member", "Core member level access (highest)")
        ]
        
        for username, group, description in users:
            print(f"  • {username} → {group} group → {description}")
        
        print(f"\n" + "="*60)
        print("🎯 EXAMPLE: Getting core_member token")
        print("="*60)
        
        # Get token for core_member user
        core_member_token = get_mock_cognito_token("testuser_core_member")
        
        if core_member_token:
            print(f"\n📋 How to use this token:")
            print(f"export CORE_MEMBER_TOKEN='{core_member_token}'")
            print(f"")
            print(f"# Test with curl:")
            print(f"curl -H \"Authorization: Bearer $CORE_MEMBER_TOKEN\" http://localhost:8000/core_member")
            print(f"")
            print(f"# Test with Python requests:")
            print(f"import requests")
            print(f"headers = {{'Authorization': 'Bearer {core_member_token[:20]}...'}}")
            print(f"response = requests.get('http://localhost:8000/core_member', headers=headers)")
            
            # Test the token against API if it's running
            try:
                api_health = requests.get("http://localhost:8000/health", timeout=3)
                if api_health.status_code == 200:
                    test_token_with_api(core_member_token)
                else:
                    print(f"\n⚠️  API is not running at http://localhost:8000")
                    print(f"   Start it with: python simple_api_unified.py")
            except requests.exceptions.RequestException:
                print(f"\n⚠️  API is not running at http://localhost:8000")
                print(f"   Start it with: python simple_api_unified.py")
        
        print(f"\n" + "="*60)
        print("🔍 OTHER EXAMPLES")
        print("="*60)
        
        # Show examples for other users
        other_users = ["testuser_observer", "testuser_contributor", "testuser_partner"]
        for username in other_users:
            token = get_mock_cognito_token(username)
            if token:
                print(f"   {username} token: {token[:30]}...")
    
    print(f"\n" + "="*60)
    print("🏢 AWS COGNITO EXAMPLE")
    print("="*60)
    print("For AWS Cognito, you need to:")
    print("1. Get your User Pool ID and App Client ID:")
    print("   ./get-cognito-ids.sh")
    print("")
    print("2. Create users in AWS Cognito User Pool with appropriate groups")
    print("3. Use the get_aws_cognito_token() function:")
    print("")
    print("# Example code:")
    print("token = get_aws_cognito_token(")
    print("    username='your-aws-username',")
    print("    password='your-aws-password',") 
    print("    user_pool_id='eu-central-1_xxxxxxxxx',")
    print("    client_id='xxxxxxxxxxxxxxxxxx'")
    print(")")
    
    print(f"\n✅ Guide completed!")

if __name__ == "__main__":
    main()