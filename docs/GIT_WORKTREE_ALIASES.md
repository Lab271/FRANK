# Git Worktree Bash Aliases for FRANK

## Quick Reference

```bash
gw <branch>         # Create new worktree in ../worktree/<branch>
gwc <branch>        # Create worktree AND auto-setup (.frank + venv)
wm <branch>         # Move to worktree
lw                  # List all worktrees
bw                  # Back to main worktree
rw <branch>         # Remove worktree
pw                  # Print current worktree path
cw                  # Cleanup removed worktrees
```

## Installation

Add these aliases to your `~/.bashrc` or `~/.zshrc`:

```bash
# ============================================================================
# FRANK Git Worktree Aliases
# ============================================================================

# WORKTREE_BASE: Base directory for all worktrees (relative to repo root)
export WORKTREE_BASE="../worktree"

# Helper function to get main worktree path
_get_main_worktree() {
    git worktree list | head -1 | awk '{print $1}'
}

# Helper function to get worktree root (handles being in subdirectories)
_get_worktree_root() {
    git rev-parse --show-toplevel 2>/dev/null
}

# gw: Git Worktree - Create new worktree
# Usage: gw feat/authentication
#        gw bugfix/issue-123
alias gw='_git_worktree_create'
_git_worktree_create() {
    if [ -z "$1" ]; then
        echo "Usage: gw <branch-name>"
        echo "Example: gw feat/authentication"
        return 1
    fi

    local branch_name="$1"
    local worktree_name=$(echo "$branch_name" | sed 's/\//-/g')  # Replace / with -
    local worktree_path="${WORKTREE_BASE}/${worktree_name}"

    echo "Creating worktree: $worktree_path"
    echo "Branch: $branch_name"

    # Create worktree
    if git worktree add "$worktree_path" "$branch_name"; then
        echo "✅ Worktree created successfully!"
        echo "To move there: wm $worktree_name"
        echo "To setup:      cd $worktree_path && make dev && venv"
    else
        echo "❌ Failed to create worktree"
        return 1
    fi
}

# gwc: Git Worktree Create and setup - Create worktree + auto-setup environment
# Usage: gwc feat/authentication
alias gwc='_git_worktree_create_and_setup'
_git_worktree_create_and_setup() {
    if [ -z "$1" ]; then
        echo "Usage: gwc <branch-name>"
        echo "Example: gwc feat/authentication"
        echo "This creates the worktree AND runs 'make dev && venv'"
        return 1
    fi

    local branch_name="$1"
    local worktree_name=$(echo "$branch_name" | sed 's/\//-/g')
    local worktree_path="${WORKTREE_BASE}/${worktree_name}"

    echo "🌳 Creating worktree: $worktree_path"
    echo "📋 Branch: $branch_name"

    # Create worktree
    if git worktree add "$worktree_path" "$branch_name"; then
        echo "✅ Worktree created!"

        # Move to worktree
        cd "$worktree_path" || return 1
        echo "📂 Changed to: $(pwd)"

        # Setup environment
        echo "🔧 Running 'make dev'..."
        if make dev; then
            echo "✅ Environment setup complete!"
            echo ""
            echo "🎯 Ready to work! Run 'venv' to activate environment"
            echo ""
            # Try to activate (may not work in some shells, but worth trying)
            source .*/bin/activate 2>/dev/null && echo "✅ Virtual environment activated!" || echo "Run: venv"
        else
            echo "❌ 'make dev' failed - please check errors above"
            return 1
        fi
    else
        echo "❌ Failed to create worktree"
        return 1
    fi
}

# wm: Worktree Move - Move to a worktree
# Usage: wm feat-authentication
#        wm bugfix-issue-123
alias wm='_worktree_move'
_worktree_move() {
    if [ -z "$1" ]; then
        echo "Usage: wm <worktree-name>"
        echo "Available worktrees:"
        lw
        return 1
    fi

    local worktree_name="$1"
    local worktree_path="${WORKTREE_BASE}/${worktree_name}"

    if [ -d "$worktree_path" ]; then
        cd "$worktree_path" || return 1
        echo "📂 Moved to: $(pwd)"
        echo "🌳 Branch: $(git branch --show-current)"

        # Check if .frank exists
        if [ -d ".frank" ]; then
            echo "✅ Virtual environment exists (.frank/)"
            echo "Run: venv"
        else
            echo "⚠️  No virtual environment found - run: make dev"
        fi
    else
        echo "❌ Worktree not found: $worktree_path"
        echo "Available worktrees:"
        lw
        return 1
    fi
}

# lw: List Worktrees - Show all worktrees with status
alias lw='_list_worktrees'
_list_worktrees() {
    echo "Git Worktrees:"
    echo "=============="

    git worktree list | while IFS= read -r line; do
        local path=$(echo "$line" | awk '{print $1}')
        local branch=$(echo "$line" | awk '{print $3}' | tr -d '[]')
        local status=$(echo "$line" | cut -d' ' -f4-)

        # Check if this is the current worktree
        local current_path=$(git rev-parse --show-toplevel 2>/dev/null)
        local marker=""
        if [ "$path" = "$current_path" ]; then
            marker="👉 "
        fi

        # Check if .frank exists in this worktree
        local env_status=""
        if [ -d "$path/.frank" ]; then
            env_status="[✅ .frank]"
        else
            env_status="[❌ no env]"
        fi

        echo "${marker}${path}"
        echo "   Branch: ${branch} ${env_status} ${status}"
    done

    echo ""
    echo "Use: wm <name> to move to worktree"
    echo "Use: bw to return to main"
}

# bw: Back to main Worktree
alias bw='_back_to_main'
_back_to_main() {
    local main_path=$(_get_main_worktree)

    if [ -z "$main_path" ]; then
        echo "❌ Could not find main worktree"
        return 1
    fi

    cd "$main_path" || return 1
    echo "📂 Back to main: $(pwd)"
    echo "🌳 Branch: $(git branch --show-current)"

    # Check if .frank exists
    if [ -d ".frank" ]; then
        echo "✅ Virtual environment exists (.frank/)"
        echo "Run: venv"
    else
        echo "⚠️  No virtual environment found - run: make dev"
    fi
}

# rw: Remove Worktree
# Usage: rw feat-authentication
alias rw='_remove_worktree'
_remove_worktree() {
    if [ -z "$1" ]; then
        echo "Usage: rw <worktree-name>"
        echo "Available worktrees:"
        lw
        return 1
    fi

    local worktree_name="$1"
    local worktree_path="${WORKTREE_BASE}/${worktree_name}"

    # Verify worktree exists
    if ! git worktree list | grep -q "$worktree_path"; then
        echo "❌ Worktree not found: $worktree_path"
        echo "Available worktrees:"
        lw
        return 1
    fi

    # Confirm removal
    echo "⚠️  About to remove worktree:"
    echo "   Path: $worktree_path"
    echo "   Branch: $(git worktree list | grep "$worktree_path" | awk '{print $3}' | tr -d '[]')"
    echo ""
    read -p "Continue? [y/N] " -n 1 -r
    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then
        if git worktree remove "$worktree_path"; then
            echo "✅ Worktree removed: $worktree_path"
        else
            echo "❌ Failed to remove worktree"
            echo "Try: git worktree remove --force $worktree_path"
            return 1
        fi
    else
        echo "❌ Cancelled"
    fi
}

# pw: Print current Worktree path
alias pw='_print_worktree'
_print_worktree() {
    local worktree_path=$(_get_worktree_root)

    if [ -z "$worktree_path" ]; then
        echo "❌ Not in a git repository"
        return 1
    fi

    local branch=$(git branch --show-current)
    local is_main=$(git worktree list | head -1 | grep -q "$worktree_path" && echo "yes" || echo "no")

    echo "Current Worktree:"
    echo "================="
    echo "Path:   $worktree_path"
    echo "Branch: $branch"
    echo "Main:   $is_main"

    if [ -d "$worktree_path/.frank" ]; then
        echo "Env:    ✅ .frank exists"
        if [ -n "$VIRTUAL_ENV" ]; then
            echo "Active: ✅ $(basename $VIRTUAL_ENV)"
        else
            echo "Active: ❌ (run: venv)"
        fi
    else
        echo "Env:    ❌ No .frank (run: make dev)"
    fi
}

# cw: Cleanup removed Worktrees
alias cw='_cleanup_worktrees'
_cleanup_worktrees() {
    echo "Pruning removed worktrees..."
    git worktree prune -v
    echo "✅ Cleanup complete"
}

# Combined alias for quick workflow
alias gww='_git_worktree_workflow'
_git_worktree_workflow() {
    echo "Git Worktree Quick Workflow"
    echo "============================"
    echo "1. gw <branch>   - Create worktree"
    echo "2. gwc <branch>  - Create + setup (make dev + venv)"
    echo "3. wm <name>     - Move to worktree"
    echo "4. lw            - List all worktrees"
    echo "5. bw            - Back to main"
    echo "6. rw <name>     - Remove worktree"
    echo "7. pw            - Print current worktree info"
    echo "8. cw            - Cleanup pruned worktrees"
    echo ""
    echo "Current worktrees:"
    lw
}

# ============================================================================
# End FRANK Git Worktree Aliases
# ============================================================================
```

