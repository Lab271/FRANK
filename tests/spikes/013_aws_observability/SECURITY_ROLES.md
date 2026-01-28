# FRANK Security Roles - Ansible Integration

## Overview

The security roles creation has been integrated into the main Ansible playbook. This allows you to create and manage IAM roles using infrastructure-as-code principles instead of manual shell scripts.

## Usage

### 1. Create Security Roles

```bash
# Create all security roles using Ansible
ansible-playbook ansible/playbook.yml --tags security

# Or specifically create roles
ansible-playbook ansible/playbook.yml --tags create-roles

# Create specific role types
ansible-playbook ansible/playbook.yml --tags infra-creator
ansible-playbook ansible/playbook.yml --tags app-deployer
ansible-playbook ansible/playbook.yml --tags data-reader
```

### 2. Customize Security Configuration

You can override security settings using extra vars:

```bash
# Use custom external ID
ansible-playbook ansible/playbook.yml --tags security \
  -e security_external_id="my-custom-external-id"

# Use different AWS profile
ansible-playbook ansible/playbook.yml --tags security \
  -e aws_profile="my-admin-profile"
```

### 3. Full Deployment with Security Setup

```bash
# Complete deployment: security roles + infrastructure + application
ansible-playbook ansible/playbook.yml --tags security,ssl,docker,cloudformation,deploy

# Or step by step
ansible-playbook ansible/playbook.yml --tags security     # 1. Create roles
ansible-playbook ansible/playbook.yml --tags ssl          # 2. SSL setup
ansible-playbook ansible/playbook.yml --tags docker       # 3. Build images
ansible-playbook ansible/playbook.yml --tags cloudformation # 4. Deploy infra
ansible-playbook ansible/playbook.yml --tags deploy       # 5. Deploy app
```

## Generated Files

After running the security tasks, you'll find:

1. **AWS CLI Configuration**: `aws-config-roles-{ACCOUNT-ID}.ini`
   - Ready-to-use AWS CLI profiles
   - Includes MFA configuration
   - Time-limited sessions

2. **Temporary Files** (automatically cleaned up):
   - Trust policy with your account ID
   - Temporary role assumption files

## Role Specifications

| Role Name | Max Session | MFA Required | Purpose |
|-----------|------------|--------------|---------|
| `frank-infra-creator` | 2 hours | ✅ Yes | Create infrastructure |
| `frank-infra-destroyer` | 30 minutes | ✅ Yes | Delete infrastructure |
| `frank-app-deployer` | 4 hours | ❌ No | Deploy applications |
| `frank-data-reader` | 8 hours | ❌ No | Read data and logs |
| `frank-emergency-admin` | 15 minutes | ✅ Yes | Emergency access |

## Configuration Variables

### Default Variables (in playbook.yml)
```yaml
security_external_id: "frank-deployment-access"
security_require_mfa: true
aws_profile: "spike-account"
aws_region: "eu-central-1"
```

### Override Examples
```bash
# Custom external ID for additional security
-e security_external_id="my-org-frank-access"

# Disable MFA requirement (not recommended)
-e security_require_mfa=false

# Different region
-e aws_region="us-east-1"
```

## Post-Creation Steps

### 1. Update AWS CLI Configuration

```bash
# Copy generated config to your AWS config
cat aws-config-roles-{ACCOUNT-ID}.ini >> ~/.aws/config

# Edit to add your actual MFA serial number
vim ~/.aws/config
```

### 2. Test Role Assumption

```bash
# Test infrastructure creator role
aws sts assume-role \
  --role-arn arn:aws:iam::{ACCOUNT-ID}:role/frank-infra-creator \
  --role-session-name test-session \
  --external-id frank-deployment-access \
  --profile spike-account

# Test using the new profiles (after config update)
aws sts get-caller-identity --profile frank-data
aws sts get-caller-identity --profile frank-deploy
```

### 3. Update Deployment Scripts

Modify your deployment commands to use specific roles:

```bash
# Infrastructure creation with limited role
ansible-playbook ansible/playbook.yml --tags cloudformation \
  -e aws_profile="frank-infra"

# Application deployment with deployment role  
ansible-playbook ansible/playbook.yml --tags deploy \
  -e aws_profile="frank-deploy"

# Data operations with read-only role
aws dynamodb scan --table-name frank-data --profile frank-data
```

## Security Benefits

✅ **Infrastructure as Code**: Roles defined in version control  
✅ **Idempotent**: Safe to run multiple times  
✅ **Auditable**: All changes tracked in Ansible logs  
✅ **Consistent**: Same roles across environments  
✅ **Reversible**: Can delete and recreate roles  

## Troubleshooting

### Role Already Exists
```bash
# If roles exist, Ansible will update them
# To force recreation, delete first:
aws iam delete-role --role-name frank-infra-creator --profile spike-account
```

### Permission Denied
```bash
# Ensure your spike-account profile has IAM permissions:
# - iam:CreateRole
# - iam:PutRolePolicy  
# - iam:AttachRolePolicy
# - iam:TagRole
```

### MFA Issues
```bash
# Ensure MFA device is configured:
aws iam list-mfa-devices --profile spike-account

# Create MFA device if needed:
aws iam create-virtual-mfa-device --virtual-mfa-device-name your-username
```

## Migration from Shell Script

If you previously used `create-security-roles.sh`:

1. **Backup existing roles** (if you want to preserve them)
2. **Run Ansible version**: `ansible-playbook ansible/playbook.yml --tags security`
3. **Update AWS CLI config** with generated file
4. **Test role assumption** to ensure everything works
5. **Remove old shell script** (now deprecated)

The Ansible version provides the same functionality but with better:
- Error handling
- Idempotency  
- Integration with your deployment pipeline
- Version control tracking