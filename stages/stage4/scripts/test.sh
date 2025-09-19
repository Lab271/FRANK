#!/bin/bash

echo "🧪 Testing FRANK LocalStack API..."

# Change to terraform directory to get outputs
cd "$(dirname "$0")/../localstack/terraform"

# Get API details
API_ID=$(terraform output -raw api_gateway_id 2>/dev/null || echo "")
API_KEY=$(terraform output -raw api_key 2>/dev/null || echo "")

if [[ -z "$API_ID" || -z "$API_KEY" ]]; then
    echo "❌ Failed to get API details. Make sure deployment is complete."
    exit 1
fi

BASE_URL="http://localhost:4566/restapis/${API_ID}/local/_user_request_"

echo "🔍 Testing API endpoints..."
echo "   Base URL: ${BASE_URL}"
echo "   API Key: ${API_KEY}"
echo ""

# Test data
TEST_SUBMISSION='{
    "submission": {
      "submitter": {
        "access_level": "partner",
        "sector": "finance"
      },
      "sighting": {
        "sighting_id": "test-sighting-001",
        "timestamp": "2025-09-05T12:00:00Z",
        "confidence": 85,
        "observables": {
          "network": [
            {
              "type": "ipv4",
              "value": "192.168.1.100",
              "role": "c2_server"
            },
            {
              "type": "domain",
              "value": "malicious.example.com",
              "role": "phishing_domain"
            }
          ]
        }
      }
    }
  }'

# Test 1: POST /v1/submission
echo "1️⃣  Testing POST /v1/submission..."
echo "   Response:"
curl -s -X POST "${BASE_URL}/v1/submission" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: ${API_KEY}" \
  -d "$TEST_SUBMISSION" | jq '.' 2>/dev/null || curl -s -X POST "${BASE_URL}/v1/submission" \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: ${API_KEY}" \
  -d "$TEST_SUBMISSION"

echo -e "\n"

# Test 2: GET /v1/stats
echo "2️⃣  Testing GET /v1/stats..."
echo "   Response:"
curl -s "${BASE_URL}/v1/stats?sector=finance&time_range=24h" \
  -H "X-Api-Key: ${API_KEY}" | jq '.' 2>/dev/null || curl -s "${BASE_URL}/v1/stats?sector=finance&time_range=24h" \
  -H "X-Api-Key: ${API_KEY}"

echo -e "\n"

# Test 3: GET /v1/sighting
echo "3️⃣  Testing GET /v1/sighting..."
echo "   Response:"
curl -s "${BASE_URL}/v1/sighting?limit=5" \
  -H "X-Api-Key: ${API_KEY}" | jq '.' 2>/dev/null || curl -s "${BASE_URL}/v1/sighting?limit=5" \
  -H "X-Api-Key: ${API_KEY}"

echo -e "\n"

# Test 4: Error handling (missing API key)
echo "4️⃣  Testing error handling (missing API key)..."
echo "   Response:"
curl -s "${BASE_URL}/v1/stats" | jq '.' 2>/dev/null || curl -s "${BASE_URL}/v1/stats"

echo -e "\n"

# Test 5: Check AWS resources
echo "5️⃣  Checking AWS resources..."
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export AWS_DEFAULT_REGION=eu-west-1

echo "   DynamoDB tables:"
aws dynamodb list-tables --endpoint-url http://localhost:4566 2>/dev/null || echo "   Failed to list DynamoDB tables"

echo "   S3 buckets:"
aws s3 ls --endpoint-url http://localhost:4566 2>/dev/null || echo "   Failed to list S3 buckets"

echo "   Lambda functions:"
aws lambda list-functions --endpoint-url http://localhost:4566 --query 'Functions[].FunctionName' 2>/dev/null || echo "   Failed to list Lambda functions"

echo ""
echo "✅ API testing complete!"
echo ""
echo "🔗 You can also test manually:"
echo "   curl -X POST ${BASE_URL}/v1/submission -H \"X-Api-Key: ${API_KEY}\" -H \"Content-Type: application/json\" -d @../../examples/minimal.json"
