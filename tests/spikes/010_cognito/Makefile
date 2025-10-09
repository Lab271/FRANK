# ==============================================================================
# FRANK Platform - Cognito Authentication Spike - Build and Test Automation
# ==============================================================================
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0
#
# This spike tests authentication patterns using Mock Cognito service and Simple API:
#
# 1. Mock Cognito service: FastAPI-based authentication service
#    - Docker internal: :8100, External via nginx: :8100
#
# 2. Simple API service: Role-based access control demo (Multiple variants)
#    - simple_api.py: Mock Cognito only
#    - simple_api_aws.py: AWS Cognito only  
#    - simple_api_unified.py: Both Mock and AWS Cognito (RECOMMENDED)
#    - Docker internal: :8000, External via nginx: :443 (HTTPS), :8080 (HTTP)
#    - Swagger: https://frank-010-cognito.local/docs
#
# 3. Nginx Load Balancer: SSL termination and routing
#    - :80 -> redirect to :443 (HTTPS)
#    - :443 -> HTTPS to Simple API
#    - :8000 -> Direct HTTP to Simple API locally
#    - :8080 -> Direct HTTP to Simple API externally to Docker
#    - :8100 -> Direct HTTP to Mock Cognito
#
# Usage: make up / make setup / make test / make test-api / make run-local
# ==============================================================================

LOCAL_DOMAIN = frank-010-cognito.local
MOCK_COGNITO_ENDPOINT = http://localhost:8100
SIMPLE_API_ENDPOINT = https://$(LOCAL_DOMAIN)
SIMPLE_API_HTTP_ENDPOINT = http://localhost:8000

start: ## Start Colima if not already running
	@colima start
	@colima status

ssl-certs/nginx.crt: ~/.ssl-certs/ca.crt
	@mkdir -p ssl-certs
	@mkcert -key-file ssl-certs/nginx.key -cert-file ssl-certs/nginx.crt $(LOCAL_DOMAIN)

cleanup: ## Clean up docker
	@docker rm -f $$(docker ps -aq) || true
	@docker volume prune -f || true
	@docker network prune -f || true
	@docker system prune -f || true

stop: cleanup ## Stop Colima and clean up
	@colima stop

up: ssl-certs/nginx.crt ## Build and start all services with SSL
	@if ! grep -q "$(LOCAL_DOMAIN)" /etc/hosts; then \
		echo "127.0.0.1 $(LOCAL_DOMAIN)" | sudo tee -a /etc/hosts; \
	fi
	@echo "🚀 Starting services with SSL..."
	docker-compose up -d --build
	@echo "✅ Services should be ready"
	@echo "   Simple API (HTTPS): $(SIMPLE_API_ENDPOINT)"
	@echo "   Simple API (HTTP):  $(SIMPLE_API_HTTP_ENDPOINT)"
	@echo "   Swagger Docs:       $(SIMPLE_API_ENDPOINT)/docs"
	@echo "   Mock Cognito:       $(MOCK_COGNITO_ENDPOINT)"
	@echo "   Swagger Docs: $(SIMPLE_API_ENDPOINT)/docs"

down: ## Stop and remove all containers
	@echo "🛑 Stopping services..."
	docker-compose down
	@echo "✅ All services stopped"

destroy: down ## Stop and remove containers (alias for down)

run-local: ## Run services locally for development (deprecated - use run-unified-mock)
	@echo "🚀 Starting services locally for development..."
	@echo "   Mock Cognito will run on :8100"
	@echo "   Simple API will run on :8000 locally"
	@echo ""
	@echo "⚠️  DEPRECATED: Use 'make run-unified-mock' for the recommended unified API"
	@echo ""
	@echo "To run legacy services:"
	@echo "  Terminal 1: python mock_cognito.py"
	@echo "  Terminal 2: MOCK_COGNITO_URL=http://localhost:8100 python simple_api.py"
	@echo ""
	@echo "Then access:"
	@echo "  Mock Cognito: http://localhost:8100"
	@echo "  Simple API: http://localhost:8000"
	@echo "  Swagger: http://localhost:8000/docs"

run-unified-mock: ## Run unified API with Mock Cognito (RECOMMENDED)
	@echo "🚀 Starting Unified API with Mock Cognito..."
	@echo "   Mock Cognito will run on :8100"
	@echo "   Unified API will run on :8000"
	@echo ""
	@echo "To run unified services:"
	@echo "  Terminal 1: python mock_cognito.py"
	@echo "  Terminal 2: python simple_api_unified.py"
	@echo ""
	@echo "Then access:"
	@echo "  Mock Cognito: http://localhost:8100"
	@echo "  Unified API: http://localhost:8000"
	@echo "  Swagger: http://localhost:8000/docs"
	@echo ""
	@echo "Test with: make test-unified"

