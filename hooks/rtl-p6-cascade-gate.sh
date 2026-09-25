#!/bin/sh
# RTL Phase 6 Cascade Gate: Stop hook
# Keeps Claude working when RTL files were modified after the Phase 6 review was completed.
#
# Stale marker:   .rat/state/phase6-stale       (set by rtl-edit-tracker.sh)
# Cascade done:   .rat/state/phase6-cascade-done (set after updating the review documents)
#
# Flow:
#   - phase6-stale absent            → allow exit (Phase 6 was never completed or no RTL edits)
#   - phase6-cascade-done present    → verify document mtimes, clean up both markers, allow exit
#   - otherwise                      → block; after RAT_STOP_BLOCK_LIMIT blocks without progress
#                                      in one chain, hand over to the user (stop-budget-util.sh)

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/hook-output-util.sh"
. "$SCRIPT_DIR/lib/stop-budget-util.sh"
. "$SCRIPT_DIR/lib/team-gate-util.sh"
. "$SCRIPT_DIR/lib/posix-util.sh"
. "$SCRIPT_DIR/lib/rat-dir-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
RAT_DIR=$(rat_project_dir "$CWD")
[ -z "$RAT_DIR" ] && { emit_post_continue; }

STATE_DIR="$RAT_DIR/state"
STALE_MARKER="$STATE_DIR/phase6-stale"
CASCADE_DONE="$STATE_DIR/phase6-cascade-done"
REVIEW_DIR="$CWD/reviews/phase-6-review"

if teamu_should_skip_gate "$STATE_DIR"; then
  emit_post_continue
fi
STOP_CHAIN=$(stopu_chain_active "$INPUT" "$STATE_DIR" p6-cascade)

# If no stale marker, Phase 6 was not affected — allow exit
if [ ! -f "$STALE_MARKER" ]; then
  stopu_clear p6-cascade "$STATE_DIR"
  emit_post_continue
fi

# Progress: markers and Phase 6 document mtimes. Updating any of them restarts
# the breaker.
P6_PROGRESS=""
for doc in "$STALE_MARKER" "$CASCADE_DONE" "$STATE_DIR/ppa-opt-done" \
           "$REVIEW_DIR/code-review.md" "$REVIEW_DIR/design-review.md" \
           "$REVIEW_DIR/improvements.md" "$REVIEW_DIR"/design-note*.md; do
  [ -f "$doc" ] && P6_PROGRESS="$P6_PROGRESS $doc:$(get_mtime_epoch "$doc")"
done
P6_NOTICE="[Phase 6 Cascade Gate] RTL changed after the Phase 6 review and the review documents are not yet updated. The Phase 6 cascade gate is not asking Claude to continue in this turn and will ask again on your next message. Re-run /rtl-agent-team:rtl-p6-design-review, then touch $(shq "$CASCADE_DONE")."

# If cascade work is confirmed done, verify documents were actually updated (G5: mtime check)
if [ -f "$CASCADE_DONE" ]; then
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
    stopu_gate p6-cascade "$STATE_DIR" "$STOP_CHAIN" "$P6_PROGRESS" "[Phase 6 Cascade Gate BLOCKED] cascade-done marker present but design documents (code-review.md, design-review.md, design-note*.md, improvements.md) were not found or not updated after RTL change. Document mtime must be newer than the stale marker. Action: Update documents to reflect RTL modifications, then touch $(shq "$CASCADE_DONE") again." "$P6_NOTICE"
  fi

  rm -f "$STALE_MARKER" "$CASCADE_DONE"
  stopu_clear p6-cascade "$STATE_DIR"
  emit_post_continue
fi

# If PPA optimization completed after Phase 6 artifacts were written, flag re-review.
# This handles the case where ppa-opt-done was written by the PPA optimizer after
# design-note*.md was last updated, meaning the Phase 6 review is now stale.
# Supports split files per P6 policy: design-note-overview.md, design-note-{module}.md, etc.
if [ -f "$STATE_DIR/ppa-opt-done" ]; then
  ppa_mtime=$(get_mtime_epoch "$STATE_DIR/ppa-opt-done")
  [ -z "$ppa_mtime" ] && ppa_mtime=0
  # Find any design-note*.md file with mtime older than ppa-opt-done
  stale=0
  for design_note in "$REVIEW_DIR"/design-note*.md; do
    [ ! -f "$design_note" ] && continue
    p6_mtime=$(get_mtime_epoch "$design_note")
    [ -z "$p6_mtime" ] && p6_mtime=0
    if [ "$ppa_mtime" -gt "$p6_mtime" ] 2>/dev/null; then
      stale=1
      break
    fi
  done
  if [ "$stale" = "1" ]; then
    stopu_gate p6-cascade "$STATE_DIR" "$STOP_CHAIN" "$P6_PROGRESS" "[Phase 6 Cascade Gate BLOCKED] PPA optimization completed after Phase 6 design-note*.md was last written. RTL may have changed. Required: re-run rtl-p6-design-review to reflect PPA-Opt results." "$P6_NOTICE"
  fi
fi

# Phase 6 stale and cascade not yet confirmed — block; the breaker bounds the chain.
stopu_gate p6-cascade "$STATE_DIR" "$STOP_CHAIN" "$P6_PROGRESS" "[Phase 6 Cascade Gate BLOCKED] Phase 6 review documents exist but RTL files were modified. Required steps: (1) Re-run lint (verilator --lint-only -Wall) (2) Update code-review.md (3) Update design-review.md (4) Update design-note*.md (single or split files per P6 policy) (5) Update improvements.md. When done: touch $(shq "$CASCADE_DONE")" "$P6_NOTICE"
