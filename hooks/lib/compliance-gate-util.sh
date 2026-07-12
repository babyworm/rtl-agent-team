#!/bin/sh
# compliance-gate-util.sh — Compliance-pass auto-resolution for skill completion gate.
# Requires: json-util.sh and flock-util.sh sourced and parser detected.
#
# Usage:
#   . "$SCRIPT_DIR/lib/compliance-gate-util.sh"
#   compliance_preprocess "$SKILL_STATE" "$STATE_DIR" "$PENDING"
#   PENDING="$_CGU_PENDING"           # possibly updated pending string
#   # $_CGU_DYN_MSG is set if compliance FAIL produced a dynamic prompt addition

# compliance_preprocess <skill_state_path> <state_dir> <pending>
#
# Performs compliance-pass detection and auto-resolution:
# - If compliance-report.json exists with PASS verdict, removes "compliance-pass" from pending
# - If compliance-report.json exists with non-PASS verdict, injects authority-specific budgets
#   and dynamic prompt into the skill state file
# - If infeasibility is detected and iteration exceeds primary budget, sets upstream_challenge strategy
#
# Output variables (set after call):
#   _CGU_PENDING  — the (possibly modified) pending string
#   _CGU_DYN_MSG  — dynamic prompt message from compliance FAIL (empty if PASS or no report)

# _cgu_mtime <path> — print file mtime as epoch seconds (empty if unavailable).
# Self-contained (mirrors posix-util.sh get_mtime_epoch) so this lib does not
# depend on the caller having sourced posix-util.sh.
_cgu_mtime() {
  [ ! -e "$1" ] && return 0
  stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || printf ''
}

