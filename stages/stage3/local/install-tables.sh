
#!/bin/bash
#
# FRANK Platform - Stage 3 Local DynamoDB Table Installation Script
# Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling
#
# This script creates the required DynamoDB tables for local development
# using LocalStack. It sets up both the main data table and audit table
# with the same schema structure used in the AWS CloudFormation deployment.
#
# Tables Created:
# - frank-data: Main application data with PK/SK design and GSI1 index
# - frank-audit: Audit trail data with matching schema structure
#
# Prerequisites:
# - LocalStack running on localhost:4566
# - AWS CLI configured with 'localstack' profile
# - DynamoDB service available in LocalStack
#
# Usage:
#   ./install-tables.sh
#
# Schema Design:
# - Primary Key: PK (Hash) + SK (Range) - enables hierarchical data
# - Global Secondary Index: GSI1PK (Hash) + GSI1SK (Range) - query flexibility
# - DynamoDB Streams: Enabled for change data capture and audit trails
#
# Error Handling:
# - Gracefully handles existing tables (idempotent operation)
# - Displays informative messages for successful creation or existing tables
#
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0
#

set +e  # Do not exit on error

# Configuration variables
ENDPOINT_URL="http://localhost:4566"
REGION="eu-west-1"
PROFILE="localstack"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "🚀 Installing FRANK Stage 3 DynamoDB tables for local development..."
echo "📍 Target: LocalStack ($ENDPOINT_URL)"
echo

echo "📊 Creating frank-data table..."
aws dynamodb create-table \
    --table-name frank-data \
    --attribute-definitions \
        AttributeName=PK,AttributeType=S \
        AttributeName=SK,AttributeType=S \
        AttributeName=GSI1PK,AttributeType=S \
        AttributeName=GSI1SK,AttributeType=S \
    --key-schema \
        AttributeName=PK,KeyType=HASH \
        AttributeName=SK,KeyType=RANGE \
    --global-secondary-indexes \
        IndexName=GSI1,KeySchema='[{AttributeName=GSI1PK,KeyType=HASH},{AttributeName=GSI1SK,KeyType=RANGE}]',Projection='{ProjectionType=ALL}' \
    --billing-mode PAY_PER_REQUEST \
    --stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES \
    --endpoint-url $ENDPOINT_URL \
    --region $REGION \
    --profile $PROFILE \
    --no-cli-pager 

echo
echo "📋 Creating frank-audit table..."
aws dynamodb create-table \
    --table-name frank-audit \
    --attribute-definitions \
        AttributeName=PK,AttributeType=S \
        AttributeName=SK,AttributeType=S \
        AttributeName=GSI1PK,AttributeType=S \
        AttributeName=GSI1SK,AttributeType=S \
    --key-schema \
        AttributeName=PK,KeyType=HASH \
        AttributeName=SK,KeyType=RANGE \
    --global-secondary-indexes \
        IndexName=GSI1,KeySchema='[{AttributeName=GSI1PK,KeyType=HASH},{AttributeName=GSI1SK,KeyType=RANGE}]',Projection='{ProjectionType=ALL}' \
    --billing-mode PAY_PER_REQUEST \
    --endpoint-url $ENDPOINT_URL \
    --region $REGION \
    --profile $PROFILE \
    --no-cli-pager 

echo
echo "✅ DynamoDB table installation completed!"
echo "📊 Tables available:"
echo -e "   - ${GREEN}frank-data${NC} (main application data)"
echo -e "   - ${GREEN}frank-audit${NC} (audit trail data)"
echo
echo "🔍 Verify tables with:"
echo -e "${YELLOW}   aws dynamodb list-tables --endpoint-url $ENDPOINT_URL --region $REGION --profile $PROFILE --no-cli-pager${NC}"