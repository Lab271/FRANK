#!/bin/bash
# ==============================================================================
# FRANK Platform - Cognito Authentication Spike - AWS Deployment Script
# ==============================================================================
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0
#
# Deploy AWS Cognito User Pool to eu-central-1 using spike-account profile
# ==============================================================================

set -e

# Configuration
PROJECT_NAME="frank-cognito-010"
ENVIRONMENT="spike"
STACK_NAME="${PROJECT_NAME}-${ENVIRONMENT}"
REGION="eu-central-1"
PROFILE="spike-account"
TEMPLATE_FILE="cognito-aws-infrastructure.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo -e "${BLUE}=================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}=================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

check_prerequisites() {
    print_header "Checking Prerequisites"
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        print_error "AWS CLI is not installed"
        exit 1
    fi
    print_success "AWS CLI is available"
    
    # Check AWS profile
    if ! aws configure list-profiles | grep -q "$PROFILE"; then
        print_error "AWS profile '$PROFILE' not found"
        echo "Available profiles:"
        aws configure list-profiles
        exit 1
    fi
    print_success "AWS profile '$PROFILE' is available"
    
    # Check template file
    if [ ! -f "$TEMPLATE_FILE" ]; then
        print_error "CloudFormation template '$TEMPLATE_FILE' not found"
        exit 1
    fi
    print_success "CloudFormation template found"
    
    # Test AWS credentials
    echo "Testing AWS credentials..."
    if ! aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" &> /dev/null; then
        print_error "Failed to authenticate with AWS using profile '$PROFILE'"
        exit 1
    fi
    print_success "AWS credentials are valid"
    
    # Show caller identity
    CALLER_IDENTITY=$(aws sts get-caller-identity --profile "$PROFILE" --region "$REGION")
    echo "Authenticated as:"
    echo "$CALLER_IDENTITY" | jq .
}

validate_template() {
    print_header "Validating CloudFormation Template"
    
    if aws cloudformation validate-template \
        --template-body "file://$TEMPLATE_FILE" \
        --profile "$PROFILE" \
        --region "$REGION" > /dev/null; then
        print_success "CloudFormation template is valid"
    else
        print_error "CloudFormation template validation failed"
        exit 1
    fi
}

deploy_stack() {
    print_header "Deploying Cognito Infrastructure"
    
    echo "Stack Name: $STACK_NAME"
    echo "Region: $REGION"
    echo "Profile: $PROFILE"
    echo ""
    
    # Check if stack exists
    if aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --profile "$PROFILE" \
        --region "$REGION" &> /dev/null; then
        
        print_warning "Stack '$STACK_NAME' already exists. Updating..."
        OPERATION="update-stack"
    else
        echo "Creating new stack '$STACK_NAME'..."
        OPERATION="create-stack"
    fi
    
    # Deploy stack
    aws cloudformation "$OPERATION" \
        --stack-name "$STACK_NAME" \
        --template-body "file://$TEMPLATE_FILE" \
        --parameters \
            ParameterKey=ProjectName,ParameterValue=$PROJECT_NAME \
            ParameterKey=Environment,ParameterValue=$ENVIRONMENT \
        --capabilities CAPABILITY_IAM \
        --profile "$PROFILE" \
        --region "$REGION"
    
    print_success "Stack deployment initiated"
    
    # Wait for completion
    echo "Waiting for stack deployment to complete..."
    if aws cloudformation wait stack-"${OPERATION//-stack/}"-complete \
        --stack-name "$STACK_NAME" \
        --profile "$PROFILE" \
        --region "$REGION"; then
        print_success "Stack deployment completed successfully"
    else
        print_error "Stack deployment failed"
        exit 1
    fi
}

