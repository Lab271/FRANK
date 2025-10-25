#!/bin/bash

# Stage 3 API Local Test Script
# Tests the Simple API service running on port 8000 with Mock Cognito authentication

set -e

echo "🚀 Stage 3 API Test Insert"
echo "=========================="

# Configuration
# Use port from command line argument if provided, otherwise default to 8000
PORT="${1:-8000}"
SIMPLE_API_URL="http://localhost:$PORT"
MOCK_COGNITO_URL="http://localhost:8100"


# Set AWS credentials for mock service
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=eu-west-1

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
# OBSERVER_TOKEN=$(get_access_token "testuser_observer")
# CONTRIBUTOR_TOKEN=$(get_access_token "testuser_contributor")
# PARTNER_TOKEN=$(get_access_token "testuser_partner")
CORE_MEMBER_TOKEN=$(get_access_token "testuser_core_member")

if [ "$CORE_MEMBER_TOKEN" = "ERROR" ]; then
    echo "❌ Failed to get core member token - is Mock Cognito running on $MOCK_COGNITO_URL?"
    exit 1
fi

echo "📋 Inserting smallest submissions at $SIMPLE_API_URL"
ORG_UUID="$(python -c 'import uuid; print(uuid.uuid4())')"
# Test inserting a submission
response=$(curl -s -w "%{http_code}" -o /tmp/submission_response.json -X POST "$SIMPLE_API_URL/v1/submission" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $CORE_MEMBER_TOKEN" \
    -d '{ 
        "submission": { 
            "submitter": { 
                "organisation_id": "identity--'$ORG_UUID'" 
            }, 
            "sighting": { 
                "observables": { 
                    "network": [ 
                        { 
                            "type": "ipv4-addr", 
                            "value": "185.220.102.45" 
                        }, 
                        { 
                            "type": "domain-name", 
                            "value": "secure-bank-verify.nl" 
                        } 
                    ] 
                } 
            } 
        } 
    }')
http_code="${response: -3}"
if [ "$http_code" -eq 200 ]; then
    python -m json.tool < /tmp/submission_response.json
    rm -f /tmp/submission_response.json
    echo "✅ Submission insert test PASSED"
else
    echo "❌ Error: Received HTTP status $http_code"
    cat /tmp/submission_response.json
fi



echo "📋 Inserting submissions at $SIMPLE_API_URL"
SUB_UUID="$(python -c 'import uuid; print(uuid.uuid4())')"
SIGHT_UUID="$(python -c 'import uuid; print(uuid.uuid4())')"
# Test inserting a submission
response=$(curl -s -w "%{http_code}" -o /tmp/submission_response.json -X POST "$SIMPLE_API_URL/v1/submission" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $CORE_MEMBER_TOKEN" \
    -d '{ 
        "submission": { 
            "submission_id": "submission--'$SUB_UUID'", 
            "submitter": { 
                "organisation_id": "identity--f431f809-377b-45e0-aa1c-6a4751cae5ff", 
                "access_level": "partner",
                "organisation_type": "cyber_partner" 
            }, 
            "sighting": { 
                "hit_target": { 
                    "region": "EU",
                    "sector": "financial"
                },
                "sighting_id": "sighting--'$SIGHT_UUID'", 
                "timestamp": "2025-01-20T14:30:22Z", 
                "confidence": 87, 
                "observables": { 
                    "network": [ 
                        { 
                            "type": "ipv4-addr", 
                            "value": "185.220.102.45" 
                        }, 
                        { 
                            "type": "domain-name", 
                            "value": "secure-bank-verify.nl" 
                        } 
                    ] 
                } 
            } 
        } 
    }')
http_code="${response: -3}"
if [ "$http_code" -eq 200 ]; then
    python -m json.tool < /tmp/submission_response.json

    submission_id=$(jq -r '.submission_id' /tmp/submission_response.json)
    rm -f /tmp/submission_response.json
    echo "✅ Submission insert test PASSED"
else
    echo "❌ Error: Received HTTP status $http_code"
    cat /tmp/submission_response.json
fi

curl -s -X GET "$SIMPLE_API_URL/v1/submission/$submission_id" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $CORE_MEMBER_TOKEN" | python -m json.tool 


curl -s -X GET "$SIMPLE_API_URL/v1/sightings?observable=185.220.102.45" \
    -H "Accept: application/stix+json" \
    -H "Authorization: Bearer $CORE_MEMBER_TOKEN" | python -m json.tool 
