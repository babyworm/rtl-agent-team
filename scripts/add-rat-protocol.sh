#!/bin/sh
# Add RAT audit protocol reference to all agent .md files.
# Idempotent: skips files that already contain the reference.
# Usage: sh scripts/add-rat-protocol.sh

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS_DIR="$REPO_ROOT/agents"
PROTOCOL_REF="Follow the structured output annotation protocol defined in \`agents/lib/audit-output-protocol.md\`."

UPDATED=0
SKIPPED=0
TOTAL=0

for agent_file in "$AGENTS_DIR"/*.md; do
  [ -f "$agent_file" ] || continue
  TOTAL=$((TOTAL + 1))

  # Skip if already contains the reference
  if grep -qF "audit-output-protocol.md" "$agent_file" 2>/dev/null; then
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  # Find the end of YAML frontmatter (second ---)
  # Insert the protocol reference line after the frontmatter
  FRONTMATTER_END=$(awk '/^---$/{n++; if(n==2){print NR; exit}}' "$agent_file")

  if [ -z "$FRONTMATTER_END" ]; then
    echo "WARN: No frontmatter end found in $(basename "$agent_file"), skipping"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  # Insert blank line + protocol reference after frontmatter
  sed -i "${FRONTMATTER_END}a\\
\\
${PROTOCOL_REF}" "$agent_file"

  UPDATED=$((UPDATED + 1))
done

# Also handle agents in lib/ subdirectory (but skip non-agent files)
for lib_file in "$AGENTS_DIR"/lib/*.md; do
  [ -f "$lib_file" ] || continue
  BASENAME=$(basename "$lib_file")

  # Skip the protocol file itself and non-agent files
  case "$BASENAME" in
    audit-output-protocol.md) continue ;;
  esac

  TOTAL=$((TOTAL + 1))

  if grep -qF "audit-output-protocol.md" "$lib_file" 2>/dev/null; then
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  # lib files may not have frontmatter — check first
  if head -n 1 "$lib_file" | grep -q '^---$'; then
    FRONTMATTER_END=$(awk '/^---$/{n++; if(n==2){print NR; exit}}' "$lib_file")
    if [ -n "$FRONTMATTER_END" ]; then
      sed -i "${FRONTMATTER_END}a\\
\\
${PROTOCOL_REF}" "$lib_file"
      UPDATED=$((UPDATED + 1))
      continue
    fi
  fi

  # No frontmatter — prepend after first heading
  FIRST_HEADING=$(grep -n '^#' "$lib_file" | head -n 1 | cut -d: -f1)
  if [ -n "$FIRST_HEADING" ]; then
    sed -i "${FIRST_HEADING}a\\
\\
${PROTOCOL_REF}" "$lib_file"
    UPDATED=$((UPDATED + 1))
  else
    SKIPPED=$((SKIPPED + 1))
  fi
done

echo "RAT protocol reference: ${UPDATED} updated, ${SKIPPED} skipped, ${TOTAL} total"
