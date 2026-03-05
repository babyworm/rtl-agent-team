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

# If cascade work is confirmed done, clean up and allow exit
if [ -f "$CASCADE_DONE" ]; then
  rm -f "$STALE_MARKER" "$CASCADE_DONE"
  printf '{"continue":true}'
  exit 0
fi

# Phase 6 stale and cascade not yet confirmed — BLOCK exit
printf '{"continue":false,"hookSpecificOutput":{"additionalContext":"[Phase 6 Cascade Gate BLOCKED] Phase 6 review documents exist but RTL files were modified. You must: (1) re-run lint (verilator --lint-only -Wall), (2) update code-review.md, (3) update design-note.md. When done: touch .rtl-agent-team/state/phase6-cascade-done"}}'
