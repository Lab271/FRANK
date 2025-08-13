# FRANK Deployment - Next Steps

## Summary

I attempted to deploy the FRANK cybersecurity threat intelligence platform to AWS. Several core components were successfully deployed but the Lambda functions encountered issues. All resources have been cleaned up.

## ✅ What Was Fixed During Deployment

### 1. Cognito Template Issues
- **Problem**: SMS MFA role lacked proper SNS permissions
- **Fix**: Updated `CognitoSMSRole` in `/development/01-cognito/cognito-template.yaml`:
  ```yaml
  Policies:
    - PolicyName: CognitoSNSPolicy
      PolicyDocument:
        Version: '2012-10-17'
        Statement:
          - Effect: Allow
            Action:
              - sns:Publish
            Resource: '*'
  ```

### 2. S3 Template Configuration
- **Problem**: S3 lifecycle policy tried to transition to STANDARD_IA after 7 days (minimum is 30)
- **Fix**: Updated exports bucket lifecycle in `/development/03-s3/s3-template.yaml`:
  ```yaml
  TransitionInDays: 30  # Changed from 7
  StorageClass: STANDARD_IA
  ```
- **Problem**: Lambda notification configuration referenced non-existent functions
- **Fix**: Removed notification configuration temporarily
- **Problem**: Invalid bucket policies with role wildcards
- **Fix**: Removed bucket policies temporarily (can be added after Lambda deployment)

### 3. DynamoDB Template Issues
- **Problem**: Invalid billing mode `ON_DEMAND` 
- **Fix**: Changed to `PAY_PER_REQUEST` in `/development/04-dynamodb/dynamodb-template.yaml`
- **Problem**: Missing SSEType in encryption configuration
- **Fix**: Added `SSEType: KMS` to all SSESpecification sections

### 4. IAM Permissions
- **Problem**: Deployment user lacked CloudWatch permissions for DynamoDB alarms
- **Fix**: Updated `/frank-deployment-policy.json` to include `"cloudwatch:*"`

### 5. Lambda Configuration
- **Problem**: Template hardcoded to Python 3.11 but system has Python 3.12
- **Fix**: Updated `/development/05-lambda/generate-lambda-config.py`:
  ```python
  'Runtime': 'python3.12'
  'CompatibleRuntimes': ['python3.12']
  ```

## ❌ Remaining Issues That Need Fixing

### 1. Lambda Functions - Critical Issues

#### Template Generation Problems
- **File**: `/development/05-lambda/generate-lambda-config.py`
- **Issues**:
  - References non-existent resources: `OpenSearchDomain`, `SigmaTranslateStateMachine`
  - Invalid CloudFormation syntax for outputs with `!Sub` in export names
  - Incorrect handler references (`lambda_function.lambda_handler` vs `index.handler`)
  - S3 event configuration references buckets by name instead of using proper CloudFormation references

#### Missing Source Code
- Lambda function directories exist but only contain placeholder code
- Need actual implementation for:
  - `/src/ingest_sightings/index.py`
  - `/src/write_persistence/index.py` 
  - `/src/query_stats/index.py`
  - `/src/sigma_update/index.py`

#### Dependencies Issues
- Lambda layer references non-existent dependencies
- `requirements.txt` files missing in function directories
- Layer build process not properly configured

### 2. Missing Infrastructure Components

#### OpenSearch Cluster
- Lambda functions reference `OpenSearchDomain.DomainEndpoint` but cluster not deployed
- Template exists: `/development/07-opensearch/opensearch-template.yaml`
- Needs deployment before Lambda functions

#### Step Functions
- SIGMA update function references `SigmaTranslateStateMachine`
- Template exists: `/development/08-step-functions/stepfunctions-template.yaml`
- Required for SIGMA rule processing workflow

#### API Gateway
- No actual API Gateway template exists
- Only configuration documentation: `/development/06-api-gateway/api-gateway-configuration.md`
- Need to create CloudFormation template

### 3. Template Dependencies and Ordering

#### Circular Dependencies
- Lambda functions need S3 buckets for deployment artifacts ✓
- S3 buckets want to notify Lambda functions (removed temporarily)
- DynamoDB references need to be resolved properly

#### Missing Cross-Stack References
- Lambda functions hardcode resource names instead of using CloudFormation imports
- No proper dependency chain between stacks

## 🔧 Recommended Fix Approach

### Phase 1: Fix Core Infrastructure (1-2 hours)
1. **Deploy in correct order**:
   ```bash
   ./scripts/deploy-all.sh kms
   ./scripts/deploy-all.sh cognito  
   ./scripts/deploy-all.sh s3
   ./scripts/deploy-all.sh dynamodb
   ```

### Phase 2: Deploy Supporting Services (2-3 hours)
2. **OpenSearch**: Deploy cluster before Lambda functions
3. **Step Functions**: Deploy workflow definitions
4. **API Gateway**: Create and deploy template

### Phase 3: Fix Lambda Deployment (3-4 hours)
5. **Simplify Lambda template**:
   - Remove references to non-existent resources
   - Fix export name syntax
   - Use proper CloudFormation references
6. **Create basic function implementations**
7. **Fix layer dependencies and build process**
8. **Test individual function deployments**

### Phase 4: Integration (2-3 hours)
9. **Add back S3 notifications** after Lambda functions exist
10. **Add back S3 bucket policies** with proper permissions
11. **Test end-to-end functionality**

## 📋 Files Modified During This Session

### Modified Files:
- `/development/01-cognito/cognito-template.yaml` - Fixed SNS permissions
- `/development/03-s3/s3-template.yaml` - Fixed lifecycle policy, removed notifications/policies
- `/development/04-dynamodb/dynamodb-template.yaml` - Fixed billing mode and SSE configuration  
- `/development/05-lambda/generate-lambda-config.py` - Updated Python version, fixed handlers
- `/development/scripts/deploy-all.sh` - Added S3 bucket parameter for SAM deployment
- `/frank-deployment-policy.json` - Added CloudWatch permissions

### Created Files:
- `/development/05-lambda/src/*/index.py` - Placeholder Lambda functions
- `/development/05-lambda/layers/dependencies/requirements.txt` - Empty requirements file

## 🏠 Current State

**All AWS resources have been cleaned up.** You can safely start fresh with the fixes above.

## 💰 Cost Impact

During this session:
- **Deployed resources for ~2 hours**: Estimated cost < $1 USD
- **All resources deleted**: No ongoing costs
- **Recommendation**: Use smaller instance sizes for dev environment to minimize costs during development

## 🚀 Quick Start for Next Time

1. Apply all the template fixes mentioned above
2. Deploy basic infrastructure first (KMS, Cognito, S3, DynamoDB)
3. Create simplified Lambda template without external dependencies
4. Deploy Lambda functions with basic implementations
5. Add back integrations incrementally

The FRANK platform has solid architectural foundations. The main issues were template syntax errors and missing dependencies, which are straightforward to fix with the guidance above.