# FRANK Application - Stage 3: Add SSL/HTTPS

## Status
INTEGRATED

## Integrated Into
- `stages/stage3/` - AWS cloud deployment with SSL/TLS
- `ansible/` - Certificate and deployment automation

---

## Hypothesis Documentation

This stage builds upon Stage 2's load balancer architecture by introducing SSL/TLS encryption and custom domain support to enable production-ready HTTPS endpoints.

## Stage Evolution

**Previous Stage (Stage 2):** Application Load Balancer with HTTP-only access  
**Current Stage (Stage 3):** SSL/TLS termination at ALB with custom domain  
**Next Stage (Stage 4):** DynamoDB integration and multi-AZ redundancy

## Architectural Hypothesis

### Core Hypothesis
> By implementing SSL/TLS termination at the Application Load Balancer and integrating with Route 53 DNS management, we can provide production-ready HTTPS endpoints with custom domain support while maintaining the stability and health monitoring established in Stage 2.

### Problem Statement from Stage 2
- **HTTP Only**: No encryption for production traffic
- **Generic Endpoint**: ALB-generated DNS names not suitable for production
- **Security Headers Missing**: No HSTS or security policy enforcement
- **Certificate Management**: Manual certificate handling required
- **Browser Trust**: HTTP-only endpoints trigger security warnings

### Stage 3 Solutions
1. **SSL/TLS Encryption**: HTTPS termination at ALB with AWS Certificate Manager
2. **Custom Domain**: Route 53 hosted zone with professional domain name
3. **Certificate Automation**: ACM handles certificate provisioning and renewal
4. **Security Headers**: ALB injects HSTS and security policy headers
5. **HTTP Redirect**: Automatic HTTP → HTTPS redirection for security

## Architecture Components

### AWS Infrastructure
```
Route 53 (DNS) → Internet Gateway
    ↓
Application Load Balancer (SSL Termination)
    ↓ (HTTPS → HTTP internally)
ECS Fargate Task (Private Subnet)
    ↓ (Outbound only)
NAT Gateway → Internet Gateway
```

### Component Details

1. **AWS Certificate Manager (ACM)**
   - **Hypothesis**: Managed SSL certificates reduce operational overhead
   - **Expected Outcome**: Valid SSL certificate for `frank-009-stage3.lab271.io`
   - **Validation**: DNS validation through Route 53
   - **Renewal**: Automatic before expiration

2. **Route 53 Hosted Zone**
   - **Hypothesis**: DNS management enables custom domain integration
   - **Expected Outcome**: `frank-009-stage3.lab271.io` resolves to ALB
   - **Record Type**: A record (alias) pointing to ALB
   - **TTL**: 300 seconds for development flexibility

3. **ALB HTTPS Listener**
   - **Hypothesis**: SSL termination at load balancer optimizes performance
   - **Expected Outcome**: HTTPS traffic decrypted at ALB, HTTP to containers
   - **Certificate**: ACM certificate attachment
   - **Security Policy**: TLS 1.2+ enforcement

4. **HTTP → HTTPS Redirect**
   - **Hypothesis**: Automatic redirects improve security without user friction
   - **Expected Outcome**: All HTTP requests redirect to HTTPS (301)
   - **Performance**: Minimal redirect overhead
   - **SEO**: Search engine friendly permanent redirect

## Validation Criteria

### Functional Requirements
- [ ] HTTPS endpoint accessible via custom domain
- [ ] SSL certificate valid and trusted by browsers
- [ ] HTTP requests automatically redirect to HTTPS
- [ ] Health checks work over HTTPS
- [ ] Application functionality preserved with SSL

### Performance Requirements
- [ ] HTTPS response time < 3 seconds (accounting for SSL overhead)
- [ ] SSL handshake time < 500ms
- [ ] HTTP redirect time < 200ms
- [ ] Health check response time < 1 second over HTTPS

### Security Requirements
- [ ] SSL certificate from trusted CA (AWS Certificate Manager)
- [ ] TLS 1.2+ enforced, no weak ciphers
- [ ] HSTS header present in responses
- [ ] HTTP Strict Transport Security policy active
- [ ] Certificate chain validation successful

## Expected Benefits

### Security Enhancements
- **Traffic Encryption**: All communication encrypted in transit
- **Data Integrity**: Prevention of man-in-the-middle attacks
- **Authentication**: Certificate-based server authentication
- **Compliance**: Meets security requirements for production deployment

### Professional Presentation
- **Custom Domain**: Professional URL for business use
- **Browser Trust**: Green lock icon, no security warnings
- **SEO Benefits**: HTTPS preference in search rankings
- **User Confidence**: Secure appearance increases user trust

### Operational Benefits
- **Certificate Automation**: ACM handles renewal automatically
- **DNS Management**: Route 53 integration for subdomain control
- **Security Headers**: Automatic injection of security policies
- **Monitoring**: SSL certificate expiration monitoring

## Known Limitations

### Current Stage Constraints
- **Single Domain**: One SSL certificate for one subdomain
- **No WAF**: No Web Application Firewall protection yet
- **Basic Security Headers**: Minimal security policy implementation
- **Development Certificate**: Using development subdomain

