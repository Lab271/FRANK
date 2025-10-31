# MCP Server Deployment - Spike 014

This deployment structure provides both local (Docker) and AWS (Fargate) deployment options for MCP servers.

## Architecture

### Local Deployment
- **NGINX Gateway**: Routes requests to MCP servers via subpaths
- **MCP Servers**: Each runs in its own container with dedicated subpath
- **Domain**: `mcp.local` (configured in /etc/hosts)
- **SSL**: Self-signed certificates for local HTTPS

### AWS Production Deployment
- **Application Load Balancer**: HTTPS termination and routing
- **ECS Fargate**: Serverless container hosting
- **VPC**: Multi-AZ with private/public subnets
- **AWS Secrets Manager**: Secure environment variable injection
- **Domain**: `mcp.lab271.io`

## Directory Structure

```
deployment/
├── local/                      # Local Docker deployment
│   ├── docker-compose.yml     # Main compose file
│   ├── nginx-gateway.conf     # NGINX reverse proxy config
│   ├── .env.example           # Example environment variables
│   └── ssl-certs/             # Self-signed certificates
├── aws/                        # AWS CloudFormation
│   ├── mcp-infrastructure.yaml
│   └── parameters/
│       ├── dev.json
│       └── prod.json
├── ansible/                    # Ansible automation
│   ├── playbook.yml
│   ├── requirements.yml
│   └── tasks/
├── dockerfiles/               # Dockerfiles for each MCP server
│   ├── Dockerfile.log-mcp
│   └── Dockerfile.base
└── README.md                  # This file
```

## Quick Start

### Local Deployment

1. **Configure /etc/hosts**:
   ```bash
   sudo sh -c 'echo "127.0.0.1 mcp.local" >> /etc/hosts'
   ```

2. **Set up environment variables**:
   ```bash
   cd local
   cp .env.example .env
   # Edit .env and add your ABUSEIPDB_API_KEY
   ```

3. **Generate SSL certificates**:
   ```bash
   cd local
   make generate-certs
   ```

4. **Start services**:
   ```bash
   docker-compose up -d
   ```

5. **Access services**:
   - Gateway: https://mcp.local
   - Log MCP: https://mcp.local/log/

### AWS Deployment

1. **Prerequisites**:
   ```bash
   # Install Ansible dependencies
   ansible-galaxy install -r ansible/requirements.yml
   
   # Configure AWS credentials
   aws configure --profile mcp-prod
   ```

2. **Store secrets in AWS Secrets Manager**:
   ```bash
   aws secretsmanager create-secret \
     --name mcp/log-server/env \
     --secret-string '{"ABUSEIPDB_API_KEY":"your-key-here"}' \
     --region us-east-1 \
     --profile mcp-prod
   ```

3. **Deploy using Ansible**:
   ```bash
   cd ansible
   ansible-playbook playbook.yml -e env=prod
   ```

## Environment Variables

### Log MCP Server
- `ABUSEIPDB_API_KEY`: API key for AbuseIPDB threat intelligence lookups

## Secure Environment Variable Injection (AWS Fargate)

AWS Fargate supports secure environment variable injection through:

### 1. AWS Secrets Manager (Recommended)
```yaml
Environment:
  - Name: NORMAL_VAR
    Value: some-value
Secrets:
  - Name: ABUSEIPDB_API_KEY
    ValueFrom: arn:aws:secretsmanager:region:account:secret:mcp/log-server/env:ABUSEIPDB_API_KEY::
```

### 2. AWS Systems Manager Parameter Store
```yaml
Secrets:
  - Name: ABUSEIPDB_API_KEY
    ValueFrom: arn:aws:ssm:region:account:parameter/mcp/log-server/api-key
```

### 3. Security Best Practices
- Secrets are injected at container startup
- Never stored in CloudFormation templates
- IAM task role requires `secretsmanager:GetSecretValue` permission
- Secrets are encrypted at rest using AWS KMS
- Automatic rotation supported via Lambda

## Monitoring

### Local
```bash
# View logs
docker-compose logs -f log-mcp

# Check NGINX status
docker-compose exec nginx-gateway nginx -t

# View all containers
docker-compose ps
```

### AWS
```bash
# View ECS service status
aws ecs describe-services \
  --cluster mcp-cluster \
  --services log-mcp-service \
  --region us-east-1

# View CloudWatch logs
aws logs tail /ecs/log-mcp-server --follow
```

## Scaling

### Local
Adjust replica count in docker-compose.yml:
```yaml
services:
  log-mcp:
    deploy:
      replicas: 3
```

### AWS
Configure auto-scaling in CloudFormation or adjust manually:
```bash
aws ecs update-service \
  --cluster mcp-cluster \
  --service log-mcp-service \
  --desired-count 3
```

## Troubleshooting

### Local
- **NGINX fails to start**: Check ssl-certs directory has certificates
- **MCP server won't connect**: Verify environment variables in .env
- **Port conflicts**: Check no other services using ports 80/443

### AWS
- **Task fails to start**: Check CloudWatch logs for errors
- **Health check failing**: Verify health check path in target group
- **Secrets not loading**: Verify IAM task role has secretsmanager permissions

## Cost Optimization (AWS)

- Use Fargate Spot for non-critical environments
- Enable auto-scaling with appropriate thresholds
- Use Application Load Balancer efficiently (shared across services)
- Monitor and right-size task CPU/memory allocations

## Security Considerations

1. **Network Security**:
   - Local: Services isolated in Docker network
   - AWS: Private subnets, security groups, NACLs

2. **Secrets Management**:
   - Local: .env file (add to .gitignore)
   - AWS: Secrets Manager with KMS encryption

3. **SSL/TLS**:
   - Local: Self-signed certificates (dev only)
   - AWS: ACM certificates with automatic renewal

4. **Access Control**:
   - Local: Local network only
   - AWS: IAM roles, security groups, ALB rules

## Adding New MCP Servers

1. Create Dockerfile in `dockerfiles/`
2. Add service to `local/docker-compose.yml`
3. Add routing rule to `local/nginx-gateway.conf`
4. Add ECS task definition to `aws/mcp-infrastructure.yaml`
5. Update Ansible playbook tasks

## License

Copyright (c) 2025 LAB271
SPDX-License-Identifier: Apache-2.0
