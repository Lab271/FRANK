# BDD Test Setup

This guide shows how to install and set up BDD testing dependencies.

## Prerequisites

- Python 3.11 or higher
- Virtual environment activated

## Installation

### Option 1: Install Dev Dependencies (Recommended)

Install all development dependencies including behave:

```bash
# Using uv (recommended)
uv pip install -e ".[dev]"

# Or using pip
pip install -e ".[dev]"

# Or using make (if available)
make dev
```

This installs:
- `behave>=1.2.6` - BDD testing framework
- `PyHamcrest>=2.0.0` - Assertion library for behave
- `pytest` and plugins - Unit testing
- `coverage` - Code coverage
- `mypy` - Type checking
- `isort` - Import sorting

### Option 2: Install Only BDD Testing Dependencies

If you only need BDD testing:

```bash
pip install behave PyHamcrest
```

## Verify Installation

```bash
# Check behave is installed
behave --version

# Should output:
# behave 1.2.6
```

## Dependencies for BDD Tests

### Already Included in Project
These are in the main `dependencies` section:
- ✅ `requests>=2.32.0` - HTTP client for API calls
- ✅ `PyJWT[crypto]>=2.10.0` - JWT token handling

### Dev Dependencies (BDD)
These are in `[project.optional-dependencies].dev`:
- ✅ `behave>=1.2.6` - BDD testing framework
- ✅ `PyHamcrest>=2.0.0` - Assertion matchers

## Running Tests

After installation:

```bash
# Test behave works
cd tests/integration
behave --version

# Run Cognito tests
behave features/cognito_management.feature -D cognito_port=8100

# Run server tests
behave features/frank_server_api.feature -D server_port=8000
```

## Troubleshooting

### behave command not found

**Problem:**
```bash
behave --version
-bash: behave: command not found
```

**Solution:**
```bash
# Make sure virtual environment is activated
source .venv/bin/activate

# Reinstall dev dependencies
pip install -e ".[dev]"

# Verify behave is in the venv
which behave
# Should show: /path/to/project/.venv/bin/behave
```

### Import errors

**Problem:**
```python
ModuleNotFoundError: No module named 'hamcrest'
```

**Solution:**
```bash
# Install PyHamcrest
pip install PyHamcrest

# Or reinstall dev dependencies
pip install -e ".[dev]"
```

### requests or jwt module not found

**Problem:**
```python
ModuleNotFoundError: No module named 'requests'
```

**Solution:**
```bash
# Install main project dependencies
pip install -e .

# This installs requests, PyJWT, and all other dependencies
```

## CI/CD Setup

### GitHub Actions

Add to your workflow:

```yaml
- name: Install dependencies
  run: |
    python -m pip install --upgrade pip
    pip install -e ".[dev]"

- name: Run BDD tests
  run: |
    cd tests/integration
    behave --junit --junit-directory results/
```

### Docker

Add to your Dockerfile:

```dockerfile
# Install dev dependencies
RUN pip install -e ".[dev]"

# Run tests
CMD ["behave", "tests/integration/features/"]
```

## What Gets Installed

### BDD Testing Stack
```
behave==1.2.6
  └─ parse>=1.18.0         # Parsing Gherkin steps
  └─ parse-type>=0.6.0     # Type parsing for steps
  └─ six>=1.15.0           # Python 2/3 compatibility

PyHamcrest==2.0.4
  └─ (no dependencies)     # Assertion matchers
```

### Already in Project
```
requests==2.32.3
  └─ charset-normalizer
  └─ idna
  └─ urllib3
  └─ certifi

PyJWT[crypto]==2.10.1
  └─ cryptography          # For RS256 tokens
```

## Quick Start Checklist

- [ ] Install dev dependencies: `pip install -e ".[dev]"`
- [ ] Verify behave: `behave --version`
- [ ] Activate virtual environment: `source .venv/bin/activate`
- [ ] Start Mock Cognito: `cd tests/spikes/014_cognito && python mock_cognito.py`
- [ ] Run tests: `cd tests/integration && behave features/cognito_management.feature`

## Related Documentation

- `README_BDD.md` - General BDD testing guide
- `RUN_COGNITO_TESTS.md` - Cognito-specific test guide
- `pyproject.toml` - Project dependencies

---

**Last Updated:** 2026-01-31
