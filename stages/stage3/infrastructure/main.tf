# ================================
# FRANK Platform Stage 3 - MINIMAL AWS Setup
# Just FastAPI + DynamoDB on AWS
# ================================

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project   = "FRANK-Platform"
      Stage     = "3-minimal"
      ManagedBy = "OpenTofu"
    }
  }
}

# ================================
# VARIABLES
# ================================

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

# ================================
# DATA SOURCES
# ================================

data "aws_caller_identity" "current" {}

# ================================
# DYNAMODB TABLE
# ================================

# KMS Key for DynamoDB encryption (matching SSESpecification)
resource "aws_kms_key" "frank_dynamodb" {
  description             = "KMS key for FRANK DynamoDB table encryption"
  deletion_window_in_days = 7
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow DynamoDB Service"
        Effect = "Allow"
        Principal = {
          Service = "dynamodb.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })
  
  tags = {
    Application        = "FRANK"
    Environment        = "development"
    DataClassification = "confidential"
  }
}

resource "aws_kms_alias" "frank_dynamodb" {
  name          = "alias/${var.project_name}-dynamodb"
  target_key_id = aws_kms_key.frank_dynamodb.key_id
}



resource "aws_dynamodb_table" "frank" {
  name         = "${var.project_name}-table"  # Matching your exact table name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"  # Uppercase to match your definition
  range_key    = "SK"  # Uppercase to match your definition
  
  # Attribute definitions matching your boto3 config
  attribute {
    name = "PK"
    type = "S"
  }
  
  attribute {
    name = "SK"
    type = "S"
  }
  
  attribute {
    name = "GSI1PK"  # Uppercase to match your definition
    type = "S"
  }
  
  attribute {
    name = "GSI1SK"  # Uppercase to match your definition
    type = "S"
  }
  
  # Global Secondary Index matching your definition
  global_secondary_index {
    name               = "GSI1"
    hash_key           = "GSI1PK"  # Uppercase to match your definition
    range_key          = "GSI1SK"  # Uppercase to match your definition
    projection_type    = "ALL"
  }
  
    # Server-side encryption matching your SSESpecification
  server_side_encryption {
    enabled = true
  }



  # Tags matching your boto3 definition
  tags = {
    Name = "${var.project_name}-dynamodb-table"
    Application        = "FRANK"
    Environment        = "development"
    DataClassification = "confidential"
  }
}

resource "aws_dynamodb_table" "frank_audit" {
  name         = "${var.project_name}-audit-table"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"  # Uppercase to match your definition
  range_key    = "SK"  # Uppercase to match your definition
  
  # Attribute definitions matching your boto3 config
  attribute {
    name = "PK"
    type = "S"
  }
  
  attribute {
    name = "SK"
    type = "S"
  }
  
  attribute {
    name = "GSI1PK"  # Uppercase to match your definition
    type = "S"
  }
  
  attribute {
    name = "GSI1SK"  # Uppercase to match your definition
    type = "S"
  }
  
  # Global Secondary Index matching your definition
  global_secondary_index {
    name               = "GSI1"
    hash_key           = "GSI1PK"  # Uppercase to match your definition
    range_key          = "GSI1SK"  # Uppercase to match your definition
    projection_type    = "ALL"
  }
  
  # Server-side encryption matching your SSESpecification
  server_side_encryption {
    enabled     = true
  }

  tags = {
    Name = "${var.project_name}-audit-dynamodb-table"
    Application        = "FRANK"
    Environment        = "development"
    DataClassification = "confidential"
  }
}

# ================================
# IAM ROLE FOR LOCAL DEVELOPMENT
# ================================

resource "aws_iam_user" "frank_app" {
  name = "${var.project_name}-app-user"
  
  tags = {
    Name = "${var.project_name}-app-user"
  }
}

resource "aws_iam_user_policy" "frank_app_dynamodb" {
  name = "${var.project_name}-app-dynamodb-policy"
  user = aws_iam_user.frank_app.name
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem",
          "dynamodb:DescribeTable"
        ]
        Resource = [
          aws_dynamodb_table.frank.arn,
          "${aws_dynamodb_table.frank.arn}/index/*",
          aws_dynamodb_table.frank_audit.arn,
          "${aws_dynamodb_table.frank_audit.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = aws_kms_key.frank_dynamodb.arn
      }
    ]
  })
}

resource "aws_iam_access_key" "frank_app" {
  user = aws_iam_user.frank_app.name
}

# ================================
# OUTPUTS
# ================================

output "dynamodb_table_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.frank.name
}

output "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table"
  value       = aws_dynamodb_table.frank.arn
}

output "dynamodb_table_audit_name" {
  description = "Name of the DynamoDB table"
  value       = aws_dynamodb_table.frank_audit.name
}

output "dynamodb_table_audit_arn" {
  description = "ARN of the DynamoDB table"
  value       = aws_dynamodb_table.frank_audit.arn
}

output "aws_region" {
  description = "AWS region"
  value       = var.aws_region
}

output "aws_access_key_id" {
  description = "AWS Access Key ID for the application"
  value       = aws_iam_access_key.frank_app.id
}

output "aws_secret_access_key" {
  description = "AWS Secret Access Key for the application"
  value       = aws_iam_access_key.frank_app.secret
  sensitive   = true
}

output "application_config" {
  description = "Configuration for running the application"
  value = {
    AWS_DEFAULT_REGION     = var.aws_region
    DYNAMODB_TABLE         = aws_dynamodb_table.frank.name
    DYNAMODB_AUDIT_TABLE   = aws_dynamodb_table.frank_audit.name
    AWS_ACCESS_KEY_ID      = aws_iam_access_key.frank_app.id
    AWS_SECRET_ACCESS_KEY  = aws_iam_access_key.frank_app.secret
  }
  sensitive = true
}