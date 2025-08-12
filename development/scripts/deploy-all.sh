#!/bin/bash

# FRANK Infrastructure Deployment Script
# Deploys all AWS components in the correct order

set -e

# Configuration
PROJECT_NAME=${PROJECT_NAME:-frank}
AWS_REGION=${AWS_REGION:-eu-west-1}
ENVIRONMENT=${ENVIRONMENT:-dev}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI not found. Please install AWS CLI v2."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Run 'aws configure'."
        exit 1
    fi
    
    # Check SAM CLI
    if ! command -v sam &> /dev/null; then
        log_error "SAM CLI not found. Please install SAM CLI."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Deploy CloudFormation stack
deploy_stack() {
    local stack_name=$1
    local template_file=$2
    local parameters=$3
    local capabilities=$4
    
    log_info "Deploying stack: $stack_name"
    
    aws cloudformation deploy \
        --template-file "$template_file" \
        --stack-name "$stack_name" \
        --parameter-overrides $parameters \
        --capabilities ${capabilities:-CAPABILITY_IAM} \
        --region "$AWS_REGION" \
        --tags \
            Project="$PROJECT_NAME" \
            Environment="$ENVIRONMENT" \
            DeployedBy="$(aws sts get-caller-identity --query 'Arn' --output text)" \
            DeployedAt="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    
    if [ $? -eq 0 ]; then
        log_success "Stack $stack_name deployed successfully"
    else
        log_error "Failed to deploy stack $stack_name"
        exit 1
    fi
}

# Get stack output
get_stack_output() {
    local stack_name=$1
    local output_key=$2
    
    aws cloudformation describe-stacks \
        --stack-name "$stack_name" \
        --region "$AWS_REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='$output_key'].OutputValue" \
        --output text
}

# Deploy KMS
deploy_kms() {
    log_info "=== Deploying KMS Keys ==="
    
    cd "$(dirname "$0")/../02-kms"
    
    deploy_stack \
        "${PROJECT_NAME}-kms-${ENVIRONMENT}" \
        "kms-template.yaml" \
        "Environment=${ENVIRONMENT} ProjectName=${PROJECT_NAME}"
    
    cd - > /dev/null
}

# Deploy Cognito
deploy_cognito() {
    log_info "=== Deploying Cognito ==="
    
    cd "$(dirname "$0")/../01-cognito"
    
    deploy_stack \
        "${PROJECT_NAME}-cognito-${ENVIRONMENT}" \
        "cognito-template.yaml" \
        "Environment=${ENVIRONMENT} ProjectName=${PROJECT_NAME}"
    
    cd - > /dev/null
}

# Deploy S3
deploy_s3() {
    log_info "=== Deploying S3 Buckets ==="
    
    # Get S3 KMS key ARN
    local s3_key_arn=$(get_stack_output "${PROJECT_NAME}-kms-${ENVIRONMENT}" "S3KeyArn")
    
    if [ -z "$s3_key_arn" ]; then
        log_error "Could not retrieve S3 KMS key ARN"
        exit 1
    fi
    
    cd "$(dirname "$0")/../03-s3"
    
    deploy_stack \
        "${PROJECT_NAME}-s3-${ENVIRONMENT}" \
        "s3-template.yaml" \
        "Environment=${ENVIRONMENT} ProjectName=${PROJECT_NAME} S3KeyArn=${s3_key_arn}"
    
    cd - > /dev/null
}

# Deploy DynamoDB
deploy_dynamodb() {
    log_info "=== Deploying DynamoDB Tables ==="
    
    # Get DynamoDB KMS key ARN
    local ddb_key_arn=$(get_stack_output "${PROJECT_NAME}-kms-${ENVIRONMENT}" "DynamoDBKeyArn")
    
    if [ -z "$ddb_key_arn" ]; then
        log_error "Could not retrieve DynamoDB KMS key ARN"
        exit 1
    fi
    
    cd "$(dirname "$0")/../04-dynamodb"
    
    deploy_stack \
        "${PROJECT_NAME}-dynamodb-${ENVIRONMENT}" \
        "dynamodb-template.yaml" \
        "Environment=${ENVIRONMENT} ProjectName=${PROJECT_NAME} DynamoDBKeyArn=${ddb_key_arn}"
    
    cd - > /dev/null
}

