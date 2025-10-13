#!/bin/bash
# FRANK - Install Git Worktree Aliases
#
# This script installs git worktree aliases to your shell configuration.
# It detects your shell (bash/zsh) and adds aliases to the appropriate config file.
#
# Usage:
#   ./install-worktree-aliases.sh
#
# Copyright (c) 2025 Schuberg Philis B.V.
# SPDX-License-Identifier: Apache-2.0

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Detect shell
SHELL_NAME=$(basename "$SHELL")
if [ "$SHELL_NAME" = "bash" ]; then
    CONFIG_FILE="$HOME/.bashrc"
elif [ "$SHELL_NAME" = "zsh" ]; then
    CONFIG_FILE="$HOME/.zshrc"
else
    echo -e "${RED}Unsupported shell: $SHELL_NAME${NC}"
    echo "Please manually add aliases to your shell config from:"
    echo "  docs/GIT_WORKTREE_ALIASES.md"
    exit 1
fi

echo -e "${BLUE}FRANK Git Worktree Aliases Installer${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""
echo "Shell detected: $SHELL_NAME"
echo "Config file: $CONFIG_FILE"
echo ""

# Check if already installed
if grep -q "FRANK Git Worktree Aliases" "$CONFIG_FILE" 2>/dev/null; then
    echo -e "${YELLOW}⚠️  Aliases already installed in $CONFIG_FILE${NC}"
    read -p "Reinstall? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}❌ Installation cancelled${NC}"
        exit 0
    fi

    # Remove old installation
    echo "Removing old aliases..."
    sed -i.bak '/# FRANK Git Worktree Aliases/,/# End FRANK Git Worktree Aliases/d' "$CONFIG_FILE"
fi

# Get aliases from docs
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCS_DIR="$(dirname "$SCRIPT_DIR")/docs"
ALIASES_FILE="$DOCS_DIR/GIT_WORKTREE_ALIASES.md"

if [ ! -f "$ALIASES_FILE" ]; then
    echo -e "${RED}❌ Aliases file not found: $ALIASES_FILE${NC}"
    exit 1
fi

# Extract bash code block from markdown
echo "Extracting aliases..."
ALIASES=$(sed -n '/^```bash/,/^```$/p' "$ALIASES_FILE" | grep -A 1000 "# FRANK Git Worktree Aliases" | head -n -1 | tail -n +2)

if [ -z "$ALIASES" ]; then
    echo -e "${RED}❌ Could not extract aliases from documentation${NC}"
    exit 1
fi

# Backup config file
echo "Backing up $CONFIG_FILE to ${CONFIG_FILE}.backup"
cp "$CONFIG_FILE" "${CONFIG_FILE}.backup"

# Append aliases
echo "" >> "$CONFIG_FILE"
echo "$ALIASES" >> "$CONFIG_FILE"

echo ""
echo -e "${GREEN}✅ Aliases installed successfully!${NC}"
echo ""
echo "Available commands:"
echo -e "  ${GREEN}gw${NC}  <branch>  - Create new worktree"
echo -e "  ${GREEN}gwc${NC} <branch>  - Create worktree + auto-setup (make dev)"
echo -e "  ${GREEN}wm${NC}  <name>    - Move to worktree"
echo -e "  ${GREEN}lw${NC}            - List all worktrees"
echo -e "  ${GREEN}bw${NC}            - Back to main worktree"
echo -e "  ${GREEN}rw${NC}  <name>    - Remove worktree"
echo -e "  ${GREEN}pw${NC}            - Print current worktree info"
echo -e "  ${GREEN}cw${NC}            - Cleanup removed worktrees"
echo ""
echo "To activate now, run:"
echo -e "  ${BLUE}source $CONFIG_FILE${NC}"
echo ""
echo "Or start a new terminal session."
echo ""
echo -e "${YELLOW}Configuration:${NC}"
echo "  Worktrees will be created in: ../worktree/<branch-name>"
echo "  To change, set: export WORKTREE_BASE=\"/your/path\""
echo ""
