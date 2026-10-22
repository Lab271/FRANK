#!/bin/bash
# ===================================
# minimal_test.sh
# Ultra-minimal LocalStack test
# ===================================

echo "🧪 Testing minimal LocalStack setup..."

# Clean everything
docker stop minimal-localstack minimal-api minimal-dynamodb-admin 2>/dev/null || true
docker rm minimal-localstack minimal-api minimal-dynamodb-admin 2>/dev/null || true

# Start just LocalStack with minimal config
echo "🚀 Starting LocalStack..."
docker run -d \
  --name minimal-localstack \
  -p 4566:4566 \
  -e SERVICES=dynamodb \
  -e DEBUG=1 \
  -e AWS_DEFAULT_REGION=eu-west-1 \
  localstack/localstack:2.0

# Wait and check
echo "⏳ Waiting for LocalStack..."
sleep 15

echo "📋 LocalStack logs:"
docker logs minimal-localstack | tail -10

echo "🔍 Testing LocalStack health:"
curl -s http://localhost:4566/health || echo "❌ Health check failed"

echo "🗃️  Testing DynamoDB:"
aws --endpoint-url=http://localhost:4566 dynamodb list-tables || echo "❌ DynamoDB test failed"

echo "✅ If you see table list above (even if empty), LocalStack is working!"