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
STACK_NAME="frank-cognito-spike"
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
            ParameterKey=ProjectName,ParameterValue=frank-cognito-spike \
            ParameterKey=Environment,ParameterValue=spike \
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

setup_user_passwords() {
    print_header "Setting Up User Passwords"
    
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
    
    # Set password for testuser_observer
    echo "Setting password for testuser_observer..."
    if aws cognito-idp admin-set-user-password \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_observer" \
        --password "TempPass123!" \
        --permanent \
        --profile "$PROFILE" \
        --region "$REGION"; then
        print_success "Password set for testuser_observer"
    else
        print_warning "Failed to set password for testuser_observer (user may not exist yet)"
    fi
    
    # Set password for testuser_contributor
    echo "Setting password for testuser_contributor..."
    if aws cognito-idp admin-set-user-password \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_contributor" \
        --password "TempPass123!" \
        --permanent \
        --profile "$PROFILE" \
        --region "$REGION"; then
        print_success "Password set for testuser_contributor"
    else
        print_warning "Failed to set password for testuser_contributor (user may not exist yet)"
    fi
    
    # Set password for testuser_partner
    echo "Setting password for testuser_partner..."
    if aws cognito-idp admin-set-user-password \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_partner" \
        --password "TempPass123!" \
        --permanent \
        --profile "$PROFILE" \
        --region "$REGION"; then
        print_success "Password set for testuser_partner"
    else
        print_warning "Failed to set password for testuser_partner (user may not exist yet)"
    fi
    
    # Set password for testuser_core_member
    echo "Setting password for testuser_core_member..."
    if aws cognito-idp admin-set-user-password \
        --user-pool-id "$USER_POOL_ID" \
        --username "testuser_core_member" \
        --password "TempPass123!" \
        --permanent \
        --profile "$PROFILE" \
        --region "$REGION"; then
        print_success "Password set for testuser_core_member"
    else
        print_warning "Failed to set password for testuser_core_member (user may not exist yet)"
    fi
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
    
    COGNITO_ENDPOINT=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --profile "$PROFILE" \
        --region "$REGION" \
        --query 'Stacks[0].Outputs[?OutputKey==`CognitoAuthEndpoint`].OutputValue' \
        --output text)
    
    echo ""
    print_header "Next Steps"
    echo "1. Test authentication:"
    echo "   python simple_api.py --endpoint=$COGNITO_ENDPOINT --user-pool-id=$USER_POOL_ID --app-client-id=$APP_CLIENT_ID"
    echo ""
    echo "2. Test user login with AWS CLI:"
    echo "   aws cognito-idp admin-initiate-auth \\"
    echo "     --user-pool-id $USER_POOL_ID \\"
    echo "     --client-id $APP_CLIENT_ID \\"
    echo "     --auth-flow ADMIN_NO_SRP_AUTH \\"
    echo "     --auth-parameters USERNAME=testuser_contributor,PASSWORD=TempPass123! \\"
    echo "     --profile $PROFILE \\"
    echo "     --region $REGION"
    echo ""
    echo "3. Run Simple API with AWS Cognito:"
    echo "   python simple_api_aws.py"
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
        setup_user_passwords
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