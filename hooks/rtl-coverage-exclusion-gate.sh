#!/bin/sh
# RTL Coverage Exclusion Approval Gate: blocks session exit if non-standard
# coverage exclusions exist without user approval.
#
# Non-standard categories (per rtl-p5s-coverage-policy):
#   - Unimplemented features (out-of-scope)
#   - Ambiguous spec applicability
# These require user approval via AskUserQuestion before session exit.
#
# Approval evidence: .rat/state/coverage-exclusion-approved (marker file)
# Waiver: same marker — agent creates it after user confirms via AskUserQuestion.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/hook-output-util.sh"
. "$SCRIPT_DIR/lib/team-gate-util.sh"
. "$SCRIPT_DIR/lib/rat-dir-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
RAT_DIR=$(rat_project_dir "$CWD")
[ -z "$RAT_DIR" ] && { emit_post_continue; }

STATE_DIR="$RAT_DIR/state"
APPROVAL_MARKER="$STATE_DIR/coverage-exclusion-approved"

# Team mode: only leader checks
if teamu_should_skip_gate "$STATE_DIR"; then
  emit_post_continue
fi

# If approval marker exists, pass immediately
if [ -f "$APPROVAL_MARKER" ]; then
  emit_post_continue
fi

# Check if any exclusion records exist
REVIEW_DIR="$CWD/reviews/phase-5-verify"
if [ ! -d "$REVIEW_DIR" ]; then
  emit_post_continue
fi

# Scan for non-standard exclusion entries in module + system exclusion files
# Non-standard patterns: "Unimplemented" or "Ambiguous" in exclusion category columns
UNAPPROVED_COUNT=0
UNAPPROVED_BINS=""

for excl_file in "$REVIEW_DIR"/*-coverage-exclusions.md "$REVIEW_DIR"/system-coverage-exclusions.md; do
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
  emit_post_continue
fi

# Non-standard exclusions found without approval → BLOCK
SAFE_BINS=$(printf '%s' "$UNAPPROVED_BINS" | sed 's/"/\\"/g')
printf '{"decision":"block","reason":"[Coverage Exclusion Gate] %d non-standard exclusion(s) require user approval: %s. These bins (Unimplemented features / Ambiguous spec) need explicit confirmation via AskUserQuestion. After approval: touch %s/coverage-exclusion-approved"}' \
  "$UNAPPROVED_COUNT" "$SAFE_BINS" "$STATE_DIR"