After adding, reload your shell:

```bash
source ~/.bashrc  # or source ~/.zshrc
```

## Usage Examples

### Creating a New Feature Worktree

**Quick Setup (Recommended):**
```bash
# Create worktree + auto-setup environment
gwc feat/token-refresh
# Output:
#   🌳 Creating worktree: ../worktree/feat-token-refresh
#   📋 Branch: feat/token-refresh
#   ✅ Worktree created!
#   📂 Changed to: /Users/you/worktree/feat-token-refresh
#   🔧 Running 'make dev'...
#   ✅ Environment setup complete!
#   ✅ Virtual environment activated!

# You're immediately ready to work!
pytest
```

**Manual Setup:**
```bash
# Create worktree only
gw feat/authentication
# Output:
#   Creating worktree: ../worktree/feat-authentication
#   Branch: feat/authentication
#   ✅ Worktree created successfully!
#   To move there: wm feat-authentication
#   To setup:      cd ../worktree/feat-authentication && make dev && venv

# Move to worktree
wm feat-authentication
# Output:
#   📂 Moved to: /Users/you/worktree/feat-authentication
#   🌳 Branch: feat-authentication
#   ⚠️  No virtual environment found - run: make dev

# Setup environment
make dev && venv
```

### Working with Multiple Worktrees

