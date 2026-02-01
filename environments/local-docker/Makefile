# FRANK Local Docker Environment Makefile
# Convenience commands for Docker Compose operations

.PHONY: help up down restart logs logs-api logs-web logs-admin logs-cognito logs-postgres logs-localstack ps clean rebuild

help:
	@echo "FRANK Local Docker Environment"
	@echo ""
	@echo "Available commands:"
	@echo "  make up              - Start all services in background"
	@echo "  make down            - Stop all services"
	@echo "  make restart         - Restart all services"
	@echo "  make logs            - Show logs for all services"
	@echo "  make logs-api        - Show logs for Management API"
	@echo "  make logs-web        - Show logs for Web GUI"
	@echo "  make logs-admin      - Show logs for Admin API"
	@echo "  make logs-cognito    - Show logs for Mock Cognito"
	@echo "  make logs-postgres   - Show logs for PostgreSQL"
	@echo "  make logs-localstack - Show logs for LocalStack"
	@echo "  make ps              - Show running containers"
	@echo "  make clean           - Remove all containers, volumes, and networks"
	@echo "  make rebuild         - Rebuild and restart all services"

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-api:
	docker-compose logs -f frank-management-api

logs-web:
	docker-compose logs -f frank-web-gui

logs-admin:
	docker-compose logs -f frank-admin-api

logs-cognito:
	docker-compose logs -f mock-cognito

logs-postgres:
	docker-compose logs -f postgres

logs-localstack:
	docker-compose logs -f localstack

ps:
	docker-compose ps

clean:
	docker-compose down -v --remove-orphans
	@echo "✅ All containers, volumes, and networks removed"

rebuild:
	docker-compose down
	docker-compose build --no-cache
	docker-compose up -d
	@echo "✅ Services rebuilt and started"
