# FRANK Application

An application built with FastAPI in our road towards Cloud Agnostic in several stages

## Architecture Philosophy

FRANK is developed incrementally through stages, from a minimal viable setup to a production-ready multi-AZ application with full observability. Each stage adds some major capabilities, making learning and troubleshooting straightforward.

---

## Development Stages

### Stage 1: Absolute Minimal Setup
**Goal:** Single FastAPI container accessible via public IP

Read more about the [Stage 1 - Hypothesis](../009_aws_stage1/README.md).

#### AWS Components
- Single ECS Fargate task in public subnet
- ECR for container
- Public IP with HTTP (port 80)
- Security group: allow inbound 0.0.0.0/0:80
- Access: `http://<public-ip>` or AWS hostname

#### Local Setup
```bash
# Install dependencies
pip install fastapi uvicorn

# Run application
uvicorn main:app --host 0.0.0.0 --port 8000

# Access
open http://localhost:8000
```

#### Local Container Setup
```bash
docker build -t simple_api .

docker run -d -p 8000:8000 --name simple_test simple_api

# Access
open http://localhost:8000
```

**Limitations:** IP changes on restart, no persistence, single point of failure

---

### Stage 2: Add Load Balancer
**Goal:** Stable endpoint with health checking

Read more about the [Stage 2 - Hypothesis](../009_aws_stage2/README.md).

#### AWS Components
- Application Load Balancer (ALB) in public subnet
- ALB target group → Fargate task
- Health check: `/v1/health`
- Fargate moved to private subnet
- NAT Gateway for outbound access
- Include the main FRANK python package
- Access: `http://frank-alb-xxx.region.elb.amazonaws.com`

#### Local Setup
```bash
# docker-compose.yml
services:
  fastapi:
    build: .
    ports:
      - "8000:8000"
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - fastapi

# Start services
docker-compose up

# Access through loadbalancer
open http://localhost:80
```

**Benefits:** Stable endpoint, health monitoring, better security

---

### Stage 3: Add SSL/HTTPS
**Goal:** Secure traffic with certificates

Read more about the [Stage 3 - Hypothesis](../009_aws_stage3/README.md).

#### AWS Components
- Route 53 hosted zone: `lab271.io`
- ACM certificate for `lab271.io`
- ALB listener on port 443 with SSL
- HTTP → HTTPS redirect (port 80 → 443)
- Route 53 A record (alias) → ALB
- Access: `https://frank-009-stage3.lab271.io`

#### Local Setup
```bash
# Generate self-signed certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout nginx.key -out nginx.crt \
  -subj "/CN=frank-stage3.local"

# Update /etc/hosts
echo "127.0.0.1 frank-stage3.local" | sudo tee -a /etc/hosts

# Update nginx.conf for SSL
# Start services
docker-compose up

# Access (ignore certificate warning)
open https://frank-stage3.local
```

**Benefits:** Encrypted traffic, professional domain, browser trust

---

### Stage 4: Add DynamoDB with Audit Trail, Add Multi-AZ Redundancy
**Goal:** Persistent storage and request auditing and High availability across 3 availability zones

Read more about the [Stage 4 - Hypothesis](../009_aws_stage4/README.md).

#### AWS Components
- DynamoDB `main_table`: business data
- DynamoDB `audit_table`: web request logs
  - Captures: timestamp, user ID, IP, method, path, headers, status, duration
- IAM role: Fargate task → DynamoDB permissions
- FastAPI middleware: log every request to audit_table
- Environment variables for table names

#### Local Setup
```bash
# docker-compose.yml (add DynamoDB Local)
services:
  dynamodb-local:
    image: amazon/dynamodb-local
    ports:
      - "8001:8000"
    command: "-jar DynamoDBLocal.jar -sharedDb"

  fastapi:
    environment:
      - AWS_ENDPOINT_URL=http://dynamodb-local:8000
      - MAIN_TABLE=main_table
      - AUDIT_TABLE=audit_table

# Create tables locally
aws dynamodb create-table \
  --table-name main_table \
  --attribute-definitions AttributeName=id,AttributeType=S \
  --key-schema AttributeName=id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --endpoint-url http://localhost:8001

aws dynamodb create-table \
  --table-name audit_table \
  --attribute-definitions AttributeName=request_id,AttributeType=S \
  --key-schema AttributeName=request_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --endpoint-url http://localhost:8001

# Start all services
docker-compose up
```

