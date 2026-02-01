.ONESHELL:
SHELL := /bin/bash
VENV := .venv
PYTHON_VERSION := 3.11
PACKAGE := frank

.PHONY: help version check env sync lock test lint format type-check clean docker-up docker-down docker-logs docker-build env-help

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

env-help: ## Show environment deployment options
	@echo "FRANK Deployment Environments"
	@echo ""
	@echo "Local Development:"
	@echo "  environments/local-docker/   - Docker Compose (recommended)"
	@echo "  environments/local-python/   - Python virtualenv (debugging)"
	@echo ""
	@echo "AWS Deployment:"
	@echo "  environments/aws-dev/        - Development environment"
	@echo "  environments/aws-preprod/    - Pre-production environment"
	@echo "  environments/aws-prod/       - Production environment"
	@echo ""
	@echo "Quick Start:"
	@echo "  cd environments/local-docker && make stage3"
	@echo ""
	@echo "Documentation:"
	@echo "  cat environments/README.md"

docker-build: ## Build all Docker images
	@echo "Building Docker images..."
	@cd environments/local-docker && docker compose build

docker-up: ## Start all services (Web GUI + Management API + Mock Cognito)
	@echo "Starting FRANK platform services..."
	@cd environments/local-docker && $(MAKE) stage3

docker-down: ## Stop all services
	@echo "Stopping FRANK platform services..."
	@cd environments/local-docker && $(MAKE) down

docker-logs: ## Follow logs from all services
	@cd environments/local-docker && $(MAKE) logs

.DEFAULT_GOAL := help

help: ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'