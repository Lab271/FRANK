#!/usr/bin/env python3
"""
FRANK Platform - Cognito Authentication Spike - Setup Validation Script

Validates that Mock Cognito service is running and accessible.
Fetches configuration from the mock service and saves it for other test scripts.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import requests
import json
import time

# Mock Cognito configuration
MOCK_COGNITO_ENDPOINT = "http://localhost:8080"

def check_mock_cognito():
    """Check if mock Cognito service is running"""
    try:
        response = requests.get(f"{MOCK_COGNITO_ENDPOINT}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Mock Cognito service is running")
            return True
        else:
            print(f"❌ Mock Cognito service returned status: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Cannot connect to Mock Cognito service: {e}")
        return False

def get_available_users():
    """Get list of available test users from mock service"""
    try:
        response = requests.get(f"{MOCK_COGNITO_ENDPOINT}/auth/users", timeout=5)
        if response.status_code == 200:
            users_data = response.json()
            print("✅ Available test users:")
            for user in users_data["users"]:
                print(f"  - {user['username']} (Groups: {user['groups']}) - Email: {user['email']}")
            return users_data["users"]
        else:
            print(f"❌ Failed to get users: {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"❌ Error getting users: {e}")
        return []

def test_service_endpoints():
    """Test that all expected endpoints are available"""
    try:
        response = requests.get(f"{MOCK_COGNITO_ENDPOINT}/", timeout=5)
        if response.status_code == 200:
            service_info = response.json()
            print("✅ Mock Cognito service endpoints:")
            for endpoint_name, endpoint_path in service_info["endpoints"].items():
                print(f"  - {endpoint_name}: {endpoint_path}")
            return True
        else:
            print(f"❌ Failed to get service info: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Error getting service info: {e}")
        return False

def save_configuration():
    """Save configuration for test scripts by fetching from mock service"""
    try:
        response = requests.get(f"{MOCK_COGNITO_ENDPOINT}/config", timeout=5)
        if response.status_code == 200:
            config = response.json()
            
            with open("cognito_config.json", "w") as f:
                json.dump(config, f, indent=2)
            
            print("✅ Configuration fetched from mock service and saved to cognito_config.json")
            return True
        else:
            print(f"❌ Failed to get config from mock service: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching config from mock service: {e}")
        return False

def main():
    """Main setup function"""
    print("🚀 Setting up Mock Cognito validation...")
    
    # Wait a moment for services to be ready
    print("⏳ Waiting for services to be ready...")
    time.sleep(3)
    
    # Check if mock service is running
    if not check_mock_cognito():
        print("\n❌ Mock Cognito service is not available!")
        print("   Make sure to run: docker-compose up -d")
        exit(1)
    
    # Test endpoints
    if not test_service_endpoints():
        print("\n❌ Mock Cognito service endpoints are not working properly!")
        exit(1)
    
    # Get available users
    users = get_available_users()
    if not users:
        print("\n❌ No test users available!")
        exit(1)
    
    # Save configuration
    if not save_configuration():
        print("\n❌ Failed to fetch configuration from mock service!")
        exit(1)
    
    print("\n🎉 Mock Cognito setup validation completed!")
    print(f"Mock Cognito Service: {MOCK_COGNITO_ENDPOINT}")
    print("\nTest Users available:")
    for user in users:
        print(f"  - {user['username']} (Groups: {user['groups']})")
    
    print("\n📝 Next steps:")
    print("  1. Run: python test_cognito_api.py")
    print("  2. Test authentication flows")

if __name__ == "__main__":
    main()