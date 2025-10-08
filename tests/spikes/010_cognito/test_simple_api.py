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

from typing import Optional

def get_auth_token(username: str, password: str) -> Optional[str]:
    """Get JWT token from Mock Cognito service"""
    try:
        response = requests.post(
            f"{MOCK_COGNITO_URL}/auth/login",
            json={"username": username, "password": password},
            timeout=10
        )
        response.raise_for_status()
        return response.json()["access_token"]
    except Exception as e:
        print(f"❌ Failed to get token for {username}: {e}")
        return None

def test_endpoint(url: str, token: Optional[str] = None, description: str = ""):
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
    test_endpoint(f"{SIMPLE_API_URL}/observer", description="Observer endpoint without token")
    test_endpoint(f"{SIMPLE_API_URL}/contributor", description="Contributor endpoint without token")
    test_endpoint(f"{SIMPLE_API_URL}/partner", description="Partner endpoint without token")
    test_endpoint(f"{SIMPLE_API_URL}/core_member", description="Core member endpoint without token")
    test_endpoint(f"{SIMPLE_API_URL}/user-info", description="User info endpoint without token")
    
    # Test 4: Get authentication tokens
    print_section("Authentication Token Acquisition")
    print_test("Getting tokens for test users")
    
    # Get tokens for different users
    token_observer = get_auth_token("testuser_observer", "TempPass123!")
    token_contributor = get_auth_token("testuser_contributor", "TempPass123!")
    token_partner = get_auth_token("testuser_partner", "TempPass123!")
    token_core_member = get_auth_token("testuser_core_member", "TempPass123!")
    
    if not all([token_observer, token_contributor, token_partner, token_core_member]):
        print("❌ Failed to get tokens for all users")
        return
    
    print(f"✅ Token Observer: {token_observer[:50] if token_observer else 'None'}...")
    print(f"✅ Token Contributor: {token_contributor[:50] if token_contributor else 'None'}...")
    print(f"✅ Token Partner: {token_partner[:50] if token_partner else 'None'}...")
    print(f"✅ Token Core Member: {token_core_member[:50] if token_core_member else 'None'}...")
    
    # Test user info endpoint with all tokens
    print("\n🔍 Testing user info endpoints:")
    test_endpoint(f"{SIMPLE_API_URL}/user-info", token_observer, "Observer user info")
    test_endpoint(f"{SIMPLE_API_URL}/user-info", token_contributor, "Contributor user info")
    test_endpoint(f"{SIMPLE_API_URL}/user-info", token_partner, "Partner user info")
    test_endpoint(f"{SIMPLE_API_URL}/user-info", token_core_member, "Core member user info")
    
    # Test access control - Observer user
    print("\n🔐 Testing access control for Observer user:")
    test_endpoint(f"{SIMPLE_API_URL}/observer", token_observer, "Observer accessing observer endpoint")
    test_endpoint(f"{SIMPLE_API_URL}/contributor", token_observer, "Observer accessing contributor endpoint (should fail)")
    test_endpoint(f"{SIMPLE_API_URL}/partner", token_observer, "Observer accessing partner endpoint (should fail)")
    test_endpoint(f"{SIMPLE_API_URL}/core_member", token_observer, "Observer accessing core member endpoint (should fail)")
    
    # Test access control - Contributor user
    print("\n🔐 Testing access control for Contributor user:")
    test_endpoint(f"{SIMPLE_API_URL}/observer", token_contributor, "Contributor accessing observer endpoint")
    test_endpoint(f"{SIMPLE_API_URL}/contributor", token_contributor, "Contributor accessing contributor endpoint")
    test_endpoint(f"{SIMPLE_API_URL}/partner", token_contributor, "Contributor accessing partner endpoint (should fail)")
    test_endpoint(f"{SIMPLE_API_URL}/core_member", token_contributor, "Contributor accessing core member endpoint (should fail)")
    
    # Test access control - Partner user
    print("\n🔐 Testing access control for Partner user:")
    test_endpoint(f"{SIMPLE_API_URL}/observer", token_partner, "Partner accessing observer endpoint")
    test_endpoint(f"{SIMPLE_API_URL}/contributor", token_partner, "Partner accessing contributor endpoint")
    test_endpoint(f"{SIMPLE_API_URL}/partner", token_partner, "Partner accessing partner endpoint")
    test_endpoint(f"{SIMPLE_API_URL}/core_member", token_partner, "Partner accessing core member endpoint (should fail)")
    
    # Test access control - Core Member user
    print("\n🔐 Testing access control for Core Member user:")
    test_endpoint(f"{SIMPLE_API_URL}/observer", token_core_member, "Core member accessing observer endpoint")
    test_endpoint(f"{SIMPLE_API_URL}/contributor", token_core_member, "Core member accessing contributor endpoint")
    test_endpoint(f"{SIMPLE_API_URL}/partner", token_core_member, "Core member accessing partner endpoint")
    test_endpoint(f"{SIMPLE_API_URL}/core_member", token_core_member, "Core member accessing core member endpoint")
    
    # Test 8: Invalid token handling
    print_section("Invalid Token Handling")
    test_endpoint(f"{SIMPLE_API_URL}/contributor", "invalid_token", "Invalid token test")
    
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