#!/usr/bin/env bash
##
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0
##

# Run Management API BDD Tests
#
# This script runs BDD tests for the FRANK Management API.
#
# Usage:
#   ./run_management_api_tests.sh [management_port] [cognito_port] [tags]
#
# Examples:
#   ./run_management_api_tests.sh                    # Use defaults (8200, 8100)
#   ./run_management_api_tests.sh 9000 8100          # Custom ports
#   ./run_management_api_tests.sh 8200 8100 @users   # Run only @users tests
#   ./run_management_api_tests.sh 8200 8100 @auth    # Run only @auth tests

set -e

# Default ports
MANAGEMENT_PORT=${1:-8001}
COGNITO_PORT=${2:-8100}
TAGS=${3:-}

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}FRANK Management API BDD Tests${NC}"
echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}Management API Port:${NC} $MANAGEMENT_PORT"
echo -e "${GREEN}Mock Cognito Port:${NC}   $COGNITO_PORT"
if [ -n "$TAGS" ]; then
    echo -e "${GREEN}Tags:${NC}                $TAGS"
fi
echo -e "${BLUE}============================================================${NC}"

# Check if Management API is running
echo -e "${YELLOW}Checking Management API availability...${NC}"
if ! curl -s -f "http://localhost:$MANAGEMENT_PORT/health" > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Management API is not running on port $MANAGEMENT_PORT${NC}"
    echo -e "${YELLOW}Start it with: python -m frank.management.server${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Management API is running${NC}"

# Check if Mock Cognito is running
echo -e "${YELLOW}Checking Mock Cognito availability...${NC}"
if ! curl -s -f "http://localhost:$COGNITO_PORT/health" > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Cognito stub is not running on port $COGNITO_PORT${NC}"
    echo -e "${YELLOW}Start it with: uv run python tests/stubs/cognito/stub_cognito.py${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Mock Cognito is running${NC}"

echo -e "${BLUE}============================================================${NC}"
echo -e "${YELLOW}Running BDD tests...${NC}"
echo ""

# Build behave command
BEHAVE_CMD="behave features/management_api_users.feature -D management_port=$MANAGEMENT_PORT -D cognito_port=$COGNITO_PORT"

if [ -n "$TAGS" ]; then
    BEHAVE_CMD="$BEHAVE_CMD --tags=$TAGS"
fi

# Run tests
$BEHAVE_CMD

# Capture exit code
EXIT_CODE=$?

echo ""
echo -e "${BLUE}============================================================${NC}"
if [ $EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
else
    echo -e "${RED}✗ Some tests failed (exit code: $EXIT_CODE)${NC}"
fi
echo -e "${BLUE}============================================================${NC}"

exit $EXIT_CODE
