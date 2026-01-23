# Spike 002: Access-Based Filtering Architecture

## Status
INTEGRATED

## Hypothesis
Can rule-based filtering provide granular, maintainable access control across multiple data sensitivity levels while preserving analytical value for each access tier?

## Integrated Into
- `src/frank/core/enum.py` - AccessTier enumeration
- `src/frank/storage/base.py` - `_filter_submission_by_access_level()`, `_filter_observable_by_access_level()`
- `src/frank/core/models.py` - Access tier field integration

## Key Learnings
- Rule-based filtering enables flexible, maintainable access control
- Tier hierarchy (PUBLIC < OBSERVER < CONTRIBUTOR < PARTNER < CORE_MEMBER) works well
- Filter actions (ALLOW, REMOVE, HASH, MASK, AGGREGATE, GENERALIZE) cover all use cases
- Deep filtering on nested structures requires careful wildcard pattern matching
- Performance acceptable for real-time API filtering

## Validation Areas
- Rule definition clarity across complex data structures
- Performance of deep filtering operations
- Data utility preservation for each tier
- Security effectiveness (no data leaks)

## Filter Actions Implemented
- **ALLOW**: Pass through unchanged
- **REMOVE**: Remove field entirely
- **HASH**: Replace with deterministic hash
- **MASK**: Partial masking (e.g., IP obfuscation)
- **AGGREGATE**: Replace with statistical summary
- **GENERALIZE**: Replace with broader category
