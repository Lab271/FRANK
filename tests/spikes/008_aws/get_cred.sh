#!/bin/bash
# Script to extract AWS credentials from 1Password and set as environment variables
# Item: "Our Family/Private/AWS - frank - sbp_lab_frank"
# Run this with "source get_cred.sh"

set -e  # Exit on any error

# Check if 1Password CLI is installed
if ! command -v op &> /dev/null; then
    echo "Error: 1Password CLI (op) is not installed or not in PATH"
    echo "Please install it from: https://developer.1password.com/docs/cli/get-started/"
    exit 1
fi

# Check if user is signed in to 1Password
if ! op account list &> /dev/null; then
    echo "Error: Not signed in to 1Password CLI"
    echo "Please run: op signin"
    exit 1
fi

ITEM_PATH="AWS - frank - sbp_labs_frank"
ITEM_PATH="AWS Credentials - FRANK"

echo "Extracting AWS credentials from 1Password..."

# Get the item and extract the fields
# Using op item get with --format json and then parsing with jq
ITEM_JSON=$(op item get "$ITEM_PATH" --format json --account "my.1password.eu" )
ITEM_JSON=$(op item get "$ITEM_PATH" --format json )

if [ $? -ne 0 ]; then
    echo "Error: Could not retrieve item '$ITEM_PATH'"
    echo "Please check that the item exists and you have access to it"
    exit 1
fi

# Extract access key and secret key
# Assuming the fields are named 'access_key' and 'secret_access_key'
AWS_ACCESS_KEY_ID=$(echo "$ITEM_JSON" | jq -r '.fields[] | select(.label=="access_key" or .id=="access_key") | .value')
AWS_SECRET_ACCESS_KEY=$(echo "$ITEM_JSON" | jq -r '.fields[] | select(.label=="secret_access_key" or .id=="secret_access_key") | .value')

# Check if we got the values
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ "$AWS_ACCESS_KEY_ID" = "null" ]; then
    echo "Error: Could not find 'access_key' field in the 1Password item"
    echo "Available fields:"
    echo "$ITEM_JSON" | jq -r '.fields[] | .label // .id'
    exit 1
fi

if [ -z "$AWS_SECRET_ACCESS_KEY" ] || [ "$AWS_SECRET_ACCESS_KEY" = "null" ]; then
    echo "Error: Could not find 'secret_access_key' field in the 1Password item"
    echo "Available fields:"
    echo "$ITEM_JSON" | jq -r '.fields[] | .label // .id'
    exit 1
fi

# Export the environment variables
export AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY

echo "✓ AWS credentials successfully exported to environment variables"
echo "  AWS_ACCESS_KEY_ID: ${AWS_ACCESS_KEY_ID:0:4}****"
echo "  AWS_SECRET_ACCESS_KEY: ****"

# Optional: Show current AWS identity (if AWS CLI is installed)
if command -v aws &> /dev/null; then
    echo ""
    echo "Testing AWS credentials..."
    aws sts get-caller-identity 2>/dev/null || echo "Note: Could not verify AWS credentials (AWS CLI may not be configured)"
fi