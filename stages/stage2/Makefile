# FRANK Platform - Setup Script

# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0
# ================================
# Makefile - Development Commands
# ================================
.PHONY: help setup up up-simple down logs test clean lint

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup:  ## Initial setup - create directories and set permissions
	mkdir -p localstack_data logs
	chmod +x localstack_init/*.sh
	cp .env.stage2 .env

build-simple: ## Build application container - simple
	docker-compose -f docker-compose.simple.yml build

build:  ## Build application container - hybrid
	docker-compose -f docker-compose.hybrid.yml build frank-app


up:  ## Start all services
	docker-compose -f docker-compose.mysql.yml up -d
	@echo "Waiting for services to be ready..."
	@echo "Services started:"
	@echo "- FRANK API: http://localhost:8000"
	@echo "- Adminer (RDS): http://localhost:8080"
	@echo "- DynamoDB Admin: http://localhost:8081"
	@echo "- LocalStack: http://localhost:4566"

up-hybrid:  ## Start all services
	docker-compose -f docker-compose.hybrid.yml up -d
	@echo "Waiting for services to be ready..."
	@echo "Services started:"
	@echo "- FRANK API: http://localhost:8000"
	@echo "- Adminer (RDS): http://localhost:8080"
	@echo "- DynamoDB Admin: http://localhost:8001"
	@echo "- LocalStack: http://localhost:4566"

up-simple:  ## Start all services simple
	docker-compose -f docker-compose.simple.yml up -d
	@echo "Waiting for services to be ready..."
	@echo "Services started:"
	@echo "- FRANK API: http://localhost:8000"
	@echo "- Adminer (RDS): http://localhost:8080"
	@echo "- MySQL: http://localhost:4566"

down:  ## Stop all services
	docker-compose --file docker-compose.simple.yml down
	docker-compose down

restart:  ## Restart all services
	docker-compose -f docker-compose.simple.yml down
	docker-compose down
	docker-compose up -d

logs:  ## Show logs from all services
	docker-compose --file docker-compose.hybrid.yml logs -f

logs-app:  ## Show logs from FRANK app only
	docker-compose --file docker-compose.hybrid.yml logs -f frank-app

logs-localstack:  ## Show logs from LocalStack only
	docker-compose --file docker-compose.hybrid.yml logs -f localstack

test:  ## Run tests
	docker-compose exec frank-app python -m pytest tests/ -v

test-api:  ## Test API endpoints
	@echo "Testing health endpoint..."
	curl -s http://localhost:8000/v1/health | python -m json.tool
	@echo "\nTesting root endpoint..."
	curl -s http://localhost:8000/ | python -m json.tool

test-submission:  ## Submit a test threat intelligence submission
	curl -s -X POST "http://localhost:8000/v1/submission" \
		-H "Content-Type: application/json" \
		-H "Authorization: Bearer core_test_token" \
		-d '{ \
			"submission": { \
				"submitter": { \
					"organization_id": "identity-f431f809-377b-45e0-aa1c-6a4751cae5ff", \
					"tier": "partner" \
				}, \
				"sighting": { \
					"sighting_id": "sighting-ee20065d-2555-424f-ad9e-0f8428623c75", \
					"timestamp": "2025-01-20T14:30:22Z", \
					"confidence": 87, \
					"observables": { \
						"network": [ \
							{ \
								"id": "ipv4-addr-c4e54321-1234-5678-9abc-def012345678", \
								"type": "ipv4", \
								"value": "185.220.102.45" \
							}, \
							{ \
								"id": "domain-name-d5f65432-2345-6789-abcd-ef0123456789", \
								"type": "domain", \
								"value": "secure-bank-verify.nl" \
							} \
						] \
					} \
				} \
			} \
		}' | python -m json.tool

clean:  ## Clean up containers and volumes
	docker-compose down -v
	docker system prune -f
	rm -rf localstack_data logs mysql_init
	rm -f .env


shell:  ## Open shell in application container
	docker-compose exec frank-app bash

db-inspect-rds:  ## Inspect RDS database
	@echo "Connect to Adminer at http://localhost:8080"
	@echo "Server: localstack:4566"
	@echo "Username: frank_user"
	@echo "Password: frank_pass"
	@echo "Database: frank"

db-inspect-dynamo:  ## Inspect DynamoDB
	@echo "DynamoDB Admin at http://localhost:8001"
	@echo "Or use AWS CLI:"
	@echo "aws --endpoint-url=http://localhost:4566 dynamodb scan --table-name frank-data"

# Advanced operations
migrate-test:  ## Test data migration between databases
	@echo "Testing data migration..."
	curl -X POST "http://localhost:8000/v1/test/generate-sample-data?count=3"
	@echo "\nChecking data in both databases..."
	curl -s "http://localhost:8000/v1/organizations/test-org/submissions?database=dynamodb" | python -m json.tool
	curl -s "http://localhost:8000/v1/organizations/test-org/submissions?database=rds" | python -m json.tool

benchmark:  ## Run performance benchmark
	@echo "Running performance benchmark..."
	curl -X POST "http://localhost:8000/v1/test/generate-sample-data?count=50"
	sleep 2
	curl -s "http://localhost:8000/v1/performance" | python -m json.tool

status:  ## Show service status
	@echo "Docker containers:"
	@docker-compose -f docker-compose.simple.yml ps
	@echo "\nService health:"
	@curl -s http://localhost:8000/v1/health | python -c "import sys, json; data=json.load(sys.stdin); print(f\"Overall: {data['status']}\"); [print(f\"{db}: {info['status']}\") for db, info in data['databases'].items()]" 2>/dev/null || echo "API not responding"
