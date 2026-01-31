# ADR-0015: PostgreSQL for Management API Data Storage

**Status:** Accepted
**Date:** 2026-01-31
**Deciders:** Development Team
**Tags:** infrastructure, database, management-api, postgresql, aws-rds

## Context

The FRANK Management API requires persistent storage for:
- **Organisations** (Member organisations): Authenticated entities that participate in the platform (partners and customers)
- **Organisation Members**: User-to-organisation relationships with roles (includes human users and service accounts)
- **Refresh Tokens** (Optional): JWT token revocation tracking for logout functionality

**Important Distinctions:**
- **Member Organisations**: Stored in PostgreSQL (identity--{uuid4}, authenticated parties)
- **Target Organisations**: Stored in DynamoDB with sightings (identity--{uuid4}, victim parties)
- See `docs/glossary.md` for detailed definitions

**Authentication Strategy:**
All authentication via AWS Cognito JWT tokens (ADR-0005):
- Human users: Authenticate via Web GUI/TUI → Cognito → JWT
- Service accounts: Cognito users with `service-*` naming → JWT
- No custom API keys (never intended per ADR-0005)
- Refresh tokens optional (Cognito can handle logout tracking)

Previously, the Management API used SQLite for local development, with plans to use DynamoDB. However, investigation revealed that:

1. **DynamoDB** is optimized for threat intelligence data (submissions, observables, sightings)
2. **Management data** has different access patterns:
   - Relational queries (joins between organisations and members)
   - Transactional integrity (atomic user-org membership changes)
   - Structured schema with foreign keys
   - Lower volume, higher consistency requirements

3. **SQLite limitations**:
   - File-based storage problematic in containerized environments
   - Not suitable for production multi-instance deployments
   - Limited concurrent write access

## Decision

We will use **PostgreSQL** as the dedicated database for the Management API, separate from DynamoDB threat intelligence storage.

### Database Scope and Responsibilities

PostgreSQL stores **ONLY member organisation business data**:

**IN SCOPE (PostgreSQL):**
- ✅ **Member organisations**: Authenticated parties (identity--{uuid4})
  - Organisation type (cyber_partner, customer)
  - Access tier (observer, contributor, partner, core_member)
  - Sector, region, contribution score
  - Metadata (flexible JSON)

- ✅ **Organisation members**: User-to-organisation relationships
  - Username from Cognito (both humans and service-* accounts)
  - Role within organisation (member, admin, owner)
  - Membership timestamp

- ✅ **Refresh tokens** (optional): For logout revocation tracking
  - Can be omitted if using Cognito-only logout
  - Provides faster local revocation checking

**OUT OF SCOPE (PostgreSQL):**
- ❌ **Users**: Stored in Cognito only (ADR-0005)
- ❌ **Passwords**: Never stored in FRANK
- ❌ **Authentication tokens**: Validated via Cognito JWKS (stateless)
- ❌ **API keys**: Never intended per ADR-0005
- ❌ **Target organisations**: Victim orgs stored in DynamoDB with sightings
- ❌ **Threat intelligence**: Submissions, observables, sightings in DynamoDB

**Rationale:**
- PostgreSQL for relational data (orgs ↔ members)
- Cognito for authentication data (users, passwords, MFA)
- DynamoDB for threat intelligence data (submissions, sightings, targets)
- Clean separation of concerns

### Architecture

```
┌─────────────────────────────────────────────────┐
│          FRANK Platform Architecture            │
├─────────────────────────────────────────────────┤
│                                                 │
│  Management API (FastAPI)                       │
│         │                                       │
│         ├─► PostgreSQL                          │
│         │   • organisations                     │
│         │   • organisation_members (includes    │
│         │     service accounts)                 │
│         │   • refresh_tokens                    │
│         │                                       │
│         └─► Cognito (via Mock/AWS)              │
│             • users (humans + service accounts) │
│             • groups & MFA                      │
│             • JWT authentication                │
│                                                 │
│  Main FRANK API - Sightings (FastAPI)           │
│         │                                       │
│         └─► DynamoDB                            │
│             • submissions                       │
│             • observables                       │
│             • sightings                         │
│             • statistics                        │
│             • target organisations (victims)    │
│                                                 │
└─────────────────────────────────────────────────┘
```

