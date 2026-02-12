# ADR-0002: Repository Pattern for Database Abstraction

## Status

Accepted

## Context

FRANK's four-stage evolution (ADR-0001) requires the same business logic to work across different database technologies:
- SQLite (Stage 1)
- DynamoDB (Stages 2-3)
- ScyllaDB (Stage 4)

Without proper abstraction, business logic would become entangled with database-specific code, making technology transitions risky and requiring rewrites at each stage.

Key requirements:
- Business logic must not import database-specific libraries
- All database implementations must behave identically
- Access control filtering must be consistent across implementations
- New database backends must be addable without changing existing code

## Decision

Implement the **Repository Pattern** with an abstract base class (`BaseFRANKDatabase`) that defines the interface for all database operations.

### Interface Definition

```python
class BaseFRANKDatabase(ABC):
    @abstractmethod
    def store_submission(self, submission: Submission) -> None

    @abstractmethod
    def get_submission_by_id(self, submission_id: str) -> Dict[str, Any]

    @abstractmethod
    def query_observables(self, org_id: str, ...) -> List[Observable]

    @abstractmethod
    def upsert_organisation(self, org_data: Dict[str, Any]) -> bool

    @abstractmethod
    def health_check(self) -> Dict[str, Any]

    @abstractmethod
    def log_access(self, org_id: str, action: str, ...) -> None
```

### Shared Behavior in Base Class

Access control filtering is implemented once in the base class:
- `_filter_submission_by_access_level()` - Filter submission data by access tier
- `_filter_observable_by_access_level()` - Filter observable data by access tier
- `hash_observable()` - Consistent hashing for deduplication

### Concrete Implementations

Each database technology implements the abstract interface:
- `SQLiteFRANKDatabase` in `src/frank/storage/sqlite.py`
- `DynamoDBFRANKDatabase` in `src/frank/storage/dynamodb.py`

### Usage Pattern

```python
# Business logic uses the abstract interface
def process_submission(db: BaseFRANKDatabase, submission: Submission):
    db.store_submission(submission)
    return db.get_submission_by_id(submission.submission_id)

# Infrastructure code provides the concrete implementation
if stage == 1:
    db = SQLiteFRANKDatabase({"db_path": "frank.db"})
elif stage == 3:
    db = DynamoDBFRANKDatabase({"table_name": "frank-submissions"})
```

## Consequences

### Positive

- **Technology Independence**: Business logic never imports sqlite3 or boto3
- **Consistent Behavior**: Access filtering works identically across all databases
- **Safe Transitions**: Switch databases by changing one line of configuration
- **Testable**: Can mock the interface for unit tests

### Negative

- **Interface Constraints**: Database-specific optimizations may be limited
- **Multiple Implementations**: Code must be maintained for each backend
- **Abstraction Overhead**: Some queries may be less efficient than native

### Tradeoffs

The repository pattern trades raw performance for portability. DynamoDB's query patterns differ from SQLite's, but the abstract interface finds a common subset that works for both.

## Alternatives Considered

### ORM (SQLAlchemy)
Use an Object-Relational Mapper to abstract database access.

**Rejected**: ORMs assume relational databases. DynamoDB and ScyllaDB are NoSQL with fundamentally different access patterns. An ORM would force relational thinking onto non-relational systems.

### Direct Database Access
Each stage uses database-specific code without abstraction.

**Rejected**: Would require rewriting business logic for each stage transition. High risk of behavioral differences between stages. No shared access control implementation.

### Query Builder Pattern
Abstract only query construction, not full repository.

**Rejected**: Still exposes database concepts to business logic. Doesn't solve the access filtering consistency problem.

## Validation

The repository pattern is validated through:

1. **Unit Tests**: Each implementation tested against the same test cases
2. **Integration Tests**: BDD tests verify identical behavior across databases
3. **Spike Tests**: New database backends validated before production use

Test evidence:
- `tests/unit/storage/` - Repository unit tests
- `tests/integration/` - Cross-database behavior tests

## Related ADRs

- ADR-0001: Four-Stage Infrastructure Evolution
- ADR-0003: Tiered Access Control Model

## Implementation Notes

- Base class: `src/frank/storage/base.py`
- SQLite impl: `src/frank/storage/sqlite.py`
- DynamoDB impl: `src/frank/storage/dynamodb.py`
- Factory pattern recommended for instantiation in production
