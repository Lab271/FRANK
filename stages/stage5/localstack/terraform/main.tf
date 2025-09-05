terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region                      = var.aws_region
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  endpoints {
    apigateway   = "http://localhost:4566"
    lambda       = "http://localhost:4566"
    dynamodb     = "http://localhost:4566"
    s3          = "http://localhost:4566"
    opensearch  = "http://localhost:4566"
    iam         = "http://localhost:4566"
    logs        = "http://localhost:4566"
  }
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "frank"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "local"
}

# Local values
locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
  }

  lambda_runtime = "python3.11"
  lambda_timeout = 30
}
