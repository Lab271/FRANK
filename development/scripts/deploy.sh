#!/bin/bash
set -e

echo "🚀 Starting FRANK LocalStack Environment..."

# Change to development directory
cd "$(dirname "$0")/.."

# Check if LocalStack is running
if curl -s http://localhost:4566/_localstack/health > /dev/null 2>&1; then
    echo "✅ LocalStack is already running"
else
    echo "🔄 Starting LocalStack..."
    cd localstack
    docker-compose up -d
    
    # Wait for LocalStack to be ready
    echo "⏳ Waiting for LocalStack to be ready..."
    for i in {1..30}; do
        if curl -s http://localhost:4566/_localstack/health > /dev/null 2>&1; then
            echo "✅ LocalStack is ready"
            break
        fi
        echo "   Waiting... ($i/30)"
        sleep 2
    done
    
    cd ..
fi

echo "🏗️  Deploying FRANK infrastructure..."

# Build Lambda packages
echo "   Building Lambda packages..."
./scripts/build-lambdas.sh

# Deploy with Terraform
echo "   Initializing Terraform..."
cd localstack/terraform
terraform init

echo "   Applying Terraform configuration..."
terraform apply -auto-approve

echo "📊 Getting deployment outputs..."
terraform output

echo ""
echo "🎉 FRANK LocalStack deployment complete!"
echo ""
echo "📡 Available endpoints:"
echo "   API Gateway: http://localhost:4566/restapis/\$(terraform output -raw api_gateway_id)/local/_user_request_"
echo "   POST /v1/submission"
echo "   GET /v1/sighting"
echo "   GET /v1/stats"
echo ""
echo "🔑 API Key:"
terraform output -raw api_key
echo ""
echo "🧪 Test the API:"
echo "   curl -X POST http://localhost:4566/restapis/\$(terraform output -raw api_gateway_id)/local/_user_request_/v1/submission \\"
echo "     -H \"Content-Type: application/json\" \\"
echo "     -H \"X-Api-Key: \$(terraform output -raw api_key)\" \\"
echo "     -d '{\"submission\":{\"submitter\":{\"tier\":\"partner\"},\"sighting\":{\"confidence\":85}}}'"
