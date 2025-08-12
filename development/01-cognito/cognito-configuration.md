# Amazon Cognito Configuration

## Overview
Amazon Cognito provides authentication and authorization for the FRANK platform using JWT tokens and custom attributes for multi-tenant access control.

## User Pool Configuration

### Basic Settings
- **Pool Name**: `frank-user-pool-{env}`
- **Sign-in Options**: Email, Username
- **Case Sensitivity**: Case insensitive
- **Username Configuration**: Email as username

### Security Settings
- **Password Policy**:
  - Minimum length: 12 characters
  - Require uppercase letters: Yes
  - Require lowercase letters: Yes
  - Require numbers: Yes
  - Require symbols: Yes
  - Temporary password validity: 7 days

- **Multi-Factor Authentication**:
  - MFA enforcement: Optional (recommended: Required for admins)
  - MFA methods: SMS, TOTP
  - SMS role ARN: `arn:aws:iam::{account}:role/service-role/frank-cognito-sms-role`

- **Advanced Security Features**:
  - Enable: Yes
  - Actions for risky sign-ins: Block
  - Actions for compromised credentials: Block

### Custom Attributes
```json
{
  "tenant_id": {
    "AttributeDataType": "String",
    "Mutable": true,
    "Required": false
  },
  "sector": {
    "AttributeDataType": "String",
    "Mutable": true,
    "Required": false
  },
  "organization": {
    "AttributeDataType": "String",
    "Mutable": true,
    "Required": false
  }
}
```

### App Client Configuration
- **Client Name**: `frank-api-client`
- **Client Secret**: No (for public clients)
- **Refresh Token Expiration**: 30 days
- **Access Token Expiration**: 1 hour
- **ID Token Expiration**: 1 hour
- **Auth Flows**: 
  - ALLOW_USER_PASSWORD_AUTH
  - ALLOW_REFRESH_TOKEN_AUTH
  - ALLOW_USER_SRP_AUTH

### Resource Server & Scopes
- **Resource Server Identifier**: `frank-api`
- **Scopes**:
  - `sightings:write` - Submit security sightings
  - `sightings:read` - Read own sightings
  - `stats:read` - Access aggregated statistics
  - `sigma:read` - Download SIGMA rules
  - `sigma:write` - Update SIGMA rules (admin only)
  - `admin:manage` - Administrative functions

### Groups Configuration
- **Publishers**: Users who can submit sightings
  - Precedence: 10
  - IAM Role: `frank-publisher-role`
  
- **Readers**: Users who can only read statistics
  - Precedence: 20
  - IAM Role: `frank-reader-role`
  
- **Admins**: Administrative users
  - Precedence: 1
  - IAM Role: `frank-admin-role`

### Lambda Triggers
- **Pre-Token Generation**: Customize JWT claims with tenant_id
- **Pre-Sign-up**: Validate email domains against allowed list
- **Post-Confirmation**: Initialize tenant metadata

## Identity Pool Configuration

### Basic Settings
- **Identity Pool Name**: `frank_identity_pool_{env}`
- **Unauthenticated Access**: Disabled
- **Provider**: Cognito User Pool

### IAM Roles
- **Authenticated Role**: `frank-cognito-authenticated-role`
- **Unauthenticated Role**: Not used

## Environment Variables
```bash
COGNITO_USER_POOL_ID=eu-west-1_XXXXXXXXX
COGNITO_CLIENT_ID=XXXXXXXXXXXXXXXXXXXXXXXXXX
COGNITO_IDENTITY_POOL_ID=eu-west-1:xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
COGNITO_REGION=eu-west-1
```

## Implementation Checklist
- [ ] Create User Pool with security settings
- [ ] Configure custom attributes
- [ ] Set up app client
- [ ] Create resource server and scopes
- [ ] Configure user groups
- [ ] Set up Lambda triggers
- [ ] Test authentication flow
- [ ] Configure MFA
- [ ] Set up monitoring and alarms
