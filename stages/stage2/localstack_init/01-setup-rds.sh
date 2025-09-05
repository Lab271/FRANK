# ================================
# localstack_init/01-setup-rds.sh - LocalStack RDS Initialization
# ================================
#!/bin/bash

echo "Initializing LocalStack RDS for FRANK Stage 2..."

# Wait for LocalStack to be ready
sleep 15

# Create RDS MySQL instance
echo "Creating RDS MySQL instance..."
awslocal rds create-db-instance \
    --db-instance-identifier frank-dev \
    --db-instance-class db.t3.micro \
    --engine mysql \
    --engine-version 8.0.28 \
    --master-username frank_user \
    --master-user-password frank_pass \
    --db-name frank \
    --allocated-storage 20 \
    --storage-type gp2 \
    --publicly-accessible \
    --port 3306

# Wait for RDS instance to be available
echo "Waiting for RDS instance to be available..."
awslocal rds wait db-instance-available --db-instance-identifier frank-dev

# Get the RDS endpoint
RDS_ENDPOINT=$(awslocal rds describe-db-instances --db-instance-identifier frank-dev --query 'DBInstances[0].Endpoint.Address' --output text)
echo "RDS endpoint: $RDS_ENDPOINT"

# Create S3 bucket for future use
echo "Creating S3 bucket for future stages..."
awslocal s3 mb s3://frank-raw-dev

# Create IAM role for RDS access (for future use)
echo "Creating IAM role for RDS access..."
awslocal iam create-role \
    --role-name FrankRDSAccessRole \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {"Service": "lambda.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }
        ]
    }'

echo "LocalStack RDS initialization complete!"
echo "Connect to RDS at: $RDS_ENDPOINT:3306"
echo "Database: frank"
echo "Username: frank_user"
echo "Password: frank_pass"