### Cost Implications
- **Route 53 Hosted Zone**: $0.50/month per hosted zone
- **ACM Certificate**: Free for ALB usage
- **Minimal Additional Cost**: ~$0.50-1.00/month increase
- **DNS Queries**: $0.40 per million queries

## Risk Assessment

### Low Risk
- ACM certificate provisioning and renewal
- Route 53 DNS reliability
- ALB HTTPS listener configuration

### Medium Risk
- DNS propagation delays during initial setup
- Certificate validation timing
- Custom domain configuration complexity

### High Risk (Mitigated)
- Certificate validation failure (mitigated by automated DNS validation)
- Domain ownership verification (mitigated by Route 53 control)
- SSL configuration errors (mitigated by AWS managed policies)

## Testing Strategy

### SSL/TLS Validation
```bash
# Test HTTPS endpoint
curl -v https://frank-009-stage3.lab271.io/

# Verify certificate details
openssl s_client -connect frank-009-stage3.lab271.io:443 -servername frank-009-stage3.lab271.io

# Test SSL Labs rating
curl "https://api.ssllabs.com/api/v3/analyze?host=frank-009-stage3.lab271.io"
```

### Security Testing
```bash
# Test HTTP → HTTPS redirect
curl -I http://frank-009-stage3.lab271.io/

# Verify security headers
curl -I https://frank-009-stage3.lab271.io/

# Test HSTS enforcement
curl -H "Host: frank-009-stage3.lab271.io" http://frank-009-stage3.lab271.io/
```

### Performance Testing
```bash
# HTTPS response time
time curl -s https://frank-009-stage3.lab271.io/

# SSL handshake timing
curl -w "@curl-format.txt" -o /dev/null -s https://frank-009-stage3.lab271.io/

# Health check over HTTPS
time curl -s https://frank-009-stage3.lab271.io/v1/health
```

## Success Metrics

### Security Metrics
- **SSL Labs Grade**: A or A+ rating
- **Certificate Validity**: >30 days remaining
- **TLS Version**: 1.2+ enforced
- **Cipher Strength**: Strong ciphers only

### Performance Metrics
- **HTTPS Response Time**: <3 seconds
- **SSL Handshake**: <500ms
- **Redirect Time**: <200ms
- **Health Check Time**: <1 second

### Availability Metrics
- **Certificate Uptime**: 100% valid certificate
- **DNS Resolution**: 99.9% successful lookups
- **HTTPS Availability**: 99.9% during testing period

## Local Development Equivalent

To replicate Stage 3 architecture locally:

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
      - simple-api
    networks:
      - frank-network

  simple-api:
    build: .
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
      - frank-network
    
networks:
  frank-network:
    driver: bridge
```

```nginx
# nginx-ssl.conf
events {
    worker_connections 1024;
}

http {
    upstream simple_api_backend {
        server simple-api:8000;
    }

    # HTTP server - redirect to HTTPS
    server {
        listen 80;
        server_name frank-stage3.local;
        return 301 https://$server_name$request_uri;
    }

    # HTTPS server
    server {
        listen 443 ssl;
        server_name frank-stage3.local;

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
        }
    }
}
```

### Local SSL Certificate Setup
```bash
# Generate self-signed certificate for local development
mkdir -p ssl-certs

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout ssl-certs/nginx.key \
  -out ssl-certs/nginx.crt \
  -subj "/CN=frank-stage3.local"

# Add to /etc/hosts
echo "127.0.0.1 frank-stage3.local" | sudo tee -a /etc/hosts

# Start services
docker-compose up

# Access via HTTPS (accept certificate warning)
open https://frank-stage3.local
```

## Transition to Stage 4

Stage 3 establishes the security foundation for Stage 4 enhancements:
- **DynamoDB Integration**: Secure API endpoints for database operations
- **Multi-AZ Deployment**: SSL configuration scales across availability zones
- **API Authentication**: HTTPS foundation for secure authentication flows
- **Audit Logging**: Encrypted communication for sensitive audit data

The HTTPS endpoints and custom domain provided by Stage 3 are essential for production database integration and user-facing API development.

## Environment Configuration

### Development
- **Domain**: `frank-009-stage3-dev.lab271.io`
- **Certificate**: ACM development certificate
- **DNS**: Route 53 development subdomain

### Production (Future)
- **Domain**: `frank.lab271.io`
- **Certificate**: ACM production certificate  
- **DNS**: Route 53 production domain

## Documentation Structure

```
011_aws_ssl/
├── README.md                    # This file
├── stage3_hypothesis.py         # Validation and testing code
├── deploy.sh                    # Deployment automation
├── Dockerfile                   # Container definition
├── docker-compose.yml           # Local development setup
├── nginx-lb.conf                # nginx SSL configuration
├── frank-009-stage3-infra.yaml  # CloudFormation template
├── simple_api.py                # Application code
└── Makefile                     # Build automation
```

This stage represents the transition from development networking (Stage 2) to production-ready security architecture, establishing encrypted communication patterns that will support all subsequent stages requiring secure data transmission.