# Deploy Lambda functions
deploy_lambda() {
    log_info "=== Deploying Lambda Functions ==="
    
    cd "$(dirname "$0")/../05-lambda"
    
    # Generate SAM template if not exists
    if [ ! -f "lambda-template-${ENVIRONMENT}.yaml" ]; then
        log_info "Generating Lambda SAM template..."
        python3 generate-lambda-config.py "$ENVIRONMENT"
    fi
    
    # Build SAM application
    log_info "Building SAM application..."
    sam build --template-file "lambda-template-${ENVIRONMENT}.yaml"
    
    # Deploy SAM application
    log_info "Deploying SAM application..."
    sam deploy \
        --template-file ".aws-sam/build/template.yaml" \
        --stack-name "${PROJECT_NAME}-lambda-${ENVIRONMENT}" \
        --capabilities CAPABILITY_IAM \
        --region "$AWS_REGION" \
        --parameter-overrides \
            Environment="$ENVIRONMENT" \
            ProjectName="$PROJECT_NAME" \
        --tags \
            Project="$PROJECT_NAME" \
            Environment="$ENVIRONMENT"
    
    cd - > /dev/null
}

# Deploy API Gateway
deploy_api_gateway() {
    log_info "=== Deploying API Gateway ==="
    
    # Note: API Gateway would typically be deployed via SAM with Lambda functions
    # or as a separate CloudFormation template
    log_warning "API Gateway deployment would be included in Lambda SAM template or separate template"
}

# Main deployment function
main() {
    log_info "Starting FRANK infrastructure deployment"
    log_info "Project: $PROJECT_NAME"
    log_info "Environment: $ENVIRONMENT"
    log_info "Region: $AWS_REGION"
    
    check_prerequisites
    
    # Deploy in dependency order
    deploy_kms
    deploy_cognito
    deploy_s3
    deploy_dynamodb
    deploy_lambda
    deploy_api_gateway
    
    log_success "FRANK infrastructure deployment completed successfully!"
    
    # Display important outputs
    log_info "=== Deployment Summary ==="
    echo ""
    echo "Cognito User Pool ID: $(get_stack_output "${PROJECT_NAME}-cognito-${ENVIRONMENT}" "UserPoolId")"
    echo "S3 Raw Bucket: $(get_stack_output "${PROJECT_NAME}-s3-${ENVIRONMENT}" "RawDataBucketName")"
    echo "DynamoDB Aggregates Table: $(get_stack_output "${PROJECT_NAME}-dynamodb-${ENVIRONMENT}" "AggregatesTableName")"
    echo ""
    log_info "Check AWS Console for additional details and configure remaining services manually."
}

# Handle script arguments
case "${1:-all}" in
    "all")
        main
        ;;
    "kms")
        check_prerequisites
        deploy_kms
        ;;
    "cognito")
        check_prerequisites
        deploy_cognito
        ;;
    "s3")
        check_prerequisites
        deploy_s3
        ;;
    "dynamodb")
        check_prerequisites
        deploy_dynamodb
        ;;
    "lambda")
        check_prerequisites
        deploy_lambda
        ;;
    "api")
        check_prerequisites
        deploy_api_gateway
        ;;
    *)
        echo "Usage: $0 [all|kms|cognito|s3|dynamodb|lambda|api]"
        echo "  all     - Deploy all components (default)"
        echo "  kms     - Deploy KMS keys only"
        echo "  cognito - Deploy Cognito only"
        echo "  s3      - Deploy S3 buckets only"
        echo "  dynamodb- Deploy DynamoDB tables only"
        echo "  lambda  - Deploy Lambda functions only"
        echo "  api     - Deploy API Gateway only"
        exit 1
        ;;
esac
