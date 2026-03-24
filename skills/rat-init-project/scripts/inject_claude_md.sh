#!/usr/bin/env bash
# inject_claude_md.sh — Inject/update RAT-managed section in project CLAUDE.md
#
# Usage: inject_claude_md.sh [project_root]
#
# Handles 3 cases:
#   1. CLAUDE.md doesn't exist       → create with RAT section
#   2. CLAUDE.md exists, no RAT tags → append RAT section
#   3. CLAUDE.md exists, RAT tags    → replace content between tags
#
# The RAT section is delimited by <!-- RAT:START --> / <!-- RAT:END --> tags.
# Content outside these tags is never modified.

set -euo pipefail

PROJECT_ROOT="${1:-.}"
CLAUDE_MD="$PROJECT_ROOT/CLAUDE.md"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$(cd "$SCRIPT_DIR/.." && pwd)/templates/claude-md-rat-section.md"

START_TAG="<!-- RAT:START -->"
END_TAG="<!-- RAT:END -->"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "ERROR: Template not found: $TEMPLATE" >&2
  exit 1
fi

if [[ ! -f "$CLAUDE_MD" ]]; then
  # Case 1: Create new file with RAT section
  {
    echo "$START_TAG"
    cat "$TEMPLATE"
    echo "$END_TAG"
  } > "$CLAUDE_MD"
  echo "RAT: Created $CLAUDE_MD with managed section"

elif grep -qF "$START_TAG" "$CLAUDE_MD"; then
  # Case 3: Replace existing RAT section
  awk -v start="$START_TAG" -v end="$END_TAG" -v tpl="$TEMPLATE" '
    $0 == start {
      print start
      while ((getline line < tpl) > 0) print line
      close(tpl)
      skip = 1
      next
    }
    $0 == end && skip {
      print end
      skip = 0
      next
    }
    !skip { print }
  ' "$CLAUDE_MD" > "${CLAUDE_MD}.rat-tmp"
  mv "${CLAUDE_MD}.rat-tmp" "$CLAUDE_MD"
  echo "RAT: Updated managed section in $CLAUDE_MD"

else
  # Case 2: Append RAT section to existing file
  {
    echo ""
    echo "$START_TAG"
    cat "$TEMPLATE"
    echo "$END_TAG"
  } >> "$CLAUDE_MD"
  echo "RAT: Appended managed section to $CLAUDE_MD"
fi