**Benefits:** Data persistence, complete audit trail, user analytics foundation


#### AWS Components
- VPC expanded to 3 AZs
- Public subnets in each AZ (for ALB)
- Private subnets in each AZ (for Fargate)
- NAT Gateway per AZ (or shared)
- ALB spans all 3 AZs automatically
- ECS Service: 3 tasks (one per AZ)
- DynamoDB: multi-AZ by default

#### Local Setup
```bash
# docker-compose.yml (add replicas)
services:
  fastapi:
    deploy:
      replicas: 3
    
  nginx:
    # Update to round-robin load balance
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf

# nginx-lb.conf
upstream fastapi_backend {
  server fastapi:8000;
  # Docker Compose will automatically load balance across replicas
}

# Start services
docker-compose up --scale fastapi=3
```

**Benefits:** Survive AZ failure, geographic distribution, true production availability

---

### Stage 5: Add ALB Observability
**Goal:** Full visibility into infrastructure and application

#### AWS Components
- S3 bucket for ALB access logs
- S3 bucket policy: allow ALB writes
- ALB configured to log to S3
- S3 lifecycle policy: 90-day retention
- CloudWatch Logs: container stdout/stderr
- CloudWatch Container Insights: ECS cluster

**Two-layer logging:**
- **ALB Logs (S3):** Infrastructure-level traffic, response times, HTTP errors
- **Audit Table (DynamoDB):** Application-level user actions, business context

#### Local Setup
```bash
# docker-compose.yml (add logging)
services:
  fastapi:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
  
  nginx:
    volumes:
      - ./logs:/var/log/nginx

# View logs
docker-compose logs -f fastapi
tail -f logs/access.log
```

**Benefits:** Complete visibility, troubleshooting capability, security analysis, compliance

---

## Quick Start

### Prerequisites
- AWS account with appropriate permissions
- Docker Desktop or Colima
- Python 3.9+
- AWS CLI configured

### Local Development
```bash
# Clone repository
git clone <repository-url>
cd frank

# Option 1: Direct Python
pip install -r requirements.txt
uvicorn main:app --reload

# Option 2: Docker Compose (recommended)
docker-compose up

# Access application
open http://localhost:8000/docs
```

### AWS Deployment
```bash
# Build and push container
docker build -t frank:latest .
aws ecr get-login-password | docker login --username AWS --password-stdin <account>.dkr.ecr.<region>.amazonaws.com
docker tag frank:latest <account>.dkr.ecr.<region>.amazonaws.com/frank:latest
docker push <account>.dkr.ecr.<region>.amazonaws.com/frank:latest

# Deploy to ECS (infrastructure as code recommended)
# See deployment/ directory for Terraform/CloudFormation templates
```

---

## API Endpoints

### `GET /`
Returns static application information
```json
{
  "application": "FRANK",
  "version": "0.1.0",
  "status": "running",
  "message": "Welcome to FRANK application"
}
```

### `GET /v1/health`
Health check endpoint for load balancers
```json
{
  "status": "healthy",
  "timestamp": "2025-10-01T12:00:00.000000",
  "service": "FRANK"
}
```

---

## Project Structure
```
frank/
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container definition
├── docker-compose.yml     # Local development setup
├── README.md              # This file
├── deployment/            # IaC templates (future)
└── tests/                 # Test suite (future)
```

---

## Next Stages (Future)

**Stage 7:** Multi-account setup with subdomain (`spike-test.lab271.io`)  
**Stage 8:** Auto-scaling, WAF, CloudFront, advanced analytics

---

## Contributing

We follow a staged development approach. When adding features:
1. Test locally first
2. Deploy to spike environment
3. Validate functionality
4. Document changes
5. Deploy to production

---

## Support

For questions or issues, contact the FRANK development team or open an issue in the repository.

---

**License:** [Your License]  
**Version:** 0.1.0 (Stage 1-6 Complete)