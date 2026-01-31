#!/bin/bash
#
# FRANK Platform - Test Comprehensive Fixture Data
#
# This script tests the complete fixture system by:
# 1. Initializing the database with fixture data
# 2. Starting mock_cognito (shows organizations and users)
# 3. Testing authentication for users from different tiers
#
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0

set -e

echo "=== FRANK Comprehensive Fixture Test ==="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Step 1: Initialize database
echo -e "${BLUE}Step 1: Initializing database with fixture data...${NC}"
uv run python init_fixtures.py
echo ""

# Step 2: Instructions for starting mock_cognito
echo -e "${BLUE}Step 2: Mock Cognito Server${NC}"
echo "To start mock_cognito and see organizations/users, run:"
echo ""
echo "  cd tests/spikes/014_cognito"
echo "  uv run python mock_cognito.py --reload"
echo ""
echo "You should see:"
echo "  - 6 organizations grouped by tier"
echo "  - 7 users linked to organizations"
echo "  - User summary table"
echo ""

# Step 3: Test instructions
echo -e "${BLUE}Step 3: Test Authentication (in another terminal)${NC}"
echo ""
echo "Test Core Member (sees everything):"
echo "  curl -X POST http://localhost:8100/auth/login \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"username\": \"admin\", \"password\": \"admin123\"}'"
echo ""
echo "Test Partner (sees partner-level data):"
echo "  curl -X POST http://localhost:8100/auth/login \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"username\": \"s_unit_analyst\", \"password\": \"TempPass123!\"}'"
echo ""
echo "Test Observer (sees only own org):"
echo "  curl -X POST http://localhost:8100/auth/login \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"username\": \"kpn_observer\", \"password\": \"TempPass123!\"}'"
echo ""

echo -e "${GREEN}✅ Database initialized successfully!${NC}"
echo "Follow the steps above to test the complete system."