**Key Distinction:**
- **Management API → PostgreSQL**: Member organisations (authenticated parties who use the platform)
- **Sightings API → DynamoDB**: Target organisations (victims in threat intelligence data)

### Implementation

1. **Storage Backend**: `src/frank/storage/postgresql.py`
   - Implements `BaseFRANKDatabase` interface
   - Uses psycopg 3.x (modern async-capable driver)
   - Connection pooling via psycopg connection pool
   - Parameterized queries for security

2. **Database Schema** (as of Migration 001):
   ```sql
   organisations (
       organisation_id TEXT PRIMARY KEY,  -- STIX format: identity--{uuid4}
       organisation_type TEXT CHECK (cyber_partner|customer),
       access_level TEXT,  -- observer|contributor|partner|core_member
       sector TEXT,
       region TEXT,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       last_active TIMESTAMP,
       contribution_score INTEGER DEFAULT 0,
       client_count INTEGER DEFAULT 0,
       metadata_json TEXT  -- JSON for flexible metadata
   )

   organisation_members (
       id SERIAL PRIMARY KEY,
       organisation_id TEXT REFERENCES organisations,
       username TEXT,  -- From Cognito (humans + service-* accounts)
       role TEXT CHECK (member|admin|owner),  -- Org-specific role
       joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       UNIQUE(organisation_id, username)
   )

   refresh_tokens (
       token_id TEXT PRIMARY KEY,  -- JWT jti claim
       user_id TEXT,  -- Username from Cognito
       token_hash TEXT UNIQUE,  -- SHA-256 hash of refresh token
       expires_at TIMESTAMP,
       created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
       is_revoked BOOLEAN DEFAULT FALSE
   )
   ```

   **Scope of PostgreSQL Storage:**
   - ✅ **Member organisations** (authenticated parties): identity--{uuid4}
   - ✅ **Organisation members** (Cognito usernames): humans + service accounts
   - ✅ **Refresh tokens** (optional): For logout tracking
   - ❌ **NOT users**: Users stored in Cognito only (ADR-0005)
   - ❌ **NOT api_keys**: Removed in Migration 001, never intended (ADR-0005)
   - ❌ **NOT target organisations**: Victim orgs stored in DynamoDB with sightings

   **Removed in Migration 001**: `api_keys` table (replaced by unified Cognito authentication)

3. **Configuration**:
   - Environment variable: `DATABASE_URL`
   - Format: `postgresql://user:password@host:port/database`
   - Fallback to SQLite if `DATABASE_URL` not set (local dev)

4. **Automatic Seeding**:
   - `src/frank/management/seed.py` provides initial data
   - Auto-seeds on startup if database is empty
   - Syncs with Mock Cognito fixture users
   - Manual seed endpoint: `POST /admin/seed?force=true`

## Deployment Strategy

### Local Development

```yaml
# docker-compose.local.yml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: frank_management
      POSTGRES_USER: frank
      POSTGRES_PASSWORD: frank_dev
    volumes:
      - postgres-data:/var/lib/postgresql/data

  management-api:
    environment:
      DATABASE_URL: postgresql://frank:frank_dev@postgres:5432/frank_management
```

**Start Command**: `docker compose -f docker-compose.local.yml up`

### AWS Production Deployment

Use **Amazon RDS PostgreSQL** with the following configuration:

#### RDS Configuration

```yaml
Engine: PostgreSQL 16.x
Instance Class: db.t4g.micro (burst) → db.r6g.large (production)
Storage: 20GB SSD (gp3) with auto-scaling to 100GB
Multi-AZ: Yes (high availability)
Backup Retention: 7 days (automated daily backups)
Encryption: AWS KMS encryption at rest
```

#### Network & Security

- **VPC**: Same VPC as Management API ECS tasks
- **Security Group**:
  - Ingress: Port 5432 from Management API security group only
  - Egress: None required
- **Subnet Group**: Private subnets across multiple AZs
- **Publicly Accessible**: No

#### Connection Management

