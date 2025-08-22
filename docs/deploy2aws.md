# FRANK Deployment Guide

This guide provides step-by-step instructions for deploying the FRANK cybersecurity threat intelligence platform to AWS using the provided automation scripts.

## Prerequisites

### 1. Required Tools

Before starting the deployment, ensure you have the following tools installed:

```bash
# AWS CLI v2
aws --version
# Should show: aws-cli/2.x.x or later

# SAM CLI
sam --version
# Should show: SAM CLI, version 1.x.x or later

# Python 3.11
python3.11 --version
# Should show: Python 3.11.x

# Docker (for building Lambda layers)
docker --version
# Should show: Docker version 20.x.x or later

# jq (for JSON processing)
jq --version
# Should show: jq-1.x or later
```

### 2. Install Missing Tools

**AWS CLI v2:**
```bash
# macOS
brew install awscli

# Or download from: https://aws.amazon.com/cli/
```

**SAM CLI:**
```bash
# macOS
brew install aws-sam-cli

# Or follow: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
```

**jq:**
```bash
# macOS
brew install jq
```

## AWS Account Setup

### 1. AWS Account Requirements

- **AWS Account**: Active AWS account with billing enabled
- **Region**: Choose a region that supports all required services (recommended: `eu-west-1`, `us-east-1`, `us-west-2`)
- **Permissions**: Administrator access or specific IAM permissions (see below)

### 2. AWS Organizations Setup (Recommended)

For better isolation and security, create a dedicated AWS account for FRANK:

**Option A: Create New Member Account (Recommended)**
```bash
# Check organization status using your master account
export AWS_PROFILE=bjenniskens@sbp-labs
aws organizations describe-organization

# Create dedicated account for FRANK
aws organizations create-account \
    --email frank-security@yourcompany.com \
    --account-name "FRANK-CyberThreat-Platform" \
    --role-name OrganizationAccountAccessRole

# Get the new account ID
aws organizations list-accounts --query 'Accounts[?Name==`FRANK-CyberThreat-Platform`].Id' --output text
```

**Option B: Use Existing Account with Master Profile**
```bash
# Use your master account for FRANK project
export AWS_PROFILE=bjenniskens@sbp-labs

# Verify your account access
aws sts get-caller-identity
```

**Benefits of Dedicated Account:**
- Complete resource isolation
- Separate billing and cost tracking  
- Enhanced security boundaries
- Independent service quotas
- Easier compliance auditing

### 3. Required AWS Permissions

Your AWS user/role must have the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "iam:*",
        "s3:*",
        "dynamodb:*",
        "lambda:*",
        "apigateway:*",
        "cognito-idp:*",
        "cognito-identity:*",
        "kms:*",
        "logs:*",
        "events:*",
        "sqs:*",
        "states:*",
        "ecs:*",
        "ecr:*",
        "opensearch:*",
        "es:*",
        "xray:*",
        "secretsmanager:*",
        "ssm:*",
        "organizations:*"
      ],
      "Resource": "*"
    }
  ]
}
```

**For Production**: Create a more restrictive policy based on specific resource ARNs.

**For Organizations Management**: Add these additional permissions if managing AWS Organizations:
```json
{
  "Version": "2012-10-17", 
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "organizations:CreateAccount",
        "organizations:DescribeOrganization", 
        "organizations:ListAccounts",
        "organizations:CreateOrganizationalUnit",
        "organizations:MoveAccount"
      ],
      "Resource": "*"
    }
  ]
}
```

### 4. Create Dedicated IAM User (Recommended)

**Step 1: Create FRANK IAM User**
```bash
## Step 2: Create IAM User for Deployment ✅

To ensure secure deployment, we'll create a dedicated IAM user with limited permissions:

```bash
# Create the IAM user
aws iam create-user --user-name frank-deployment-user --profile bjenniskens@sbp-labs

# Create access keys (save these securely!)
aws iam create-access-key --user-name frank-deployment-user --profile bjenniskens@sbp-labs
```

**✅ Completed**: 
- IAM user `frank-deployment-user` created
- Access keys generated and configured
- User ID: `AIDAVC7S2ZPVIYEVV2OPP`

## Step 3: Create and Attach IAM Policy ✅

Create the deployment policy:

```bash
# Create the policy
aws iam create-policy --policy-name FRANKDeploymentPolicy --policy-document file://frank-deployment-policy.json --profile bjenniskens@sbp-labs

# Attach policy to user
aws iam attach-user-policy --user-name frank-deployment-user --policy-arn "arn:aws:iam::350012230634:policy/FRANKDeploymentPolicy" --profile bjenniskens@sbp-labs
```

**✅ Completed**:
- Policy `FRANKDeploymentPolicy` created
- Policy attached to frank-deployment-user
- Policy ARN: `arn:aws:iam::350012230634:policy/FRANKDeploymentPolicy`

## Step 4: Configure AWS CLI Profile ✅

Configure the new profile for deployment:

```bash
aws configure set aws_access_key_id AKIAVC7S2ZPVMO36FK5H --profile frank-deployment
aws configure set aws_secret_access_key "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" --profile frank-deployment
aws configure set region eu-central-1 --profile frank-deployment
aws configure set output json --profile frank-deployment
```

Test the profile:
```bash
aws sts get-caller-identity --profile frank-deployment
```

**✅ Completed**: AWS CLI profile `frank-deployment` configured and tested
```

**Step 2: Create IAM Policy for FRANK**
```bash
# Create policy file (frank-deployment-policy.json)
cat > frank-deployment-policy.json << 'EOF'
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "cloudformation:*",
        "iam:*",
        "s3:*",
        "dynamodb:*",
        "lambda:*",
        "apigateway:*",
        "cognito-idp:*",
        "cognito-identity:*",
        "kms:*",
        "logs:*",
        "events:*",
        "sqs:*",
        "states:*",
        "ecs:*",
        "ecr:*",
        "opensearch:*",
        "es:*",
        "xray:*",
        "secretsmanager:*",
        "ssm:*",
        "organizations:DescribeOrganization",
        "organizations:ListAccounts",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}
EOF

# Create the policy
aws iam create-policy \
    --policy-name FRANKDeploymentPolicy \
    --policy-document file://frank-deployment-policy.json

# Attach policy to user
aws iam attach-user-policy \
    --user-name frank-deployment-user \
    --policy-arn "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):policy/FRANKDeploymentPolicy"
```

**Step 3: Configure AWS CLI with FRANK User**
```bash
# Configure AWS CLI with the new FRANK user
aws configure --profile frank-project

# When prompted, enter:
# AWS Access Key ID: [AccessKeyId from step 1]
# AWS Secret Access Key: [SecretAccessKey from step 1]  
# Default region name: eu-central-1  # or your preferred region
# Default output format: json

# Set profile for FRANK deployment
export AWS_PROFILE=frank-project

# Verify configuration
aws sts get-caller-identity --profile frank-project
```

**Alternative: Use Existing Account (Less Secure)**
```bash
# If you prefer to use your existing user
aws configure --profile frank-project
# Use your existing credentials
```

**Alternative: Using AWS SSO or IAM Roles**
```bash
# For AWS SSO
aws configure sso --profile frank-sso

# For EC2 instance roles or other assumed roles
# Ensure proper role assumption is configured
```

### 5. Security Considerations

**Best Practices for IAM User:**
- ✅ **Use dedicated IAM user** for FRANK project
- ✅ **Rotate access keys** regularly (every 90 days)
- ✅ **Enable MFA** on the IAM user account
- ✅ **Limit permissions** to only what FRANK needs
- ✅ **Monitor usage** through CloudTrail logs

**Enable MFA for FRANK User:**
```bash
# Create virtual MFA device
aws iam create-virtual-mfa-device \
    --virtual-mfa-device-name frank-deployment-user-mfa \
    --outfile QRCode.png \
    --bootstrap-method QRCodePNG

# Enable MFA (after scanning QR code)
aws iam enable-mfa-device \
    --user-name frank-deployment-user \
    --serial-number "arn:aws:iam::$(aws sts get-caller-identity --query Account --output text):mfa/frank-deployment-user-mfa" \
    --authentication-code-1 123456 \
    --authentication-code-2 654321
```

**For Production: Additional Security Measures**
```bash
# Create more restrictive policy
# Limit to specific resource ARNs
# Use AWS IAM Access Analyzer
# Enable AWS CloudTrail for auditing
```

## Environment Configuration

### 1. Set Environment Variables

Create a configuration file or set environment variables:

```bash
# Required environment variables
export AWS_REGION="eu-west-1"           # Your AWS region
export PROJECT_NAME="frank"             # Project name (used in resource naming)
export ENVIRONMENT="dev"                # Environment: dev, test, or prod

