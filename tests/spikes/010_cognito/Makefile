# ==============================================================================
# FRANK Platform - Cognito Authentication Spike - Build and Test Automation
# ==============================================================================
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0
#
# This spike tests authentication patterns using Mock Cognito service and Simple API:
#
# 1. Mock Cognito service: FastAPI-based authentication service
#    - Docker internal:8100, External:8100
#
# 2. Simple API service: Role-based access control demo (Multiple variants)
#    - simple_api_010.py:8000 
#    - Docker internal: :8000, External via nginx: :443 (HTTPS), :80 (HTTP)
#    - Swagger: https://frank-010-cognito.local/docs
#
# ==============================================================================

LOCAL_DOMAIN = frank-010-cognito.local
SIMPLE_API_ENDPOINT = https://$(LOCAL_DOMAIN)
SIMPLE_API_HTTP_ENDPOINT = http://localhost:8080
MOCK_COGNITO_ENDPOINT = http://localhost:8100

.PHONY: help start ssl-certs clean stop up down destroy rebuild test integration logs logs-mock logs-api

start: ## Start Colima if not already running
	@colima start
	@colima status

ssl-certs/nginx.crt: 
	@if ! grep -q "$(LOCAL_DOMAIN)" /etc/hosts; then \
		echo "127.0.0.1 $(LOCAL_DOMAIN)" | sudo tee -a /etc/hosts; \
	fi
	@mkdir -p ssl-certs
	@mkcert -key-file ssl-certs/nginx.key -cert-file ssl-certs/nginx.crt $(LOCAL_DOMAIN)

clean: ## Clean up docker
	@docker rm -f $$(docker ps -aq) || true
	@docker volume prune -f || true
	@docker network prune -f || true
	@docker system prune -f || true

stop: clean ## Stop Colima and clean up
	@colima stop

up: ssl-certs/nginx.crt ## Build and start all services with SSL
	@echo "🚀 Starting services with SSL..."
	docker-compose up -d --build
	@echo "✅ Services should be ready"
	@echo "   Simple API (HTTPS): $(SIMPLE_API_ENDPOINT)"
	@echo "   Simple API (HTTP):  $(SIMPLE_API_HTTP_ENDPOINT)"
	@echo "   Swagger Docs:       $(SIMPLE_API_ENDPOINT)/docs"
	@echo "   Mock Cognito:       $(MOCK_COGNITO_ENDPOINT)"
	@echo "   Swagger Docs:       $(SIMPLE_API_ENDPOINT)/docs"

down: ## Stop and remove all containers
	@echo "🛑 Stopping services..."
	docker-compose down

destroy: down ## Stop and remove containers (alias for down)

rebuild: ## Force rebuild and restart all services
	@echo "🔄 Rebuilding services..."
	docker-compose down
	docker-compose up -d --build --force-recreate

test: ## Run Mock Cognito API authentication tests
	@coverage run -m pytest
	@coverage report -m 

integration: up ## Run integration tests simulating external calls to docker
	@echo "🧪 Running integration tests..."
	@./test_mock_cognito_local.sh > /dev/null 2>&1 && echo "✅ Mock Cognito tests completed" || (echo "❌ Mock Cognito tests failed"; exit 1)
	@./test_simple_api_010_local.sh 8080 > /dev/null 2>&1 && echo "✅ Simple API tests completed" || (echo "❌ Simple API tests failed"; exit 1)
	@echo "✅ Integration tests completed"

logs: ## Show Mock Cognito logs
	docker-compose logs -f

logs-mock: ## Show Mock Cognito logs (alias)
	docker-compose logs -f mock-cognito

logs-api: ## Show Simple API logs
	docker-compose logs -f simple-api

###################################################################
# Old stuff
###################################################################

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


aws-full-test: aws-deploy aws-config aws-test ## Complete AWS workflow: deploy + configure + test
	@echo "🎯 AWS Cognito deployment and testing completed"

help: ## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
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
