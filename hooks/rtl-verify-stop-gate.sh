#!/bin/sh
# RTL Verify Stop Gate: blocks session exit if RTL files were modified without verification.
#
# Tracking file: .rtl-agent-team/state/rtl-modified-files.txt (one path per line)
# Verification evidence: .rtl-agent-team/state/rtl-verify-done (marker file)
# Waiver: .rtl-agent-team/state/rtl-verify-waiver (bypass marker)
#
# If modified RTL files exist and no evidence/waiver is found, session exit is BLOCKED.

INPUT=$(cat)
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
. "$SCRIPT_DIR/lib/json-util.sh"
. "$SCRIPT_DIR/lib/hook-output-util.sh"
. "$SCRIPT_DIR/lib/team-gate-util.sh"
jsonu_detect_parser

CWD=$(jsonu_get_input_string "$INPUT" "cwd")
[ -z "$CWD" ] && CWD="$(pwd)"

STATE_DIR="$CWD/.rtl-agent-team/state"
TRACK_FILE="$STATE_DIR/rtl-modified-files.txt"
VERIFY_DONE="$STATE_DIR/rtl-verify-done"
VERIFY_WAIVER="$STATE_DIR/rtl-verify-waiver"

if teamu_should_skip_gate "$STATE_DIR"; then
  emit_post_continue
fi

# Team mode aggregation: merge all session-scoped tracking files into a combined view.
# In team mode, each worker writes to rtl-modified-files-{SESSION_ID}.txt.
# The leader (this gate only runs on the leader) aggregates all of them.
TEAM_CONFIG="$STATE_DIR/team-config.json"
AGGREGATED_TRACK=""
if [ -f "$TEAM_CONFIG" ]; then
  TEAM_MODE=$(jsonu_get_file_path_bool "$TEAM_CONFIG" "team_mode")
  if [ "$TEAM_MODE" = "true" ]; then
    # Merge solo + all session-scoped files into a temporary aggregated file
    AGGREGATED_TRACK="$STATE_DIR/rtl-modified-files-aggregated.tmp"
    rm -f "$AGGREGATED_TRACK"
    touch "$AGGREGATED_TRACK"
    # Include solo file if it exists
    if [ -f "$TRACK_FILE" ] && [ -s "$TRACK_FILE" ]; then
      cat "$TRACK_FILE" >> "$AGGREGATED_TRACK"
    fi
    # Include all session-scoped files
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
  emit_post_continue
fi

# If verification was done or waived, clean up and allow exit
if [ -f "$VERIFY_DONE" ] || [ -f "$VERIFY_WAIVER" ]; then
  # Clean up solo + all session-scoped tracking files
  rm -f "$STATE_DIR/rtl-modified-files.txt" "$VERIFY_DONE" "$VERIFY_WAIVER" "$AGGREGATED_TRACK" "$STATE_DIR/rtl-modified-files-fallback.txt"
  for sf in "$STATE_DIR"/rtl-modified-files-*.txt; do
    [ -f "$sf" ] && rm -f "$sf"
  done
  emit_post_continue
fi

# Modified RTL files exist without verification — BLOCK exit
COUNT=$(wc -l < "$TRACK_FILE" | tr -d ' ')
FILES=$(while IFS= read -r f; do basename "$f"; done < "$TRACK_FILE" | tr '\n' ', ' | sed 's/,$//')
# Clean up temporary aggregated file
rm -f "$AGGREGATED_TRACK"
# Escape JSON-special characters in filenames
FILES=$(jsonu_escape "$FILES")

MSG="[RTL Verify Gate BLOCKED] ${COUNT} RTL files modified but functional verification not performed: ${FILES}. Options: (1) Run /rtl-agent-team:rtl-p5s-func-verify for functional verification (2) Waive: touch .rtl-agent-team/state/rtl-verify-waiver (3) Reset: rm .rtl-agent-team/state/rtl-modified-files.txt"
emit_stop_block "$MSG"
