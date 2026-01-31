# FRANK Comprehensive Fixture Data

This directory contains comprehensive fixture data for local development with realistic organizations and users.

## Overview

The fixture system provides:
- **6 Organizations** across all access tiers (Core Member, Partner, Contributor, Observer)
- **7 Users** linked to organizations via Cognito groups
- **Organization memberships** linking users to their organizations

## Organizations

| Organization | Access Tier | Type | Sector | Users |
|--------------|-------------|------|--------|-------|
| Schuberg Philis | Core Member | Cyber Partner | Cybersecurity Services | admin, ijsbrand |
| S-Unit | Partner | Cyber Partner | Law Enforcement | s_unit_analyst |
| Rabobank | Contributor | Customer | Financial | rabobank_security |
| ING Bank | Contributor | Customer | Financial | ing_soc |
| Gemeente Amsterdam | Observer | Customer | Government | amsterdam_monitor |
| KPN | Observer | Customer | Telecommunications | kpn_observer |

## Users

| Username | Email | Password | Groups | Organization |
|----------|-------|----------|--------|--------------|
| admin | admin@schubergphilis.com | admin123 | core_member | Schuberg Philis |
| ijsbrand | ijsbrand.heitlager@schubergphilis.com | TempPass123! | core_member | Schuberg Philis |
| s_unit_analyst | analyst@s-unit.nl | TempPass123! | partner | S-Unit |
| rabobank_security | security@rabobank.nl | TempPass123! | contributor | Rabobank |
| ing_soc | soc@ing.nl | TempPass123! | contributor | ING Bank |
| amsterdam_monitor | monitor@amsterdam.nl | TempPass123! | observer | Gemeente Amsterdam |
| kpn_observer | security@kpn.com | TempPass123! | observer | KPN |

## Access Control

The fixture data demonstrates FRANK's tier-based access control:

- **Core Members** (admin, ijsbrand): See all data from all organizations
- **Partners** (s_unit_analyst): See partner-level data and below
- **Contributors** (rabobank_security, ing_soc): See contributor-level data and below
- **Observers** (amsterdam_monitor, kpn_observer): See only their own organization's data

## Usage

### 1. Start Mock Cognito

```bash
cd tests/spikes/014_cognito
python mock_cognito.py --reload
```

You should see organizations and users listed on startup:

```
=== Organisations ===

CORE MEMBER:
  Schuberg Philis (identity--schuberg-philis)
    Users: admin, ijsbrand

PARTNER:
  S Unit (identity--s-unit)
    Users: s_unit_analyst

...
```

### 2. Initialize Database Fixtures

```bash
cd tests/spikes/014_cognito
python init_fixtures.py
```

This will:
- Create all organizations in the database
- Link users to organizations via memberships
- Display a summary of created data

### 3. Start FRANK Application

Start your FRANK application pointing to the seeded database:

```bash
# For Stage 1 (SQLite)
cd stages/stage1
python server.py
```

### 4. Test Access Control

Login with different users to test access control:

```bash
# Core Member - sees everything
curl -X POST http://localhost:8100/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Partner - sees partner-level data
curl -X POST http://localhost:8100/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "s_unit_analyst", "password": "TempPass123!"}'

# Observer - sees only own organization
curl -X POST http://localhost:8100/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "kpn_observer", "password": "TempPass123!"}'
```

## Programmatic Usage

You can use the `ComprehensiveFixtureSeeder` in your own scripts:

```python
from frank.storage.sqlite import SQLiteFRANKDatabase
from frank.util import ComprehensiveFixtureSeeder
import logging

logger = logging.getLogger(__name__)
db = SQLiteFRANKDatabase({"db_path": "/tmp/frank.db"}, logger=logger)

# Seed with comprehensive fixtures
seeder = ComprehensiveFixtureSeeder()
seeder.seed(db)
```

## Files

- `mock_cognito.py`: Mock Cognito service with fixture user data
- `init_fixtures.py`: Script to initialize database with organizations and memberships
- `FIXTURES.md`: This documentation file

## Customization

To add more organizations or users:

1. Add users to `USERS_DB` in `mock_cognito.py`
2. Add organizations to `ComprehensiveFixtureSeeder` in `src/frank/util/sample_builder.py`
3. Link users to organizations in the `memberships` list
4. Re-run `init_fixtures.py`

## Notes

- Passwords are intentionally simple for development (admin123, TempPass123!)
- Organization IDs use format: `identity--<name>` (STIX-compliant)
- Users have `organisation_id` custom attribute linking them to their org
- Access tiers follow: Observer < Contributor < Partner < Core Member
