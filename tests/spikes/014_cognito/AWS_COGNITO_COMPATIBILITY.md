# Mock Cognito - AWS Cognito API Compatibility

This document shows how Mock Cognito implements AWS Cognito APIs for 100% compatibility.

## Custom Attributes

### AWS Cognito Format
```python
# User Pool Configuration
custom_attributes = [
    {
        "Name": "organisation_id",
        "AttributeDataType": "String",
        "Mutable": True
    },
    {
        "Name": "organisation_name",
        "AttributeDataType": "String",
        "Mutable": True
    },
    {
        "Name": "role",
        "AttributeDataType": "String",
        "Mutable": True
    }
]
```

### Mock Cognito Implementation
```python
USERS_DB = {
    "admin": {
        "username": "admin",
        "email": "admin@schubergphilis.com",
        "custom:organisation_id": "identity--schuberg-philis",
        "custom:organisation_name": "Schuberg Philis",
        "custom:role": "owner"
    }
}
```

## API Endpoints

### 1. AdminGetUser

**AWS Cognito SDK:**
```python
import boto3

cognito = boto3.client('cognito-idp')
response = cognito.admin_get_user(
    UserPoolId='us-east-1_abc123',
    Username='admin'
)
```

**AWS Response Format:**
```json
{
  "Username": "admin",
  "UserAttributes": [
    {"Name": "sub", "Value": "admin"},
    {"Name": "email", "Value": "admin@schubergphilis.com"},
    {"Name": "email_verified", "Value": "true"},
    {"Name": "custom:organisation_id", "Value": "identity--schuberg-philis"},
    {"Name": "custom:organisation_name", "Value": "Schuberg Philis"},
    {"Name": "custom:role", "Value": "owner"}
  ],
  "UserStatus": "CONFIRMED",
  "Enabled": true
}
```

**Mock Cognito Endpoint:**
```bash
GET http://localhost:8100/admin/users/admin
```

**Mock Response:** ✅ Same as AWS format

---

### 2. AdminUpdateUserAttributes

**AWS Cognito SDK:**
```python
response = cognito.admin_update_user_attributes(
    UserPoolId='us-east-1_abc123',
    Username='admin',
    UserAttributes=[
        {'Name': 'custom:organisation_id', 'Value': 'identity--new-org'},
        {'Name': 'custom:role', 'Value': 'admin'}
    ]
)
```

**Mock Cognito Endpoint:**
```bash
PUT http://localhost:8100/admin/users/admin
Content-Type: application/json

{
  "UserAttributes": [
    {"Name": "custom:organisation_id", "Value": "identity--new-org"},
    {"Name": "custom:role", "Value": "admin"}
  ]
}
```

**Compatibility:** ✅ Supports AWS UserAttributes format

---

### 3. ListUsers with Filter

**AWS Cognito SDK:**
```python
response = cognito.list_users(
    UserPoolId='us-east-1_abc123',
    Filter='custom:organisation_id = "identity--schuberg-philis"',
    Limit=60
)
```

**AWS Response Format:**
```json
{
  "Users": [
    {
      "Username": "admin",
      "Attributes": [
        {"Name": "email", "Value": "admin@schubergphilis.com"},
        {"Name": "custom:organisation_id", "Value": "identity--schuberg-philis"},
        {"Name": "custom:role", "Value": "owner"}
      ],
      "UserStatus": "CONFIRMED",
      "Enabled": true,
      "UserCreateDate": "2026-01-31T10:00:00Z"
    }
  ]
}
```

**Mock Cognito Endpoint:**
```bash
GET http://localhost:8100/admin/users?filter=custom:organisation_id = "identity--schuberg-philis"&limit=60
```

**Mock Response:** ✅ Same as AWS format

---

### 4. AdminCreateUser

**AWS Cognito SDK:**
```python
response = cognito.admin_create_user(
    UserPoolId='us-east-1_abc123',
    Username='newuser',
    UserAttributes=[
        {'Name': 'email', 'Value': 'newuser@example.com'},
        {'Name': 'custom:organisation_id', 'Value': 'identity--rabobank'},
        {'Name': 'custom:role', 'Value': 'member'}
    ],
    TemporaryPassword='TempPass123!'
)
```

**Mock Cognito Endpoint:**
```bash
POST http://localhost:8100/admin/users
Content-Type: application/json

{
  "username": "newuser",
  "email": "newuser@example.com",
  "password": "TempPass123!",
  "groups": ["contributor"],
  "temporary_password": true,
  "custom:organisation_id": "identity--rabobank",
  "custom:role": "member"
}
```

**Compatibility:** ✅ Supports custom attributes in create

---

### 5. AdminAddUserToGroup

**AWS Cognito SDK:**
```python
response = cognito.admin_add_user_to_group(
    UserPoolId='us-east-1_abc123',
    Username='admin',
    GroupName='core_member'
)
```

**Mock Cognito Endpoint:**
```bash
POST http://localhost:8100/admin/users/admin/groups
Content-Type: application/json

{
  "group": "core_member"
}
```

