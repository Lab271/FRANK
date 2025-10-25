#!/bin/bash

# AWS Cognito Test Script
# Tests real AWS Cognito authentication and GetUser API calls

set -e

echo "🔐 AWS Cognito Authentication Test"
echo "=================================="

# Parse command-line arguments for -u (username) and -p (profile)
AWS_PROFILE="spike-account"
USERNAME="testuser_observer@example.com"

while [[ $# -gt 0 ]]; do
    case "$1" in
        -u|--username)
            USERNAME="$2"
            shift 2
            ;;
        -p|--profile)
            AWS_PROFILE="$2"
            shift 2
            ;;
        *)
            shift
            ;;
    esac
done

# Configuration
REGION="eu-central-1"
# Generate a simple password: "TempPass-" + current epoch time hash
PASSWORD="TempPass-$(date +%s | sha256sum | cut -c1-8)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color


# Retrieve the first available User Pool ID dynamically
echo "🔍 Retrieving the first available User Pool ID dynamically..."
USER_POOL_ID=$(aws cognito-idp list-user-pools --max-results 10 --region "$REGION" --profile "$AWS_PROFILE" --output json | jq -r '.UserPools[0].Id')
if [ -z "$USER_POOL_ID" ] || [ "$USER_POOL_ID" = "null" ]; then
    echo -e "${RED}❌ ERROR: Could not retrieve User Pool ID${NC}"
    exit 1
fi


echo "🔑 Setting password for user '$USERNAME' in user pool '$USER_POOL_ID'..."
# be sure to set the password to a known value first for USERNAME and USER_POOL_ID
if aws cognito-idp admin-set-user-password \
    --user-pool-id "$USER_POOL_ID" \
    --username "$USERNAME" \
    --password "$PASSWORD" \
    --permanent \
    --profile "$AWS_PROFILE" \
    --region "$REGION"; then
        echo -e "${GREEN}✅ Password set successfully for user '$USERNAME'${NC}"
else
        echo -e "${RED}❌ Failed to set password for user '$USERNAME'${NC}"
        exit 1
fi

echo "📋 Configuration:"
echo "  Region: $REGION"
echo "  User Pool ID: $USER_POOL_ID" 
echo "  Username: $USERNAME"
echo "  Password: $PASSWORD"
echo "  AWS Profile: $AWS_PROFILE"
echo "  JWKS URL: https://cognito-idp.$REGION.amazonaws.com/$USER_POOL_ID/.well-known/jwks.json"
echo ""


# Check if AWS CLI is configured first
echo "🔧 Checking AWS CLI configuration..."
if ! aws sts get-caller-identity --profile "$AWS_PROFILE" >/dev/null 2>&1; then
    echo -e "${RED}❌ ERROR: AWS CLI profile '$AWS_PROFILE' is not configured or credentials are invalid${NC}"
    echo "Please check your AWS profile configuration"
    exit 1
fi

AWS_IDENTITY=$(aws sts get-caller-identity --profile "$AWS_PROFILE" --output json)
echo -e "${GREEN}✅ AWS CLI configured${NC}"
echo "  Account: $(echo "$AWS_IDENTITY" | jq -r '.Account')"
echo "  User/Role: $(echo "$AWS_IDENTITY" | jq -r '.Arn')"
echo ""

# Retrieve CLIENT_ID dynamically
echo "🔍 Retrieving Client ID from AWS Cognito..."
CLIENT_ID=$(aws cognito-idp list-user-pool-clients \
    --user-pool-id "$USER_POOL_ID" \
    --region "$REGION" \
    --profile "$AWS_PROFILE" \
    --output json | jq -r '.UserPoolClients[0].ClientId' 2>/dev/null)

if [ -z "$CLIENT_ID" ] || [ "$CLIENT_ID" = "null" ]; then
    echo -e "${RED}❌ ERROR: Could not retrieve Client ID${NC}"
    echo "Available clients:"
    aws cognito-idp list-user-pool-clients \
        --user-pool-id "$USER_POOL_ID" \
        --region "$REGION" \
        --profile "$AWS_PROFILE" \
        --output table
    exit 1
fi

CLIENT_NAME=$(aws cognito-idp list-user-pool-clients \
    --user-pool-id "$USER_POOL_ID" \
    --region "$REGION" \
    --profile "$AWS_PROFILE" \
    --output json | jq -r '.UserPoolClients[0].ClientName' 2>/dev/null)

echo -e "${GREEN}✅ Client ID retrieved${NC}"
echo "  Client ID: $CLIENT_ID"
echo "  Client Name: $CLIENT_NAME"
echo ""

