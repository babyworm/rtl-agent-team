#!/bin/sh
# show-audit.sh — CLI viewer for RTL Agent Team audit trace logs.
# Usage:
#   sh scripts/show-audit.sh                # Show current session trace
#   sh scripts/show-audit.sh --follow       # tail -f mode (live)
#   sh scripts/show-audit.sh --decisions    # DECISION events only
#   sh scripts/show-audit.sh --summary      # Statistics summary
#   sh scripts/show-audit.sh --prompts      # List saved prompts
#   sh scripts/show-audit.sh --session ID   # Show specific session

set -e

# ANSI colors
C_RESET='\033[0m'
C_BOLD='\033[1m'
C_DIM='\033[2m'
C_BLUE='\033[34m'
C_GREEN='\033[32m'
C_YELLOW='\033[33m'
C_MAGENTA='\033[35m'
C_RED='\033[31m'
C_CYAN='\033[36m'

# Defaults
CWD="${PWD}"
AUDIT_DIR="$CWD/.rat/audit"
MODE="timeline"
SESSION_ID=""
FILTER=""

# Parse arguments
while [ $# -gt 0 ]; do
  case "$1" in
    --follow|-f)    MODE="follow" ;;
    --decisions|-d) MODE="timeline"; FILTER="decision" ;;
    --summary|-s)   MODE="summary" ;;
    --prompts|-p)   MODE="prompts" ;;
    --session)      shift; SESSION_ID="$1" ;;
    --help|-h)
      echo "Usage: sh scripts/show-audit.sh [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --follow, -f     Live tail mode"
      echo "  --decisions, -d  Show DECISION events only"
      echo "  --summary, -s    Show statistics summary"
      echo "  --prompts, -p    List saved prompts"
      echo "  --session ID     Show specific session"
      echo "  --help, -h       Show this help"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
  shift
done

# Resolve session
if [ -z "$SESSION_ID" ]; then
  SESSION_ID_FILE="$AUDIT_DIR/session-id.txt"
  if [ -f "$SESSION_ID_FILE" ]; then
    SESSION_ID=$(cat "$SESSION_ID_FILE")
  else
    echo "No active audit session found. Run an RTL skill first."
    exit 1
  fi
fi

TRACE_FILE="$AUDIT_DIR/$SESSION_ID/trace.jsonl"
PROMPTS_DIR="$AUDIT_DIR/$SESSION_ID/prompts"

if [ ! -f "$TRACE_FILE" ] && [ "$MODE" != "follow" ]; then
  echo "No trace file found: $TRACE_FILE"
  exit 1
fi

# Color mapping for event types
color_for_event() {
  case "$1" in
    spawn_start)    printf '%b' "$C_MAGENTA" ;;
    spawn_complete) printf '%b' "$C_MAGENTA" ;;
    skill_invoke)   printf '%b' "$C_CYAN" ;;
    artifact_write) printf '%b' "$C_GREEN" ;;
    decision)       printf '%b' "$C_BLUE" ;;
    *)              printf '%b' "$C_DIM" ;;
  esac
}

