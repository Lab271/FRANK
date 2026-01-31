#!/usr/bin/env bash
##
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0
##

# Run FRANK Server API BDD Tests
#
# This script runs BDD tests for the FRANK Server API.
#
# Usage:
#   ./run_frank_api_tests.sh [server_port] [tags]
#
# Examples:
#   ./run_frank_api_tests.sh                    # Use default (8000)
#   ./run_frank_api_tests.sh 8000               # Explicit port
#   ./run_frank_api_tests.sh 8000 @health       # Run only @health tests

set -e

# Default ports
SERVER_PORT=${1:-8000}
TAGS=${2:-}

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}FRANK Server API BDD Tests${NC}"
echo -e "${BLUE}============================================================${NC}"
echo -e "${GREEN}Server Port:${NC}   $SERVER_PORT"
if [ -n "$TAGS" ]; then
    echo -e "${GREEN}Tags:${NC}          $TAGS"
fi
echo -e "${BLUE}============================================================${NC}"

# Check if FRANK API is running
echo -e "${YELLOW}Checking FRANK API availability...${NC}"
if ! curl -s -f "http://localhost:$SERVER_PORT/v1/health" > /dev/null 2>&1; then
    echo -e "${RED}ERROR: FRANK API is not running on port $SERVER_PORT${NC}"
    echo -e "${YELLOW}Start it with: python -m frank.server${NC}"
    exit 1
fi
echo -e "${GREEN}✓ FRANK API is running${NC}"

echo -e "${BLUE}============================================================${NC}"
echo -e "${YELLOW}Running BDD tests...${NC}"
echo ""

# Get script directory and change to tests/integration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Build behave command
BEHAVE_CMD="uv run behave features/frank_server_api.feature -D server_port=$SERVER_PORT"

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
    echo -e "${GREEN}✓ All FRANK API tests passed!${NC}"
else
    echo -e "${RED}✗ Some FRANK API tests failed (exit code: $EXIT_CODE)${NC}"
fi
echo -e "${BLUE}============================================================${NC}"

exit $EXIT_CODE
