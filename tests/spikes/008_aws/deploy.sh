#!/bin/bash

# ===================================
# FRANK Platform - Simple Deployment
# No SSL, no custom domain, just working app
# ===================================

set -e


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
    echo "🐳 Building Docker image..."
    docker build -t frank-spike .

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
    "destroy")
        log_warning "Destroying infrastructure..."
        tofu destroy -auto-approve
        log_success "Infrastructure destroyed."
        ;;
    *)
        echo "Usage: $0 {deploy|destroy}"
        echo ""
        echo "Commands:"
        echo "  deploy              - Full deployment (default)"
        echo "  destroy            - Destroy all infrastructure"
        exit 1
        ;;
esac