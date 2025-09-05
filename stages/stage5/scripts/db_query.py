#!/usr/bin/env python3
"""
FRANK Database Query Tool
Easy database access for FRANK LocalStack DynamoDB tables
"""

import boto3
import json
import sys
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

class FrankDBClient:
    def __init__(self):
        """Initialize DynamoDB client for LocalStack"""
        self.dynamodb = boto3.resource(
            'dynamodb',
            endpoint_url='http://localhost:4566',
            region_name='eu-west-1',
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        
        try:
            self.submissions_table = self.dynamodb.Table('frank-submissions-local')
            self.aggregates_table = self.dynamodb.Table('frank-aggregates-local')
        except Exception as e:
            print(f"Error connecting to DynamoDB: {e}")
            print("Make sure LocalStack is running!")
            sys.exit(1)
    
    def list_tables(self):
        """List all DynamoDB tables"""
        client = boto3.client(
            'dynamodb',
            endpoint_url='http://localhost:4566',
            region_name='eu-west-1',
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        
        try:
            response = client.list_tables()
            return response['TableNames']
        except ClientError as e:
            print(f"Error listing tables: {e}")
            return []
    
    def get_all_submissions(self, limit=None):
        """Get all submissions from the database"""
        try:
            if limit:
                response = self.submissions_table.scan(Limit=limit)
            else:
                response = self.submissions_table.scan()
            return response['Items']
        except ClientError as e:
            print(f"Error scanning submissions: {e}")
            return []
    
    def get_submission_by_id(self, submission_id):
        """Get a specific submission by ID"""
        try:
            response = self.submissions_table.get_item(
                Key={'submission_id': submission_id}
            )
            return response.get('Item')
        except ClientError as e:
            print(f"Error getting submission {submission_id}: {e}")
            return None
    
    def get_submissions_by_tenant(self, tenant_id, limit=10):
        """Get submissions for a specific tenant"""
        try:
            response = self.submissions_table.query(
                IndexName='tenant-timestamp-index',
                KeyConditionExpression=boto3.dynamodb.conditions.Key('tenant_id').eq(tenant_id),
                Limit=limit,
                ScanIndexForward=False  # Most recent first
            )
            return response['Items']
        except ClientError as e:
            print(f"Error querying submissions for tenant {tenant_id}: {e}")
            return []
    
    def get_all_aggregates(self, limit=None):
        """Get all aggregates from the database"""
        try:
            if limit:
                response = self.aggregates_table.scan(Limit=limit)
            else:
                response = self.aggregates_table.scan()
            return response['Items']
        except ClientError as e:
            print(f"Error scanning aggregates: {e}")
            return []
    
    def get_table_info(self, table_name):
        """Get detailed information about a table"""
        client = boto3.client(
            'dynamodb',
            endpoint_url='http://localhost:4566',
            region_name='eu-west-1',
            aws_access_key_id='test',
            aws_secret_access_key='test'
        )
        
        try:
            response = client.describe_table(TableName=table_name)
            return response['Table']
        except ClientError as e:
            print(f"Error describing table {table_name}: {e}")
            return None

def print_json(data, title=""):
    """Pretty print JSON data"""
    if title:
        print(f"\n=== {title} ===")
    print(json.dumps(data, indent=2, default=str))

def main():
    """Main CLI interface"""
    print("🗃️  FRANK Database Query Tool")
    print("=" * 40)
    
    db = FrankDBClient()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python db_query.py tables                    # List all tables")
        print("  python db_query.py submissions [limit]       # Get all submissions")
        print("  python db_query.py submission <id>           # Get submission by ID")
        print("  python db_query.py tenant <tenant_id>        # Get submissions by tenant")
        print("  python db_query.py aggregates [limit]        # Get all aggregates")
        print("  python db_query.py info <table_name>         # Get table info")
        return
    
    command = sys.argv[1].lower()
    
    if command == "tables":
        tables = db.list_tables()
        print_json(tables, "Available Tables")
    
    elif command == "submissions":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        submissions = db.get_all_submissions(limit)
        print_json(submissions, f"Submissions (limit: {limit or 'none'})")
    
    elif command == "submission":
        if len(sys.argv) < 3:
            print("Please provide submission ID")
            return
        submission_id = sys.argv[2]
        submission = db.get_submission_by_id(submission_id)
        if submission:
            print_json(submission, f"Submission: {submission_id}")
        else:
            print(f"Submission {submission_id} not found")
    
    elif command == "tenant":
        if len(sys.argv) < 3:
            print("Please provide tenant ID")
            return
        tenant_id = sys.argv[2]
        submissions = db.get_submissions_by_tenant(tenant_id)
        print_json(submissions, f"Submissions for tenant: {tenant_id}")
    
    elif command == "aggregates":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
        aggregates = db.get_all_aggregates(limit)
        print_json(aggregates, f"Aggregates (limit: {limit or 'none'})")
    
    elif command == "info":
        if len(sys.argv) < 3:
            print("Please provide table name")
            return
        table_name = sys.argv[2]
        info = db.get_table_info(table_name)
        if info:
            print_json(info, f"Table Info: {table_name}")
        else:
            print(f"Table {table_name} not found")
    
    else:
        print(f"Unknown command: {command}")

if __name__ == "__main__":
    main()
