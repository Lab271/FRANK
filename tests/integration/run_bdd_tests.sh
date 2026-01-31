#!/bin/bash
#
# FRANK Platform - Run BDD Tests
#
# Examples of running BDD tests with different configurations
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

echo -e "${BLUE}=== FRANK BDD Test Runner ===${NC}"
echo ""

# Check if behave is installed
if ! command -v behave &> /dev/null; then
    echo -e "${RED}Error: behave is not installed${NC}"
    echo "Install with: pip install behave"
    exit 1
fi

# Parse command-line arguments
SERVER_PORT=${1:-8000}
COGNITO_PORT=${2:-8100}
TAGS=${3:-}

echo -e "${YELLOW}Configuration:${NC}"
echo "  Server Port: $SERVER_PORT"
echo "  Cognito Port: $COGNITO_PORT"
if [ -n "$TAGS" ]; then
    echo "  Tags: $TAGS"
fi
echo ""

# Build behave command
BEHAVE_CMD="behave -D server_port=$SERVER_PORT -D cognito_port=$COGNITO_PORT"

if [ -n "$TAGS" ]; then
    BEHAVE_CMD="$BEHAVE_CMD --tags=$TAGS"
fi

# Run tests
echo -e "${BLUE}Running BDD tests...${NC}"
echo "Command: $BEHAVE_CMD"
echo ""

if $BEHAVE_CMD; then
    echo ""
    echo -e "${GREEN}✅ All BDD tests passed!${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}❌ Some BDD tests failed${NC}"
    exit 1
fi
