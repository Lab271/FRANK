# ===================================
# FRANK Platform - Local Values
# ===================================

locals {
  # Environment-specific naming
  name_prefix = "${var.project_name}-${var.environment}"
  
  # Common tags merged with environment-specific tags
  common_tags = merge(var.common_tags, {
    Environment = var.environment
    Region      = var.region
    Domain      = var.domain_name
    Deployment  = "opentofu"
  })

  # Network calculations
  availability_zones = slice(data.aws_availability_zones.available.names, 0, length(var.public_subnet_cidrs))
  
  # Container configuration
  container_definitions = {
    name         = "${var.project_name}-container"
    image        = "${aws_ecr_repository.main.repository_url}:latest"
    cpu          = var.container_cpu
    memory       = var.container_memory
    port         = var.container_port
    log_group    = aws_cloudwatch_log_group.main.name
    user         = "frankuser"
  }

  # SSL configuration
  ssl_domains = concat([var.domain_name], ["*.${var.hosted_zone_name}"])
  
  # Health check configuration
  health_check = {
    path                = "/health"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  # ALB configuration
  alb_config = {
    name               = "${local.name_prefix}-alb"
    internal           = false
    load_balancer_type = "application"
    deletion_protection = false
    access_logs_enabled = true
  }

  # ECS configuration
  ecs_config = {
    cluster_name                = "${local.name_prefix}-cluster"
    service_name               = "${local.name_prefix}-service"
    task_family                = var.project_name
    network_mode               = "awsvpc"
    requires_compatibilities   = ["FARGATE"]
    launch_type                = "FARGATE"
    platform_version          = "LATEST"
    assign_public_ip           = true
    deployment_maximum_percent = 200
    deployment_minimum_percent = 100
  }

  # Environment variables for container
  container_environment = [
    {
      name  = "FRANK_ENVIRONMENT"
      value = "aws"
    },
    {
      name  = "AWS_DEFAULT_REGION"
      value = var.region
    },
    {
      name  = "PORT"
      value = tostring(var.container_port)
    },
    {
      name  = "LOG_LEVEL"
      value = var.environment == "prod" ? "INFO" : "DEBUG"
    },
    {
      name  = "ENVIRONMENT"
      value = var.environment
    }
  ]

  # Security group rules
  alb_ingress_rules = [
    {
      description = "HTTP"
      from_port   = 80
      to_port     = 80
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    },
    {
      description = "HTTPS"
      from_port   = 443
      to_port     = 443
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  ]

  ecs_ingress_rules = [
    {
      description     = "Container port from ALB"
      from_port       = var.container_port
      to_port         = var.container_port
      protocol        = "tcp"
      security_groups = true  # Will be replaced with actual SG ID
    }
  ]
}