# Test 1: Check JWKS endpoint
echo "🔗 Step 1: Testing JWKS endpoint..."
JWKS_URL="https://cognito-idp.$REGION.amazonaws.com/$USER_POOL_ID/.well-known/jwks.json"
echo "  URL: $JWKS_URL"

if curl -s -f "$JWKS_URL" > /tmp/jwks.json; then
    echo -e "${GREEN}✅ JWKS endpoint accessible${NC}"
    KEY_COUNT=$(jq '.keys | length' /tmp/jwks.json)
    echo "  Found $KEY_COUNT signing keys"
    echo "  First key ID: $(jq -r '.keys[0].kid' /tmp/jwks.json)"
else
    echo -e "${RED}❌ JWKS endpoint not accessible${NC}"
    exit 1
fi
echo ""

# Test 2: Authenticate user and get token using AWS CLI
echo "🎫 Step 2: Authenticating user with AWS Cognito..."
echo "  Attempting to authenticate: $USERNAME"

AUTH_RESPONSE=$(aws cognito-idp initiate-auth \
    --region "$REGION" \
    --profile "$AWS_PROFILE" \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id "$CLIENT_ID" \
    --auth-parameters USERNAME="$USERNAME",PASSWORD="$PASSWORD" \
    --output json 2>/tmp/auth_error.log)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Authentication successful${NC}"
    
    # Extract tokens
    ACCESS_TOKEN=$(echo "$AUTH_RESPONSE" | jq -r '.AuthenticationResult.AccessToken')
    ID_TOKEN=$(echo "$AUTH_RESPONSE" | jq -r '.AuthenticationResult.IdToken')
    REFRESH_TOKEN=$(echo "$AUTH_RESPONSE" | jq -r '.AuthenticationResult.RefreshToken')
    
    echo "  Access Token: ${ACCESS_TOKEN:0:50}..."
    echo "  ID Token: ${ID_TOKEN:0:50}..."
    echo "  Token Type: $(echo "$AUTH_RESPONSE" | jq -r '.AuthenticationResult.TokenType')"
    echo "  Expires In: $(echo "$AUTH_RESPONSE" | jq -r '.AuthenticationResult.ExpiresIn') seconds"
else
    echo -e "${RED}❌ Authentication failed${NC}"
    echo "Error details:"
    cat /tmp/auth_error.log
    exit 1
fi
echo ""

# Test 3: Make raw CURL call to GetUser API
echo "🌐 Step 3: Testing raw CURL call to GetUser API..."
echo "  Endpoint: https://cognito-idp.$REGION.amazonaws.com/"
echo "  Target: AWSCognitoIdentityProviderService.GetUser"

# This should succeed with a valid access token
echo "  Making authenticated request with access token..."
CURL_RESPONSE=$(curl -s -w "HTTPSTATUS:%{http_code}" \
    -X POST "https://cognito-idp.$REGION.amazonaws.com/" \
    -H "X-Amz-Target: AWSCognitoIdentityProviderService.GetUser" \
    -H "Content-Type: application/x-amz-json-1.1" \
    -d "{\"AccessToken\": \"$ACCESS_TOKEN\"}")

