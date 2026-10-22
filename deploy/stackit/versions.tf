terraform {
  required_version = ">= 1.6"
  required_providers {
    stackit = {
      source  = "stackitcloud/stackit"
      version = "~> 0.121"
    }
  }
}

# Credentials from the environment (STACKIT_SERVICE_ACCOUNT_KEY_PATH);
# see https://registry.terraform.io/providers/stackitcloud/stackit/latest/docs
provider "stackit" {
  default_region = var.region
}
