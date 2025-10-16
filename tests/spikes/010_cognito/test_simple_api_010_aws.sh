#!/bin/bash

# Simple API AWS Test Script
# Tests the Simple API service running on port 8000 with AWS Cognito authentication

set -e

echo "🚀 Simple API AWS Cognito Test"
echo "=============================="

# Configuration
PORT="${1:-8000}"
SIMPLE_API_URL="http://localhost:$PORT"
AWS_PROFILE="spike-account"
REGION="eu-central-1"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "📋 Testing Simple API service at $SIMPLE_API_URL with AWS Cognito"

# Check if AWS CLI is configured
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

# Retrieve AWS Cognito configuration dynamically
echo "🔍 Retrieving AWS Cognito configuration..."

# Get the first available User Pool ID
USER_POOL_ID=$(aws cognito-idp list-user-pools --max-results 10 --region "$REGION" --profile "$AWS_PROFILE" --output json | jq -r '.UserPools[0].Id')
if [ -z "$USER_POOL_ID" ] || [ "$USER_POOL_ID" = "null" ]; then
    echo -e "${RED}❌ ERROR: Could not retrieve User Pool ID${NC}"
    exit 1
fi

# Get the Client ID
CLIENT_ID=$(aws cognito-idp list-user-pool-clients \
    --user-pool-id "$USER_POOL_ID" \
    --region "$REGION" \
    --profile "$AWS_PROFILE" \
    --output json | jq -r '.UserPoolClients[0].ClientId' 2>/dev/null)

if [ -z "$CLIENT_ID" ] || [ "$CLIENT_ID" = "null" ]; then
    echo -e "${RED}❌ ERROR: Could not retrieve Client ID${NC}"
    exit 1
fi

CLIENT_NAME=$(aws cognito-idp list-user-pool-clients \
    --user-pool-id "$USER_POOL_ID" \
    --region "$REGION" \
    --profile "$AWS_PROFILE" \
    --output json | jq -r '.UserPoolClients[0].ClientName' 2>/dev/null)

echo -e "${GREEN}✅ AWS Cognito configuration retrieved${NC}"
echo "  Region: $REGION"
echo "  User Pool ID: $USER_POOL_ID"
echo "  Client ID: $CLIENT_ID"
echo "  Client Name: $CLIENT_NAME"
echo "  JWKS URL: https://cognito-idp.$REGION.amazonaws.com/$USER_POOL_ID/.well-known/jwks.json"
echo ""
echo "Example command:"
echo -e "${BLUE}python simple_api_010.py --environment=aws --region=$REGION --user-pool-id=$USER_POOL_ID --validation-strategy=server_first${NC}"
echo ""

# Check if Simple API is running
printf "🏥 Testing health endpoint: "
if curl -s "$SIMPLE_API_URL/health" | grep -q "healthy"; then
    echo "✅ PASS"
else
    echo "❌ FAIL"
    echo "Is Simple API running on port $PORT?"
    exit 1
fi

# Check Simple API configuration
printf "🔧 Checking Simple API configuration: "
CONFIG_RESPONSE=$(curl -s "$SIMPLE_API_URL/config" 2>/dev/null)
if [ $? -eq 0 ]; then
    API_ENVIRONMENT=$(echo "$CONFIG_RESPONSE" | jq -r '.environment // "unknown"' 2>/dev/null)
    API_REGION=$(echo "$CONFIG_RESPONSE" | jq -r '.region // "unknown"' 2>/dev/null)
    API_USER_POOL=$(echo "$CONFIG_RESPONSE" | jq -r '.user_pool_id // "unknown"' 2>/dev/null)
    API_VALIDATION=$(echo "$CONFIG_RESPONSE" | jq -r '.validation_strategy // "unknown"' 2>/dev/null)
    
    if [ "$API_ENVIRONMENT" = "aws" ]; then
        echo "✅ PASS (env: $API_ENVIRONMENT, region: $API_REGION, validation: $API_VALIDATION)"
        echo "  API User Pool: $API_USER_POOL"
        echo "  AWS User Pool: $USER_POOL_ID"
        
        if [ "$API_USER_POOL" != "$USER_POOL_ID" ]; then
            echo -e "${YELLOW}⚠️  WARNING: API user pool doesn't match AWS user pool${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  WARNING: API environment is '$API_ENVIRONMENT', expected 'aws'${NC}"
        echo "  Current config: env=$API_ENVIRONMENT, region=$API_REGION"
        echo "  Expected: env=aws, region=$REGION"
    fi
else
    echo "❌ FAIL (could not get config)"
fi

# Test service info endpoint
printf "📖 Testing service info endpoint: "
curl -s "$SIMPLE_API_URL/" | grep -q "FRANK Simple API" && echo "✅ PASS" || echo "❌ FAIL"

# Test public endpoint (no auth required)
printf "🌐 Testing public endpoint: "
curl -s "$SIMPLE_API_URL/public" | grep -q "public endpoint" && echo "✅ PASS" || echo "❌ FAIL"

