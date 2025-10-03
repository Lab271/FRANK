# ==============================================================================
# FRANK Stage 4 - GCP Deployment
# ==============================================================================

start:	## Start Colima if not already running
	@colima start
	@colima status

cleanup:	## Clean up docker
	@docker rm -f $(docker ps -aq) || true
	@docker volume prune -f || true
	@docker network prune -f || true
	@docker system prune -f || true

stop:	cleanup ## Stop Colima and clean up
	@colima stop

build:	## Build application container
	docker-compose up simple-api --build -d

up:	## Build and start application containers
	docker-compose up --build -d

rebuild:	## Force rebuild without cache and restart
	docker-compose build --no-cache simple-api
	docker-compose up -d

build-and-tag:	## Build with docker-compose and tag for registry
	docker-compose build simple-api
	docker tag $(docker-compose images -q simple-api) simple-api:latest
	@echo "Image tagged as simple-api:latest"

destroy:	## Stop and remove the Docker container
	@docker-compose down

build-gcp:	## Build for GCP Cloud Run (AMD64)
	docker buildx build --platform linux/amd64 -t simple_api:amd64 .

call_root:	## Call the root endpoint
	@curl -s http://localhost:8080/ | jq .

call_health:	## Call the health endpoint
	@curl -s http://localhost:8080/v1/health | jq .

run_local:	## Run the application locally
	uvicorn simple_api:app --host 0.0.0.0 --port 8000

logs:	## Show logs from all services
	docker-compose logs -f

logs-app:	## Show logs from FRANK app only
	docker-compose logs -f simple-api

deploy:	## Deploy to GCP
	@bash deploy.sh deploy

destroy-cloud:	## Destroy from GCP
	@bash deploy.sh destroy

help:	## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
