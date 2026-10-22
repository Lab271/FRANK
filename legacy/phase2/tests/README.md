# FRANK Testing Framework

## Overview

The FRANK testing framework is organized into three distinct types of tests, each serving a specific purpose in validating the platform's functionality and reliability.

## Test Structure

```
tests/
├── unit/                             # Unit tests for all modules
├── integration/                      # BDD cucumber/behave tests  
├── spikes/                           # Hypothesis-driven learning spikes
└── README.md                         # This documentation
```

## Test Types

### 1. Unit Tests (`unit/`)

**Purpose**: Basic unit testing of all modules using pytest

- Test individual functions and classes in isolation
- Validate core business logic
- Mock external dependencies
- Fast execution and reliable feedback

**Running unit tests:**
```bash
pytest tests/unit/
```

or more simple

```bash
pytest .
```

To also include the spikes

### 2. Integration Tests (`integration/`)

**Purpose**: Cucumber/Behave driven BDD (Behavior Driven Development) tests

- End-to-end workflow validation
- Business scenario testing
- User story verification
- Real system integration testing

**Running integration tests:**
```bash
behave tests/integration/
```

### 3. Spikes (`spikes/`)

**Purpose**: Hypothesis-driven spikes (following Extreme Programming principles)

Spikes are time-boxed investigations to learn about specific elements:
- **Folders**: Exploratory code for learning new technologies or approaches
- **Files**: Standalone experiments and prototypes
- **Files with `*_test.py`**: Part of the pytest suite for validation

**Examples of spikes:**
- `spikes/009_aws_stage4/` - AWS ECS Fargate deployment with DynamoDB integration
- `spikes/006_dynamodb/` - Learning DynamoDB access patterns and queries
- `spikes/003_pydantic_test.py` - Pydantic model validation (part of pytest)

**Running spike tests:**
```bash
# Run all spike tests (only files ending with _test.py)
pytest tests/spikes/ -k "*_test.py"

# Run specific spike exploration
cd tests/spikes/009_aws_stage4/
python stage4_hypothesis.py
```

## Quick Start

### Prerequisites
- Python 3.11+
- Required dependencies: `cd xxx/FRANK && pip install -r requirements.txt`

### Running All Tests
```bash
# Unit tests
pytest tests/unit/

# Integration tests  
behave tests/integration/

# Spike tests
pytest tests/spikes/ -k "*_test.py"

# All tests in root of this project
make test  # or your preferred test runner
```

## Test Development Guidelines

### Unit Tests
- Follow pytest conventions
- Use descriptive test names
- Mock external dependencies
- Keep tests fast and isolated

### Integration Tests
- Write features in Gherkin syntax
- Implement step definitions in Python
- Use real system components when possible
- Clean up test data after scenarios

### Spikes
- Time-box investigations (typically 1-4 hours)
- Document findings in spike folders
- Convert valuable discoveries to proper tests
- Name validation files with `*_test.py` suffix

## Contributing

1. Choose the appropriate test type for your contribution
2. Follow the naming conventions for each category
3. Add proper documentation and cleanup
4. Ensure tests are reliable and maintainable
