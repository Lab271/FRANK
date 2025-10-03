# FRANK Application - Stage 4: Add DynamoDB & Multi-AZ

## Hypothesis Documentation

This stage builds upon Stage 3's SSL/HTTPS security foundation by introducing persistent data storage with DynamoDB and multi-availability zone deployment for production-ready resilience and scalability.

## Stage Evolution

**Previous Stage (Stage 3):** SSL/TLS termination with custom domain  
**Current Stage (Stage 4):** DynamoDB integration + Multi-AZ deployment  
**Next Stage (Stage 5):** API Gateway integration and advanced security

## Architectural Hypothesis

### Core Hypothesis
> By integrating DynamoDB for persistent data storage and deploying across multiple availability zones, we can provide a production-ready, scalable, and resilient application architecture that maintains sub-second response times while supporting concurrent user sessions and data persistence.

### Problem Statement from Stage 3
- **No Data Persistence**: Application state lost on container restart
- **Single AZ Deployment**: No resilience against availability zone failures
- **Limited API Functionality**: Only basic health check and static responses
- **No User Sessions**: Cannot track user interactions or preferences
- **Scalability Constraints**: Single container cannot handle production load

### Stage 4 Solutions
1. **DynamoDB Integration**: Serverless NoSQL database for scalable data storage
2. **Multi-AZ Deployment**: ECS tasks distributed across multiple availability zones
3. **API Endpoints**: RESTful APIs for data operations (CRUD operations)
4. **Session Management**: User session tracking and state persistence
5. **Auto Scaling**: ECS service auto-scaling based on CPU/memory metrics

## Architecture Components

### AWS Infrastructure
```
Route 53 (DNS) → Internet Gateway
    ↓
Application Load Balancer (SSL Termination) - Multi-AZ
    ↓ (HTTPS → HTTP internally)
ECS Fargate Tasks (Multi-AZ: eu-central-1a, eu-central-1b, eu-central-1c)
    ↓ (VPC Endpoints)
DynamoDB (Serverless, Multi-AZ replication)
    ↓ (CloudWatch Integration)
Auto Scaling + Monitoring
```

### Component Details

1. **DynamoDB Tables**
   - **Hypothesis**: Serverless NoSQL provides infinite scale with predictable performance
   - **Expected Outcome**: Sub-100ms read/write latency with automatic scaling
   - **Table Design**: 
     - `frank-sessions` (partition key: session_id, TTL enabled)
     - `frank-users` (partition key: user_id, GSI on email)
     - `frank-metrics` (partition key: date, sort key: timestamp)
   - **Backup Strategy**: Point-in-time recovery enabled

2. **Multi-AZ ECS Service**
   - **Hypothesis**: Multiple AZ deployment provides 99.9%+ availability
   - **Expected Outcome**: Service survives single AZ failure without user impact
   - **Configuration**: Minimum 2 tasks across 3 AZs
   - **Health Checks**: ALB health checks with 30s interval, 3 healthy threshold

3. **Auto Scaling Configuration**
   - **Hypothesis**: Dynamic scaling maintains performance under variable load
   - **Expected Outcome**: Automatic scale-out at 70% CPU, scale-in at 30% CPU
   - **Metrics**: Target tracking on CPU utilization and request count
   - **Scaling Policy**: Scale out by 100%, scale in by 25%

4. **API Endpoints**
   - **Hypothesis**: RESTful APIs provide intuitive data operations interface
   - **Expected Outcome**: Full CRUD operations with <500ms response time
   - **Endpoints**:
     - `POST /api/v1/sessions` - Create user session
     - `GET /api/v1/sessions/{id}` - Retrieve session data
     - `PUT /api/v1/sessions/{id}` - Update session data
     - `DELETE /api/v1/sessions/{id}` - Delete session
     - `GET /api/v1/metrics` - Application metrics dashboard

## Validation Criteria

### Functional Requirements
- [ ] DynamoDB tables created and accessible
- [ ] Multi-AZ ECS service deployment successful
- [ ] All API endpoints respond with appropriate HTTP codes
- [ ] Session data persists across container restarts
- [ ] Auto scaling triggers work under load

