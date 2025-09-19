.ONESHELL:
SHELL := /bin/bash

PACKAGE=frank
VIRTUALENV = ./.$(PACKAGE)
PYTHON = $(VIRTUALENV)/bin/python
.PHONY: test lint coverage help unittests integration clean env dev update freeze outdated check

default: clean env test

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

clean: ## Clean all build files
	-@echo y | pip uninstall $(PACKAGE)
	@rm -rdf $(PACKAGE).egg*
	@find . -name *.pyc -delete
	@rm -rdf build dist
	@rm -rdf $(VIRTUALENV)
	@rm -frd .pytest_cache .ruff_cache .coverage
	@rm -rfd __pycache__

dev:$(VIRTUALENV)/bin/python  ## Install this for development
	@$(PYTHON) -m pip install --upgrade pip
	@$(PYTHON) -m pip install -e .
	@$(PYTHON) -m pip install lark
	@$(PYTHON) -m pip install ruff
	@$(PYTHON) -m pip install pytest
	@$(PYTHON) -m pip install coverage


unittests:  		## Run all unittests
	@$(PYTHON) -mpytest tests/unit/ \
		--verbose \
		--tb=short \
		--cov=src/ \
		--cov-report=xml \
		--cov-report=html \
		--cov-report=term-missing \
		--cov-fail-under=50 \
		--junitxml=test-results.xml

integration:  ## Run all integration tests
	@behave tests/integration

lint: test ## Static code checking
	@ruff check .

coverage: ## Code coverage
	@coverage run -m pytest
	@coverage report -m 

env: $(VIRTUALENV)/bin/python ## create the virtualenv
	@$(PYTHON) -m pip install -r requirements.txt

$(VIRTUALENV)/bin/python: # create the local virtualenv
	virtualenv $(VIRTUALENV)
	echo "To activate 'source $(VIRTUALENV)/bin/activate'"

update: ## update all packages
	@$(PYTHON) -m pip install --upgrade pip

outdated: ## list all outdated packages
	@$(PYTHON) -m pip list --outdated	
	
help: ## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""