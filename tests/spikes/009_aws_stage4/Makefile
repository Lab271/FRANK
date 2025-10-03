# ==============================================================================
# FRANK Stage 3 - SSL/HTTPS Setup
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
	
ssl-certs/nginx.crt: ~/.ssl-certs/ca.crt
	@mkdir -p ssl-certs
	@mkcert -key-file ssl-certs/nginx.key -cert-file ssl-certs/nginx.crt $(LOCAL_DOMAIN)

build: ## Build application container
	docker-compose -f docker-compose.yml up simple-api --build -d

up: ssl-certs/nginx.crt ## Build and start application containers
	@if ! grep -q "$(LOCAL_DOMAIN)" /etc/hosts; then \
		echo "127.0.0.1 $(LOCAL_DOMAIN)" | sudo tee -a /etc/hosts; \
	fi
	docker-compose -f docker-compose.yml up --build -d

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

destroy: ## Stop and remove the Docker container
	@docker-compose -f docker-compose.yml down

build-aws: ## Build for AWS Fargate (AMD64)
	docker buildx build --platform linux/amd64 -t simple_api:amd64 .

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