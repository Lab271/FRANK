#!/bin/bash

# Mock Cognito Service Local Test Script
# Tests the Mock Cognito service running on port 8100

set -e

echo "🔐 Mock Cognito Service Test"
echo "============================="

# Configuration
MOCK_COGNITO_URL="http://localhost:8100"

# Set AWS credentials for mock service
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=eu-west-1

echo "1. 📋 Testing Mock Cognito service at $MOCK_COGNITO_URL"

# Check if Mock Cognito is running
printf "   🏥 Testing health endpoint: "
curl -s "$MOCK_COGNITO_URL/health" | grep -q "healthy" && echo "✅ PASS" || echo "❌ FAIL"

# Test service info endpoint
printf "   📖 Testing service info endpoint: "
curl -s "$MOCK_COGNITO_URL/" | grep -q "Mock Cognito Service" && echo "✅ PASS" || echo "❌ FAIL"

# Test user list endpoint
printf "   👥 Testing user list endpoint: "
curl -s "$MOCK_COGNITO_URL/auth/users" | grep -q "testuser_observer" && echo "✅ PASS" || echo "❌ FAIL"

echo
echo "2. 🧪 Testing AWS CLI Authentication Flow..."

# Test AWS CLI InitiateAuth for different users
test_aws_cli_auth() {
    local username="$1"
    local expected_group="$2"
    
    set +e  # Temporarily disable exit on error
    printf "   🎫 Testing AWS CLI auth for $username: "
    
    AUTH_RESPONSE=$(aws cognito-idp initiate-auth \
        --endpoint-url "$MOCK_COGNITO_URL" \
        --auth-flow USER_PASSWORD_AUTH \
        --client-id mock-client-id-123456 \
        --auth-parameters USERNAME="$username",PASSWORD=TempPass123! \
        --output json 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        ACCESS_TOKEN=$(echo "$AUTH_RESPONSE" | jq -r '.AuthenticationResult.AccessToken')
        if [ "$ACCESS_TOKEN" != "null" ] && [ -n "$ACCESS_TOKEN" ]; then
            echo "✅ PASS"
            echo "      Token length: ${#ACCESS_TOKEN}"
            
            # Test GetUser with the token
            printf "      Testing GetUser API: "
            USER_RESPONSE=$(aws cognito-idp get-user \
                --endpoint-url "$MOCK_COGNITO_URL" \
                --access-token "$ACCESS_TOKEN" \
                --output json 2>/dev/null)
            
            if [ $? -eq 0 ]; then
                USERNAME_FROM_API=$(echo "$USER_RESPONSE" | jq -r '.Username')
                if [ "$USERNAME_FROM_API" = "$username" ]; then
                    echo "✅ PASS"
                else
                    echo "❌ FAIL (wrong username: $USERNAME_FROM_API)"
                fi
            else
                echo "❌ FAIL (GetUser failed)"
            fi
        else
            echo "❌ FAIL (no access token)"
        fi
    else
        echo "❌ FAIL (auth failed)"
    fi
    set -e  # Re-enable exit on error
}

# Test all user types
test_aws_cli_auth "testuser_observer" "observer"
test_aws_cli_auth "testuser_contributor" "contributor"
test_aws_cli_auth "testuser_partner" "partner"
test_aws_cli_auth "testuser_core_member" "core_member"

echo
echo "3. 🔒 Testing REST API Authentication..."

# Test REST login endpoint
test_rest_login() {
    local username="$1"
    
    printf "   🔑 Testing REST login for $username: "
    
    RESPONSE=$(curl -s -w "HTTPSTATUS:%{http_code}" \
        -H "Content-Type: application/json" \
        -d "{\"username\": \"$username\", \"password\": \"TempPass123!\"}" \
        "$MOCK_COGNITO_URL/auth/login")
    
    HTTP_CODE=$(echo "$RESPONSE" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
    BODY=$(echo "$RESPONSE" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')
    
    if [ "$HTTP_CODE" = "200" ]; then
        ACCESS_TOKEN=$(echo "$BODY" | jq -r '.access_token')
        if [ "$ACCESS_TOKEN" != "null" ] && [ -n "$ACCESS_TOKEN" ]; then
            echo "✅ PASS"
            
            # Test token validation
            printf "      Testing token validation: "
            VALIDATION_RESPONSE=$(curl -s -H "Content-Type: application/json" \
                -d "{\"token\": \"$ACCESS_TOKEN\"}" \
                "$MOCK_COGNITO_URL/auth/validate")
            
            VALID=$(echo "$VALIDATION_RESPONSE" | jq -r '.valid')
            if [ "$VALID" = "true" ]; then
                echo "✅ PASS"
            else
                echo "❌ FAIL (validation failed)"
            fi
        else
            echo "❌ FAIL (no access token)"
        fi
    else
        echo "❌ FAIL (HTTP $HTTP_CODE)"
    fi
}

# Test REST login for all users
test_rest_login "testuser_observer"
test_rest_login "testuser_contributor"
test_rest_login "testuser_partner"
test_rest_login "testuser_core_member"

echo
echo "4. ❌ Testing Invalid Credentials..."
set +e  # Temporarily disable exit on error

# Test invalid username
printf "   🚫 Testing invalid username: "
AUTH_ERROR=$(aws cognito-idp initiate-auth \
    --endpoint-url "$MOCK_COGNITO_URL" \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id mock-client-id-123456 \
    --auth-parameters USERNAME=invalid_user,PASSWORD=TempPass123! \
    --output json 2>&1)
AUTH_EXIT_CODE=$?

if [ $AUTH_EXIT_CODE -ne 0 ]; then
    # Check if error contains expected AWS error format
    if echo "$AUTH_ERROR" | grep -q "UserNotFoundException\|An error occurred (400)"; then
        echo "✅ PASS (correctly rejected with AWS error)"
    else
        echo "❌ FAIL (unexpected error format: $AUTH_ERROR)"
    fi
else
    echo "❌ FAIL (should have been rejected)"
fi

# Test invalid password
printf "   🚫 Testing invalid password: "
AUTH_ERROR=$(aws cognito-idp initiate-auth \
    --endpoint-url "$MOCK_COGNITO_URL" \
    --auth-flow USER_PASSWORD_AUTH \
    --client-id mock-client-id-123456 \
    --auth-parameters USERNAME=testuser_observer,PASSWORD=wrongpassword \
    --output json 2>&1)
AUTH_EXIT_CODE=$?

if [ $AUTH_EXIT_CODE -ne 0 ]; then
    # Check if error contains expected AWS error format for wrong password
    if echo "$AUTH_ERROR" | grep -q "NotAuthorizedException\|An error occurred (400)"; then
        echo "✅ PASS (correctly rejected with AWS error)"
    else
        echo "❌ FAIL (unexpected error format: $AUTH_ERROR)"
    fi
else
    echo "❌ FAIL (should have been rejected)"
fi

echo
echo "5. 🔧 Testing AWS API Operations..."

# Test missing X-Amz-Target header
printf "   🚫 Testing missing X-Amz-Target header: "
RESPONSE=$(curl -s -w "%{http_code}" -o /tmp/response.json \
    -H "Content-Type: application/x-amz-json-1.1" \
    -d '{}' \
    "$MOCK_COGNITO_URL/")

if [ "$RESPONSE" = "400" ]; then
    echo "✅ PASS (correctly rejected)"
else
    echo "❌ FAIL (unexpected status: $RESPONSE)"
fi

# Test invalid operation
printf "   🚫 Testing invalid operation: "
RESPONSE=$(curl -s -w "%{http_code}" -o /tmp/response.json \
    -H "X-Amz-Target: AWSCognitoIdentityProviderService.InvalidOperation" \
    -H "Content-Type: application/x-amz-json-1.1" \
    -d '{}' \
    "$MOCK_COGNITO_URL/")

if [ "$RESPONSE" = "400" ]; then
    echo "✅ PASS (correctly rejected)"
else
    echo "❌ FAIL (unexpected status: $RESPONSE)"
fi

# Test invalid credentials with curl (direct HTTP status validation)
printf "   🚫 Testing invalid password with curl: "
RESPONSE=$(curl -s -w "HTTPSTATUS:%{http_code}" \
    -H "X-Amz-Target: AWSCognitoIdentityProviderService.InitiateAuth" \
    -H "Content-Type: application/x-amz-json-1.1" \
    -d '{
        "AuthFlow": "USER_PASSWORD_AUTH",
        "ClientId": "mock-client-id-123456",
        "AuthParameters": {
            "USERNAME": "testuser_observer",
            "PASSWORD": "wrongpassword"
        }
    }' \
    "$MOCK_COGNITO_URL/")

HTTP_CODE=$(echo "$RESPONSE" | tr -d '\n' | sed -E 's/.*HTTPSTATUS:([0-9]{3})$/\1/')
BODY=$(echo "$RESPONSE" | sed -E 's/HTTPSTATUS:[0-9]{3}$//')

if [ "$HTTP_CODE" = "400" ]; then
    # Check if response body contains AWS-style error
    if echo "$BODY" | jq -r '.__type // empty' 2>/dev/null | grep -q "NotAuthorizedException"; then
        echo "✅ PASS (HTTP 400 with NotAuthorizedException)"
    else
        echo "❌ FAIL (HTTP 400 but wrong error type: $(echo "$BODY" | jq -r '.__type // "none"' 2>/dev/null))"
    fi
else
    echo "❌ FAIL (unexpected HTTP status: $HTTP_CODE)"
fi
set -e  # Re-enable exit on error

echo
echo "📋 Manual Test Commands:"
echo "========================"
echo "Get access token:"
echo -e "\033[33maws cognito-idp initiate-auth \ \033[0m"
echo -e "\033[33m  --endpoint-url $MOCK_COGNITO_URL \ \033[0m"
echo -e "\033[33m  --auth-flow USER_PASSWORD_AUTH \ "
echo -e "\033[33m  --client-id mock-client-id-123456 \ \033[0m"
echo -e "\033[33m  --auth-parameters USERNAME=testuser_observer,PASSWORD=TempPass123!\033[0m"
echo
echo "# Test with curl (REST API):"
echo -e "\033[33mcurl -H \"Content-Type: application/json\" \ \033[0m"
echo -e "\033[33m     -d '{\"username\": \"testuser_observer\", \"password\": \"TempPass123!\"}' \ \033[0m"
echo -e "\033[33m     $MOCK_COGNITO_URL/auth/login\033[0m"
echo
echo "# Check service health:"
echo -e "\033[33mcurl $MOCK_COGNITO_URL/health\033[0m"

# Cleanup
rm -f /tmp/response.json

echo
echo "✅ Mock Cognito tests completed!"