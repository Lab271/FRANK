# Spike 006: DynamoDB Storage Layer

## Status
INTEGRATED

## Hypothesis
Can DynamoDB provide a scalable, cloud-native storage solution for FRANK while maintaining the same interface as SQLite for seamless stage transitions?

## Integrated Into
- `src/frank/storage/dynamodb.py` - DynamoDB implementation
- `stages/stage2/` - Docker/LocalStack stage
- `stages/stage3/` - AWS cloud deployment

## Key Learnings
- DynamoDB single-table design works well for threat intelligence
- Composite keys (PK/SK) enable flexible query patterns
- GSI (Global Secondary Index) needed for observable lookups
- LocalStack provides adequate local development experience
- Same `BaseFRANKDatabase` interface ensures code portability

## Table Design
- **Main Table**: Submissions, organisations, observables
- **Audit Table**: Request logs with TTL
- Partition key: entity type + ID
- Sort key: timestamp or secondary identifier

## Query Patterns
- Get submission by ID
- Query observables by type/value
- Organisation lookups
- Time-range queries via sort key

## Local Development
Uses LocalStack for local DynamoDB emulation:
```bash
docker-compose up dynamodb-local
```
