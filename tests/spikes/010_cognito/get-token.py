#!/usr/bin/env python3
"""
FRANK Platform - Quick Token Generator

Simple command-line tool to get authentication tokens for testing.

Usage:
  python get-token.py core_member
  python get-token.py contributor  
  python get-token.py --help

Copyright (c) 2025 Schuberg Philis B.V.
SPDX-License-Identifier: Apache-2.0
"""

import requests
import argparse
import sys

MOCK_COGNITO_URL = "http://localhost:8100"
DEFAULT_PASSWORD = "TempPass123!"

# User mapping
USER_MAPPING = {
    "observer": "testuser_observer",
    "contributor": "testuser_contributor", 
    "partner": "testuser_partner",
    "core_member": "testuser_core_member",
    "core": "testuser_core_member",  # alias
}

def get_token(user_type: str, password: str = DEFAULT_PASSWORD) -> str:
    """Get token for a specific user type"""
    
    # Map user type to username
    username = USER_MAPPING.get(user_type.lower())
    if not username:
        print(f"❌ Unknown user type: {user_type}")
        print(f"   Available types: {', '.join(USER_MAPPING.keys())}")
        sys.exit(1)
    
    print(f"🔐 Getting token for {user_type} ({username})...")
    
    try:
        # Check if Mock Cognito is running
        health_response = requests.get(f"{MOCK_COGNITO_URL}/health", timeout=3)
        if health_response.status_code != 200:
            print(f"❌ Mock Cognito service is not healthy")
            sys.exit(1)
    except requests.exceptions.RequestException:
        print(f"❌ Mock Cognito service is not running at {MOCK_COGNITO_URL}")
        print(f"   Start it with: python mock_cognito.py")
        sys.exit(1)
    
    try:
        # Get token
        response = requests.post(
            f"{MOCK_COGNITO_URL}/auth/login",
            json={"username": username, "password": password},
            timeout=10
        )
        
        if response.status_code == 200:
            token_data = response.json()
            access_token = token_data["access_token"]
            
            print(f"✅ Token obtained successfully!")
            print(f"\n📋 Token Details:")
            print(f"   Username: {username}")
            print(f"   User Type: {user_type}")
            print(f"   Token: {access_token}")
            
            print(f"\n🚀 Usage Examples:")
            print(f"# Export as environment variable:")
            print(f"export TOKEN='{access_token}'")
            print(f"")
            print(f"# Test with curl:")
            print(f"curl -H \"Authorization: Bearer $TOKEN\" http://localhost:8000/user-info")
            print(f"curl -H \"Authorization: Bearer $TOKEN\" http://localhost:8000/{user_type}")
            print(f"")
            print(f"# Copy token to clipboard (macOS):")
            print(f"echo '{access_token}' | pbcopy")
            
            return access_token
        else:
            print(f"❌ Failed to get token: {response.status_code}")
            print(f"   Error: {response.text}")
            sys.exit(1)
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(
        description="Get authentication tokens for FRANK API testing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python get-token.py core_member    # Get core member token
  python get-token.py contributor    # Get contributor token
  python get-token.py observer       # Get observer token
  python get-token.py partner        # Get partner token

Available user types:
  observer, contributor, partner, core_member, core (alias for core_member)

The token will be printed to stdout and can be used with:
  curl -H "Authorization: Bearer TOKEN" http://localhost:8000/endpoint
        """
    )
    
    parser.add_argument(
        "user_type", 
        help="Type of user to get token for (observer, contributor, partner, core_member)"
    )
    parser.add_argument(
        "--password", 
        default=DEFAULT_PASSWORD,
        help=f"Password for the user (default: {DEFAULT_PASSWORD})"
    )
    parser.add_argument(
        "--url",
        default=MOCK_COGNITO_URL, 
        help=f"Mock Cognito URL (default: {MOCK_COGNITO_URL})"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Only output the token (useful for scripts)"
    )
    
    args = parser.parse_args()
    
    # Update global URL if specified
    global MOCK_COGNITO_URL
    MOCK_COGNITO_URL = args.url
    
    token = get_token(args.user_type, args.password)
    
    if args.quiet:
        # Only output token to stdout
        import sys
        sys.stdout.write(token + '\n')

if __name__ == "__main__":
    main()