# Optional but recommended
export AWS_PROFILE="bjenniskens@sbp-labs"  # Your master AWS profile
export AWS_DEFAULT_OUTPUT="json"           # AWS CLI output format
```

**For persistent configuration, add to your shell profile:**
```bash
# Add to ~/.zshrc or ~/.bashrc
echo 'export AWS_REGION="eu-west-1"' >> ~/.zshrc
echo 'export PROJECT_NAME="frank"' >> ~/.zshrc
echo 'export ENVIRONMENT="dev"' >> ~/.zshrc
source ~/.zshrc
```

### 2. Environment-Specific Configuration

#### Development Environment
```bash
export ENVIRONMENT="dev"
# Features: Debug logging, minimal scaling, cost-optimized
# Resources: On-demand DynamoDB, small Lambda memory, basic monitoring
```

#### Test Environment
```bash
export ENVIRONMENT="test"
# Features: Production-like settings with test data
# Resources: Auto-scaling enabled, enhanced monitoring
```

#### Production Environment
```bash
export ENVIRONMENT="prod"
# Features: Full security, monitoring, high availability
# Resources: Provisioned capacity, multi-AZ, comprehensive backups
```

## Pre-Deployment Validation

### 1. Validate Configuration

Before deploying, run the validation script to check your setup:

```bash
# Navigate to the project directory
cd /path/to/FRANK/development

# Run validation script
./scripts/validate-config.sh

# Expected output:
# [INFO] Starting FRANK configuration validation
# [SUCCESS] All required tools are available
# [SUCCESS] AWS credentials valid
# [SUCCESS] Region eu-west-1 is accessible
# [SUCCESS] Template KMS is valid
# [SUCCESS] Template Cognito is valid
# [SUCCESS] Template S3 is valid
# [SUCCESS] Template DynamoDB is valid
# [SUCCESS] ✅ All validations passed
```

### 2. Fix Validation Issues

If validation fails, address the issues:

**Missing Tools:**
```bash
# Install missing tools using the commands in Prerequisites section
```

**AWS Credential Issues:**
```bash
# Reconfigure AWS credentials
aws configure

# Or check if your credentials expired
aws sts get-caller-identity
```

**Template Issues:**
```bash
# Check CloudFormation template syntax
aws cloudformation validate-template --template-body file://path/to/template.yaml
```

## Deployment Process

### 1. Full Deployment (Recommended for First Time)

Deploy all components automatically:

```bash
# Navigate to development directory
cd development/

# Run full deployment
./scripts/deploy-all.sh

# The script will deploy in this order:
# 1. KMS Keys
# 2. Cognito User Pool
# 3. S3 Buckets
# 4. DynamoDB Tables
# 5. Lambda Functions
# 6. API Gateway
```

**Expected Output:**
```
[INFO] Starting FRANK infrastructure deployment
[INFO] Project: frank
[INFO] Environment: dev
[INFO] Region: eu-west-1
[INFO] Checking prerequisites...
[SUCCESS] Prerequisites check passed
[INFO] === Deploying KMS Keys ===
[INFO] Deploying stack: frank-kms-dev
[SUCCESS] Stack frank-kms-dev deployed successfully
[INFO] === Deploying Cognito ===
...
[SUCCESS] FRANK infrastructure deployment completed successfully!

=== Deployment Summary ===
Cognito User Pool ID: eu-west-1_XXXXXXXXX
S3 Raw Bucket: frank-raw-123456789012-dev
DynamoDB Aggregates Table: frank-aggregates-dev
```

### 2. Component-by-Component Deployment

For more control, deploy individual components:

```bash
# Deploy only KMS keys
./scripts/deploy-all.sh kms

# Deploy only Cognito
./scripts/deploy-all.sh cognito

# Deploy only S3 buckets
./scripts/deploy-all.sh s3

# Deploy only DynamoDB tables
./scripts/deploy-all.sh dynamodb

# Deploy only Lambda functions
./scripts/deploy-all.sh lambda

# Deploy only API Gateway
./scripts/deploy-all.sh api
```

### 3. Manual Deployment Steps

If you prefer manual deployment or need to customize:

#### Step 1: Deploy KMS Keys
```bash
cd 02-kms/
aws cloudformation deploy \
  --template-file kms-template.yaml \
  --stack-name frank-kms-dev \
  --parameter-overrides Environment=dev ProjectName=frank \
  --capabilities CAPABILITY_IAM \
  --region eu-west-1
