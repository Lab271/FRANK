# ===================================
# FRANK Platform - Input Variables
# ===================================

variable "region" {
  description = "AWS region for deployment"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "frank-spike"
}

variable "environment" {
  description = "Environment name (spike, dev, prod)"
  type        = string
  default     = "spike"
}

variable "domain_name" {
  description = "Custom domain name for the application"
  type        = string
  default     = "frank-spike.lab271.io"
}

variable "hosted_zone_name" {
  description = "Route53 hosted zone name"
  type        = string
  default     = "lab271.io"
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "container_port" {
  description = "Port on which the application container listens"
  type        = number
  default     = 8000
}

variable "container_cpu" {
  description = "CPU units for the container (256, 512, 1024, etc.)"
  type        = string
  default     = "256"
}

variable "container_memory" {
  description = "Memory for the container in MB"
  type        = string
  default     = "512"
}

variable "desired_count" {
  description = "Desired number of ECS tasks"
  type        = number
  default     = 1
}

variable "log_retention_days" {
  description = "CloudWatch log retention period in days"
  type        = number
  default     = 7
}

variable "ssl_policy" {
  description = "SSL policy for the Application Load Balancer"
  type        = string
  default     = "ELBSecurityPolicy-TLS-1-2-2017-01"
}

variable "common_tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default = {
    Project     = "FRANK"
    Environment = "spike"
    ManagedBy   = "OpenTofu"
    Owner       = "SchubergPhilis"
  }
}