**Option 1: Direct Connection** (Simple, suitable for low-medium traffic)
```python
DATABASE_URL=postgresql://frank_mgmt:${DB_PASSWORD}@frank-mgmt-db.xxxxx.eu-west-1.rds.amazonaws.com:5432/frank_management
```

**Option 2: RDS Proxy** (Recommended for production)
- Connection pooling at database layer
- Automatic failover handling
- IAM authentication support
- Reduced database connection overhead

```python
DATABASE_URL=postgresql://frank_mgmt:${DB_PASSWORD}@frank-mgmt-proxy.proxy-xxxxx.eu-west-1.rds.amazonaws.com:5432/frank_management
```

#### CloudFormation/Ansible Provisioning

```yaml
Resources:
  FrankManagementDBSubnetGroup:
    Type: AWS::RDS::DBSubnetGroup
    Properties:
      DBSubnetGroupName: frank-management-db-subnet-group
      SubnetIds: !Ref PrivateSubnets

  FrankManagementDBSecurityGroup:
    Type: AWS::EC2::SecurityGroup
    Properties:
      SecurityGroupIngress:
        - IpProtocol: tcp
          FromPort: 5432
          ToPort: 5432
          SourceSecurityGroupId: !Ref ManagementAPISecurityGroup

  FrankManagementDB:
    Type: AWS::RDS::DBInstance
    Properties:
      DBInstanceIdentifier: frank-management-db
      Engine: postgres
      EngineVersion: "16.1"
      DBInstanceClass: db.t4g.micro
      AllocatedStorage: 20
      StorageType: gp3
      StorageEncrypted: true
      MultiAZ: true
      MasterUsername: frank_mgmt
      MasterUserPassword: !Ref DBMasterPassword
      DBSubnetGroupName: !Ref FrankManagementDBSubnetGroup
      VPCSecurityGroups:
        - !Ref FrankManagementDBSecurityGroup
      BackupRetentionPeriod: 7
      PreferredBackupWindow: "03:00-04:00"
      PreferredMaintenanceWindow: "sun:04:00-sun:05:00"
      EnableCloudwatchLogsExports:
        - postgresql
```

#### Environment Variables (ECS Task Definition)

```json
{
  "environment": [
    {
      "name": "DATABASE_URL",
      "value": "postgresql://frank_mgmt:${DB_PASSWORD}@frank-mgmt-db.xxxxx.eu-west-1.rds.amazonaws.com:5432/frank_management"
    }
  ],
  "secrets": [
    {
      "name": "DB_PASSWORD",
      "valueFrom": "arn:aws:secretsmanager:eu-west-1:xxxx:secret:frank-db-password"
    }
  ]
}
```

### Migration from SQLite to PostgreSQL

For existing SQLite databases, use this migration script:

```python
#!/usr/bin/env python3
"""Migrate SQLite to PostgreSQL"""

from frank.storage.sqlite import create_sqlite_database
from frank.storage.postgresql import create_postgresql_database

# Connect to both databases
sqlite_db = create_sqlite_database("/tmp/frank_management.db")
pg_db = create_postgresql_database("postgresql://frank:password@localhost:5432/frank_management")

# Migrate organisations
orgs = sqlite_db.list_organisations()
for org in orgs:
    pg_db.upsert_organisation(org)

# Migrate organisation members
for org in orgs:
    members = sqlite_db.get_organisation_members(org['organisation_id'])
    for member in members:
        pg_db.add_organisation_member(
            organisation_id=org['organisation_id'],
            username=member['username'],
            role=member['role']
        )

# Note: As of Migration 001, api_keys table no longer exists
# Refresh tokens are short-lived, no migration needed
print("Migration complete!")
```

See `docs/migrations/001_drop_api_keys_table.md` for details on unified Cognito authentication migration.

## Consequences

### Positive

1. **Separation of Concerns**: Management data cleanly separated from threat intelligence data
2. **Relational Integrity**: Foreign keys and transactions ensure data consistency
3. **Production Ready**: RDS provides enterprise-grade reliability, backups, and monitoring
4. **Scalability**: Read replicas and connection pooling support growth
5. **Development Experience**: PostgreSQL excellent for local development with Docker
6. **Query Performance**: Optimized for relational queries (JOINs, aggregations)
7. **AWS Integration**: Native integration with CloudWatch, Secrets Manager, IAM

