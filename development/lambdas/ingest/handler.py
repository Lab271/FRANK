import json
import boto3
import os
from datetime import datetime, timezone
import uuid

def lambda_handler(event, context):
    """
    Lambda handler that actually stores submissions in DynamoDB
    """
    print(f"Received event: {json.dumps(event, default=str)}")
    
    try:
        # Parse the request body
        if 'body' in event:
            if isinstance(event['body'], str):
                body = json.loads(event['body'])
            else:
                body = event['body']
        else:
            body = event
        
        # Generate submission ID
        submission_id = f"sub-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Initialize DynamoDB client for LocalStack with internal networking
        dynamodb = boto3.resource(
            'dynamodb',
            endpoint_url='http://localstack:4566',  # Use internal container name
            region_name='eu-west-1',
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        

        # Initialize S3 client for LocalStack
        s3 = boto3.client(
            's3',
            endpoint_url='http://localstack:4566',
            region_name='eu-west-1',
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        
        # Get table and bucket names
        table = dynamodb.Table(os.environ.get('SUBMISSIONS_TABLE', 'frank-submissions-local'))
        bucket_name = os.environ.get('RAW_DATA_BUCKET', 'frank-raw-data-local')
        
        # Store raw data in S3
        s3_key = f"submissions/{submission_id}.json"
        s3.put_object(
            Bucket=bucket_name,
            Key=s3_key,
            Body=json.dumps(body, indent=2),
            ContentType='application/json'
        )

        
        # Store in DynamoDB
        item = {
            'submission_id': submission_id,
            'timestamp': timestamp,
            'data': body,
            'status': 'processed',
            's3_location': f"s3://{bucket_name}/{s3_key}"
        }
        
        table.put_item(Item=item)
        print(f"Successfully stored submission {submission_id} in DynamoDB and S3")

        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'submission_id': submission_id,
                'status': 'received',
                'timestamp': timestamp
            })
        }
        
    except Exception as e:
        print(f"Error processing submission: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Failed to process submission',
                'details': str(e)
            })
        }
