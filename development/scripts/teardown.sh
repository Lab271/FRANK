#!/bin/bash

# FRANK Infrastructure Teardown Script
# Safely removes all AWS components in reverse dependency order

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

# Confirm deletion
confirm_deletion() {
    if [ "$ENVIRONMENT" = "prod" ]; then
        log_warning "You are about to delete PRODUCTION environment!"
        echo -n "Type 'DELETE PRODUCTION' to confirm: "
        read confirmation
        if [ "$confirmation" != "DELETE PRODUCTION" ]; then
            log_info "Deletion cancelled"
            exit 0
        fi
    else
        echo -n "Are you sure you want to delete the $ENVIRONMENT environment? (y/N): "
        read confirmation
        if [ "$confirmation" != "y" ] && [ "$confirmation" != "Y" ]; then
            log_info "Deletion cancelled"
            exit 0
        fi
    fi
}

# Empty S3 buckets before deletion
empty_s3_buckets() {
    log_info "Emptying S3 buckets..."
    
    local buckets=(
        "${PROJECT_NAME}-raw-$(aws sts get-caller-identity --query 'Account' --output text)-${ENVIRONMENT}"
        "${PROJECT_NAME}-artifacts-$(aws sts get-caller-identity --query 'Account' --output text)-${ENVIRONMENT}"
        "${PROJECT_NAME}-exports-$(aws sts get-caller-identity --query 'Account' --output text)-${ENVIRONMENT}"
    )
    
    for bucket in "${buckets[@]}"; do
        if aws s3api head-bucket --bucket "$bucket" 2>/dev/null; then
            log_info "Emptying bucket: $bucket"
            aws s3 rm "s3://$bucket" --recursive --region "$AWS_REGION" || true
            
            # Delete versioned objects
            aws s3api list-object-versions --bucket "$bucket" --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' --output json | \
            jq '.Objects[]?' | \
            while read -r version; do
                key=$(echo "$version" | jq -r '.Key // empty')
                version_id=$(echo "$version" | jq -r '.VersionId // empty')
                if [ -n "$key" ] && [ -n "$version_id" ] && [ "$version_id" != "null" ]; then
                    aws s3api delete-object --bucket "$bucket" --key "$key" --version-id "$version_id" --region "$AWS_REGION" || true
                fi
            done
            
            # Delete delete markers
            aws s3api list-object-versions --bucket "$bucket" --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' --output json | \
            jq '.Objects[]?' | \
            while read -r marker; do
                key=$(echo "$marker" | jq -r '.Key // empty')
                version_id=$(echo "$marker" | jq -r '.VersionId // empty')
                if [ -n "$key" ] && [ -n "$version_id" ] && [ "$version_id" != "null" ]; then
                    aws s3api delete-object --bucket "$bucket" --key "$key" --version-id "$version_id" --region "$AWS_REGION" || true
                fi
            done
            
            log_success "Bucket $bucket emptied"
        else
            log_warning "Bucket $bucket not found or not accessible"
        fi
    done
}

# Delete CloudFormation stack
delete_stack() {
    local stack_name=$1
    
    log_info "Deleting stack: $stack_name"
    
    if aws cloudformation describe-stacks --stack-name "$stack_name" --region "$AWS_REGION" &>/dev/null; then
        aws cloudformation delete-stack --stack-name "$stack_name" --region "$AWS_REGION"
        
        log_info "Waiting for stack deletion to complete..."
        aws cloudformation wait stack-delete-complete --stack-name "$stack_name" --region "$AWS_REGION"
        
        if [ $? -eq 0 ]; then
            log_success "Stack $stack_name deleted successfully"
        else
            log_error "Failed to delete stack $stack_name"
            log_warning "Check AWS Console for details and manual cleanup"
        fi
    else
        log_warning "Stack $stack_name not found"
    fi
}

# Delete Lambda functions and SAM artifacts
delete_lambda() {
    log_info "=== Deleting Lambda Functions ==="
    
    # Delete SAM stack
    delete_stack "${PROJECT_NAME}-lambda-${ENVIRONMENT}"
    
    # Clean up SAM artifacts
    cd "$(dirname "$0")/../05-lambda"
    if [ -d ".aws-sam" ]; then
        log_info "Cleaning up SAM build artifacts..."
        rm -rf .aws-sam
    fi
    cd - > /dev/null
}