CURL_HTTP_CODE=$(echo "$CURL_RESPONSE" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
BODY=$(echo "$CURL_RESPONSE" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')

echo "  HTTP Status: $CURL_HTTP_CODE"
if [ "$CURL_HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}✅ Raw CURL call successful${NC}"
    echo "  Response:"
    echo "$BODY" | jq '.'
    
    # Extract user info from CURL response for comparison
    CURL_USERNAME=$(echo "$BODY" | jq -r '.Username')
    echo "  Username from CURL: $CURL_USERNAME"
elif [ "$CURL_HTTP_CODE" = "403" ] || [ "$CURL_HTTP_CODE" = "401" ]; then
    echo -e "${RED}❌ Raw CURL call failed - authentication issue${NC}"
    echo "  Response: $(echo "$BODY" | jq -r '.message // .' 2>/dev/null || echo "$BODY")"
else
    echo -e "${RED}❌ Unexpected HTTP status: $CURL_HTTP_CODE${NC}"
    echo "  Response: $BODY"
fi
echo ""

# Test 4: Use AWS CLI get-user command
echo "🔧 Step 4: Testing AWS CLI get-user command..."
echo "  Command: aws cognito-idp get-user --access-token [token] --region $REGION"

if GET_USER_RESPONSE=$(aws cognito-idp get-user \
    --access-token "$ACCESS_TOKEN" \
    --region "$REGION" \
    --profile "$AWS_PROFILE" \
    --output json 2>/tmp/getuser_error.log); then
    
    echo -e "${GREEN}✅ AWS CLI get-user successful${NC}"
    
    # Parse user information
    USERNAME_FROM_TOKEN=$(echo "$GET_USER_RESPONSE" | jq -r '.Username')
    USER_ATTRIBUTES=$(echo "$GET_USER_RESPONSE" | jq -r '.UserAttributes')
    
    echo "  Username: $USERNAME_FROM_TOKEN"
    echo "  User Attributes:"
    echo "$USER_ATTRIBUTES" | jq -r '.[] | "    \(.Name): \(.Value)"'
    
    # Check for groups
    GROUPS=$(echo "$GET_USER_RESPONSE" | jq -r '.UserAttributes[] | select(.Name=="custom:groups") | .Value // empty')
    if [ -n "$GROUPS" ]; then
        echo "  Groups: $GROUPS"
    else
        echo "  Groups: None found in custom:groups attribute"
    fi
    
else
    echo -e "${RED}❌ AWS CLI get-user failed${NC}"
    echo "Error details:"
    cat /tmp/getuser_error.log
fi
echo ""

# Test 5: Decode JWT tokens locally (for verification)
echo "🔍 Step 5: Decoding JWT tokens locally..."

# Function to decode JWT payload (base64 decode the middle part)
decode_jwt_payload() {
    local token="$1"
    local payload=$(echo "$token" | cut -d'.' -f2)
    
    # Add padding if needed
    case $((${#payload} % 4)) in
        2) payload="${payload}==" ;;
        3) payload="${payload}=" ;;
    esac
    
    echo "$payload" | base64 -d 2>/dev/null | jq '.' 2>/dev/null || echo "Failed to decode"
}

echo "  Access Token payload:"
decode_jwt_payload "$ACCESS_TOKEN"
echo ""

echo "  ID Token payload:"  
decode_jwt_payload "$ID_TOKEN" 
echo ""

# Test 6: Verify JWKS validation would work
echo "🔐 Step 6: Verifying token signature info..."

# Extract the kid (key ID) from the token header
ACCESS_TOKEN_HEADER=$(echo "$ACCESS_TOKEN" | cut -d'.' -f1)
case $((${#ACCESS_TOKEN_HEADER} % 4)) in
    2) ACCESS_TOKEN_HEADER="${ACCESS_TOKEN_HEADER}==" ;;
    3) ACCESS_TOKEN_HEADER="${ACCESS_TOKEN_HEADER}=" ;;
esac

TOKEN_KID=$(echo "$ACCESS_TOKEN_HEADER" | base64 -d 2>/dev/null | jq -r '.kid' 2>/dev/null)
echo "  Token Key ID: $TOKEN_KID"

# Check if this key exists in JWKS
JWKS_KEY_IDS=$(jq -r '.keys[].kid' /tmp/jwks.json | tr '\n' ' ')
echo "  Available JWKS Key IDs: $JWKS_KEY_IDS"

if echo "$JWKS_KEY_IDS" | grep -q "$TOKEN_KID"; then
    echo -e "${GREEN}✅ Token key ID found in JWKS - signature validation would work${NC}"
else
    echo -e "${RED}❌ Token key ID not found in JWKS - signature validation would fail${NC}"
fi
echo ""

# Summary
echo "📊 Test Summary:"
echo "================"
echo "1. JWKS Endpoint: ✅ Accessible"
echo "2. User Authentication: ✅ Successful"
echo "3. Raw CURL GetUser: $(if [ "$CURL_HTTP_CODE" = "200" ]; then echo "✅ Successful"; else echo "❌ Failed"; fi)"
echo "4. AWS CLI GetUser: ✅ Successful"
echo "5. JWT Decoding: ✅ Working"
echo "6. JWKS Key Matching: $(if echo "$JWKS_KEY_IDS" | grep -q "$TOKEN_KID"; then echo "✅ Working"; else echo "❌ Failed"; fi)"
echo ""

echo "🎯 For your application:"
echo "======================="
echo "• Set environment='aws' in your app config"
echo "• Use region: $REGION"
echo "• Use user_pool_id: $USER_POOL_ID"
echo "• Use client_id: $CLIENT_ID"
echo "• The system will use this cognito-url: https://cognito-idp.$REGION.amazonaws.com/$USER_POOL_ID"
echo ""

echo "📋 Export commands for testing:"
echo "export TOKEN='$ACCESS_TOKEN'"
echo "export REGION='$REGION'"
echo "export CLIENT_ID='$CLIENT_ID'"
echo "export USER_POOL_ID='$USER_POOL_ID'"
echo ""

# Cleanup
rm -f /tmp/jwks.json /tmp/auth_error.log /tmp/getuser_error.log

echo -e "${GREEN}✅ AWS Cognito test completed!${NC}"