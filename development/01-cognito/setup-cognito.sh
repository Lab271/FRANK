#!/bin/bash

# FRANK Cognito Setup Script
# This script creates the Cognito User Pool and associated resources

set -e

# Configuration
ENV=${1:-dev}
REGION=${2:-eu-west-1}
STACK_NAME="frank-cognito-${ENV}"

echo "Creating Cognito resources for environment: ${ENV} in region: ${REGION}"

# Deploy CloudFormation stack
aws cloudformation deploy \
  --template-file cognito-template.yaml \
  --stack-name ${STACK_NAME} \
  --parameter-overrides \
    Environment=${ENV} \
    ProjectName=frank \
  --capabilities CAPABILITY_IAM \
  --region ${REGION} \
  --tags \
    Project=frank \
    Environment=${ENV} \
    Component=cognito

# Get outputs
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name ${STACK_NAME} \
  --region ${REGION} \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
  --output text)

CLIENT_ID=$(aws cloudformation describe-stacks \
  --stack-name ${STACK_NAME} \
  --region ${REGION} \
  --query 'Stacks[0].Outputs[?OutputKey==`ClientId`].OutputValue' \
  --output text)

echo "Cognito User Pool created successfully!"
echo "User Pool ID: ${USER_POOL_ID}"
echo "Client ID: ${CLIENT_ID}"

# Create default admin user
echo "Creating default admin user..."
aws cognito-idp admin-create-user \
  --user-pool-id ${USER_POOL_ID} \
  --username admin@frank.local \
  --user-attributes \
    Name=email,Value=admin@frank.local \
    Name=custom:tenant_id,Value=system \
    Name=custom:sector,Value=government \
  --temporary-password TempPass123! \
  --message-action SUPPRESS \
  --region ${REGION}

# Add admin to admin group
aws cognito-idp admin-add-user-to-group \
  --user-pool-id ${USER_POOL_ID} \
  --username admin@frank.local \
  --group-name Admins \
  --region ${REGION}

echo "Default admin user created: admin@frank.local"
echo "Temporary password: TempPass123!"

# Output environment variables
echo ""
echo "Environment variables for your application:"
echo "export COGNITO_USER_POOL_ID=${USER_POOL_ID}"
echo "export COGNITO_CLIENT_ID=${CLIENT_ID}"
echo "export COGNITO_REGION=${REGION}"
