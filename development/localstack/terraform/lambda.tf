# Lambda Functions for FRANK Platform

# IAM role for Lambda execution
resource "aws_iam_role" "lambda_execution_role" {
  name = "${var.project_name}-lambda-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = local.common_tags
}

# IAM policy for Lambda
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.project_name}-lambda-policy"
  role = aws_iam_role.lambda_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem"
        ]
        Resource = [
          aws_dynamodb_table.submissions.arn,
          aws_dynamodb_table.aggregates.arn,
          "${aws_dynamodb_table.submissions.arn}/index/*",
          "${aws_dynamodb_table.aggregates.arn}/index/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "${aws_s3_bucket.raw_data.arn}/*"
      }
    ]
  })
}

# Lambda function packages (built by build-lambdas.sh script)
# The build script creates these zip files in /tmp/

# Ingest Lambda function
resource "aws_lambda_function" "ingest" {
  filename         = "/tmp/frank-ingest.zip"
  function_name    = "${var.project_name}-ingest-${var.environment}"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "handler.lambda_handler"
  runtime         = local.lambda_runtime
  timeout         = local.lambda_timeout
  memory_size     = 512

  environment {
    variables = {
      FRANK_ENVIRONMENT     = var.environment
      SUBMISSIONS_TABLE     = aws_dynamodb_table.submissions.name
      AGGREGATES_TABLE      = aws_dynamodb_table.aggregates.name
      RAW_DATA_BUCKET      = aws_s3_bucket.raw_data.bucket
      AWS_ENDPOINT_URL     = "http://localhost:4566"
    }
  }

  tags = local.common_tags
}

# Query Lambda function
resource "aws_lambda_function" "query" {
  filename         = "/tmp/frank-query.zip"
  function_name    = "${var.project_name}-query-${var.environment}"
  role            = aws_iam_role.lambda_execution_role.arn
  handler         = "handler.lambda_handler"
  runtime         = local.lambda_runtime
  timeout         = 15
  memory_size     = 256

  environment {
    variables = {
      FRANK_ENVIRONMENT     = var.environment
      SUBMISSIONS_TABLE     = aws_dynamodb_table.submissions.name
      AGGREGATES_TABLE      = aws_dynamodb_table.aggregates.name
      AWS_ENDPOINT_URL     = "http://localhost:4566"
    }
  }

  tags = local.common_tags
}

# Lambda permissions for API Gateway
resource "aws_lambda_permission" "api_gateway_ingest" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.frank_api.execution_arn}/*/*"
}

resource "aws_lambda_permission" "api_gateway_query" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.query.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_api_gateway_rest_api.frank_api.execution_arn}/*/*"
}
