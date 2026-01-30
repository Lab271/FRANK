.ONESHELL:
SHELL := /bin/bash
VENV := .venv
PYTHON_VERSION := 3.11
PACKAGE := frank

.PHONY: help version check env sync lock test lint format type-check clean docker-up docker-down docker-logs docker-build

version: ## Show project version
	@uv run python -c "from $(PACKAGE) import __version__; print(f'version: {__version__}')"

check: ## Verify required tooling is available
	@echo "Checking for required tools..."
	@printf "Checking for 'uv'... "
	@command -v uv >/dev/null 2>&1 || { echo >&2 "✗ 'uv' is required but not installed. Please install it from https://github.com/astral-sh/uv"; exit 1; }
	@printf "\rChecking for 'pytest'... "
	@uv run pytest --version > /dev/null 2>&1 || { echo >&2 "✗ pytest is not installed"; exit 1; }
	@printf "\rChecking for 'ruff'... "
	@uv run ruff --version > /dev/null 2>&1 || { echo >&2 "✗ ruff is not installed"; exit 1; }
	@printf "\rChecking for 'mypy'... "
	@uv run mypy --version > /dev/null 2>&1 || { echo >&2 "✗ mypy is not installed"; exit 1; }
	@printf "\r\033[K✓ All required tools are installed\n"

env: ## Create and populate the development virtual environment
	@echo "Setting up development environment with Python $(PYTHON_VERSION)..."
	uv venv $(VENV) --python $(PYTHON_VERSION) --clear > /dev/null
	@echo "✓ Virtual environment created at $(VENV)/"
	@uv sync > /dev/null
	@uv sync --all-groups > /dev/null
	@if [ ! -f uv.lock ]; then \
		echo "No uv.lock found, generating lock file..."; \
		uv lock; \
	fi
	@uv run python -c "from $(PACKAGE) import __version__; print(f'version: {__version__}')"
	@echo "To activate: source $(VENV)/bin/activate"
	@echo "✓ Development environment is ready"

sync: ## Sync dependencies into the virtual environment
	@echo "Syncing dependencies into virtual environment..."
	uv sync > /dev/null
	uv sync --all-groups > /dev/null
	@echo "✓ Dependencies synced"

lock: ## Lock dependencies into uv.lock
	@echo "Locking dependencies..."
	uv lock

test: ## Run tests with coverage
	@echo "Running tests..."
	uv run pytest --cov=src/$(PACKAGE) tests/

lint: ## Lint code with ruff
	@echo "Linting with ruff..."
	uv run ruff check src/ tests/

format: ## Format code with ruff
	@echo "Formatting with ruff..."
	uv run ruff check --fix src/ tests/
	uv run ruff format src/ tests/

type-check: ## Run type checks with mypy
	@echo "Type checking with mypy..."
	uv run mypy src/

clean: ## Clean up artifacts and caches
	@echo "Cleaning up..."
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name htmlcov -exec rm -rf {} + 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name ".coverage" -delete
	@echo "✓ Cleaned"

docker-build: ## Build all Docker images
	@echo "Building Docker images..."
	docker compose -f docker-compose.local.yml build

docker-up: ## Start all services (Web GUI + Management API + Mock Cognito)
	@echo "Starting FRANK platform services..."
	@docker compose -f docker-compose.local.yml up -d
	@echo "✓ Services started"
	@echo ""
	@echo "Access points:"
	@echo "  Web GUI:        http://localhost:3000"
	@echo "  Management API: http://localhost:8001/docs"
	@echo "  Mock Cognito:   http://localhost:8100/health"
	@echo ""
	@echo "View logs: make docker-logs"
	@echo "Stop services: make docker-down"

docker-down: ## Stop all services
	@echo "Stopping FRANK platform services..."
	@docker compose -f docker-compose.local.yml down
	@echo "✓ Services stopped"

docker-logs: ## Follow logs from all services
	@docker compose -f docker-compose.local.yml logs -f

.DEFAULT_GOAL := help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'