# Delete API Gateway
delete_api_gateway() {
    log_info "=== Deleting API Gateway ==="
    # API Gateway is typically included in Lambda SAM stack
    log_info "API Gateway resources deleted with Lambda stack"
}

# Delete DynamoDB
delete_dynamodb() {
    log_info "=== Deleting DynamoDB Tables ==="
    delete_stack "${PROJECT_NAME}-dynamodb-${ENVIRONMENT}"
}

# Delete S3
delete_s3() {
    log_info "=== Deleting S3 Buckets ==="
    empty_s3_buckets
    delete_stack "${PROJECT_NAME}-s3-${ENVIRONMENT}"
}

# Delete Cognito
delete_cognito() {
    log_info "=== Deleting Cognito ==="
    delete_stack "${PROJECT_NAME}-cognito-${ENVIRONMENT}"
}

# Delete KMS (only if not used by other environments)
delete_kms() {
    log_info "=== Deleting KMS Keys ==="
    
    if [ "$ENVIRONMENT" = "prod" ]; then
        log_warning "Skipping KMS deletion for production environment"
        log_warning "KMS keys contain important data and should be manually reviewed before deletion"
        return
    fi
    
    log_warning "KMS keys will be scheduled for deletion with 7-day waiting period"
    delete_stack "${PROJECT_NAME}-kms-${ENVIRONMENT}"
}

# Cleanup additional resources
cleanup_additional_resources() {
    log_info "=== Cleaning Up Additional Resources ==="
    
    # Delete log groups
    log_info "Deleting CloudWatch log groups..."
    aws logs describe-log-groups --region "$AWS_REGION" --log-group-name-prefix "/aws/lambda/frank-" --query 'logGroups[].logGroupName' --output text | \
    grep "$ENVIRONMENT" | \
    while read -r log_group; do
        if [ -n "$log_group" ]; then
            log_info "Deleting log group: $log_group"
            aws logs delete-log-group --log-group-name "$log_group" --region "$AWS_REGION" || true
        fi
    done
    
    # Delete API Gateway log groups
    aws logs describe-log-groups --region "$AWS_REGION" --log-group-name-prefix "API-Gateway-Execution-Logs" --query 'logGroups[].logGroupName' --output text | \
    while read -r log_group; do
        if [[ "$log_group" == *"$ENVIRONMENT"* ]]; then
            log_info "Deleting API Gateway log group: $log_group"
            aws logs delete-log-group --log-group-name "$log_group" --region "$AWS_REGION" || true
        fi
    done
    
    # Note: ECR repositories, if any, should be manually cleaned
    log_info "Note: ECR repositories (if any) should be manually reviewed and cleaned"
}

# Main teardown function
main() {
    log_info "Starting FRANK infrastructure teardown"
    log_info "Project: $PROJECT_NAME"
    log_info "Environment: $ENVIRONMENT"
    log_info "Region: $AWS_REGION"
    
    confirm_deletion
    
    # Delete in reverse dependency order
    delete_api_gateway
    delete_lambda
    delete_dynamodb
    delete_s3
    delete_cognito
    delete_kms
    
    cleanup_additional_resources
    
    log_success "FRANK infrastructure teardown completed!"
    log_warning "Please verify in AWS Console that all resources have been properly deleted"
    
    if [ "$ENVIRONMENT" != "prod" ]; then
        log_info "KMS keys are scheduled for deletion with a 7-day waiting period"
        log_info "Cancel deletion in AWS Console if needed during this period"
    fi
}

# Handle script arguments
case "${1:-all}" in
    "all")
        main
        ;;
    "confirm")
        # Skip confirmation for automation
        PROJECT_NAME="$PROJECT_NAME" AWS_REGION="$AWS_REGION" ENVIRONMENT="$ENVIRONMENT" main
        ;;
    *)
        echo "Usage: $0 [all|confirm]"
        echo "  all     - Interactive teardown with confirmation (default)"
        echo "  confirm - Teardown without confirmation prompt (for automation)"
        exit 1
        ;;
esac