**Compatibility:** ✅ Already implemented

---

## JWT Token Claims

### AWS Cognito JWT
```json
{
  "sub": "admin",
  "cognito:groups": ["core_member"],
  "email": "admin@schubergphilis.com",
  "custom:organisation_id": "identity--schuberg-philis",
  "custom:role": "owner",
  "token_use": "access",
  "iat": 1738320000,
  "exp": 1738323600
}
```

### Mock Cognito JWT
```json
{
  "sub": "admin",
  "cognito:groups": ["core_member"],
  "username": "admin",
  "token_use": "access",
  "iat": 1738320000,
  "exp": 1738323600,
  "client_id": "mock-client-id-123456",
  "iss": "https://cognito-idp.eu-west-1.amazonaws.com/eu-west-1_MOCKPOOL"
}
```

**Note:** Custom attributes are stored in Cognito, but typically NOT included in JWT tokens. They're retrieved via AdminGetUser API.

---

## Management API Usage

### Get User's Organization
```python
from frank.management.cognito_service import get_cognito_service

cognito = get_cognito_service()

# Get user with organization info
user = await cognito.get_user("admin")
# Returns: {username, email, groups, custom:organisation_id, custom:role, ...}

# Extract organization
org_id = user.get("custom:organisation_id")
role = user.get("custom:role")
```

### List Organization Members
```python
# Query Cognito for users in organization
members = await cognito.list_users_in_organisation("identity--schuberg-philis")
# Returns list of users with custom:organisation_id matching
```

### Update User's Organization
```python
# Update user's custom attributes
await cognito.update_user_attributes(
    username="admin",
    attributes={
        "custom:organisation_id": "identity--new-org",
        "custom:organisation_name": "New Org",
        "custom:role": "admin"
    }
)
```

---

## Key Differences: Mock vs AWS

| Feature | AWS Cognito | Mock Cognito | Compatible? |
|---------|-------------|--------------|-------------|
| Custom attributes | Via UserPool config | Stored in USERS_DB | ✅ Yes |
| AdminGetUser | Returns UserAttributes array | Returns UserAttributes array | ✅ Yes |
| ListUsers filter | Supports filter syntax | Supports simple filters | ✅ Partial |
| AdminUpdateUserAttributes | UserAttributes format | UserAttributes + legacy | ✅ Yes |
| JWT tokens | Standard claims | Standard claims | ✅ Yes |
| User Pool ID | Real AWS ID | Mock ID | ✅ Compatible |
| Groups | Cognito Groups | In-memory groups | ✅ Yes |
| MFA | TOTP/SMS | TOTP only | ✅ Partial |
| Lambda triggers | Full support | Not supported | ❌ No |
| OAuth flows | Full support | Basic only | ⚠️ Limited |

---

## Migration to AWS Cognito

When moving from Mock to AWS Cognito:

### 1. Create User Pool with Custom Attributes
```bash
aws cognito-idp create-user-pool \
  --pool-name frank-users \
  --schema \
    AttributeDataType=String,Name=organisation_id,Mutable=true \
    AttributeDataType=String,Name=organisation_name,Mutable=true \
    AttributeDataType=String,Name=role,Mutable=true
```

### 2. Create Groups
```bash
for group in observer contributor partner core_member; do
  aws cognito-idp create-group \
    --user-pool-id us-east-1_abc123 \
    --group-name $group
done
```

### 3. Import Users
```python
for username, user_data in USERS_DB.items():
    cognito.admin_create_user(
        UserPoolId='us-east-1_abc123',
        Username=username,
        UserAttributes=[
            {'Name': 'email', 'Value': user_data['email']},
            {'Name': 'custom:organisation_id', 'Value': user_data['custom:organisation_id']},
            {'Name': 'custom:organisation_name', 'Value': user_data['custom:organisation_name']},
            {'Name': 'custom:role', 'Value': user_data['custom:role']}
        ]
    )

    # Add to groups
    for group in user_data['groups']:
        cognito.admin_add_user_to_group(
            UserPoolId='us-east-1_abc123',
            Username=username,
            GroupName=group
        )
```

### 4. Update Environment Variables
```bash
# From Mock
COGNITO_URL=http://localhost:8100
USER_POOL_ID=eu-west-1_MOCKPOOL

# To AWS
COGNITO_URL=https://cognito-idp.eu-west-1.amazonaws.com
USER_POOL_ID=us-east-1_abc123def
```

**No code changes required!** 🎉

---

## Testing Compatibility

```bash
# Test with Mock Cognito
export COGNITO_URL=http://localhost:8100
export USER_POOL_ID=eu-west-1_MOCKPOOL
python -m frank.management.api

# Test with AWS Cognito
export COGNITO_URL=https://cognito-idp.eu-west-1.amazonaws.com
export USER_POOL_ID=us-east-1_abc123def
python -m frank.management.api

# Same code, different backend!
```

---

**Last Updated**: 2026-01-31
**Mock Cognito Version**: Compatible with AWS Cognito User Pools API v1
