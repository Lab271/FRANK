# FRANK Evolving Design Approach

## Philosophy: Structured Evolution Over Big-Bang Development

FRANK (Feedback Infrastructure for Cyber Risk Analysis and Network Knowledge sharing) demonstrates a **structured evolutionary approach** to software development that separates infrastructure complexity from functional complexity while maintaining working systems at every stage.

Rather than attempting to build the complete system in one go, FRANK evolves through deliberate stages where each stage maintains a fully working system, introduces one major complexity dimension at a time, provides fallback options to previous stages, and enables confident experimentation through comprehensive testing.

## Portable Development Environment

FRANK employs a **portable, local-first development environment** strategy that enables developers to work efficiently across multiple branches, worktrees, and machines without environment conflicts or complex setup procedures.

### The `.frank` Virtual Environment Pattern

The project uses a **hidden directory pattern** for virtual environments that provides several key benefits:

```bash
# Virtual environment location
.frank/                    # Hidden directory (gitignored)
├── bin/                   # Python executables
│   ├── python            # Python 3.13 interpreter
│   ├── pip               # Package installer
│   └── pytest            # Test runner
├── lib/                   # Installed packages
└── pyvenv.cfg            # Virtualenv configuration
```

**Key Design Decisions:**

1. **Hidden Directory (`.frank`)**: Using a dot-prefix keeps the virtual environment hidden from casual directory listings while making it easily identifiable as project infrastructure.

2. **Project-Named Pattern**: The virtualenv is named after the project (`.$(PACKAGE)` where `PACKAGE=frank`), making it instantly recognizable and avoiding generic names like `.venv` that could conflict with other conventions.

3. **Local to Repository Root**: Each git clone/worktree gets its own isolated virtual environment, preventing cross-contamination between branches or experimental work.

4. **Python 3.13 Explicit**: The virtualenv explicitly uses Python 3.13, ensuring consistency across all development environments regardless of system Python version.

### Makefile-Driven Setup

The project uses GNU Make to provide a **single command setup** for new developers or new worktrees:

```bash
# One-command setup for new clone or worktree
make dev
```

This single command:
1. Creates `.frank/` virtualenv if not present
2. Upgrades pip to latest version
3. Installs FRANK package in editable mode (`-e .`)
4. Installs development tools (ruff, pytest, coverage, lark)

**Makefile Pattern:**
```makefile
PACKAGE=frank
VIRTUALENV = ./.$(PACKAGE)
PYTHON = $(VIRTUALENV)/bin/python

dev:$(VIRTUALENV)/bin/python  ## Install this for development
	@$(PYTHON) -m pip install --upgrade pip
	@$(PYTHON) -m pip install -e .
	@$(PYTHON) -m pip install ruff pytest coverage lark

$(VIRTUALENV)/bin/python: # create the local virtualenv
	virtualenv $(VIRTUALENV)
	echo "To activate 'source $(VIRTUALENV)/bin/activate'"
```

**Benefits:**
- **Idempotent**: Running `make dev` multiple times is safe and fast
- **Declarative**: Dependencies declared in one place
- **Cross-Platform**: Works on macOS, Linux, and WSL2
- **Version Controlled**: Makefile is committed, ensuring all developers use same setup

### Shell Integration: The `venv` Alias

Developers use a **wildcard shell alias** for rapid environment activation:

```bash
# In ~/.bashrc or ~/.zshrc
alias venv='source .*/bin/activate'
```

**How It Works:**
- The wildcard `.*` matches any hidden directory (`.frank`, `.venv`, `.python`, etc.)
- Automatically finds and activates the local virtual environment
- Works in any project directory without remembering specific names
- One command across all projects: just type `venv`

**Usage Pattern:**
```bash
$ cd ~/wc/FRANK
$ venv                        # Activates .frank/bin/activate
(.frank) $ python --version   # Python 3.13.7
(.frank) $ pytest            # Runs tests in isolated env
```

### Git Worktree Compatibility

This pattern is **specifically designed for git worktrees**, which allow working on multiple branches simultaneously:

