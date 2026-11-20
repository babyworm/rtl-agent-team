#!/bin/sh
# RTL Verify Stop Gate: keeps Claude working when RTL files were modified without verification.
#
# Tracking file: .rat/state/rtl-modified-files.txt (one path per line)
# Verification evidence: runner-written verify-evidence.json with fresh hashes
# Waiver: .rat/state/rtl-verify-waiver (the user's decision)
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
RAT_DIR=$(rat_project_dir "$CWD")
[ -z "$RAT_DIR" ] && { emit_post_continue; }
CWD=$(dirname "$RAT_DIR")  # the project root, even when the session has cd'd into a subdirectory

STATE_DIR="$RAT_DIR/state"
TRACK_FILE="$STATE_DIR/rtl-modified-files.txt"
VERIFY_DONE="$STATE_DIR/rtl-verify-done"
VERIFY_WAIVER="$STATE_DIR/rtl-verify-waiver"

if teamu_should_skip_gate "$STATE_DIR" "$INPUT"; then
  emit_post_continue
fi
STOP_CHAIN=$(stopu_chain_active "$INPUT" "$STATE_DIR" verify)
stopu_background_agent_pending "$INPUT" && emit_post_continue  # paused for a background agent; its completion wakes the session
VERIFY_RECEIPT="$(stopu_budget_file verify "$STATE_DIR").reported"

# Team mode aggregation: merge all session-scoped tracking files into a combined view.
# In team mode, each worker writes to rtl-modified-files-{SESSION_ID}.txt.
# The leader (this gate only runs on the leader) aggregates all of them.
#
# Trigger aggregation whenever team mode is active OR any session-scoped worker
# tracking file is present. Gating on team-config.json alone is unsafe: team
# skills delete team-config.json during teardown BEFORE the leader's first Stop,
# so worker RTL edits recorded in rtl-modified-files-{SESSION_ID}.txt would
# otherwise escape Rule 5 (verify gate) once the config is gone.
TEAM_CONFIG="$STATE_DIR/team-config.json"
TEAM_MODE=""
if [ -f "$TEAM_CONFIG" ]; then
  TEAM_MODE=$(jsonu_get_file_path_bool "$TEAM_CONFIG" "team_mode")
fi
# Detect leftover session-scoped worker files (exclude the non-team fallback
# file, which is handled separately below).
HAS_SESSION_TRACK=false
for sf in "$STATE_DIR"/rtl-modified-files-*.txt; do
  [ -f "$sf" ] || continue
  case "$sf" in
    "$STATE_DIR"/rtl-modified-files-fallback.txt) continue ;;
  esac
  HAS_SESSION_TRACK=true
  break
done
AGGREGATED_TRACK=""
if [ "$TEAM_MODE" = "true" ] || [ "$HAS_SESSION_TRACK" = "true" ]; then
  # Merge solo + all session-scoped files into a temporary aggregated file
  AGGREGATED_TRACK="$STATE_DIR/rtl-modified-files-aggregated.$$.tmp"
  trap 'rm -f "$AGGREGATED_TRACK" "$AGGREGATED_TRACK.dedup"' EXIT
  trap 'exit 129' HUP
  trap 'exit 130' INT
  trap 'exit 143' TERM
  rm -f "$AGGREGATED_TRACK"
  touch "$AGGREGATED_TRACK"
  # Include solo file if it exists
  if [ -f "$TRACK_FILE" ] && [ -s "$TRACK_FILE" ]; then
    cat "$TRACK_FILE" >> "$AGGREGATED_TRACK"
  fi
  # Include all session-scoped files (glob also covers the fallback file)
  for sf in "$STATE_DIR"/rtl-modified-files-*.txt; do
    [ -f "$sf" ] && cat "$sf" >> "$AGGREGATED_TRACK"
  done
  # Deduplicate
  if [ -s "$AGGREGATED_TRACK" ]; then
    sort -u "$AGGREGATED_TRACK" > "$AGGREGATED_TRACK.dedup"
    mv "$AGGREGATED_TRACK.dedup" "$AGGREGATED_TRACK"
    TRACK_FILE="$AGGREGATED_TRACK"
  else
    rm -f "$AGGREGATED_TRACK"
  fi
fi

# Merge lock-failure fallback entries (non-team mode; team mode glob already includes them)
FALLBACK_FILE="$STATE_DIR/rtl-modified-files-fallback.txt"
if [ -z "$AGGREGATED_TRACK" ] && [ -f "$FALLBACK_FILE" ] && [ -s "$FALLBACK_FILE" ]; then
  cat "$FALLBACK_FILE" >> "$TRACK_FILE"
  rm -f "$FALLBACK_FILE"
fi

# If no tracked files, allow exit
if [ ! -f "$TRACK_FILE" ] || [ ! -s "$TRACK_FILE" ]; then
  rm -f "$AGGREGATED_TRACK" "$VERIFY_RECEIPT"
  stopu_clear verify "$STATE_DIR"
  emit_post_continue
fi

