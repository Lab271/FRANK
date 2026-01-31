# FRANK Platform Glossary

## Organizations

### Member Organisation
A **member organisation** is an authenticated party that participates in the FRANK threat intelligence platform.

**Characteristics:**
- Has user accounts in AWS Cognito
- Can authenticate and access the Admin Web GUI
- Can **file sightings** (submit threat intelligence)
- Can **read sightings** (consume threat intelligence, subject to access tiers)
- Stored in PostgreSQL `organisations` table
- Has an access tier (public, observer, contributor, partner, core_member)
- **ID Format:** STIX-compliant `identity--{uuid4}` (e.g., `identity--550e8400-e29b-41d4-a716-446655440000`)

**Examples:**
- Schuberg Philis: `identity--7c9e6679-7425-40de-944b-e07fc1f90ae7` (cyber partner, core_member access)
- Rabobank: `identity--a3f2d8c1-9b4e-4d6f-8c2a-1e5f7b9d3c4a` (customer, contributor access)
- ING: `identity--2b8e4f6a-3c5d-4e7f-9a1b-6d8c2e4f7a9b` (customer, contributor access)

**Note:** Development/testing environments may use human-readable IDs like `identity--rabobank` for convenience.

**Storage:**
- PostgreSQL: Organisation metadata, member users
- Cognito: User authentication, groups, MFA

### Target Organisation
A **target organisation** (also called "hit target" or "victim organisation") is the party affected by a cybersecurity incident described in a sighting.

**Characteristics:**
- Appears in sightings as the victim/target of an attack
- **Does NOT need** Cognito accounts
- **Does NOT** authenticate to FRANK
- Can be anonymized for privacy
- May have limited metadata (sector, region, size)
- **ID Format:** STIX-compliant `identity--{uuid4}` (same format as member orgs, different UUID)

**Examples:**
- Target organisation: `identity--9d4e5f7a-2b3c-4d5e-8f9a-1c2d3e4f5a6b` (specific victim)
- Anonymized target: `identity--4a7b8c9d-3e2f-4a5b-9c8d-7e6f5a4b3c2d` (privacy-protected, minimal metadata)

**Note:**
- Both member and target organisations use `identity--{uuid}` format (STIX identity type)
- The UUID itself distinguishes them (different UUIDs for member vs target)
- Target orgs typically have minimal metadata (sector, region) for privacy

**Storage:**
- DynamoDB: As part of sighting/submission records
- Not in PostgreSQL (not a member)

---

## Key Distinction: Member vs Target

### Should They Be Separate?

**Recommendation: YES - Keep member and target organisations separate.**

#### Scenario: Member Testing Their Own Infrastructure

**Question:** If Rabobank (a member organisation) is testing its firewalls and discovers vulnerabilities in its own infrastructure, should they file a sighting against themselves?

**Answer:** Create a separate target organisation ID.

**Why Separate?**

1. **Clear Separation of Concerns**
   - Member org: `identity--a3f2d8c1-...` (authenticated, files sightings)
   - Target org: `identity--7b8e4f2c-...` (different UUID, victim in the sighting data)
   - Keeps identity layer separate from data layer

2. **Privacy & Anonymization**
   - Member orgs are always identified (authenticated with full metadata)
   - Target orgs can have minimal metadata for anonymization
   - If they use the same UUID, you can't anonymize yourself

3. **Access Control**
   - Member's access tier controls what they can READ
   - Target org in sighting controls who can SEE that data
   - Mixing them creates confusion about permissions

4. **Testing & Internal Use**
   - Rabobank can file sightings about different target UUIDs for testing
   - Keeps internal testing separate from production intelligence
   - Can have multiple target representations with different UUIDs

5. **Statistics & Reporting**
   - "Most targeted organisations" report won't confuse member identity with victim data
   - Member org can see stats about themselves as a target
   - Cleaner data model

#### Example: Rabobank Testing Scenario

```python
# Rabobank (member org) files a sighting about their own infrastructure
sighting = {
    "submitter": {
        "organisation_id": "identity--a3f2d8c1-9b4e-4d6f-8c2a-1e5f7b9d3c4a",  # Member who filed it
        "access_tier": "contributor"
    },
    "hit_target": {
        "organisation_id": "identity--7b8e4f2c-3d5a-4e6f-9a2b-8c7d6e5f4a3b",  # Target (different UUID)
        "sector": "Finance",
        "region": "Netherlands",
        "anonymization_level": "low"  # Or "high" for more privacy
    },
    "observables": [...],
    "description": "Detected during internal firewall testing"
}
```