```bash
# Main development repository
/Users/iheitlager/wc/FRANK/
├── .frank/                    # Virtual env for main branch
├── src/frank/                 # Source code
└── tests/                     # Tests

# Separate worktree for feature branch
/Users/iheitlager/wc/new-worktree/background-tasks/
├── .frank/                    # Independent virtual env
├── src/frank/                 # Same source, different branch
└── tests/                     # Same tests, different state
```

**Worktree Workflow:**
```bash
# Create new worktree for feature branch
git worktree add ../new-worktree/background-tasks feat/background-tasks

# Setup independent environment
cd ../new-worktree/background-tasks
make dev                      # Creates separate .frank/ virtualenv

# Activate and work
venv                          # Activates this worktree's environment
pytest                        # Tests run in isolation
```

**Key Benefits for Worktrees:**
1. **No Interference**: Each worktree has isolated dependencies
2. **Version Testing**: Can test Python package upgrades in one worktree without affecting others
3. **Branch-Specific Tools**: Different branches can have different dev tool versions
4. **Parallel Development**: Work on multiple features without environment switching
5. **Quick Context Switch**: `cd` to worktree, type `venv`, and you're ready

### VS Code Integration

VS Code's Python extension automatically detects `.frank/` virtual environments:

**Automatic Detection:**
- Extension scans for `pyvenv.cfg` in hidden directories
- `.frank/bin/python` appears in Python interpreter selector
- IntelliSense uses correct package versions
- Integrated terminal auto-activates environment

**Configuration (Optional):**
```json
// .vscode/settings.json (project-specific, gitignored)
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.frank/bin/python",
  "python.terminal.activateEnvironment": true
}
```

**Workspace Setup:**
1. Open FRANK project in VS Code
2. Press `Cmd+Shift+P` → "Python: Select Interpreter"
3. Choose `.frank/bin/python` (Python 3.13.7)
4. All Python features now use correct environment

**Multi-Worktree Setup:**
```json
// VS Code workspace file (optional)
{
  "folders": [
    {"path": "../FRANK"},                        // Main worktree
    {"path": "../new-worktree/background-tasks"} // Feature worktree
  ]
}
```
Each folder maintains its own interpreter selection from its local `.frank/`.

### Comparison: `make dev` vs `make env`

The Makefile provides two targets that serve different purposes:

```makefile
env: $(VIRTUALENV)/bin/python ## create the virtualenv
	@$(PYTHON) -m pip install -r requirements.txt

dev:$(VIRTUALENV)/bin/python  ## Install this for development
	@$(PYTHON) -m pip install --upgrade pip
	@$(PYTHON) -m pip install -e .
	@$(PYTHON) -m pip install ruff pytest coverage lark
```

**When to Use Each:**

| Command | Purpose | Use Case |
|---------|---------|----------|
| `make env` | **Production-like install** | CI/CD pipelines, testing frozen dependencies |
| `make dev` | **Development setup** | Local development, adding features, debugging |

**Should They Be Merged?**

**Recommendation: Keep them separate** for these reasons:

1. **Different Dependencies**:
   - `make env`: Installs from frozen `requirements.txt` (reproducible builds)
   - `make dev`: Installs latest dev tools + editable package (active development)

2. **Different Installation Modes**:
   - `make env`: Regular install (like production)
   - `make dev`: Editable install (`-e .`) - changes reflected immediately

3. **Different Workflows**:
   - `make env`: CI testing against locked versions
   - `make dev`: Local iteration with latest tools

**Best Practice Pattern:**
```bash
# Starting new feature development
git worktree add ../feature-branch feat/new-feature
cd ../feature-branch
make dev              # Development environment
venv                  # Activate
pytest                # Develop and test

# Before committing (verify against frozen deps)
make clean            # Remove .frank
make env              # Install from requirements.txt
make test             # Ensure tests pass with locked versions
```

### Complete Workflow Example

**Scenario: Starting work on a new feature in a worktree**

