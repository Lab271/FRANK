import json
import os
import boto3
from datetime import datetime, timezone

def lambda_handler(event, context):
    """Simple ingest handler for testing"""
    try:
        print(f"Received event: {json.dumps(event, default=str)}")
        
        # Parse request body
        body = event.get('body', '{}')
        if isinstance(body, str):
            submission_data = json.loads(body)
        else:
            submission_data = body
        
        # Generate response
        submission_id = f"sub-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{hash(str(submission_data)) % 10000}"
        
        response = {
            'status': 'accepted',
            'submission_id': submission_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'message': 'Submission processed successfully'
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response)
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': 'internal_error',
                'message': str(e)
            })
        }
