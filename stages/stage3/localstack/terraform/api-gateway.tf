# API Gateway for FRANK Platform

# REST API
resource "aws_api_gateway_rest_api" "frank_api" {
  name        = "${var.project_name}-api-${var.environment}"
  description = "FRANK Threat Intelligence API"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = local.common_tags
}

# API Key
resource "aws_api_gateway_api_key" "frank_api_key" {
  name        = "${var.project_name}-api-key-${var.environment}"
  description = "API key for FRANK threat intelligence platform"
  enabled     = true

  tags = local.common_tags
}

# Usage Plan
resource "aws_api_gateway_usage_plan" "frank_usage_plan" {
  name         = "${var.project_name}-usage-plan-${var.environment}"
  description  = "Usage plan for FRANK API"

  api_stages {
    api_id = aws_api_gateway_rest_api.frank_api.id
    stage  = aws_api_gateway_deployment.frank_deployment.stage_name
  }

  quota_settings {
    limit  = 1000
    period = "DAY"
  }

  throttle_settings {
    rate_limit  = 100
    burst_limit = 200
  }

  tags = local.common_tags
}

# Usage Plan Key
resource "aws_api_gateway_usage_plan_key" "frank_usage_plan_key" {
  key_id        = aws_api_gateway_api_key.frank_api_key.id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.frank_usage_plan.id
}

# Request Validator
resource "aws_api_gateway_request_validator" "frank_validator" {
  name                        = "frank-validator"
  rest_api_id                 = aws_api_gateway_rest_api.frank_api.id
  validate_request_body       = true
  validate_request_parameters = true
}

# Resources
resource "aws_api_gateway_resource" "v1" {
  rest_api_id = aws_api_gateway_rest_api.frank_api.id
  parent_id   = aws_api_gateway_rest_api.frank_api.root_resource_id
  path_part   = "v1"
}

resource "aws_api_gateway_resource" "submission" {
  rest_api_id = aws_api_gateway_rest_api.frank_api.id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "submission"
}

resource "aws_api_gateway_resource" "sighting" {
  rest_api_id = aws_api_gateway_rest_api.frank_api.id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "sighting"
}

resource "aws_api_gateway_resource" "stats" {
  rest_api_id = aws_api_gateway_rest_api.frank_api.id
  parent_id   = aws_api_gateway_resource.v1.id
  path_part   = "stats"
}

# Methods
resource "aws_api_gateway_method" "submission_post" {
  rest_api_id          = aws_api_gateway_rest_api.frank_api.id
  resource_id          = aws_api_gateway_resource.submission.id
  http_method          = "POST"
  authorization        = "NONE"
  api_key_required     = true
  request_validator_id = aws_api_gateway_request_validator.frank_validator.id
}

resource "aws_api_gateway_method" "sighting_get" {
  rest_api_id      = aws_api_gateway_rest_api.frank_api.id
  resource_id      = aws_api_gateway_resource.sighting.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true
}

resource "aws_api_gateway_method" "stats_get" {
  rest_api_id      = aws_api_gateway_rest_api.frank_api.id
  resource_id      = aws_api_gateway_resource.stats.id
  http_method      = "GET"
  authorization    = "NONE"
  api_key_required = true
}

# Integrations
resource "aws_api_gateway_integration" "submission_integration" {
  rest_api_id             = aws_api_gateway_rest_api.frank_api.id
  resource_id             = aws_api_gateway_resource.submission.id
  http_method             = aws_api_gateway_method.submission_post.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.ingest.invoke_arn
}

resource "aws_api_gateway_integration" "sighting_integration" {
  rest_api_id             = aws_api_gateway_rest_api.frank_api.id
  resource_id             = aws_api_gateway_resource.sighting.id
  http_method             = aws_api_gateway_method.sighting_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.query.invoke_arn
}

resource "aws_api_gateway_integration" "stats_integration" {
  rest_api_id             = aws_api_gateway_rest_api.frank_api.id
  resource_id             = aws_api_gateway_resource.stats.id
  http_method             = aws_api_gateway_method.stats_get.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = aws_lambda_function.query.invoke_arn
}

# Deployment
resource "aws_api_gateway_deployment" "frank_deployment" {
  rest_api_id = aws_api_gateway_rest_api.frank_api.id
  stage_name  = var.environment

  depends_on = [
    aws_api_gateway_method.submission_post,
    aws_api_gateway_method.sighting_get,
    aws_api_gateway_method.stats_get,
    aws_api_gateway_integration.submission_integration,
    aws_api_gateway_integration.sighting_integration,
    aws_api_gateway_integration.stats_integration
  ]
}
