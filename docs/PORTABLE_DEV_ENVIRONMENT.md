# FRANK Portable Development Environment

## TL;DR - Quick Start

```bash
# Setup new clone or worktree
make dev

# Activate environment
venv

# You're ready!
pytest
```

## The `.frank` Pattern

FRANK uses a **hidden, project-named virtual environment** pattern that enables portable, isolated development across git worktrees:

```
.frank/                    # Hidden virtualenv (gitignored)
├── bin/python            # Python 3.13.7
├── bin/pip               # Package manager
└── bin/pytest            # Test runner
```

### Why `.frank` and not `.venv`?

| Aspect | `.frank` | `.venv` |
|--------|----------|---------|
| **Visibility** | Project-specific | Generic naming |
| **Recognition** | Instantly identifiable | Could be anything |
| **Conflicts** | No convention clash | May conflict with other tools |
| **Branding** | Reinforces project identity | Generic |

## The `venv` Alias Magic

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
alias venv='source .*/bin/activate'
```

**How it works:**
- Wildcard `.*` matches any hidden directory
- Finds and activates local virtualenv automatically
- Works in every Python project
- One command to rule them all

**Usage:**
```bash
cd ~/wc/FRANK
venv                       # Activates .frank/bin/activate
(.frank) $ python          # Python 3.13.7
```

## Git Worktree Workflow

### The Problem

Traditional virtualenv approaches break with worktrees:

```bash
# ❌ Shared virtualenv causes conflicts
/project/.venv/                    # Shared by all worktrees
/project/                          # Main worktree (main branch)
/worktrees/feature-a/              # Feature worktree (dependencies conflict!)
/worktrees/feature-b/              # Another feature (more conflicts!)
```

### The Solution

Each worktree gets its own isolated environment:

```bash
# ✅ Independent environments
/project/.frank/                   # Main worktree's virtualenv
/worktrees/feature-a/.frank/       # Feature A's independent virtualenv
/worktrees/feature-b/.frank/       # Feature B's independent virtualenv
```

### Real Workflow

```bash
# Create worktree for new feature
git worktree add ../new-worktree/feat-auth feat/authentication
cd ../new-worktree/feat-auth

# Setup takes ONE command
make dev
# Creates .frank/, installs deps, ready to go!

# Activate and work
venv
pytest                             # Tests in isolation

# Switch to another worktree
cd ~/wc/FRANK                      # Main worktree
venv                               # Different .frank/, different deps
```

## Make Targets Explained

### `make dev` - Development Setup

```makefile
dev:$(VIRTUALENV)/bin/python  ## Install this for development
	@$(PYTHON) -m pip install --upgrade pip
	@$(PYTHON) -m pip install -e .        # Editable install
	@$(PYTHON) -m pip install ruff pytest coverage lark
```

**Use for:**
- Local feature development
- Active coding and testing
- Editable package install (changes reflect immediately)

### `make env` - Production-like Setup

```makefile
env: $(VIRTUALENV)/bin/python ## create the virtualenv
	@$(PYTHON) -m pip install -r requirements.txt
```

**Use for:**
- CI/CD pipelines
- Testing with frozen dependencies
- Reproducible builds

### Should They Be Merged?

**No.** Keep them separate because:

1. **Different installation modes**: `dev` uses `-e .` (editable), `env` uses regular install
2. **Different dependencies**: `dev` has dev tools, `env` has production deps
3. **Different workflows**: `dev` for iteration, `env` for verification

**Best practice:**
```bash
# Develop with latest tools
make dev && venv
# Edit, test, iterate...

