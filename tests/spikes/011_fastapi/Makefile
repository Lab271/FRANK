# FRANK Platform - FastAPI Testability Spike - Build Automation
# Feedbackinfrastructuur voor cyberRisico Analyse en Netwerk Kennisdeling
#
# This Makefile provides convenient commands for FastAPI testability spike
# development workflow including dependency installation, testing with coverage,
# development server management with hot-reload, and code quality validation.
#
# Key targets:
#   make install       - Install Python dependencies
#   make test          - Run comprehensive test suite
#   make test-coverage - Generate test coverage reports
#   make run.          - Start development server with hot-reload
#   make validate      - Complete validation workflow
#
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0

.PHONY: install dev test test-outside test-coverage clean run help

# Default target
help: ## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	pip install fastapi==0.104.1 uvicorn[standard]==0.24.0 httpx==0.25.2

dev: install ## Install development dependencies (includes testing tools)
	pip install pytest pytest-cov pytest-xdist coverage[toml]

test: ## Run all tests
	pytest test_simple_api.py -v

test-outside: ## Run tests simulating external calls
	@echo "🔍 Testing all FastAPI endpoints..."
	@printf "📌 Testing public endpoint: "
	@curl -s http://localhost:8000/ | grep -q "Public endpoint accessed successfully" && echo "✅ PASS" || echo "❌ FAIL"
	@printf "🔐 Testing protected endpoint (valid token): "
	@curl -s -H "Authorization: Bearer valid-token" http://localhost:8000/protected | grep -q "Protected endpoint accessed successfully" && echo "✅ PASS" || echo "❌ FAIL"
	@printf "🚫 Testing protected endpoint (invalid token): "
	@curl -s -H "Authorization: Bearer invalid-token" http://localhost:8000/protected | grep -q "Invalid authentication token" && echo "✅ PASS" || echo "❌ FAIL"
	@printf "💥 Testing exception endpoint (500 error): "
	@curl -s http://localhost:8000/error | grep -q "This is a controlled exception for testing purposes" && echo "✅ PASS" || echo "❌ FAIL"
	@printf "🐍 Testing Python exception endpoint (500 error): "
	@curl -s http://localhost:8000/python-error | grep -q "This is a Python exception converted to HTTP 500" && echo "✅ PASS" || echo "❌ FAIL"
	@printf "⚠️  Testing custom error endpoint (401 error): "
	@curl -s http://localhost:8000/unauthorized | grep -q "Custom unauthorized error from endpoint" && echo "✅ PASS" || echo "❌ FAIL"
	@printf "❤️  Testing health check endpoint: "
	@curl -s http://localhost:8000/health | grep -q "healthy" && echo "✅ PASS" || echo "❌ FAIL"

test-coverage: ## Run tests with coverage report
	pytest test_simple_api.py --cov=simple_api --cov-report=html --cov-report=term-missing

run: ## Run the FastAPI server
	python simple_api.py --reload

clean: ## Clean up temporary files
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -name "*.pyc" -delete
	find . -name "*.pyo" -delete
