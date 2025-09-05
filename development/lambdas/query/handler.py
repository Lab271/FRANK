import json
import os
from datetime import datetime, timezone

def lambda_handler(event, context):
    """Simple query handler for testing"""
    try:
        print(f"Received event: {json.dumps(event, default=str)}")
        
        # Parse request
        path = event.get('path', '')
        query_params = event.get('queryStringParameters') or {}
        
        # Route to appropriate handler
        if path.endswith('/stats'):
            response = {
                'query': query_params,
                'statistics': {
                    'total_sightings': 0,
                    'unique_sources': 0,
                    'time_range_hours': 24
                },
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
        elif path.endswith('/sighting'):
            response = {
                'query': query_params,
                'sightings': [],
                'total_count': 0,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'not_found'})
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
