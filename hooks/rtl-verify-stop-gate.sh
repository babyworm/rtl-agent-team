#!/bin/sh
# RTL Verify Stop Gate: keeps Claude working when RTL files were modified without verification.
#
# Tracking file: .rat/state/rtl-modified-files.txt (one path per line)
# Verification evidence: .rat/state/rtl-verify-done (marker file)
# Waiver: .rat/state/rtl-verify-waiver (the user's decision)
#
# Unverified RTL blocks the stop so Claude keeps working, within the bounds of
# hooks/lib/stop-budget-util.sh. After RAT_STOP_BLOCK_LIMIT blocks without progress in
# one continuation chain, the gate lets Claude stop and shows the user a notice.
# From the chain's Stop STOPU_CHAIN_CAP + 1 on, whichever hooks blocked the earlier
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
TRACK_FILE="$STATE_DIR/rtl-modified-files.txt"
VERIFY_DONE="$STATE_DIR/rtl-verify-done"
VERIFY_WAIVER="$STATE_DIR/rtl-verify-waiver"

if teamu_should_skip_gate "$STATE_DIR"; then
  emit_post_continue
fi
STOP_CHAIN=$(stopu_chain_active "$INPUT" "$STATE_DIR" verify)

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
  rm -f "$AGGREGATED_TRACK"
  stopu_clear verify "$STATE_DIR"
  emit_post_continue
fi

# If verification was done or waived, clean up and allow exit
if [ -f "$VERIFY_DONE" ] || [ -f "$VERIFY_WAIVER" ]; then
  # Clean up solo + all session-scoped tracking files
  rm -f "$STATE_DIR/rtl-modified-files.txt" "$VERIFY_DONE" "$VERIFY_WAIVER" "$AGGREGATED_TRACK" "$STATE_DIR/rtl-modified-files-fallback.txt"
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
# A tracking file with blank lines only lists no files: allow exit.
if [ -z "$TRACKED" ]; then
  rm -f "$AGGREGATED_TRACK"
  stopu_clear verify "$STATE_DIR"
  emit_post_continue
fi
COUNT=$(printf '%s\n' "$TRACKED" | grep -c .)
FILES=$(printf '%s\n' "$TRACKED" | awk -v max=10 'NF { n++; if (n <= max) printf "%s%s", (n > 1 ? ", " : ""), $0 } END { if (n > max) printf ", and %d more", n - max }')
# Clean up temporary aggregated file
rm -f "$AGGREGATED_TRACK"

MSG="[RTL Verify Gate BLOCKED] ${COUNT} RTL files modified but functional verification not performed: ${FILES}. Run functional verification for the affected modules (for example /rtl-agent-team:rtl-p5s-func-verify, or /rtl-agent-team:rtl-p4s-unit-test for unit tests). When the simulation passes, record it: touch $(shq "$VERIFY_DONE"). If verification cannot run here, report what is missing and ask the user with AskUserQuestion whether to waive it; a waiver is the user's decision."
NOTICE="[RTL Verify Gate] ${COUNT} RTL files have no recorded verification: ${FILES}. The verify gate is not asking Claude to continue in this turn and will ask again on your next message. Run functional verification, or waive it if the change is non-functional: touch $(shq "$VERIFY_WAIVER")"
stopu_gate verify "$STATE_DIR" "$STOP_CHAIN" "$TRACKED" "$MSG" "$NOTICE"