### Performance Requirements
- [ ] DynamoDB read latency < 100ms (99th percentile)
- [ ] DynamoDB write latency < 100ms (99th percentile)
- [ ] API endpoint response time < 500ms (95th percentile)
- [ ] Application startup time < 60 seconds
- [ ] Health check response time < 1 second

### Resilience Requirements
- [ ] Service survives single AZ failure (simulated)
- [ ] Service survives container failure and restarts
- [ ] Data consistency maintained during failures
- [ ] Auto scaling maintains service during load spikes
- [ ] Zero data loss during normal operations

### Security Requirements
- [ ] DynamoDB VPC endpoints used (no internet traffic)
- [ ] ECS task IAM roles follow least privilege principle
- [ ] API endpoints require authentication headers
- [ ] Session data encrypted at rest and in transit
- [ ] CloudWatch logs capture security events

## Expected Benefits

### Data Persistence & State Management
- **Session Continuity**: User sessions survive container restarts
- **Data Durability**: 99.999999999% (11 9's) durability guarantee
- **Consistency**: Eventually consistent reads with strong consistency options
- **Backup & Recovery**: Automated backup with point-in-time recovery

### High Availability & Resilience
- **Multi-AZ Deployment**: Service continues during AZ outages
- **Auto Recovery**: Failed containers automatically replaced
- **Load Distribution**: Traffic automatically balanced across healthy instances
- **Graceful Degradation**: Service degrades gracefully under extreme load

### Scalability & Performance
- **Horizontal Scaling**: ECS service scales from 2 to 10+ instances
- **Database Scaling**: DynamoDB automatically scales read/write capacity
- **Response Time**: Consistent sub-second response times under load
- **Cost Optimization**: Pay-per-use pricing for actual resource consumption

### Operational Benefits
- **Monitoring**: CloudWatch dashboards for all key metrics
- **Alerting**: Automated alerts for service degradation
- **Logging**: Centralized logging for debugging and audit
- **Deployment**: Blue-green deployments with zero downtime

## Known Limitations

### Current Stage Constraints
- **Database Choice**: NoSQL only - no complex relational queries
- **Single Region**: Deployment limited to eu-central-1
- **Authentication**: Basic session management, no OAuth/SAML
- **API Versioning**: Single API version, no backward compatibility

### Cost Implications
- **DynamoDB**: $0.25 per GB storage + $1.25 per million read units
- **Multi-AZ ECS**: 2-3x compute costs for redundancy
- **VPC Endpoints**: $0.01 per hour per endpoint + data transfer
- **Estimated Monthly Cost**: $50-150 for development workload

### Performance Constraints
- **Cold Start**: Initial container startup takes 45-60 seconds
- **DynamoDB Throttling**: May occur during sudden traffic spikes
- **ECS Scaling**: Auto scaling takes 2-5 minutes to add capacity
- **Cross-AZ Latency**: ~1-2ms additional latency for cross-AZ calls

## Risk Assessment

### Low Risk
- DynamoDB service reliability and performance
- ECS multi-AZ deployment automation
- IAM role and security group configuration

### Medium Risk
- Auto scaling configuration and timing
- VPC endpoint connectivity and routing
- Container resource allocation and limits
- DynamoDB cost optimization under varying load

### High Risk (Mitigated)
- Data migration from stateless to stateful (mitigated by gradual rollout)
- Service complexity increase (mitigated by comprehensive monitoring)
- Multi-AZ cost increase (mitigated by auto scaling policies)

## Testing Strategy

### Database Integration Testing
```bash
# Test DynamoDB connectivity
curl -X POST https://frank-009-stage4.lab271.io/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user", "data": {"key": "value"}}'

# Test session persistence
SESSION_ID=$(curl -s -X POST https://frank-009-stage4.lab271.io/api/v1/sessions \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test-user"}' | jq -r '.session_id')

curl -s https://frank-009-stage4.lab271.io/api/v1/sessions/$SESSION_ID | jq .
```

### Multi-AZ Resilience Testing
```bash
# Simulate AZ failure by stopping tasks in one AZ
aws ecs update-service \
  --cluster frank-009-stage4 \
  --service frank-stage4-service \
  --desired-count 1

# Monitor service health during simulated failure
watch 'curl -s https://frank-009-stage4.lab271.io/v1/health | jq .'
```

### Auto Scaling Testing
```bash
# Load test to trigger auto scaling
artillery quick --count 100 --num 10 \
  https://frank-009-stage4.lab271.io/

# Monitor scaling events
aws ecs describe-services \
  --cluster frank-009-stage4 \
  --services frank-stage4-service \
  --query 'services[0].runningCount'
```

### Performance Testing
```bash
# Database performance testing
ab -n 1000 -c 10 \
  -H "Content-Type: application/json" \
  -p session-data.json \
  https://frank-009-stage4.lab271.io/api/v1/sessions

# API endpoint latency testing
for endpoint in health sessions metrics; do
  echo "Testing /$endpoint"
  curl -w "@curl-format.txt" -o /dev/null -s \
    https://frank-009-stage4.lab271.io/api/v1/$endpoint
done
```

## Success Metrics

### Performance Metrics
- **API Response Time**: 95th percentile < 500ms
- **Database Latency**: 99th percentile < 100ms
- **Service Availability**: >99.9% uptime
- **Error Rate**: <0.1% of all requests

### Scalability Metrics
- **Auto Scale Response**: Scale-out within 5 minutes
- **Load Handling**: 1000+ concurrent sessions
- **Database Throughput**: 100+ requests/second sustained
- **Multi-AZ Distribution**: Even traffic distribution

### Resilience Metrics
- **AZ Failure Recovery**: <30 seconds failover
- **Container Restart**: <60 seconds recovery
- **Data Consistency**: Zero data loss during failures
- **Health Check Success**: >99% health check pass rate

## Local Development Equivalent

To replicate Stage 4 architecture locally with DynamoDB Local:

```yaml
# docker-compose.yml
version: '3.8'
services:
  nginx-lb:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx-ssl.conf:/etc/nginx/nginx.conf
      - ./ssl-certs:/etc/nginx/ssl
    depends_on:
      - simple-api-1
      - simple-api-2
    networks:
      - frank-network

  simple-api-1:
    build: .
    container_name: simple-api-1
    environment:
      - DYNAMODB_ENDPOINT=http://dynamodb-local:8000
      - AWS_ACCESS_KEY_ID=dummy
      - AWS_SECRET_ACCESS_KEY=dummy
      - AWS_DEFAULT_REGION=eu-central-1
    depends_on:
      - dynamodb-local
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - frank-network

  simple-api-2:
    build: .
    container_name: simple-api-2
    environment:
      - DYNAMODB_ENDPOINT=http://dynamodb-local:8000
      - AWS_ACCESS_KEY_ID=dummy
      - AWS_SECRET_ACCESS_KEY=dummy
      - AWS_DEFAULT_REGION=eu-central-1
    depends_on:
      - dynamodb-local
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - frank-network

  dynamodb-local:
    image: amazon/dynamodb-local:latest
    container_name: dynamodb-local
    ports:
      - "8000:8000"
    command: ["-jar", "DynamoDBLocal.jar", "-inMemory", "-sharedDb"]
    networks:
      - frank-network
    
networks:
  frank-network:
    driver: bridge
```

```nginx
# nginx-ssl.conf with load balancing
events {
    worker_connections 1024;
}

http {
    upstream simple_api_backend {
        server simple-api-1:8000;
        server simple-api-2:8000;
    }

    # HTTP server - redirect to HTTPS
    server {
        listen 80;
        server_name frank-stage4.local;
        return 301 https://$server_name$request_uri;
    }

    # HTTPS server with load balancing
    server {
        listen 443 ssl;
        server_name frank-stage4.local;

        ssl_certificate /etc/nginx/ssl/nginx.crt;
        ssl_certificate_key /etc/nginx/ssl/nginx.key;
        ssl_protocols TLSv1.2 TLSv1.3;
        ssl_ciphers HIGH:!aNULL:!MD5;

        # Security headers
        add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
        add_header X-Content-Type-Options nosniff always;
        add_header X-Frame-Options DENY always;

        location /health {
            proxy_pass http://simple_api_backend/v1/health;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
        
        location / {
            proxy_pass http://simple_api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            
            # Load balancing configuration
            proxy_next_upstream error timeout invalid_header http_500 http_502 http_503 http_504;
            proxy_buffering off;
        }
    }
}
```

### Local DynamoDB Setup
```bash
# Create local DynamoDB tables
aws dynamodb create-table \
  --endpoint-url http://localhost:8000 \
  --table-name frank-sessions \
  --attribute-definitions \
    AttributeName=session_id,AttributeType=S \
  --key-schema \
    AttributeName=session_id,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST

aws dynamodb create-table \
  --endpoint-url http://localhost:8000 \
  --table-name frank-users \
  --attribute-definitions \
    AttributeName=user_id,AttributeType=S \
    AttributeName=email,AttributeType=S \
  --key-schema \
    AttributeName=user_id,KeyType=HASH \
  --global-secondary-indexes \
    'IndexName=email-index,KeySchema=[{AttributeName=email,KeyType=HASH}],Projection={ProjectionType=ALL}' \
  --billing-mode PAY_PER_REQUEST

# Test data insertion
aws dynamodb put-item \
  --endpoint-url http://localhost:8000 \
  --table-name frank-sessions \
  --item '{
    "session_id": {"S": "test-session-123"},
    "user_id": {"S": "test-user"},
    "created_at": {"S": "2025-01-01T00:00:00Z"},
    "data": {"M": {"key": {"S": "value"}}}
  }'
```

### Local Load Balancing Test
```bash
# Add to /etc/hosts
echo "127.0.0.1 frank-stage4.local" | sudo tee -a /etc/hosts

# Start services
docker-compose up

# Test load balancing
for i in {1..10}; do
  curl -s https://frank-stage4.local/ | jq '.container_id // .hostname'
done
```

## Transition to Stage 5

Stage 4 establishes the data and resilience foundation for Stage 5 enhancements:
- **API Gateway Integration**: Centralized API management and throttling
- **Advanced Authentication**: OAuth, JWT tokens, and role-based access
- **Microservices Architecture**: Service decomposition and inter-service communication
- **Advanced Monitoring**: Distributed tracing and performance analytics

The multi-AZ deployment and DynamoDB integration provided by Stage 4 are essential for supporting advanced API patterns and microservices architecture in Stage 5.

## Environment Configuration

### Development
- **Domain**: `frank-009-stage4-dev.lab271.io`
- **DynamoDB**: On-demand billing mode for cost optimization
- **ECS Tasks**: 2 minimum, 4 maximum for development load

### Staging
- **Domain**: `frank-009-stage4-staging.lab271.io`
- **DynamoDB**: Provisioned billing with auto scaling
- **ECS Tasks**: 2 minimum, 8 maximum for staging load testing

### Production (Future)
- **Domain**: `frank.lab271.io`
- **DynamoDB**: Provisioned billing with reserved capacity
- **ECS Tasks**: 3 minimum, 20 maximum for production scale

## Documentation Structure

```
009_aws_stage4/
├── README.md                    # This file
├── stage4_hypothesis.py         # Validation and testing code
├── deploy.sh                    # Deployment automation
├── Dockerfile                   # Container definition
├── docker-compose.yml           # Local development setup
├── nginx-lb.conf                # nginx load balancing configuration
├── frank_stage4_api.py          # Enhanced API with DynamoDB
├── frank-009-stage4-infra.yaml  # CloudFormation template
├── dynamodb_setup.py            # DynamoDB table creation script
├── load_test.py                 # Performance testing script
└── Makefile                     # Build and test automation
```

This stage represents the transition from secure single-instance deployment (Stage 3) to production-ready, scalable, and resilient architecture with persistent data storage and multi-zone redundancy.