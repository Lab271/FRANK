# ADR-0005: MVC Architecture for Admin Module

## Status

Accepted

## Context

The FRANK Admin module provides a terminal-based user interface (TUI) for managing organisations and users. Initial implementation mixed UI code with business logic in Textual screens, resulting in:

- **Low testability**: Textual screens require complex AppTest setup to test
- **No reusability**: Business logic embedded in TUI couldn't be shared with a future web GUI
- **Mixed concerns**: Display formatting interleaved with API calls and validation

Key requirements:
- Business logic must be testable without Textual
- Display logic must be reusable across TUI and web GUI
- DTOs must be pure data containers without presentation concerns
- Clear separation between data transfer, business rules, and display

## Decision

Implement a **Model-ViewModel-Service (MVS)** architecture with three distinct layers:

### Layer 1: Models (DTOs)

Pure data transfer objects for API communication. No display logic.

```
src/frank/admin/models/
├── base.py           # Shared utilities (parse_datetime)
├── organisation.py   # OrganisationDTO, OrganisationListResult
├── user.py           # UserDTO, UserListResult
├── member.py         # MemberDTO, MemberListResult
└── health.py         # HealthStatus
```

```python
@dataclass
class OrganisationDTO:
    organisation_id: str
    name: str
    organisation_type: str
    sector: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "OrganisationDTO":
        """Create from API response."""

    def to_dict(self) -> dict:
        """Convert for API request."""
```

### Layer 2: Services

Business logic layer with validation, error handling, and API orchestration.

```
src/frank/admin/services/
├── base.py                    # ServiceResult pattern
├── auth_service.py            # Login, logout, token management
├── organisation_service.py    # Organisation CRUD
└── user_service.py            # User CRUD
```

```python
class OrganisationService:
    def __init__(self, client: AdminClient):
        self.client = client

    async def create_organisation(
        self, name: str, organisation_type: str, ...
    ) -> ServiceResult:
        """Validate and create organisation."""
        if not name:
            return ServiceResult.fail("Name is required")
        if organisation_type not in ("customer", "cyber_partner"):
            return ServiceResult.fail("Invalid type")
        # ... call client, wrap result
```

### Layer 3: ViewModels

Display-oriented presentation logic. Wraps DTOs with formatting.

```
src/frank/admin/viewmodels/
├── organisation_vm.py  # OrganisationViewModel
├── user_vm.py          # UserViewModel, MemberViewModel
└── health_vm.py        # HealthViewModel
```

```python
@dataclass
class OrganisationViewModel:
    dto: OrganisationDTO

    @property
    def type_display(self) -> str:
        """Human-readable type."""
        return {"customer": "Customer", "cyber_partner": "Cyber Partner"}.get(
            self.dto.organisation_type, self.dto.organisation_type
        )

    def to_table_row(self) -> Tuple[str, str, str, str, str]:
        """Convert to DataTable row."""
        return (self.id, self.name, self.type_display, ...)
```

### Data Flow

```
API Response → Client → Service → DTO → ViewModel → Screen
                          ↓           ↓
                     validation    formatting

Screen Input → ViewModel → Service → Client → API Request
                              ↓
                         validation
```

### ServiceResult Pattern

All service methods return a consistent result type:

```python
@dataclass
class ServiceResult:
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None

    @classmethod
    def ok(cls, data=None) -> "ServiceResult"

    @classmethod
    def fail(cls, error: str) -> "ServiceResult"
```

## Consequences

### Positive

- **Testable Services**: 95+ tests for services without Textual dependency
- **Reusable ViewModels**: Same display logic for TUI and future web GUI
- **Pure DTOs**: Clean data containers without presentation concerns
- **Consistent Error Handling**: ServiceResult pattern across all operations
- **Coverage**: 75% overall (services at 70-77%, viewmodels at 100%)

### Negative

- **More Files**: 15+ files instead of monolithic screens
- **Indirection**: Data passes through multiple layers
- **Learning Curve**: Developers must understand layer responsibilities

### Tradeoffs

The architecture prioritizes testability and reusability over simplicity. For a TUI-only application, this might be over-engineered. However, FRANK plans to add a web GUI, making the investment worthwhile.

## Alternatives Considered

### Fat Screens

Keep all logic in Textual screens.

**Rejected**: Makes testing difficult, prevents code reuse with web GUI, mixes concerns.

### Service + DTO Only

Skip ViewModels, put display logic in screens or DTOs.

**Rejected**: DTOs become polluted with UI concerns, display logic duplicated across TUI and web GUI.

### MVVM with Reactive Bindings

Full Model-View-ViewModel with observable properties.

**Rejected**: Overkill for current needs. Textual has its own reactive system. Would add complexity without clear benefit.

## Validation

The architecture is validated through:

1. **Unit Tests**: 169 admin tests, 95+ for services/viewmodels alone
2. **Coverage**: 75.15% overall, meeting 74% threshold
3. **Independence**: Services testable with mocked client, no Textual import

Test evidence:
- `tests/unit/admin/test_services/` - Service layer tests
- `tests/unit/admin/test_viewmodels/` - ViewModel tests

## Related ADRs

- ADR-0002: Repository Pattern - Similar abstraction approach
- ADR-0004: Three-Layer Testing Strategy - Test organization

## Implementation Notes

Directory structure:
```
src/frank/admin/
├── models/        # DTOs - pure data
├── services/      # Business logic
├── viewmodels/    # Display logic
├── screens/       # Textual views (thin)
├── client.py      # HTTP client
├── config.py      # Configuration
└── app.py         # Main application
```

Key files:
- `models/__init__.py` - DTO exports
- `services/base.py` - ServiceResult
- `viewmodels/__init__.py` - ViewModel exports

Future work:
- Wire screens to use services/viewmodels (currently screens still use client directly)
- Add web GUI using same services/viewmodels
