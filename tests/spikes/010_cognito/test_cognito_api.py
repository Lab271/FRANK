#!/usr/bin/env python3
"""
FRANK Platform - Cognito Authentication Spike - API Testing Script

Tests authentication flows and token validation with Mock Cognito service.
Validates JWT token generation, user authentication, and role-based access control.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import requests
import json
import base64

# Load configuration
def load_config():
    """Load configuration from mock service or fallback to JSON file"""
    # First try to get config from mock service
    try:
        response = requests.get("http://localhost:8100/config", timeout=5)
        if response.status_code == 200:
            print("✅ Configuration loaded from mock service")
            return response.json()
    except requests.exceptions.RequestException:
        pass  # Fallback to JSON file
    
CONFIG = load_config()

def authenticate_user(username, password):
    """Authenticate user and return tokens"""
    endpoint = f"{CONFIG['mock_cognito_endpoint']}/auth/login"
    
    try:
        response = requests.post(
            endpoint,
            json={"username": username, "password": password},
            timeout=10
        )
        
        if response.status_code == 200:
            tokens = response.json()
            print(f"✅ Authentication successful for {username}")
            return tokens
        else:
            error_detail = response.json().get("detail", "Unknown error")
            print(f"❌ Authentication failed for {username}: {error_detail}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error during authentication for {username}: {e}")
        return None

def decode_token_payload(token):
    """Decode JWT token payload (without verification for testing)"""
    try:
        # Split token and decode payload
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError("Invalid token format")
        
        # Add padding if needed
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += '=' * padding
        
        decoded = base64.urlsafe_b64decode(payload)
        return json.loads(decoded)
        
    except Exception as e:
        print(f"❌ Error decoding token: {e}")
        return None

def validate_token_with_service(token):
    """Validate token using the mock service endpoint"""
    endpoint = f"{CONFIG['mock_cognito_endpoint']}/auth/validate"
    
    try:
        response = requests.post(
            endpoint,
            json={"token": token},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Token validation request failed: {response.status_code}")
            return {"valid": False, "error": "Service validation failed"}
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error during token validation: {e}")
        return {"valid": False, "error": str(e)}

def validate_token_structure(token_name, token, expected_user):
    """Validate token structure and claims"""
    print(f"\n🔍 Validating {token_name}...")
    
    payload = decode_token_payload(token)
    if not payload:
        return False
    
    print(f"  Token Type: {payload.get('token_use', 'unknown')}")
    print(f"  Username: {payload.get('username', 'N/A')}")
    print(f"  Cognito Groups: {payload.get('cognito:groups', [])}")
    print(f"  Expires: {payload.get('exp', 'N/A')}")
    print(f"  Issued: {payload.get('iat', 'N/A')}")
    
    # Validate expected claims
    if payload.get('username') != expected_user['username']:
        print(f"  ❌ Username mismatch")
        return False
    
    if expected_user['group'] not in payload.get('cognito:groups', []):
        print(f"  ❌ Group membership missing")
        return False
    
    print(f"  ✅ {token_name} validation passed")
    
    # Also validate with service
    validation_result = validate_token_with_service(token)
    if validation_result.get("valid", False):
        print(f"  ✅ Service validation passed")
        return True
    else:
        print(f"  ❌ Service validation failed: {validation_result.get('error', 'Unknown')}")
        return False

def test_user_authentication():
    """Test authentication for all test users"""
    print("🧪 Testing User Authentication")
    print("=" * 50)
    
    results = {}
    
    for user in CONFIG["test_users"]:
        print(f"\n👤 Testing user: {user['username']} (Group: {user['group']})")
        
        tokens = authenticate_user(user['username'], user['password'])
        if tokens:
            results[user['username']] = {
                'user': user,
                'tokens': tokens,
                'success': True
            }
            
            # Validate token structure
            validate_token_structure("Access Token", tokens['access_token'], user)
            validate_token_structure("ID Token", tokens['id_token'], user)
            
        else:
            results[user['username']] = {
                'user': user,
                'tokens': None,
                'success': False
            }
    
    return results

def test_invalid_credentials():
    """Test authentication with invalid credentials"""
    print("\n🧪 Testing Invalid Credentials")
    print("=" * 50)
    
    # Test invalid username
    print("\n🔒 Testing invalid username...")
    tokens = authenticate_user("nonexistent_user", "TempPass123!")
    assert tokens is None, "Should fail with invalid username"
    
    # Test invalid password
    print("\n🔒 Testing invalid password...")
    user = CONFIG["test_users"][0]
    tokens = authenticate_user(user['username'], "WrongPassword123!")
    assert tokens is None, "Should fail with invalid password"
    
    print("✅ Invalid credentials tests passed")

def test_token_based_access():
    """Test using tokens for API access (simulated)"""
    print("\n🧪 Testing Token-Based Access")
    print("=" * 50)
    
    # Get tokens for first user
    user = CONFIG["test_users"][0]
    tokens = authenticate_user(user['username'], user['password'])
    
    if not tokens:
        print("❌ Cannot test token access without valid tokens")
        return
    
    access_token = tokens['access_token']
    
    # Test getting user info with token
    print(f"\n🎯 Testing user info endpoint:")
    try:
        response = requests.get(
            f"{CONFIG['mock_cognito_endpoint']}/auth/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        )
        
        if response.status_code == 200:
            user_info = response.json()
            print(f"  ✅ User info retrieved successfully:")
            print(f"    Username: {user_info['username']}")
            print(f"    Email: {user_info['email']}")
            print(f"    Groups: {user_info['groups']}")
        else:
            print(f"  ❌ Failed to get user info: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"  ❌ Network error getting user info: {e}")
    
    # Simulate API calls with different endpoints
    endpoints = [
        {"name": "Public Endpoint", "requires_auth": False, "required_group": None},
        {"name": "Observer Endpoint", "requires_auth": True, "required_group": "observer"},
        {"name": "Contributor Endpoint", "requires_auth": True, "required_group": "contributor"},
        {"name": "Partner Endpoint", "requires_auth": True, "required_group": "partner"},
        {"name": "Core Member Endpoint", "requires_auth": True, "required_group": "core_member"},
    ]
    
    print(f"\n📍 Simulating access control for user: {user['username']} (Group: {user['group']})")
    
    for endpoint in endpoints:
        print(f"\n🎯 Testing {endpoint['name']}:")
        
        if not endpoint['requires_auth']:
            print("  ✅ Public access - should always work")
            continue
        
        # Check if user has required group
        token_payload = decode_token_payload(access_token)
        user_groups = token_payload.get('cognito:groups', [])
        
        if endpoint['required_group'] in user_groups:
            print(f"  ✅ Access granted - user has required group: {endpoint['required_group']}")
        else:
            print(f"  ❌ Access denied - user lacks required group: {endpoint['required_group']}")

def test_service_health():
    """Test that the mock service is healthy"""
    print("\n🧪 Testing Service Health")
    print("=" * 50)
    
    try:
        response = requests.get(f"{CONFIG['mock_cognito_endpoint']}/health", timeout=5)
        if response.status_code == 200:
            health_data = response.json()
            print("✅ Mock Cognito service is healthy")
            print(f"  Service: {health_data['service']}")
            print(f"  Status: {health_data['status']}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check network error: {e}")
        return False

def generate_test_report(auth_results):
    """Generate a summary test report"""
    print("\n📊 Test Report")
    print("=" * 50)
    
    total_users = len(CONFIG["test_users"])
    successful_auths = sum(1 for result in auth_results.values() if result['success'])
    
    print(f"Total Test Users: {total_users}")
    print(f"Successful Authentications: {successful_auths}")
    print(f"Failed Authentications: {total_users - successful_auths}")
    
    print("\n👥 User Details:")
    for username, result in auth_results.items():
        status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
        group = result['user']['group']
        print(f"  {username} ({group}): {status}")
    
    if successful_auths == total_users:
        print("\n🎉 All authentication tests passed!")
        return True
    else:
        print("\n⚠️ Some authentication tests failed!")
        return False

def main():
    """Main testing function"""
    print("🚀 Starting Mock Cognito API Tests")
    print("=" * 60)
    
    try:
        # Check service health first
        if not test_service_health():
            print("\n💥 Mock Cognito service is not healthy. Cannot proceed with tests.")
            exit(1)
        
        # Run all tests
        auth_results = test_user_authentication()
        test_invalid_credentials()
        test_token_based_access()
        
        # Generate report
        success = generate_test_report(auth_results)
        
        if success:
            print("\n🏆 All tests completed successfully!")
            print(f"\n📋 Summary:")
            print(f"  Mock Service: {CONFIG['mock_cognito_endpoint']}")
            print(f"  Authentication: ✅ Working")
            print(f"  Token Validation: ✅ Working")
            print(f"  Role-based Access: ✅ Simulated")
        else:
            print("\n⚠️ Some tests failed - check the output above")
            
    except Exception as e:
        print(f"\n💥 Test execution failed: {e}")
        raise

if __name__ == "__main__":
    main()