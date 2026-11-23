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

CWD=$(jsonu_get_root_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
RAT_DIR=$(rat_project_dir "$CWD"); RAT_RC=$?
[ -z "$RAT_DIR" ] && { [ "$RAT_RC" -ne 2 ] || stopu_refuse_symlink_state; emit_post_continue; }
CWD=$(dirname "$RAT_DIR")  # the project root, even when the session has cd'd into a subdirectory

STATE_DIR="$RAT_DIR/state"

# Team mode: only leader checks
if teamu_should_skip_gate "$STATE_DIR" "$INPUT"; then
  emit_post_continue
fi
STOP_CHAIN=$(stopu_chain_active "$INPUT" "$STATE_DIR" coverage-exclusion)
stopu_background_agent_pending "$INPUT" && emit_post_continue  # paused for a background agent; its completion wakes the session

# Fast-path: start Python only when exclusion files actually exist.
_CEG_HAS_FILES=false
if [ -f "$CWD/reviews/phase-5-verify/coverage-exclusions.json" ]; then
  _CEG_HAS_FILES=true
else
  for _ceg_f in "$CWD/reviews/phase-5-verify"/*-coverage-exclusions.md; do
    if [ -f "$_ceg_f" ]; then _CEG_HAS_FILES=true; break; fi
  done
fi
if [ "$_CEG_HAS_FILES" != true ]; then
  stopu_clear coverage-exclusion "$STATE_DIR"
  emit_post_continue
fi

HELPER="$SCRIPT_DIR/../scripts/coverage_approval.py"
PYTHON=$(jsonu_python) || PYTHON=""
if [ -z "$PYTHON" ]; then
  MSG="[Coverage Exclusion Gate] Python >=3.9 is needed to validate exclusion approval fingerprints."
  stopu_gate coverage-exclusion "$STATE_DIR" "$STOP_CHAIN" parser-unavailable "$MSG" "$MSG" 0
fi
RESULT=$("$PYTHON" "$HELPER" check --root "$CWD" 2>/dev/null)
STATUS=$?
if [ "$STATUS" = 0 ]; then
  stopu_clear coverage-exclusion "$STATE_DIR"
  emit_post_continue
fi
if [ "$STATUS" != 1 ]; then
  MSG="[Coverage Exclusion Gate] The exclusion records could not be parsed; approval is still pending."
  stopu_gate coverage-exclusion "$STATE_DIR" "$STOP_CHAIN" parser-error "$MSG" "$MSG" 0
fi
PARSED=$(printf '%s' "$RESULT" | "$PYTHON" -I -c 'import json,sys
d=json.load(sys.stdin)
c,fp=d["count"],d["fingerprint"]
if not isinstance(c,int) or not isinstance(fp,str) or not fp: raise ValueError("invalid")
print(f"{c}\t{fp}")' 2>/dev/null)
if [ -z "$PARSED" ]; then
  MSG="[Coverage Exclusion Gate] The exclusion records could not be parsed; approval is still pending."
  stopu_gate coverage-exclusion "$STATE_DIR" "$STOP_CHAIN" parser-error "$MSG" "$MSG" 0
fi
COUNT=${PARSED%%	*}
FINGERPRINT=${PARSED#*	}
MSG="[Coverage Exclusion Gate] $COUNT non-standard exclusions await the user's confirmation. Ask once for the current exclusion set. After confirmation, record the answer with scripts/coverage_approval.py approve --root <project> --decision <user-answer>. A touched marker does not approve later changes."
NOTICE="[Coverage Exclusion Gate] $COUNT non-standard exclusions still await your confirmation. The approval applies only to this exclusion set."
stopu_gate coverage-exclusion "$STATE_DIR" "$STOP_CHAIN" "$FINGERPRINT" "$MSG" "$NOTICE" 1