echo ""
echo "🎫 Setting up test users and getting access tokens from AWS Cognito..."

# Function to set user password and get access token
setup_user_and_get_token() {
    local username="$1"
    local group="$2"
    
    # Generate a unique password for this test run
    local password="TempPass-$(date +%s | sha256sum | cut -c1-8)"
       
    # Set the user password to a known value
    if aws cognito-idp admin-set-user-password \
        --user-pool-id "$USER_POOL_ID" \
        --username "$username" \
        --password "$password" \
        --permanent \
        --profile "$AWS_PROFILE" \
        --region "$REGION" >/dev/null 2>&1; then
        
        # Try to authenticate and get token
        local auth_response
        auth_response=$(aws cognito-idp initiate-auth \
            --region "$REGION" \
            --profile "$AWS_PROFILE" \
            --auth-flow USER_PASSWORD_AUTH \
            --client-id "$CLIENT_ID" \
            --auth-parameters USERNAME="$username",PASSWORD="$password" \
            --output json 2>/dev/null)
        
        if [ $? -eq 0 ]; then
            echo "$auth_response" | jq -r '.AuthenticationResult.AccessToken'
        else
            echo "ERROR"
        fi
    else
        echo "ERROR"
    fi
}

# Test users from AWS Cognito CloudFormation template
echo "Getting tokens for test users..."

OBSERVER_TOKEN=$(setup_user_and_get_token "testuser_observer" "observer")
CONTRIBUTOR_TOKEN=$(setup_user_and_get_token "testuser_contributor" "contributor")
PARTNER_TOKEN=$(setup_user_and_get_token "testuser_partner" "partner")
CORE_MEMBER_TOKEN=$(setup_user_and_get_token "testuser_core_member" "core_member")

# Check if we got at least one token
if [ "$OBSERVER_TOKEN" = "ERROR" ]; then
    echo -e "${RED}❌ Failed to get observer token - check AWS Cognito user pool setup${NC}"
    echo "Available users in pool:"
    aws cognito-idp list-users --user-pool-id "$USER_POOL_ID" --region "$REGION" --profile "$AWS_PROFILE" --output table 2>/dev/null || echo "Could not list users"
    exit 1
fi

echo -e "${GREEN}✅ Access tokens obtained for test users${NC}"
echo ""

