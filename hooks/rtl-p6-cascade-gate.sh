#!/bin/sh
# RTL Phase 6 Cascade Gate: Stop hook
# Blocks session exit when RTL files were modified after Phase 6 review was completed.
#
# Stale marker:   .rtl-agent-team/state/phase6-stale       (set by rtl-edit-tracker.sh)
# Cascade done:   .rtl-agent-team/state/phase6-cascade-done (set manually after updating docs)
#
# Flow:
#   - phase6-stale absent            → allow exit (Phase 6 was never completed or no RTL edits)
#   - phase6-cascade-done present    → clean up both markers, allow exit
#   - otherwise                      → BLOCK exit, instruct to re-run lint + update review docs

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/team-gate-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"

STATE_DIR="$CWD/.rtl-agent-team/state"
STALE_MARKER="$STATE_DIR/phase6-stale"
CASCADE_DONE="$STATE_DIR/phase6-cascade-done"

if teamu_should_skip_gate "$STATE_DIR"; then
  printf '{"continue":true}'
  exit 0
fi

# If no stale marker, Phase 6 was not affected — allow exit
if [ ! -f "$STALE_MARKER" ]; then
  printf '{"continue":true}'
  exit 0
fi

# If cascade work is confirmed done, verify documents were actually updated (G5: mtime check)
if [ -f "$CASCADE_DONE" ]; then
  REVIEW_DIR="$CWD/reviews/phase-6-review"
  STALE_MTIME=$(stat -c %Y "$STALE_MARKER" 2>/dev/null || stat -f %m "$STALE_MARKER" 2>/dev/null || echo 0)
  DOCS_STALE=false
  DOCS_FOUND=false
  for doc in "$REVIEW_DIR/design-note.md" "$REVIEW_DIR/code-review.md"; do
    if [ -f "$doc" ]; then
      DOCS_FOUND=true
      DOC_MTIME=$(stat -c %Y "$doc" 2>/dev/null || stat -f %m "$doc" 2>/dev/null || echo 0)
      if [ "$DOC_MTIME" -le "$STALE_MTIME" ] 2>/dev/null; then
        DOCS_STALE=true
      fi
    fi
  done

  # phase6-stale is only set when review docs exist (rtl-edit-tracker.sh guard).
  # If docs are now absent, they were deleted — treat as stale.
  if [ "$DOCS_FOUND" = "false" ]; then
    DOCS_STALE=true
  fi

  if [ "$DOCS_STALE" = "true" ]; then
    printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"[Phase 6 Cascade Gate BLOCKED] cascade-done marker present but design documents (design-note.md, code-review.md) were not found or not updated after RTL change. Document mtime must be newer than the stale marker. Update documents to reflect RTL modifications, then touch .rtl-agent-team/state/phase6-cascade-done again."}}'
    exit 0
  fi

  rm -f "$STALE_MARKER" "$CASCADE_DONE"
  printf '{"continue":true}'
  exit 0
fi

# Phase 6 stale and cascade not yet confirmed — BLOCK exit
printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"[Phase 6 Cascade Gate BLOCKED] Phase 6 review documents exist but RTL files were modified. You must: (1) re-run lint (verilator --lint-only -Wall), (2) update code-review.md, (3) update design-note.md. When done: touch .rtl-agent-team/state/phase6-cascade-done"}}'
