#!/usr/bin/env python3
"""
FRANK Platform - Cognito Authentication Spike - Unified API Testing Script

Tests the unified simple_api_unified.py with both Mock Cognito and AWS Cognito modes.
Validates JWT token generation, user authentication, and role-based access control.

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import requests
import json
import os
import sys
import time
import argparse
from typing import Optional, List, Dict

# Configuration
SIMPLE_API_URL = "http://localhost:8000"
MOCK_COGNITO_URL = "http://localhost:8100"

def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def print_test(description: str):
    """Print a test description"""
    print(f"\n🧪 {description}")

def load_config():
    """Load configuration from mock service or fallback to JSON file"""
    try:
        response = requests.get(f"{MOCK_COGNITO_URL}/config", timeout=5)
        if response.status_code == 200:
            print("✅ Configuration loaded from mock service")
            return response.json()
    except requests.exceptions.RequestException:
        pass
    
    try:
        with open("cognito_config.json", "r") as f:
            print("✅ Configuration loaded from cognito_config.json")
            return json.load(f)
    except FileNotFoundError:
        print("❌ Cannot load configuration")
        return None

def get_auth_token(username: str, password: str, use_aws: bool = False) -> Optional[str]:
    """
    Get JWT token from appropriate Cognito service.
    
    Mock Cognito Users (all use password "TempPass123!"):
    - testuser_observer → observer group → AccessTier.OBSERVER
    - testuser_contributor → contributor group → AccessTier.CONTRIBUTOR  
    - testuser_partner → partner group → AccessTier.PARTNER
    - testuser_core_member → core_member group → AccessTier.CORE_MEMBER
    
    Example usage:
    token = get_auth_token("testuser_core_member", "TempPass123!")
    
    For manual testing:
    curl -X POST http://localhost:8100/auth/login \
         -H "Content-Type: application/json" \
         -d '{"username":"testuser_core_member","password":"TempPass123!"}'
    """
    if use_aws:
        # For AWS Cognito, you would typically use boto3 here
        # This is a placeholder for AWS Cognito token generation
        print(f"⚠️  AWS Cognito token generation not implemented in test script")
        print(f"   Use get-tokens-guide.py for AWS Cognito examples")
        return None
    else:
        # Mock Cognito token generation
        try:
            response = requests.post(
                f"{MOCK_COGNITO_URL}/auth/login",
                json={"username": username, "password": password},
                timeout=10
            )
            response.raise_for_status()
            token = response.json()["access_token"]
            print(f"✅ Got token for {username}: {token[:30]}...")
            return token
        except Exception as e:
            print(f"❌ Failed to get token for {username}: {e}")
            return None

def test_endpoint(url: str, token: Optional[str] = None, description: str = ""):
    """Test an API endpoint with optional authentication"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    print(f"🔗 Testing: {description}")
    print(f"   URL: {url}")
    print(f"   Auth: {'Yes' if token else 'No'}")
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Success (200): {data.get('message', 'No message')}")
            if 'access_tier' in data.get('user_info', {}):
                print(f"      Access Tier: {data['user_info']['access_tier']}")
            if 'provider' in data.get('user_info', {}):
                print(f"      Provider: {data['user_info']['provider']}")
        elif response.status_code == 401:
            print(f"   🔒 Unauthorized (401): Authentication required")
        elif response.status_code == 403:
            print(f"   🚫 Forbidden (403): Insufficient permissions")
        else:
            print(f"   ❌ Error ({response.status_code}): {response.text[:100]}")
    except requests.exceptions.RequestException as e:
        print(f"   ❌ Network error: {e}")

def test_api_health():
    """Test API health endpoint"""
    print_section("API Health Check")
    test_endpoint(f"{SIMPLE_API_URL}/health", description="API Health Check")

def test_public_endpoints():
    """Test public endpoints"""
    print_section("Public Endpoints")
    
    test_endpoint(f"{SIMPLE_API_URL}/", description="Root endpoint")
    test_endpoint(f"{SIMPLE_API_URL}/public", description="Public endpoint")

def test_protected_endpoints_without_auth():
    """Test protected endpoints without authentication"""
    print_section("Protected Endpoints - No Authentication")
    
    test_endpoint(f"{SIMPLE_API_URL}/observer", description="Observer endpoint without token")
    test_endpoint(f"{SIMPLE_API_URL}/contributor", description="Contributor endpoint without token")
    test_endpoint(f"{SIMPLE_API_URL}/partner", description="Partner endpoint without token")
    test_endpoint(f"{SIMPLE_API_URL}/core_member", description="Core member endpoint without token")

