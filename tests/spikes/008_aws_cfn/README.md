# FRANK 008 AWS Spike - Python + CloudFormation Deployment

Complete cross-account deployment solution for FRANK threat intelligence platform using Python orchestration and CloudFormation templates.

## 🎯 **What This Solves**

- **Cross-Account Deployment**: Infrastructure in spike account, DNS in main account
- **SSL Certificate Automation**: Automated DNS validation across accounts  
- **Container Deployment**: FastAPI application with ECS Fargate
- **Infrastructure as Code**: CloudFormation templates with Python orchestration
- **Safety & Isolation**: Complete resource isolation with proper naming

## 🏗️ **Architecture**

```
┌─────────────────┐         ┌─────────────────┐
│   Main Account  │         │  Spike Account  │
│                 │         │                 │
│ ┌─────────────┐ │         │ ┌─────────────┐ │
│ │   Route53   │ │◄────────┤ │     VPC     │ │
│ │ lab271.io   │ │         │ │ Multi-AZ    │ │
│ └─────────────┘ │         │ └─────────────┘ │
│                 │         │                 │
│ ┌─────────────┐ │         │ ┌─────────────┐ │
│ │ SSL Cert    │ │         │ │ ECS Fargate │ │
│ │ Validation  │ │         │ │ FastAPI App │ │
│ └─────────────┘ │         │ └─────────────┘ │
│                 │         │                 │
│ ┌─────────────┐ │         │ ┌─────────────┐ │
│ │Cross-Account│ │         │ │     ALB     │ │
│ │    Role     │ │         │ │  + SSL      │ │
│ └─────────────┘ │         │ └─────────────┘ │
└─────────────────┘         └─────────────────┘
```

## 📁 **Project Structure**

```
tests/spikes/008_aws_cfn/
├── deploy.py                    # 🎯 Main orchestration script
├── setup.py                     # 🔧 Environment setup
├── setup-cross-account-role.py  # 🔑 Cross-account role creator
├── requirements.txt             # 📦 Python dependencies
├── 008_aws_spike.py             # 🐍 FastAPI application
├── Dockerfile                   # 🐳 Container definition
├── utils/
│   ├── aws_client.py           # ☁️ Cross-account AWS client
│   ├── stack_deployer.py       # 📚 CloudFormation manager
│   └── domain_validator.py     # 🔒 SSL certificate helper
├── config/
│   ├── accounts.yaml           # 🏢 Account configuration
│   └── spike-params.yaml       # ⚙️ Deployment parameters
└── templates/
    ├── networking.yaml         # 🌐 VPC and security groups
    ├── load-balancer.yaml      # ⚖️ ALB and target groups
    ├── ssl-cert.yaml           # 🔒 SSL certificate
    ├── route53.yaml            # 🌍 DNS records (main account)
    └── ecs.yaml                # 🚀 ECS cluster and service
```

## 🚀 **Quick Start**

### **1. Prerequisites**
```bash
# Required tools
- Python 3.8+
- AWS CLI configured  
- Docker Desktop
- Access to both AWS accounts
```

### **2. Initial Setup**
```bash
# Clone and navigate
cd tests/spikes/008_aws_cfn

# Install dependencies and verify environment
python setup.py

# This will check:
# ✅ Python version
# ✅ AWS CLI and credentials
# ✅ Docker installation
# ✅ Required directories
```

### **3. Configure Accounts**
```bash
# Edit account configuration
vim config/accounts.yaml
```

Update with your real account IDs:
```yaml
spike:
  account_id: "111111111111"  # Your spike account ID
  profile_name: "spike-account"  # AWS profile name

main:
  account_id: "222222222222"  # Your main account ID  
  cross_account_role_arn: "arn:aws:iam::222222222222:role/FrankRoute53CrossAccountRole"
  external_id: "frank-008-unique-external-id-2025"
```

### **4. Configure Deployment Parameters**
```bash
# Edit deployment settings
vim config/spike-params.yaml
```

