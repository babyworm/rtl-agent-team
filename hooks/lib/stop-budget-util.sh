#!/bin/sh
# stop-budget-util.sh — no-progress breaker shared by the Stop gates.
# Requires: json-util.sh and hook-output-util.sh sourced.
#
# A Stop gate blocks (Claude keeps working) until it has blocked N times in one
# continuation chain while its progress stayed the same; on the next Stop it lets
# Claude stop and shows its notice to the user. A chain starts at the first Stop
# after a user turn (stop_hook_active false) and lasts while Stop blocks from any
# hook keep the turn going. A change in the gate's progress text restarts the
# count, but only before the notice: a gate that showed its notice stays silent
# for the rest of the chain whatever its progress, because the notice tells the
# user the gate will ask again on their next message.
#
# Each gate also counts the chain's Stops itself (line 3), whoever blocked them,
# so blocks by other plugins' Stop hooks count, gates that block together keep
# their own limit, and no gate reads another gate's file. From the chain's Stop
# STOPU_CHAIN_CAP + 1 on, a gate that would block shows its notice instead: the
# notice comes after at most STOPU_CHAIN_CAP (6 by default) consecutive blocked
# Stops from any hooks, under Claude Code's own cap, which counts consecutive Stops
# that any hook blocked, once per Stop, and past CLAUDE_CODE_STOP_HOOK_BLOCK_CAP
# (default 8; 0 disables it) overrides the block and ends the turn with a warning
# and an empty result (CLI 2.1.282). When the user sets that variable,
# STOPU_CHAIN_CAP follows it: two Stops under it (at least 1), or 99999 when it is
# 0, which keeps Stop counts under stopu_count_line's six-digit guard. A
# continuation Stop whose budget file is missing, has no valid Stop count, or was
# written for another prompt (line 5) means the gate missed the chain start: the
# gate assumes the worst case and hands over instead of blocking blind. An input
# without prompt_id cannot tell a leftover file from an earlier prompt, so its
# count is trusted.
#
# N is RAT_STOP_BLOCK_LIMIT (default 3; invalid values fall back to 3). A gate may
# pass a lower per-call limit, never a higher one, so RAT_STOP_BLOCK_LIMIT=0 turns
# every block into a notice.
#
# Caller contract: every gate calls STOP_CHAIN=$(stopu_chain_active "$INPUT"
# <state-dir> <ids>) on every Stop, right after its team-mode skip and before any
# other exit; the Stop count depends on it. At a chain start the call sets the
# count to 1 whatever files are left over, and every continuation adds 1. Once the
# gate's condition is satisfied, call stopu_clear: it resets lines 1, 2 and 4 but
# keeps the Stop count, so a gate that blocks again later in the chain still
# hands over in time. A gate that counts its own attempts asks stopu_decision
# before counting one, so a Stop that ends in a notice or silence is no attempt.
#
# Budget file: <state-dir>/stop-budget-<gate-id>.txt. Line 1 counts the blocks
# without progress, line 2 holds the progress fingerprint, line 3 is this chain's
# Stop number as seen by this gate, line 4 is 1 once the gate showed its notice in
# this chain (0 otherwise), and line 5 is the prompt_id of the Stop that last wrote
# the file (empty when the input has none). Budgets are per project, so two
# sessions working in one project share them; Claude Code's own Stop block cap,
# unless the user disables it, still bounds each session.

STOPU_CHAIN_CAP=6
# Follow Claude Code's own cap when the user changed it: stay two Stops under it
# (at least 1), or lift the cap when it is disabled (0). The no-progress limit
# still applies either way. Anything but a plain number of up to five digits keeps
# 6. A leading zero counts as not plain, because $((...)) reads it as octal or
# fails on it.
case "${CLAUDE_CODE_STOP_HOOK_BLOCK_CAP:-}" in
  ''|*[!0-9]*|0?*|??????*) ;;
  0) STOPU_CHAIN_CAP=99999 ;;
  1|2) STOPU_CHAIN_CAP=1 ;;
  *) STOPU_CHAIN_CAP=$((CLAUDE_CODE_STOP_HOOK_BLOCK_CAP - 2)) ;;
esac

