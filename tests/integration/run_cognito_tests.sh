#!/usr/bin/env bash
##
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0
##

# Run Mock Cognito BDD Tests
#
# This script runs BDD tests for the Mock Cognito service.
#
# Usage:
#   ./run_cognito_tests.sh [cognito_port] [tags]
#
# Examples:
#   ./run_cognito_tests.sh                    # Use default (8100)
#   ./run_cognito_tests.sh 8100               # Explicit port
#   ./run_cognito_tests.sh 8100 @health       # Run only @health tests

set -e

# Default ports
COGNITO_PORT=${1:-8100}
TAGS=${2:-}

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}FRANK Mock Cognito BDD Tests${NC}"
echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}Mock Cognito Port:${NC}   $COGNITO_PORT"
if [ -n "$TAGS" ]; then
    echo -e "${GREEN}Tags:${NC}                $TAGS"
fi
echo -e "${BLUE}============================================================${NC}"

# Check if Mock Cognito is running
echo -e "${YELLOW}Checking Mock Cognito availability...${NC}"
if ! curl -s -f "http://localhost:$COGNITO_PORT/health" > /dev/null 2>&1; then
    echo -e "${RED}ERROR: Mock Cognito is not running on port $COGNITO_PORT${NC}"
    echo -e "${YELLOW}Start it with: cd tests/spikes/014_cognito && uv run python mock_cognito.py${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Mock Cognito is running${NC}"

echo -e "${BLUE}============================================================${NC}"
echo -e "${YELLOW}Running BDD tests...${NC}"
echo ""

# Get script directory and change to tests/integration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Build behave command
BEHAVE_CMD="uv run behave features/cognito_management.feature -D cognito_port=$COGNITO_PORT"

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
    echo -e "${GREEN}✓ All Mock Cognito tests passed!${NC}"
else
    echo -e "${RED}✗ Some Mock Cognito tests failed (exit code: $EXIT_CODE)${NC}"
fi
echo -e "${BLUE}============================================================${NC}"

exit $EXIT_CODE