### Negative

1. **Additional Infrastructure**: Another database service to manage and monitor
2. **Cost**: RDS instances add ~$15-50/month (t4g.micro) to ~$300+/month (r6g.large)
3. **Complexity**: Two database technologies (PostgreSQL + DynamoDB) vs. one
4. **Migration Path**: Requires data migration from SQLite for existing deployments

### Neutral

1. **Backup Strategy**: RDS automated backups handle Management API data separately from DynamoDB
2. **Monitoring**: CloudWatch metrics for RDS separate from DynamoDB metrics
3. **Disaster Recovery**: RDS snapshots and point-in-time recovery independent of DynamoDB

## Alternatives Considered

### 1. DynamoDB for All Data

**Pros**: Single database technology, fully managed, auto-scaling
**Cons**:
- Relational queries expensive (multiple queries + client-side joins)
- No foreign key constraints (application-level enforcement)
- Higher complexity for transactional updates
- Not implemented for organisations yet (would require significant work)

**Decision**: Rejected - DynamoDB optimized for different access patterns

### 2. SQLite in Persistent Volume

**Pros**: Simple, no additional infrastructure
**Cons**:
- File locking issues with multiple ECS tasks
- Not suitable for high availability
- No read replicas
- Backup/restore requires volume snapshots
- Doesn't scale beyond single instance

**Decision**: Rejected - Not production-ready

### 3. MySQL/MariaDB on RDS

**Pros**: Similar relational capabilities, widely known
**Cons**:
- PostgreSQL superior JSON support (for metadata_json fields)
- PostgreSQL better indexing and query optimizer
- Team preference for PostgreSQL

**Decision**: Rejected - PostgreSQL preferred

## References

### Related ADRs
- **ADR-0005**: Cognito Authentication Strategy (defines authentication approach)
- **ADR-0003**: Tiered Access Control Model (access levels stored in organisations table)

### Documentation
- `docs/glossary.md`: Member vs target organisations, service accounts
- `docs/highlevel_design.md`: Complete platform architecture
- `docs/migrations/001_drop_api_keys_table.md`: API keys removal migration

### External References
- [PostgreSQL 16 Documentation](https://www.postgresql.org/docs/16/)
- [Amazon RDS PostgreSQL](https://aws.amazon.com/rds/postgresql/)
- [psycopg 3 Documentation](https://www.psycopg.org/psycopg3/docs/)
- AWS Well-Architected Framework: Reliability Pillar

## Validation

### Consistency Check ✅

**ADR-0005 Compliance:**
- ✅ Users stored only in Cognito (no users table)
- ✅ Service accounts as Cognito users (service-* naming)
- ✅ No custom API keys (removed in Migration 001)
- ✅ Stateless JWT validation

**ADR-0003 Compliance:**
- ✅ Access tiers stored in organisations.access_level
- ✅ 5-tier model: public → observer → contributor → partner → core_member

**Glossary Compliance:**
- ✅ Member organisations: PostgreSQL (identity--{uuid4})
- ✅ Target organisations: DynamoDB (identity--{uuid4}, different UUIDs)
- ✅ Service accounts: Cognito users, stored as members
- ✅ Clear separation of authenticated vs victim organisations

### Implementation Evidence

**Files:**
- `src/frank/storage/postgresql.py`: Schema implementation (654 lines)
- `src/frank/management/seed.py`: Database seeding with 6 orgs, 7 members
- `src/frank/management/api.py`: Service account creation with auto-password
- `docs/migrations/001_drop_api_keys_table.md`: Migration guide

**Tests:**
- `tests/unit/storage/test_postgresql.py`: Unit tests for PostgreSQL backend
- `tests/integration/features/management_api_users.feature`: BDD tests
- `tests/unit/management/test_api.py`: Service account creation tests

**Deployment:**
- `docker-compose.local.yml`: PostgreSQL service configuration
- `docker/Dockerfile.management`: psycopg dependencies
- Ansible playbooks ready for AWS RDS deployment

## Revision History

- 2026-01-31: Initial version - PostgreSQL adoption for Management API
- 2026-01-31: Updated to clarify database scope, remove API keys, validate compliance
