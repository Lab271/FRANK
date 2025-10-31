#!/bin/bash
# Test Script for Greeting MCP Server
# Copyright (c) 2025 LAB271
# SPDX-License-Identifier: Apache-2.0

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BASE_URL="https://mcp.local"
GREETING_URL="${BASE_URL}/greeting"

echo -e "${BLUE}🧪 Testing Greeting MCP Server${NC}"
echo "Base URL: ${BASE_URL}"
echo "Greeting Service: ${GREETING_URL}"
echo ""

# Function to test endpoint
test_endpoint() {
    local url=$1
    local expected_status=$2
    local description=$3
    
    echo -e "${YELLOW}Testing: ${description}${NC}"
    echo "URL: ${url}"
    
    response=$(curl -sk -w "\n%{http_code}" "${url}" 2>/dev/null)
    body=$(echo "$response" | head -n -1)
    status=$(echo "$response" | tail -n 1)
    
    if [ "$status" -eq "$expected_status" ]; then
        echo -e "${GREEN}✅ PASS${NC} (Status: $status)"
        if [ -n "$body" ]; then
            echo "Response: $body" | jq . 2>/dev/null || echo "Response: $body"
        fi
    else
        echo -e "${RED}❌ FAIL${NC} (Expected: $expected_status, Got: $status)"
        echo "Response: $body"
    fi
    echo ""
}

# Function to test MCP tools via JSON-RPC (if server supports it)
test_mcp_tool() {
    local tool_name=$1
    local params=$2
    local description=$3
    
    echo -e "${YELLOW}Testing MCP Tool: ${description}${NC}"
    
    # Create JSON-RPC request
    json_request=$(cat <<EOF
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "${tool_name}",
        "arguments": ${params}
    }
}
EOF
)
    
    echo "Request: $json_request" | jq .
    
    response=$(curl -sk \
        -H "Content-Type: application/json" \
        -d "$json_request" \
        "${GREETING_URL}/mcp" 2>/dev/null || echo "")
    
    if [ -n "$response" ]; then
        echo -e "${GREEN}✅ Response received${NC}"
        echo "$response" | jq . 2>/dev/null || echo "Response: $response"
    else
        echo -e "${RED}❌ No response or endpoint not available${NC}"
    fi
    echo ""
}

echo "=== 1. Gateway and Health Checks ==="

# Test gateway root
test_endpoint "${BASE_URL}/" 200 "Gateway Root"

# Test gateway health
test_endpoint "${BASE_URL}/health" 200 "Gateway Health"

# Test greeting service health
test_endpoint "${GREETING_URL}/health" 200 "Greeting Service Health"

echo "=== 2. Service Discovery ==="

# Check if greeting service is listed in gateway
echo -e "${YELLOW}Checking if greeting service is registered in gateway...${NC}"
gateway_response=$(curl -sk "${BASE_URL}/" 2>/dev/null)
if echo "$gateway_response" | grep -q "greeting"; then
    echo -e "${GREEN}✅ Greeting service found in gateway${NC}"
    echo "$gateway_response" | jq .services 2>/dev/null || echo "Services: $gateway_response"
else
    echo -e "${RED}❌ Greeting service not found in gateway${NC}"
fi
echo ""

echo "=== 3. MCP Protocol Tests ==="

# Test if MCP endpoint exists (try different possible endpoints)
for endpoint in "/mcp" "/jsonrpc" "/rpc" ""; do
    full_url="${GREETING_URL}${endpoint}"
    echo -e "${YELLOW}Trying MCP endpoint: ${full_url}${NC}"
    
    # Try to get server info
    server_info=$(cat <<EOF
{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {
            "name": "test-client",
            "version": "1.0.0"
        }
    }
}
EOF
)
    
    response=$(curl -sk \
        -H "Content-Type: application/json" \
        -d "$server_info" \
        "${full_url}" 2>/dev/null || echo "")
    
    if [ -n "$response" ] && echo "$response" | grep -q "result\|capabilities\|serverInfo"; then
        echo -e "${GREEN}✅ MCP endpoint found at: ${endpoint}${NC}"
        echo "$response" | jq . 2>/dev/null || echo "Response: $response"
        
        # Test greeting tool
        echo ""
        test_mcp_tool "greet" '{"name": "Alice"}' "Greet Alice"
        
        # Test farewell tool
        test_mcp_tool "farewell" '{"name": "Bob"}' "Farewell Bob"
        
        break
    else
        echo -e "${RED}❌ No MCP response from: ${endpoint}${NC}"
    fi
done

echo ""
echo "=== 4. Error Handling Tests ==="

# Test invalid endpoints
test_endpoint "${GREETING_URL}/invalid" 404 "Invalid Endpoint"

# Test method not allowed (if applicable)
echo -e "${YELLOW}Testing POST to health endpoint...${NC}"
post_response=$(curl -sk -X POST "${GREETING_URL}/health" -w "\n%{http_code}" 2>/dev/null || echo -e "\n500")
post_body=$(echo "$post_response" | head -n -1)
post_status=$(echo "$post_response" | tail -n 1)
echo "POST Status: $post_status"
echo ""

echo "=== 5. Performance Test ==="

# Simple performance test
echo -e "${YELLOW}Testing response time (5 requests)...${NC}"
total_time=0
for i in {1..5}; do
    time_taken=$(curl -sk -w "%{time_total}" -o /dev/null "${GREETING_URL}/health" 2>/dev/null || echo "0")
    echo "Request $i: ${time_taken}s"
    total_time=$(echo "$total_time + $time_taken" | bc -l 2>/dev/null || echo "$total_time")
done

if command -v bc &> /dev/null; then
    avg_time=$(echo "scale=3; $total_time / 5" | bc)
    echo "Average response time: ${avg_time}s"
else
    echo "Average response time: ~$(echo "$total_time / 5" | cut -d. -f1)s (approx)"
fi

echo ""
echo -e "${BLUE}🏁 Testing Complete!${NC}"
echo ""
echo "Manual test commands:"
echo "  curl -sk ${BASE_URL}/"
echo "  curl -sk ${GREETING_URL}/health"
echo "  curl -sk ${BASE_URL}/health"
echo ""
echo "View logs:"
echo "  make logs-greeting-mcp"
echo "  make logs"