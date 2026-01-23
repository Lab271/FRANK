# ==============================================================================
# FRANK Stage 4 - DynamoDB and SSL
# ==============================================================================
# Configuration
# Two different ways to run the application:
#
# 1. docker-compose: Load balancer setup (nginx on :80 -> simple-api on :8000)
#    - Access via: http://localhost:80 (mirrors AWS ALB architecture)
#    - Use: make up / make rebuild
#
# 2. run_local: Python development server on :8080
#    - Access via: http://localhost:8080 (direct uvicorn)
#    - Use: make run_local
# ==============================================================================

LOCAL_DOMAIN = frank-stage4.local

up: ssl-certs/nginx.crt ## Build and start application containers
	@if ! grep -q "$(LOCAL_DOMAIN)" /etc/hosts; then \
		echo "127.0.0.1 $(LOCAL_DOMAIN)" | sudo tee -a /etc/hosts; \
	fi
	docker-compose -f docker-compose.yml up --build -d

create-tables: ## Create DynamoDB tables locally (matching CloudFormation)
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
	
ssl-certs/nginx.crt: # Create self-signed SSL certificates
	@mkdir -p ssl-certs
	@mkcert -key-file ssl-certs/nginx.key -cert-file ssl-certs/nginx.crt \
		$(LOCAL_DOMAIN) \
		localhost \
		127.0.0.1 \
		*.$(LOCAL_DOMAIN)

build: ## Build application container
	docker-compose -f docker-compose.yml up simple-api --build -d

rebuild: ## Force rebuild without cache and restart
	docker-compose -f docker-compose.yml build --no-cache simple-api
	docker-compose -f docker-compose.yml up -d

build-and-tag: ## Build with docker-compose and tag for registry
	docker-compose -f docker-compose.yml build simple-api
	docker tag $$(docker-compose images -q simple-api) simple-api:latest
	@echo "Image tagged as simple-api:latest"

build-for-registry: ## Build and tag for local registry
	docker-compose -f docker-compose.yml build simple-api
	docker tag $$(docker-compose images -q simple-api) localhost:5000/simple-api:latest
	@echo "Image ready for push: localhost:5000/simple-api:latest"

down: ## Stop and remove the Docker container
	@docker-compose -f docker-compose.yml down

list-tables: ## List DynamoDB tables in LocalStack
	@echo "DynamoDB tables in LocalStack:"
	@aws dynamodb list-tables --endpoint-url http://localhost:4566 --region eu-west-1 --no-cli-pager || echo "LocalStack not running"

describe-tables: ## Describe DynamoDB table schemas
	@echo "Main table schema:"
	@aws dynamodb describe-table --table-name frank-009-stage4-data --endpoint-url http://localhost:4566 --region eu-west-1 --no-cli-pager || echo "Table not found"
	@echo "\nAudit table schema:"
	@aws dynamodb describe-table --table-name frank-009-stage4-audit --endpoint-url http://localhost:4566 --region eu-west-1 --no-cli-pager || echo "Table not found"

clean-tables: ## Delete DynamoDB tables from LocalStack
	@aws dynamodb delete-table --table-name frank-009-stage4-data --endpoint-url http://localhost:4566 --region eu-west-1 --no-cli-pager || echo "Main table not found"
	@aws dynamodb delete-table --table-name frank-009-stage4-audit --endpoint-url http://localhost:4566 --region eu-west-1 --no-cli-pager || echo "Audit table not found"
	@echo "Tables deleted"

build-aws: ## Build for AWS Fargate (AMD64)
	@cd ../../.. && docker buildx build --platform linux/amd64 -f tests/spikes/012_aws_dynamodb/Dockerfile -t simple_api:amd64 .

call_root: ## Call the root endpoint
	@curl -s http://localhost:80/ | jq .

call_health: ## Call the health endpoint
	@curl -s http://localhost:80/v1/health | jq .

call_root_ssl: ## Call the root endpoint via HTTPS
	@curl -s https://$(LOCAL_DOMAIN)/ | jq .

call_health_ssl: ## Call the health endpoint via HTTPS
	@curl -s https://$(LOCAL_DOMAIN)/v1/health | jq .

run_local: ## Run the application locally
	uvicorn simple_api:app --host 0.0.0.0 --port 8080

logs:  ## Show logs from all services
	docker-compose --file docker-compose.yml logs -f

logs-app:  ## Show logs from FRANK app only
	docker-compose --file docker-compose.yml logs -f simple-api

help: ## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "\033[33mDeployment Options:\033[0m"
	@echo "  docker-compose: Load balancer on :80 -> simple-api on :8000 (make up)"
	@echo "  run_local:      Python dev server on :8080 (make run_local)"
	@echo "  SSL endpoints:  https://$(LOCAL_DOMAIN) (make call_root_ssl)"
	@echo ""