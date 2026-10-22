# ==============================================================================
# FRANK Stage 5 - DynamoDB + Multi-Container Setup
# ==============================================================================
# Configuration
# Three different ways to run the application:
#
# 1. docker-compose: Load balancer setup (nginx on :80/:443 -> 2x simple-api)
#    - HTTP: http://localhost:80 (redirects to HTTPS)
#    - HTTPS: https://frank-stage5.local:443 (mirrors AWS ALB architecture)
#    - Use: make up / make rebuild
#
# 2. direct containers: Access containers directly for testing
#    - simple-api-1: http://localhost:8000
#    - simple-api-2: http://localhost:8001
#
# 3. run_local: Python development server on :8080
#    - Access via: http://localhost:8080 (direct uvicorn)
#    - Use: make run_local (assumes DynamoDB Local is running)
# ==============================================================================

LOCAL_DOMAIN = frank-stage5.local

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

build: ## Build application containers
	docker-compose -f docker-compose.yml up simple-api-1 simple-api-2 --build -d

rebuild: ## Force rebuild without cache and restart
	docker-compose -f docker-compose.yml build --no-cache simple-api-1 simple-api-2
	docker-compose -f docker-compose.yml up -d

build-and-tag: ## Build with docker-compose and tag for registry
	docker-compose -f docker-compose.yml build simple-api-1 simple-api-2
	docker tag $$(docker-compose images -q simple-api-1) simple-api:latest
	@echo "Image tagged as simple-api:latest"

build-for-registry: ## Build and tag for local registry
	docker-compose -f docker-compose.yml build simple-api-1 simple-api-2
	docker tag $$(docker-compose images -q simple-api-1) localhost:5000/simple-api:latest
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
	@cd ../../.. && docker buildx build --platform linux/amd64 -f tests/spikes/013_aws_observability/Dockerfile -t simple_api:amd64 .

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

logs-app1:  ## Show logs from FRANK app 1 only
	docker-compose --file docker-compose.yml logs -f simple-api-1

logs-app2:  ## Show logs from FRANK app 2 only
	docker-compose --file docker-compose.yml logs -f simple-api-2

# ==============================================================================
# Load Balancing and Horizontal Scaling Tests
# ==============================================================================

test-lb: ## Test load balancing - shows which container serves each request
	@echo "🔄 Testing load balancing across containers..."
	@echo "Making 10 requests to see container distribution:"
	@for i in {1..10}; do \
		echo -n "Request $$i: "; \
		curl -s http://localhost/ | jq -r '.container_id // .hostname // "unknown"'; \
		sleep 0.1; \
	done

test-lb-ssl: ## Test load balancing via HTTPS
	@echo "🔄 Testing HTTPS load balancing across containers..."
	@echo "Making 10 requests to see container distribution:"
	@for i in {1..10}; do \
		echo -n "Request $$i: "; \
		curl -sk https://$(LOCAL_DOMAIN)/ | jq -r '.container_id // .hostname // "unknown"'; \
		sleep 0.1; \
	done

test-health-lb: ## Test health endpoint load balancing
	@echo "🏥 Testing health endpoint load balancing..."
	@for i in {1..5}; do \
		echo -n "Health $$i: "; \
		curl -s http://localhost/health | jq -r '.container_id // .hostname // "unknown"'; \
		sleep 0.1; \
	done

test-direct: ## Test direct container access
	@echo "🎯 Testing direct container access..."
	@echo -n "Container 1 (port 8000): "; \
	curl -s http://localhost:8000/ | jq -r '.container_id // .hostname // "unknown"'
	@echo -n "Container 2 (port 8001): "; \
	curl -s http://localhost:8001/ | jq -r '.container_id // .hostname // "unknown"'

test-upstream-headers: ## Test nginx upstream headers
	@echo "🔍 Testing nginx upstream headers..."
	@curl -s -I http://localhost/lb-status | grep -E "(X-Upstream|X-Response)"

load-test: ## Simple load test to trigger scaling behavior
	@echo "🚀 Running simple load test..."
	@echo "Sending 100 requests over 10 seconds..."
	@for i in {1..100}; do \
		curl -s http://localhost/ > /dev/null & \
		if [ $$((i % 10)) -eq 0 ]; then echo "Sent $$i requests..."; fi; \
		sleep 0.1; \
	done; \
	wait; \
	echo "✅ Load test complete"

monitor-containers: ## Monitor container resource usage
	@echo "📊 Monitoring container resource usage..."
	@docker stats frank-api-1 frank-api-2 --no-trunc --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

scale-up: ## Scale up to 3 containers (simulates auto-scaling)
	@echo "📈 Scaling up to 3 containers..."
	@docker-compose up -d --scale simple-api-1=2 simple-api-2=1
	@echo "✅ Scaled up - check with 'make test-lb'"

scale-down: ## Scale back down to 2 containers
	@echo "📉 Scaling down to 2 containers..."
	@docker-compose up -d --scale simple-api-1=1 simple-api-2=1
	@echo "✅ Scaled down - check with 'make test-lb'"

failover-test: ## Test failover by stopping one container
	@echo "🛑 Testing failover - stopping container 1..."
	@docker-compose stop simple-api-1
	@echo "Testing with container 1 down:"
	@make test-lb
	@echo "🔄 Restarting container 1..."
	@docker-compose start simple-api-1
	@sleep 5
	@echo "Testing after restart:"
	@make test-lb

help: ## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "\033[33mDeployment Options:\033[0m"
	@echo "  docker-compose: Load balancer on :80/:443 -> 2x simple-api containers (make up)"
	@echo "  direct access:  Container 1 on :8000, Container 2 on :8001"
	@echo "  run_local:      Python dev server on :8080 (make run_local)"
	@echo "  SSL endpoints:  https://$(LOCAL_DOMAIN) (make call_root_ssl)"
	@echo "  DynamoDB Admin: http://localhost:8100 (minimal-dynamodb-admin)"
	@echo ""
	@echo "\033[33mHorizontal Scaling Tests:\033[0m"
	@echo "  make test-lb           # Test load balancing distribution"
	@echo "  make test-direct       # Test direct container access"
	@echo "  make load-test         # Simple load testing"
	@echo "  make monitor-containers # Monitor resource usage"
	@echo "  make failover-test     # Test container failover"
	@echo ""