```bash
# 1. Create worktree from main repository
cd ~/wc/FRANK
git worktree add ../feature-worktree feat/token-refresh
cd ../feature-worktree

# 2. Setup development environment (one command)
make dev
# Output:
#   Creating virtualenv at .frank/
#   Upgrading pip...
#   Installing frank package in editable mode...
#   Installing development tools...
#   Setup complete!

# 3. Activate environment (one command)
venv
# Prompt changes to: (.frank) $

# 4. Verify setup
python --version          # Python 3.13.7
which python              # .../feature-worktree/.frank/bin/python
pip list                  # Shows frank, ruff, pytest, etc.

# 5. Work on feature
pytest tests/spikes/010_cognito/  # Tests run in isolation
ruff check .                      # Lint with worktree's tools

# 6. Switch to main worktree (different environment)
cd ~/wc/FRANK
venv                      # Activates main worktree's .frank
python --version          # Same Python, different packages
```

### Benefits Summary

The portable virtual environment strategy provides:

1. **Zero Configuration**: Works immediately after `git clone` + `make dev`
2. **Worktree Isolation**: Each branch/worktree has independent dependencies
3. **Fast Context Switching**: `cd` + `venv` = instant environment activation
4. **IDE Compatible**: VS Code, PyCharm, and other IDEs auto-detect `.frank/`
5. **CI/CD Friendly**: `make env` provides reproducible builds
6. **Beginner Friendly**: New developers run two commands: `make dev` + `venv`
7. **Cross-Platform**: Works on macOS, Linux, WSL2 without modification
8. **Version Explicit**: Python 3.13 consistently across all environments

This approach exemplifies FRANK's evolutionary design philosophy: **simple, explicit, and portable** - enabling rapid iteration without sacrificing reproducibility or team consistency.

A fundamental aspect of this evolutionary strategy is maintaining one single code library (`src/frank/`) that contains all business logic, data models, and core functionality. This unified library serves as the stable foundation that persists across all infrastructure stages. The library structure encompasses models for data structures, validation for business rules, processing for core threat intelligence logic, repositories for database abstraction interfaces, and serialization for YAML/JSON conversion utilities. This approach ensures the same `frank` library code runs unchanged from SQLite in Stage 1 to ScyllaDB in Stage 4. Infrastructure changes require only new repository implementations while business logic remains completely isolated from deployment concerns.

The benefits of this single library approach include consistency where the same behavior is guaranteed across all stages, testability where core logic is tested once and works everywhere, maintainability where bug fixes and features are applied universally, confidence where infrastructure changes cannot break business logic, and velocity where the team focuses on business value rather than infrastructure porting.

## Four-Stage Infrastructure Evolution

FRANK evolves through four distinct stages, each building upon the previous while introducing controlled complexity. Stage 1 uses SQLite database with FastAPI compute on a local laptop, serving as the foundation and proof of concept while focusing on core business logic and data models. Stage 2 transitions to MySQL or DynamoDB with FastAPI running on LocalStack and Docker, emphasizing AWS service patterns with learning focused on database abstraction and containerization.

Stage 3 moves to DynamoDB with ECS compute in AWS Cloud for cloud-native deployment, concentrating on containerized patterns and real AWS services. Stage 4 adopts ScyllaDB or MongoDB with FastAPI or Go on Kubernetes for a cloud-agnostic stack, prioritizing vendor independence and scalability.

The evolution prioritizes infrastructure learning before functional complexity. Stages 1 and 2 maintain a simple submission model while focusing on infrastructure learning. Stage 3 introduces complex submission models with stable cloud infrastructure. Stage 4 delivers the full feature set with production optimization. Working fallbacks are maintained at every stage where Stage 1 remains the development baseline, each stage can fall back to the previous working configuration, and there is no "point of no return" during evolution.

## Test-Driven Evolution Strategy

FRANK employs a comprehensive testing strategy with three distinct layers that create a safety net enabling confident evolution. Unit tests provide fast, isolated component testing of individual functions, classes, and modules with execution times under 100ms per test. These tests offer high coverage of business logic and enable fearless refactoring.

Integration tests deliver system confidence by testing component interactions and data flow, validating database operations, API endpoints, and external services while ensuring cross-boundary behavior and system coherence during evolution. Spike tests provide exploration confidence by validating new technologies and patterns before adoption. These proof-of-concept implementations reduce risk for architectural decisions while capturing knowledge for future reference.

