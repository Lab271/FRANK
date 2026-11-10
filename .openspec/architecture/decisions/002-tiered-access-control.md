# ADR-002: Tiered Access Control Model

- **Status:** Accepted
- **Date:** 2026-02-12

**Context:**

FRANK operates as a threat intelligence sharing platform where organizations contribute and consume threat data. We need to balance:
1. **Encouraging contribution** - Organizations should be incentivized to share their threat intelligence
2. **Privacy protection** - Organizations should not expose sensitive victim information
3. **Trust building** - Access to sensitive data should require demonstrated commitment
4. **Preventing freeloading** - Pure consumers without contribution should have limited access

Traditional binary access models (public/private) don't capture the nuances of threat intelligence sharing communities.

**Decision:**

We will implement a **five-tier access control model** with escalating privileges based on contribution and trust:

## Access Tiers

### 1. PUBLIC (Tier 0)
- **Who**: Anonymous users, general public
- **Access**: Basic metadata only
- **Read**: Observable types, timestamps (no values)
- **Write**: None
- **Use Case**: Platform discovery, public statistics

### 2. OBSERVER (Tier 1)
- **Who**: Registered organizations, no contribution yet
- **Access**: Read most fields except sensitive ones
- **Read**: Observables, sighting details, threat context
- **Hidden**: Hit target identity, submitter identity
- **Write**: None
- **Use Case**: Evaluation period, learning mode

### 3. CONTRIBUTOR (Tier 2)
- **Who**: Organizations actively submitting intelligence
- **Access**: Read + Write threat intelligence
- **Read**: Same as OBSERVER
- **Write**: Submit observables, sightings, submissions
- **Hidden**: Hit target identity still masked
- **Use Case**: Active community participants

### 4. PARTNER (Tier 3)
- **Who**: Trusted organizations with proven track record
- **Access**: Full read including submitter identity
- **Read**: All fields including submitter organization_id
- **Write**: Submit threat intelligence
- **Revealed**: Submitter identity (who reported this?)
- **Hidden**: Hit target identity (victim privacy)
- **Use Case**: Established trust relationships

### 5. CORE_MEMBER (Tier 4)
- **Who**: Platform operators, incident responders
- **Access**: Full access including administrative operations
- **Read**: All fields including hit target identity
- **Write**: All operations + organization management
- **Revealed**: Everything (submitter + victim)
- **Use Case**: Platform administration, incident response coordination

## Implementation Approach

### Repository Layer Filtering

Access tier filtering is implemented **at the repository layer** (storage/base.py), not in application code:

```python
class BaseFRANKDatabase:
    def _filter_submission_by_access_level(
        self,
        submission: Submission,
        access_level: AccessTier
    ) -> Submission:
        """Apply access tier filtering to submission."""
        if access_level == AccessTier.PUBLIC:
            # Mask almost everything
            submission.observables = None
            submission.submitter.organization_id = "REDACTED"

        elif access_level == AccessTier.OBSERVER:
            # Mask identities
            submission.submitter.organization_id = "REDACTED"
            submission.hit_target.organization_id = "REDACTED"

        elif access_level == AccessTier.CONTRIBUTOR:
            # Same as OBSERVER (masking)
            submission.submitter.organization_id = "REDACTED"
            submission.hit_target.organization_id = "REDACTED"

        elif access_level == AccessTier.PARTNER:
            # Reveal submitter, mask victim
            submission.hit_target.organization_id = "REDACTED"

        elif access_level == AccessTier.CORE_MEMBER:
            # Full access, no masking
            pass

        return submission
```

### Benefits of Repository Layer Filtering

1. **Centralized**: Single implementation for all database backends
2. **Consistent**: Cannot be bypassed by application code
3. **Testable**: Clear unit tests for each tier
4. **Auditable**: Filtering logic in one place

### Access Tier Assignment

- Stored in AWS Cognito as user groups (Stage 3)
- Extracted from JWT token `cognito:groups` claim
- Passed to repository methods: `get_submission_by_id(id, access_level)`
- No database lookup required for access checks (stateless)

**Rationale:**

### Why Five Tiers?

1. **PUBLIC** - Necessary for platform discovery without login walls
2. **OBSERVER** - Trial period allows evaluation before committing
3. **CONTRIBUTOR** - Reward contribution with deeper access
4. **PARTNER** - Attribution matters for trusted relationships
5. **CORE_MEMBER** - Operators need full visibility for incident response

### Why Repository Layer?

- **Security**: Cannot be bypassed by application bugs
- **Consistency**: Works identically across all database implementations
- **Performance**: Filter once in repository vs filtering in every API endpoint
- **Simplicity**: Application code doesn't need to know about access tiers

### Why Progressive Revelation?

- **Encourages Contribution**: "Give to get" model prevents freeloading
- **Privacy Protection**: Victim identity requires highest trust
- **Attribution**: Knowing the source matters for threat validation
- **Trust Building**: Access increases with demonstrated commitment

**Consequences:**

### Positive

- ✅ Encourages active contribution over passive consumption
- ✅ Protects victim privacy (hit target) at all but highest tier
- ✅ Reveals attribution (submitter) to partners for validation
- ✅ Cannot bypass filtering (repository layer enforcement)
- ✅ Clear progression path: OBSERVER → CONTRIBUTOR → PARTNER
- ✅ Stateless (access tier in JWT, no database lookups)

### Negative

- ❌ More complex than binary public/private
- ❌ Requires careful field masking in repository layer
- ❌ Need to educate users about tier meanings
- ❌ Manual tier promotion requires platform admin

### Neutral

- 🔄 Tier promotion process needs definition
- 🔄 Metrics needed to determine promotion criteria
- 🔄 Appeals process for denied promotions

**Alternative Considered:**

### Binary Access (Rejected)

- **Public or Private** - Too coarse-grained
- **Problem**: No incentive to contribute
- **Problem**: No way to build trust incrementally

### Role-Based Only (Rejected)

- **Admin, User, Guest** - Doesn't capture contribution
- **Problem**: Treats active contributors same as lurkers
- **Problem**: No progressive trust model

### Contribution Score Based (Deferred)

- **Algorithmic tier assignment** based on quantity/quality
- **Deferred to Stage 4**: Requires operational data to calibrate
- **May supplement** manual tier assignment in future

**Validation:**

This decision has been implemented and validated:
- ✅ Repository layer filtering in `src/frank/storage/base.py`
- ✅ Unit tests for each access tier
- ✅ Cognito groups mapped to AccessTier enum
- ✅ JWT claims include access tier
- ✅ API endpoints enforce minimum tiers

**References:**

- Implementation: `src/frank/storage/base.py` (_filter_submission_by_access_level)
- Enum: `src/frank/core/enum.py` (AccessTier)
- Spec: `.openspec/specs/010-sightings-api/spec.md`
- Tests: `tests/unit/storage/test_access_filtering.py`

**Review Date:** 2026-08-12 (6 months, evaluate promotion criteria)
