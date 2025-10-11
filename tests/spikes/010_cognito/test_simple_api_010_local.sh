#!/bin/bash

# Simple API Local Test Script
# Tests the Simple API service running on port 8000 with Mock Cognito authentication

set -e

echo "🚀 Simple API Service Test"
echo "=========================="

# Configuration
SIMPLE_API_URL="http://localhost:8000"
MOCK_COGNITO_URL="http://localhost:8100"

# Set AWS credentials for mock service
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=eu-west-1

echo "📋 Testing Simple API service at $SIMPLE_API_URL"

# Check if Simple API is running
printf "🏥 Testing health endpoint: "
curl -s "$SIMPLE_API_URL/health" | grep -q "healthy" && echo "✅ PASS" || echo "❌ FAIL"

# Test service info endpoint
printf "📖 Testing service info endpoint: "
curl -s "$SIMPLE_API_URL/" | grep -q "FRANK Simple API" && echo "✅ PASS" || echo "❌ FAIL"

# Test public endpoint (no auth required)
printf "🌐 Testing public endpoint: "
curl -s "$SIMPLE_API_URL/public" | grep -q "public endpoint" && echo "✅ PASS" || echo "❌ FAIL"

echo
echo "🎫 Getting access tokens from Mock Cognito..."

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

echo "✅ Access tokens obtained for all user roles"

echo
echo "🔍 Testing authenticated endpoints..."

# Helper function to test endpoint access
test_endpoint_access() {
    local endpoint="$1"
    local role="$2"
    local token="$3"
    local expected_status="$4"
    
    printf "Testing $endpoint with $role role: "
    
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
        if [ "$HTTP_CODE" = "200" ]; then
            echo "   User: $(echo "$BODY" | jq -r '.user_info.username // .username // "unknown"')"
            echo "   Access Tier: $(echo "$BODY" | jq -r '.user_info.access_tier // .access_tier // "unknown"')"
            echo "   Validation: $(echo "$BODY" | jq -r '.user.validation_source // "local"')"
        fi
    else
        echo "❌ FAIL (expected $expected_status, got $HTTP_CODE)"
        if [ "$HTTP_CODE" != "200" ]; then
            echo "   Error: $(echo "$BODY" | jq -r '.detail // .' 2>/dev/null || echo "$BODY")"
        fi
    fi
}

echo "👤 Testing /user-info endpoint (requires any auth):"
test_endpoint_access "/user-info" "observer" "$OBSERVER_TOKEN" "200"
test_endpoint_access "/user-info" "contributor" "$CONTRIBUTOR_TOKEN" "200"

echo
echo "👁️  Testing /observer endpoint (requires OBSERVER+):"
test_endpoint_access "/observer" "observer" "$OBSERVER_TOKEN" "200"
test_endpoint_access "/observer" "contributor" "$CONTRIBUTOR_TOKEN" "200"
test_endpoint_access "/observer" "partner" "$PARTNER_TOKEN" "200"
test_endpoint_access "/observer" "core_member" "$CORE_MEMBER_TOKEN" "200"

echo
echo "🤝 Testing /contributor endpoint (requires CONTRIBUTOR+):"
test_endpoint_access "/contributor" "observer" "$OBSERVER_TOKEN" "403"
test_endpoint_access "/contributor" "contributor" "$CONTRIBUTOR_TOKEN" "200"
test_endpoint_access "/contributor" "partner" "$PARTNER_TOKEN" "200"
test_endpoint_access "/contributor" "core_member" "$CORE_MEMBER_TOKEN" "200"

echo
echo "🤝 Testing /partner endpoint (requires PARTNER+):"
test_endpoint_access "/partner" "observer" "$OBSERVER_TOKEN" "403"
test_endpoint_access "/partner" "contributor" "$CONTRIBUTOR_TOKEN" "403"
test_endpoint_access "/partner" "partner" "$PARTNER_TOKEN" "200"
test_endpoint_access "/partner" "core_member" "$CORE_MEMBER_TOKEN" "200"

echo
echo "🔑 Testing /core_member endpoint (requires CORE_MEMBER):"
test_endpoint_access "/core_member" "observer" "$OBSERVER_TOKEN" "403"
test_endpoint_access "/core_member" "contributor" "$CONTRIBUTOR_TOKEN" "403"
test_endpoint_access "/core_member" "partner" "$PARTNER_TOKEN" "403"
test_endpoint_access "/core_member" "core_member" "$CORE_MEMBER_TOKEN" "200"

echo
echo "🚫 Testing unauthorized access..."

# Test with no token
printf "Testing /user-info with no token: "
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json \
    -H "Content-Type: application/json" \
    "$SIMPLE_API_URL/user-info")
[ "$HTTP_STATUS" = "403" ] && echo "✅ PASS (correctly rejected)" || echo "❌ FAIL (unexpected status: $HTTP_STATUS)"

# Test with invalid token
printf "Testing /user-info with invalid token: "
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json \
    -H "Authorization: Bearer invalid-token-here" \
    -H "Content-Type: application/json" \
    "$SIMPLE_API_URL/user-info")
[ "$HTTP_STATUS" = "401" ] && echo "✅ PASS (correctly rejected)" || echo "❌ FAIL (unexpected status: $HTTP_STATUS)"

echo
echo "📊 Access Control Matrix Summary:"
echo "================================="
echo "| Role        | /public | /observer | /contributor | /partner | /core_member |"
echo "|-------------|---------|-----------|--------------|----------|--------------|"
echo "| PUBLIC      |   ✅    |    ❌     |      ❌      |    ❌    |      ❌      |"
echo "| OBSERVER    |   ✅    |    ✅     |      ❌      |    ❌    |      ❌      |"
echo "| CONTRIBUTOR |   ✅    |    ✅     |      ✅      |    ❌    |      ❌      |"
echo "| PARTNER     |   ✅    |    ✅     |      ✅      |    ✅    |      ❌      |"
echo "| CORE_MEMBER |   ✅    |    ✅     |      ✅      |    ✅    |      ✅      |"

echo
echo "📋 Manual Test Commands:"
echo "========================"
echo "# Test with observer token:"
echo "export OBSERVER_TOKEN='$OBSERVER_TOKEN'"
echo "curl -H \"Authorization: Bearer \$OBSERVER_TOKEN\" $SIMPLE_API_URL/user-info | jq '.'"
echo "curl -H \"Authorization: Bearer \$OBSERVER_TOKEN\" $SIMPLE_API_URL/observer | jq '.'"
echo
echo "# Test with contributor token:"
echo "export CONTRIBUTOR_TOKEN='$CONTRIBUTOR_TOKEN'"
echo "curl -H \"Authorization: Bearer \$CONTRIBUTOR_TOKEN\" $SIMPLE_API_URL/contributor | jq '.'"
echo
echo "# Test public endpoints (no auth needed):"
echo "curl $SIMPLE_API_URL/public | jq '.'"
echo "curl $SIMPLE_API_URL/health | jq '.'"

# Test validation strategy if environment variable is set
if [ -n "$VALIDATION_STRATEGY" ]; then
    echo
    echo "🔧 Current validation strategy: $VALIDATION_STRATEGY"
    echo "Available strategies:"
    echo "  - server_first: Try server validation first, fallback to local JWT"
    echo "  - local_only: Always validate JWT locally (fastest)"
    echo "  - server_only: Always validate with server (most secure)"
fi

# Cleanup
rm -f /tmp/response.json

echo
echo "✅ Simple API tests completed!"