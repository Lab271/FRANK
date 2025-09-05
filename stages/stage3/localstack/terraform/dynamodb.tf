# DynamoDB Tables for FRANK Platform

# Submissions table - stores raw submissions
resource "aws_dynamodb_table" "submissions" {
  name           = "${var.project_name}-submissions-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "submission_id"

  attribute {
    name = "submission_id"
    type = "S"
  }

  attribute {
    name = "tenant_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  # GSI for tenant queries
  global_secondary_index {
    name           = "tenant-timestamp-index"
    hash_key       = "tenant_id"
    range_key      = "timestamp"
    projection_type = "ALL"
  }

  tags = local.common_tags
}

# Aggregates table - stores aggregated statistics
resource "aws_dynamodb_table" "aggregates" {
  name           = "${var.project_name}-aggregates-${var.environment}"
  billing_mode   = "PAY_PER_REQUEST"
  hash_key       = "pk"
  range_key      = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "gsi1_pk"
    type = "S"
  }

  attribute {
    name = "gsi1_sk"
    type = "S"
  }

  # GSI for sector-based queries
  global_secondary_index {
    name           = "sector-index"
    hash_key       = "gsi1_pk"
    range_key      = "gsi1_sk"
    projection_type = "ALL"
  }

  tags = local.common_tags
}
