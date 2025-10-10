#!/bin/bash

# Complete demo: AWS CLI Cognito Token → Simple API calls

set -e

echo "🧪 Complete Demo: AWS CLI Cognito Token → Simple API"
echo "====================================================="

# Set AWS credentials for mock service
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=eu-west-1

echo "1. Getting access token from Mock Cognito via AWS CLI..."

# Get token and extract access token
AUTH_RESPONSE=$(aws cognito-idp initiate-auth \
    --endpoint-url http://localhost:8100 \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id mock-client-id-123456 \
    --auth-parameters USERNAME=testuser_observer,PASSWORD=TempPass123! \
    --output json)

if [ $? -ne 0 ]; then
    echo "❌ Failed to get token from Mock Cognito"
    exit 1
fi

# Extract access token
ACCESS_TOKEN=$(echo "$AUTH_RESPONSE" | jq -r '.AuthenticationResult.AccessToken')

if [ "$ACCESS_TOKEN" = "null" ] || [ -z "$ACCESS_TOKEN" ]; then
    echo "❌ No access token received"
    exit 1
fi

echo "✅ Access token received (length: ${#ACCESS_TOKEN})"
echo "   Token starts with: ${ACCESS_TOKEN:0:20}..."

echo
echo "2. Testing Simple API endpoints with the token..."

# Test endpoints
SIMPLE_API_URL="http://localhost:8000"

echo
echo "🔍 Testing all Simple API endpoints..."

printf "📌 Testing health endpoint: "
curl -s "$SIMPLE_API_URL/health" | grep -q "healthy" && echo "✅ PASS" || echo "❌ FAIL"

printf "👤 Testing /user-info endpoint (with valid token): "
RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
               -H "Content-Type: application/json" \
               "$SIMPLE_API_URL/user-info")
echo "$RESPONSE" | grep -q "testuser_observer" && echo "✅ PASS" || echo "❌ FAIL"
echo "   Response: $(echo "$RESPONSE" | jq -c '.')"

printf "👁️  Testing /observer endpoint (should work for testuser_observer): "
RESPONSE=$(curl -s -H "Authorization: Bearer $ACCESS_TOKEN" \
               -H "Content-Type: application/json" \
               "$SIMPLE_API_URL/observer")
echo "$RESPONSE" | grep -q "observer" && echo "✅ PASS" || echo "❌ FAIL"
echo "   Response: $(echo "$RESPONSE" | jq -c '.')"

printf "� Testing /contributor endpoint (should fail - insufficient access): "
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json \
              -H "Authorization: Bearer $ACCESS_TOKEN" \
              -H "Content-Type: application/json" \
              "$SIMPLE_API_URL/contributor")
[ "$HTTP_STATUS" = "403" ] && echo "✅ PASS (correctly rejected)" || echo "❌ FAIL (unexpected status: $HTTP_STATUS)"
echo "   Response: $(cat /tmp/response.json | jq -c '.')"

printf "🤝 Testing /partner endpoint (should fail - insufficient access): "
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json \
              -H "Authorization: Bearer $ACCESS_TOKEN" \
              -H "Content-Type: application/json" \
              "$SIMPLE_API_URL/partner")
[ "$HTTP_STATUS" = "403" ] && echo "✅ PASS (correctly rejected)" || echo "❌ FAIL (unexpected status: $HTTP_STATUS)"
echo "   Response: $(cat /tmp/response.json | jq -c '.')"

printf "🔑 Testing /core_member endpoint (should fail - insufficient access): "
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json \
              -H "Authorization: Bearer $ACCESS_TOKEN" \
              -H "Content-Type: application/json" \
              "$SIMPLE_API_URL/core_member")
[ "$HTTP_STATUS" = "403" ] && echo "✅ PASS (correctly rejected)" || echo "❌ FAIL (unexpected status: $HTTP_STATUS)"
echo "   Response: $(cat /tmp/response.json | jq -c '.')"

printf "🚫 Testing /user-info endpoint (no token): "
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json \
              -H "Content-Type: application/json" \
              "$SIMPLE_API_URL/user-info")
[ "$HTTP_STATUS" = "403" ] && echo "✅ PASS (correctly unauthorized)" || echo "❌ FAIL (unexpected status: $HTTP_STATUS)"
echo "   Response: $(cat /tmp/response.json | jq -c '.')"

printf "🔓 Testing /user-info endpoint (invalid token): "
HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json \
              -H "Authorization: Bearer invalid-token-here" \
              -H "Content-Type: application/json" \
              "$SIMPLE_API_URL/user-info")
