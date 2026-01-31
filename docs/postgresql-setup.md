# PostgreSQL Setup for FRANK Management API

Complete guide for running the Management API with PostgreSQL database.

## Quick Start

Start everything with one command:

```bash
cd /Users/iheitlager/wc/FRANK-worktree/agent-1
docker compose -f docker-compose.local.yml up --build
```

This starts:
- **PostgreSQL** (port 5432) - Management data storage
- **Mock Cognito** (port 8100) - User authentication
- **Management API** (port 8001) - Organisation & user management
- **Web GUI** (port 3000) - Web interface

## Architecture

```
┌────────────────────────────────────────────────┐
│  Management API (port 8001)                    │
│      ↓                    ↓                    │
│  PostgreSQL          Mock Cognito              │
│  (port 5432)         (port 8100)               │
│                                                │
│  • organisations      • users (humans)         │
│  • org_members        • service accounts       │
│  • refresh_tokens     • groups & MFA           │
│                       • JWT tokens             │
└────────────────────────────────────────────────┘
```

**Key Design**: All authentication via Cognito JWT tokens. Service accounts are Cognito users with `service-*` naming convention.

## Database Seeding

The database **automatically seeds** on first startup with:
- 6 organisations (Schuberg Philis, S-Unit, Rabobank, ING, Amsterdam, KPN)
- 7 user memberships matching Mock Cognito users

### Manual Seeding

Check seed status:
```bash
curl http://localhost:8001/admin/seed/status
```

Force reseed (requires authentication):
```bash
# Login first
TOKEN=$(curl -X POST http://localhost:8001/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  | jq -r '.access_token')

# Reseed database
curl -X POST "http://localhost:8001/admin/seed?force=true" \
  -H "Authorization: Bearer $TOKEN"
```

## Initial Data

### Organisations

| Organisation | Type | Access Level | Sector |
|--------------|------|--------------|--------|
| Schuberg Philis | cyber_partner | core_member | Technology |
| S-Unit | cyber_partner | partner | Security Services |
| Rabobank | customer | contributor | Finance |
| ING | customer | contributor | Finance |
| Gemeente Amsterdam | customer | observer | Government |
| KPN | customer | observer | Telecommunications |

### Users (from Mock Cognito)

| Username | Organisation | Role | Password |
|----------|--------------|------|----------|
| admin | Schuberg Philis | owner | admin123 |
| ijsbrand | Schuberg Philis | admin | TempPass123! |
| s_unit_analyst | S-Unit | member | TempPass123! |
| rabobank_security | Rabobank | member | TempPass123! |
| ing_soc | ING | member | TempPass123! |
| amsterdam_monitor | Gemeente Amsterdam | member | TempPass123! |
| kpn_observer | KPN | member | TempPass123! |

## API Examples

### 1. Login
```bash
curl -X POST http://localhost:8001/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

Response:
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### 2. List Organisations
```bash
curl http://localhost:8001/v1/organisations \
  -H "Authorization: Bearer $TOKEN"
```

### 3. Get Organisation Members
```bash
curl http://localhost:8001/v1/organisations/identity--schuberg-philis/members \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Create User
```bash
curl -X POST http://localhost:8001/v1/organisations/identity--schuberg-philis/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "newuser",
    "email": "newuser@example.com",
    "password": "TempPass123!",
    "groups": ["contributor"]
  }'
```

### 5. Create Service Account
Service accounts are Cognito users with `service-*` naming convention:

```bash
curl -X POST http://localhost:8001/v1/organisations/identity--rabobank/users \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "service-rabobank-ingestion",
    "email": "service-rabobank@example.com",
    "groups": ["contributor"]
  }'
```

**Note**: Password is auto-generated for service accounts. They authenticate with Cognito JWT tokens, not passwords.

## Database Access

### Connect to PostgreSQL

```bash
# Using psql
docker exec -it frank-postgres psql -U frank -d frank_management

# Using pgAdmin or other GUI tools
Host: localhost
Port: 5432
Database: frank_management
Username: frank
Password: frank_dev
```

### Useful SQL Queries