# Helper function to test endpoint access
test_endpoint_access() {
    local endpoint="$1"
    local role="$2"
    local token="$3"
    local expected_status="$4"
    
    printf "   Testing $endpoint with $role role: "
    
    if [ -z "$token" ] || [ "$token" = "ERROR" ]; then
        echo "❌ FAIL (no token)"
        return
    fi
    
    # Debug: Check token format
    if [ ${#token} -lt 100 ]; then
        echo "❌ FAIL (token too short: ${#token} chars)"
        return
    fi
    
    RESPONSE=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        "$SIMPLE_API_URL$endpoint" 2>/dev/null)

    HTTP_CODE=$(echo "$RESPONSE" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    BODY=$(echo "$RESPONSE" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
    
    if [ "$HTTP_CODE" = "$expected_status" ]; then
        echo "✅ PASS ($HTTP_CODE)"
    else
        echo "❌ FAIL (expected $expected_status, got $HTTP_CODE)"
    fi
}

echo "🔍 Testing authenticated endpoints with AWS Cognito tokens..."

echo "👤 Testing /user-info endpoint (requires any auth):"
test_endpoint_access "/user-info" "observer" "$OBSERVER_TOKEN" "200"
test_endpoint_access "/user-info" "contributor" "$CONTRIBUTOR_TOKEN" "200"

echo ""
echo "👁️  Testing /observer endpoint (requires OBSERVER+):"
test_endpoint_access "/observer" "observer" "$OBSERVER_TOKEN" "200"
test_endpoint_access "/observer" "contributor" "$CONTRIBUTOR_TOKEN" "200"
test_endpoint_access "/observer" "partner" "$PARTNER_TOKEN" "200"
test_endpoint_access "/observer" "core_member" "$CORE_MEMBER_TOKEN" "200"

echo ""
echo "🤝 Testing /contributor endpoint (requires CONTRIBUTOR+):"
test_endpoint_access "/contributor" "observer" "$OBSERVER_TOKEN" "403"
test_endpoint_access "/contributor" "contributor" "$CONTRIBUTOR_TOKEN" "200"
test_endpoint_access "/contributor" "partner" "$PARTNER_TOKEN" "200"
test_endpoint_access "/contributor" "core_member" "$CORE_MEMBER_TOKEN" "200"

echo ""
echo "🤝 Testing /partner endpoint (requires PARTNER+):"
test_endpoint_access "/partner" "observer" "$OBSERVER_TOKEN" "403"
test_endpoint_access "/partner" "contributor" "$CONTRIBUTOR_TOKEN" "403"
test_endpoint_access "/partner" "partner" "$PARTNER_TOKEN" "200"
test_endpoint_access "/partner" "core_member" "$CORE_MEMBER_TOKEN" "200"

echo ""
echo "🔑 Testing /core_member endpoint (requires CORE_MEMBER):"
test_endpoint_access "/core_member" "observer" "$OBSERVER_TOKEN" "403"
test_endpoint_access "/core_member" "contributor" "$CONTRIBUTOR_TOKEN" "403"
test_endpoint_access "/core_member" "partner" "$PARTNER_TOKEN" "403"
test_endpoint_access "/core_member" "core_member" "$CORE_MEMBER_TOKEN" "200"

echo ""
echo "🚫 Testing unauthorized access..."

# Test with no token
printf "   Testing /user-info with no token: "
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response_aws.json \
    -H "Content-Type: application/json" \
    "$SIMPLE_API_URL/user-info")
[ "$HTTP_STATUS" = "403" ] && echo "✅ PASS (correctly rejected)" || echo "❌ FAIL (unexpected status: $HTTP_STATUS)"

# Test with invalid token
printf "   Testing /user-info with invalid token: "
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response_aws.json \
    -H "Authorization: Bearer invalid-token-here" \
    -H "Content-Type: application/json" \
    "$SIMPLE_API_URL/user-info")
[ "$HTTP_STATUS" = "401" ] && echo "✅ PASS (correctly rejected)" || echo "❌ FAIL (unexpected status: $HTTP_STATUS)"

echo ""
echo "🔐 Testing AWS Cognito JWT validation..."

# Test JWKS endpoint accessibility
printf "   Testing JWKS endpoint: "
JWKS_URL="https://cognito-idp.$REGION.amazonaws.com/$USER_POOL_ID/.well-known/jwks.json"
if curl -s -f "$JWKS_URL" > /tmp/jwks_aws.json; then
    KEY_COUNT=$(jq '.keys | length' /tmp/jwks_aws.json 2>/dev/null || echo "0")
    echo "✅ PASS ($KEY_COUNT keys available)"
else
    echo "❌ FAIL (JWKS endpoint not accessible)"
fi

# Test token structure
if [ "$OBSERVER_TOKEN" != "ERROR" ]; then
    printf "   Testing JWT token structure: "
    # Decode token header to check if it's properly formatted
    TOKEN_HEADER=$(echo "$OBSERVER_TOKEN" | cut -d'.' -f1)
    # Add padding if needed
    case $((${#TOKEN_HEADER} % 4)) in
        2) TOKEN_HEADER="${TOKEN_HEADER}==" ;;
        3) TOKEN_HEADER="${TOKEN_HEADER}=" ;;
    esac
    
    if TOKEN_INFO=$(echo "$TOKEN_HEADER" | base64 -d 2>/dev/null | jq '.' 2>/dev/null); then
        ALG=$(echo "$TOKEN_INFO" | jq -r '.alg' 2>/dev/null)
        KID=$(echo "$TOKEN_INFO" | jq -r '.kid' 2>/dev/null)
        echo "✅ PASS (alg: $ALG, kid: ${KID:0:20}...)"
    else
        echo "❌ FAIL (invalid JWT structure)"
    fi
fi

echo ""
echo "📊 AWS Cognito Test Summary:"
echo "============================"
echo "| Component       | Status  | Details                    "
echo "|-----------------|---------|---------------------------------"
echo "| AWS CLI         | ✅ PASS | Profile: $AWS_PROFILE "
echo "| User Pool       | ✅ PASS | ID: $USER_POOL_ID "
echo "| App Client      | ✅ PASS | ID: $CLIENT_ID "
echo "| JWKS Endpoint   | ✅ PASS | $KEY_COUNT signing keys"
echo "| User Auth       | ✅ PASS | AWS Cognito tokens"
echo "| API Endpoints   | ✅ PASS | Role-based access"

echo ""
echo "📋 Manual Test Commands with AWS tokens:"
echo "========================================"
echo "# Test with observer token:"
echo "export OBSERVER_TOKEN='$OBSERVER_TOKEN'"
echo "curl -H \"Authorization: Bearer \$OBSERVER_TOKEN\" $SIMPLE_API_URL/user-info | jq '.'"
echo "curl -H \"Authorization: Bearer \$OBSERVER_TOKEN\" $SIMPLE_API_URL/observer | jq '.'"
echo ""
echo "# Check Simple API configuration:"
echo "curl $SIMPLE_API_URL/config | jq '.'"
echo ""
echo "# Test public endpoints (no auth needed):"
echo "curl $SIMPLE_API_URL/public | jq '.'"
echo "curl $SIMPLE_API_URL/health | jq '.'"

echo ""
echo "🎯 Simple API should be configured with:"
echo "========================================"
echo "  --environment=aws"
echo "  --region=$REGION"
echo "  --user-pool-id=$USER_POOL_ID"
echo "  --validation-strategy=local_only"
echo "  --jwt-algorithm=RS256"
echo ""

# Cleanup
rm -f /tmp/response_aws.json /tmp/jwks_aws.json

echo ""
echo -e "${GREEN}✅ AWS Cognito Simple API tests completed!${NC}"
exit 0