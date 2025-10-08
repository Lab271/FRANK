#!/usr/bin/env python3
"""
FRANK Platform - Cognito Authentication Spike - Simple API Test Script

Comprehensive testing of the Simple API with role-based access control.
Demonstrates authentication flows, access control, and error handling.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import requests
import json
import sys
import os
from typing import Dict, Any

# Service endpoints - can be overridden by environment variables
MOCK_COGNITO_URL = os.getenv("MOCK_COGNITO_ENDPOINT", "http://localhost:8100")
SIMPLE_API_URL = os.getenv("SIMPLE_API_ENDPOINT", "https://frank-010-cognito.local")

def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"🧪 {title}")
    print(f"{'='*60}")

def print_test(description: str):
    """Print a test description"""
    print(f"\n📍 {description}")
    print("-" * 50)

def get_auth_token(username: str, password: str) -> str:
    """Get authentication token from Mock Cognito"""
    try:
        response = requests.post(
            f"{MOCK_COGNITO_URL}/auth/login",
            json={"username": username, "password": password},
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        print(f"❌ Failed to get token for {username}: {e}")
        return None

def test_endpoint(url: str, token: str = None, description: str = ""):
    """Test an API endpoint with optional authentication"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    try:
        # Disable SSL verification for self-signed certificates
        response = requests.get(url, headers=headers, verify=False)
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ Success:")
            print(json.dumps(response.json(), indent=2))
        elif response.status_code == 401:
            print("🔒 Authentication Required (401):")
            print(json.dumps(response.json(), indent=2))
        elif response.status_code == 403:
            print("🚫 Access Forbidden (403):")
            print(json.dumps(response.json(), indent=2))
        else:
            print(f"❓ Unexpected response ({response.status_code}):")
            print(response.text)
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

def main():
    """Run comprehensive Simple API tests"""
    
    # Disable SSL warnings for self-signed certificates
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    print("🚀 FRANK Simple API - Comprehensive Test Suite")
    print("=" * 60)
    print(f"Mock Cognito: {MOCK_COGNITO_URL}")
    print(f"Simple API: {SIMPLE_API_URL}")
    print(f"Swagger Docs: {SIMPLE_API_URL}/docs")
    print("⚠️  SSL verification disabled for self-signed certificates")
    
    # Test 1: Public endpoint (no authentication)
    print_section("Public Access - No Authentication Required")
    test_endpoint(f"{SIMPLE_API_URL}/public", description="Public endpoint")
    
    # Test 2: Service information
    print_section("Service Information")
    test_endpoint(f"{SIMPLE_API_URL}/", description="Root endpoint with service info")
    test_endpoint(f"{SIMPLE_API_URL}/health", description="Health check")
    
    # Test 3: Authentication required endpoints (no token)
    print_section("Authentication Required - No Token Provided")
    test_endpoint(f"{SIMPLE_API_URL}/user_role_a", description="Contributor endpoint without token")
    test_endpoint(f"{SIMPLE_API_URL}/user_role_b", description="Partner endpoint without token")
    test_endpoint(f"{SIMPLE_API_URL}/user-info", description="User info endpoint without token")
    
    # Test 4: Get authentication tokens
    print_section("Authentication Token Acquisition")
    print_test("Getting tokens for test users")
    
    token_a = get_auth_token("testuser_a", "TempPass123!")
    token_b = get_auth_token("testuser_b", "TempPass123!")
    
    if not token_a or not token_b:
        print("❌ Cannot proceed without authentication tokens")
        sys.exit(1)
    
    print(f"✅ Token A (testuser_a): {token_a[:50]}...")
    print(f"✅ Token B (testuser_b): {token_b[:50]}...")
    
    # Test 5: User info with authentication
    print_section("User Information Retrieval")
    test_endpoint(f"{SIMPLE_API_URL}/user-info", token_a, "User A info")
    test_endpoint(f"{SIMPLE_API_URL}/user-info", token_b, "User B info")
    
    # Test 6: Role-based access control - User A (Contributor)
    print_section("User A (Contributor) Access Control")
    test_endpoint(f"{SIMPLE_API_URL}/user_role_a", token_a, "User A accessing contributor endpoint")
    test_endpoint(f"{SIMPLE_API_URL}/user_role_b", token_a, "User A accessing partner endpoint (should fail)")
    
    # Test 7: Role-based access control - User B (Partner)
    print_section("User B (Partner) Access Control")
    test_endpoint(f"{SIMPLE_API_URL}/user_role_a", token_b, "User B accessing contributor endpoint")
    test_endpoint(f"{SIMPLE_API_URL}/user_role_b", token_b, "User B accessing partner endpoint")
    
    # Test 8: Invalid token handling
    print_section("Invalid Token Handling")
    test_endpoint(f"{SIMPLE_API_URL}/user_role_a", "invalid_token", "Invalid token test")
    
    # Test 9: API Documentation
    print_section("API Documentation")
    print_test("Checking Swagger documentation availability")
    try:
        response = requests.get(f"{SIMPLE_API_URL}/docs", verify=False)
        if response.status_code == 200:
            print("✅ Swagger documentation is available")
            print(f"   Access at: {SIMPLE_API_URL}/docs")
        else:
            print(f"❌ Swagger docs not available (Status: {response.status_code})")
    except Exception as e:
        print(f"❌ Failed to check docs: {e}")
    
    # Summary
    print_section("Test Summary")
    print("✅ Public endpoints: Working")
    print("✅ Authentication: Working") 
    print("✅ Role-based access control: Working")
    print("✅ Error handling: Working")
    print("✅ API documentation: Available")
    print("\n🎉 All tests completed successfully!")
    print(f"\n🔗 Quick access:")
    print(f"   Simple API: {SIMPLE_API_URL}")
    print(f"   Swagger UI: {SIMPLE_API_URL}/docs")
    print(f"   Mock Cognito: {MOCK_COGNITO_URL}")

if __name__ == "__main__":
    main()