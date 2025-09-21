#!/bin/bash

# ===================================
# FRANK Platform - Simple Deployment
# No SSL, no custom domain, just working app
# ===================================

set -euo pipefail

# Configuration
AWS_REGION="eu-west-1"
PROJECT_NAME="frank"
ENVIRONMENT="spike"
REPOSITORY_NAME="${PROJECT_NAME}-${ENVIRONMENT}"

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

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if AWS CLI is installed
    if ! command -v aws &> /dev/null; then
        log_error "AWS CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check if OpenTofu is installed
    if ! command -v tofu &> /dev/null; then
        log_error "OpenTofu is not installed. Please install it first."
        exit 1
    fi
    
    # Check AWS credentials
    if ! aws sts get-caller-identity &> /dev/null; then
        log_error "AWS credentials not configured. Please run 'aws configure'."
        exit 1
    fi
    
    log_success "All prerequisites are met."
}

deploy() {
    echo "🚀 Deploying FRANK spike to AWS..."

    # 1. Deploy infrastructure
    echo "📦 Deploying infrastructure..."
    tofu init
    tofu apply -auto-approve

    # 2. Get ECR URL
    ECR_URL=$(tofu output -raw ecr_repository_url)
    echo "📝 ECR Repository: $ECR_URL"

    # 3. Build and push image
    # Check if running on Apple Silicon
    if [[ $(uname -m) == "arm64" ]]; then
        echo "🍎 Detected Apple Silicon (M1/M2) - building for linux/amd64"
        docker buildx build --platform linux/amd64 -t frank-spike .
    else
        echo "💻 Detected x86_64 - building normally"
        docker build -t frank-spike .
    fi

    echo "🔐 Logging into ECR..."
    aws ecr get-login-password --region eu-west-1 | \
        docker login --username AWS --password-stdin $ECR_URL

    docker tag frank-spike:latest $ECR_URL:latest
    docker push $ECR_URL:latest

    # 4. Update ECS service
    echo "🔄 Updating ECS service..."
    aws ecs update-service \
        --cluster frank-spike-cluster \
        --service frank-spike-service \
        --force-new-deployment \
        --region eu-west-1 > /dev/null

    echo "⏳ Waiting for deployment..."
    aws ecs wait services-stable \
        --cluster frank-spike-cluster \
        --services frank-spike-service \
        --region eu-west-1

    # 5. Get URL and test
    APP_URL=$(tofu output -raw application_url)
    HEALTH_URL=$(tofu output -raw health_check_url)

    echo ""
    echo "✅ Deployment complete!"
    echo "🌐 Application: $APP_URL"
    echo "❤️  Health Check: $HEALTH_URL"
    echo ""
    echo "Testing health endpoint..."
    sleep 10
    curl -f $HEALTH_URL && echo "✅ Health check passed!" || echo "⚠️  Health check failed"
}

# Handle script arguments
case "${1:-help}" in
    "deploy")
        deploy
        ;;
    "check")
        check_prerequisites
        ;;
    "destroy")
        log_warning "Destroying infrastructure..."
        tofu destroy -auto-approve
        log_success "Infrastructure destroyed."
        ;;
    *)
        echo "Usage: $0 {check|deploy|destroy}"
        echo ""
        echo "Commands:"
        echo "  check              - Check prerequisites"
        echo "  deploy             - Full deployment (default)"
        echo "  destroy            - Destroy all infrastructure"
        exit 1
        ;;
esac