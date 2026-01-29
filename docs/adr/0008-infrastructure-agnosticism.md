# Infrastructure Agnosticism

- **Status:** accepted
- **Date:** 2026-01-28
- **Decision Makers:** FRANK Architecture Team
- **Related:** [ADR-0007](0007-single-source-of-truth.md), [ADR-0009](0009-controlled-complexity-introduction.md)

## Context and Problem Statement

FRANK must operate across diverse infrastructure environments (local SQLite, cloud DynamoDB, Kubernetes ScyllaDB) as it evolves through four stages. How can we prevent vendor lock-in and ensure the system can confidently transition between technologies without requiring business logic rewrites?

## Decision Drivers

- Need to support multiple database technologies (SQLite, DynamoDB, ScyllaDB)
- Must avoid vendor lock-in to specific cloud providers or platforms
- Enable confident technology evolution based on operational needs
- Support multiple compute platforms (laptop, Docker, ECS, Kubernetes)
- Facilitate parallel operation of different infrastructure implementations
- Allow infrastructure-specific optimizations without coupling business logic

## Considered Options

1. **Abstract Repository Pattern** - Database and infrastructure accessed only through abstract interfaces
2. **Direct Database Integration** - Business logic directly uses database-specific APIs
3. **Microservices Architecture** - Separate services for each database technology

## Decision Outcome

Chosen option: "Abstract Repository Pattern", because it enables seamless infrastructure transitions while maintaining a single unified codebase and allowing infrastructure-specific optimizations when needed.

The system operates across diverse infrastructure environments without code changes to business logic. Database technology, compute platforms, and deployment environments remain interchangeable through abstraction layers.

### Positive Consequences

- Can switch databases without business logic changes
- Prevents vendor lock-in to cloud providers
- Enables A/B testing between infrastructure implementations
- Container-based deployments portable across cloud providers
- Infrastructure-specific optimizations possible within adapters
- Can run multiple infrastructure implementations simultaneously

### Negative Consequences

- Requires careful abstraction layer design
- May limit access to database-specific advanced features initially
- Testing complexity increases (must validate across all implementations)
- Performance tuning requires infrastructure-specific knowledge

## Pros and Cons of the Options

### Abstract Repository Pattern

- Good, because business logic remains infrastructure-independent
- Good, because enables confident technology transitions
- Good, because prevents vendor lock-in
- Good, because supports multiple simultaneous implementations
- Good, because container portability across cloud providers
- Bad, because abstraction layer adds initial complexity
- Bad, because may hide database-specific capabilities

### Direct Database Integration

- Good, because simple and direct
- Good, because full access to database features
- Good, because maximum performance initially
- Bad, because couples business logic to specific technologies
- Bad, because vendor lock-in
- Bad, because technology transitions require rewrites
- Bad, because cannot run multiple implementations

### Microservices Architecture

- Good, because complete isolation between implementations
- Good, because independent scaling per service
- Bad, because excessive complexity for current needs
- Bad, because network overhead between services
- Bad, because distributed system complexity (consistency, transactions)
- Bad, because operational overhead

## Implementation Details

### Repository Interface

All database operations go through `BaseFRANKDatabase` abstract interface ([src/frank/storage/base.py](../../src/frank/storage/base.py)):

```python
class BaseFRANKDatabase(ABC):
    @abstractmethod
    def store_submission(self, submission: Submission) -> str:
        """Store threat intelligence submission"""

    @abstractmethod
    def get_submission_by_id(self, submission_id: str, requester_access_level: AccessTier) -> Optional[Submission]:
        """Retrieve submission with access filtering"""

    @abstractmethod
    def query_observables(self, org_id: str, observable_type: Optional[ObservableType] = None, ...) -> List[Observable]:
        """Query observables with access control"""
```

### Infrastructure Implementations

- **SQLite** ([src/frank/storage/sqlite.py](../../src/frank/storage/sqlite.py)) - Stage 1: Local development
- **DynamoDB** ([src/frank/storage/dynamodb.py](../../src/frank/storage/dynamodb.py)) - Stages 2-3: AWS Cloud
- **ScyllaDB** (planned) - Stage 4: Kubernetes production

### Container Strategy

Docker containers enable portability:
- Base images consistent across environments
- Environment-specific configuration via environment variables
- Database connection strings externalized
- Infrastructure adapters selected at runtime

### Testing Strategy

- Unit tests validate abstract interface contracts
- Integration tests run against all infrastructure implementations
- Performance benchmarks compare implementations
- Migration validation ensures data integrity across transitions

## Links

- Enables [ADR-0007: Single Source of Truth](0007-single-source-of-truth.md)
- Supports [ADR-0009: Controlled Complexity Introduction](0009-controlled-complexity-introduction.md)
- Implementation: [src/frank/storage/](../../src/frank/storage/)
- Related: [docs/evolutionary_design.md](../evolutionary_design.md)
