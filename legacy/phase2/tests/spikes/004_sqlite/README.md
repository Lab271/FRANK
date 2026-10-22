# Spike 004: SQLite Storage Layer

## Status
INTEGRATED

## Hypothesis
Can SQLite provide sufficient performance and reliability for local FRANK development while maintaining data integrity across complex threat intelligence submission workflows?

## Integrated Into
- `src/frank/storage/sqlite.py` - SQLite database implementation
- `src/frank/storage/base.py` - BaseFRANKDatabase abstract interface
- `stages/stage1/` - Local development stage

## Key Learnings
- SQLite handles nested threat intelligence data structures well
- Foreign key constraints ensure data integrity
- JSON columns work for flexible observable storage
- Transaction safety adequate for development scenarios
- Query performance acceptable for expected data volumes

## Schema Design
- `organisations` table for cyber partners and customers
- `submissions` table with JSON sighting data
- `observables` table with type/value indexing
- Foreign key relationships maintain referential integrity

## Database Abstraction
This spike established the `BaseFRANKDatabase` interface pattern:
- `store_submission()`
- `get_submission_by_id()`
- `query_observables()`
- `upsert_organisation()`
- `health_check()`

Same interface later implemented for DynamoDB (Spike 006).
