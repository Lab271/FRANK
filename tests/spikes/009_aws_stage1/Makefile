start: ## Start Colima if not already running
	@colima start
	@colima status

stop: ## Stop Colima
	@colima stop
	
build: ## Build and run the Docker container (native platform)
	@docker stop simple_testsimple_api || true
	@docker rm simple_testsimple_api || true
	@docker build -t simple_api .
	@docker run -d -p 8000:8000 --name simple_test simple_api

build-aws: ## Build for AWS Fargate (AMD64)
	docker build --platform linux/amd64 -t simple_api:amd64 .

build-arm: ## Build for ARM64 explicitly  
	docker build --platform linux/arm64 -t simple_api:arm64 .	

call_root: ## Call the root endpoint
	@curl -s http://localhost:8000/ | jq .

call_health: ## Call the health endpoint
	@curl -s http://localhost:8000/v1/health | jq .

run_local: ## Run the application locally
	uvicorn simple_api:app --host 0.0.0.0 --port 8000

help: ## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""