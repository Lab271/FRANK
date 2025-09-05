# AWS Key Management Service (KMS) Configuration

## Overview
KMS provides encryption keys for all FRANK data at rest and in transit. Each service uses dedicated customer-managed keys for isolation and granular access control.

## Key Strategy

### Customer Managed Keys (CMKs)

#### 1. S3 Encryption Key
- **Key ID**: `frank-s3-key-{env}`
- **Purpose**: Encrypt S3 buckets (raw data, artifacts, exports)
- **Key Policy**: Lambda functions, Step Functions, and authorized users
- **Key Rotation**: Enabled (annual)

#### 2. DynamoDB Encryption Key
- **Key ID**: `frank-ddb-key-{env}`
- **Purpose**: Encrypt DynamoDB tables
- **Key Policy**: Lambda functions and DynamoDB service
- **Key Rotation**: Enabled (annual)

#### 3. OpenSearch Encryption Key
- **Key ID**: `frank-os-key-{env}`
- **Purpose**: Encrypt OpenSearch cluster and indices
- **Key Policy**: OpenSearch service and Lambda functions
- **Key Rotation**: Enabled (annual)

#### 4. Application Key
- **Key ID**: `frank-app-key-{env}`
- **Purpose**: HMAC seeds, application secrets, data keys
- **Key Policy**: Lambda functions only
- **Key Rotation**: Enabled (annual)

## Key Policies

### S3 Key Policy Principals
- Lambda execution roles
- Step Functions execution roles
- Cross-account backup roles (if applicable)
- Administrative roles for key management

### DynamoDB Key Policy Principals
- Lambda execution roles
- DynamoDB service principal
- Backup service roles

### OpenSearch Key Policy Principals
- OpenSearch service principal
- Lambda execution roles for indexing
- Administrative roles

### Application Key Policy Principals
- Lambda execution roles only
- Key administrators

## Key Usage Patterns

### Encryption Context
All keys use encryption context for additional security:

```json
{
  "aws:RequestedRegion": "eu-west-1",
  "Project": "frank",
  "Environment": "{env}",
  "Service": "{service-name}"
}
```

### HMAC Pseudonymization
The application key is used to protect HMAC seeds:

```python
# Generate data key for HMAC seed encryption
data_key = kms_client.generate_data_key(
    KeyId='frank-app-key-{env}',
    KeySpec='AES_256',
    EncryptionContext={
        'Project': 'frank',
        'Environment': env,
        'Purpose': 'hmac-seed'
    }
)

# Use data key to encrypt tenant-specific HMAC seed
encrypted_seed = encrypt_with_data_key(data_key, tenant_hmac_seed)
```

## Key Grants

### Lambda Function Grants
Each Lambda function receives specific grants:

```json
{
  "GranteePrincipal": "arn:aws:iam::{account}:role/frank-lambda-{function}-role",
  "Operations": ["Decrypt", "GenerateDataKey"],
  "Constraints": {
    "EncryptionContextSubset": {
      "Service": "{service-name}"
    }
  }
}
```

## Monitoring and Compliance

### CloudTrail Integration
All KMS operations are logged in CloudTrail:
- Key usage events
- Administrative actions
- Failed access attempts

### Key Usage Metrics
CloudWatch metrics to monitor:
- Number of encryption/decryption operations
- Key usage by service
- Failed operations

### Compliance Features
- **Key Rotation**: Automatic annual rotation
- **Key Material Origin**: AWS_KMS (AWS-generated)
- **Key Spec**: SYMMETRIC_DEFAULT
- **Key Usage**: ENCRYPT_DECRYPT

## Security Best Practices

### Access Control
- Least privilege key policies
- Separate keys per service
- Regular access reviews
- Conditional access based on encryption context

### Operational Security
- Key administrators separate from key users
- Multi-person integrity for key deletion
- Regular rotation of administrative access

### Backup and Recovery
- Cross-region key replication for disaster recovery
- Encrypted backups using appropriate keys
- Documented key recovery procedures

## Environment Variables
```bash
# KMS Key ARNs
FRANK_S3_KEY_ARN=arn:aws:kms:eu-west-1:{account}:key/{key-id}
FRANK_DDB_KEY_ARN=arn:aws:kms:eu-west-1:{account}:key/{key-id}
FRANK_OS_KEY_ARN=arn:aws:kms:eu-west-1:{account}:key/{key-id}
FRANK_APP_KEY_ARN=arn:aws:kms:eu-west-1:{account}:key/{key-id}

# Key Aliases
FRANK_S3_KEY_ALIAS=alias/frank-s3-key-{env}
FRANK_DDB_KEY_ALIAS=alias/frank-ddb-key-{env}
FRANK_OS_KEY_ALIAS=alias/frank-os-key-{env}
FRANK_APP_KEY_ALIAS=alias/frank-app-key-{env}
```

## Implementation Checklist
- [ ] Create S3 encryption key with appropriate policy
- [ ] Create DynamoDB encryption key
- [ ] Create OpenSearch encryption key
- [ ] Create application encryption key
- [ ] Set up key aliases for easy reference
- [ ] Configure key rotation
- [ ] Create key grants for Lambda functions
- [ ] Set up CloudWatch monitoring
- [ ] Test encryption/decryption operations
- [ ] Document key recovery procedures
