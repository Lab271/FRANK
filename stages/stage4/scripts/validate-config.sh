#!/bin/bash

# FRANK Configuration Validation Script
# Validates CloudFormation templates and configuration files

set -e

# Configuration
PROJECT_NAME=${PROJECT_NAME:-frank}
AWS_REGION=${AWS_REGION:-eu-west-1}

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

# Validate CloudFormation template
validate_cfn_template() {
    local template_file=$1
    local template_name=$2
    
    log_info "Validating CloudFormation template: $template_name"
    
    if [ ! -f "$template_file" ]; then
        log_error "Template file not found: $template_file"
        return 1
    fi
    
    # Validate syntax
    if aws cloudformation validate-template --template-body "file://$template_file" --region "$AWS_REGION" &>/dev/null; then
        log_success "Template $template_name is valid"
        return 0
    else
        log_error "Template $template_name validation failed"
        aws cloudformation validate-template --template-body "file://$template_file" --region "$AWS_REGION" 2>&1 | head -5
        return 1
    fi
}

# Validate JSON files
validate_json_file() {
    local json_file=$1
    local file_name=$2
    
    log_info "Validating JSON file: $file_name"
    
    if [ ! -f "$json_file" ]; then
        log_warning "JSON file not found: $json_file"
        return 1
    fi
    
    if python3 -m json.tool "$json_file" &>/dev/null; then
        log_success "JSON file $file_name is valid"
        return 0
    else
        log_error "JSON file $file_name is invalid"
        return 1
    fi
}

# Validate YAML files
validate_yaml_file() {
    local yaml_file=$1
    local file_name=$2
    
    log_info "Validating YAML file: $file_name"
    
    if [ ! -f "$yaml_file" ]; then
        log_warning "YAML file not found: $yaml_file"
        return 1
    fi
    
    if python3 -c "import yaml; yaml.safe_load(open('$yaml_file'))" &>/dev/null; then
        log_success "YAML file $file_name is valid"
        return 0
    else
        log_error "YAML file $file_name is invalid"
        return 1
    fi
}

