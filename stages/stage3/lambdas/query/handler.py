import json
import boto3
import os
from datetime import datetime, timezone
from boto3.dynamodb.conditions import Key

def lambda_handler(event, context):
    """
    Lambda handler for threat intelligence queries with DynamoDB access
    """
    print(f"Received event: {json.dumps(event, default=str)}")
    
    # Initialize AWS clients for LocalStack
    dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')
    
    try:
        # Get path to determine endpoint
        path = event.get('path', '')
        query_params = event.get('queryStringParameters') or {}
        
        if '/stats' in path:
            return handle_stats_query(dynamodb, query_params)
        elif '/sighting' in path:
            return handle_sighting_query(dynamodb, query_params)
        else:
            return {
                'statusCode': 404,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({'error': 'endpoint_not_found'})
            }
            
    except Exception as e:
        print(f"Error processing query: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'error': 'Internal server error',
                'message': str(e)
            })
        }

def handle_stats_query(dynamodb, query_params):
    """Handle statistics queries"""
    try:
        submissions_table = dynamodb.Table(os.environ.get('SUBMISSIONS_TABLE', 'frank-submissions-local'))
        
        # Get parameters
        sector = query_params.get('sector')
        time_range = query_params.get('time_range', '24h')
        
        # Scan submissions table for stats
        scan_kwargs = {}
        if sector:
            scan_kwargs['FilterExpression'] = Key('sector').eq(sector)
            
        response = submissions_table.scan(**scan_kwargs)
        items = response['Items']
        
        # Calculate statistics
        total_sightings = len(items)
        unique_sources = len(set(item.get('tenant_id', 'unknown') for item in items))
        
        # Get confidence distribution
        confidence_levels = [item.get('confidence', 0) for item in items if item.get('confidence')]
        avg_confidence = sum(confidence_levels) / len(confidence_levels) if confidence_levels else 0
        
        # Get sector distribution
        sectors = {}
        for item in items:
            item_sector = item.get('sector', 'unknown')
            sectors[item_sector] = sectors.get(item_sector, 0) + 1
        
        stats_response = {
            "query": {
                "sector": sector,
                "time_range": time_range
            },
            "statistics": {
                "total_sightings": total_sightings,
                "unique_sources": unique_sources,
                "average_confidence": round(avg_confidence, 2),
                "time_range_hours": parse_time_range(time_range),
                "sector_distribution": sectors
            },
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(stats_response)
        }
        
    except Exception as e:
        print(f"Error in stats query: {str(e)}")
        raise

def handle_sighting_query(dynamodb, query_params):
    """Handle sighting queries"""
    try:
        submissions_table = dynamodb.Table(os.environ.get('SUBMISSIONS_TABLE', 'frank-submissions-local'))
        
        # Get parameters
        limit = int(query_params.get('limit', 10))
        confidence_min = query_params.get('confidence_min')
        sector = query_params.get('sector')
        
        # Scan submissions table
        scan_kwargs = {
            'Limit': limit
        }
        
        # Apply filters
        filter_expressions = []
        expression_values = {}
        
        if confidence_min:
            filter_expressions.append('confidence >= :min_conf')
            expression_values[':min_conf'] = int(confidence_min)
            
        if sector:
            filter_expressions.append('sector = :sector')
            expression_values[':sector'] = sector
            
        if filter_expressions:
            scan_kwargs['FilterExpression'] = ' AND '.join(filter_expressions)
            scan_kwargs['ExpressionAttributeValues'] = expression_values
        
        response = submissions_table.scan(**scan_kwargs)
        items = response['Items']
        
        # Format sightings
        sightings = []
        for item in items:
            submission_data = item.get('submission_data', {})
            sighting_data = submission_data.get('sighting', {})
            
            sightings.append({
                'submission_id': item.get('submission_id'),
                'sighting_id': sighting_data.get('sighting_id'),
                'timestamp': item.get('timestamp'),
                'confidence': item.get('confidence', 0),
                'sector': item.get('sector'),
                'submitter_tier': item.get('access_level'),
                'observables': sighting_data.get('observables', {})
            })
        
        sighting_response = {
            "query": dict(query_params),
            "sightings": sightings,
            "total_count": len(sightings),
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps(sighting_response)
        }
        
    except Exception as e:
        print(f"Error in sighting query: {str(e)}")
        raise

def parse_time_range(time_range):
    """Parse time range string to hours"""
    if time_range.endswith('h'):
        return int(time_range[:-1])
    elif time_range.endswith('d'):
        return int(time_range[:-1]) * 24
    elif time_range.endswith('w'):
        return int(time_range[:-1]) * 24 * 7
    else:
        return 24  # Default to 24 hours
