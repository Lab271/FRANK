#!/bin/bash

# Stage 3 API Local Test Script
# Tests the Simple API service running on port 8000 with Mock Cognito authentication

set -e

echo "🚀 Stage 3 API Service Test"
echo "==========================="

# Configuration
# Use port from command line argument if provided, otherwise default to 8000
PORT="${1:-8000}"
SIMPLE_API_URL="http://localhost:$PORT"
MOCK_COGNITO_URL="http://localhost:8100"


# Set AWS credentials for mock service
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=eu-west-1

echo "📋 Testing Simple API service at $SIMPLE_API_URL"

# Check if Simple API is running
printf "🏥 Testing health endpoint: "
curl -s "$SIMPLE_API_URL/v1/health" | grep -q "healthy" && echo "✅ PASS" || echo "❌ FAIL"

# Test service info endpoint
printf "📖 Testing service info endpoint: "
curl -s "$SIMPLE_API_URL/" | grep -q "FRANK Root" && echo "✅ PASS" || echo "❌ FAIL"


# Helper function to get access token
get_access_token() {
    local username="$1"
    local response

    response=$(aws cognito-idp initiate-auth \
        --endpoint-url "$MOCK_COGNITO_URL" \
        --auth-flow USER_PASSWORD_AUTH \
        --client-id mock-client-id-123456 \
        --auth-parameters USERNAME="$username",PASSWORD=TempPass123! \
        --output json 2>/dev/null)

    if [ $? -eq 0 ]; then
        echo "$response" | jq -r '.AuthenticationResult.AccessToken'
    else
        echo "ERROR"
    fi
}

# Get tokens for different user roles
OBSERVER_TOKEN=$(get_access_token "testuser_observer")
CONTRIBUTOR_TOKEN=$(get_access_token "testuser_contributor")
PARTNER_TOKEN=$(get_access_token "testuser_partner")
CORE_MEMBER_TOKEN=$(get_access_token "testuser_core_member")

if [ "$OBSERVER_TOKEN" = "ERROR" ]; then
    echo "❌ Failed to get observer token - is Mock Cognito running on $MOCK_COGNITO_URL?"
    exit 1
fi

# Helper function to test endpoint access
test_endpoint_access() {
    local endpoint="$1"
    local role="$2"
    local token="$3"
    local expected_status="$4"
    
    printf "   - $endpoint with $role role: "
    
    if [ -z "$token" ] || [ "$token" = "ERROR" ]; then
        echo "❌ FAIL (no token)"
        return
    fi
    
    RESPONSE=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -H "Authorization: Bearer $token" \
        -H "Content-Type: application/json" \
        "$SIMPLE_API_URL$endpoint")
    
    HTTP_CODE=$(echo "$RESPONSE" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    BODY=$(echo "$RESPONSE" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
    
    if [ "$HTTP_CODE" = "$expected_status" ]; then
        echo "✅ PASS ($HTTP_CODE)"
        # if [ "$HTTP_CODE" = "200" ]; then
        #     echo "   User: $(echo "$BODY" | jq -r '.user_info.username // .username // "unknown"')"
        #     echo "   Access Tier: $(echo "$BODY" | jq -r '.user_info.access_tier // .access_tier // "unknown"')"
        #     echo "   Validation: $(echo "$BODY" | jq -r '.user.validation_source // "local"')"
        # fi
    else
        echo "❌ FAIL (expected $expected_status, got $HTTP_CODE)"
        if [ "$HTTP_CODE" != "200" ]; then
            echo "   Error: $(echo "$BODY" | jq -r '.detail // .' 2>/dev/null || echo "$BODY")"
        fi
    fi
}


echo "🤝 Testing /protected endpoint (requires OBSERVER+):"
test_endpoint_access "/protected" "observer" "$OBSERVER_TOKEN" "403"
test_endpoint_access "/protected" "contributor" "$CONTRIBUTOR_TOKEN" "403"
test_endpoint_access "/protected" "partner" "$PARTNER_TOKEN" "403"
test_endpoint_access "/protected" "core_member" "$CORE_MEMBER_TOKEN" "200"

echo "✅ Stage 3 API Service Local Test Completed"