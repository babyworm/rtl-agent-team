#!/bin/sh
# RTL Phase 6 Cascade Gate: Stop hook
# Keeps Claude working when RTL files were modified after the Phase 6 review was completed.
#
# Stale marker:   .rat/state/phase6-stale       (set by rtl-edit-tracker.sh)
# Cascade done:   .rat/state/phase6-cascade-done (set after updating the review documents)
#
# Flow (first match wins):
#   - phase6-stale absent            → allow exit (Phase 6 was never completed or no RTL edits)
#   - phase6-cascade-done present    → if every Phase 6 document is newer than phase6-stale
#                                      and no design-note*.md is older than ppa-opt-done, clean
#                                      up both markers and allow exit; otherwise block and keep
#                                      the marker
#   - ppa-opt-done newer than a design-note*.md → block (PPA-Opt ran after the Phase 6 review)
#   - otherwise                      → block (RTL changed after the Phase 6 review)
#
# Every block goes through hooks/lib/stop-budget-util.sh: after RAT_STOP_BLOCK_LIMIT blocks
# without progress in one continuation chain, the gate lets Claude stop and shows the user a
# notice. From the chain's Stop STOPU_CHAIN_CAP + 1 on, whichever hooks blocked the earlier
# Stops, the gate shows the notice instead of blocking.

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
CWD=$(dirname "$RAT_DIR")  # the project root, even when the session has cd'd into a subdirectory

STATE_DIR="$RAT_DIR/state"
STALE_MARKER="$STATE_DIR/phase6-stale"
CASCADE_DONE="$STATE_DIR/phase6-cascade-done"
REVIEW_DIR="$CWD/reviews/phase-6-review"

if teamu_should_skip_gate "$STATE_DIR" "$INPUT"; then
  emit_post_continue
fi
STOP_CHAIN=$(stopu_chain_active "$INPUT" "$STATE_DIR" p6-cascade)

# If no stale marker, Phase 6 was not affected — allow exit
if [ ! -f "$STALE_MARKER" ]; then
  stopu_clear p6-cascade "$STATE_DIR"
  emit_post_continue
fi

# Progress: file name and mtime of the stale marker, ppa-opt-done and each Phase 6
# document. Before the notice, updating a document or the stale marker restarts the
# no-progress count; the chain cap still applies. The cascade-done marker counts by
# presence: touching it again moves nothing.
P6_PROGRESS=""
[ -f "$CASCADE_DONE" ] && P6_PROGRESS="cascade-done"
for doc in "$STALE_MARKER" "$STATE_DIR/ppa-opt-done" \
           "$REVIEW_DIR/code-review.md" "$REVIEW_DIR/design-review.md" \
           "$REVIEW_DIR/improvements.md" "$REVIEW_DIR"/design-note*.md; do
  [ -f "$doc" ] && P6_PROGRESS="$P6_PROGRESS ${doc##*/}:$(get_mtime_epoch "$doc")"
done
P6_NOTICE="[Phase 6 Cascade Gate] RTL changed after the Phase 6 review, and updated review documents are not yet recorded. The Phase 6 cascade gate is not asking Claude to continue in this turn and will ask again on your next message. Re-run /rtl-agent-team:rtl-p6-design-review, then record it: touch $(shq "$CASCADE_DONE")"

# If cascade work is confirmed done, verify documents were actually updated (G5: mtime check)
if [ -f "$CASCADE_DONE" ]; then
  STALE_MTIME=$(get_mtime_epoch "$STALE_MARKER")
  [ -z "$STALE_MTIME" ] && STALE_MTIME=0
  # A PPA-Opt result newer than a design note also leaves the review stale.
  PPA_MTIME=0
  [ -f "$STATE_DIR/ppa-opt-done" ] && PPA_MTIME=$(get_mtime_epoch "$STATE_DIR/ppa-opt-done")
  [ -z "$PPA_MTIME" ] && PPA_MTIME=0
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
    if [ "$DOC_MTIME" -le "$STALE_MTIME" ] 2>/dev/null || [ "$DOC_MTIME" -lt "$PPA_MTIME" ] 2>/dev/null; then
      DOCS_STALE=true
    fi
  done
  if [ "$DN_FOUND" = "false" ]; then
    DOCS_STALE=true
  fi

  if [ "$DOCS_STALE" = "true" ]; then
    P6_NOTICE="[Phase 6 Cascade Gate] The Phase 6 review is recorded as updated, but its documents are missing or older than the last RTL change or PPA-Opt result. The Phase 6 cascade gate is not asking Claude to continue in this turn and will ask again on your next message. Re-run /rtl-agent-team:rtl-p6-design-review; the recorded marker stays in place."
    stopu_gate p6-cascade "$STATE_DIR" "$STOP_CHAIN" "$P6_PROGRESS" "[Phase 6 Cascade Gate BLOCKED] The cascade-done marker is present, but the Phase 6 documents (code-review.md, design-review.md, design-note*.md, improvements.md) were not found or not updated after the last RTL change or PPA-Opt result. Re-run /rtl-agent-team:rtl-p6-design-review or update them to reflect those changes. The marker stays in place: the gate passes once every document is newer than phase6-stale and no design-note*.md is older than ppa-opt-done." "$P6_NOTICE"
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
    stopu_gate p6-cascade "$STATE_DIR" "$STOP_CHAIN" "$P6_PROGRESS" "[Phase 6 Cascade Gate BLOCKED] PPA optimization completed after Phase 6 design-note*.md was last written, so RTL may have changed. Re-run /rtl-agent-team:rtl-p6-design-review to reflect the PPA-Opt results, then record it: touch $(shq "$CASCADE_DONE")" "$P6_NOTICE"
  fi
fi

# Phase 6 stale and cascade not yet confirmed — block; the breaker bounds the chain.
stopu_gate p6-cascade "$STATE_DIR" "$STOP_CHAIN" "$P6_PROGRESS" "[Phase 6 Cascade Gate BLOCKED] RTL files were modified after the Phase 6 review. Re-run /rtl-agent-team:rtl-p6-design-review, or update the Phase 6 documents by hand: (1) re-run lint (verilator --lint-only -Wall) (2) update code-review.md (3) update design-review.md (4) update design-note*.md (single or split files per P6 policy) (5) update improvements.md. When done: touch $(shq "$CASCADE_DONE")" "$P6_NOTICE"
