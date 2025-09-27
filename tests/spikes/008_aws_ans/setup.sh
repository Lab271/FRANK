#!/bin/bash

# ===================================
# FRANK 008 AWS Spike - Ansible Setup Script
# Installs Ansible and required collections
# ===================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is required but not installed"
        exit 1
    fi
    log_success "Python 3: $(python3 --version)"
    
    # Check pip
    if ! command -v pip3 &> /dev/null; then
        log_error "pip3 is required but not installed"
        exit 1
    fi
    log_success "pip3: $(pip3 --version)"
    
    # Check AWS CLI
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is required but not installed"
        log_info "Install with: pip3 install awscli"
        exit 1
    fi
    log_success "AWS CLI: $(aws --version)"
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is required but not installed"
        exit 1
    fi
    log_success "Docker: $(docker --version)"
}

# Install Ansible
install_ansible() {
    log_info "Installing Ansible..."
    
    # Check if Ansible is already installed
    if command -v ansible-playbook &> /dev/null; then
        current_version=$(ansible --version | head -n1)
        log_info "Ansible already installed: $current_version"
    else
        log_info "Installing Ansible via pip..."
        pip3 install --user ansible
        
        # Add to PATH if needed
        if ! command -v ansible-playbook &> /dev/null; then
            log_warning "Ansible not found in PATH"
            log_info "Add ~/.local/bin to your PATH: export PATH=\$PATH:~/.local/bin"
        fi
    fi
    
    log_success "Ansible installed: $(ansible --version | head -n1)"
}

# Install required collections
install_collections() {
    log_info "Installing Ansible collections..."
    
    ansible-galaxy collection install -r requirements.yml
    
    log_success "Collections installed successfully"
}

# Create directory structure
create_directories() {
    log_info "Creating directory structure..."
    
    directories=(
        "logs"
        "group_vars"
        "host_vars"
        "roles"
        "../templates"  # CloudFormation templates
    )
    
    for dir in "${directories[@]}"; do
        mkdir -p "$dir"
        log_info "Created directory: $dir"
    done
    
    log_success "Directory structure created"
}

# Verify AWS credentials
verify_aws_credentials() {
    log_info "Verifying AWS credentials..."
    
    # Check default profile
    if aws sts get-caller-identity &> /dev/null; then
        identity=$(aws sts get-caller-identity)
        account=$(echo "$identity" | grep -o '"Account": "[^"]*"' | cut -d'"' -f4)
        log_success "Default AWS profile: Account $account"
    else
        log_warning "Default AWS profile not configured"
    fi
    
    # Check spike account profile
    if aws sts get-caller-identity --profile spike-account &> /dev/null; then
        identity=$(aws sts get-caller-identity --profile spike-account)
        account=$(echo "$identity" | grep -o '"Account": "[^"]*"' | cut -d'"' -f4)
        log_success "Spike account profile: Account $account"
    else
        log_warning "Spike account profile not configured"
        log_info "Configure with: aws configure --profile spike-account"
    fi
    
    # Check main account profile
    if aws sts get-caller-identity --profile main-account &> /dev/null; then
        identity=$(aws sts get-caller-identity --profile main-account)
        account=$(echo "$identity" | grep -o '"Account": "[^"]*"' | cut -d'"' -f4)
        log_success "Main account profile: Account $account"
    else
        log_warning "Main account profile not configured"
        log_info "Configure with: aws configure --profile main-account"
    fi
}

# Test Ansible installation
test_ansible() {
    log_info "Testing Ansible installation..."
    
    # Test basic functionality
    if ansible localhost -m ping &> /dev/null; then
        log_success "Ansible ping test passed"
    else
        log_error "Ansible ping test failed"
        exit 1
    fi
    
    # Test AWS collection
    if ansible localhost -m amazon.aws.aws_caller_info &> /dev/null; then
        log_success "AWS collection test passed"
    else
        log_warning "AWS collection test failed - check AWS credentials"
    fi
}

# Display setup summary
display_summary() {
    echo ""
    echo "=========================================="
    echo "🎉 FRANK Ansible Setup Complete!"
    echo "=========================================="
    echo ""
    echo "📋 Next Steps:"
    echo "1. Update vars/accounts.yml with your AWS account IDs"
    echo "2. Update vars/frank-config.yml with your domain settings"
    echo "3. Ensure cross-account IAM role exists in main account"
    echo "4. Deploy FRANK infrastructure:"
    echo "   ansible-playbook deploy-frank.yml"
    echo ""
    echo "🔧 Available Commands:"
    echo "   Deploy:    ansible-playbook deploy-frank.yml"
    echo "   Cleanup:   ansible-playbook deploy-frank.yml --tags cleanup"
    echo "   Check:     ansible-playbook deploy-frank.yml --check"
    echo "   Verbose:   ansible-playbook deploy-frank.yml -vvv"
    echo ""
    echo "📁 Configuration Files:"
    echo "   - vars/accounts.yml (AWS account settings)"
    echo "   - vars/frank-config.yml (FRANK configuration)"
    echo "   - inventory.yml (Ansible inventory)"
    echo "   - ansible.cfg (Ansible settings)"
    echo "=========================================="
}

# Main execution
main() {
    echo "🚀 FRANK Ansible Environment Setup"
    echo "=================================="
    
    check_prerequisites
    install_ansible
    create_directories
    install_collections
    verify_aws_credentials
    test_ansible
    display_summary
}

# Handle command line arguments
case "${1:-setup}" in
    "setup")
        main
        ;;
    "test")
        log_info "Running Ansible tests..."
        test_ansible
        ;;
    "check")
        log_info "Checking prerequisites..."
        check_prerequisites
        verify_aws_credentials
        ;;
    *)
        echo "Usage: $0 {setup|test|check}"
        echo ""
        echo "Commands:"
        echo "  setup - Full environment setup (default)"
        echo "  test  - Test Ansible installation"
        echo "  check - Check prerequisites only"
        exit 1
        ;;
esac