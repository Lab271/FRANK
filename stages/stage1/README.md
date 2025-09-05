# FRANK Implementation Plan - Stage 1

## Overview
This stage 1 is part of the 5-stage progressive development approach for FRANK (Feedback Infrastructure for Cyber Risk Analysis and Network Knowledge sharing), evolving from a local SQLite/FastAPI prototype to a scalable AWS production system.


**Technology Stack**:
- **Database**: SQLite (local file)
- **API**: FastAPI
- **Location**: Local development
- **Submissions**: Minimal model

**Capabilities**:
- Pydantic data models with validation
- SQLite database with normalized schema
- Comprehensive unit tests
- Basic threat intelligence submission handling

**Deliverables**:
- Working FastAPI application
- SQLite database schema
- Unit test suite
- Minimal submission model

To run, try:
```bash

python stages/stage\ 1/server.py
```

For more details see the [implementation plan](../../docs/implementation_plan.md#Stage-1).