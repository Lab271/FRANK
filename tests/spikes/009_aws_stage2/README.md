# FRANK Application - Stage 2: Add Load Balancer

## Hypothesis Documentation

This stage builds upon Stage 1's minimal setup by introducing load balancing and improved networking architecture to address the limitations of direct public IP access.

## Stage Evolution

**Previous Stage (Stage 1):** Single Fargate task with direct public IP access  
**Current Stage (Stage 2):** Application Load Balancer with private subnet deployment  
**Next Stage (Stage 3):** SSL/HTTPS and custom domain integration

## Architectural Hypothesis

### Core Hypothesis
> By introducing an Application Load Balancer (ALB) and moving the Fargate task to a private subnet, we can achieve stable endpoint access, health monitoring, and improved security posture while maintaining simplicity and cost-effectiveness.

### Problem Statement from Stage 1
- **IP Volatility**: Public IP changes on every task restart
- **No Health Monitoring**: Manual verification required for application status
- **Security Exposure**: Direct internet access to application container
- **No Load Distribution**: Single point of failure with no redundancy capability

### Stage 2 Solutions
1. **Stable Endpoint**: ALB provides consistent DNS name regardless of task restarts
2. **Health Checking**: ALB monitors `/v1/health` endpoint and routes traffic only to healthy tasks
3. **Network Security**: Fargate tasks in private subnet, only ALB exposed to internet
4. **Foundation for Scaling**: ALB ready for multiple target registration
5. **Incklude main package**: prep container build for python inclusion

## Architecture Components

### AWS Infrastructure
```
Internet Gateway
    ↓
Application Load Balancer (Public Subnet)
    ↓ (Health Checks: /v1/health)
ECS Fargate Task (Private Subnet)
    ↓ (Outbound only)
NAT Gateway → Internet Gateway
```

### Component Details

1. **Application Load Balancer (ALB)**
   - **Hypothesis**: Layer 7 load balancing provides intelligent traffic routing
   - **Expected Outcome**: Stable `http://frank-alb-xxx.region.elb.amazonaws.com` endpoint
   - **Health Check**: `GET /v1/health` every 30 seconds
   - **Target**: Single Fargate task (expandable to multiple)

2. **Private Subnet Deployment**
   - **Hypothesis**: Private subnets improve security without complexity
   - **Expected Outcome**: Fargate tasks inaccessible from internet directly
   - **Outbound Access**: Via NAT Gateway for ECR/CloudWatch communication

3. **NAT Gateway**
   - **Hypothesis**: Managed NAT service provides reliable outbound connectivity
   - **Expected Outcome**: Container can pull images and send logs
   - **Cost Impact**: ~$45/month base cost + data transfer

4. **Target Group Configuration**
   - **Health Check Path**: `/v1/health`
   - **Health Check Interval**: 30 seconds
   - **Healthy Threshold**: 2 consecutive successes
   - **Unhealthy Threshold**: 2 consecutive failures
   - **Timeout**: 5 seconds

## Validation Criteria

### Functional Requirements
- [ ] ALB endpoint responds to HTTP requests
- [ ] Application accessible via stable ALB DNS name
- [ ] Health checks pass consistently
- [ ] Task restarts don't affect endpoint availability
- [ ] Fargate task not directly accessible from internet

### Performance Requirements
- [ ] Response time < 2 seconds for application endpoints
- [ ] Health check response time < 1 second
- [ ] ALB failover time < 30 seconds during task restart
- [ ] Zero downtime during planned task updates

### Security Requirements
- [ ] Fargate tasks in private subnet only
- [ ] Security group allows ALB → Fargate communication only
- [ ] No direct internet access to application containers
- [ ] ALB security group restricts inbound to HTTP (port 80) only

## Expected Benefits

### Stability Improvements
- **Persistent Endpoint**: ALB DNS name never changes
- **Health Monitoring**: Automatic detection of application failures
- **Graceful Failover**: ALB stops routing to unhealthy tasks

### Security Enhancements
- **Network Isolation**: Application containers in private subnets
- **Controlled Access**: Only ALB exposed to internet
- **Reduced Attack Surface**: Direct container access eliminated

### Operational Benefits
- **Monitoring**: ALB metrics in CloudWatch
- **Logging**: ALB access logs capture all HTTP requests
- **Debugging**: Clear separation of load balancer vs application issues

