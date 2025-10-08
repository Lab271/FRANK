# ==============================================================================
# FRANK Platform - Cognito Authentication Spike - Build and Test Automation
# ==============================================================================
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0
#
# This spike tests authentication patterns using a Mock Cognito service:
#
# 1. Mock Cognito service: FastAPI-based authentication service on :8080
#    - Access via: http://localhost:8080 (Mock Cognito API endpoint)
#    - Use: make up / make setup / make test
#
# 2. Python test execution: Direct test runner
#    - Setup: make setup (validates mock service is running)
#    - Test: make test (runs authentication and API tests)
# ==============================================================================

MOCK_COGNITO_ENDPOINT = http://localhost:8080

start: ## Start Colima if not already running
	@colima start
	@colima status

cleanup: ## Clean up docker
	@docker rm -f $$(docker ps -aq) || true
	@docker volume prune -f || true
	@docker network prune -f || true
	@docker system prune -f || true

stop: cleanup ## Stop Colima and clean up
	@colima stop

up: ## Start Mock Cognito service
	@echo "🚀 Starting Mock Cognito service..."
	docker-compose up -d
	@echo "⏳ Waiting for Mock Cognito to be ready..."
	@sleep 10
	@echo "✅ Mock Cognito should be ready at $(MOCK_COGNITO_ENDPOINT)"

down: ## Stop and remove Mock Cognito containers
	@echo "🛑 Stopping Mock Cognito..."
	docker-compose down
	@echo "✅ Mock Cognito stopped"

destroy: down ## Stop and remove containers (alias for down)

rebuild: ## Force rebuild and restart Mock Cognito
	@echo "🔄 Rebuilding Mock Cognito..."
	docker-compose down
	docker-compose up -d --build --force-recreate
	@echo "⏳ Waiting for Mock Cognito to be ready..."
	@sleep 10
	@echo "✅ Mock Cognito rebuilt and ready"

setup: up ## Validate Mock Cognito service is running and accessible
	@echo "🔧 Validating Mock Cognito service..."
	@sleep 5  # Extra wait to ensure service is ready
	python test_cognito_setup.py
	@echo "✅ Mock Cognito validation completed"

test: ## Run Mock Cognito API authentication tests
	@echo "🧪 Running Mock Cognito API tests..."
	python test_cognito_api.py
	@echo "✅ Mock Cognito tests completed"

full-test: setup test ## Complete workflow: setup + test
	@echo "🎯 Full Mock Cognito spike test completed"

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

validate-config: ## Validate cognito_config.json exists and is valid
	@if [ ! -f cognito_config.json ]; then \
		echo "❌ cognito_config.json not found. Run 'make setup' first."; \
		exit 1; \
	fi
	@echo "✅ Configuration file found:"
	@python -c "import json; config=json.load(open('cognito_config.json')); print(f'  User Pool ID: {config[\"user_pool_id\"]}'); print(f'  Client ID: {config[\"client_id\"]}'); print(f'  Test Users: {len(config[\"test_users\"])}')"

clean-config: ## Remove generated configuration files
	@echo "🧹 Cleaning configuration files..."
	@rm -f cognito_config.json
	@echo "✅ Configuration files removed"

reset: down clean-config ## Full reset: stop containers and clean config
	@echo "🔄 Full reset completed"

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
	@if [ -f cognito_config.json ]; then \
		echo "📄 Configuration: ✅ Ready"; \
		make validate-config; \
	else \
		echo "📄 Configuration: ❌ Missing (run 'make setup')"; \
	fi

help: ## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "\033[33mQuick Start:\033[0m"
	@echo "  make start        # Start Colima"
	@echo "  make full-test    # Complete spike: Mock Cognito + setup + test"
	@echo "  make status       # Check overall status"
	@echo "  make stop         # Stop everything and cleanup"
	@echo ""
	@echo "\033[33mDevelopment Workflow:\033[0m"
	@echo "  make up           # Start Mock Cognito only"
	@echo "  make setup        # Validate Mock Cognito service"
	@echo "  make test         # Run authentication tests"
	@echo "  make reset        # Clean slate restart"
	@echo ""
	@echo "\033[33mEndpoints:\033[0m"
	@echo "  Mock Cognito API: $(MOCK_COGNITO_ENDPOINT)"
	@echo "  Health Check:     $(MOCK_COGNITO_ENDPOINT)/health"
	@echo "  Login:            $(MOCK_COGNITO_ENDPOINT)/auth/login"
	@echo "  Configuration:    $(MOCK_COGNITO_ENDPOINT)/config"
	@echo ""
