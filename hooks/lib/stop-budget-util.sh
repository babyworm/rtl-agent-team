#!/bin/sh
# stop-budget-util.sh — no-progress breaker shared by the Stop gates.
# Requires: json-util.sh and hook-output-util.sh sourced.
#
# A Stop gate blocks (Claude keeps working) until it has blocked
# RAT_STOP_BLOCK_LIMIT times (default 3) in one continuation chain while its
# progress fingerprint stayed the same; then it lets Claude stop and shows a
# notice to the user instead. A chain starts at the first Stop after a user
# turn (stop_hook_active false) and lasts while Stop blocks keep the turn
# going. A changed fingerprint means the gate's condition moved, which restarts
# the count. RAT_STOP_BLOCK_LIMIT=0 turns every block into a notice.

# Print "true" when this Stop continues a chain started by an earlier block.
# Usage: stopu_chain_active "$INPUT"
stopu_chain_active() {
  if printf '%s' "$1" | grep -Eq '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
    printf 'true'
  else
    printf 'false'
  fi
}

# Reduce arbitrary text to a one-token progress fingerprint.
# Usage: FP=$(stopu_fingerprint "text")
stopu_fingerprint() {
  printf '%s' "$1" | cksum | awk '{printf "%s-%s", $1, $2}'
}

# Block, or hand over to the user once the chain's budget is spent. Always exits.
# Usage: stopu_gate <gate-id> <state-dir> <chain-active> <fingerprint> <reason> <notice> [limit]
stopu_gate() {
  _SG_FILE="$2/stop-budget-$1.txt"
  _SG_LIMIT=${7:-${RAT_STOP_BLOCK_LIMIT:-3}}
  case "$_SG_LIMIT" in ''|*[!0-9]*) _SG_LIMIT=3 ;; esac
  _SG_COUNT=0
  if [ "$3" = "true" ] && [ -f "$_SG_FILE" ]; then
    _SG_COUNT=$(sed -n '1p' "$_SG_FILE")
    case "$_SG_COUNT" in ''|*[!0-9]*) _SG_COUNT=0 ;; esac
    [ "$(sed -n '2p' "$_SG_FILE")" = "$4" ] || _SG_COUNT=0
  fi
  if [ "$_SG_COUNT" -ge "$_SG_LIMIT" ]; then
    emit_stop_notice "$6"
  fi
  # Record the budget before blocking. If it cannot be recorded the count never
  # advances, so hand over to the user instead of blocking without a bound.
  mkdir -p "$2" 2>/dev/null
  if ! { printf '%s\n%s\n' "$((_SG_COUNT + 1))" "$4" > "$_SG_FILE"; } 2>/dev/null; then
    emit_stop_notice "$6"
  fi
  emit_stop_block "$5"
}

# Forget a gate's budget once its condition is satisfied.
# Usage: stopu_clear <gate-id> <state-dir>
stopu_clear() {
  rm -f "$2/stop-budget-$1.txt" 2>/dev/null
}
