#!/bin/bash
# ===================================
# test_api.sh
# Test script for minimal DynamoDB API
# ===================================

set -e

API_URL="http://localhost:8000"
echo "🧪 Testing Minimal DynamoDB API at $API_URL"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

test_endpoint() {
    local method=$1
    local endpoint=$2
    local data=$3
    local description=$4
    
    echo -e "\n${BLUE}Testing: $description${NC}"
    echo "Request: $method $endpoint"
    
    if [ -n "$data" ]; then
        echo "Data: $data"
        response=$(curl -s -X $method "$API_URL$endpoint" \
            -H "Content-Type: application/json" \
            -d "$data")
    else
        response=$(curl -s -X $method "$API_URL$endpoint")
    fi
    
    echo -e "${GREEN}Response:${NC} $response"
    echo "Status: ✅"
}

# Wait for API to be ready
echo "⏳ Waiting for API to be ready..."
for i in {1..30}; do
    if curl -s "$API_URL/health" > /dev/null 2>&1; then
        echo "✅ API is ready!"
        break
    fi
    echo "  Waiting... ($i/30)"
    sleep 2
done

# Test 1: Health check
test_endpoint "GET" "/" "Health Check"

# Test 2: Detailed health
test_endpoint "GET" "/health" "Detailed Health Check"

# Test 3: List records (should be empty initially)
test_endpoint "GET" "/records" "List Records (Empty)"

# Test 4: Create a record
test_endpoint "POST" "/records" '{
    "name": "Test Record 1",
    "data": "This is test data",
    "category": "testing"
}' "Create Record 1"

# Test 5: Create another record
test_endpoint "POST" "/records" '{
    "name": "Test Record 2", 
    "data": "More test data",
    "category": "demo"
}' "Create Record 2"

# Test 6: List records (should have 2 now)
echo -e "\n${BLUE}Testing: List All Records${NC}"
echo "Request: GET /records"
records_response=$(curl -s "$API_URL/records")
echo -e "${GREEN}Response:${NC} $records_response"

# Extract first record ID for individual tests
first_record_id=$(echo $records_response | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data and len(data) > 0:
    print(data[0]['id'])
else:
    print('no-id')
")

if [ "$first_record_id" != "no-id" ]; then
    # Test 7: Get specific record
    test_endpoint "GET" "/records/$first_record_id" "Get Specific Record"
    
    # Test 8: Delete record
    test_endpoint "DELETE" "/records/$first_record_id" "Delete Record"
    
    # Test 9: Try to get deleted record (should fail)
    echo -e "\n${BLUE}Testing: Get Deleted Record (Should Fail)${NC}"
    echo "Request: GET /records/$first_record_id"
    
    http_code=$(curl -s -o /dev/null -w "%{http_code}" "$API_URL/records/$first_record_id")
    if [ "$http_code" = "404" ]; then
        echo -e "${GREEN}Response: 404 Not Found ✅${NC}"
    else
        echo -e "${RED}Unexpected response code: $http_code ❌${NC}"
    fi
fi

# Test 10: Final record count
test_endpoint "GET" "/records" "Final Records List"

echo -e "\n🎉 ${GREEN}All tests completed!${NC}"
echo ""
echo "🌐 API Documentation: http://localhost:8000/docs"
echo "🗃️  DynamoDB Admin: http://localhost:8001"