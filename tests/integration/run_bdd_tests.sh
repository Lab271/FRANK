#!/usr/bin/env bash
##
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0
##

# FRANK Platform - Run All BDD Tests
#
# This script orchestrates all BDD test suites:
# - Mock Cognito tests
# - FRANK Server API tests
# - Management API tests
#
# Each test suite runs independently and checks for service availability.
# The script reports which services are available and skips unavailable ones.
#
# Usage:
#   ./run_bdd_tests.sh [options]
#
# Examples:
#   ./run_bdd_tests.sh                          # Run all available tests
#   ./run_bdd_tests.sh --skip-unavailable       # Skip unavailable services (default)
#   ./run_bdd_tests.sh --fail-on-unavailable    # Fail if any service unavailable

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default ports
COGNITO_PORT=${COGNITO_PORT:-8100}
SERVER_PORT=${SERVER_PORT:-8000}
MANAGEMENT_PORT=${MANAGEMENT_PORT:-8200}

# Parse options
FAIL_ON_UNAVAILABLE=false
for arg in "$@"; do
    case $arg in
        --fail-on-unavailable)
            FAIL_ON_UNAVAILABLE=true
            shift
            ;;
        --skip-unavailable)
            FAIL_ON_UNAVAILABLE=false
            shift
            ;;
    esac
done

echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}FRANK Platform - BDD Test Suite Orchestrator${NC}"
echo -e "${BLUE}============================================================${NC}"
echo ""

# Track test results
TOTAL_SUITES=0
PASSED_SUITES=0
FAILED_SUITES=0
SKIPPED_SUITES=0

# Function to check service availability
check_service() {
    local name=$1
    local url=$2

    if curl -s -f "$url" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ $name is available${NC}"
        return 0
    else
        echo -e "${YELLOW}✗ $name is NOT available${NC}"
        return 1
    fi
}

# Function to run a test suite
run_suite() {
    local name=$1
    local script=$2
    local port=$3

    echo ""
    echo -e "${BLUE}============================================================${NC}"
    echo -e "${BLUE}Running: $name${NC}"
    echo -e "${BLUE}============================================================${NC}"

    TOTAL_SUITES=$((TOTAL_SUITES + 1))

    if "$script" "$port"; then
        PASSED_SUITES=$((PASSED_SUITES + 1))
        return 0
    else
        FAILED_SUITES=$((FAILED_SUITES + 1))
        return 1
    fi
}

# Check service availability
echo -e "${YELLOW}Checking service availability...${NC}"
echo ""

COGNITO_AVAILABLE=false
SERVER_AVAILABLE=false
MANAGEMENT_AVAILABLE=false

if check_service "Mock Cognito" "http://localhost:$COGNITO_PORT/health"; then
    COGNITO_AVAILABLE=true
fi

if check_service "FRANK Server API" "http://localhost:$SERVER_PORT/v1/health"; then
    SERVER_AVAILABLE=true
fi

if check_service "Management API" "http://localhost:$MANAGEMENT_PORT/health"; then
    MANAGEMENT_AVAILABLE=true
fi

echo ""
echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}Test Suite Execution Plan${NC}"
echo -e "${BLUE}============================================================${NC}"

# Determine which tests to run
COGNITO_TESTS="SKIP"
SERVER_TESTS="SKIP"
MANAGEMENT_TESTS="SKIP"

if [ "$COGNITO_AVAILABLE" = true ]; then
    COGNITO_TESTS="RUN"
elif [ "$FAIL_ON_UNAVAILABLE" = true ]; then
    echo -e "${RED}Mock Cognito is required but not available${NC}"
    exit 1
fi

if [ "$SERVER_AVAILABLE" = true ]; then
    SERVER_TESTS="RUN"
elif [ "$FAIL_ON_UNAVAILABLE" = true ]; then
    echo -e "${RED}FRANK Server API is required but not available${NC}"
    exit 1
fi

if [ "$MANAGEMENT_AVAILABLE" = true ]; then
    MANAGEMENT_TESTS="RUN"
elif [ "$FAIL_ON_UNAVAILABLE" = true ]; then
    echo -e "${RED}Management API is required but not available${NC}"
    exit 1
fi

echo -e "Mock Cognito Tests:    ${COGNITO_TESTS}"
echo -e "FRANK API Tests:       ${SERVER_TESTS}"
echo -e "Management API Tests:  ${MANAGEMENT_TESTS}"
echo -e "${BLUE}============================================================${NC}"

# Run Mock Cognito tests
if [ "$COGNITO_TESTS" = "RUN" ]; then
    if ! run_suite "Mock Cognito Tests" "./tests/integration/run_cognito_tests.sh" "$COGNITO_PORT"; then
        echo -e "${RED}Mock Cognito tests failed${NC}"
    fi
else
    echo ""
    echo -e "${YELLOW}Skipping Mock Cognito tests (service not available)${NC}"
    SKIPPED_SUITES=$((SKIPPED_SUITES + 1))
fi

# Run FRANK Server API tests
if [ "$SERVER_TESTS" = "RUN" ]; then
    if ! run_suite "FRANK Server API Tests" "./tests/integration/run_frank_api_tests.sh" "$SERVER_PORT"; then
        echo -e "${RED}FRANK Server API tests failed${NC}"
    fi
else
    echo ""
    echo -e "${YELLOW}Skipping FRANK Server API tests (service not available)${NC}"
    SKIPPED_SUITES=$((SKIPPED_SUITES + 1))
fi

# Run Management API tests
if [ "$MANAGEMENT_TESTS" = "RUN" ]; then
    if ! run_suite "Management API Tests" "./tests/integration/run_management_api_tests.sh" "$MANAGEMENT_PORT"; then
        echo -e "${RED}Management API tests failed${NC}"
    fi
else
    echo ""
    echo -e "${YELLOW}Skipping Management API tests (service not available)${NC}"
    SKIPPED_SUITES=$((SKIPPED_SUITES + 1))
fi

# Final summary
echo ""
echo -e "${BLUE}============================================================${NC}"
echo -e "${BLUE}BDD Test Suite Summary${NC}"
echo -e "${BLUE}============================================================${NC}"
echo -e "Total Suites:   $TOTAL_SUITES"
echo -e "${GREEN}Passed:         $PASSED_SUITES${NC}"
echo -e "${RED}Failed:         $FAILED_SUITES${NC}"
echo -e "${YELLOW}Skipped:        $SKIPPED_SUITES${NC}"
echo -e "${BLUE}============================================================${NC}"

# Determine exit code
if [ $FAILED_SUITES -gt 0 ]; then
    echo -e "${RED}✗ Some test suites failed${NC}"
    exit 1
elif [ $TOTAL_SUITES -eq 0 ]; then
    echo -e "${YELLOW}⚠ No test suites were run (all services unavailable)${NC}"
    exit 1
else
    echo -e "${GREEN}✓ All executed test suites passed!${NC}"
    exit 0
fi
