# ===================================
# FRANK Platform - MINIMAL OpenTofu Configuration
# Simple ECS deployment without SSL/DNS complexity
# ===================================

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = "eu-west-1"
}

# ===================================
# DATA SOURCES
# ===================================

data "aws_availability_zones" "available" {
  state = "available"
}

# ===================================
# VPC AND NETWORKING
# ===================================

resource "aws_vpc" "frank_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "frank-spike-vpc"
  }
}

resource "aws_internet_gateway" "frank_igw" {
  vpc_id = aws_vpc.frank_vpc.id

  tags = {
    Name = "frank-spike-igw"
  }
}

resource "aws_subnet" "frank_public_subnets" {
  count = 2

  vpc_id                  = aws_vpc.frank_vpc.id
  cidr_block              = "10.0.${count.index + 1}.0/24"
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "frank-spike-public-subnet-${count.index + 1}"
  }
}

resource "aws_route_table" "frank_public_rt" {
  vpc_id = aws_vpc.frank_vpc.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.frank_igw.id
  }

  tags = {
    Name = "frank-spike-public-rt"
  }
}

resource "aws_route_table_association" "frank_public_rta" {
  count = length(aws_subnet.frank_public_subnets)

  subnet_id      = aws_subnet.frank_public_subnets[count.index].id
  route_table_id = aws_route_table.frank_public_rt.id
}

# ===================================
# SECURITY GROUPS
# ===================================

resource "aws_security_group" "frank_alb_sg" {
  name   = "frank-spike-alb-sg"
  vpc_id = aws_vpc.frank_vpc.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "frank-spike-alb-sg"
  }
}

resource "aws_security_group" "frank_ecs_sg" {
  name   = "frank-spike-ecs-sg"
  vpc_id = aws_vpc.frank_vpc.id

  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.frank_alb_sg.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "frank-spike-ecs-sg"
  }
}

# ===================================
# ECR REPOSITORY (Keep - it's simple and useful)
# ===================================

resource "aws_ecr_repository" "frank_repo" {
  name = "frank-spike"

  tags = {
    Name = "frank-spike-ecr"
  }
}

# ===================================
# APPLICATION LOAD BALANCER
# ===================================

resource "aws_lb" "frank_alb" {
  name               = "frank-spike-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.frank_alb_sg.id]
  subnets            = aws_subnet.frank_public_subnets[*].id

  tags = {
    Name = "frank-spike-alb"
  }
}

resource "aws_lb_target_group" "frank_tg" {
  name        = "frank-spike-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.frank_vpc.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }

  tags = {
    Name = "frank-spike-tg"
  }
}

resource "aws_lb_listener" "frank_http_listener" {
  load_balancer_arn = aws_lb.frank_alb.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.frank_tg.arn
  }
}

# ===================================
# IAM ROLES (Minimal required)
# ===================================

resource "aws_iam_role" "frank_ecs_task_execution_role" {
  name = "frank-spike-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "frank_ecs_task_execution_role_policy" {
  role       = aws_iam_role.frank_ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ===================================
# CLOUDWATCH LOGS
# ===================================

resource "aws_cloudwatch_log_group" "frank_logs" {
  name              = "/ecs/frank-spike"
  retention_in_days = 3

  tags = {
    Name = "frank-spike-logs"
  }
}

# ===================================
# ECS CLUSTER
# ===================================

resource "aws_ecs_cluster" "frank_cluster" {
  name = "frank-spike-cluster"

  tags = {
    Name = "frank-spike-cluster"
  }
}

# ===================================
# ECS TASK DEFINITION
# ===================================

resource "aws_ecs_task_definition" "frank_task" {
  family                   = "frank-spike"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.frank_ecs_task_execution_role.arn

  container_definitions = jsonencode([
    {
      name  = "frank-container"
      image = "${aws_ecr_repository.frank_repo.repository_url}:latest"
      
      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "FRANK_ENVIRONMENT"
          value = "aws"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.frank_logs.name
          "awslogs-region"        = "eu-west-1"
          "awslogs-stream-prefix" = "ecs"
        }
      }

      essential = true
    }
  ])

  tags = {
    Name = "frank-spike-task"
  }
}

# ===================================
# ECS SERVICE
# ===================================

resource "aws_ecs_service" "frank_service" {
  name            = "frank-spike-service"
  cluster         = aws_ecs_cluster.frank_cluster.id
  task_definition = aws_ecs_task_definition.frank_task.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    security_groups  = [aws_security_group.frank_ecs_sg.id]
    subnets          = aws_subnet.frank_public_subnets[*].id
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.frank_tg.arn
    container_name   = "frank-container"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.frank_http_listener]

  tags = {
    Name = "frank-spike-service"
  }
}

# ===================================
# OUTPUTS
# ===================================

output "application_url" {
  description = "Application URL (HTTP only)"
  value       = "http://${aws_lb.frank_alb.dns_name}"
}

output "health_check_url" {
  description = "Health check URL"
  value       = "http://${aws_lb.frank_alb.dns_name}/health"
}

output "ecr_repository_url" {
  description = "ECR repository URL"
  value       = aws_ecr_repository.frank_repo.repository_url
}

output "alb_dns_name" {
  description = "Load balancer DNS name"
  value       = aws_lb.frank_alb.dns_name
}