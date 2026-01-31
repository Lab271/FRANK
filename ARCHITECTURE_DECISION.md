# Architecture Decision: User Organizations in Cognito

## Decision

**All user organization data lives in Cognito (AWS or Mock), NOT in the database.**

## Two Types of Organizations

### 1. Sighting Organizations (DynamoDB)
Organizations mentioned in threat intelligence data:
- **Submitters**: Who reported the threat
- **Hit Targets**: Who was affected
- Stored in DynamoDB as part of submission data
- Already implemented ✅

### 2. User Organizations (Cognito)
Organizations that USE the FRANK platform:
- Have users with credentials
- Have access tiers (observer, contributor, partner, core_member)
- Have roles (owner, admin, member)
- Stored in Cognito custom attributes ✅

## Cognito User Structure

### AWS Cognito Custom Attributes
```json
{
  "username": "admin",
  "email": "admin@schubergphilis.com",
  "groups": ["core_member"],
  "custom:organisation_id": "identity--schuberg-philis",
  "custom:organisation_name": "Schuberg Philis",
  "custom:role": "owner"
}
```

### Mock Cognito Compatible Structure
```python
USERS_DB = {
    "admin": {
        "username": "admin",
        "email": "admin@schubergphilis.com",
        "groups": ["core_member"],
        "custom:organisation_id": "identity--schuberg-philis",
        "custom:organisation_name": "Schuberg Philis",
        "custom:role": "owner",
        "enabled": True,
        "user_status": "CONFIRMED"
    }
}
```

## Management API Changes

### Before (WRONG - uses database):
```python
# ❌ Old approach
members = db.get_organisation_members(organisation_id)
db.add_organisation_member(org_id, username, role)
```

### After (CORRECT - uses Cognito):
```python
# ✅ New approach
members = await cognito.list_users_in_organisation(organisation_id)
await cognito.update_user_organisation(username, organisation_id, role)
```

## AWS Cognito API Compatibility

### Required AWS Cognito APIs
Mock Cognito must implement these AWS APIs:

1. **AdminGetUser** - Get user with custom attributes
2. **AdminUpdateUserAttributes** - Update custom:organisation_id, custom:role
3. **ListUsers** - With filter by custom attribute
4. **AdminAddUserToGroup** - Add to access tier group
5. **AdminRemoveUserFromGroup** - Remove from group

### Example AWS SDK Usage
```python
import boto3

cognito = boto3.client('cognito-idp')

# Get user with custom attributes
response = cognito.admin_get_user(
    UserPoolId='us-east-1_abc123',
    Username='admin'
)

# custom:organisation_id in UserAttributes
for attr in response['UserAttributes']:
    if attr['Name'] == 'custom:organisation_id':
        org_id = attr['Value']

# Update user's organization
cognito.admin_update_user_attributes(
    UserPoolId='us-east-1_abc123',
    Username='admin',
    UserAttributes=[
        {'Name': 'custom:organisation_id', 'Value': 'identity--new-org'},
        {'Name': 'custom:role', 'Value': 'admin'}
    ]
)

# List users in organization
response = cognito.list_users(
    UserPoolId='us-east-1_abc123',
    Filter='custom:organisation_id = "identity--schuberg-philis"'
)
```

## Database Methods to REMOVE

These methods should raise `NotImplementedError` or be removed:

```python
# ❌ Remove from BaseFRANKDatabase
def add_organisation_member(...)
def remove_organisation_member(...)
def get_organisation_members(...)
def get_user_organisations(...)
def get_organisation_member(...)
```

## Migration Path

### Phase 1: Update Mock Cognito ✅
- Use custom attribute format (custom:organisation_id)
- Implement AWS Cognito API endpoints
- AdminGetUser returns UserAttributes array

### Phase 2: Update Management API
- Replace db.get_organisation_members() with cognito.list_users_in_organisation()
- Replace db.add_organisation_member() with cognito.update_user_organisation()
- Remove database dependency for user/org operations

### Phase 3: Update CognitoService
- Add list_users_in_organisation() method
- Add update_user_organisation() method
- Ensure both Mock and AWS implementations

### Phase 4: AWS Cognito Setup
- Create custom attributes in User Pool
- Set custom:organisation_id (mutable, string)
- Set custom:role (mutable, string)
- Set custom:organisation_name (mutable, string)

## Benefits

1. **Single Source of Truth**: Cognito owns all user data
2. **No Synchronization**: No need to sync between Cognito and database
3. **AWS Compatible**: Works with both Mock and AWS Cognito
4. **Simpler Architecture**: Authentication layer handles user organizations
5. **Scalable**: Cognito scales automatically

## Implementation Status

- [ ] Update mock_cognito.py to use custom:attribute format
- [ ] Add AWS Cognito API compatibility methods
- [ ] Update CognitoService with organization queries
- [ ] Update Management API endpoints
- [ ] Remove database membership methods
- [ ] Update fixtures to use Cognito-only
- [ ] Update documentation

## References

- AWS Cognito Custom Attributes: https://docs.aws.amazon.com/cognito/latest/developerguide/user-pool-settings-attributes.html
- AWS SDK AdminGetUser: https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_AdminGetUser.html
- AWS SDK ListUsers: https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_ListUsers.html

---

**Last Updated**: 2026-01-31
**Status**: In Progress
