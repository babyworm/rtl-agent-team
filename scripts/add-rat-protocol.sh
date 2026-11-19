#!/bin/sh
# Add the condensed RAT audit protocol block to all agent .md files.
# Idempotent: skips files that already contain the reference.
# Usage: sh scripts/add-rat-protocol.sh
#
# The block is inlined (NOT a path pointer) because agent prompts execute in the
# user's project CWD at plugin runtime, where plugin_docs/agent-lib/*.md does not exist.
# The dev source of truth for the full protocol is plugin_docs/agent-lib/audit-output-protocol.md.
#
# NOTE: plugin_docs/agent-lib/*.md templates must NOT carry this block — their content is
# stamped into agent files (sync_step0.sh, inject-worker-protocol.sh), and agents
# already carry the block at the top of the file. Stamping it into templates
# would duplicate it per agent.

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AGENTS_DIR="$REPO_ROOT/agents"

PROTOCOL_BLOCK_FILE=$(mktemp)
trap 'rm -f "$PROTOCOL_BLOCK_FILE"' EXIT
cat > "$PROTOCOL_BLOCK_FILE" <<'BLOCK_EOF'
RAT audit protocol (condensed; dev source: `plugin_docs/agent-lib/audit-output-protocol.md` — plugin-internal, do NOT Read it at runtime):
- Record `[RAT: CATEGORY | SOURCE] description` for decisions or observable results: DECISION, INSIGHT, DELEGATE, WARNING. Do not output internal reasoning.
- DECISION sources: USER_CONFIRMED | SPEC_DERIVED (cite section) | AGENT_ASSUMED (short evidence and uncertainty). Record significant decisions only.
- Prompt self-report: on spawn, save your received task description to `.rat/audit/{session_id}/prompts/{NNN}_{agent-name}.md` ({session_id} from `.rat/audit/session-id.txt`); skip silently if the audit dir is absent.
- Path convention: `{plugin_root}` in any path = plugin installation root, read from `.rat/state/spawn-context.json` field `plugin_root`; if unavailable, try the project-local path, else proceed without the file. Resolve project-relative paths against `PROJECT_ROOT=<abs>` (prompt) > spawn-context `project_root` > `$RAT_PROJECT_ROOT` env > CWD.
BLOCK_EOF

UPDATED=0
SKIPPED=0
TOTAL=0

# Insert a blank line followed by the protocol block after line $1 of file $2.
insert_protocol_after_line() {
  _IPAL_LINE="$1"
  _IPAL_FILE="$2"
  _IPAL_TMP=$(mktemp)
  {
    head -n "$_IPAL_LINE" "$_IPAL_FILE"
    echo ""
    cat "$PROTOCOL_BLOCK_FILE"
    tail -n +"$((_IPAL_LINE + 1))" "$_IPAL_FILE"
  } > "$_IPAL_TMP" && mv "$_IPAL_TMP" "$_IPAL_FILE"
}

for agent_file in "$AGENTS_DIR"/*.md; do
  [ -f "$agent_file" ] || continue
  TOTAL=$((TOTAL + 1))

  # Skip if already contains the reference
  if grep -qF "audit-output-protocol.md" "$agent_file" 2>/dev/null; then
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  # Find the end of YAML frontmatter (second ---)
  # Insert the protocol block after the frontmatter
  FRONTMATTER_END=$(awk '/^---$/{n++; if(n==2){print NR; exit}}' "$agent_file")

  if [ -z "$FRONTMATTER_END" ]; then
    echo "WARN: No frontmatter end found in $(basename "$agent_file"), skipping"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  insert_protocol_after_line "$FRONTMATTER_END" "$agent_file"

  UPDATED=$((UPDATED + 1))
done

echo "RAT protocol block: ${UPDATED} updated, ${SKIPPED} skipped, ${TOTAL} total"