```bash
# List all worktrees
lw
# Output:
#   Git Worktrees:
#   ==============
#   👉 /Users/you/wc/FRANK
#      Branch: main [✅ .frank]
#   /Users/you/worktree/feat-authentication
#      Branch: feat-authentication [✅ .frank]
#   /Users/you/worktree/bugfix-issue-123
#      Branch: bugfix-issue-123 [❌ no env]

# Move to another worktree
wm feat-authentication
# Work on feature...
pytest tests/

# Back to main
bw
# Output:
#   📂 Back to main: /Users/you/wc/FRANK
#   🌳 Branch: main
#   ✅ Virtual environment exists (.frank/)
#   Run: venv
```

### Checking Current Status

```bash
# Print current worktree info
pw
# Output:
#   Current Worktree:
#   =================
#   Path:   /Users/you/worktree/feat-authentication
#   Branch: feat-authentication
#   Main:   no
#   Env:    ✅ .frank exists
#   Active: ✅ .frank
```

### Cleaning Up

```bash
# Remove a worktree
rw feat-authentication
# Output:
#   ⚠️  About to remove worktree:
#      Path: ../worktree/feat-authentication
#      Branch: feat-authentication
#
#   Continue? [y/N] y
#   ✅ Worktree removed: ../worktree/feat-authentication

# Cleanup pruned worktrees
cw
# Output:
#   Pruning removed worktrees...
#   ✅ Cleanup complete
```

## Complete Workflow Example

### Scenario: Developing a New Feature

```bash
# 1. Create worktree with auto-setup
gwc feat/user-authentication
# Everything is set up automatically!

# 2. Check status
pw
# Confirms you're in the right place with .frank active

# 3. Work on feature
pytest tests/auth/
ruff check src/
git commit -am "Add user authentication"

# 4. Switch to main to check something
bw
venv
git log

# 5. Back to feature
wm feat-user-authentication
venv

# 6. Continue working...
pytest
git push

# 7. Feature complete - remove worktree
bw  # Go back to main first
rw feat-user-authentication
# Confirm removal
```

## Alias Customization

### Change Worktree Base Directory

By default, worktrees are created in `../worktree/<branch-name>`. To change this:

```bash
# In your ~/.bashrc or ~/.zshrc
export WORKTREE_BASE="$HOME/worktrees"  # All worktrees in ~/worktrees/
# or
export WORKTREE_BASE="../wt"            # Shorter path
```

### Add Custom Aliases

```bash
# Quick navigation (add to ~/.bashrc)
alias wl='lw'                              # Shorter list
alias wg='gwc'                             # Shorter create+setup
alias wd='rw'                              # Shorter delete (remove)

# Integration with FRANK
alias wt='gwc && pytest'                   # Create + test
alias wc='bw && git checkout'              # Back + checkout branch
```

## Tips and Tricks

