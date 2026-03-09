#!/bin/sh
# SessionStart hook: RTL project initialization advisor
# Checks if RTL project directories exist and advises setup if not.
# Only fires when in a git repository without rtl/ or docs/ directories.

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

if [ ! -d "$CWD/rtl" ] && [ ! -d "$CWD/docs" ] && { [ -d "$CWD/.git" ] || [ -f "$CWD/.git" ]; }; then
  printf '{"hookSpecificOutput":{"additionalContext":"RTL project directories not detected. Run /rtl-agent-team:rat-setup to initialize project structure."}}'
  exit 0
fi

# Happy path — no output needed for SessionStart hooks
exit 0
