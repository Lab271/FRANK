# Migration 001: Drop api_keys Table

**Date**: 2026-01-31
**Type**: Schema Change
**Reason**: Unified Cognito Authentication Architecture

## Context

The FRANK platform has transitioned to unified AWS Cognito authentication for all access (both humans and services). Custom API tokens are no longer needed as all services authenticate using Cognito JWT tokens.

See:
- `docs/highlevel_design.md` - Architecture overview
- `.openspec/architecture/decisions/0015-postgresql-management-api.md` - PostgreSQL decision

## Schema Change

### Tables to Drop

```sql
-- Drop api_keys table (no longer needed)
DROP TABLE IF EXISTS api_keys CASCADE;

-- Drop related indexes (if they exist)
DROP INDEX IF EXISTS idx_api_keys_user_id;
DROP INDEX IF EXISTS idx_api_keys_hash;
```

### Service Account Pattern

Service accounts are now regular Cognito users with naming convention: `service-{org}-{purpose}`

Examples:
- `service-rabobank-ingestion`
- `service-ing-threat-feed`
- `service-sunit-automated-scanner`

Service accounts:
- Authenticate via Cognito JWT tokens
- Are stored as regular members in `organisation_members` table
- Use auto-generated secure passwords (not used directly, only for Cognito)
- Have same access control as regular users (via Cognito groups)

## Migration Steps

### For Local Development

```bash
# Connect to local PostgreSQL
psql postgresql://frank:frank_dev@localhost:5432/frank_management

# Drop api_keys table
DROP TABLE IF EXISTS api_keys CASCADE;
DROP INDEX IF EXISTS idx_api_keys_user_id;
DROP INDEX IF EXISTS idx_api_keys_hash;

# Verify table is gone
\dt
```

### For Docker Compose Environments

```bash
# Connect via docker-compose
docker-compose -f docker-compose.local.yml exec postgres psql -U frank -d frank_management

# Run the same SQL commands as above
```

### For AWS RDS (Production)

```bash
# Connect to RDS instance (requires proper IAM/security group access)
psql postgresql://frank_admin:${PASSWORD}@${RDS_ENDPOINT}:5432/frank_management

# Run migration in transaction
BEGIN;

-- Drop api_keys table
DROP TABLE IF EXISTS api_keys CASCADE;
DROP INDEX IF EXISTS idx_api_keys_user_id;
DROP INDEX IF EXISTS idx_api_keys_hash;

-- Verify
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

COMMIT;
```

## Verification

After running migration, verify:

1. **Table removed**:
   ```sql
   SELECT tablename FROM pg_tables WHERE tablename = 'api_keys';
   -- Should return 0 rows
   ```

2. **Remaining tables**:
   ```sql
   \dt
   -- Should show only:
   --   organisations
   --   organisation_members
   --   refresh_tokens
   ```

3. **Application health**:
   ```bash
   curl http://localhost:8001/health
   # Should return healthy status
   ```

4. **Service accounts work**:
   ```bash
   # Create a service account
   curl -X POST http://localhost:8001/v1/organisations/identity--rabobank/users \
     -H "Authorization: Bearer ${ADMIN_TOKEN}" \
     -H "Content-Type: application/json" \
     -d '{
       "username": "service-rabobank-test",
       "email": "service-rabobank@example.com",
       "groups": ["contributor"]
     }'

   # Service account should be created successfully
   ```

## Rollback

**WARNING**: This migration is generally not reversible without data loss.

If rollback is absolutely necessary:

```sql
-- Recreate api_keys table (empty)
CREATE TABLE api_keys (
    key_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    key_prefix TEXT NOT NULL,
    name TEXT NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
```

However, note that:
1. All previous API keys are lost
2. Code changes must also be rolled back
3. Service accounts must be recreated as API keys

## Impact Assessment

- **Breaking Change**: Yes - existing API keys will stop working
- **Service Interruption**: Minimal - services must switch to Cognito JWT authentication
- **Data Loss**: Yes - all API key records are permanently deleted
- **Migration Duration**: < 1 second
- **Rollback Available**: Table can be recreated but data cannot be recovered

## Communication Plan

1. **Before Migration**:
   - Notify all service account owners to switch to Cognito authentication
   - Provide migration guide for services (JWT-based authentication)
   - Schedule maintenance window if needed

2. **During Migration**:
   - Run migration during low-traffic period
   - Monitor logs for authentication errors
   - Have rollback plan ready (though not recommended)

3. **After Migration**:
   - Verify all services authenticate successfully
   - Monitor for any authentication failures
   - Update documentation to remove API key references

## References

- ADR-0009: PostgreSQL for Management API
- `docs/highlevel_design.md`: Unified Cognito Architecture
- `src/frank/storage/postgresql.py`: Updated schema (no api_keys)
- `src/frank/management/api.py`: API key endpoints removed

## Status

- [ ] Migration script reviewed
- [ ] Tested on local development environment
- [ ] Tested on staging environment
- [ ] Executed on production
- [ ] Verified all services working
- [ ] Documentation updated
