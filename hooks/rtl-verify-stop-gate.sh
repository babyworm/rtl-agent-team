#!/bin/sh
# RTL Verify Stop Gate (Rule 5): keeps Claude working when RTL files were modified without
# verification. This launcher owns the Stop budget (stop-budget-util.sh, shared by every Stop
# gate); hooks/lib/verify_gate.py reads tracking, configuration and evidence.
#
# Tracking: .rat/state/rtl-modified-files.txt, plus rtl-modified-files-<session>.txt in team mode
# Evidence: runner-written verify-evidence.json with fresh hashes (scripts/run_sim.sh, the
#   regression wrappers, or eda_runner.py verify-run around a project's own runner)
# Waiver: .rat/state/rtl-verify-waiver (the user's decision)
# Mode: verification.stop_gate is block (default; also for unknown values), notify (one line
#   per content state, never blocks) or off (silent; tracking stays)
# Without Python >= RAT_PYTHON_MIN the evidence cannot be read, so the gate blocks.
#
# Request verification once for a new unverified content state. Its next Stop
# shows one informational line even if the user started a new prompt.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/hook-output-util.sh"
. "$SCRIPT_DIR/lib/stop-budget-util.sh"
. "$SCRIPT_DIR/lib/team-gate-util.sh"
. "$SCRIPT_DIR/lib/posix-util.sh"
. "$SCRIPT_DIR/lib/rat-dir-util.sh"
. "$SCRIPT_DIR/lib/python-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_root_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"
RAT_DIR=$(rat_project_dir "$CWD"); RAT_RC=$?
[ -z "$RAT_DIR" ] && { [ "$RAT_RC" -ne 2 ] || stopu_refuse_symlink_state; emit_post_continue; }
CWD=$(dirname "$RAT_DIR")  # the project root, even when the session has cd'd into a subdirectory

STATE_DIR="$RAT_DIR/state"
if teamu_should_skip_gate "$STATE_DIR" "$INPUT"; then
  emit_post_continue
fi
STOP_CHAIN=$(stopu_chain_active "$INPUT" "$STATE_DIR" verify)
stopu_background_agent_pending "$INPUT" && emit_post_continue  # paused for a background agent; its completion wakes the session
VERIFY_RECEIPT="$(stopu_budget_file verify "$STATE_DIR").reported"

clear_and_continue() {
  rm -f "$VERIFY_RECEIPT"
  stopu_clear verify "$STATE_DIR"
  emit_post_continue
}

# Nothing tracked: no Python start on an ordinary Stop.
HAS_TRACK=false
for _vg_file in "$STATE_DIR/rtl-modified-files.txt" "$STATE_DIR"/rtl-modified-files-*.txt; do
  if [ -s "$_vg_file" ]; then HAS_TRACK=true; break; fi
done
[ "$HAS_TRACK" = true ] || clear_and_continue

VG_ACTION=""
if PYTHON=$(rat_select_python 2>/dev/null); then
  # -I: no PYTHON* variables, user site or script-directory imports can add to what eval runs.
  eval "$("$PYTHON" -I "$SCRIPT_DIR/lib/verify_gate.py" --root "$CWD" --state "$STATE_DIR" \
    --plugin "$(cd "$SCRIPT_DIR/.." && pwd)" 2>/dev/null)"
  VG_REASON="the evidence helper hooks/lib/verify_gate.py failed (run it by hand to see why)"
else
  VG_REASON="Python >= $RAT_PYTHON_MIN was not found; install it or set RAT_PYTHON"
