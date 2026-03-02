#!/bin/bash
# SessionStart hook: RTL project initialization advisor
# Checks if RTL project directories exist and advises setup if not.
# Only fires when in a git repository without rtl/ or docs/ directories.

if [ ! -d "rtl" ] && [ ! -d "docs" ] && { [ -d ".git" ] || [ -f ".git/HEAD" ]; }; then
  echo "RTL project directories not detected. Run /rtl-agent-team:rtl-setup to initialize project structure."
fi