### 1. Branch Name to Worktree Name Conversion

The aliases automatically convert branch names to filesystem-safe names:

```bash
gw feat/authentication        # Creates: ../worktree/feat-authentication
gw bugfix/issue-123          # Creates: ../worktree/bugfix-issue-123
gw release/v1.0.0            # Creates: ../worktree/release-v1.0.0
```

### 2. Tab Completion (Bash)

Add tab completion for worktree names:

```bash
# In ~/.bashrc
_complete_worktrees() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local worktrees=$(git worktree list | tail -n +2 | awk '{print $1}' | xargs -n1 basename)
    COMPREPLY=($(compgen -W "$worktrees" -- "$cur"))
}

complete -F _complete_worktrees wm
complete -F _complete_worktrees rw
```

### 3. Visual Indicator in Prompt

Show current worktree in your prompt:

```bash
# Add to ~/.bashrc
parse_git_worktree() {
    local worktree_root=$(git rev-parse --show-toplevel 2>/dev/null)
    if [ -n "$worktree_root" ]; then
        local main_worktree=$(git worktree list | head -1 | awk '{print $1}')
        if [ "$worktree_root" != "$main_worktree" ]; then
            echo " [wt:$(basename $worktree_root)]"
        fi
    fi
}

# Add to PS1
PS1='${debian_chroot:+($debian_chroot)}\u@\h:\w$(parse_git_worktree)\$ '
```

Result:
```bash
user@host:~/worktree/feat-auth [wt:feat-auth]$
```

### 4. Combined with FRANK Makefile

```bash
# Create worktree + setup + run tests
gwc feat/new-api && pytest tests/api/

# Create worktree + setup + start server
gwc feat/ui && python -m frank.server

# Quick iteration workflow
alias frankdev='gwc $1 && venv && pytest && ruff check .'
```

## Troubleshooting

### Alias not found

```bash
# Check if aliases are loaded
type gw
# Should show: gw is a function

# Reload shell configuration
source ~/.bashrc  # or source ~/.zshrc
```

### Worktree creation fails

```bash
# Check if branch exists
git branch -a | grep <branch-name>

# Create branch first if needed
git branch feat/new-feature
gw feat/new-feature
```

### `make dev` fails in `gwc`

```bash
# Check if Makefile exists in worktree
wm <worktree-name>
ls Makefile

# If missing, check git worktree setup
git worktree list
```

### Cleanup issues

```bash
# Force remove worktree
git worktree remove --force <path>

# Prune all removed worktrees
cw  # or: git worktree prune -v
```

## Integration with VS Code

### Open Worktree in VS Code

```bash
# Add to ~/.bashrc
alias wcode='_worktree_vscode'
_worktree_vscode() {
    if [ -z "$1" ]; then
        code .
    else
        local worktree_path="${WORKTREE_BASE}/$1"
        code "$worktree_path"
    fi
}

# Usage:
wcode feat-authentication  # Opens worktree in VS Code
```

### Multi-Worktree Workspace

```bash
# Create VS Code workspace with all worktrees
alias wworkspace='_create_workspace'
_create_workspace() {
    local workspace_file="frank-worktrees.code-workspace"
    echo '{' > "$workspace_file"
    echo '  "folders": [' >> "$workspace_file"

    git worktree list | while IFS= read -r line; do
        local path=$(echo "$line" | awk '{print $1}')
        echo "    {\"path\": \"$path\"}," >> "$workspace_file"
    done

    echo '  ]' >> "$workspace_file"
    echo '}' >> "$workspace_file"

    code "$workspace_file"
}
```

## Philosophy

These aliases embody FRANK's **portable, rapid-iteration** philosophy:

1. **Simple**: Short, memorable commands (`gw`, `wm`, `bw`)
2. **Explicit**: Clear what each command does
3. **Portable**: Works across projects (customize `WORKTREE_BASE`)
4. **Fast**: Context switching is instant
5. **Integrated**: Works seamlessly with `.frank` + `venv` pattern

The combination of:
- Git worktrees (isolated branches)
- `.frank` virtualenvs (isolated dependencies)
- These aliases (rapid navigation)
- `venv` alias (instant activation)

Creates a **zero-friction development environment** where switching contexts takes seconds, not minutes.

## References

- [FRANK Portable Dev Environment](PORTABLE_DEV_ENVIRONMENT.md)
- [FRANK Evolutionary Design](evolutionary_design.md)
- [Git Worktree Documentation](https://git-scm.com/docs/git-worktree)
