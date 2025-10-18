.ONESHELL:
SHELL := /bin/bash

PACKAGE=frank
VIRTUALENV = ./.$(PACKAGE)
PYTHON = $(VIRTUALENV)/bin/python
.PHONY: test lint help unittests integration clean env dev update freeze outdated check

default: help

TARGETS = check env test
all: $(TARGETS)

check: ## Validate primary development dependencies
	@python --version > /dev/null
	@python -m pip > /dev/null
	@docker --version > /dev/null
	@echo "All required tools available"

freeze:  ## Freezes pip requirements
	@echo "# Generated on `date`" >| requirements.txt
	@$(PYTHON) -m pip freeze | grep -v "$(PACKAGE)" >> requirements.txt
	@echo "requirements.txt regenerated"

clean: ## Clean all build files and virtualenv
	-@echo y | pip uninstall $(PACKAGE)
	@rm -rdf $(PACKAGE).egg*
	@find . -name *.pyc -delete
	@rm -rdf build dist
	@rm -rdf $(VIRTUALENV)
	@rm -frd .pytest_cache .ruff_cache .coverage
	@rm -rfd __pycache__

env: $(VIRTUALENV)/bin/python ## create the virtualenv
	@$(PYTHON) -m pip install --upgrade pip
	@$(PYTHON) -m pip install -e . --require-virtualenv
	@$(PYTHON) -m pip install ruff --require-virtualenv
	@$(PYTHON) -m pip install pytest --require-virtualenv
	@$(PYTHON) -m pip install coverage --require-virtualenv
	@$(PYTHON) -m pip install -r requirements.txt --require-virtualenv

dev: $(VIRTUALENV)/bin/python ## redeploy the package
	@$(PYTHON) -m pip install -e . --require-virtualenv

test: ## Run unit tests and coverage
	@coverage run -m pytest
	@coverage report -m --fail-under=85

integration:  ## Run all integration tests
	@behave tests/integration

lint: test ## Static code checking
	@ruff check .

$(VIRTUALENV)/bin/python: # create the local virtualenv
	virtualenv $(VIRTUALENV)
	echo "To activate 'source $(VIRTUALENV)/bin/activate'"

outdated: ## list all outdated packages
	@$(PYTHON) -m pip list --outdated	
	
version: ## show versions
	@$(PYTHON) --version
	@$(PYTHON) -c "from frank import __version__; print(f'FRANK version: {__version__}')"
	@aws --version
	
help: ## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""