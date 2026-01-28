# Spike 003: Pydantic v2 Models

## Status
INTEGRATED

## Hypothesis
Can Pydantic v2 provide better validation, serialization, and developer experience than dataclasses while maintaining the patterns established in Spike 001?

## Integrated Into
- `src/frank/core/models.py` - All core models (Observable, Submission, Sighting, etc.)
- Factory methods: `Observable.create_ipv4()`, `Submission.create_minimal()`
- Legacy format support: `Submission.from_legacy_dict()`

## Key Learnings
- Pydantic v2 offers significant performance improvements over v1
- `field_validator` and `model_validator` enable complex cross-field validation
- `ConfigDict(extra="ignore")` provides forgiving input parsing
- Field aliases enable YAML/JSON flexibility (e.g., `type` vs `observable_type`)
- Automatic ID generation works well with `default_factory`

## Pydantic Patterns Adopted
- Factory methods for common use cases
- `model_validator(mode="after")` for cross-field validation
- `field_serializer` for datetime ISO string serialization
- Nested model validation with automatic type coercion
- `from_legacy_dict()` for backward compatibility

## Validation Features
- Range validation (confidence 0-100, ports 1-65535)
- Enum validation for observable types
- Timestamp consistency checks (first_observed <= last_observed)
- Automatic STIX-compliant ID generation