fi
case "$VG_ACTION" in
  continue) emit_post_continue ;;
  clear) clear_and_continue ;;
  cleared)
    rm -f "$VERIFY_RECEIPT"
    stopu_clear verify "$STATE_DIR"
    [ -n "$VG_NOTICE" ] || emit_post_continue
    # Name the runner that cleared Rule 5 once; a limit of 0 never blocks.
    stopu_gate verify "$STATE_DIR" "$STOP_CHAIN" "cleared" "$VG_NOTICE" "$VG_NOTICE" 0
    ;;
  gate) ;;
  *)
    # No decision: the evidence cannot be read, so block on whatever is tracked. A waiver
    # needs no evidence and stays the user's decision.
    if [ -f "$STATE_DIR/rtl-verify-waiver" ]; then
      rm -f "$STATE_DIR/rtl-modified-files.txt" "$STATE_DIR/rtl-verify-done" "$STATE_DIR/rtl-verify-waiver"
      for _vg_file in "$STATE_DIR"/rtl-modified-files-*.txt; do rm -f "$_vg_file"; done
      clear_and_continue
    fi
    VG_TRACKED=$(cat "$STATE_DIR/rtl-modified-files.txt" "$STATE_DIR"/rtl-modified-files-*.txt 2>/dev/null |
      grep -v '^[[:space:]]*$' | sort -u)
    [ -n "$VG_TRACKED" ] || clear_and_continue
    VG_MODE=block
    VG_SIM_PRESENT=true
    VG_PROGRESS=$VG_TRACKED
    while IFS= read -r _vg_line; do  # content in the progress, so a new edit re-arms the request
      case "$_vg_line" in /*) _vg_path=$_vg_line ;; *) _vg_path="$CWD/$_vg_line" ;; esac
      [ ! -f "$_vg_path" ] || VG_PROGRESS="$VG_PROGRESS|$(cksum < "$_vg_path")"
    done <<VG_LIST
$VG_TRACKED
VG_LIST
    VG_MSG="[RTL Verify Gate BLOCKED] RTL files were modified, but the gate cannot read the verification evidence: $VG_REASON. Then run /rtl-agent-team:rat-doctor. If verification cannot run here, report what is missing and ask the user with AskUserQuestion whether to waive it; a waiver is the user's decision."
    VG_NOTICE="Info> Functional verification is pending, and the RTL verify gate cannot read evidence: $VG_REASON."
    ;;
esac

FINGERPRINT=$(stopu_fingerprint "$VG_PROGRESS")
REPORTED=$(cat "$VERIFY_RECEIPT" 2>/dev/null)
if [ "$REPORTED" = "$FINGERPRINT info" ]; then
  emit_post_continue
fi
save_receipt() {
  printf '%s %s\n' "$FINGERPRINT" "$1" | ratu_state_write "$VERIFY_RECEIPT"
}
# Re-arm for changed content before notify/no-sim/block branches without resetting
# the cap shared by the Stop chain.
stopu_renotify verify "$STATE_DIR" "$STOP_CHAIN" "$VG_PROGRESS" || true
if [ "$VG_MODE" = notify ]; then
  # Its own receipt: returning to block must still request verification for this content.
  [ "$REPORTED" != "$FINGERPRINT notify" ] || emit_post_continue
  save_receipt notify || true
  stopu_gate verify "$STATE_DIR" "$STOP_CHAIN" "$VG_PROGRESS" "$VG_MSG" "$VG_NOTIFY_NOTICE" 0
fi
# A block helps only when a simulator can run. With none configured or on PATH,
# tell the user once per content state; LSP diagnostics still report syntax.
if [ "$VG_SIM_PRESENT" != true ]; then
  save_receipt info || true
  stopu_gate verify "$STATE_DIR" "$STOP_CHAIN" "$VG_PROGRESS" "$VG_MSG" "$VG_NOSIM_NOTICE" 0
fi
if [ "$REPORTED" = "$FINGERPRINT requested" ]; then
  save_receipt info || true
  stopu_gate verify "$STATE_DIR" "$STOP_CHAIN" "$VG_PROGRESS" "$VG_MSG" "$VG_NOTICE" 0
fi

if [ "$(stopu_decision verify "$STATE_DIR" "$STOP_CHAIN" "$VG_PROGRESS" 1)" = block ] &&
   save_receipt requested; then
  stopu_gate verify "$STATE_DIR" "$STOP_CHAIN" "$VG_PROGRESS" "$VG_MSG" "$VG_NOTICE" 1
fi
save_receipt info || true
stopu_gate verify "$STATE_DIR" "$STOP_CHAIN" "$VG_PROGRESS" "$VG_MSG" "$VG_NOTICE" 0
