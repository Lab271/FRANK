"""
JWT Token Validation Testing with Mock Cognito

This test demonstrates JWT token validation strategies with the Mock Cognito service:

1. Fetch and use the current RSA private key from mock service (TESTING ONLY)
2. Create custom signed tokens for testing
3. Validate tokens using JWKS endpoint  
4. Validate fresh tokens from mock service
5. Test signature verification flows

Key Concepts Demonstrated:
- RSA key pair usage in JWT signing/verification
- JWKS (JSON Web Key Set) endpoint usage
- Token lifecycle (generation, validation, expiration)
- Proper testing patterns for JWT authentication

⚠️ IMPORTANT: The private key download endpoint (/debug/private-key) is for 
TESTING ONLY and should NEVER exist in production systems. It's provided here
to demonstrate JWT internals and testing patterns.

Why the hardcoded token failed:
- Mock Cognito generates NEW RSA keys on every startup
- Previously issued tokens were signed with OLD private keys
- When service restarts, old signatures can't be verified with new public keys
- Solution: Always use fresh tokens OR download current private key for testing
"""

import pytest
import jwt
from jwt import PyJWKClient
import json
import requests
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend

# Configuration
cognito_region = "eu-west-1"
cognito_user_pool_id = "eu-west-1_MOCKPOOL"
cognito_url = "http://localhost:8100"
jwks_url = f"{cognito_url}/{cognito_user_pool_id}/.well-known/jwks.json"


def print_section(title: str):
    """Print a formatted section header"""
    print(f"\n{'=' * 60}")
    print(f"=== {title}")
    print('=' * 60)


def print_success(message: str):
    """Print success message"""
    print(f"✅ {message}")


def print_error(message: str):
    """Print error message"""
    print(f"❌ {message}")


def print_info(message: str):
    """Print info message"""
    print(f"ℹ️  {message}")


def download_private_key():
    """
    Download the current RSA private key from mock service.
    
    ⚠️ THIS IS FOR TESTING ONLY - Never expose private keys in production!
    """
    print_section("1. Download Current RSA Private Key (TESTING ONLY)")
    
    try:
        response = requests.get(
            f"{cognito_url}/debug/private-key",
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            private_key_pem = data["private_key_pem"]
            kid = data["kid"]
            algorithm = data["algorithm"]
            
            print_success(f"Downloaded private key (kid: {kid}, algorithm: {algorithm})")
            print_info(data["warning"])
            
            # Load the private key
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode('utf-8'),
                password=None,
                backend=default_backend()
            )
            
            return private_key, kid, algorithm
        else:
            print_error(f"Failed to download private key: {response.status_code}")
            return None, None, None
            
    except Exception as e:
        print_error(f"Error downloading private key: {e}")
        return None, None, None


@pytest.fixture(scope="module")
def key_data():
    """
    Pytest fixture that downloads the private key and kid.
    Shared across all tests in the module.
    """
    private_key, kid, algorithm = download_private_key()
    if not private_key:
        pytest.skip("Mock Cognito service not available")
    return private_key, kid, algorithm


@pytest.fixture(scope="module")
def private_key(key_data):
    """Pytest fixture for the private key."""
    return key_data[0]


@pytest.fixture(scope="module")
def kid(key_data):
    """Pytest fixture for the key ID."""
    return key_data[1]


def create_custom_token(private_key, kid: str, username: str = "testuser_custom", 
                        groups: list = None, expired: bool = False):
    """
    Create a custom JWT token signed with the provided private key.
    
    This demonstrates how JWT tokens are created and signed.
    """
    if groups is None:
        groups = ["observer"]
    
    now = datetime.now(timezone.utc)
    
    # Create token payload matching Cognito format
    payload = {
        "sub": username,
        "cognito:groups": groups,
        "token_use": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1 if not expired else -1)).timestamp()),
        "client_id": "mock-client-id-123456",
        "username": username,
        "iss": f"https://cognito-idp.{cognito_region}.amazonaws.com/{cognito_user_pool_id}"
    }
    
    # Sign the token with the private key
    headers = {"kid": kid}
    token = jwt.encode(payload, private_key, algorithm="RS256", headers=headers)
    
    return token


def validate_token_with_jwks(token: str):
    """
    Validate a JWT token using the JWKS endpoint.
    
    This is the standard way to validate JWT tokens in production.
    """
    try:
        # Get signing key from JWKS endpoint
        jwks_client = PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        # Decode and verify the token
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
            issuer=f"https://cognito-idp.{cognito_region}.amazonaws.com/{cognito_user_pool_id}"
        )
        
        return True, payload, None
        
    except jwt.ExpiredSignatureError:
        return False, None, "Token has expired"
    except jwt.InvalidTokenError as e:
        return False, None, f"Invalid token: {str(e)}"
    except Exception as e:
        return False, None, f"Validation error: {str(e)}"


