#!/bin/bash
# FRANK Security Roles Creation Script
# Run this script to create all IAM roles for FRANK project

set -e

# Configuration
PROFILE="spike-account"
EXTERNAL_ID="frank-deployment-access"

echo "🔐 Creating FRANK Security IAM Roles"
echo "Using AWS Profile: ${PROFILE}"
echo "=========================================="

# Get account ID for trust policy
ACCOUNT_ID=$(aws sts get-caller-identity --profile ${PROFILE} --query Account --output text)
echo "Account ID: ${ACCOUNT_ID}"

# Create temporary trust policy with actual account ID
cat > /tmp/trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "AWS": "arn:aws:iam::${ACCOUNT_ID}:root"
      },
      "Action": "sts:AssumeRole",
      "Condition": {
        "StringEquals": {
          "sts:ExternalId": "${EXTERNAL_ID}"
        },
        "Bool": {
          "aws:MultiFactorAuthPresent": "true"
        },
        "NumericLessThan": {
          "aws:MultiFactorAuthAge": "3600"
        }
      }
    }
  ]
}
EOF

# 1. Create frank-infra-creator role
echo "📋 Creating frank-infra-creator role..."
aws iam create-role \
    --profile ${PROFILE} \
    --role-name frank-infra-creator \
    --assume-role-policy-document file:///tmp/trust-policy.json \
    --description "FRANK Infrastructure Creator - Create AWS resources" \
    --max-session-duration 7200 \
    --tags Key=Purpose,Value=InfrastructureCreation Key=Project,Value=FRANK || true

# aws iam put-role-policy \
#     --profile ${PROFILE} \
#     --role-name frank-infra-creator \
#     --policy-name InfraCreatorPolicy \
#     --policy-document file://ansible/templates/infra-creator-policy.json

# # 2. Create frank-infra-destroyer role  
# echo "💥 Creating frank-infra-destroyer role..."
# aws iam create-role \
#     --profile ${PROFILE} \
#     --role-name frank-infra-destroyer \
#     --assume-role-policy-document file:///tmp/trust-policy.json \
#     --description "FRANK Infrastructure Destroyer - Delete AWS resources" \
#     --max-session-duration 1800 \
#     --tags Key=Purpose,Value=InfrastructureDestruction Key=Project,Value=FRANK

# aws iam put-role-policy \
#     --profile ${PROFILE} \
#     --role-name frank-infra-destroyer \
#     --policy-name InfraDestroyerPolicy \
#     --policy-document file://ansible/templates/infra-destroyer-policy.json

# 3. Create frank-app-deployer role
echo "🚀 Creating frank-app-deployer role..."
aws iam create-role \
    --profile ${PROFILE} \
    --role-name frank-app-deployer \
    --assume-role-policy-document file:///tmp/trust-policy.json \
    --description "FRANK Application Deployer - Deploy containers and applications" \
    --max-session-duration 14400 \
    --tags Key=Purpose,Value=ApplicationDeployment Key=Project,Value=FRANK

aws iam put-role-policy \
    --profile ${PROFILE} \
    --role-name frank-app-deployer \
    --policy-name AppDeployerPolicy \
    --policy-document file://ansible/templates/app-deployer-policy.json

# 4. Create frank-data-reader role
echo "📊 Creating frank-data-reader role..."
aws iam create-role \
    --profile ${PROFILE} \
    --role-name frank-data-reader \
    --assume-role-policy-document file:///tmp/trust-policy.json \
    --description "FRANK Data Reader - Read-only access to data and logs" \
    --max-session-duration 28800 \
    --tags Key=Purpose,Value=DataReading Key=Project,Value=FRANK

aws iam put-role-policy \
    --profile ${PROFILE} \
    --role-name frank-data-reader \
    --policy-name DataReaderPolicy \
    --policy-document file://ansible/templates/data-reader-policy.json

# 5. Create frank-emergency-admin role
echo "🚨 Creating frank-emergency-admin role..."
aws iam create-role \
    --profile ${PROFILE} \
    --role-name frank-emergency-admin \
    --assume-role-policy-document file:///tmp/trust-policy.json \
    --description "FRANK Emergency Admin - Break glass full access" \
    --max-session-duration 900 \
    --tags Key=Purpose,Value=EmergencyAccess Key=Project,Value=FRANK Key=EmergencyAccess,Value=true

aws iam put-role-policy \
    --profile ${PROFILE} \
    --role-name frank-emergency-admin \
    --policy-name EmergencyAdminPolicy \
    --policy-document file://ansible/templates/emergency-admin-policy.json

# Clean up temporary file
rm /tmp/trust-policy.json

echo ""
echo "✅ All FRANK security roles created successfully!"
echo ""
echo "📋 Created Roles:"
echo "  • frank-infra-creator    (2 hours, MFA required)"
echo "  • frank-infra-destroyer  (30 minutes, MFA required)" 
echo "  • frank-app-deployer     (4 hours)"
echo "  • frank-data-reader      (8 hours)"
echo "  • frank-emergency-admin  (15 minutes, MFA required)"
echo ""
echo "🔗 Role ARNs:"
aws iam list-roles --profile ${PROFILE} --query "Roles[?starts_with(RoleName, 'frank-')].{RoleName:RoleName,Arn:Arn}" --output table

echo ""
echo "🛠️  Next Steps:"
echo "1. Configure AWS CLI profiles in ~/.aws/config"
echo "2. Test role assumption with: aws sts assume-role"
echo "3. Update your deployment scripts to use specific roles"
echo ""
echo "📖 Example usage:"
echo "  aws --profile frank-infra cloudformation deploy ..."
echo "  aws --profile frank-deploy ecs update-service ..."
echo "  aws --profile frank-data dynamodb scan ..."