```

#### Step 2: Deploy Cognito
```bash
cd ../01-cognito/
aws cloudformation deploy \
  --template-file cognito-template.yaml \
  --stack-name frank-cognito-dev \
  --parameter-overrides Environment=dev ProjectName=frank \
  --capabilities CAPABILITY_IAM \
  --region eu-west-1
```

#### Step 3: Deploy S3 Buckets
```bash
cd ../03-s3/

# Get S3 KMS key ARN from previous deployment
S3_KEY_ARN=$(aws cloudformation describe-stacks \
  --stack-name frank-kms-dev \
  --region eu-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`S3KeyArn`].OutputValue' \
  --output text)

aws cloudformation deploy \
  --template-file s3-template.yaml \
  --stack-name frank-s3-dev \
  --parameter-overrides \
    Environment=dev \
    ProjectName=frank \
    S3KeyArn=$S3_KEY_ARN \
  --region eu-west-1
```

#### Step 4: Deploy DynamoDB Tables
```bash
cd ../04-dynamodb/

# Get DynamoDB KMS key ARN
DDB_KEY_ARN=$(aws cloudformation describe-stacks \
  --stack-name frank-kms-dev \
  --region eu-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`DynamoDBKeyArn`].OutputValue' \
  --output text)

aws cloudformation deploy \
  --template-file dynamodb-template.yaml \
  --stack-name frank-dynamodb-dev \
  --parameter-overrides \
    Environment=dev \
    ProjectName=frank \
    DynamoDBKeyArn=$DDB_KEY_ARN \
  --region eu-west-1
```

#### Step 5: Deploy Lambda Functions
```bash
cd ../05-lambda/

# Generate SAM template
python3 generate-lambda-config.py dev

# Build and deploy with SAM
sam build --template-file lambda-template-dev.yaml
sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name frank-lambda-dev \
  --capabilities CAPABILITY_IAM \
  --region eu-west-1 \
  --parameter-overrides Environment=dev ProjectName=frank
```

## Post-Deployment Configuration

### 1. Verify Deployment

Check that all resources were created successfully:

```bash
# List all FRANK CloudFormation stacks
aws cloudformation list-stacks \
  --region eu-west-1 \
  --query 'StackSummaries[?contains(StackName, `frank`) && StackStatus==`CREATE_COMPLETE`].[StackName,StackStatus]' \
  --output table

# Check specific resources
aws cognito-idp list-user-pools --max-results 10 --region eu-west-1
aws s3 ls | grep frank
aws dynamodb list-tables --region eu-west-1 | grep frank
aws lambda list-functions --region eu-west-1 --query 'Functions[?contains(FunctionName, `frank`)].FunctionName'
```

### 2. Configure Cognito Users

Create test users and configure access:

```bash
# Get User Pool ID
USER_POOL_ID=$(aws cloudformation describe-stacks \
  --stack-name frank-cognito-dev \
  --region eu-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
  --output text)

# Create a test user
aws cognito-idp admin-create-user \
  --user-pool-id $USER_POOL_ID \
  --username testuser@example.com \
  --user-attributes \
    Name=email,Value=testuser@example.com \
    Name=custom:submitter_id,Value=test-org \
    Name=custom:sector,Value=finance \
  --temporary-password TempPass123! \
  --message-action SUPPRESS \
  --region eu-west-1

# Add user to Publishers group
aws cognito-idp admin-add-user-to-group \
  --user-pool-id $USER_POOL_ID \
  --username testuser@example.com \
  --group-name Publishers \
  --region eu-west-1
