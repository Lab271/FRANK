# FRANK Database Connection Guide

## 🗃️ Database Connection Options

Your FRANK LocalStack environment uses **DynamoDB** for data storage. Here are multiple ways to connect and view your data:

## 1. 🌐 **DynamoDB Admin Web Interface** (Recommended)

**Access URL:** http://localhost:8001

This provides a graphical interface to:
- Browse tables and data
- Create, edit, and delete items
- View table schemas
- Query and scan tables

**Tables:**
- `frank-submissions-local` - Threat intelligence submissions
- `frank-aggregates-local` - Aggregated statistics

## 2. 🖥️ **AWS CLI Commands**

### View Tables
```bash
cd /Users/bjenniskens/Developer/FRANK/development
docker exec -it frank-localstack aws --endpoint-url=http://localhost:4566 dynamodb list-tables
```

### Scan Submissions Table
```bash
docker exec -it frank-localstack aws --endpoint-url=http://localhost:4566 dynamodb scan --table-name frank-submissions-local
```

### Scan Aggregates Table
```bash
docker exec -it frank-localstack aws --endpoint-url=http://localhost:4566 dynamodb scan --table-name frank-aggregates-local
```

### Query by Submission ID
```bash
docker exec -it frank-localstack aws --endpoint-url=http://localhost:4566 dynamodb get-item \
  --table-name frank-submissions-local \
  --key '{"submission_id":{"S":"YOUR_SUBMISSION_ID"}}'
```

### Query by Tenant and Time Range
```bash
docker exec -it frank-localstack aws --endpoint-url=http://localhost:4566 dynamodb query \
  --table-name frank-submissions-local \
  --index-name tenant-timestamp-index \
  --key-condition-expression "tenant_id = :tenant" \
  --expression-attribute-values '{":tenant":{"S":"YOUR_TENANT_ID"}}'
```

## 3. 🐍 **Python Script for Database Access**

```python
import boto3
import json
from datetime import datetime

# Configure boto3 for LocalStack
dynamodb = boto3.resource(
    'dynamodb',
    endpoint_url='http://localhost:4566',
    region_name='eu-west-1',
    aws_access_key_id='test',
    aws_secret_access_key='test'
)

# Access tables
submissions_table = dynamodb.Table('frank-submissions-local')
aggregates_table = dynamodb.Table('frank-aggregates-local')

# Scan all submissions
response = submissions_table.scan()
print("Submissions:", json.dumps(response['Items'], indent=2, default=str))

# Scan all aggregates
response = aggregates_table.scan()
print("Aggregates:", json.dumps(response['Items'], indent=2, default=str))
```

## 4. 📊 **DBeaver Connection (NoSQL Plugin)**

If you want to use DBeaver specifically:

1. **Install DBeaver NoSQL Plugin**
   - Go to Help → Install New Software
   - Add repository: https://dbeaver.io/update/nosql/latest/
   - Install "DBeaver NoSQL Support"

2. **Create DynamoDB Connection**
   - New Database Connection → NoSQL → DynamoDB
   - Connection settings:
     - **Endpoint:** http://localhost:4566
     - **Region:** eu-west-1
     - **Access Key:** test
     - **Secret Key:** test

## 5. 🔍 **Database Schema**

### frank-submissions-local
```
Primary Key: submission_id (String)
Global Secondary Index: tenant-timestamp-index
  - Hash Key: tenant_id (String)
  - Range Key: timestamp (String)

Attributes:
- submission_id: Unique identifier
- tenant_id: Organization identifier
- timestamp: ISO 8601 timestamp
- submission_data: JSON blob with threat intel data
```

### frank-aggregates-local
```
Primary Key: pk (String), sk (String)
Global Secondary Index: sector-index
  - Hash Key: gsi1_pk (String)
  - Range Key: gsi1_sk (String)

Attributes:
- pk: Partition key (e.g., SECTOR#finance)
- sk: Sort key (e.g., STATS#24h)
- gsi1_pk/gsi1_sk: GSI keys for sector-based queries
- aggregate_data: JSON blob with statistics
```

## 🚀 **Quick Start**

1. **Open DynamoDB Admin:** http://localhost:8001
2. **Submit data via Postman** using the collection you imported
3. **Refresh the web interface** to see new data
4. **Explore tables** and query capabilities

## 🛠️ **Troubleshooting**

If DynamoDB Admin doesn't show tables:
```bash
# Restart the admin interface
cd /Users/bjenniskens/Developer/FRANK/development/localstack
docker-compose -f docker-compose.db-admin.yml restart
```

If LocalStack isn't running:
```bash
cd /Users/bjenniskens/Developer/FRANK/development/localstack
docker-compose up -d
```

## 📝 **Sample Queries**

Check the `development/scripts/` folder for additional database query examples and utilities.
