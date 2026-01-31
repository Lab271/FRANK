# Loading Fixtures in Docker Containers

This guide explains how to load comprehensive fixture data (organizations and users) into Docker containers.

## Overview

The fixture system provides:
- **Mock Cognito**: User data is built into the container (no additional loading needed)
- **Database**: Organizations and memberships need to be initialized on container startup

## What's Already Working

### Mock Cognito (No Action Needed)

The `mock_cognito` container already includes all fixture users. When it starts, you'll see:

```
=== Organisations ===

CORE MEMBER:
  Schuberg Philis (identity--schuberg-philis)
    Users: admin, ijsbrand

PARTNER:
  S Unit (identity--s-unit)
    Users: s_unit_analyst

[... all organizations and users ...]
```

This happens automatically because `USERS_DB` in `mock_cognito.py` contains the fixture data.

## Loading Database Fixtures

The database needs organizations and user-to-organization memberships. There are three approaches:

### Approach 1: Entrypoint Script (Implemented)

The `simple-api` container now includes an entrypoint script that automatically loads fixtures on startup.

**How it works:**
1. Container starts
2. `docker-entrypoint.sh` runs `init_fixtures.py` if `LOAD_FIXTURES=true`
3. Database is initialized with organizations and memberships
4. Application starts

**Usage:**

```bash
# Default: Fixtures are loaded automatically
docker compose up

# Disable fixture loading
LOAD_FIXTURES=false docker compose up

# Check if fixtures loaded
docker logs simple-api | grep "Fixtures loaded"
```

**Files involved:**
- `docker-entrypoint.sh`: Startup script
- `init_fixtures.py`: Fixture initialization
- `Dockerfile.api`: Updated to include entrypoint
- `docker-compose.yml`: Added volumes and environment variables

### Approach 2: Init Container Pattern

For production setups, use a separate init container:

```yaml
services:
  # Database initialization container
  db-init:
    build:
      context: ../../..
      dockerfile: tests/spikes/014_cognito/Dockerfile.api
    container_name: db-init
    environment:
      - DB_PATH=/data/frank.db
    volumes:
      - frank-data:/data
    command: ["python", "/app/init_fixtures.py"]
    networks:
      - cognito-net

  # Main API service
  simple-api:
    depends_on:
      - db-init
      - mock-cognito
    # ... rest of config ...
```

**Pros:**
- Clean separation of initialization and runtime
- Init container exits after seeding
- Main service only starts after init completes

**Cons:**
- Slightly more complex setup
- Requires dependency ordering

### Approach 3: Pre-seeded Volume

For development, create a pre-seeded database volume:

```bash
# 1. Create and seed database locally
uv run python tests/spikes/014_cognito/init_fixtures.py

# 2. Copy to Docker volume
docker volume create frank-data
docker run --rm -v frank-data:/data -v /tmp/frank_stage1.db:/source/frank.db \
  alpine cp /source/frank.db /data/frank.db

# 3. Use the volume
docker compose up
```

**Pros:**
- Fast startup (no seeding delay)
- Database persists between container restarts
- Good for iterative development

**Cons:**
- Manual process
- Need to recreate if fixtures change

## Environment Variables

Control fixture loading behavior:

| Variable | Default | Description |
|----------|---------|-------------|
| `LOAD_FIXTURES` | `true` | Load fixtures on container startup |
| `DB_PATH` | `/data/frank.db` | Database file path |
| `LOG_LEVEL` | `debug` | Logging verbosity |

## Verification

### Check if fixtures loaded successfully:

```bash
# Check container logs
docker logs simple-api | grep -A 20 "Fixture Initialization"

# You should see:
# ✅ Database seeded successfully!
# === Organizations Created ===
#   Schuberg Philis           | Core Member     | Users: admin, ijsbrand
#   [...]
```

### Verify organizations in database:

```bash
# Access container
docker exec -it simple-api bash

# Check database
sqlite3 /data/frank.db "SELECT organisation_id, name, access_level FROM organisations;"

# Expected output:
# identity--schuberg-philis|Schuberg Philis|core_member
# identity--s-unit|S-Unit|partner
# [...]
```

### Verify memberships:

```bash
sqlite3 /data/frank.db "SELECT organisation_id, username, role FROM organisation_members;"

# Expected output:
# identity--schuberg-philis|admin|owner
# identity--schuberg-philis|ijsbrand|admin
# identity--s-unit|s_unit_analyst|member
# [...]
```

## Testing the Complete System

### 1. Start all services:

```bash
cd tests/spikes/014_cognito
docker compose up -d
```

### 2. Check startup logs:

```bash
# Mock Cognito should show organizations
docker logs mock-cognito | grep -A 30 "Organisations"

# Simple API should show fixtures loaded
docker logs simple-api | grep "Fixtures loaded"
```

### 3. Test authentication:

```bash
# Core Member (Schuberg Philis - sees everything)
curl -X POST https://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | jq

# Partner (S-Unit - sees partner data)
curl -X POST https://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "s_unit_analyst", "password": "TempPass123!"}' | jq

# Observer (KPN - sees only own org)
curl -X POST https://localhost/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "kpn_observer", "password": "TempPass123!"}' | jq
```

Each should return:
```json
{
  "access_token": "eyJ...",
  "id_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

## Troubleshooting

### Fixtures not loading

**Problem:** Container starts but no fixtures in database

**Solutions:**
```bash
# Check if entrypoint script ran
docker logs simple-api | head -50

# Check if LOAD_FIXTURES is enabled
docker inspect simple-api | grep LOAD_FIXTURES

# Manually run fixture initialization
docker exec -it simple-api python /app/init_fixtures.py
```

### Database permission errors

**Problem:** `Permission denied: /data/frank.db`

**Solutions:**
```bash
# Check volume permissions
docker exec -it simple-api ls -la /data

# Recreate volume with correct permissions
docker compose down -v
docker compose up
```

### Organizations not visible in Mock Cognito

**Problem:** Mock Cognito doesn't show organizations on startup

**Solutions:**
```bash
# This is normal - Mock Cognito has user data, not org data
# Organizations are in the database, accessed via API
# Mock Cognito display shows user-to-org mapping for reference

# Verify users are correctly defined
docker exec -it mock-cognito python -c "from mock_cognito import USERS_DB; print(list(USERS_DB.keys()))"
```

## Production Considerations

For production deployments:

1. **Don't load fixtures in production**
   ```yaml
   environment:
     - LOAD_FIXTURES=false
   ```

2. **Use proper database initialization**
   - Run migration scripts separately
   - Use database snapshots or backups
   - Initialize via CI/CD pipeline

3. **Secure database volumes**
   - Use encrypted volumes
   - Regular backups
   - Access control

4. **Health checks**
   - Verify database connectivity
   - Check organization count
   - Validate memberships exist

## Summary

| Component | Fixture Data | Loading Method |
|-----------|--------------|----------------|
| Mock Cognito | Users (7) | Built into `USERS_DB` (automatic) |
| Database | Organizations (6) | Entrypoint script or init container |
| Database | Memberships (7) | Entrypoint script or init container |

The implemented solution (Approach 1) automatically loads fixtures on container startup with `LOAD_FIXTURES=true` (default).