# Format a single trace line
format_line() {
  LINE="$1"
  # Parse with available JSON parser
  if command -v jq >/dev/null 2>&1; then
    TS=$(printf '%s' "$LINE" | jq -r '.ts // ""' 2>/dev/null)
    SEQ=$(printf '%s' "$LINE" | jq -r '.seq // ""' 2>/dev/null)
    EVENT=$(printf '%s' "$LINE" | jq -r '.event // ""' 2>/dev/null)
    AGENT=$(printf '%s' "$LINE" | jq -r '.agent // ""' 2>/dev/null)
    DETAIL=$(printf '%s' "$LINE" | jq -r '.detail // ""' 2>/dev/null)
    STATUS=$(printf '%s' "$LINE" | jq -r '.status // ""' 2>/dev/null)
    PHASE=$(printf '%s' "$LINE" | jq -r '.phase // ""' 2>/dev/null)
    TAG=$(printf '%s' "$LINE" | jq -r '.tag // ""' 2>/dev/null)
  else
    # Fallback: basic sed parsing
    TS=$(printf '%s' "$LINE" | sed -n 's/.*"ts"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    SEQ=$(printf '%s' "$LINE" | sed -n 's/.*"seq"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p')
    EVENT=$(printf '%s' "$LINE" | sed -n 's/.*"event"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    AGENT=$(printf '%s' "$LINE" | sed -n 's/.*"agent"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    DETAIL=$(printf '%s' "$LINE" | sed -n 's/.*"detail"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    STATUS=$(printf '%s' "$LINE" | sed -n 's/.*"status"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
    PHASE=$(printf '%s' "$LINE" | sed -n 's/.*"phase"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p')
    TAG=$(printf '%s' "$LINE" | sed -n 's/.*"tag"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
  fi

  # Apply filter
  if [ -n "$FILTER" ] && [ "$EVENT" != "$FILTER" ]; then
    return
  fi

  # Format time (extract HH:MM:SS from ISO timestamp)
  SHORT_TS=$(printf '%s' "$TS" | sed 's/.*T\([0-9:]*\).*/\1/')

  COLOR=$(color_for_event "$EVENT")

  # Status indicator
  STATUS_ICON=""
  case "$STATUS" in
    success)  STATUS_ICON="${C_GREEN}OK${C_RESET}" ;;
    failed)   STATUS_ICON="${C_RED}FAIL${C_RESET}" ;;
    started)  STATUS_ICON="${C_YELLOW}...${C_RESET}" ;;
  esac

  PHASE_STR=""
  [ -n "$PHASE" ] && PHASE_STR=" P${PHASE}"

  TAG_STR=""
  [ -n "$TAG" ] && TAG_STR=" ${C_DIM}${TAG}${C_RESET}"

  printf "%b%s%b %b%-3s%b %b%-15s%b %-25s %s %s%s\n" \
    "$C_DIM" "$SHORT_TS" "$C_RESET" \
    "$COLOR" "$SEQ" "$C_RESET" \
    "$COLOR" "$EVENT" "$C_RESET" \
    "$AGENT" \
    "$STATUS_ICON" \
    "$DETAIL" \
    "$TAG_STR"
}

# Mode: timeline
show_timeline() {
  printf "%b%s%b\n" "$C_BOLD" "=== Audit Trace: $SESSION_ID ===" "$C_RESET"
  printf "%b%-8s %-3s %-15s %-25s %-6s %s%b\n" "$C_DIM" "TIME" "SEQ" "EVENT" "AGENT" "STATUS" "DETAIL" "$C_RESET"
  printf "%b%s%b\n" "$C_DIM" "─────────────────────────────────────────────────────────────────────────────────" "$C_RESET"

  while IFS= read -r line; do
    [ -z "$line" ] && continue
    format_line "$line"
  done < "$TRACE_FILE"
}

# Mode: follow
show_follow() {
  printf "%b%s%b\n" "$C_BOLD" "=== Live Audit Trace: $SESSION_ID (Ctrl+C to exit) ===" "$C_RESET"
  mkdir -p "$(dirname "$TRACE_FILE")"
  touch "$TRACE_FILE"
  tail -f "$TRACE_FILE" 2>/dev/null | while IFS= read -r line; do
    [ -z "$line" ] && continue
    format_line "$line"
  done
}

# Mode: summary
show_summary() {
  if ! command -v jq >/dev/null 2>&1; then
    echo "Summary mode requires jq. Install jq or use timeline mode."
    exit 1
  fi

  TOTAL=$(wc -l < "$TRACE_FILE" | tr -d ' ')
  SPAWN_COUNT=$(grep -c '"spawn_start"' "$TRACE_FILE" || true)
  SKILL_COUNT=$(grep -c '"skill_invoke"' "$TRACE_FILE" || true)
  ARTIFACT_COUNT=$(grep -c '"artifact_write"' "$TRACE_FILE" || true)
  DECISION_COUNT=$(grep -c '"decision"' "$TRACE_FILE" || true)

  printf "%b%s%b\n" "$C_BOLD" "=== Audit Summary: $SESSION_ID ===" "$C_RESET"
  echo ""
  printf "  Total events:     %s\n" "$TOTAL"
  printf "  Agent spawns:     %s\n" "$SPAWN_COUNT"
  printf "  Skill invocations:%s\n" "$SKILL_COUNT"
  printf "  Artifacts written:%s\n" "$ARTIFACT_COUNT"
  printf "  Decisions:        %s\n" "$DECISION_COUNT"
  echo ""

  # Decision source breakdown
  if [ "$DECISION_COUNT" -gt 0 ]; then
    printf "%b  Decision Sources:%b\n" "$C_BOLD" "$C_RESET"
    for src in USER_CONFIRMED SPEC_DERIVED AGENT_ASSUMED; do
      CNT=$(grep -c "\"$src\"" "$TRACE_FILE" || true)
      printf "    %-20s %s\n" "$src:" "$CNT"
    done
    echo ""
  fi

  # Phase distribution
  printf "%b  Phase Distribution:%b\n" "$C_BOLD" "$C_RESET"
  for p in 1 2 3 4 5 6 7; do
    CNT=$(grep -c "\"phase\":${p}" "$TRACE_FILE" || true)
    if [ "$CNT" -gt 0 ]; then
      printf "    Phase %s: %s events\n" "$p" "$CNT"
    fi
  done
}

# Mode: prompts
show_prompts() {
  if [ ! -d "$PROMPTS_DIR" ]; then
    echo "No prompts directory found."
    exit 0
  fi

  printf "%b%s%b\n" "$C_BOLD" "=== Saved Prompts: $SESSION_ID ===" "$C_RESET"

  for f in "$PROMPTS_DIR"/*.md; do
    [ -f "$f" ] || continue
    FNAME=$(basename "$f")
    SIZE=$(wc -c < "$f" | tr -d ' ')
    printf "  %b%-40s%b %s bytes\n" "$C_CYAN" "$FNAME" "$C_RESET" "$SIZE"
  done
}

# Dispatch
case "$MODE" in
  timeline)  show_timeline ;;
  follow)    show_follow ;;
  summary)   show_summary ;;
  prompts)   show_prompts ;;
esac