# Check for required tools
check_tools() {
    log_info "Checking required tools..."
    
    local tools=("aws" "python3" "jq")
    local missing_tools=()
    
    for tool in "${tools[@]}"; do
        if ! command -v "$tool" &> /dev/null; then
            missing_tools+=("$tool")
        fi
    done
    
    if [ ${#missing_tools[@]} -gt 0 ]; then
        log_error "Missing required tools: ${missing_tools[*]}"
        return 1
    fi
    
    log_success "All required tools are available"
    return 0
}

# Validate AWS credentials
check_aws_credentials() {
    log_info "Checking AWS credentials..."
    
    if aws sts get-caller-identity --region "$AWS_REGION" &>/dev/null; then
        local account_id=$(aws sts get-caller-identity --query 'Account' --output text)
        local user_arn=$(aws sts get-caller-identity --query 'Arn' --output text)
        log_success "AWS credentials valid"
        log_info "Account ID: $account_id"
        log_info "User ARN: $user_arn"
        return 0
    else
        log_error "AWS credentials not configured or invalid"
        return 1
    fi
}

# Validate region configuration
check_region() {
    log_info "Checking AWS region configuration..."
    
    local region_check=$(aws configure get region 2>/dev/null || echo "")
    
    if [ -z "$region_check" ]; then
        log_warning "No default region configured, using: $AWS_REGION"
    else
        log_info "Configured region: $region_check"
    fi
    
    # Test region accessibility
    if aws ec2 describe-regions --region "$AWS_REGION" --region-names "$AWS_REGION" &>/dev/null; then
        log_success "Region $AWS_REGION is accessible"
        return 0
    else
        log_error "Region $AWS_REGION is not accessible"
        return 1
    fi
}

# Validate CloudFormation templates
validate_templates() {
    log_info "=== Validating CloudFormation Templates ==="
    
    local validation_failed=0
    local base_dir="$(dirname "$0")/.."
    
    # KMS template
    validate_cfn_template "$base_dir/02-kms/kms-template.yaml" "KMS" || validation_failed=1
    
    # Cognito template
    validate_cfn_template "$base_dir/01-cognito/cognito-template.yaml" "Cognito" || validation_failed=1
    
    # S3 template
    validate_cfn_template "$base_dir/03-s3/s3-template.yaml" "S3" || validation_failed=1
    
    # DynamoDB template
    validate_cfn_template "$base_dir/04-dynamodb/dynamodb-template.yaml" "DynamoDB" || validation_failed=1
    
    return $validation_failed
}

# Validate configuration files
validate_configs() {
    log_info "=== Validating Configuration Files ==="
    
    local validation_failed=0
    local base_dir="$(dirname "$0")/.."
    
    # Check if Python script exists and is valid
    if [ -f "$base_dir/05-lambda/generate-lambda-config.py" ]; then
        log_info "Checking Lambda configuration generator..."
        if python3 -m py_compile "$base_dir/05-lambda/generate-lambda-config.py" &>/dev/null; then
            log_success "Lambda configuration generator is valid"
        else
            log_error "Lambda configuration generator has syntax errors"
            validation_failed=1
        fi
    fi
    
    return $validation_failed
}

# Check for potential issues
check_potential_issues() {
    log_info "=== Checking for Potential Issues ==="
    
    local issues_found=0
    
    # Check for hardcoded values that should be parameterized
    log_info "Checking for hardcoded values..."
    
    local templates=(
        "01-cognito/cognito-template.yaml"
        "02-kms/kms-template.yaml"
        "03-s3/s3-template.yaml"
        "04-dynamodb/dynamodb-template.yaml"
    )
    
    for template in "${templates[@]}"; do
        local template_path="$(dirname "$0")/../$template"
        if [ -f "$template_path" ]; then
            # Check for hardcoded account IDs (should use AWS::AccountId)
            if grep -q "123456789012\|111122223333" "$template_path" 2>/dev/null; then
                log_warning "Potential hardcoded account ID found in $template"
                issues_found=1
            fi
            
            # Check for hardcoded regions (should use AWS::Region)
            if grep -q "us-east-1\|eu-west-1" "$template_path" 2>/dev/null && ! grep -q "AWS::Region" "$template_path"; then
                log_warning "Potential hardcoded region found in $template"
                issues_found=1
            fi
        fi
    done
    
    # Check for consistent naming patterns
    log_info "Checking naming consistency..."
    
    # This would be expanded based on specific naming conventions
    
    if [ $issues_found -eq 0 ]; then
        log_success "No obvious issues found"
    fi
    
    return $issues_found
}

# Validate resource limits and quotas
check_resource_limits() {
    log_info "=== Checking AWS Resource Limits ==="
    
    # Check VPC limits (for future OpenSearch deployment)
    local vpc_count=$(aws ec2 describe-vpcs --region "$AWS_REGION" --query 'length(Vpcs)' --output text 2>/dev/null || echo "0")
    log_info "Current VPC count: $vpc_count/5 (default limit)"
    
    # Check CloudFormation stack limits
    local stack_count=$(aws cloudformation list-stacks --region "$AWS_REGION" --stack-status-filter CREATE_COMPLETE UPDATE_COMPLETE --query 'length(StackSummaries)' --output text 2>/dev/null || echo "0")
    log_info "Current CloudFormation stack count: $stack_count/200 (default limit)"
    
    # Check Lambda function limits
    local lambda_count=$(aws lambda list-functions --region "$AWS_REGION" --query 'length(Functions)' --output text 2>/dev/null || echo "0")
    log_info "Current Lambda function count: $lambda_count/1000 (default limit)"
    
    log_success "Resource limits check completed"
}

# Generate validation report
generate_report() {
    local overall_status=$1
    
    log_info "=== Validation Report ==="
    echo ""
    echo "Project: $PROJECT_NAME"
    echo "Region: $AWS_REGION"
    echo "Validation Time: $(date)"
    echo ""
    
    if [ $overall_status -eq 0 ]; then
        log_success "✅ All validations passed"
        echo ""
        log_info "The configuration is ready for deployment."
        log_info "Run the deployment script: ./scripts/deploy-all.sh"
    else
        log_error "❌ Some validations failed"
        echo ""
        log_error "Please fix the issues above before deploying."
    fi
}

# Main validation function
main() {
    log_info "Starting FRANK configuration validation"
    
    local validation_status=0
    
    # Prerequisites
    check_tools || validation_status=1
    check_aws_credentials || validation_status=1
    check_region || validation_status=1
    
    # Template validation
    validate_templates || validation_status=1
    
    # Configuration validation
    validate_configs || validation_status=1
    
    # Additional checks
    check_potential_issues || validation_status=1
    check_resource_limits
    
    # Generate report
    generate_report $validation_status
    
    exit $validation_status
}

# Handle script arguments
case "${1:-all}" in
    "all")
        main
        ;;
    "templates")
        check_tools
        validate_templates
        ;;
    "configs")
        check_tools
        validate_configs
        ;;
    "aws")
        check_aws_credentials
        check_region
        check_resource_limits
        ;;
    *)
        echo "Usage: $0 [all|templates|configs|aws]"
        echo "  all       - Run all validations (default)"
        echo "  templates - Validate CloudFormation templates only"
        echo "  configs   - Validate configuration files only"
        echo "  aws       - Check AWS credentials and limits only"
        exit 1
        ;;
esac