run-unified-aws: ## Run unified API with AWS Cognito
	@echo "🚀 Starting Unified API with AWS Cognito..."
	@echo "   ⚠️  Requires AWS configuration:"
	@echo "   export USER_POOL_ID=eu-central-1_xxxxxxxxx"
	@echo "   export APP_CLIENT_ID=xxxxxxxxxxxxxxxxxx"
	@echo "   export AWS_REGION=eu-central-1"
	@echo ""
	@echo "To run:"
	@echo "  python simple_api_unified.py --use-aws"
	@echo ""
	@echo "Then access:"
	@echo "  Unified API: http://localhost:8000"
	@echo "  Swagger: http://localhost:8000/docs"
	@echo ""
	@echo "Test with: make test-unified-aws"

rebuild: ## Force rebuild and restart all services
	@echo "🔄 Rebuilding services..."
	docker-compose down
	docker-compose up -d --build --force-recreate
	@echo "⏳ Waiting for services to be ready..."
	@sleep 10
	@echo "✅ Services rebuilt and ready"

setup: up ## Validate services are running and accessible
	@echo "🔧 Validating services..."
	@sleep 5  # Extra wait to ensure services are ready
	MOCK_COGNITO_ENDPOINT=$(MOCK_COGNITO_ENDPOINT) python test_cognito_setup.py
	@echo "✅ Service validation completed"

test: ## Run Mock Cognito API authentication tests
	@echo "🧪 Running Mock Cognito API tests..."
	python test_cognito_api.py
	@echo "✅ Mock Cognito tests completed"

test-api: ## Test Simple API endpoints with authentication
	@echo "🧪 Testing Simple API endpoints..."
	@echo "📍 Testing public endpoint..."
	@curl -s "$(SIMPLE_API_ENDPOINT)/public" | jq '.' || true
	@echo ""
	@echo "📍 Getting authentication token..."
	@TOKEN=$$(curl -s "$(MOCK_COGNITO_ENDPOINT)/auth/login" \
		-H "Content-Type: application/json" \
		-d '{"username":"testuser_contributor","password":"TempPass123!"}' | jq -r '.access_token') && \
	echo "📍 Testing authenticated endpoint (contributor)..." && \
	curl -s "$(SIMPLE_API_ENDPOINT)/contributor" -H "Authorization: Bearer $$TOKEN" | jq '.' || true
	@echo ""
	@echo "📍 Testing access control (should get 403)..." 
	@TOKEN=$$(curl -s "$(MOCK_COGNITO_ENDPOINT)/auth/login" \
		-H "Content-Type: application/json" \
		-d '{"username":"testuser_contributor","password":"TempPass123!"}' | jq -r '.access_token') && \
	curl -s -w "HTTP Status: %{http_code}\n" "$(SIMPLE_API_ENDPOINT)/partner" -H "Authorization: Bearer $$TOKEN" || true
	@echo ""
	@echo "✅ Simple API tests completed"

test-simple: ## Run comprehensive Simple API test suite (legacy)
	@echo "🧪 Running comprehensive Simple API tests (legacy)..."
	@echo "⚠️  DEPRECATED: Use 'make test-unified' for the recommended unified API tests"
	MOCK_COGNITO_ENDPOINT=$(MOCK_COGNITO_ENDPOINT) SIMPLE_API_ENDPOINT=$(SIMPLE_API_ENDPOINT) python test_simple_api.py
	@echo "✅ Comprehensive Simple API tests completed"

test-unified: ## Run unified API test suite with Mock Cognito (RECOMMENDED)
	@echo "🧪 Running Unified API tests with Mock Cognito..."
	python test_unified_api.py --api-url http://localhost:8000 --mock-cognito-url http://localhost:8100
	@echo "✅ Unified API tests completed"

test-unified-aws: ## Run unified API test suite with AWS Cognito
	@echo "🧪 Running Unified API tests with AWS Cognito..."
	@echo "⚠️  Requires AWS configuration and running API with --use-aws flag"
	python test_unified_api.py --api-url http://localhost:8000 --test-aws
	@echo "✅ Unified API AWS tests completed"

full-test: setup test test-api test-unified ## Complete workflow: setup + all tests (RECOMMENDED)
	@echo "🎯 Full spike test completed with unified API"

full-test-legacy: setup test test-api test-simple ## Complete workflow with legacy APIs
	@echo "🎯 Full spike test completed with legacy APIs"

check-mock-cognito: ## Check if Mock Cognito is running and healthy
	@echo "🔍 Checking Mock Cognito status..."
	@if curl -s $(MOCK_COGNITO_ENDPOINT)/health > /dev/null 2>&1; then \
		echo "✅ Mock Cognito is running at $(MOCK_COGNITO_ENDPOINT)"; \
		curl -s $(MOCK_COGNITO_ENDPOINT)/health | jq .; \
	else \
		echo "❌ Mock Cognito is not accessible at $(MOCK_COGNITO_ENDPOINT)"; \
		echo "   Run 'make up' to start Mock Cognito"; \
	fi

