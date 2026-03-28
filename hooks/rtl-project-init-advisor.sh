#!/bin/sh
# SessionStart hook: RTL project initialization advisor
# Checks if RTL project directories exist and advises setup if not.
# Only fires when in a git repository without rtl/ or docs/ directories.

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

if [ ! -d "$CWD/rtl" ] && [ ! -d "$CWD/docs" ] && [ ! -d "$CWD/.rat" ] && [ ! -d "$CWD/.rtl-agent-team" ] && { [ -d "$CWD/.git" ] || [ -f "$CWD/.git" ]; }; then
  printf '{"hookSpecificOutput":{"additionalContext":"RTL project directories not detected. Run /rtl-agent-team:rat-init-project to initialize project structure."}}'
  exit 0
fi

# Happy path — minimal output to avoid "startup hook error"
printf '{}'
exit 0
