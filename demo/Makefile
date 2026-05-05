# FRANK Demo — Makefile
#
# Quick commands for running the SBIR demo

.PHONY: help up down logs demo seed clean

DEMO_PORT ?= 2718
DOCKER_COMPOSE := $(shell command -v docker-compose 2>/dev/null || echo "docker compose")

help:
	@echo "FRANK Demo Commands:"
	@echo ""
	@echo "  make up       — Start FRANK containers (central, sbp, partner)"
	@echo "  make down     — Stop all containers"
	@echo "  make logs     — Follow container logs"
	@echo "  make demo     — Run Marimo demo launcher"
	@echo "  make seed     — Seed demo data into FRANK instances"
	@echo "  make clean    — Stop containers and remove volumes"
	@echo ""
	@echo "Quick start:"
	@echo "  make up seed demo"

# Start LocalStack for data inspection (optional)
up:
	$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "LocalStack starting..."
	@echo "  - DynamoDB Admin: http://localhost:8100"
	@echo ""
	@echo "For live FRANK API, use:"
	@echo "  cd ../environments/local-docker && make stage2"

# Stop containers
down:
	$(DOCKER_COMPOSE) down

# Follow logs
logs:
	$(DOCKER_COMPOSE) logs -f

# Run demo (multi-page ASGI app)
demo run:
	uv run python serve.py

# Stop demo
stop:
	@pkill -f "serve.py" 2>/dev/null || true
	@echo "Stopped demo server"

# Seed demo data
seed:
	@echo "Seeding demo data..."
	uv run python seed_data.py

# Clean everything
clean:
	$(DOCKER_COMPOSE) down -v
	@echo "Containers stopped and volumes removed"