# A bare verify-done marker does not establish that a simulation ran. Check
# runner evidence once; when no parser is available, keep verification pending.
EVIDENCE_VERIFIED=false
EVIDENCE_PENDING=""
EVIDENCE_PYTHON=$(rat_select_python 2>/dev/null) || EVIDENCE_PYTHON=""
EVIDENCE_HELPER="$SCRIPT_DIR/../scripts/verify_evidence.py"
if [ -n "$EVIDENCE_PYTHON" ] && [ -f "$EVIDENCE_HELPER" ]; then
  if "$EVIDENCE_PYTHON" "$EVIDENCE_HELPER" pending --root "$CWD" --track "$TRACK_FILE"; then
    emit_post_continue
  fi
  EVIDENCE_PENDING=$("$EVIDENCE_PYTHON" "$EVIDENCE_HELPER" unverified --root "$CWD" --track "$TRACK_FILE")
  EVIDENCE_STATUS=$?
  [ "$EVIDENCE_STATUS" -eq 0 ] && EVIDENCE_VERIFIED=true
  [ "$EVIDENCE_STATUS" -le 1 ] || EVIDENCE_PENDING=""
fi

if [ "$EVIDENCE_VERIFIED" = "true" ] || [ -f "$VERIFY_WAIVER" ]; then
  # Clean up solo + all session-scoped tracking files
  rm -f "$STATE_DIR/rtl-modified-files.txt" "$VERIFY_DONE" "$VERIFY_WAIVER" "$AGGREGATED_TRACK" "$STATE_DIR/rtl-modified-files-fallback.txt" "$VERIFY_RECEIPT"
  for sf in "$STATE_DIR"/rtl-modified-files-*.txt; do
    [ -f "$sf" ] && rm -f "$sf"
  done
  stopu_clear verify "$STATE_DIR"
  emit_post_continue
fi

# Modified RTL files exist without verification — block; the breaker bounds the chain.
# One project-relative, de-duplicated list drives the count, the display and the progress.
PROJECT_ROOT=$(dirname "$RAT_DIR")
TRACKED=$(RAT_TRACK_ROOT="$PROJECT_ROOT/" awk 'BEGIN { p = ENVIRON["RAT_TRACK_ROOT"] }
  NF { if (index($0, p) == 1) $0 = substr($0, length(p) + 1); sub(/^\.\//, ""); print }' "$TRACK_FILE" | sort -u)
[ -z "$EVIDENCE_PENDING" ] || TRACKED="$EVIDENCE_PENDING"
# A tracking file with blank lines only lists no files: allow exit.
if [ -z "$TRACKED" ]; then
  rm -f "$AGGREGATED_TRACK" "$VERIFY_RECEIPT"
  stopu_clear verify "$STATE_DIR"
  emit_post_continue
fi
COUNT=$(printf '%s\n' "$TRACKED" | grep -c .)
FILES=$(printf '%s\n' "$TRACKED" | awk -v max=10 'NF { n++; if (n <= max) printf "%s%s", (n > 1 ? ", " : ""), $0 } END { if (n > max) printf ", and %d more", n - max }')
# Clean up temporary aggregated file
rm -f "$AGGREGATED_TRACK"

MSG="[RTL Verify Gate BLOCKED] ${COUNT} RTL files modified but functional verification not performed: ${FILES}. Run functional verification for the affected modules through scripts/run_sim.sh (for example /rtl-agent-team:rtl-p5s-func-verify, or /rtl-agent-team:rtl-p4s-unit-test). A passing testbench emits RAT_SIM_PASS or a recognized test summary; the runner records fresh source and log hashes in $(shq "$STATE_DIR/verify-evidence.json"). A touched marker is insufficient. If verification cannot run here, report what is missing and ask the user with AskUserQuestion whether to waive it; a waiver is the user's decision."
NOTICE="Info> Functional verification is pending for ${COUNT} RTL file(s)."
VERIFY_PROGRESS="$TRACKED"
while IFS= read -r _vp_file; do
  case "$_vp_file" in /*) ;; *) _vp_file="$PROJECT_ROOT/$_vp_file" ;; esac
  [ ! -f "$_vp_file" ] || VERIFY_PROGRESS="$VERIFY_PROGRESS|$(cksum < "$_vp_file")"
done <<EOF
$TRACKED
EOF
FINGERPRINT=$(stopu_fingerprint "$VERIFY_PROGRESS")
REPORTED=$(cat "$VERIFY_RECEIPT" 2>/dev/null)
if [ "$REPORTED" = "$FINGERPRINT info" ]; then
  emit_post_continue
fi
save_receipt() {
  printf '%s %s\n' "$FINGERPRINT" "$1" | ratu_state_write "$VERIFY_RECEIPT"
}
if [ "$REPORTED" = "$FINGERPRINT requested" ]; then
  save_receipt info || true
  stopu_gate verify "$STATE_DIR" "$STOP_CHAIN" "$VERIFY_PROGRESS" "$MSG" "$NOTICE" 0
fi

# Re-arm for changed content without resetting the cap shared by the Stop chain.
stopu_renotify verify "$STATE_DIR" "$STOP_CHAIN" "$VERIFY_PROGRESS" || true
if [ "$(stopu_decision verify "$STATE_DIR" "$STOP_CHAIN" "$VERIFY_PROGRESS" 1)" = block ] &&
   save_receipt requested; then
  stopu_gate verify "$STATE_DIR" "$STOP_CHAIN" "$VERIFY_PROGRESS" "$MSG" "$NOTICE" 1
fi
save_receipt info || true
stopu_gate verify "$STATE_DIR" "$STOP_CHAIN" "$VERIFY_PROGRESS" "$MSG" "$NOTICE" 0