# Print "true" when this Stop continues a chain started by an earlier block, and
# count the chain's Stops for each named gate: line 3 of its budget file is 1 at the
# chain start and grows by one on every later Stop of the chain, whoever blocked.
# A continuation that finds no file (the gate missed the chain start) records the
# worst case, so the gate hands over instead of blocking blind. Line 5 records the
# Stop's prompt_id, so a file written for another prompt is a missed chain start
# too.
# Usage: STOP_CHAIN=$(stopu_chain_active "$INPUT" [<state-dir> <gate-id>...])
stopu_chain_active() {
  if printf '%s' "$1" | grep -Eq '"stop_hook_active"[[:space:]]*:[[:space:]]*true'; then
    _SCA_CHAIN=true
  else
    _SCA_CHAIN=false
  fi
  if [ -n "${2:-}" ]; then
    _SCA_PROMPT=$(stopu_prompt_id "$1")
    _SCA_DIR=$2
    shift 2
    mkdir -p "$_SCA_DIR" 2>/dev/null
    for _SCA_ID in "$@"; do
      _SCA_FILE="$_SCA_DIR/stop-budget-$_SCA_ID.txt"
      if [ "$_SCA_CHAIN" = "false" ]; then
        { printf '0\n\n1\n0\n%s\n' "$_SCA_PROMPT" > "$_SCA_FILE"; } 2>/dev/null
      elif [ -f "$_SCA_FILE" ] && { [ -z "$_SCA_PROMPT" ] || [ "$(sed -n '5p' "$_SCA_FILE")" = "$_SCA_PROMPT" ]; }; then
        _SCA_L1=$(sed -n '1p' "$_SCA_FILE")
        _SCA_L2=$(sed -n '2p' "$_SCA_FILE")
        _SCA_L4=$(sed -n '4p' "$_SCA_FILE")
        _SCA_STOPS=$(stopu_count_line "$_SCA_FILE" 3)
        [ "$_SCA_STOPS" -ge 1 ] || _SCA_STOPS=$STOPU_CHAIN_CAP
        { printf '%s\n%s\n%s\n%s\n%s\n' "$_SCA_L1" "$_SCA_L2" "$((_SCA_STOPS + 1))" "$_SCA_L4" "$_SCA_PROMPT" > "$_SCA_FILE"; } 2>/dev/null
      else
        # No file, or one written for another prompt: this gate missed the chain start.
        { printf '0\n\n%s\n0\n%s\n' "$((STOPU_CHAIN_CAP + 1))" "$_SCA_PROMPT" > "$_SCA_FILE"; } 2>/dev/null
      fi
    done
  fi
  printf '%s' "$_SCA_CHAIN"
}

# Reduce arbitrary text to a one-token fingerprint.
# Usage: FP=$(stopu_fingerprint "text")
stopu_fingerprint() {
  printf '%s' "$1" | cksum | awk '{printf "%s-%s", $1, $2}'
}

# Print the prompt id of a hook input (Claude Code's UUID for the user prompt a
# Stop belongs to), or nothing when the input has none or it is not a plain token.
# Usage: PROMPT=$(stopu_prompt_id "$INPUT")
stopu_prompt_id() {
  _SPI=$(jsonu_get_input_string "$1" "prompt_id")
  case "$_SPI" in *[!0-9A-Za-z-]*) _SPI="" ;; esac
  printf '%s' "$_SPI"
}

# Block, or hand over to the user once the chain's budget is spent. Always exits.
# <progress> is any text that changes when the gate's condition moves.
# Usage: stopu_gate <gate-id> <state-dir> "$STOP_CHAIN" <progress> <reason> <notice> [limit]
stopu_gate() {
  _stopu_decide "$1" "$2" "$3" "$4" "${7:-}"
  [ "$_SG_DECISION" = "silent" ] && emit_post_continue
  mkdir -p "$2" 2>/dev/null
  if [ "$_SG_DECISION" = "notice" ]; then
    { printf '%s\n%s\n%s\n1\n%s\n' "$_SG_COUNT" "$_SG_FP" "$_SG_STOPS" "$_SG_PROMPT" > "$_SG_FILE"; } 2>/dev/null
    emit_stop_notice "$6"
  fi
  # Record the block before making it. If it cannot be recorded the count never
  # advances, so hand over to the user instead of blocking without a bound.
  if ! { printf '%s\n%s\n%s\n0\n%s\n' "$((_SG_COUNT + 1))" "$_SG_FP" "$_SG_STOPS" "$_SG_PROMPT" > "$_SG_FILE"; } 2>/dev/null; then
    emit_stop_notice "$6"
  fi
  emit_stop_block "$5"
}

