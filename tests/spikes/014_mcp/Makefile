# MCP Server Platform - Local Deployment Makefile
# Copyright (c) 2025 LAB271
# SPDX-License-Identifier: Apache-2.0

LOCAL_DOMAIN = mcp.local
GATEWAY = https://$(LOCAL_DOMAIN)


.PHONY: help setup generate-certs start stop restart logs clean status test

start: ## Start Colima if not already running
	@colima start
	@colima status

.ssl-certs/nginx.crt: 
	@if ! grep -q "$(LOCAL_DOMAIN)" /etc/hosts; then \
		echo "127.0.0.1 $(LOCAL_DOMAIN)" | sudo tee -a /etc/hosts; \
	fi
	@mkdir -p .ssl-certs
	@mkcert -key-file .ssl-certs/nginx.key -cert-file .ssl-certs/nginx.crt $(LOCAL_DOMAIN)


up: .ssl-certs/nginx.crt
	@echo "Starting MCP platform..."
	@docker-compose -f deployment/local/docker-compose.yml up -d --build
	@echo ""
	@echo "✅ Services started!"

stop:
	@echo "🛑 Stopping MCP platform..."
	@docker-compose -f deployment/local/docker-compose.yml down

cleanup: ## Clean up docker
	@docker images | grep "localhost:" | awk '{print $$3}' | xargs docker rmi -f || true
	@docker rm -f $$(docker ps -aq) || true
	@docker rmi -f $$(docker images -aq) || true
	@docker volume prune -f || true
	@docker network prune -f || true
	@docker system prune -a -f --volumes|| true

restart:
	@echo "Restarting MCP platform..."
	@docker-compose -f deployment/local/docker-compose.yml restart

rebuild:
	@echo "Rebuilding and restarting services..."
	@docker-compose -f deployment/local/docker-compose.yml up -d --build

logs:
	@docker-compose -f deployment/local/docker-compose.yml logs -f

logs-nginx:
	@docker-compose -f deployment/local/docker-compose.yml logs -f nginx-gateway

logs-log-mcp:
	@docker-compose -f deployment/local/docker-compose.yml logs -f log-mcp

status:
	@echo "Service Status:"
	@docker-compose -f deployment/local/docker-compose.yml ps
	@echo ""
	@echo "Network Status:"
	@docker network inspect mcp-platform_mcp-network 2>/dev/null | grep -A 5 "Containers" || echo "Network not found"

test: test-gateway test-log-mcp test-greeting-mcp

test-full: ## Run comprehensive tests
	@echo "Running comprehensive test suite..."
	@./test_greeting_server.sh

test-greeting: ## Run greeting MCP server Python tests
	test-simple: ## Run simple Python tests
	@echo "Running simple Python tests..."
	@python3 test_greeting_simple.py

test-http: ## Run HTTP endpoint tests
	@echo "Running HTTP endpoint tests..."
	@python3 test_http_endpoints.py

test-gateway:
	@echo "Testing Gateway..."
	@echo ""
	@echo "HTTP -> HTTPS redirect:"
	@curl -sI http://mcp.local/ | head -3
	@echo ""
	@echo "Gateway health:"
	@curl -sk https://mcp.local/health | jq . || curl -sk https://mcp.local/health
	@echo ""
	@echo "Gateway info:"
	@curl -sk https://mcp.local/ | jq . || curl -sk https://mcp.local/

test-log-mcp:
	@echo ""
	@echo "Testing Log MCP Server..."
	@echo ""
	@echo "Log MCP health:"
	@curl -sk https://mcp.local/log/health | jq . || curl -sk https://mcp.local/log/health
	@echo ""

test-greeting-mcp:
	@echo ""
	@echo "Testing Greeting MCP Server..."
	@echo ""
	@echo "Greeting MCP health:"
	@curl -sk https://mcp.local/greeting/health | jq . || curl -sk https://mcp.local/greeting/health
	@echo ""

logs-greeting-mcp:
	@docker-compose -f deployment/local/docker-compose.yml logs -f greeting-mcp

clean:
	@echo "Stopping and removing all containers and volumes..."
	@docker-compose -f deployment/local/docker-compose.yml down -v
	@echo "✓ Cleanup complete"

clean-certs:
	@echo "Removing SSL certificates..."
	@rm -rf .ssl-certs
	@echo "✓ Certificates removed"

.DEFAULT_GOAL := help
help: ## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "\033[33mAccess URLs:\033[0m"
	@echo "  Gateway:   $(GATEWAY)"
	@echo "  Log MCP:   $(GATEWAY)/log/"
	@echo "  Greeting:  $(GATEWAY)/greeting/"
	@echo ""
	@echo "Run 'make logs' to view logs"
