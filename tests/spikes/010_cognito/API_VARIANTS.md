# FRANK Simple API - Authentication Variants

This directory contains three variants of the FRANK Simple API demonstrating different authentication approaches:

## 🎯 API Variants

### 1. `simple_api_unified.py` - **RECOMMENDED**
**Unified API supporting both Mock Cognito and AWS Cognito**

```bash
# Run with Mock Cognito (default)
python simple_api_unified.py

# Run with AWS Cognito
python simple_api_unified.py --use-aws --user-pool-id your-pool-id --app-client-id your-client-id

# Environment variable configuration
export USE_AWS_COGNITO=true
export USER_POOL_ID=eu-central-1_xxxxxxxxx
export APP_CLIENT_ID=xxxxxxxxxxxxxxxxxx
python simple_api_unified.py
```

**Features:**
- ✅ Single codebase for both authentication providers
- ✅ Command-line and environment variable configuration
- ✅ Automatic provider detection and setup
- ✅ Consistent API endpoints and responses
- ✅ Enhanced error handling and logging
- ✅ Provider information in responses

### 2. `simple_api.py` - Mock Cognito Only
**Dedicated Mock Cognito implementation**

```bash
# Start Mock Cognito service first
python mock_cognito.py

# Run API (in another terminal)
python simple_api.py
```

### 3. `simple_api_aws.py` - AWS Cognito Only
**Dedicated AWS Cognito implementation**

```bash
# Set AWS environment variables
export USER_POOL_ID=eu-central-1_xxxxxxxxx
export APP_CLIENT_ID=xxxxxxxxxxxxxxxxxx
export AWS_REGION=eu-central-1

# Run API
python simple_api_aws.py
```

## 🧪 Testing

### Unified Testing Script
Test all authentication scenarios with the unified API:

```bash
# Test Mock Cognito mode
python test_unified_api.py

# Test AWS Cognito mode (requires AWS setup)
python test_unified_api.py --test-aws

# Custom API URL
python test_unified_api.py --api-url http://localhost:8001
```

### Individual Testing Scripts
- `test_simple_api.py` - Tests Mock Cognito variant
- `test_aws_cognito.py` - Tests AWS Cognito variant
- `test_cognito_api.py` - General authentication testing

## 🔐 Authentication Flow

### Mock Cognito Flow
1. **Start Mock Service**: `python mock_cognito.py`
2. **Get Token**: POST to `http://localhost:8100/auth/login`
3. **Access API**: Use token in Authorization header

### AWS Cognito Flow
1. **Configure AWS**: Set User Pool ID and App Client ID
2. **Get Token**: Use AWS SDK or Cognito endpoints
3. **Access API**: Use token in Authorization header

## 🏗️ AccessTier Hierarchy

All variants support the same role-based access control:

```
PUBLIC (0) - No authentication required
└── OBSERVER (1) - Basic read access
    └── CONTRIBUTOR (2) - Submit indicators, read threat intel
        └── PARTNER (3) - Advanced features, IOCs, feed management
            └── CORE_MEMBER (4) - Full admin access
```

## 📋 API Endpoints

All variants expose the same endpoints:

| Endpoint | Access Level | Description |
|----------|-------------|-------------|
| `GET /` | Public | Service information |
| `GET /health` | Public | Health check |
| `GET /public` | Public | Public data |
| `GET /observer` | Observer+ | Observer level data |
| `GET /contributor` | Contributor+ | Contributor level data |
| `GET /partner` | Partner+ | Partner level data |
| `GET /core_member` | Core Member | Core member level data |
| `GET /user-info` | Authenticated | Current user information |
| `GET /docs` | Public | Swagger documentation |

## 🔧 Configuration

### Getting AWS Cognito Credentials

Use the provided script to automatically find your Cognito User Pool and App Client:

```bash
# Run the credential discovery script
./get-cognito-ids.sh

# Or manually with AWS CLI
aws cognito-idp list-user-pools --max-results 60 --profile spike-account --region eu-central-1
aws cognito-idp list-user-pool-clients --user-pool-id YOUR_POOL_ID --profile spike-account --region eu-central-1
```

### Environment Variables

#### Unified API (`simple_api_unified.py`)
```bash
# Authentication Provider
USE_AWS_COGNITO=false|true

# AWS Cognito (when USE_AWS_COGNITO=true)
AWS_REGION=eu-central-1
USER_POOL_ID=eu-central-1_xxxxxxxxx
APP_CLIENT_ID=xxxxxxxxxxxxxxxxxx

# Mock Cognito (when USE_AWS_COGNITO=false)
MOCK_COGNITO_URL=http://localhost:8100
```

#### Individual APIs
See respective files for specific configuration requirements.

## 🚀 Quick Start

### Option 1: Unified API with Mock Cognito (Recommended)
```bash
# Terminal 1: Start Mock Cognito
python mock_cognito.py

# Terminal 2: Start Unified API
python simple_api_unified.py

# Terminal 3: Test
python test_unified_api.py
```

### Option 2: Unified API with AWS Cognito
```bash
# Get AWS Cognito credentials first
./get-cognito-ids.sh

# Or manually with AWS CLI
aws cognito-idp list-user-pools --max-results 60 --profile spike-account --region eu-central-1
aws cognito-idp list-user-pool-clients --user-pool-id YOUR_POOL_ID --profile spike-account --region eu-central-1

# Set AWS configuration
export USE_AWS_COGNITO=true
export USER_POOL_ID=your-pool-id
export APP_CLIENT_ID=your-client-id

# Start Unified API
python simple_api_unified.py --use-aws

# Test (requires AWS setup)
python test_unified_api.py --test-aws
```

## 📊 Response Format

All endpoints return consistent JSON responses:

```json
{
  "message": "Success message",
  "user_info": {
    "username": "testuser_contributor",
    "access_tier": "contributor",
    "groups": ["contributor"],
    "organisation_id": "org-testuser_contributor",
    "provider": "mock_cognito|aws_cognito"
  },
  "data": { /* endpoint-specific data */ },
  "timestamp": "2025-10-08T..."
}
```

## 🔍 Migration Guide

### From Individual APIs to Unified API

1. **Replace imports**: No changes needed
2. **Update startup**: Use `simple_api_unified.py` with appropriate flags
3. **Set environment**: Configure `USE_AWS_COGNITO` appropriately
4. **Update tests**: Use `test_unified_api.py` for comprehensive testing

### Benefits of Unified Approach

- ✅ **Single Codebase**: Easier maintenance and consistency
- ✅ **Environment Flexibility**: Switch between Mock/AWS without code changes
- ✅ **Better Testing**: Unified test suite covers both scenarios
- ✅ **Production Ready**: Proper error handling and configuration management
- ✅ **Documentation**: Automatic provider detection in API docs

## 🛠️ Development

### Adding New Endpoints
1. Add endpoint function to `simple_api_unified.py`
2. Use `@app.get()` decorator with appropriate path
3. Add `current_user: Dict[str, Any] = Depends(get_current_user)` for protected endpoints
4. Use `check_access_level()` for role-based access control
5. Update tests in `test_unified_api.py`

### Adding New Access Tiers
1. Update `AccessTier` enum in `frank.core.enum`
2. Update `get_access_tier_from_groups()` logic if needed
3. Add corresponding endpoints and tests
4. Update user configurations in Mock Cognito and AWS Cognito

This unified approach provides the best of both worlds: the simplicity of Mock Cognito for development and the security of AWS Cognito for production, all with a single, maintainable codebase.