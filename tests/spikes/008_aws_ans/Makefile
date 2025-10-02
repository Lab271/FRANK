install: ## Install Ansible collections
	@cd ansible && ansible-galaxy collection install -r requirements.yaml
	
deploy:  ## Create the spike environment
	@mkdir -p ansible/logs
	@cd ansible && ansible-playbook deploy-frank.yaml --tags deploy

create:  ## Create the spike environment
	@mkdir -p ansible/logs
	@cd ansible && ansible-playbook deploy-frank.yaml --tags phase1

help: ## Shows help screen
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-16s\033[0m %s\n", $$1, $$2}'
	@echo ""