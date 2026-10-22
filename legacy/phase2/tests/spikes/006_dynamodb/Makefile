# ===================================
# Makefile
# Minimal DynamoDB LocalStack + FastAPI Prototype
# ===================================

.PHONY: help build up down logs test clean status

# Default target
help:
	@echo "🚀 Minimal DynamoDB + FastAPI Prototype"
	@echo ""
	@echo "Available commands:"
	@echo "  make up      - Start all services"
	@echo "  make down    - Stop all services"
	@echo "  make build   - Build Docker images"
	@echo "  make logs    - Show logs"
	@echo "  make test    - Run API tests"
	@echo "  make status  - Check service status"
	@echo "  make clean   - Clean up everything"
	@echo ""
	@echo "📚 URLs:"
	@echo "  API:         http://localhost:8000"
	@echo "  API Docs:    http://localhost:8000/docs"
	@echo "  DynamoDB UI: http://localhost:8001"

# Build Docker images
build:
	@echo "🔨 Building Docker images..."
	docker-compose build

# Start all services
up:
	@echo "🚀 Starting services..."
	docker-compose up -d
	@echo "⏳ Waiting for services to be ready..."
	@sleep 10
	@make status

# Stop all services
down:
	@echo "🛑 Stopping services..."
	docker-compose down

# Show logs
logs:
	@echo "📋 Service logs:"
	docker-compose logs -f

# Show logs for specific service
logs-api:
	@echo "📋 API logs:"
	docker-compose logs -f api

logs-localstack:
	@echo "📋 LocalStack logs:"
	docker-compose logs -f localstack

# Check service status
status:
	@echo "📊 Service Status:"
	@echo ""
	@echo "🐳 Docker containers:"
	@docker-compose ps
	@echo ""
	@echo "🌐 API Health:"
	@curl -s http://localhost:8000/health 2>/dev/null | python3 -m json.tool || echo "❌ API not responding"
	@echo ""
	@echo "🗃️  LocalStack Health:"
	@curl -s http://localhost:4566/health 2>/dev/null | python3 -m json.tool || echo "❌ LocalStack not responding"

# Run tests
test:
	@echo "🧪 Running API tests..."
	@chmod +x test_api.sh
	@./test_api.sh

# Quick test - just create and list records
test-quick:
	@echo "🧪 Quick API test..."
	@curl -s -X POST http://localhost:8000/records \
		-H "Content-Type: application/json" \
		-d '{"name":"Quick Test","data":"Hello from make!","category":"makefile"}' | python3 -m json.tool
	@echo ""
	@curl -s http://localhost:8000/records | python3 -m json.tool

# Clean up everything
clean:
	@echo "🧹 Cleaning up..."
	docker-compose down -v --remove-orphans
	docker system prune -f
	sudo rm -rf localstack-data

# Development mode - rebuild and restart
dev:
	@echo "🔄 Development restart..."
	@make down
	@make build
	@make up
	@make test-quick

# Show AWS CLI commands for direct DynamoDB access
aws-help:
	@echo "🔧 Direct DynamoDB access commands:"
	@echo ""
	@echo "List tables:"
	@echo "  aws --endpoint-url=http://localhost:4566 dynamodb list-tables"
	@echo ""
	@echo "Scan table:"
	@echo "  aws --endpoint-url=http://localhost:4566 dynamodb scan --table-name simple-records"
	@echo ""
	@echo "Get item:"
	@echo "  aws --endpoint-url=http://localhost:4566 dynamodb get-item --table-name simple-records --key '{\"id\":{\"S\":\"YOUR_ID\"}}'"

# Show service URLs
urls:
	@echo "🌐 Service URLs:"
	@echo "  API:              http://localhost:8000"
	@echo "  API Health:       http://localhost:8000/health"
	@echo "  API Docs:         http://localhost:8000/docs"
	@echo "  DynamoDB Admin:   http://localhost:8001"
	@echo "  LocalStack:       http://localhost:4566"