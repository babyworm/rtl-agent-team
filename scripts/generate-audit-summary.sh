#!/bin/sh
# generate-audit-summary.sh — Generate markdown summary from audit trace.
# Usage:
#   sh scripts/generate-audit-summary.sh                # Current session
#   sh scripts/generate-audit-summary.sh SESSION_ID     # Specific session

set -e

CWD="${PWD}"
AUDIT_DIR="$CWD/.rtl-agent-team/audit"

SESSION_ID="${1:-}"
if [ -z "$SESSION_ID" ]; then
  SESSION_ID_FILE="$AUDIT_DIR/session-id.txt"
  if [ -f "$SESSION_ID_FILE" ]; then
    SESSION_ID=$(cat "$SESSION_ID_FILE")
  else
    echo "No active session. Provide session ID as argument."
    exit 1
  fi
fi

TRACE_FILE="$AUDIT_DIR/$SESSION_ID/trace.jsonl"
SUMMARY_FILE="$AUDIT_DIR/$SESSION_ID/summary.md"
PROMPTS_DIR="$AUDIT_DIR/$SESSION_ID/prompts"

if [ ! -f "$TRACE_FILE" ]; then
  echo "No trace file: $TRACE_FILE"
  exit 1
fi

TOTAL=$(wc -l < "$TRACE_FILE" | tr -d ' ')

# Generate summary
cat > "$SUMMARY_FILE" << HEADER
# Audit Summary: Session $SESSION_ID

Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date)

## Timeline ($TOTAL events)

HEADER

# Timeline entries
while IFS= read -r line; do
  [ -z "$line" ] && continue

  if command -v jq >/dev/null 2>&1; then
    TS=$(printf '%s' "$line" | jq -r '.ts // ""' 2>/dev/null)
    EVENT=$(printf '%s' "$line" | jq -r '.event // ""' 2>/dev/null)
    AGENT=$(printf '%s' "$line" | jq -r '.agent // ""' 2>/dev/null)
    DETAIL=$(printf '%s' "$line" | jq -r '.detail // ""' 2>/dev/null)
    STATUS=$(printf '%s' "$line" | jq -r '.status // ""' 2>/dev/null)
    PHASE=$(printf '%s' "$line" | jq -r '.phase // ""' 2>/dev/null)
    SOURCE=$(printf '%s' "$line" | jq -r '.source // ""' 2>/dev/null)
  else
    TS=$(printf '%s' "$line" | sed -n 's/.*"ts"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    EVENT=$(printf '%s' "$line" | sed -n 's/.*"event"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    AGENT=$(printf '%s' "$line" | sed -n 's/.*"agent"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    DETAIL=$(printf '%s' "$line" | sed -n 's/.*"detail"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    STATUS=$(printf '%s' "$line" | sed -n 's/.*"status"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    PHASE=$(printf '%s' "$line" | sed -n 's/.*"phase"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p')
    SOURCE=$(printf '%s' "$line" | sed -n 's/.*"source"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
  fi

  SHORT_TS=$(printf '%s' "$TS" | sed 's/.*T\([0-9:]*\).*/\1/' | sed 's/Z$//')

  PHASE_STR=""
  [ -n "$PHASE" ] && PHASE_STR=" (Phase $PHASE)"

  STATUS_STR=""
  [ -n "$STATUS" ] && STATUS_STR=" [$STATUS]"

  SOURCE_STR=""
  [ -n "$SOURCE" ] && SOURCE_STR=" {$SOURCE}"

  printf -- "- %s [%s] %s%s%s — %s%s\n" "$SHORT_TS" "$EVENT" "$AGENT" "$PHASE_STR" "$STATUS_STR" "$DETAIL" "$SOURCE_STR"
done < "$TRACE_FILE" >> "$SUMMARY_FILE"

# Statistics section
cat >> "$SUMMARY_FILE" << STATS

## Statistics

| Metric | Count |
|--------|-------|
| Total events | $TOTAL |
| Agent spawns | $(grep -c '"spawn_start"' "$TRACE_FILE" || true) |
| Skill invocations | $(grep -c '"skill_invoke"' "$TRACE_FILE" || true) |
| Artifacts written | $(grep -c '"artifact_write"' "$TRACE_FILE" || true) |
| Decisions | $(grep -c '"decision"' "$TRACE_FILE" || true) |

STATS

# Decision breakdown
DECISION_COUNT=$(grep -c '"decision"' "$TRACE_FILE" || true)
if [ "$DECISION_COUNT" -gt 0 ]; then
  cat >> "$SUMMARY_FILE" << DECISIONS
## Decision Sources

| Source | Count |
|--------|-------|
| USER_CONFIRMED | $(grep -c '"USER_CONFIRMED"' "$TRACE_FILE" || true) |
| SPEC_DERIVED | $(grep -c '"SPEC_DERIVED"' "$TRACE_FILE" || true) |
| AGENT_ASSUMED | $(grep -c '"AGENT_ASSUMED"' "$TRACE_FILE" || true) |

DECISIONS
fi

# Prompts section
if [ -d "$PROMPTS_DIR" ]; then
  PROMPT_COUNT=$(find "$PROMPTS_DIR" -name '*.md' 2>/dev/null | wc -l | tr -d ' ')
  if [ "$PROMPT_COUNT" -gt 0 ]; then
    printf "\n## Saved Prompts (%s)\n\n" "$PROMPT_COUNT" >> "$SUMMARY_FILE"
    for f in "$PROMPTS_DIR"/*.md; do
      [ -f "$f" ] || continue
      printf -- "- \`%s\`\n" "$(basename "$f")" >> "$SUMMARY_FILE"
    done
  fi
fi

echo "Summary written to: $SUMMARY_FILE"
