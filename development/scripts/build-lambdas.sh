#!/bin/bash
set -e

echo "🔨 Building Lambda packages with FRANK library..."

# Get project root
PROJECT_ROOT="/Users/bjenniskens/Developer/FRANK"
DEV_ROOT="${PROJECT_ROOT}/development"
LAMBDAS_ROOT="${DEV_ROOT}/lambdas"
BUILD_DIR="${DEV_ROOT}/build"

# Clean and create build directory
rm -rf "${BUILD_DIR}"
mkdir -p "${BUILD_DIR}"

# Function to build a lambda package
build_lambda() {
    local lambda_name=$1
    local lambda_dir="${LAMBDAS_ROOT}/${lambda_name}"
    local build_lambda_dir="${BUILD_DIR}/${lambda_name}"
    
    echo "  Building ${lambda_name}..."
    
    # Create build directory for this lambda
    mkdir -p "${build_lambda_dir}"
    
    # Copy lambda source
    cp "${lambda_dir}/handler.py" "${build_lambda_dir}/"
    
    # Copy FRANK library
    mkdir -p "${build_lambda_dir}/frank"
    cp -r "${PROJECT_ROOT}/src/frank"/* "${build_lambda_dir}/frank/"
    
    # Install requirements if they exist
    if [[ -f "${lambda_dir}/requirements.txt" ]]; then
        pip install -r "${lambda_dir}/requirements.txt" -t "${build_lambda_dir}/" --quiet
    fi
    
    # Create zip package
    cd "${build_lambda_dir}"
    zip -r "/tmp/frank-${lambda_name}.zip" . > /dev/null
    
    echo "    ✅ Created /tmp/frank-${lambda_name}.zip"
}

# Build both lambda packages
build_lambda "ingest"
build_lambda "query"

echo "✅ Lambda packages built successfully!"