def test_fresh_token_from_service():
    """
    Get a fresh token from the mock service and validate it.
    
    This is the recommended approach for testing.
    """
    print_section("2. Get Fresh Token from Mock Service")
    
    try:
        response = requests.post(
            f"{cognito_url}/auth/login",
            json={
                "username": "testuser_observer",
                "password": "TempPass123!"
            },
            timeout=5
        )
        
        if response.status_code == 200:
            tokens = response.json()
            access_token = tokens["access_token"]
            
            print_success("Got fresh token from mock service")
            
            # Validate the token
            valid, payload, error = validate_token_with_jwks(access_token)
            
            if valid:
                print_success("Fresh token validation successful!")
                print("\nToken payload:")
                print(json.dumps(payload, indent=2))
                return access_token
            else:
                print_error(f"Fresh token validation failed: {error}")
                return None
        else:
            print_error(f"Login failed: {response.status_code}")
            return None
            
    except Exception as e:
        print_error(f"Error getting fresh token: {e}")
        return None


def test_custom_token_with_current_key(private_key, kid: str):
    """
    Create and validate a custom token using the current private key.
    
    This demonstrates the complete JWT lifecycle.
    """
    print_section("3. Create and Validate Custom Token")
    
    # Create a custom token
    custom_token = create_custom_token(
        private_key, 
        kid, 
        username="testuser_custom",
        groups=["contributor", "observer"]
    )
    
    print_success("Created custom token with current private key")
    print(f"Token: {custom_token[:50]}...{custom_token[-50:]}")
    
    # Validate the custom token
    valid, payload, error = validate_token_with_jwks(custom_token)
    
    if valid:
        print_success("Custom token validation successful!")
        print("\nToken payload:")
        print(json.dumps(payload, indent=2))
    else:
        print_error(f"Custom token validation failed: {error}")


def test_expired_token(private_key, kid: str):
    """
    Test validation of an expired token.
    
    This demonstrates proper error handling for expired tokens.
    """
    print_section("4. Test Expired Token Handling")
    
    # Create an expired token
    expired_token = create_custom_token(
        private_key,
        kid,
        username="testuser_expired",
        expired=True
    )
    
    print_success("Created expired token (exp in the past)")
    
    # Try to validate the expired token
    valid, payload, error = validate_token_with_jwks(expired_token)
    
    if not valid and "expired" in error.lower():
        print_success(f"Expired token correctly rejected: {error}")
    else:
        print_error("Expired token was not properly rejected!")


def test_jwks_endpoint():
    """
    Test the JWKS endpoint directly.
    
    This demonstrates how public keys are distributed.
    """
    print_section("5. Test JWKS Endpoint")
    
    try:
        response = requests.get(jwks_url, timeout=5)
        
        if response.status_code == 200:
            jwks = response.json()
            print_success("JWKS endpoint accessible")
            print("\nJWKS content:")
            print(json.dumps(jwks, indent=2))
            
            # Show key details
            for key in jwks.get("keys", []):
                print(f"\nKey ID (kid): {key.get('kid')}")
                print(f"Algorithm: {key.get('alg')}")
                print(f"Key Type: {key.get('kty')}")
                print(f"Use: {key.get('use')}")
                print(f"Modulus (n) length: {len(key.get('n', ''))} chars")
                print(f"Exponent (e): {key.get('e')}")
        else:
            print_error(f"JWKS endpoint failed: {response.status_code}")
            
    except Exception as e:
        print_error(f"Error accessing JWKS endpoint: {e}")


def main():
    """Run all JWT validation tests"""
    print("=" * 60)
    print("JWT Token Validation Testing with Mock Cognito")
    print("=" * 60)
    print()
    print("This test demonstrates:")
    print("1. How RSA key pairs work in JWT authentication")
    print("2. Why tokens become invalid when service restarts")
    print("3. Proper testing patterns for JWT validation")
    print("4. JWKS endpoint usage for token verification")
    
    # Test 1: Download current private key
    private_key, kid, algorithm = download_private_key()
    
    if not private_key:
        print_error("Cannot proceed without private key")
        print_info("Make sure mock Cognito service is running: python stages/stage3/local/mock_cognito.py")
        return
    
    # Test 2: Get fresh token from service
    fresh_token = test_fresh_token_from_service()
    
    # Test 3: Create and validate custom token
    if private_key and kid:
        test_custom_token_with_current_key(private_key, kid)
    
    # Test 4: Test expired token handling
    if private_key and kid:
        test_expired_token(private_key, kid)
    
    # Test 5: Examine JWKS endpoint
    test_jwks_endpoint()
    
    # Summary
    print_section("Summary")
    print()
    print("Key Learnings:")
    print("1. ✅ RSA private key is used to SIGN tokens")
    print("2. ✅ RSA public key (via JWKS) is used to VERIFY tokens")
    print("3. ✅ Mock Cognito generates NEW keys on each startup")
    print("4. ✅ Always use FRESH tokens for testing (not hardcoded)")
    print("5. ✅ JWKS endpoint provides public keys for verification")
    print()
    print("Why Hardcoded Tokens Fail:")
    print("- Old tokens were signed with OLD private keys")
    print("- Service now has NEW keys after restart")
    print("- Signature verification fails with mismatched keys")
    print()
    print("Best Practices:")
    print("- Always fetch fresh tokens in tests")
    print("- Use JWKS endpoint for verification")
    print("- Handle expired tokens gracefully")
    print("- Never expose private keys in production")
    print()


if __name__ == "__main__":
    main()
