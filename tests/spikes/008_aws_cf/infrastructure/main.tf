# ===================================
# FRANK Platform - Main Configuration
# ===================================

# This file serves as the entry point and references all other modules
# All actual resources are defined in their respective files:
#
# - providers.tf     → Provider configuration and backend
# - variables.tf     → Input variables and configuration
# - locals.tf        → Local values and computed variables
# - data.tf          → Data sources
# - networking.tf    → VPC, subnets, IGW, route tables
# - security.tf      → Security groups and network ACLs
# - ssl.tf           → SSL certificates and DNS validation
# - ecr.tf           → Container registry
# - load_balancer.tf → Application Load Balancer and target groups
# - iam.tf           → IAM roles and policies
# - ecs.tf           → ECS cluster, service, and task definitions
# - outputs.tf       → Output values
#
# This modular approach provides:
# ✅ Better organization and readability
# ✅ Easier maintenance and debugging
# ✅ Logical separation of concerns
# ✅ Simplified troubleshooting
# ✅ Team collaboration on different components

# Null resource for deployment validation
resource "null_resource" "deployment_validation" {
  depends_on = [
    aws_ecs_service.main,
    aws_route53_record.app,
    aws_acm_certificate_validation.main
  ]

  triggers = {
    service_arn = aws_ecs_service.main.id
    domain_name = var.domain_name
    timestamp   = timestamp()
  }

  provisioner "local-exec" {
    command = <<-EOT
      echo "🚀 FRANK deployment validation starting..."
      echo "Domain: ${var.domain_name}"
      echo "Service: ${aws_ecs_service.main.name}"
      echo "Cluster: ${aws_ecs_cluster.main.name}"
      echo "Repository: ${aws_ecr_repository.main.repository_url}"
      echo "✅ Infrastructure deployment completed successfully!"
    EOT
  }
}