# Before committing: verify with frozen deps
make clean && make env && make test
```

## VS Code Integration

### Automatic Detection

VS Code's Python extension automatically detects `.frank/`:

1. Open project in VS Code
2. `Cmd+Shift+P` → "Python: Select Interpreter"
3. Choose `.frank/bin/python` (Python 3.13.7)
4. Done!

### Multi-Worktree Setup

```json
// workspace.code-workspace
{
  "folders": [
    {"path": "/Users/you/wc/FRANK"},              // Main
    {"path": "/Users/you/wc/worktree/feat-auth"}  // Feature
  ]
}
```

Each folder maintains its own interpreter from its local `.frank/`.

## Benefits

### For Individual Developers

- ✅ **Zero configuration**: Clone → `make dev` → `venv` → code
- ✅ **Fast context switching**: `cd` + `venv` = instant activation
- ✅ **No environment confusion**: Each worktree isolated
- ✅ **Works everywhere**: macOS, Linux, WSL2

### For Teams

- ✅ **Consistent setup**: Everyone runs same `make dev`
- ✅ **Onboarding**: New devs productive in minutes
- ✅ **CI/CD compatible**: `make env` for reproducible builds
- ✅ **No "works on my machine"**: Virtualenv in git root

### For Git Worktrees

- ✅ **Independent dependencies**: Test package upgrades in one worktree
- ✅ **Parallel development**: Work on multiple features simultaneously
- ✅ **Branch-specific tools**: Different tool versions per worktree
- ✅ **No interference**: Changes in one worktree don't affect others

## Complete Example

### Scenario: Developing Authentication Feature

```bash
# 1. Create worktree from main branch
cd ~/wc/FRANK
git worktree add ../auth-worktree feat/token-refresh

# 2. Setup environment (ONE command)
cd ../auth-worktree
make dev
# Output:
#   Creating virtualenv at .frank/
#   Installing frank in editable mode...
#   Installing development tools...
#   Done!

# 3. Activate (ONE command)
venv
# Prompt: (.frank) $

# 4. Verify
python --version                   # Python 3.13.7
which python                       # .../auth-worktree/.frank/bin/python
pip list | grep frank              # Shows frank package

# 5. Develop
pytest tests/spikes/010_cognito/   # Run tests
ruff check src/                    # Lint code
python -m frank.server             # Run server

# 6. Switch to main worktree (different environment!)
cd ~/wc/FRANK
venv                               # Activates main's .frank
pytest                             # Uses main's dependencies

# 7. Back to feature worktree
cd ../auth-worktree
venv                               # Activates feature's .frank
# Continue development...

# 8. Cleanup when done
cd ~/wc/FRANK
git worktree remove ../auth-worktree
```

## Troubleshooting

### `venv` alias not working?

```bash
# Add to ~/.bashrc or ~/.zshrc
alias venv='source .*/bin/activate'

# Reload shell config
source ~/.bashrc  # or source ~/.zshrc
```

### Virtual environment not found?

```bash
# Check if .frank exists
ls -la .frank

# If not, create it
make dev
```

### Wrong Python version?

```bash
# Check virtualenv Python
.frank/bin/python --version  # Should be 3.13.7

# Recreate if wrong
make clean
make dev
```

### VS Code not detecting .frank?

```bash
# Manually set interpreter
Cmd+Shift+P → "Python: Select Interpreter"
→ Enter interpreter path: ${workspaceFolder}/.frank/bin/python
```

### Multiple worktrees interfering?

They shouldn't! Each worktree has its own `.frank/`. Verify:

```bash
# Check each worktree
cd ~/wc/FRANK && which python          # Should be .../FRANK/.frank/bin/python
cd ~/wc/worktree/feat && which python  # Should be .../feat/.frank/bin/python
```

## Advanced: CI/CD Integration

### GitHub Actions

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Python 3.13
        uses: actions/setup-python@v4
        with:
          python-version: '3.13'

      - name: Install virtualenv
        run: pip install virtualenv

      - name: Setup environment
        run: make env  # Use frozen dependencies

      - name: Run tests
        run: |
          source .frank/bin/activate
          make test
```

### Local Pre-commit Hook

```bash
# .git/hooks/pre-commit
#!/bin/bash
set -e

# Activate virtualenv
source .frank/bin/activate || { echo "Run 'make dev' first"; exit 1; }

# Run checks
echo "Running linter..."
ruff check .

echo "Running tests..."
pytest

echo "All checks passed!"
```

## Philosophy

The portable development environment strategy embodies FRANK's evolutionary design principles:

1. **Simple**: Two commands to start (`make dev` + `venv`)
2. **Explicit**: Virtual environment is visible in path
3. **Portable**: Works across machines, OSes, worktrees
4. **Isolated**: No global state, no hidden dependencies
5. **Reproducible**: Same setup for everyone
6. **Fast**: Context switching is instant

This isn't just about virtual environments - it's about **enabling rapid iteration while maintaining consistency**.

## References

- [FRANK Evolutionary Design](evolutionary_design.md)
- [Python venv documentation](https://docs.python.org/3/library/venv.html)
- [Git worktree documentation](https://git-scm.com/docs/git-worktree)
- [GNU Make manual](https://www.gnu.org/software/make/manual/)