def test_access_control_mock():
    """Test access control with Mock Cognito"""
    print_section("Access Control Testing - Mock Cognito")
    
    config = load_config()
    if not config:
        print("❌ Cannot load configuration for Mock Cognito testing")
        return
    
    # Get tokens for different users
    tokens = {}
    test_users = {
        "testuser_observer": "observer",
        "testuser_contributor": "contributor", 
        "testuser_partner": "partner",
        "testuser_core_member": "core_member"
    }
    
    for username, expected_tier in test_users.items():
        token = get_auth_token(username, "TempPass123!", use_aws=False)
        if token:
            tokens[expected_tier] = token
            print(f"✅ Token for {username} ({expected_tier}): {token[:50]}...")
        else:
            print(f"❌ Failed to get token for {username}")
    
    if not tokens:
        print("❌ No tokens available for testing")
        return
    
    # Test user info endpoints
    print("\n🔍 Testing user info endpoints:")
    for tier, token in tokens.items():
        test_endpoint(f"{SIMPLE_API_URL}/user-info", token, f"{tier.title()} user info")
    
    # Test access control hierarchy
    endpoints = ["observer", "contributor", "partner", "core_member"]
    
    for user_tier, token in tokens.items():
        print(f"\n🔐 Testing access control for {user_tier.title()} user:")
        for endpoint in endpoints:
            should_succeed = get_access_level_value(user_tier) >= get_access_level_value(endpoint)
            expectation = "should succeed" if should_succeed else "should fail"
            test_endpoint(
                f"{SIMPLE_API_URL}/{endpoint}", 
                token, 
                f"{user_tier.title()} accessing {endpoint} endpoint ({expectation})"
            )

def get_access_level_value(tier: str) -> int:
    """Get numeric value for access tier for comparison"""
    tier_values = {
        "observer": 1,
        "contributor": 2, 
        "partner": 3,
        "core_member": 4
    }
    return tier_values.get(tier, 0)

def test_invalid_token():
    """Test invalid token handling"""
    print_section("Invalid Token Handling")
    test_endpoint(f"{SIMPLE_API_URL}/contributor", "invalid_token", "Invalid token test")

def test_api_documentation():
    """Test API documentation availability"""
    print_section("API Documentation")
    print_test("Checking Swagger documentation availability")
    
    try:
        response = requests.get(f"{SIMPLE_API_URL}/docs", timeout=10)
        if response.status_code == 200:
            print("✅ Swagger documentation available at /docs")
        else:
            print(f"❌ Swagger documentation not available: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error accessing documentation: {e}")

def main():
    """Main test function"""
    parser = argparse.ArgumentParser(description="Test FRANK Simple API - Unified")
    parser.add_argument("--api-url", type=str, default="http://localhost:8000",
                       help="API base URL (default: http://localhost:8000)")
    parser.add_argument("--mock-cognito-url", type=str, default="http://localhost:8100", 
                       help="Mock Cognito URL (default: http://localhost:8100)")
    parser.add_argument("--test-aws", action="store_true",
                       help="Test AWS Cognito mode (requires AWS setup)")
    
    args = parser.parse_args()
    
    global SIMPLE_API_URL, MOCK_COGNITO_URL
    SIMPLE_API_URL = args.api_url
    MOCK_COGNITO_URL = args.mock_cognito_url
    
    print("🚀 FRANK Simple API - Unified Testing")
    print(f"   API URL: {SIMPLE_API_URL}")
    print(f"   Mock Cognito URL: {MOCK_COGNITO_URL}")
    print(f"   Testing AWS mode: {args.test_aws}")
    
    # Basic connectivity tests
    test_api_health()
    test_public_endpoints()
    test_protected_endpoints_without_auth()
    
    # Authentication tests
    if not args.test_aws:
        test_access_control_mock()
    else:
        print_section("AWS Cognito Testing")
        print("⚠️  AWS Cognito testing requires manual setup and is not fully automated")
        print("   Please ensure:")
        print("   1. AWS credentials are configured")
        print("   2. User Pool ID and App Client ID are set")
        print("   3. Test users exist in the User Pool")
        print("   4. The API is running with --use-aws flag")
    
    # Error handling tests
    test_invalid_token()
    
    # Documentation tests
    test_api_documentation()
    
    print("\n✅ Testing completed!")
    print(f"   View API documentation: {SIMPLE_API_URL}/docs")

if __name__ == "__main__":
    main()