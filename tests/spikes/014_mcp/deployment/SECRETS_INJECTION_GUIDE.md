# Secure Environment Variable Injection in AWS Fargate

This guide teaches you how to securely inject sensitive environment variables (like API keys) into AWS Fargate containers using AWS Secrets Manager.

## Why Secrets Manager?

**Problems with traditional approaches:**
- ❌ Hardcoding secrets in code → exposed in version control
- ❌ Environment variables in CloudFormation → visible in template
- ❌ Environment variables in ECS task definition → visible in console
- ❌ Build-time injection → secrets in Docker images

**Benefits of AWS Secrets Manager:**
- ✅ Secrets encrypted at rest using AWS KMS
- ✅ Secrets never appear in CloudFormation templates
- ✅ Automatic rotation support
- ✅ Fine-grained IAM access control
- ✅ Audit trail via CloudTrail
- ✅ Versioning and rollback support

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  1. Secret stored in AWS Secrets Manager (encrypted at rest) │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    │ IAM permissions via TaskExecutionRole
                    │
┌───────────────────▼─────────────────────────────────────────┐
│  2. ECS pulls secret at container startup                    │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    │ Injected as environment variable
                    │
┌───────────────────▼─────────────────────────────────────────┐
│  3. Container reads ABUSEIPDB_API_KEY from environment      │
└─────────────────────────────────────────────────────────────┘
```

## Step-by-Step Implementation

### Step 1: Create a Secret in AWS Secrets Manager

```bash
# Create a new secret with JSON structure
aws secretsmanager create-secret \
    --name mcp/log-server/env \
    --description "Environment variables for MCP Log Server" \
    --secret-string '{"ABUSEIPDB_API_KEY":"your-actual-api-key-here"}' \
    --region us-east-1

