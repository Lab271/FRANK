.ONESHELL:
SHELL := /bin/bash

PACKAGE=frank
VIRTUALENV = ./.venv
PYTHON = $(VIRTUALENV)/bin/python
.PHONY: test lint help unittests integration clean env dev update freeze outdated check

default: help

TARGETS = check env test
all: $(TARGETS)

check: ## Validate primary development dependencies
	@uv --version > /dev/null && echo "✅ uv available" || (echo "❌ Please install uv as package manager: https://docs.astral.sh/uv/" && exit 1)
	@aws --version > /dev/null && echo "✅ aws available" || (echo "❌ Please install aws-cli: https://aws.amazon.com/cli/" && exit 1)
	@docker --version > /dev/null && echo "✅ docker available" || (echo "❌ Please install docker: https://docs.docker.com/get-docker/" && exit 1)
	@docker-compose --version > /dev/null && echo "✅ docker-compose available" || (echo "❌ Please install docker-compose: https://docs.docker.com/compose/install/" && exit 1)
	@echo "🔧 All required tools available"

freeze:  ## Freezes pip requirements
	@echo "# Generated on `date`" >| requirements.txt
	@uv pip freeze | grep -v "$(PACKAGE)" >> requirements.txt
	@echo "requirements.txt regenerated"

clean: ## Clean all build files and virtualenv
	@find . -name *.pyc -delete
	@rm -f uv.lock .python-version
	@rm -frd .pytest_cache .ruff_cache .coverage
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name "$(PACKAGE).egg-*" -exec rm -rf {} +
	@rm -rdf build dist
	-@echo y | uv pip uninstall $(PACKAGE) 2>&1 > /dev/null || true
	@rm -rdf $(VIRTUALENV)

env: $(VIRTUALENV)/bin/python ## create the virtualenv
	@uv pip install --upgrade pip
	@uv pip install -e . 
	@uv pip install -r requirements.txt

dev: $(VIRTUALENV)/bin/python ## redeploy the package
	@uv pip install -e . 
	@uv pip install ruff
	@uv pip install pytest
	@uv pip install coverage

test: ## Run unit tests and coverage
	@coverage run -m pytest
	@coverage report -m --fail-under=85

integration:  ## Run all integration tests
	@behave tests/integration

lint: test ## Static code checking
	@ruff check .

$(VIRTUALENV)/bin/python: # create the local virtualenv
	@uv venv
	echo "To activate 'source $(VIRTUALENV)/bin/activate'"

outdated: ## list all outdated packages
	@$(PYTHON) -m pip list --outdated |  grep -v "$(PACKAGE)"
	
version: ## show versions
	@$(PYTHON) --version
	@$(PYTHON) -c "from frank import __version__; print(f'FRANK version: {__version__}')"
	
help: ## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""