create_users() {
    print_header "Creating Test Users"
    
    # Get User Pool ID from stack outputs
    USER_POOL_ID=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
        --output text)
    
    if [ -z "$USER_POOL_ID" ]; then
        print_error "Could not get User Pool ID from stack outputs"
        exit 1
    fi
    
    print_success "User Pool ID: $USER_POOL_ID"
    echo ""
    
    # Create testuser_observer
    echo "Creating testuser_observer@example.com..."
    aws cognito-idp admin-create-user \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_observer@example.com" \
        --user-attributes \
            Name=email,Value=testuser_observer@example.com \
            Name=given_name,Value=Observer \
            Name=family_name,Value=User \
            Name=custom:organisation,Value=acme-corp \
            Name=email_verified,Value=true \
        --message-action SUPPRESS \
        --profile "$PROFILE" \
        --region "$REGION" 2>/dev/null || echo "  (User may already exist)"
    
    aws cognito-idp admin-set-user-password \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_observer@example.com" \
        --password "TempPass123!" \
        --permanent \
        --profile "$PROFILE" \
        --region "$REGION" >/dev/null
    
    aws cognito-idp admin-add-user-to-group \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_observer@example.com" \
        --group-name "observer" \
        --profile "$PROFILE" \
        --region "$REGION" 2>/dev/null || true
    
    print_success "testuser_observer@example.com created and added to observer group"
    
    # Create testuser_contributor
    echo "Creating testuser_contributor@example.com..."
    aws cognito-idp admin-create-user \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_contributor@example.com" \
        --user-attributes \
            Name=email,Value=testuser_contributor@example.com \
            Name=given_name,Value=Contributor \
            Name=family_name,Value=User \
            Name=custom:organisation,Value=cyber-security-inc \
            Name=email_verified,Value=true \
        --message-action SUPPRESS \
        --profile "$PROFILE" \
        --region "$REGION" 2>/dev/null || echo "  (User may already exist)"
    
    aws cognito-idp admin-set-user-password \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_contributor@example.com" \
        --password "TempPass123!" \
        --permanent \
        --profile "$PROFILE" \
        --region "$REGION" >/dev/null
    
    aws cognito-idp admin-add-user-to-group \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_contributor@example.com" \
        --group-name "contributor" \
        --profile "$PROFILE" \
        --region "$REGION" 2>/dev/null || true
    
    print_success "testuser_contributor@example.com created and added to contributor group"
    
    # Create testuser_partner
    echo "Creating testuser_partner@example.com..."
    aws cognito-idp admin-create-user \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_partner@example.com" \
        --user-attributes \
            Name=email,Value=testuser_partner@example.com \
            Name=given_name,Value=Partner \
            Name=family_name,Value=User \
            Name=custom:organisation,Value=threat-intel-partners \
            Name=email_verified,Value=true \
        --message-action SUPPRESS \
        --profile "$PROFILE" \
        --region "$REGION" 2>/dev/null || echo "  (User may already exist)"
    
    aws cognito-idp admin-set-user-password \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_partner@example.com" \
        --password "TempPass123!" \
        --permanent \
        --profile "$PROFILE" \
        --region "$REGION" >/dev/null
    
    aws cognito-idp admin-add-user-to-group \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_partner@example.com" \
        --group-name "partner" \
        --profile "$PROFILE" \
        --region "$REGION" 2>/dev/null || true
    
    print_success "testuser_partner@example.com created and added to partner group"
    
    # Create testuser_core_member
    echo "Creating testuser_core_member@example.com..."
    aws cognito-idp admin-create-user \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_core_member@example.com" \
        --user-attributes \
            Name=email,Value=testuser_core_member@example.com \
            Name=given_name,Value="Core Member" \
            Name=family_name,Value=User \
            Name=custom:organisation,Value=frank-platform \
            Name=email_verified,Value=true \
        --message-action SUPPRESS \
        --profile "$PROFILE" \
        --region "$REGION" 2>/dev/null || echo "  (User may already exist)"
    
    aws cognito-idp admin-set-user-password \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_core_member@example.com" \
        --password "TempPass123!" \
        --permanent \
        --profile "$PROFILE" \
        --region "$REGION" >/dev/null
    
    aws cognito-idp admin-add-user-to-group \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_core_member@example.com" \
        --group-name "core_member" \
        --profile "$PROFILE" \
        --region "$REGION" 2>/dev/null || true
    
    print_success "testuser_core_member@example.com created and added to core_member group"
}

get_outputs() {
    print_header "Stack Outputs"
    
    OUTPUTS=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs' \
        --output table)
    
    echo "$OUTPUTS"
    echo ""
    
    # Get specific outputs for easy access
    USER_POOL_ID=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
        --output text)
    
    APP_CLIENT_ID=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`AppClientId`].OutputValue' \
        --output text)
    
    COGNITO_URL=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`CognitoAuthEndpoint`].OutputValue' \
        --output text)
    
    echo ""
    print_header "Next Steps"
    echo "1. Test authentication:"
    echo -e "${YELLOW}   python simple_api_010.py --environment=aws --cognito-url=$COGNITO_URL --user-pool-id=$USER_POOL_ID --app-client-id=$APP_CLIENT_ID ${NC}"
    echo ""
    echo "2. Test user login with AWS CLI:"
    echo -e "${YELLOW}   aws cognito-idp admin-initiate-auth \\ ${NC}"
    echo -e "${YELLOW}     --user-pool-id $USER_POOL_ID \\ ${NC}"
    echo -e "${YELLOW}     --client-id $APP_CLIENT_ID \\ ${NC}"
    echo -e "${YELLOW}     --auth-flow ADMIN_NO_SRP_AUTH \\ ${NC}"
    echo -e "${YELLOW}     --auth-parameters USERNAME=testuser_contributor,PASSWORD=TempPass123! \\ ${NC}"
    echo -e "${YELLOW}     --profile $PROFILE \\ ${NC}"
    echo -e "${YELLOW}     --region $REGION ${NC}"
    echo ""
}

cleanup_stack() {
    print_header "Cleaning Up Stack"
    
    read -p "Are you sure you want to delete the stack '$STACK_NAME'? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        aws cloudformation delete-stack \
            --stack-name "$STACK_NAME" \
            --profile "$PROFILE" \
            --region "$REGION"
        
        print_success "Stack deletion initiated"
        
        echo "Waiting for stack deletion to complete..."
        aws cloudformation wait stack-delete-complete \
            --stack-name "$STACK_NAME" \
            --profile "$PROFILE" \
            --region "$REGION"
        
        print_success "Stack deleted successfully"
        
    else
        echo "Stack deletion cancelled"
    fi
}

# Main script
case "${1:-deploy}" in
    "check")
        check_prerequisites
        ;;
    "deploy")
        check_prerequisites
        validate_template
        deploy_stack
        create_users
        get_outputs
        ;;
    "setup")
        create_users
        get_outputs
        ;;
    "status")
        get_outputs
        ;;
    "cleanup"|"destroy"|"delete")
        cleanup_stack
        ;;
    "help"|"-h"|"--help")
        echo "Usage: $0 [check|deploy|config|status|outputs|cleanup]"
        echo ""
        echo "Commands:"
        echo "  check    - Check AWS prerequisites only"
        echo "  deploy   - Deploy Cognito infrastructure and setup users"
        echo "  setup    - Setup users"
        echo "  status   - Show stack status and configuration"
        echo "  cleanup  - Delete the stack and clean up"
        echo "  help     - Show this help message"
        ;;
    *)
        print_error "Unknown command: $1"
        echo "Use '$0 help' for usage information"
        exit 1
        ;;
esac
