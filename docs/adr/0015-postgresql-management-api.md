# ADR-0015: PostgreSQL for Management API Data Storage

**Status:** Accepted
**Date:** 2026-01-31
**Deciders:** Development Team
**Tags:** infrastructure, database, management-api, postgresql, aws-rds

## Context

The FRANK Management API requires persistent storage for:
- **Organisations**: Threat intelligence entities (partners and customers)
- **Organisation Members**: User-to-organisation relationships with roles (includes service accounts)
- **Refresh Tokens**: JWT token revocation lists for logout functionality

**Note**: As of Migration 001 (2026-01-31), all authentication is via AWS Cognito JWT tokens. Service accounts are Cognito users with `service-*` naming convention, stored as regular members.

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
│  Data API (FastAPI)                             │
│         │                                       │
│         └─► DynamoDB                            │
│             • submissions                       │
│             • observables                       │
│             • sightings                         │
│             • statistics                        │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Implementation

1. **Storage Backend**: `src/frank/storage/postgresql.py`
   - Implements `BaseFRANKDatabase` interface
   - Uses psycopg 3.x (modern async-capable driver)
   - Connection pooling via psycopg connection pool
   - Parameterized queries for security

2. **Database Schema** (as of Migration 001):
   ```sql
   organisations (
       organisation_id TEXT PRIMARY KEY,
       organisation_type TEXT CHECK (cyber_partner|customer),
       access_level TEXT,
       sector TEXT,
       region TEXT,
       contribution_score INTEGER,
       client_count INTEGER,
       metadata_json TEXT
   )

   organisation_members (
       id SERIAL PRIMARY KEY,
       organisation_id TEXT REFERENCES organisations,
       username TEXT,  -- Includes service accounts (service-*)
       role TEXT CHECK (member|admin|owner),
       UNIQUE(organisation_id, username)
   )

   refresh_tokens (
       token_id TEXT PRIMARY KEY,
       user_id TEXT,
       token_hash TEXT UNIQUE,
       expires_at TIMESTAMP,
       is_revoked BOOLEAN
   )
   ```

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

- ADR-0005: Cognito Integration for User Management (orthogonal - handles authentication)
- [PostgreSQL 16 Documentation](https://www.postgresql.org/docs/16/)
- [Amazon RDS PostgreSQL](https://aws.amazon.com/rds/postgresql/)
- [psycopg 3 Documentation](https://www.psycopg.org/psycopg3/docs/)
- AWS Well-Architected Framework: Reliability Pillar

## Revision History

- 2026-01-31: Initial version - PostgreSQL adoption for Management API
