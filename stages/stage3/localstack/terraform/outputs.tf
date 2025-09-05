# Terraform Outputs

output "api_gateway_id" {
  description = "ID of the API Gateway"
  value       = aws_api_gateway_rest_api.frank_api.id
}

output "api_gateway_url" {
  description = "URL of the API Gateway"
  value       = aws_api_gateway_rest_api.frank_api.execution_arn
}

output "api_key" {
  description = "API Key for authentication"
  value       = aws_api_gateway_api_key.frank_api_key.value
  sensitive   = true
}

output "submissions_table" {
  description = "Name of the submissions DynamoDB table"
  value       = aws_dynamodb_table.submissions.name
}

output "aggregates_table" {
  description = "Name of the aggregates DynamoDB table"
  value       = aws_dynamodb_table.aggregates.name
}

output "raw_data_bucket" {
  description = "Name of the S3 bucket for raw data"
  value       = aws_s3_bucket.raw_data.bucket
}

output "ingest_lambda_name" {
  description = "Name of the ingest Lambda function"
  value       = aws_lambda_function.ingest.function_name
}

output "query_lambda_name" {
  description = "Name of the query Lambda function"
  value       = aws_lambda_function.query.function_name
}
