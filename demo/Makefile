# FRANK Demo — Makefile
#
# Quick commands for running the SBIR demo

.PHONY: help up down logs demo seed clean

DEMO_PORT ?= 2718

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

# Start all FRANK containers
up:
	docker compose up -d
	@echo ""
	@echo "FRANK instances starting..."
	@echo "  - Central: http://localhost:8000/docs"
	@echo "  - SBP:     http://localhost:8001/docs"
	@echo "  - Partner: http://localhost:8002/docs"
	@echo "  - DynamoDB Admin: http://localhost:8100"

# Stop containers
down:
	docker compose down

# Follow logs
logs:
	docker compose logs -f

# Run demo launcher
demo:
	@echo "Starting FRANK Demo at http://localhost:$(DEMO_PORT)"
	uv run marimo run index.py --host 0.0.0.0 --port $(DEMO_PORT)

# Run individual scenarios
s1:
	uv run marimo run s1_active_incident.py --host 0.0.0.0 --port $(DEMO_PORT)

s2:
	uv run marimo run s2_evolving_case.py --host 0.0.0.0 --port $(DEMO_PORT)

s3:
	uv run marimo run s3_supply_chain.py --host 0.0.0.0 --port $(DEMO_PORT)

s4:
	uv run marimo run s4_cyclotron.py --host 0.0.0.0 --port $(DEMO_PORT)

s5:
	uv run marimo run s5_dashboard.py --host 0.0.0.0 --port $(DEMO_PORT)

# Seed demo data
seed:
	@echo "Seeding demo data..."
	uv run python seed_data.py

# Clean everything
clean:
	docker compose down -v
	@echo "Containers stopped and volumes removed"