check-endpoints: ## Check if Mock Cognito endpoints are available
	@echo "🔍 Checking Mock Cognito endpoints..."
	@if curl -s $(MOCK_COGNITO_ENDPOINT)/ | jq -r '.endpoints' > /dev/null 2>&1; then \
		echo "✅ Mock Cognito endpoints are available:"; \
		curl -s $(MOCK_COGNITO_ENDPOINT)/ | jq '.endpoints'; \
	else \
		echo "❌ Mock Cognito endpoints are not available"; \
		echo "   Check service logs: make logs"; \
	fi

logs: ## Show Mock Cognito logs
	docker-compose logs -f

logs-mock: ## Show Mock Cognito logs (alias)
	docker-compose logs -f mock-cognito

status: ## Show overall spike status
	@echo "📊 Mock Cognito Spike Status"
	@echo "==============================="
	@make check-mock-cognito
	@echo ""
	@make check-endpoints
	@echo ""

# AWS Cognito deployment and testing targets
aws-prerequisites: ## Check AWS prerequisites for deployment
	@echo "🔍 Checking AWS prerequisites..."
	@./deploy-cognito.sh check

aws-deploy: ## Deploy AWS Cognito infrastructure to eu-central-1
	@echo "🚀 Deploying AWS Cognito infrastructure..."
	@./deploy-cognito.sh deploy

aws-status: ## Check AWS Cognito deployment status
	@echo "📊 Checking AWS Cognito deployment status..."
	@./deploy-cognito.sh status


aws-cleanup: ## Delete AWS Cognito CloudFormation stack
	@echo "🗑️ Cleaning up AWS Cognito infrastructure..."
	@./deploy-cognito.sh cleanup

aws-test: ## Test AWS Cognito authentication and API
	@echo "🧪 Testing AWS Cognito authentication..."
	python test_aws_cognito.py

aws-api: ## Run Simple API with AWS Cognito (port 8000)
	@echo "🚀 Starting Simple API with AWS Cognito..."
	@echo "   API will run at: http://localhost:8000"
	@echo "   Swagger docs: http://localhost:8000/docs"
	python simple_api_aws.py

aws-full-test: aws-deploy aws-config aws-test ## Complete AWS workflow: deploy + configure + test
	@echo "🎯 AWS Cognito deployment and testing completed"

help: ## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "\033[33mQuick Start (Mock Cognito):\033[0m"
	@echo "  make start              # Start Colima"
	@echo "  make full-test          # Complete spike: Mock Cognito + setup + test (unified API)"
	@echo "  make status             # Check overall status"
	@echo "  make stop               # Stop everything and cleanup"
	@echo ""
	@echo "\033[33mUnified API Workflow (RECOMMENDED):\033[0m"
	@echo "  make run-unified-mock   # Run unified API with Mock Cognito"
	@echo "  make run-unified-aws    # Run unified API with AWS Cognito"
	@echo "  make test-unified       # Test unified API with Mock Cognito"
	@echo "  make test-unified-aws   # Test unified API with AWS Cognito"
	@echo ""
	@echo "\033[33mDevelopment Workflow (Mock):\033[0m"
	@echo "  make up                 # Start Mock Cognito only"
	@echo "  make setup              # Validate Mock Cognito service"
	@echo "  make test               # Run authentication tests"
	@echo "  make reset              # Clean slate restart"
	@echo ""
	@echo "\033[33mAWS Cognito Workflow:\033[0m"
	@echo "  make aws-prerequisites  # Check AWS CLI and credentials"
	@echo "  make aws-full-test      # Deploy + configure + test AWS Cognito"
	@echo "  make aws-api            # Run Simple API with AWS Cognito"
	@echo "  make aws-cleanup        # Delete AWS infrastructure"
	@echo ""
	@echo "\033[33mMock Cognito Endpoints:\033[0m"
	@echo "  Mock Cognito API: $(MOCK_COGNITO_ENDPOINT)"
	@echo "  Health Check:     $(MOCK_COGNITO_ENDPOINT)/health"
	@echo "  Login:            $(MOCK_COGNITO_ENDPOINT)/auth/login"
	@echo "  Configuration:    $(MOCK_COGNITO_ENDPOINT)/config"
	@echo ""
	@echo "\033[33mDocker Endpoints:\033[0m"
	@echo "   Simple API (HTTPS): $(SIMPLE_API_ENDPOINT)"
	@echo "   Simple API (HTTP):  $(SIMPLE_API_HTTP_ENDPOINT)"
	@echo "   Swagger Docs:       $(SIMPLE_API_ENDPOINT)/docs"
	@echo "   Mock Cognito:       $(MOCK_COGNITO_ENDPOINT)"
	@echo ""
