#!/bin/sh
# stop-budget-util.sh — no-progress breaker shared by the Stop gates.
# Requires: json-util.sh and hook-output-util.sh sourced.
#
# A Stop gate blocks (Claude keeps working) until it has blocked N times in one
# continuation chain while its progress stayed the same; on the next Stop it lets
# Claude stop and shows its notice to the user. A chain starts at the first Stop
# after a user turn (stop_hook_active false) and lasts while Stop blocks keep the
# turn going. A change in the gate's progress text restarts the count, but only
# before the notice: a gate that showed its notice stays silent for the rest of
# the chain whatever its progress, because the notice tells the user the gate
# will ask again on their next message.
#
# The cap is shared by the chain. While a chain continues, a gate hands over once
# the blocks of every gate in the chain (line 3 summed over all budget files in the
# state dir, its own included) reach STOPU_CHAIN_CAP (6). Each blocked Stop raises
# at least one gate's line 3, so the sum is at least the number of blocked Stops,
# and the notice arrives before Claude Code's own cap of 8 consecutive blocks ends
# the turn with an empty result. At a chain start the other gates' files are
# ignored, because they may not be cleared yet.
#
# N is RAT_STOP_BLOCK_LIMIT (default 3; invalid values fall back to 3). A gate may
# pass a lower per-call limit, never a higher one, so RAT_STOP_BLOCK_LIMIT=0 turns
# every block into a notice.
#
# Caller contract: set STOP_CHAIN=$(stopu_chain_active "$INPUT" <state-dir> <ids>)
# right after the team-mode skip and before any other exit. That call deletes the
# gate's budget files at the start of each chain, whichever path the gate takes
# next. Once the gate's condition is satisfied, call stopu_clear: it resets the
# count, the fingerprint and the notice flag but keeps the chain total, so a
# satisfied gate cannot erase blocks it already made from the shared sum.
#
# Budget file: <state-dir>/stop-budget-<gate-id>.txt. Line 1 counts the blocks
# without progress, line 2 holds the progress fingerprint, line 3 counts this
# gate's blocks in the chain (a progress change does not reset it), and line 4 is
# 1 once the gate showed its notice in this chain (0 otherwise). Budgets are per
# project, so two sessions working in one project share them; Claude Code's own
# Stop block cap (8 consecutive blocks, measured on CLI 2.1.282) still bounds each
# session.

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
  _SG_SUM=0
  if [ "$3" = "true" ]; then
    if [ -f "$_SG_FILE" ]; then
      # A gate that already showed its notice stays silent until the chain ends.
      [ "$(sed -n '4p' "$_SG_FILE")" = "1" ] && emit_post_continue
      _SG_TOTAL=$(stopu_count_line "$_SG_FILE" 3)
      _SG_COUNT=$(stopu_count_line "$_SG_FILE" 1)
      [ "$(sed -n '2p' "$_SG_FILE")" = "$_SG_FP" ] || _SG_COUNT=0
    fi
    # Blocks by every gate in this chain; each blocked Stop counts at least once.
    for _SG_OTHER in "$2"/stop-budget-*.txt; do
      [ -f "$_SG_OTHER" ] || continue
      _SG_SUM=$((_SG_SUM + $(stopu_count_line "$_SG_OTHER" 3)))
    done
  fi
  mkdir -p "$2" 2>/dev/null
  if [ "$_SG_COUNT" -ge "$_SG_LIMIT" ] || [ "$_SG_SUM" -ge "$STOPU_CHAIN_CAP" ]; then
    { printf '%s\n%s\n%s\n1\n' "$_SG_COUNT" "$_SG_FP" "$_SG_TOTAL" > "$_SG_FILE"; } 2>/dev/null
    emit_stop_notice "$6"
  fi
  # Record the block before making it. If it cannot be recorded the counts never
  # advance, so hand over to the user instead of blocking without a bound.
  if ! { printf '%s\n%s\n%s\n0\n' "$((_SG_COUNT + 1))" "$_SG_FP" "$((_SG_TOTAL + 1))" > "$_SG_FILE"; } 2>/dev/null; then
    emit_stop_notice "$6"
  fi
  emit_stop_block "$5"
}

# Print line <n> of a budget file as a count; anything but a plain number is 0.
# Usage: N=$(stopu_count_line <file> <n>)
stopu_count_line() {
  _SCL=$(sed -n "${2}p" "$1" 2>/dev/null)
  case "$_SCL" in ''|*[!0-9]*|0?*|??????*) _SCL=0 ;; esac
  printf '%s' "$_SCL"
}

# Reset a gate's budget once its condition is satisfied. The chain's block total
# stays, so the shared cap still counts the blocks this gate already made.
# Usage: stopu_clear <gate-id> <state-dir>
stopu_clear() {
  _SC_FILE="$2/stop-budget-$1.txt"
  [ -f "$_SC_FILE" ] || return 0
  _SC_TOTAL=$(stopu_count_line "$_SC_FILE" 3)
  { printf '0\n\n%s\n0\n' "$_SC_TOTAL" > "$_SC_FILE"; } 2>/dev/null
}