Update domain and hosted zone:
```yaml
domain:
  name: "frank-spike.lab271.io"
  hosted_zone: "lab271.io"
  hosted_zone_id: "Z1234567890ABC"  # Get from Route53
```

### **5. Create Cross-Account Role**
```bash
# Switch to main account credentials
aws configure --profile main-account

# Create the cross-account role
python setup-cross-account-role.py

# This creates:
# ✅ IAM role in main account
# ✅ Trust policy allowing spike account
# ✅ Route53 permissions for lab271.io
# ✅ Tests role assumption
```

### **6. Test Cross-Account Access**
```bash
# Switch back to spike account
aws configure --profile spike-account

# Test cross-account setup
python deploy.py setup-accounts

# This verifies:
# ✅ Spike account access
# ✅ Cross-account role assumption
# ✅ Route53 permissions
# ✅ ECR access
```

### **7. Deploy Infrastructure**
```bash
# Preview deployment (recommended)
python deploy.py deploy --dry-run

# Deploy everything
python deploy.py deploy

# This deploys:
# 📦 Networking (VPC, subnets, security groups)
# 🔒 SSL certificate (with DNS validation)
# ⚖️ Load balancer (ALB with target group)
# 🌍 DNS records (in main account)
# 🚀 ECS service (Fargate with FastAPI)
```

## 🎮 **Usage Commands**

### **Check Status**
```bash
# Show deployment status across both accounts
python deploy.py status

# Example output:
# networking     (spike): CREATE_COMPLETE
# ssl-cert       (spike): CREATE_COMPLETE
# load-balancer  (spike): CREATE_COMPLETE
# route53        ( main): CREATE_COMPLETE
# ecs            (spike): CREATE_COMPLETE
```

### **Update Application**
```bash
# Rebuild and deploy just the container
python deploy.py update-app

# This will:
# 🐳 Build container for AMD64
# 📤 Push to ECR
# 🔄 Update ECS service
# ❤️ Wait for health checks
```

### **Destroy Infrastructure**
```bash
# Destroy all resources (with confirmation)
python deploy.py destroy --confirm-destruction

# Destroys in reverse order:
# 🗑️ ECS service
# 🗑️ Route53 records (main account)
# 🗑️ Load balancer
# 🗑️ SSL certificate
# 🗑️ Networking
```

## 🔧 **Advanced Features**

### **Cross-Account SSL Validation**
The system automatically handles SSL certificate validation across accounts:

1. **Certificate Creation**: Created in spike account
2. **Validation Records**: Automatically created in main account Route53
3. **Validation Waiting**: Monitors certificate status
4. **DNS Cleanup**: Removes validation records after completion

### **Container Multi-Architecture**
Handles building on Apple Silicon for AWS deployment:

```bash
# Automatically detects architecture and builds accordingly
# M1/M2 Mac → AMD64 for AWS Fargate
# Intel/AMD64 → Native build
```

### **Smart Dependency Management**
Stacks are deployed in dependency order:
```
networking → ssl-cert → load-balancer → route53 → ecs
```

Parameters flow between stacks:
- VPC ID from networking → load-balancer
- ALB DNS from load-balancer → route53  
- Certificate ARN from ssl-cert → route53

### **Comprehensive Error Handling**
- **Stack Events**: Displays CloudFormation events on failures
- **Cross-Account Errors**: Detailed role assumption debugging
- **Health Checks**: Validates application deployment
- **Rollback Support**: CloudFormation handles failed deployments

## 🛡️ **Safety Features**

### **✅ Account Isolation**
- **Separate AWS accounts** prevent accidental resource conflicts
- **Resource naming** with consistent prefixes (`frank-008-aws-*`)
- **Stack isolation** prevents interference with other workloads

### **✅ Cross-Account Security** 
- **External ID** prevents confused deputy attacks
- **Session limits** (1 hour maximum)
- **Minimal permissions** (only Route53 for specific zone)
- **Audit trail** in CloudTrail

