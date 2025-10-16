# FRANK Platform - Setup Script

# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0
# ================================
# Makefile - Development Commands
# ================================
LOCAL_DOMAIN = frank-stage3.local

.PHONY: help


help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'	

# ================================
# AWS setup
# ================================

aws-create: ## Create AWS Deployment
	@ansible-playbook ansible/playbook.yml --tags create

aws-destroy: ## Destroy AWS Deployment
	@ansible-playbook ansible/playbook.yml --tags destroy

aws-deploy: ## Deploy AWS Docker with new build
	@ansible-playbook ansible/playbook.yml --tags docker

# ================================
# SETUP
# ================================

start: ## Start Colima if not already running
	@colima start
	@colima status

cleanup: ## Clean up docker
	@docker images | grep "localhost:" | awk '{print $$3}' | xargs docker rmi -f || true
	@docker rm -f $$(docker ps -aq) || true
	@docker rmi -f $$(docker images -aq) || true
	@docker volume prune -f || true
	@docker network prune -f || true
	@docker system prune -a -f --volumes|| true

stop: cleanup ## Stop Colima and clean up
	@colima stop

# ================================
# Local Development
# ================================
up: ssl-certs/nginx.crt ## Build and start application containers
	docker-compose -f local/docker-compose.yml up --build -d

down: ## Stop application containers
	docker-compose -f local/docker-compose.yml down

build: ## Build application container
	docker-compose -f local/docker-compose.yml up frank-app-1 frank-app-2 --build -d

rebuild: ## Rebuild application container
	docker-compose -f local/docker-compose.yml up frank-app-1 frank-app-2 --build -d --force-recreate

health: ## Check health of all services
	@echo "🔍 Checking health of services..."
	@curl -s "https://$(LOCAL_DOMAIN)/v1/health" > /dev/null 2>&1 && echo "✅ Simple API health check passed" || echo "❌ Simple API health check failed"	

logs: ## Show logs
	docker-compose -f local/docker-compose.yml logs -f

create-tables: ## Create DynamoDB tables (matching CloudFormation)
	@aws dynamodb create-table \
		--table-name frank-data \
		--attribute-definitions \
			AttributeName=PK,AttributeType=S \
			AttributeName=SK,AttributeType=S \
			AttributeName=GSI1PK,AttributeType=S \
			AttributeName=GSI1SK,AttributeType=S \
		--key-schema \
			AttributeName=PK,KeyType=HASH \
			AttributeName=SK,KeyType=RANGE \
		--global-secondary-indexes \
			IndexName=GSI1,KeySchema='[{AttributeName=GSI1PK,KeyType=HASH},{AttributeName=GSI1SK,KeyType=RANGE}]',Projection='{ProjectionType=ALL}' \
		--billing-mode PAY_PER_REQUEST \
		--stream-specification StreamEnabled=true,StreamViewType=NEW_AND_OLD_IMAGES \
		--endpoint-url http://localhost:4566 \
		--region eu-west-1 \
		--profile localstack \
		--no-cli-pager || echo "Main table already exists"
	@aws dynamodb create-table \
		--table-name frank-audit \
		--attribute-definitions \
			AttributeName=PK,AttributeType=S \
			AttributeName=SK,AttributeType=S \
			AttributeName=GSI1PK,AttributeType=S \
			AttributeName=GSI1SK,AttributeType=S \
		--key-schema \
			AttributeName=PK,KeyType=HASH \
			AttributeName=SK,KeyType=RANGE \
		--global-secondary-indexes \
			IndexName=GSI1,KeySchema='[{AttributeName=GSI1PK,KeyType=HASH},{AttributeName=GSI1SK,KeyType=RANGE}]',Projection='{ProjectionType=ALL}' \
		--billing-mode PAY_PER_REQUEST \
		--endpoint-url http://localhost:4566 \
		--region eu-west-1 \
		--profile localstack \
		--no-cli-pager || echo "Audit table already exists"

ssl-certs/nginx.crt: # Create self-signed SSL certificates
	@if ! grep -q "$(LOCAL_DOMAIN)" /etc/hosts; then \
		echo "127.0.0.1 $(LOCAL_DOMAIN)" | sudo tee -a /etc/hosts; \
	fi
	@mkdir -p ssl-certs
	@mkcert -key-file ssl-certs/nginx.key -cert-file ssl-certs/nginx.crt \
		$(LOCAL_DOMAIN) \
		localhost \
		127.0.0.1 \
		*.$(LOCAL_DOMAIN)