## Known Limitations

### Current Stage Constraints
- **HTTP Only**: No SSL/TLS encryption (addressed in Stage 3)
- **Single Task**: No horizontal scaling yet (foundation established)
- **No Custom Domain**: Using ALB-generated DNS name
- **Basic Health Checks**: Simple HTTP 200 validation only

### Cost Implications
- **ALB**: ~$22/month base cost + LCU charges
- **NAT Gateway**: ~$45/month + data processing
- **Increased Complexity**: More components to monitor
- **Total Increase**: ~$70-100/month over Stage 1

## Risk Assessment

### Low Risk
- ALB reliability (AWS managed service)
- Health check accuracy for simple endpoints
- Private subnet networking

### Medium Risk
- NAT Gateway single point of failure
- Increased cost for development environments
- Additional network complexity

### High Risk (Mitigated)
- Application health endpoint reliability (mitigated by robust `/v1/health`)
- Target group configuration errors (mitigated by testing)

## Testing Strategy

### Deployment Validation
```bash
# Test ALB endpoint
curl http://frank-alb-xxx.region.elb.amazonaws.com/

# Test health endpoint
curl http://frank-alb-xxx.region.elb.amazonaws.com/v1/health

# Verify private subnet isolation
curl http://<fargate-private-ip>/  # Should timeout/fail
```

### Resilience Testing
```bash
# Force task restart and verify endpoint stability
aws ecs update-service --force-new-deployment --service frank-stage2-service

# Monitor health check status
aws elbv2 describe-target-health --target-group-arn <target-group-arn>
```

### Performance Testing
```bash
# Load testing with multiple concurrent requests
ab -n 1000 -c 10 http://frank-alb-xxx.region.elb.amazonaws.com/

# Health check response time monitoring
for i in {1..10}; do
  time curl -s http://frank-alb-xxx.region.elb.amazonaws.com/v1/health
done
```

## Success Metrics

### Availability Metrics
- **Uptime**: 99.9% during testing period
- **Health Check Success Rate**: >99%
- **Failover Time**: <30 seconds during task restarts

### Performance Metrics
- **Response Time**: <2 seconds for application endpoints
- **Health Check Time**: <1 second
- **ALB Request Latency**: <100ms additional overhead

### Security Metrics
- **Direct Access Attempts**: 0 successful connections to private IPs
- **Security Group Violations**: 0 unauthorized access attempts
- **Network Isolation**: 100% compliance with private subnet rules

## Local Development Equivalent

To replicate Stage 2 architecture locally:

```yaml
# docker-compose.yml
services:
  nginx-lb:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf
    depends_on:
      - simple-api
    networks:
      - private-net
          
  simple-api:
    build: .
    # No external ports - only accessible via nginx
    container_name: simple-api
    ports:
      - "8000:8000"    
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    networks:
      - private-net
    
networks:
  private-net:
    driver: bridge
```

```nginx
# nginx-lb.conf
http {
    upstream simple_api_backend {
        server simple-api:8000;
    }

    server {
        listen 80;
        
        location /health {
            proxy_pass http://simple_api_backend/v1/health;
            proxy_set_header Host $host;
        }
        
        location / {
            proxy_pass http://simple_api_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
}
```

## Transition to Stage 3

Stage 2 establishes the foundation for Stage 3 enhancements:
- **SSL/TLS**: ALB already supports HTTPS listeners
- **Custom Domain**: Route 53 can alias to ALB
- **Certificate Management**: ACM integration ready
- **Security Headers**: ALB can inject security headers

The stable endpoint and health monitoring provided by Stage 2 are essential prerequisites for production SSL deployment and custom domain configuration.

## Documentation Structure

```
009_aws_stage2/
├── README.md                    # This file
├── stage2_hypothesis.py         # Validation and testing code
├── deploy.sh                    # Deployment automation
├── Dockerfile                   # Dockerfile
├── docker-compose.yml           # Docker-compose build file
├── nginx-lb.conf                # nginx-lb.conf
├── frank-009-stage2-infra.yaml  # CloudFormation template
├── simple_api.py                # Application code
└── Makefile                     # Build automation
```

This stage represents a critical transition from development-focused (Stage 1) to production-ready networking architecture, establishing patterns that will scale through subsequent stages.