Database abstraction allows the same business logic to work across different storage technologies, with comprehensive tests ensuring all implementations behave identically. This approach enables safe technology transitions while maintaining system reliability. New requirements trigger spike implementations for validation before integration. If a spike fails, the team tries a different approach. If a spike succeeds, they build the production implementation. This pattern provides risk reduction through early validation, knowledge acquisition before commitment, and clear go/no-go decision points.

## Functional MVP Evolution

Each functional evolution is captured as a Git version tag, enabling precise tracking of capability growth. Version 0.1.0 establishes minimal viable threat intelligence with basic submission models, simple confidence scoring, and organization identity management. Version 0.2.0 introduces enhanced observables with complex observable types covering network, file, and behavioral data, observable relationships and context, plus improved validation and error handling. Version 0.3.0 adds threat context including campaign attribution, threat actor profiling, and attack context with TTPs.

Version 0.4.0 implements sharing intelligence with multi-organization sharing levels, privacy controls and anonymization, and collaborative threat hunting features. Version 1.0.0 delivers the production intelligence platform with full STIX/TAXII compatibility, real-time threat feeds, and advanced analytics and reporting.

Each MVP represents a complete, deployable system with no "work in progress" states in version tags, ensuring immediate value delivery to users. Each version adds meaningful capability while maintaining backward compatibility where possible and providing clear migration paths between versions. The system employs abstract interfaces that enable evolution, where database abstractions define methods for saving submissions and querying data, with concrete implementations for SQLite, DynamoDB, and ScyllaDB. This approach enables technology switching without business logic changes, A/B testing of different implementations, and gradual migration capabilities.

## Key Success Factors

Success in evolutionary development requires maintaining working systems by never breaking the current working stage while building the next, always having a deployment-ready version available, and using feature flags for gradual rollouts. The approach demands keeping infrastructure complexity separate from functional complexity, database technology separate from business logic, and deployment environment separate from application code.

Comprehensive testing includes unit tests for component reliability, integration tests for system reliability, spike tests for technology validation, and performance tests for scalability validation. The strategy requires Git tags for functional milestones, Docker tags for deployment artifacts, database schema versions for data migration, and configuration versions for environment management.

Documentation is integral to evolutionary development, not an afterthought. FRANK employs a multi-layered documentation strategy that captures knowledge at different levels of abstraction and serves different audiences. Code-level documentation through comprehensive docstrings captures API contracts, provides concrete examples for developer onboarding, documents explicit error conditions to prevent debugging sessions, and makes breaking changes immediately obvious during evolution.

Spike documentation accompanies every spike test with detailed markdown files capturing the hypothesis, implementation approach, results including both successes and failures, and final decisions. This preserves decision rationale for future developers, prevents re-learning the same lessons, documents risk assessments, and provides blueprints for production implementation.

High-level design documentation in the docs folder organizes content into architecture, design, infrastructure, and decisions sections. These living documents are updated with each architectural evolution, maintain audience-specific technical depth, capture decision records for major choices, and provide cross-references between related concepts and implementations.

Architecture principles, while planned for future implementation, will document numbered principles that ensure consistency in team decisions, provide trade-off guidance with clear criteria for evaluating design alternatives, support onboarding by helping new team members understand system philosophy, and guide evolution while preventing architectural drift.

## Benefits of Evolutionary Approach

The evolutionary approach provides incremental learning that reduces big failure risks, working fallbacks that provide safety nets, and early validation that prevents costly mistakes. This strategy enables always deployable systems, incremental value delivery, and faster feedback cycles. Teams learn new technologies gradually, see architectural patterns emerge organically, and address technical debt continuously. The approach provides demonstrable progress at every stage, clear milestone achievements, and predictable delivery timelines.

## Conclusion

The FRANK evolutionary approach demonstrates that complex systems can be built incrementally without sacrificing quality or velocity. By separating infrastructure evolution from functional evolution, maintaining comprehensive test coverage, and ensuring working systems at every stage, teams can confidently navigate technological complexity while delivering continuous value.

This approach is particularly powerful when combined with AI-assisted development, where the safety net of tests and abstractions enables aggressive experimentation and rapid iteration while maintaining system reliability.