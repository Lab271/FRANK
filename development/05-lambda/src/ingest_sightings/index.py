import json

def handler(event, context):
    """
    FRANK Ingest Sightings Lambda Function
    Processes incoming security sightings
    """
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Ingest sightings placeholder'})
    }