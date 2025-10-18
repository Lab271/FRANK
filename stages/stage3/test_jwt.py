import jwt
from jwt import PyJWKClient
import json
import requests

cognito_region = "eu-west-1"
cognito_user_pool_id = "eu-west-1_MOCKPOOL"

# For mock Cognito service running locally (adjust port if different)
cognito_url = "http://localhost:8100"
# For real AWS Cognito (if you want to test against real AWS)
# cognito_url = f"https://cognito-idp.{cognito_region}.amazonaws.com"

jwks_url = f"{cognito_url}/{cognito_user_pool_id}/.well-known/jwks.json"

token = "eyJhbGciOiJSUzI1NiIsImtpZCI6Im1vY2stY29nbml0by1rZXktMSIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ0ZXN0dXNlcl9vYnNlcnZlciIsImNvZ25pdG86Z3JvdXBzIjpbIm9ic2VydmVyIl0sInRva2VuX3VzZSI6ImFjY2VzcyIsImlhdCI6MTc2MDgxNjA4NiwiZXhwIjoxNzYwODE5Njg2LCJjbGllbnRfaWQiOiJtb2NrLWNsaWVudC1pZC0xMjM0NTYiLCJ1c2VybmFtZSI6InRlc3R1c2VyX29ic2VydmVyIiwiaXNzIjoiaHR0cHM6Ly9jb2duaXRvLWlkcC5ldS13ZXN0LTEuYW1hem9uYXdzLmNvbS9ldS13ZXN0LTFfTU9DS1BPT0wifQ.XwLi4VDHBLQjg_Hxwmua_xTZPNFJDS_b8t-qpFOO_ZlfRtEREfST0b1rHJg81xL11EoI2GJ63tRIrygiJMIx1ilOmpysGA0sHTokK00qK7IpDKwHhrsb_iaUlgHaSzBQtOLAB6B2rojr_peLB19AI_8H1uYs5CtwSubhvhZMkbAK7vJp4IvBHaeXnYC_bO2O6BXcMIj4m02FvAYs9DaErou8GJyrMJwkM2iR0KdR-nV2yBRJZpb3-KSlLGbVLMRnhGS1dkuVnr-8MiE1mtHrQ4clpwCmlA82hOj5y8RAfznzPh4zMonu1_pgRshVqkpl1OA_gZZL-CK7HlnU8jBgVg"

print(f"Attempting to fetch JWKS from: {jwks_url}")

# First, let's try to decode the JWT without verification to see what's inside
print("=== 1. Decoding JWT without verification ===")
try:
    # Decode without verification first to inspect the token
    header = jwt.get_unverified_header(token)
    payload_unverified = jwt.decode(token, options={"verify_signature": False})
    
    print("JWT Header:")
    print(json.dumps(header, indent=2))
    print("\nJWT Payload (unverified):")
    print(json.dumps(payload_unverified, indent=2))
    print(f"\n✅ Expected issuer from token: {payload_unverified.get('iss')}")
    
except Exception as e:
    print(f"❌ Error decoding JWT: {e}")
    exit(1)

# Now try JWKS validation
print("=== 2. JWKS Validation ===")
try:
    print(f"Issuer from token for verification: {payload_unverified.get('iss')}")
    print(f"Using JWKS URL: {jwks_url}")
    jwks_client = PyJWKClient(jwks_url)
    signing_key = jwks_client.get_signing_key_from_jwt(token)

    print(f"Signing key obtained: {signing_key.key}")
    payload = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        options={"verify_aud": False},  # Skip audience verification for mock
        issuer=payload_unverified.get('iss')  # Use the issuer from the token
    )
    
    print("Decoded JWT Payload:")
    print(json.dumps(payload, indent=2))

    print("\n✅ JWKS Validation Successful")
except Exception as e:
    print(f"\n❌ JWKS Validation Failed")
    print(f"Error: {e}")

# Fallback: Try HS256 with a known secret (for testing only)
print("=== 3. HS256 with a known secret (for testing only) ===")

try:
    payload = jwt.decode(
        token,
        header["kid"],  # This should match your mock service secret
        algorithms=["HS256"],
        options={"verify_signature": False}  # Skip signature verification for testing
    )

    print("Decoded JWT Payload:")
    print(json.dumps(payload, indent=2))

    print("✅ HS256 fallback successful (signature not verified)")
except Exception as e2:
    print(f"❌ HS256 fallback also failed: {e2}")

# Try to get a fresh token from the mock service
print("\n=== 4. Getting Fresh Token from Mock Service ===")
try:
    login_response = requests.post(
        f"{cognito_url}/auth/login",
        json={
            "username": "testuser_observer",
            "password": "TempPass123!"
        },
        timeout=5
    )
    
    if login_response.status_code == 200:
        fresh_tokens = login_response.json()
        fresh_token = fresh_tokens.get("access_token")
        print("✅ Got fresh token from mock service")
        print(f"Fresh Token: {fresh_token}")
        
        # Try validation with fresh token
        try:
            jwks_client = PyJWKClient(jwks_url)
            signing_key = jwks_client.get_signing_key_from_jwt(fresh_token)
            
            fresh_payload = jwt.decode(
                fresh_token,
                signing_key.key,
                algorithms=["RS256"],
                options={"verify_aud": False}
            )
            
            print("✅ Fresh token validation successful!")
            print("Fresh token payload:")
            print(json.dumps(fresh_payload, indent=2))
            
        except Exception as fresh_e:
            print(f"❌ Fresh token validation failed: {fresh_e}")
    else:
        print(f"❌ Could not get fresh token: {login_response.status_code}")
        
except Exception as login_e:
    print(f"❌ Could not connect to mock service for fresh token: {login_e}")

print("\n=== Summary ===")
print("The signature verification failure suggests:")
print("1. Your existing token was signed with a different private key")
print("2. Try using a fresh token from the mock service")
print("3. Or check that the mock service is using consistent RSA keys")