# Output:
# {
#     "ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:mcp/log-server/env-AbCdEf",
#     "Name": "mcp/log-server/env",
#     "VersionId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
# }
```

**Important notes:**
- The secret value is a JSON string with key-value pairs
- The secret name follows a naming convention: `mcp/<service>/<type>`
- Save the ARN - you'll need it for the task definition

### Step 2: Grant IAM Permissions

The ECS Task Execution Role needs permission to read the secret:

```yaml
# In CloudFormation template
TaskExecutionRole:
  Type: AWS::IAM::Role
  Properties:
    AssumeRolePolicyDocument:
      Version: '2012-10-17'
      Statement:
        - Effect: Allow
          Principal:
            Service: ecs-tasks.amazonaws.com
          Action: sts:AssumeRole
    ManagedPolicyArns:
      - arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
    Policies:
      - PolicyName: SecretsManagerAccess
        PolicyDocument:
          Version: '2012-10-17'
          Statement:
            # Permission to read secrets
            - Effect: Allow
              Action:
                - secretsmanager:GetSecretValue
              Resource:
                - arn:aws:secretsmanager:region:account:secret:mcp/*
            
            # Permission to decrypt using KMS (required)
            - Effect: Allow
              Action:
                - kms:Decrypt
              Resource: '*'
              Condition:
                StringEquals:
                  'kms:ViaService': 'secretsmanager.region.amazonaws.com'
```

**Key points:**
- Use `secretsmanager:GetSecretValue` - NOT `secretsmanager:DescribeSecret`
- Include KMS decrypt permission (Secrets Manager uses KMS for encryption)
- Use resource patterns like `mcp/*` to allow multiple secrets

### Step 3: Reference Secret in ECS Task Definition

```yaml
# In CloudFormation template
TaskDefinition:
  Type: AWS::ECS::TaskDefinition
  Properties:
    Family: log-mcp-task
    ExecutionRoleArn: !GetAtt TaskExecutionRole.Arn
    ContainerDefinitions:
      - Name: log-mcp-container
        Image: your-ecr-image
        
        # Regular environment variables (non-sensitive)
        Environment:
          - Name: SERVER_NAME
            Value: log-mcp
          - Name: LOG_LEVEL
            Value: info
        
        # Secrets from AWS Secrets Manager
        Secrets:
          - Name: ABUSEIPDB_API_KEY
            ValueFrom: arn:aws:secretsmanager:region:account:secret:mcp/log-server/env:ABUSEIPDB_API_KEY::
```

**Secret ValueFrom format:**
```
arn:aws:secretsmanager:region:account:secret:secret-name:json-key::
                                                          ^^^^^^^^
                                                          Extract this key from JSON
```

For example, if your secret contains:
```json
{
  "ABUSEIPDB_API_KEY": "abc123",
  "OTHER_KEY": "xyz789"
}
```

You reference specific keys like:
```yaml
Secrets:
  - Name: ABUSEIPDB_API_KEY
    ValueFrom: arn:...:secret:mcp/log-server/env:ABUSEIPDB_API_KEY::
  - Name: OTHER_KEY
    ValueFrom: arn:...:secret:mcp/log-server/env:OTHER_KEY::
```

### Step 4: Use Secret in Your Application

In your Python application, secrets are available as regular environment variables:

```python
import os

# Read the secret (injected at container startup)
api_key = os.getenv('ABUSEIPDB_API_KEY')

if not api_key:
    raise ValueError("ABUSEIPDB_API_KEY not found in environment")

# Use the API key
async with aiohttp.ClientSession() as session:
    headers = {'Key': api_key}
    async with session.get(url, headers=headers) as response:
        data = await response.json()
```

## Security Best Practices

### 1. Use Least Privilege IAM Policies

```yaml
# ❌ BAD: Too broad
Resource: '*'

# ✅ GOOD: Specific resources
Resource:
  - arn:aws:secretsmanager:us-east-1:123456789012:secret:mcp/*
```

### 2. Enable Secret Rotation

```bash
# Enable automatic rotation (requires Lambda function)
aws secretsmanager rotate-secret \
    --secret-id mcp/log-server/env \
    --rotation-lambda-arn arn:aws:lambda:region:account:function:SecretsManagerRotation \
    --rotation-rules AutomaticallyAfterDays=30
```

### 3. Use Different Secrets Per Environment

```
mcp/log-server/dev
mcp/log-server/staging
mcp/log-server/prod
```

### 4. Enable CloudTrail Logging

All secret access is logged in CloudTrail:

```bash
# Query who accessed a secret
aws cloudtrail lookup-events \
    --lookup-attributes AttributeKey=ResourceName,AttributeValue=mcp/log-server/env \
    --max-results 50
```

### 5. Use Resource Tags

```bash
aws secretsmanager tag-resource \
    --secret-id mcp/log-server/env \
    --tags Key=Environment,Value=production Key=Service,Value=log-mcp
```

## Common Pitfalls and Solutions

### Pitfall 1: Wrong IAM Role

**Problem:** Container can't access secret
**Error:** `ResourceNotFoundException` or `AccessDeniedException`

**Solution:** Ensure permissions are on TaskExecutionRole (not TaskRole):
```yaml
ExecutionRoleArn: !GetAtt TaskExecutionRole.Arn  # ← This role needs secrets access
TaskRoleArn: !GetAtt TaskRole.Arn               # ← This is for application permissions
```

### Pitfall 2: Missing KMS Permission

**Problem:** Secret exists but container can't decrypt
**Error:** `AccessDeniedException: User is not authorized to perform: kms:Decrypt`

**Solution:** Add KMS decrypt permission:
```yaml
- Effect: Allow
  Action:
    - kms:Decrypt
  Resource: '*'
  Condition:
    StringEquals:
      'kms:ViaService': 'secretsmanager.region.amazonaws.com'
```

### Pitfall 3: Wrong Secret Format

**Problem:** Secret value is retrieved but parsing fails
**Error:** `KeyError` in application

**Solution:** Use correct JSON structure and key reference:
```bash
# Correct JSON format
'{"ABUSEIPDB_API_KEY":"value"}'

# Correct ARN format with key
arn:...:secret:name:ABUSEIPDB_API_KEY::
                    ^^^^^^^^^^^^^^^^^
                    Must match JSON key exactly
```

### Pitfall 4: Secret Not Found

**Problem:** Secret doesn't exist in specified region
**Error:** `ResourceNotFoundException`

**Solution:** Create secret in same region as ECS cluster:
```bash
aws secretsmanager create-secret \
    --region us-east-1 \  # ← Must match ECS region
    --name mcp/log-server/env
```

## Verification and Debugging

### Check if secret exists:
```bash
aws secretsmanager describe-secret \
    --secret-id mcp/log-server/env \
    --region us-east-1
```

### View secret value (use carefully!):
```bash
aws secretsmanager get-secret-value \
    --secret-id mcp/log-server/env \
    --query SecretString \
    --output text
```

### Check IAM permissions:
```bash
aws iam get-role-policy \
    --role-name mcp-platform-TaskExecutionRole \
    --policy-name SecretsManagerAccess
```

### View ECS task logs:
```bash
aws logs tail /ecs/mcp-platform --follow
```

### Test secret access from within container:
```bash
# Exec into running container
aws ecs execute-command \
    --cluster mcp-cluster \
    --task task-id \
    --container log-mcp-container \
    --interactive \
    --command "/bin/bash"

# Inside container, check environment
echo $ABUSEIPDB_API_KEY
```

## Cost Considerations

**AWS Secrets Manager Pricing (us-east-1):**
- $0.40 per secret per month
- $0.05 per 10,000 API calls
- Free tier: 30-day trial for new secrets

**Example monthly cost:**
- 1 secret: $0.40/month
- 10,000 container starts (10,000 secret retrievals): $0.05
- **Total: ~$0.45/month per secret**

**Tip:** Store multiple values in one secret to reduce costs:
```json
{
  "ABUSEIPDB_API_KEY": "key1",
  "OTHER_API_KEY": "key2",
  "DATABASE_PASSWORD": "pass3"
}
```

## Alternative: AWS Systems Manager Parameter Store

For non-critical secrets or when budget is tight:

```yaml
# CloudFormation - using Parameter Store instead
Secrets:
  - Name: ABUSEIPDB_API_KEY
    ValueFrom: arn:aws:ssm:region:account:parameter/mcp/log-server/abuseipdb-key
```

**Differences:**
- Parameter Store: Free for standard parameters, $0.05/10K calls for advanced
- Secrets Manager: Built-in rotation, better audit trail, versioning
- **Recommendation:** Use Secrets Manager for sensitive data

## Summary Checklist

- [ ] Create secret in AWS Secrets Manager
- [ ] Save secret ARN
- [ ] Add `secretsmanager:GetSecretValue` to TaskExecutionRole
- [ ] Add `kms:Decrypt` permission to TaskExecutionRole
- [ ] Reference secret in task definition using `Secrets` field
- [ ] Use correct ARN format: `...secret:name:json-key::`
- [ ] Enable CloudTrail logging
- [ ] Set up secret rotation (optional)
- [ ] Test secret access in container
- [ ] Never log or print secret values

## Resources

- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [ECS Task Execution IAM Role](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html)
- [Secrets in ECS Task Definitions](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/specifying-sensitive-data-secrets.html)
- [AWS Security Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