# Print what stopu_gate would do now (block, notice or silent) without writing
# anything. A gate that keeps its own attempt counter asks first and counts only
# the Stops it blocks. The answer is only a prediction: the gate still ends the
# Stop through stopu_gate (the only call that records a block, sets the notice
# flag and hands over when the budget cannot be written), with the same id,
# chain flag, progress and limit, or a lower limit when that Stop counts nothing.
# Usage: DECISION=$(stopu_decision <gate-id> <state-dir> "$STOP_CHAIN" <progress> [limit])
stopu_decision() {
  _stopu_decide "$1" "$2" "$3" "$4" "${5:-}"
  printf '%s' "$_SG_DECISION"
}

# Read the budget and decide, writing nothing: sets _SG_DECISION to silent, notice
# or block, and _SG_FILE, _SG_FP, _SG_LIMIT, _SG_COUNT, _SG_STOPS and _SG_PROMPT
# for stopu_gate to act on.
# Usage: _stopu_decide <gate-id> <state-dir> "$STOP_CHAIN" <progress> [limit]
_stopu_decide() {
  _SG_FILE="$2/stop-budget-$1.txt"
  _SG_FP=$(stopu_fingerprint "$4")
  _SG_LIMIT=${RAT_STOP_BLOCK_LIMIT:-3}
  case "$_SG_LIMIT" in ''|*[!0-9]*|??????*) _SG_LIMIT=3 ;; esac
  case "${5:-}" in
    ''|*[!0-9]*|??????*) ;;
    *) [ "$5" -lt "$_SG_LIMIT" ] && _SG_LIMIT=$5 ;;
  esac
  _SG_COUNT=0
  _SG_STOPS=1
  _SG_PROMPT=$(sed -n '5p' "$_SG_FILE" 2>/dev/null)
  if [ "$3" = "true" ]; then
    _SG_STOPS=$((STOPU_CHAIN_CAP + 1))
    if [ -f "$_SG_FILE" ]; then
      # A gate that already showed its notice stays silent until the chain ends.
      if [ "$(sed -n '4p' "$_SG_FILE")" = "1" ]; then
        _SG_DECISION=silent
        return 0
      fi
      _SG_STOPS=$(stopu_count_line "$_SG_FILE" 3)
      [ "$_SG_STOPS" -ge 1 ] || _SG_STOPS=$((STOPU_CHAIN_CAP + 1))
      _SG_COUNT=$(stopu_count_line "$_SG_FILE" 1)
      [ "$(sed -n '2p' "$_SG_FILE")" = "$_SG_FP" ] || _SG_COUNT=0
    fi
  fi
  # Hand over after N blocks without progress, or once the chain has already had
  # STOPU_CHAIN_CAP blocked Stops from any hook.
  if [ "$_SG_COUNT" -ge "$_SG_LIMIT" ] || [ "$_SG_STOPS" -gt "$STOPU_CHAIN_CAP" ]; then
    _SG_DECISION=notice
  else
    _SG_DECISION=block
  fi
}

# Print line <n> of a budget file as a count; anything but a plain number is 0.
# Usage: N=$(stopu_count_line <file> <n>)
stopu_count_line() {
  _SCL=$(sed -n "${2}p" "$1" 2>/dev/null)
  case "$_SCL" in ''|*[!0-9]*|0?*|??????*) _SCL=0 ;; esac
  printf '%s' "$_SCL"
}

# Reset a gate's budget once its condition is satisfied. The chain's Stop count
# stays, so the chain cap still counts the Stops before this one.
# Usage: stopu_clear <gate-id> <state-dir>
stopu_clear() {
  _SC_FILE="$2/stop-budget-$1.txt"
  [ -f "$_SC_FILE" ] || return 0
  _SC_TOTAL=$(stopu_count_line "$_SC_FILE" 3)
  _SC_PROMPT=$(sed -n '5p' "$_SC_FILE")
  { printf '0\n\n%s\n0\n%s\n' "$_SC_TOTAL" "$_SC_PROMPT" > "$_SC_FILE"; } 2>/dev/null
}
