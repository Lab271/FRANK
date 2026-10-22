# ==============================================================================
# FRANK Stage 2 - Multiple Deployment Options
# ==============================================================================
# Three different ways to run the application:
#
# 1. docker-compose: Load balancer setup (nginx on :80 -> simple-api on :8000)
#    - Access via: http://localhost:80 (mirrors AWS ALB architecture)
#    - Use: make up / make rebuild
#
# 2. docker-simple: Direct container access on :8008
#    - Access via: http://localhost:8008 (simple single container)
#    - Use: make up-simple
#
# 3. run_local: Python development server on :8080
#    - Access via: http://localhost:8080 (direct uvicorn)
#    - Use: make run_local
# ==============================================================================

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
	
up-simple: ## Build and run the Docker container (native platform)
	@docker stop simple_test || true
	@docker rm simple_test || true
	@docker build -t simple_api .
	@docker run -d -p 8008:8000 --name simple_test simple_api

build:  ## Build application container
	docker-compose -f docker-compose.yml up simple-api --build -d

up:  ## Build and start application containers
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
	@echo "  docker-simple:  Direct container on :8008 (make up-simple)"
	@echo "  run_local:      Python dev server on :8080 (make run_local)"
	@echo ""