```sql
-- List all organisations
SELECT organisation_id, organisation_type, access_level, sector
FROM organisations
ORDER BY contribution_score DESC;

-- List all members with their organisations
SELECT o.organisation_id, o.organisation_type,
       m.username, m.role, m.joined_at
FROM organisation_members m
JOIN organisations o ON m.organisation_id = o.organisation_id
ORDER BY o.organisation_id, m.role DESC;

-- Count users per organisation
SELECT o.organisation_id,
       COUNT(m.username) as member_count
FROM organisations o
LEFT JOIN organisation_members m ON o.organisation_id = m.organisation_id
GROUP BY o.organisation_id
ORDER BY member_count DESC;

-- Find service accounts
SELECT m.organisation_id, m.username, m.role, m.joined_at
FROM organisation_members m
WHERE m.username LIKE 'service-%'
ORDER BY m.organisation_id, m.joined_at DESC;
```

## BDD Testing

The integration tests automatically reset the database before each scenario:

```bash
cd /Users/iheitlager/wc/FRANK-worktree/agent-1/tests/integration

# Run all Management API tests
behave features/management_api_users.feature \
  -D management_port=8001 \
  -D cognito_port=8100

# Run specific tag
behave features/management_api_users.feature \
  --tags=@users \
  -D management_port=8001 \
  -D cognito_port=8100
```

## Configuration

### Environment Variables

```bash
# PostgreSQL Connection (takes precedence)
DATABASE_URL=postgresql://frank:frank_dev@postgres:5432/frank_management

# SQLite Fallback (if DATABASE_URL not set)
FRANK_DB_PATH=/tmp/frank_management.db

# Cognito Configuration
COGNITO_URL=http://mock-cognito:8100
FRANK_AUTH_MODE=mock

# JWT Configuration
JWT_ALGORITHM=RS256
USER_POOL_ID=eu-west-1_MOCKPOOL
REGION=eu-west-1
```

### Custom Database Credentials

Create `.env` file:
```bash
POSTGRES_DB=my_database
POSTGRES_USER=my_user
POSTGRES_PASSWORD=my_secure_password
```

Then start with:
```bash
docker compose -f docker-compose.local.yml --env-file .env up
```

## Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker compose -f docker-compose.local.yml ps postgres

# View PostgreSQL logs
docker compose -f docker-compose.local.yml logs postgres

# Check if tables exist
docker exec frank-postgres psql -U frank -d frank_management -c "\dt"
```

### Seed Data Missing

```bash
# Check seed status
curl http://localhost:8001/admin/seed/status

# Force reseed
curl -X POST "http://localhost:8001/admin/seed?force=true" \
  -H "Authorization: Bearer $TOKEN"
```

### Port Conflicts

If ports are already in use:
```bash
# Use custom ports
POSTGRES_PORT=5433 \
MANAGEMENT_API_PORT=8002 \
MOCK_COGNITO_PORT=8101 \
WEB_GUI_PORT=3001 \
docker compose -f docker-compose.local.yml up
```

## Production Deployment (AWS RDS)

See [ADR-0015](adr/0015-postgresql-management-api.md) for complete AWS deployment guide including:
- RDS PostgreSQL configuration
- Multi-AZ setup
- Security groups
- Backup strategy
- CloudFormation templates
- RDS Proxy configuration

Quick summary:
```yaml
Engine: PostgreSQL 16.x
Instance: db.t4g.micro (dev) → db.r6g.large (prod)
Storage: 20GB gp3 with auto-scaling
Multi-AZ: Yes
Backups: 7 days retention
Encryption: KMS at rest
```

## Files Changed

```
src/frank/storage/postgresql.py          # PostgreSQL backend
src/frank/management/server.py           # Auto-detect PostgreSQL
src/frank/management/seed.py             # Database seeding
src/frank/management/api.py              # Admin seed endpoints
docker-compose.local.yml                 # PostgreSQL service
docker/Dockerfile.management             # PostgreSQL libraries
pyproject.toml                           # psycopg dependency
tests/integration/environment.py         # BDD test reset
docs/adr/0015-postgresql-management-api.md  # Architecture decision
```

## Next Steps

1. **Start the stack**: `docker compose -f docker-compose.local.yml up --build`
2. **Verify health**: `curl http://localhost:8001/health`
3. **Check seed status**: `curl http://localhost:8001/admin/seed/status`
4. **Login**: Use admin/admin123 credentials
5. **Explore API**: Visit http://localhost:8001/docs (Swagger UI)
6. **Run tests**: `behave tests/integration/features/management_api_users.feature`

---

**Last Updated**: 2026-01-31
