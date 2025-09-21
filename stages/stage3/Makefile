# FRANK Platform - Setup Script

# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0
# ================================
# Makefile - Development Commands
# ================================
.PHONY: help

help:  ## Show this help message
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'	


# ================================
# SETUP
# ================================
setup: ## Initial setup
	@echo "$(COLOR_BLUE)Setting up FRANK Minimal...$(COLOR_RESET)"
	@mkdir -p logs
	@cp -n minimal.example.env .env 2>/dev/null || true
	@echo "$(COLOR_GREEN)Setup complete!$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_YELLOW)Next steps:$(COLOR_RESET)"
	@echo "1. Edit .env with your AWS credentials"
	@echo "2. Run 'make deploy-aws' to create DynamoDB table"
	@echo "3. Run 'make run-local' to start the application"

# ================================
# AWS DEPLOYMENT
# ================================
deploy-aws: ## Deploy DynamoDB table to AWS
	@echo "$(COLOR_BLUE)Deploying to AWS...$(COLOR_RESET)"
	@cd infrastructure && tofu init
	@cd infrastructure && tofu apply -auto-approve
	@echo "$(COLOR_GREEN)AWS deployment complete!$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_YELLOW)Getting credentials...$(COLOR_RESET)"
	@cd infrastructure && tofu output -json application_config | jq -r 'to_entries[] | "\(.key)=\(.value)"' > ../.env.aws_config
	@echo "AWS configuration saved to .aws_config.env"


destroy-aws: ## Destroy AWS resources
	@echo "$(COLOR_RED)WARNING: This will destroy the DynamoDB table and all data!$(COLOR_RESET)"
	@read -p "Are you sure? Type 'yes' to continue: " confirm && [ "$$confirm" = "yes" ]
	@cd infrastructure && tofu destroy -auto-approve
	@echo "$(COLOR_GREEN)AWS resources destroyed$(COLOR_RESET)"

# ================================
# LOCAL DEVELOPMENT
# ================================
run-local: ## Run the application locally (connects to AWS)
	@echo "$(COLOR_BLUE)Starting FRANK Minimal locally...$(COLOR_RESET)"
	@if [ ! -f .env ]; then echo "$(COLOR_RED)Error: .env file not found. Run 'make setup' first.$(COLOR_RESET)"; exit 1; fi
	@if [ -f aws_config.env ]; then \
		echo "Loading AWS configuration..."; \
		export $$(cat .env | sed '/^\s*#/d;/^\s*$/d' | xargs) && export $$(cat .env.aws_config | xargs) && python frank_stage3.py; \
	else \
		echo "Loading .env configuration..."; \
		export $$(cat .env | sed '/^\s*#/d;/^\s*$/d' | xargs) && python frank_stage3.py; \
	fi