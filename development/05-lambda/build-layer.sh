#!/bin/bash
# Build Lambda layer for FRANK dependencies

set -e

LAYER_DIR="layers/dependencies"
BUILD_DIR="$LAYER_DIR/python"

# Clean up previous build
rm -rf $BUILD_DIR
mkdir -p $BUILD_DIR

# Install dependencies
pip install -r requirements.txt -t $BUILD_DIR --no-deps

# Remove unnecessary files to reduce size
find $BUILD_DIR -type d -name "__pycache__" -exec rm -rf {} +
find $BUILD_DIR -name "*.pyc" -delete
find $BUILD_DIR -name "*.pyo" -delete
find $BUILD_DIR -name "*.dist-info" -exec rm -rf {} +

echo "Lambda layer built successfully in $LAYER_DIR"