compliance_preprocess() {
  _CGU_SKILL_STATE="$1"
  _CGU_STATE_DIR="$2"
  _CGU_PENDING="$3"
  _CGU_DYN_MSG=""

  _CGU_HAS_COMPLIANCE=$(echo "$_CGU_PENDING" | grep -c "compliance-pass" 2>/dev/null || true)

  _CGU_CR_REPORT="$_CGU_STATE_DIR/compliance-report.json"
  if [ ! -f "$_CGU_CR_REPORT" ]; then
    # No compliance report — clear all stale compliance state
    # (runs even if compliance-pass is not in pending, to catch stale overrides)
    # (report may have been removed after requirement amendment)
    _CGU_CUR_STRAT=$(jsonu_get_file_path_string "$_CGU_SKILL_STATE" "strategy")
    _CGU_CUR_AUTH=$(jsonu_get_file_path_num "$_CGU_SKILL_STATE" "compliance_authority")
    _CGU_CUR_MAXP=$(jsonu_get_file_path_num "$_CGU_SKILL_STATE" "max_primary")
    if [ "$_CGU_CUR_STRAT" = "upstream_challenge" ] || \
       { [ -n "$_CGU_CUR_AUTH" ] && [ "$_CGU_CUR_AUTH" -gt 0 ] 2>/dev/null; } || \
       { [ -n "$_CGU_CUR_MAXP" ] && [ "$_CGU_CUR_MAXP" -gt 0 ] 2>/dev/null; }; then
      if acquire_lock "$_CGU_SKILL_STATE"; then
        _CGU_NR_SED=$(mktemp "${TMPDIR:-/tmp}/cgu-nr-sed.XXXXXX" 2>/dev/null || echo "$_CGU_SKILL_STATE.nr-sed")
        {
          printf 's/"strategy"[[:space:]]*:[[:space:]]*"upstream_challenge"/"strategy": "primary"/\n'
          printf 's/"max_primary"[[:space:]]*:[[:space:]]*[0-9]*/"max_primary": 0/\n'
          printf 's/"max_fallback"[[:space:]]*:[[:space:]]*[0-9]*/"max_fallback": 0/\n'
          printf 's/"dynamic_prompt"[[:space:]]*:[[:space:]]*"[^"]*"/"dynamic_prompt": ""/\n'
          printf 's/"compliance_authority"[[:space:]]*:[[:space:]]*[0-9]*/"compliance_authority": 0/\n'
        } > "$_CGU_NR_SED"
        if sed -f "$_CGU_NR_SED" "$_CGU_SKILL_STATE" > "$_CGU_SKILL_STATE.tmp" 2>/dev/null; then
          mv "$_CGU_SKILL_STATE.tmp" "$_CGU_SKILL_STATE"
        else
          rm -f "$_CGU_SKILL_STATE.tmp" 2>/dev/null
        fi
        rm -f "$_CGU_NR_SED" 2>/dev/null
        release_lock "$_CGU_SKILL_STATE"
      fi
    fi
    return 0
  fi

  # Phase-freshness guard (prevents cross-phase stale PASS/FAIL bleed):
  # compliance-report.json is a SHARED path that the compliance-checker overwrites
  # each phase. rtl-phase-state-bootstrap.sh rewrites compliance-state.json (giving
  # it a fresh mtime) whenever the active phase changes. If the report predates the
  # current phase marker, it belongs to an upstream phase (e.g. a stale P2 PASS) and
  # must NOT auto-satisfy the current phase's compliance-pass — leaving it pending
  # forces this phase's own compliance check to produce a fresh report. Ignore the
  # report entirely in that case (skill-active.json is created fresh per skill, so
  # there are no cross-phase overrides to clear here).
  _CGU_PHASE_STATE="$_CGU_STATE_DIR/compliance-state.json"
  if [ -f "$_CGU_PHASE_STATE" ]; then
    # Primary guard: phase-keyed. compliance-checker stamps the report's "phase"
    # with the invoking skill's short-name; compliance-state.json carries the
    # current phase's short-name (written by rtl-phase-state-bootstrap). When
    # BOTH are present, an exact match means the report belongs to THIS phase
    # (fresh); a mismatch means it is a stale upstream report — do not resolve.
    # When either side lacks a phase (legacy report / pre-bootstrap), fall back
    # to the mtime comparison (report older than the phase marker => stale).
    _CGU_RPT_PHASE=$(jsonu_get_file_path_string "$_CGU_CR_REPORT" "phase")
    _CGU_PHS_PHASE=$(jsonu_get_file_path_string "$_CGU_PHASE_STATE" "phase")
    if [ -n "$_CGU_RPT_PHASE" ] && [ -n "$_CGU_PHS_PHASE" ]; then
      if [ "$_CGU_RPT_PHASE" != "$_CGU_PHS_PHASE" ]; then
        return 0
      fi
    else
      _CGU_RPT_MTIME=$(_cgu_mtime "$_CGU_CR_REPORT")
      _CGU_PHS_MTIME=$(_cgu_mtime "$_CGU_PHASE_STATE")
      if [ -n "$_CGU_RPT_MTIME" ] && [ -n "$_CGU_PHS_MTIME" ] && \
         [ "$_CGU_RPT_MTIME" -lt "$_CGU_PHS_MTIME" ] 2>/dev/null; then
        return 0
      fi
    fi
  fi

  # Skip PASS/FAIL processing if compliance-pass is not an active criterion
  # (but stale cleanup above already ran regardless)
  if [ "$_CGU_HAS_COMPLIANCE" = "0" ]; then
    return 0
  fi

  _CGU_CR_VERDICT=$(jsonu_get_file_path_string "$_CGU_CR_REPORT" "summary.verdict")
  if [ "$_CGU_CR_VERDICT" = "PASS" ]; then
    # Auto-satisfy compliance-pass by removing it from pending
    # Also clear upstream_challenge strategy if previously latched (compliance now PASS)
    _CGU_NEW_PENDING=$(echo "$_CGU_PENDING" | sed 's/compliance-pass//' | sed 's/||/|/g' | sed 's/^|//' | sed 's/|$//')
    if acquire_lock "$_CGU_SKILL_STATE"; then
      _CGU_PASS_SED=$(mktemp "${TMPDIR:-/tmp}/cgu-pass-sed.XXXXXX" 2>/dev/null || echo "$_CGU_SKILL_STATE.pass-sed")
      # Use # as sed delimiter — pending contains | which conflicts with | delimiter
      {
        printf 's#"pending"[[:space:]]*:[[:space:]]*"[^"]*"#"pending": "%s"#\n' "$_CGU_NEW_PENDING"
        # Reset upstream_challenge back to normal ladder strategy on compliance PASS
        printf 's/"strategy"[[:space:]]*:[[:space:]]*"upstream_challenge"/"strategy": "primary"/\n'
        # Clear all stale compliance overrides (budgets + authority + dynamic prompt)
        printf 's/"max_primary"[[:space:]]*:[[:space:]]*[0-9]*/"max_primary": 0/\n'
        printf 's/"max_fallback"[[:space:]]*:[[:space:]]*[0-9]*/"max_fallback": 0/\n'
        printf 's/"dynamic_prompt"[[:space:]]*:[[:space:]]*"[^"]*"/"dynamic_prompt": ""/\n'
        printf 's/"compliance_authority"[[:space:]]*:[[:space:]]*[0-9]*/"compliance_authority": 0/\n'
      } > "$_CGU_PASS_SED"
      if sed -f "$_CGU_PASS_SED" "$_CGU_SKILL_STATE" > "$_CGU_SKILL_STATE.tmp" 2>/dev/null; then
        mv "$_CGU_SKILL_STATE.tmp" "$_CGU_SKILL_STATE"
      else
        rm -f "$_CGU_SKILL_STATE.tmp" 2>/dev/null
      fi
      rm -f "$_CGU_PASS_SED" 2>/dev/null
      release_lock "$_CGU_SKILL_STATE"
    fi
    _CGU_PENDING="$_CGU_NEW_PENDING"
  else
    # Compliance FAIL — inject authority-specific dynamic prompt
    _CGU_CR_AUTH=$(jsonu_get_file_path_num "$_CGU_CR_REPORT" "summary.max_violation_authority")
    _CGU_CR_INFEASIBLE=$(jsonu_get_file_path_string "$_CGU_CR_REPORT" "summary.infeasibility_detected")
    [ -z "$_CGU_CR_AUTH" ] && _CGU_CR_AUTH=3
    # Compute authority-specific budgets
    case "$_CGU_CR_AUTH" in
      1) _CGU_CR_TAG="[CRITICAL — UPSTREAM REQUIREMENT VIOLATION]"; _CGU_CR_MAX_P=3; _CGU_CR_MAX_F=2 ;;
      2) _CGU_CR_TAG="[WARNING — HIGH]"; _CGU_CR_MAX_P=4; _CGU_CR_MAX_F=3 ;;
      *) _CGU_CR_TAG="[WARNING]"; _CGU_CR_MAX_P=5; _CGU_CR_MAX_F=5 ;;
    esac
    _CGU_DYN_MSG="$_CGU_CR_TAG Compliance violation (authority=$_CGU_CR_AUTH). Fix violated requirements before proceeding. Re-read upstream iron-requirements.json."
    # Write authority, budgets, and dynamic prompt via sed
    if acquire_lock "$_CGU_SKILL_STATE"; then
      _CGU_CR_SED=$(mktemp "${TMPDIR:-/tmp}/cr-sed.XXXXXX" 2>/dev/null || echo "$_CGU_SKILL_STATE.cr-sed")
      {
        printf 's/"compliance_authority"[[:space:]]*:[[:space:]]*[^,]*/"compliance_authority": %s/\n' "$_CGU_CR_AUTH"
        printf 's/"max_primary"[[:space:]]*:[[:space:]]*[^,]*/"max_primary": %s/\n' "$_CGU_CR_MAX_P"
        printf 's/"max_fallback"[[:space:]]*:[[:space:]]*[^,]*/"max_fallback": %s/\n' "$_CGU_CR_MAX_F"
        printf 's/"dynamic_prompt"[[:space:]]*:[[:space:]]*"[^"]*"/"dynamic_prompt": "%s"/\n' "$(echo "$_CGU_DYN_MSG" | sed 's/[&/\]/\\&/g')"
      } > "$_CGU_CR_SED"
      # If infeasibility validated AND past primary stage, switch strategy
      # Read current iteration to enforce "after Primary exhaustion" rule
      _CGU_CR_ITER=$(jsonu_get_file_path_num "$_CGU_SKILL_STATE" "iteration")
      _CGU_CR_ITER=${_CGU_CR_ITER:-1}
      if [ "$_CGU_CR_INFEASIBLE" = "true" ] && [ "$_CGU_CR_ITER" -gt "$_CGU_CR_MAX_P" ]; then
        printf 's/"strategy"[[:space:]]*:[[:space:]]*"[^"]*"/"strategy": "upstream_challenge"/\n' >> "$_CGU_CR_SED"
      elif [ "$_CGU_CR_INFEASIBLE" != "true" ]; then
        # Clear stale upstream_challenge if infeasibility is no longer detected
        # (downgraded from infeasible FAIL to fixable FAIL)
        printf 's/"strategy"[[:space:]]*:[[:space:]]*"upstream_challenge"/"strategy": "primary"/\n' >> "$_CGU_CR_SED"
      fi
      if sed -f "$_CGU_CR_SED" "$_CGU_SKILL_STATE" > "$_CGU_SKILL_STATE.tmp" 2>/dev/null; then
        mv "$_CGU_SKILL_STATE.tmp" "$_CGU_SKILL_STATE"
      else
        rm -f "$_CGU_SKILL_STATE.tmp" 2>/dev/null
      fi
      rm -f "$_CGU_CR_SED" 2>/dev/null
      release_lock "$_CGU_SKILL_STATE"
    fi
  fi
}
