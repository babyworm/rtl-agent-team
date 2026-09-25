#!/bin/sh
# stop-budget-util.sh — no-progress breaker shared by the Stop gates.
# Requires: json-util.sh and hook-output-util.sh sourced.
#
# A Stop gate blocks (Claude keeps working) until it has blocked N times in one
# continuation chain while its progress stayed the same; on the next Stop it lets
# Claude stop and shows its notice to the user once, then stays silent for the
# rest of that chain. A chain starts at the first Stop after a user turn
# (stop_hook_active false) and lasts while Stop blocks keep the turn going. A
# change in the gate's progress text restarts the count. A gate also hands over
# after STOPU_CHAIN_CAP (6) blocks in one chain whatever its progress, so its
# notice arrives before Claude Code's own cap of 8 consecutive blocks ends the
# turn with an empty result.
#
# N is RAT_STOP_BLOCK_LIMIT (default 3; invalid values fall back to 3). A gate may
# pass a lower per-call limit, never a higher one, so RAT_STOP_BLOCK_LIMIT=0 turns
# every block into a notice.
#
# Caller contract: set STOP_CHAIN=$(stopu_chain_active "$INPUT" <state-dir> <ids>)
# right after the team-mode skip and before any other exit. That call resets the
# gate's budgets at the start of each chain, whichever path the gate takes next.
#
# Budget file: <state-dir>/stop-budget-<gate-id>.txt. Line 1 counts the blocks
# without progress, line 2 holds the progress fingerprint, and line 3 counts this
# gate's blocks in the chain (a progress change does not reset it; the file is
# still removed at chain start). A line-1 count of N+1 or a line-3 count above the
# cap means the notice was already shown in this chain. Budgets are per project,
# so two sessions working in one project share them; Claude Code's own Stop block
# cap (8 consecutive blocks, measured on CLI 2.1.282) still bounds each session.

STOPU_CHAIN_CAP=6

# Print "true" when this Stop continues a chain started by an earlier block.
# At the start of a chain, remove the named gates' budget files.
# Usage: STOP_CHAIN=$(stopu_chain_active "$INPUT" [<state-dir> <gate-id>...])
stopu_chain_active() {
  if printf '%s' "$1" | grep -Eq '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
    printf 'true'
    return 0
  fi
  if [ -n "${2:-}" ]; then
    _SCA_DIR=$2
    shift 2
    for _SCA_ID in "$@"; do
      rm -f "$_SCA_DIR/stop-budget-$_SCA_ID.txt" 2>/dev/null
    done
  fi
  printf 'false'
}

# Reduce arbitrary text to a one-token fingerprint.
# Usage: FP=$(stopu_fingerprint "text")
stopu_fingerprint() {
  printf '%s' "$1" | cksum | awk '{printf "%s-%s", $1, $2}'
}

# Block, or hand over to the user once the chain's budget is spent. Always exits.
# <progress> is any text that changes when the gate's condition moves.
# Usage: stopu_gate <gate-id> <state-dir> "$STOP_CHAIN" <progress> <reason> <notice> [limit]
stopu_gate() {
  _SG_FILE="$2/stop-budget-$1.txt"
  _SG_FP=$(stopu_fingerprint "$4")
  _SG_LIMIT=${RAT_STOP_BLOCK_LIMIT:-3}
  case "$_SG_LIMIT" in ''|*[!0-9]*|??????*) _SG_LIMIT=3 ;; esac
  case "${7:-}" in
    ''|*[!0-9]*|??????*) ;;
    *) [ "$7" -lt "$_SG_LIMIT" ] && _SG_LIMIT=$7 ;;
  esac
  _SG_COUNT=0
  _SG_TOTAL=0
  if [ "$3" = "true" ] && [ -f "$_SG_FILE" ]; then
    _SG_TOTAL=$(sed -n '3p' "$_SG_FILE")
    case "$_SG_TOTAL" in ''|*[!0-9]*|0?*|??????*) _SG_TOTAL=0 ;; esac
    _SG_COUNT=$(sed -n '1p' "$_SG_FILE")
    case "$_SG_COUNT" in ''|*[!0-9]*|0?*|??????*) _SG_COUNT=0 ;; esac
    [ "$(sed -n '2p' "$_SG_FILE")" = "$_SG_FP" ] || _SG_COUNT=0
  fi
  # The notice was already shown in this chain: stay silent until the chain ends.
  if [ "$_SG_TOTAL" -gt "$STOPU_CHAIN_CAP" ] || [ "$_SG_COUNT" -gt "$_SG_LIMIT" ]; then
    emit_post_continue
  fi
  # Record the budget before acting. If it cannot be recorded the count never
  # advances, so hand over to the user instead of blocking without a bound.
  mkdir -p "$2" 2>/dev/null
  if ! { printf '%s\n%s\n%s\n' "$((_SG_COUNT + 1))" "$_SG_FP" "$((_SG_TOTAL + 1))" > "$_SG_FILE"; } 2>/dev/null; then
    emit_stop_notice "$6"
  fi
  if [ "$_SG_TOTAL" -ge "$STOPU_CHAIN_CAP" ] || [ "$_SG_COUNT" -ge "$_SG_LIMIT" ]; then
    emit_stop_notice "$6"
  fi
  emit_stop_block "$5"
}

# Forget a gate's budget once its condition is satisfied.
# Usage: stopu_clear <gate-id> <state-dir>
stopu_clear() {
  rm -f "$2/stop-budget-$1.txt" 2>/dev/null
}
