# ===================================
# minimal_dynamodb_app.py
# Minimal DynamoDB + LocalStack + FastAPI Prototype
# ===================================

import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional

import boto3
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# ===================================
# CONFIGURATION
# ===================================

DYNAMODB_ENDPOINT = os.getenv('DYNAMODB_ENDPOINT', 'http://localhost:4566')
AWS_REGION = os.getenv('AWS_DEFAULT_REGION', 'eu-west-1')
TABLE_NAME = os.getenv('DYNAMODB_TABLE', 'simple-records')
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID', 'test')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY', 'test')

# ===================================
# PYDANTIC MODELS
# ===================================

class RecordCreate(BaseModel):
    name: str
    data: str
    category: Optional[str] = "general"

class RecordResponse(BaseModel):
    id: str
    name: str
    data: str
    category: str
    created_at: str

# ===================================
# DYNAMODB CLIENT
# ===================================

class DynamoDBClient:
    def __init__(self):
        self.dynamodb = boto3.resource(
            'dynamodb',
            endpoint_url=DYNAMODB_ENDPOINT,
            region_name=AWS_REGION,
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY
        )
        self.table_name = TABLE_NAME
        self.table = None
        self._ensure_table()

    def _ensure_table(self):
        """Create table if it doesn't exist"""
        try:
            # Try to get table
            self.table = self.dynamodb.Table(self.table_name)
            self.table.load()
            print(f"✅ Table '{self.table_name}' already exists")
        except self.dynamodb.meta.client.exceptions.ResourceNotFoundException:
            # Create table
            print(f"🔨 Creating table '{self.table_name}'...")
            self.table = self.dynamodb.create_table(
                TableName=self.table_name,
                KeySchema=[
                    {
                        'AttributeName': 'id',
                        'KeyType': 'HASH'  # Partition key
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'id',
                        'AttributeType': 'S'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )

            # Wait for table to be created
            self.table.meta.client.get_waiter('table_exists').wait(TableName=self.table_name)
            print(f"✅ Table '{self.table_name}' created successfully")

    def create_record(self, record: RecordCreate) -> RecordResponse:
        """Create a new record"""
        record_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()

        item = {
            'id': record_id,
            'name': record.name,
            'data': record.data,
            'category': record.category,
            'created_at': timestamp
        }

        try:
            self.table.put_item(Item=item)
            return RecordResponse(**item)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create record: {str(e)}")

    def get_record(self, record_id: str) -> RecordResponse:
        """Get a record by ID"""
        try:
            response = self.table.get_item(Key={'id': record_id})

            if 'Item' not in response:
                raise HTTPException(status_code=404, detail="Record not found")

            return RecordResponse(**response['Item'])
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get record: {str(e)}")

    def list_records(self) -> List[RecordResponse]:
        """List all records"""
        try:
            response = self.table.scan()
            items = response.get('Items', [])
            return [RecordResponse(**item) for item in items]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to list records: {str(e)}")

    def delete_record(self, record_id: str) -> Dict[str, str]:
        """Delete a record by ID"""
        try:
            # Check if record exists first
            self.get_record(record_id)  # This will raise 404 if not found

            self.table.delete_item(Key={'id': record_id})
            return {"message": f"Record {record_id} deleted successfully"}
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to delete record: {str(e)}")

# ===================================
# FASTAPI APPLICATION
# ===================================

app = FastAPI(
    title="Minimal DynamoDB API",
    description="Simple FastAPI + DynamoDB LocalStack prototype",
    version="1.0.0"
)

# Initialize DynamoDB client
db_client = DynamoDBClient()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Minimal DynamoDB API is running!",
        "table": TABLE_NAME,
        "endpoint": DYNAMODB_ENDPOINT
    }

@app.post("/records", response_model=RecordResponse)
async def create_record(record: RecordCreate):
    """Create a new record"""
    return db_client.create_record(record)

@app.get("/records", response_model=List[RecordResponse])
async def list_records():
    """List all records"""
    return db_client.list_records()

@app.get("/records/{record_id}", response_model=RecordResponse)
async def get_record(record_id: str):
    """Get a specific record"""
    return db_client.get_record(record_id)

@app.delete("/records/{record_id}")
async def delete_record(record_id: str):
    """Delete a specific record"""
    return db_client.delete_record(record_id)

@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        # Test DynamoDB connection
        db_client.table.load()
        dynamodb_status = "healthy"
    except Exception as e:
        dynamodb_status = f"unhealthy: {str(e)}"

    return {
        "status": "ok" if dynamodb_status == "healthy" else "error",
        "dynamodb": dynamodb_status,
        "table_name": TABLE_NAME,
        "endpoint": DYNAMODB_ENDPOINT
    }

# ===================================
# MAIN
# ===================================

if __name__ == "__main__":
    print("🚀 Starting Minimal DynamoDB API...")
    print(f"📊 DynamoDB endpoint: {DYNAMODB_ENDPOINT}")
    print(f"🗃️  Table name: {TABLE_NAME}")
    print(f"🌍 Region: {AWS_REGION}")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