### **✅ Deployment Safety**
- **Dry-run mode** shows what will be deployed
- **Confirmation prompts** for destructive operations
- **Health checks** validate successful deployment
- **Automatic rollback** on CloudFormation failures

## 🎯 **Endpoints After Deployment**

```bash
# Main application
https://frank-spike.lab271.io

# Health check
https://frank-spike.lab271.io/health

# API documentation  
https://frank-spike.lab271.io/docs

# JSON API
https://frank-spike.lab271.io/v1/hello
```

## 🐛 **Troubleshooting**

### **Common Issues**

**Cross-Account Role Issues:**
```bash
# Check role exists in main account
aws iam get-role --role-name FrankRoute53CrossAccountRole --profile main-account

# Test role assumption from spike account
aws sts assume-role \
  --role-arn arn:aws:iam::MAIN_ACCOUNT:role/FrankRoute53CrossAccountRole \
  --role-session-name test \
  --external-id frank-008-unique-external-id-2025
```

**SSL Certificate Validation:**
```bash
# Check certificate status
aws acm describe-certificate --certificate-arn CERT_ARN --region eu-west-1

# Check DNS validation records
aws route53 list-resource-record-sets --hosted-zone-id ZONE_ID
```

**Container Build Issues:**
```bash
# Build manually with correct architecture
docker buildx build --platform linux/amd64 --load -t frank-spike .

# Check ECR login
aws ecr get-login-password --region eu-west-1 | \
  docker login --username AWS --password-stdin ACCOUNT.dkr.ecr.eu-west-1.amazonaws.com
```

**ECS Service Issues:**
```bash
# Check service status
aws ecs describe-services \
  --cluster frank-008-aws-cluster \
  --services frank-008-aws-service \
  --region eu-west-1

# View logs
aws logs tail /ecs/frank-008-aws --follow --region eu-west-1
```

### **Debug Mode**
```bash
# Enable verbose logging
export AWS_CLI_LOG_LEVEL=debug
python deploy.py deploy
```

## 💰 **Cost Estimation**

### **Monthly Costs (eu-west-1)**
- **ECS Fargate**: ~$15-25 (single task, 256 CPU, 512MB RAM)
- **Application Load Balancer**: ~$16 + data transfer
- **Route53**: ~$0.50 per hosted zone
- **ECR**: ~$1 for image storage
- **CloudWatch Logs**: ~$3 for basic logging
- **SSL Certificate**: Free (AWS Certificate Manager)

**Total**: ~$35-50/month for spike environment

### **Cost Optimization**
- Use FARGATE_SPOT for non-production (50% savings)
- Set log retention to 7 days
- Clean up old ECR images automatically
- Scale ECS service to 0 when not in use

## 🔄 **Migration from OpenTofu**

If you have existing OpenTofu infrastructure:

1. **Export Resources**: Use `tofu state list` and `tofu show`
2. **Create CloudFormation**: Import resources or recreate
3. **Test in Parallel**: Deploy side-by-side first
4. **DNS Cutover**: Update Route53 records last
5. **Cleanup**: Remove OpenTofu state after validation

## 🎉 **Next Steps**

### **Immediate Enhancements**
1. **Database Integration**: Add DynamoDB for persistence
2. **Auto Scaling**: Configure ECS auto-scaling policies  
3. **Monitoring**: Add CloudWatch dashboards and alarms
4. **CI/CD Pipeline**: Automate with GitHub Actions

### **Production Readiness**
1. **Multi-Environment**: Dev/staging/production pipelines
2. **Blue/Green Deployment**: Zero-downtime deployments
3. **Backup & Recovery**: Data backup strategies
4. **Security Hardening**: WAF, security scanning, compliance

---

**🎯 This solution provides a production-ready foundation for FRANK deployment while maintaining complete safety through account isolation and cross-account security best practices.**