#!/bin/sh
# RTL Coverage Exclusion Approval Gate: asks for the user's approval when non-standard
# coverage exclusions exist without it.
#
# Non-standard categories (per rtl-p5s-coverage-policy):
#   - Unimplemented features (out-of-scope)
#   - Ambiguous spec applicability
# These require user approval, which Claude asks for via AskUserQuestion.
#
# Approval evidence: .rat/state/coverage-exclusion-approved (marker file)
# Waiver: same marker — agent creates it after user confirms via AskUserQuestion.
#
# The block goes through hooks/lib/stop-budget-util.sh with a per-call limit of 1: the gate
# blocks once per continuation chain so Claude asks the user, then lets Claude stop and shows
# the user a notice that ends with the approval command. From the chain's Stop
# STOPU_CHAIN_CAP + 1 on, whichever hooks blocked the earlier Stops, the gate shows the notice
# instead of blocking.

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
APPROVAL_MARKER="$STATE_DIR/coverage-exclusion-approved"

# Team mode: only leader checks
if teamu_should_skip_gate "$STATE_DIR" "$INPUT"; then
  emit_post_continue
fi
STOP_CHAIN=$(stopu_chain_active "$INPUT" "$STATE_DIR" coverage-exclusion)

# If approval marker exists, pass immediately
if [ -f "$APPROVAL_MARKER" ]; then
  stopu_clear coverage-exclusion "$STATE_DIR"
  emit_post_continue
fi

# Check if any exclusion records exist; without any, nothing awaits approval.
REVIEW_DIR="$CWD/reviews/phase-5-verify"
if [ ! -d "$REVIEW_DIR" ]; then
  stopu_clear coverage-exclusion "$STATE_DIR"
  emit_post_continue
fi

# Scan for non-standard exclusion entries in module + system exclusion files. The glob
# also matches system-coverage-exclusions.md, so every file is read once.
# Non-standard patterns: "Unimplemented" or "Ambiguous" in exclusion category columns
UNAPPROVED_COUNT=0
UNAPPROVED_BINS=""

for excl_file in "$REVIEW_DIR"/*-coverage-exclusions.md; do
  [ -f "$excl_file" ] || continue
  # Grep for non-standard category lines in markdown tables
  # Pattern: table row containing "Unimplemented" or "Ambiguous" (case insensitive)
  MATCHES=$(grep -i -E '\|[^|]*(Unimplemented|Ambiguous)[^|]*\|' "$excl_file" 2>/dev/null || true)
  if [ -n "$MATCHES" ]; then
    COUNT=$(printf '%s\n' "$MATCHES" | wc -l | tr -d ' ')
    UNAPPROVED_COUNT=$((UNAPPROVED_COUNT + COUNT))
    FILE_BASE=$(basename "$excl_file")
    if [ -n "$UNAPPROVED_BINS" ]; then
      UNAPPROVED_BINS="$UNAPPROVED_BINS, $FILE_BASE($COUNT)"
    else
      UNAPPROVED_BINS="$FILE_BASE($COUNT)"
    fi
  fi
done

# No non-standard exclusions found → pass
if [ "$UNAPPROVED_COUNT" -eq 0 ]; then
  stopu_clear coverage-exclusion "$STATE_DIR"
  emit_post_continue
fi

# Non-standard exclusions without approval: block once per chain so Claude asks the
# user, then hand the approval to the user.
COV_PROGRESS="$UNAPPROVED_COUNT|$UNAPPROVED_BINS"
COV_MSG="[Coverage Exclusion Gate] ${UNAPPROVED_COUNT} non-standard exclusion(s) require user approval: ${UNAPPROVED_BINS}. These bins (Unimplemented features / Ambiguous spec) need explicit confirmation via AskUserQuestion. After approval: touch $(shq "$APPROVAL_MARKER")"
COV_NOTICE="[Coverage Exclusion Gate] ${UNAPPROVED_COUNT} non-standard coverage exclusion(s) still await your approval: ${UNAPPROVED_BINS}. To approve: touch $(shq "$APPROVAL_MARKER")"
stopu_gate coverage-exclusion "$STATE_DIR" "$STOP_CHAIN" "$COV_PROGRESS" "$COV_MSG" "$COV_NOTICE" 1
