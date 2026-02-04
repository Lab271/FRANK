#!/usr/bin/env python3
"""
Simple DynamoDB test script to retrieve all records from frank-audit table.

This script uses hardcoded AWS credentials to connect to LocalStack
and retrieves all records from the frank-audit table.

Usage:
    python test_dynamodb.py
"""

import json
from datetime import datetime

import boto3


def main():
    """Main function to retrieve and print all records from frank-audit table"""

    # Hardcoded configuration
    TABLE_NAME = "frank-data"
    ENDPOINT_URL = "http://localhost:4566"
    REGION = "eu-west-1"

    print("🔌 Connecting to DynamoDB...")
    print(f"   Endpoint: {ENDPOINT_URL}")
    print(f"   Table: {TABLE_NAME}")
    print(f"   Region: {REGION}")
    print()

    try:
        session = boto3.Session(profile_name="localstack")
        dynamodb = session.resource("dynamodb", region_name=REGION, endpoint_url=ENDPOINT_URL)
        dynamodb_client = session.client("dynamodb", region_name=REGION, endpoint_url=ENDPOINT_URL)

        # List all tables first
        print("📋 Listing all tables in database...")
        response = dynamodb_client.list_tables()
        table_names = response.get('TableNames', [])

        if not table_names:
            print("⚠️  No tables found in the database")
            return 1
        else:
            print(f"📊 Found {len(table_names)} tables:")
            for i, name in enumerate(table_names, 1):
                print(f"   {i}. {name}")
        print()

        # Check if our target table exists
        if TABLE_NAME not in table_names:
            print(f"❌ Table '{TABLE_NAME}' not found!")
            print(f"💡 Available tables: {', '.join(table_names)}")
            return 1

        # Get table reference
        table = dynamodb.Table(TABLE_NAME)

        print("📊 Table information:")
        table_info = table.table_status
        print(f"   Status: {table_info}")
        print()

        # Scan all records from the table
        print(f"🔍 Scanning all records from {TABLE_NAME}...")

        response = table.scan()
        items = response.get('Items', [])

        print(f"📈 Found {len(items)} records")
        print("=" * 50)

        if not items:
            print("⚠️  No records found in the table")
        else:
            # Print each record
            for i, item in enumerate(items, 1):
                print(f"\n📝 Record {i}:")
                print(json.dumps(item, indent=2, default=str, sort_keys=True))
                print("-" * 30)

        # Handle pagination if there are more results
        while 'LastEvaluatedKey' in response:
            print("\n🔄 Fetching more records...")
            response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
            additional_items = response.get('Items', [])

            for i, item in enumerate(additional_items, len(items) + 1):
                print(f"\n📝 Record {i}:")
                print(json.dumps(item, indent=2, default=str, sort_keys=True))
                print("-" * 30)

            items.extend(additional_items)

        print(f"\n✅ Total records retrieved: {len(items)}")

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        print(f"💡 Make sure LocalStack is running on {ENDPOINT_URL}")
        print(f"💡 Make sure the table '{TABLE_NAME}' exists")
        return 1

    return 0


if __name__ == "__main__":
    print("🚀 DynamoDB Table Scanner")
    print(f"📅 Started at: {datetime.now().isoformat()}")
    print("=" * 50)

    exit_code = main()

    print("=" * 50)
    print(f"📅 Finished at: {datetime.now().isoformat()}")
    exit(exit_code)
