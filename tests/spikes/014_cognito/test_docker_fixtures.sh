#!/bin/bash
#
# FRANK Platform - Test Docker Fixture Loading
#
# This script tests that fixtures are properly loaded in Docker containers
#
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== FRANK Docker Fixture Loading Test ===${NC}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running${NC}"
    exit 1
fi

# Build and start containers
echo -e "${BLUE}Step 1: Building and starting containers...${NC}"
docker compose build --no-cache
docker compose up -d

echo ""
echo -e "${YELLOW}Waiting for containers to start (15 seconds)...${NC}"
sleep 15

# Test 1: Check if mock-cognito shows organizations
echo ""
echo -e "${BLUE}Step 2: Checking Mock Cognito fixture data...${NC}"
if docker logs mock-cognito 2>&1 | grep -q "Schuberg Philis"; then
    echo -e "${GREEN}✅ Mock Cognito shows organizations${NC}"
else
    echo -e "${RED}❌ Mock Cognito not showing organizations${NC}"
    echo "Logs:"
    docker logs mock-cognito | tail -20
fi

# Test 2: Check if simple-api loaded fixtures
echo ""
echo -e "${BLUE}Step 3: Checking Simple API fixture loading...${NC}"
if docker logs simple-api 2>&1 | grep -q "Fixtures loaded successfully"; then
    echo -e "${GREEN}✅ Simple API loaded fixtures${NC}"
else
    echo -e "${RED}❌ Simple API did not load fixtures${NC}"
    echo "Logs:"
    docker logs simple-api | tail -20
fi

# Test 3: Verify database has organizations
echo ""
echo -e "${BLUE}Step 4: Verifying database organizations...${NC}"
ORG_COUNT=$(docker exec simple-api sqlite3 /data/frank.db "SELECT COUNT(*) FROM organisations;" 2>/dev/null || echo "0")
if [ "$ORG_COUNT" -ge 6 ]; then
    echo -e "${GREEN}✅ Database has $ORG_COUNT organizations${NC}"
    docker exec simple-api sqlite3 /data/frank.db "SELECT organisation_id, name, access_level FROM organisations;" 2>/dev/null | head -7
else
    echo -e "${RED}❌ Database has only $ORG_COUNT organizations (expected 6+)${NC}"
fi

# Test 4: Verify memberships
echo ""
echo -e "${BLUE}Step 5: Verifying organization memberships...${NC}"
MEMBER_COUNT=$(docker exec simple-api sqlite3 /data/frank.db "SELECT COUNT(*) FROM organisation_members;" 2>/dev/null || echo "0")
if [ "$MEMBER_COUNT" -ge 7 ]; then
    echo -e "${GREEN}✅ Database has $MEMBER_COUNT memberships${NC}"
    docker exec simple-api sqlite3 /data/frank.db "SELECT organisation_id, username, role FROM organisation_members LIMIT 5;" 2>/dev/null
else
    echo -e "${RED}❌ Database has only $MEMBER_COUNT memberships (expected 7+)${NC}"
fi

# Test 5: Test authentication
echo ""
echo -e "${BLUE}Step 6: Testing authentication...${NC}"

# Wait for services to be fully ready
echo "Waiting for services to be ready..."
sleep 5

# Test admin login
if curl -s -X POST http://localhost:8100/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "admin", "password": "admin123"}' | grep -q "access_token"; then
    echo -e "${GREEN}✅ Admin authentication successful${NC}"
else
    echo -e "${RED}❌ Admin authentication failed${NC}"
fi

# Test partner login
if curl -s -X POST http://localhost:8100/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username": "s_unit_analyst", "password": "TempPass123!"}' | grep -q "access_token"; then
    echo -e "${GREEN}✅ Partner authentication successful${NC}"
else
    echo -e "${RED}❌ Partner authentication failed${NC}"
fi

# Summary
echo ""
echo -e "${BLUE}=== Test Summary ===${NC}"
echo ""
echo "Containers:"
docker compose ps

echo ""
echo -e "${GREEN}✅ Docker fixture loading test complete!${NC}"
echo ""
echo "Next steps:"
echo "  - Access Mock Cognito: http://localhost:8100"
echo "  - Access Simple API: http://localhost:8080"
echo "  - Access via HTTPS (nginx): https://localhost"
echo ""
echo "To view logs:"
echo "  docker logs mock-cognito"
echo "  docker logs simple-api"
echo ""
echo "To stop containers:"
echo "  docker compose down"
