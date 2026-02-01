#!/bin/bash
# FRANK Stage 1 Runner - SQLite + FastAPI (Local Python)
# Run FRANK Stage 1 natively in Python virtualenv

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
    echo "⚠️  .env file not found. Copy .env.stage1.example to .env and customize."
    exit 1
fi

# Verify FRANK_STAGE
if [ "${FRANK_STAGE:-1}" != "1" ]; then
    echo "⚠️  FRANK_STAGE should be 1 for this script. Check your .env file."
fi

echo "🚀 Starting FRANK Stage 1 (SQLite + FastAPI)"
echo "   Environment: $FRANK_ENVIRONMENT"
echo "   Stage: $FRANK_STAGE"
echo "   Port: ${PORT:-8000}"
echo "   Database: ${DATABASE_URL:-sqlite:///./frank.db}"
echo ""

# Activate virtualenv and run
cd "$PROJECT_ROOT"
source .venv/bin/activate
python stages/stage1/server.py