```

### 3. Test API Endpoints

Once deployed, test the API:

```bash
# Get API Gateway URL (from Lambda stack outputs or console)
API_URL=$(aws cloudformation describe-stacks \
  --stack-name frank-lambda-dev \
  --region eu-west-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayUrl`].OutputValue' \
  --output text)

# Test health endpoint (if implemented)
curl -X GET "$API_URL/v1/health"

# Test with authentication (requires JWT token)
# First, authenticate and get token using Cognito
```

## Environment Variables Reference

### Required Variables

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `AWS_REGION` | AWS region for deployment | `eu-west-1` | Yes |
| `PROJECT_NAME` | Project name for resource naming | `frank` | Yes |
| `ENVIRONMENT` | Environment name | `dev`, `test`, `prod` | Yes |

### Optional Variables

| Variable | Description | Default | 
|----------|-------------|---------|
| `AWS_PROFILE` | AWS CLI profile to use | `default` |
| `AWS_DEFAULT_OUTPUT` | AWS CLI output format | `json` |

### AWS Service Limits to Consider

Before deployment, check these AWS service limits:

```bash
# CloudFormation stacks (default: 200 per region)
aws cloudformation describe-account-attributes --region eu-west-1

# Lambda functions (default: 1000 per region)
aws lambda get-account-settings --region eu-west-1

# DynamoDB tables (default: 256 per region)
aws dynamodb describe-limits --region eu-west-1
```

## Troubleshooting

### Common Deployment Issues

#### 1. CloudFormation Stack Creation Failed

**Check the stack events:**
```bash
aws cloudformation describe-stack-events \
  --stack-name frank-kms-dev \
  --region eu-west-1 \
  --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`]'
```

**Common causes and solutions:**
- **Insufficient permissions**: Ensure your AWS user has required permissions
- **Resource already exists**: Delete existing resources or use different names
- **Region not supported**: Check if all services are available in your region

#### 2. Lambda Deployment Failed

**Check SAM build logs:**
```bash
sam logs --stack-name frank-lambda-dev --region eu-west-1
```

**Common causes:**
- **Python version mismatch**: Ensure Python 3.11 is available
- **Dependencies not found**: Check requirements.txt and build process
- **Memory/timeout issues**: Increase Lambda memory allocation

#### 3. API Gateway Authentication Issues

**Verify Cognito configuration:**
```bash
# Check User Pool settings
aws cognito-idp describe-user-pool \
  --user-pool-id $USER_POOL_ID \
  --region eu-west-1

# Check authorizer configuration in API Gateway
aws apigateway get-authorizers \
  --rest-api-id $API_ID \
  --region eu-west-1
```

#### 4. Permission Denied Errors

**Check IAM roles and policies:**
```bash
# List attached policies for Lambda execution role
aws iam list-attached-role-policies \
  --role-name frank-lambda-execution-role-dev
```

### Getting Help

#### 1. View CloudFormation Events
```bash
# See what went wrong during deployment
aws cloudformation describe-stack-events \
  --stack-name frank-kms-dev \
  --region eu-west-1
```

#### 2. Check CloudWatch Logs
```bash
# View Lambda function logs
aws logs describe-log-groups \
  --log-group-name-prefix "/aws/lambda/frank" \
  --region eu-west-1
```

#### 3. AWS Support Resources
- **AWS Documentation**: https://docs.aws.amazon.com/
- **AWS Support**: Create support case in AWS Console
- **AWS Forums**: https://forums.aws.amazon.com/

## Cleanup

### Complete Environment Cleanup

To remove all resources and avoid charges:

```bash
# Run the cleanup script
./scripts/teardown.sh

# For production, extra confirmation required
ENVIRONMENT=prod ./scripts/teardown.sh
```

### Manual Cleanup

If the script fails, manually delete resources:

```bash
# Delete CloudFormation stacks in reverse order
aws cloudformation delete-stack --stack-name frank-lambda-dev --region eu-west-1
aws cloudformation delete-stack --stack-name frank-dynamodb-dev --region eu-west-1
aws cloudformation delete-stack --stack-name frank-s3-dev --region eu-west-1
aws cloudformation delete-stack --stack-name frank-cognito-dev --region eu-west-1
aws cloudformation delete-stack --stack-name frank-kms-dev --region eu-west-1
```

**Note**: S3 buckets must be emptied before stack deletion.

## Security Best Practices

### 1. Production Deployment Checklist

Before deploying to production:

- [ ] Review all IAM policies for least privilege
- [ ] Enable CloudTrail logging
- [ ] Configure proper backup schedules
- [ ] Set up monitoring and alerting
- [ ] Enable MFA for administrative users
- [ ] Review security group rules
- [ ] Enable GuardDuty and Security Hub
- [ ] Configure AWS Config rules

### 2. Ongoing Security

- **Regular Updates**: Keep all dependencies and templates updated
- **Access Reviews**: Regularly review user access and permissions
- **Monitoring**: Set up automated security monitoring
- **Backup Testing**: Regularly test backup and recovery procedures

---

**Next Steps**: After successful deployment, refer to the individual component configuration files in the `development/` folder for advanced configuration options and operational procedures.
