#!/bin/bash
#
# FRANK Platform - Docker Entrypoint Script
#
# Initializes database with fixture data on container startup
#
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0

set -e

echo "=== FRANK Docker Container Startup ==="

# Check if we should load fixtures (default: yes in development)
LOAD_FIXTURES=${LOAD_FIXTURES:-true}

if [ "$LOAD_FIXTURES" = "true" ]; then
    echo "Loading comprehensive fixture data..."

    # Initialize database with fixtures if init script exists
    if [ -f "/app/init_fixtures.py" ]; then
        python /app/init_fixtures.py
        echo "✅ Fixtures loaded successfully"
    else
        echo "⚠️  init_fixtures.py not found, skipping fixture loading"
    fi
else
    echo "Skipping fixture loading (LOAD_FIXTURES=$LOAD_FIXTURES)"
fi

# Execute the main command
echo "Starting application..."
exec "$@"
