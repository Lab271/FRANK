# ADR-0003: Tiered Access Control Model

## Status

Accepted

## Context

FRANK is a threat intelligence sharing platform where different organizations contribute and consume intelligence. Not all participants should see all data:

- Some data is highly sensitive (victim organization details)
- Contributions should be rewarded with greater access
- Public statistics should be available broadly
- Trust relationships vary between organizations

Key requirements:
- Progressive disclosure based on participation level
- Consistent filtering regardless of database backend
- Privacy protection for sensitive fields (victim identity, specific IOCs)
- Audit trail for access decisions

## Decision

Implement a **five-tier access control model** with progressive disclosure:

### Access Tiers

| Tier | Description | Access Level |
|------|-------------|--------------|
| `PUBLIC` | Anonymous users, general public | Statistics only |
| `OBSERVER` | Registered but non-contributing | Masked observables |
| `CONTRIBUTOR` | Active intelligence contributors | Anonymized targets |
| `PARTNER` | Trusted sharing partners | Full submission data |
| `CORE_MEMBER` | Platform operators, vetted analysts | Full access + audit |

### Tier Permissions

**PUBLIC**
- Submission ID and timestamp
- Sighting confidence score
- Observation count
- No observable values, no victim details

**OBSERVER**
- All PUBLIC data
- Observable types (IP, domain, hash)
- Masked observable values (first 10 characters + "...")
- No hit_target or TLP information

**CONTRIBUTOR**
- All OBSERVER data
- Full observable values
- Hit target sector (anonymized)
- No victim organization_id

**PARTNER / CORE_MEMBER**
- Complete submission data
- Full hit_target details including organization_id
- TLP level information
- Access to audit logs (CORE_MEMBER only)

### Implementation

Access filtering is implemented in `BaseFRANKDatabase`:

```python
def _filter_submission_by_access_level(self, submission: Dict, access_level: AccessTier):
    if access_level == AccessTier.PUBLIC:
        # Return only statistics
    elif access_level == AccessTier.OBSERVER:
        # Mask observable values, remove sensitive sections
    elif access_level == AccessTier.CONTRIBUTOR:
        # Anonymize hit target
    else:
        # Full access for PARTNER and CORE_MEMBER
```

This ensures filtering is consistent across all database implementations.

## Consequences

### Positive

- **Privacy by Design**: Sensitive data protected at the database layer
- **Incentive Structure**: Contributing intelligence grants greater access
- **Consistent Filtering**: Same rules apply regardless of database backend
- **Auditable**: Access decisions logged for compliance

### Negative

- **Complexity**: Five tiers add business logic complexity
- **Query Overhead**: Every query includes filtering logic
- **Tier Management**: Organizations must be assigned and maintained at correct tiers

### Tradeoffs

More granular tiers (e.g., per-field permissions) would offer flexibility but increase complexity. Five tiers balances usability with security needs.

## Alternatives Considered

### Binary Access (Public/Private)
Simple two-level system: either full access or none.

**Rejected**: Doesn't support the collaborative sharing model. Contributors would have no incentive to share if observers get the same access.

### Role-Based Access Control (RBAC)
Define roles with specific permissions on each resource type.

**Rejected**: RBAC is more complex than needed. FRANK's access patterns are primarily tier-based, not role-based. RBAC would add operational overhead without benefit.

### Attribute-Based Access Control (ABAC)
Dynamic policies based on user and resource attributes.

**Rejected**: Overkill for current requirements. ABAC engines are complex and harder to audit. Tier-based model is simpler and sufficient.

## Validation

Access control validated through:

1. **Unit Tests**: Each tier tested for correct field visibility
2. **Integration Tests**: BDD scenarios verify tier behavior
3. **Manual Review**: Security review of filtering logic

Test files:
- `tests/unit/storage/test_access_filtering.py`
- `tests/integration/features/access_control.feature`

## Related ADRs

- ADR-0002: Repository Pattern for Database Abstraction

## Implementation Notes

- Enum: `src/frank/core/enum.py` - `AccessTier`
- Filtering: `src/frank/storage/base.py` - `_filter_submission_by_access_level()`
- API enforcement: Each endpoint specifies required access tier
