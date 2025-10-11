# FRANK Platform - FastAPI Testability Spike - Build Automation
# Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling
#
# This Makefile provides convenient commands for FastAPI testability spike
# development workflow including dependency installation, testing with coverage,
# development server management with hot-reload, and code quality validation.
#
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0

PORT=8000
HOST_URL=http://localhost:$(PORT)

.PHONY: dev test integration clean run help

# Default target
help: ## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install dev dependencies
	pip install fastapi==0.104.1 uvicorn[standard]==0.24.0 httpx==0.25.2
	pip install pytest pytest-cov pytest-xdist coverage[toml]

test: ## Run all tests
	@coverage run -m pytest
	@coverage report -m 

integration: ## Run tests simulating external calls
	@if ! lsof -i:8000 > /dev/null; then \
		(python simple_api_011.py --port $(PORT) --reload > /dev/null 2>&1 &); \
		sleep 1; \
	fi
	@./test_integration.sh $(HOST_URL)
	@pkill -f "simple_api_011.py --port $(PORT)" || true

run: ## Run the FastAPI server
	python simple_api_011.py --reload

clean: ## Clean up temporary files
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