[ "$HTTP_STATUS" = "401" ] && echo "✅ PASS (correctly rejected)" || echo "❌ FAIL (unexpected status: $HTTP_STATUS)"
echo "   Response: $(cat /tmp/response.json | jq -c '.')"

echo
echo "3. Testing with a different user role (contributor)..."

echo "   Getting token for testuser_contributor..."
CONTRIB_RESPONSE=$(aws cognito-idp initiate-auth \
    --endpoint-url http://localhost:8100 \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id mock-client-id-123456 \
    --auth-parameters USERNAME=testuser_contributor,PASSWORD=TempPass123! \
    --output json)

CONTRIB_TOKEN=$(echo "$CONTRIB_RESPONSE" | jq -r '.AuthenticationResult.AccessToken')

if [ "$CONTRIB_TOKEN" != "null" ] && [ -n "$CONTRIB_TOKEN" ]; then
    echo "   ✅ Contributor token received"
    
    printf "🤝 Testing /contributor endpoint (should work for testuser_contributor): "
    RESPONSE=$(curl -s -H "Authorization: Bearer $CONTRIB_TOKEN" \
                   -H "Content-Type: application/json" \
                   "$SIMPLE_API_URL/contributor")
    echo "$RESPONSE" | grep -q "contributor" && echo "✅ PASS" || echo "❌ FAIL"
    echo "   Response: $(echo "$RESPONSE" | jq -c '.')"
    
    printf "👁️  Testing /observer endpoint (should work - contributor has observer access): "
    RESPONSE=$(curl -s -H "Authorization: Bearer $CONTRIB_TOKEN" \
                   -H "Content-Type: application/json" \
                   "$SIMPLE_API_URL/observer")
    echo "$RESPONSE" | grep -q "observer" && echo "✅ PASS" || echo "❌ FAIL"
    echo "   Response: $(echo "$RESPONSE" | jq -c '.')"
    
    printf "🤝 Testing /partner endpoint (should fail - insufficient access): "
    HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/response.json \
                  -H "Authorization: Bearer $CONTRIB_TOKEN" \
                  -H "Content-Type: application/json" \
                  "$SIMPLE_API_URL/partner")
    [ "$HTTP_STATUS" = "403" ] && echo "✅ PASS (correctly rejected)" || echo "❌ FAIL (unexpected status: $HTTP_STATUS)"
    echo "   Response: $(cat /tmp/response.json | jq -c '.')"
else
    echo "   ❌ Failed to get contributor token"
fi

echo
echo "📋 Manual Commands Reference:"
echo "==============================="
echo "# Set the observer token as environment variable:"
echo "export ACCESS_TOKEN='$ACCESS_TOKEN'"
echo
echo "# Basic endpoint tests:"
echo "curl -H \"Authorization: Bearer \$ACCESS_TOKEN\" http://localhost:8000/user-info | jq '.'"
echo "curl -H \"Authorization: Bearer \$ACCESS_TOKEN\" http://localhost:8000/observer | jq '.'"
echo "curl -H \"Authorization: Bearer \$ACCESS_TOKEN\" http://localhost:8000/contributor | jq '.'"
echo
echo "# Test different user roles:"
echo "# Observer user (current):"
echo "aws cognito-idp initiate-auth \\"
echo "  --endpoint-url http://localhost:8100 \\"
echo "  --auth-flow USER_PASSWORD_AUTH \\"
echo "  --client-id mock-client-id-123456 \\"
echo "  --auth-parameters USERNAME=testuser_observer,PASSWORD=TempPass123!"
echo
echo "# Contributor user:"
echo "aws cognito-idp initiate-auth \\"
echo "  --endpoint-url http://localhost:8100 \\"
echo "  --auth-flow USER_PASSWORD_AUTH \\"
echo "  --client-id mock-client-id-123456 \\"
echo "  --auth-parameters USERNAME=testuser_contributor,PASSWORD=TempPass123!"
echo
echo "# Partner user:"
echo "aws cognito-idp initiate-auth \\"
echo "  --endpoint-url http://localhost:8100 \\"
echo "  --auth-flow USER_PASSWORD_AUTH \\"
echo "  --client-id mock-client-id-123456 \\"
echo "  --auth-parameters USERNAME=testuser_partner,PASSWORD=TempPass123!"
echo
echo "# Core member user:"
echo "aws cognito-idp initiate-auth \\"
echo "  --endpoint-url http://localhost:8100 \\"
echo "  --auth-flow USER_PASSWORD_AUTH \\"
echo "  --client-id mock-client-id-123456 \\"
echo "  --auth-parameters USERNAME=testuser_core_member,PASSWORD=TempPass123!"

# Cleanup
rm -f /tmp/response.json

echo
echo "✅ Demo completed!"