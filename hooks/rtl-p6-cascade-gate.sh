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
. "$SCRIPT_DIR/lib/posix-util.sh"
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
  STALE_MTIME=$(get_mtime_epoch "$STALE_MARKER")
  [ -z "$STALE_MTIME" ] && STALE_MTIME=0
  DOCS_STALE=false
  # All four P6 deliverables must exist and be updated after the stale marker:
  # code-review.md, design-review.md, design-note*.md (at least one), improvements.md
  for doc in "$REVIEW_DIR/code-review.md" "$REVIEW_DIR/design-review.md" "$REVIEW_DIR/improvements.md"; do
    if [ ! -f "$doc" ]; then
      DOCS_STALE=true
    else
      DOC_MTIME=$(get_mtime_epoch "$doc")
      [ -z "$DOC_MTIME" ] && DOC_MTIME=0
      if [ "$DOC_MTIME" -le "$STALE_MTIME" ] 2>/dev/null; then
        DOCS_STALE=true
      fi
    fi
  done
  # design-note*.md must have at least one file and all must be updated
  # (supports split files per P6 policy: design-note-overview.md, design-note-{module}.md, etc.)
  DN_FOUND=false
  for doc in "$REVIEW_DIR"/design-note*.md; do
    [ -f "$doc" ] || continue
    DN_FOUND=true
    DOC_MTIME=$(get_mtime_epoch "$doc")
    [ -z "$DOC_MTIME" ] && DOC_MTIME=0
    if [ "$DOC_MTIME" -le "$STALE_MTIME" ] 2>/dev/null; then
      DOCS_STALE=true
    fi
  done
  if [ "$DN_FOUND" = "false" ]; then
    DOCS_STALE=true
  fi

  if [ "$DOCS_STALE" = "true" ]; then
    printf '{"continue":false,"decision":"block","reason":"[Phase 6 Cascade Gate BLOCKED] cascade-done marker present but design documents (code-review.md, design-review.md, design-note*.md, improvements.md) were not found or not updated after RTL change.\\n\\nDocument mtime must be newer than the stale marker.\\n\\nAction: Update documents to reflect RTL modifications, then touch .rtl-agent-team/state/phase6-cascade-done again."}'
    exit 0
  fi

  rm -f "$STALE_MARKER" "$CASCADE_DONE"
  printf '{"continue":true}'
  exit 0
fi

# Phase 6 stale and cascade not yet confirmed — BLOCK exit
printf '{"continue":false,"decision":"block","reason":"[Phase 6 Cascade Gate BLOCKED] Phase 6 review documents exist but RTL files were modified.\\n\\nRequired steps:\\n  1. Re-run lint (verilator --lint-only -Wall)\\n  2. Update code-review.md\\n  3. Update design-review.md\\n  4. Update design-note*.md (single or split files per P6 policy)\\n  5. Update improvements.md\\n\\nWhen done: touch .rtl-agent-team/state/phase6-cascade-done"}'
