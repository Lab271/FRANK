# FRANK Local Docker Environment Makefile
# Convenience commands for Docker Compose operations

.PHONY: help stage1 stage2 stage3 up down restart logs logs-api logs-web logs-admin logs-cognito logs-postgres logs-localstack logs-dynamodb-admin ps clean rebuild health

help:
	@echo "FRANK Local Docker Environment"
	@echo ""
	@echo "Stage Commands:"
	@echo "  make stage1          - Start Stage 1 (SQLite only)"
	@echo "  make stage2          - Start Stage 2 (PostgreSQL + DynamoDB)"
	@echo "  make stage3          - Start Stage 3 (Full stack with Web GUI)"
	@echo ""
	@echo "General Commands:"
	@echo "  make up              - Start all services (default: stage3)"
	@echo "  make down            - Stop all services"
	@echo "  make restart         - Restart all services"
	@echo "  make health          - Check health of all services"
	@echo "  make ps              - Show running containers"
	@echo "  make clean           - Remove all containers, volumes, and networks"
	@echo "  make rebuild         - Rebuild and restart all services"
	@echo ""
	@echo "Logs:"
	@echo "  make logs            - Show logs for all services"
	@echo "  make logs-api        - Show logs for Management API"
	@echo "  make logs-web        - Show logs for Web GUI"
	@echo "  make logs-admin      - Show logs for Admin API"
	@echo "  make logs-cognito    - Show logs for Mock Cognito"
	@echo "  make logs-postgres   - Show logs for PostgreSQL"
	@echo "  make logs-localstack - Show logs for LocalStack"
	@echo "  make logs-dynamodb-admin - Show logs for DynamoDB Admin"

# Stage-specific targets
stage1:
	@echo "🚀 Starting FRANK Stage 1 (SQLite only)"
	docker-compose --profile stage1 up -d
	@echo "✅ Stage 1 running. Access Management API at http://localhost:8001/docs"

stage2:
	@echo "🚀 Starting FRANK Stage 2 (PostgreSQL + DynamoDB)"
	docker-compose --profile stage2 up -d
	@echo "✅ Stage 2 running. Access:"
	@echo "   - Management API: http://localhost:8001/docs"
	@echo "   - PostgreSQL: localhost:5432"
	@echo "   - LocalStack: http://localhost:4566"
	@echo "   - DynamoDB Admin: http://localhost:8101"

stage3:
	@echo "🚀 Starting FRANK Stage 3 (Full stack)"
	docker-compose --profile stage3 up -d
	@echo "✅ Stage 3 running. Access:"
	@echo "   - Web GUI: http://localhost:3000"
	@echo "   - Management API: http://localhost:8001/docs"
	@echo "   - Mock Cognito: http://localhost:8100/health"
	@echo "   - PostgreSQL: localhost:5432"
	@echo "   - LocalStack: http://localhost:4566"
	@echo "   - DynamoDB Admin: http://localhost:8101"

# Default: start stage3
up: stage3

down:
	docker-compose down

restart:
	docker-compose restart

health:
	@echo "🏥 Checking service health..."
	@docker-compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"

ps:
	docker-compose ps

# Log commands
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

logs-dynamodb-admin:
	docker-compose logs -f frank-dynamodb-admin

# Cleanup and rebuild
clean:
	docker-compose down -v --remove-orphans
	@echo "✅ All containers, volumes, and networks removed"

rebuild:
	docker-compose down
	docker-compose build --no-cache
	docker-compose --profile stage3 up -d
	@echo "✅ Services rebuilt and started"
