#!/bin/bash
# FRANK Stage 3 Runner - Full Stack + FastAPI (Local Python)
# Run FRANK Stage 3 natively in Python virtualenv with all dependencies

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Ensure virtualenv exists
if [ ! -d "$PROJECT_ROOT/.venv" ]; then
    echo "❌ Virtual environment not found. Run 'make dev' first."
    exit 1
fi

# Load environment variables
if [ -f "$SCRIPT_DIR/.env" ]; then
    export $(grep -v '^#' "$SCRIPT_DIR/.env" | xargs)
else
    echo "⚠️  .env file not found. Copy .env.stage3.example to .env and customize."
    exit 1
fi

# Verify FRANK_STAGE
if [ "${FRANK_STAGE:-3}" != "3" ]; then
    echo "⚠️  FRANK_STAGE should be 3 for this script. Check your .env file."
fi

# Check prerequisites
echo "📋 Checking prerequisites..."
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker is not running. Start Docker Desktop first."
    exit 1
fi

# Check if PostgreSQL is running
if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
    echo "⚠️  PostgreSQL is not running on localhost:5432"
    echo "   Start PostgreSQL or use Docker: docker run -d -p 5432:5432 -e POSTGRES_USER=frank -e POSTGRES_PASSWORD=frank_dev -e POSTGRES_DB=frank_management postgres:15"
fi

# Check if LocalStack/DynamoDB is running
if ! curl -s http://localhost:4566/_localstack/health > /dev/null 2>&1; then
    echo "⚠️  LocalStack is not running on localhost:4566"
    echo "   Start LocalStack: docker run -d -p 4566:4566 localstack/localstack"
fi

# Check if Mock Cognito is running
if [ "${FRANK_AUTH_MODE:-mock}" = "mock" ]; then
    if ! curl -s http://localhost:8100/health > /dev/null 2>&1; then
        echo "⚠️  Mock Cognito is not running on localhost:8100"
        echo "   Start Mock Cognito: python tests/stubs/cognito/stub_cognito.py"
    fi
fi

echo "🚀 Starting FRANK Stage 3 (Full Stack + FastAPI)"
echo "   Environment: $FRANK_ENVIRONMENT"
echo "   Stage: $FRANK_STAGE"
echo "   Port: ${PORT:-8000}"
echo "   Database: ${DATABASE_URL:-postgresql://localhost:5432/frank_management}"
echo "   DynamoDB: ${DYNAMODB_ENDPOINT:-http://localhost:4566}"
echo "   Auth Mode: ${FRANK_AUTH_MODE:-mock}"
echo "   Cognito URL: ${COGNITO_URL:-http://localhost:8100}"
echo ""

# Activate virtualenv and run
cd "$PROJECT_ROOT"
source .venv/bin/activate
python stages/stage3/server.py