---

## Related Concepts

### Access Tier
The level of access a **member organisation** has to read threat intelligence data.

**Levels** (from lowest to highest):
- **Public**: Can view public observables only
- **Observer**: Can view + specific sector observables
- **Contributor**: Can view + file sightings
- **Partner**: Can view partner-shared observables
- **Core Member**: Full access to platform

See: ADR-0004 (Access Tiers)

### Service Account
A machine/service identity for automated access, stored as a Cognito user.

**Characteristics:**
- Member of a member organisation
- Naming convention: `service-{org}-{purpose}` (e.g., `service-rabobank-ingestion`)
- Authenticates with Cognito JWT tokens (no password login)
- Has same access tier as parent organisation

See: docs/highlevel_design.md (Service Accounts)

### Observable
A threat indicator (IP, domain, hash, etc.) extracted from a sighting.

**Examples:**
- IPv4: `192.168.1.100`
- Domain: `malicious.example.com`
- File hash: SHA-256 of malware sample

See: src/frank/core/models.py (Observable class)

### Sighting
A specific observation of threat activity against a target organisation.

**Contains:**
- What was observed (observables)
- Who was hit (target organisation)
- When it occurred
- Context (MITRE ATT&CK, campaign info)
- Who reported it (submitter)

### Submission
A complete threat intelligence submission containing one or more sightings.

**Structure:**
- Submitter (member org filing the report)
- Multiple sightings
- Overall context and metadata

---

## Naming Conventions

### Organisation IDs (STIX Format)

**STIX-Compliant UUID Format:**
```
identity--{uuid4}
```

All organisations (both member and target) use the STIX identity type with UUID4:
- `identity--7c9e6679-7425-40de-944b-e07fc1f90ae7` (member org example)
- `identity--9d4e5f7a-2b3c-4d5e-8f9a-1c2d3e4f5a6b` (target org example)
- `identity--4a7b8c9d-3e2f-4a5b-9c8d-7e6f5a4b3c2d` (anonymized target example)

**UUID Generation:**
- UUIDs are generated using UUID4 (random)
- Format: `identity--{8 hex}-{4 hex}-{4 hex}-{4 hex}-{12 hex}`
- Each organisation gets a unique, random UUID
- Member vs target distinction is by context, not by ID format

**Development Note:** Test/development environments may use human-readable IDs like `identity--rabobank` for convenience, but production uses UUIDs.

### Service Account Usernames

**Service accounts are Cognito users with special naming:**
```
service-{organization}-{purpose}
```

Examples (usernames, not UUIDs):
- `service-rabobank-ingestion`
- `service-ing-threat-feed`
- `service-sunit-automated-scanner`

Service accounts belong to member organisations (referenced by org UUID).

---

## FAQ

### Can a member organisation see sightings where they are the target?

Yes, if their access tier permits. A member org can query sightings filtered by target UUID:

```bash
# Rabobank (member) queries sightings where they were the target
GET /v1/sightings?target_org=identity--7b8e4f2c-3d5a-4e6f-9a2b-8c7d6e5f4a3b
```

### Can target organisations become member organisations?

Yes. If a target organisation wants to participate actively:
1. Create a member org with a new UUID: `identity--{new-uuid4}`
2. Existing sightings with the old target UUID remain separate
3. They can now file AND read sightings
4. Their member UUID is different from their historical target UUID

### How do we handle anonymized targets?

Anonymized targets use the same `identity--{uuid}` format but with minimal metadata:

```python
{
    "organisation_id": "identity--4a7b8c9d-3e2f-4a5b-9c8d-7e6f5a4b3c2d",
    "sector": "Finance",              # Generic sector only
    "region": "Netherlands",          # Country/region only
    "organisation_size": "large",     # Size category
    "anonymization_level": "high"     # High anonymization
    # No specific org name, no detailed metadata
}
```

The mapping table (anonymized UUID → real organisation) is kept secure and separate from the main database.

---

**Last Updated:** 2026-01-31
**Related Documentation:**
- ADR-0003: Tiered Access Control Model
- ADR-0005: AWS Cognito Authentication Strategy
- ADR-0009: PostgreSQL for Management API
- docs/highlevel_design.md: Platform Architecture
- src/frank/core/models.py: Data Models
