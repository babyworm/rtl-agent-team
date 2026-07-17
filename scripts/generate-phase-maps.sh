#!/usr/bin/env bash
# generate-phase-maps.sh — Generate shell case statements from phase-registry.json.
# Reads the single-source-of-truth registry and either:
#   (a) prints generated blocks to stdout (--check or --print)
#   (b) replaces content between markers in target files (--write)
#
# Usage:
#   scripts/generate-phase-maps.sh --check   # Exit 1 if files differ from registry
#   scripts/generate-phase-maps.sh --print   # Print generated blocks to stdout
#   scripts/generate-phase-maps.sh --write   # Replace marker blocks in target files
#
# Requires: jq

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REGISTRY="$REPO_ROOT/phase-registry.json"

if [ ! -f "$REGISTRY" ]; then
  echo "ERROR: phase-registry.json not found at $REGISTRY" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq is required but not found" >&2
  exit 1
fi

# ── Target files ──────────────────────────────────────────────────────────────
SPAWN_CTX_UTIL="$REPO_ROOT/hooks/lib/spawn-context-util.sh"
BOOTSTRAP_HOOK="$REPO_ROOT/hooks/rtl-phase-state-bootstrap.sh"
SPAWN_HOOK="$REPO_ROOT/hooks/rtl-spawn-context.sh"
ARTIFACT_MAP="$REPO_ROOT/hooks/lib/artifact-map.sh"

BEGIN_MARKER="# BEGIN GENERATED PHASE_MAP"
END_MARKER="# END GENERATED PHASE_MAP"
ARTMAP_REQ_BEGIN="# BEGIN GENERATED ARTMAP_REQUIRED"
ARTMAP_REQ_END="# END GENERATED ARTMAP_REQUIRED"
ARTMAP_OPT_BEGIN="# BEGIN GENERATED ARTMAP_OPTIONAL"
ARTMAP_OPT_END="# END GENERATED ARTMAP_OPTIONAL"

# ── Helper: join skill names from registry by jq filter ───────────────────────
_skills_join() {
  jq -r "$1" "$REGISTRY"
}

# ── Generator: sctx_skill_to_phase() case body ───────────────────────────────
generate_skill_to_phase() {
  # Group skills by phase number, preserving the original line grouping.
  # Phase 0 skills (codex-cross-review, rat-ultraloop) are excluded — they
  # have no phase mapping in sctx_skill_to_phase().
  # Phase 5 uses phase_group "a"/"b" to control the two-line split.

  local p1_native p2 p3 p4_rtl p5_a p5_b p6 p7 p1_rat p4_rat ppa_opt

  p1_native=$(_skills_join '[.skills | to_entries[] | select(.value.phase == 1) | select(.key | test("^(p1-|rtl-p1-)")) | .key] | join("|")')
  p2=$(_skills_join '[.skills | to_entries[] | select(.value.phase == 2) | .key] | join("|")')
  p3=$(_skills_join '[.skills | to_entries[] | select(.value.phase == 3) | .key] | join("|")')
  p4_rtl=$(_skills_join '[.skills | to_entries[] | select(.value.phase == 4) | select(.key | test("^rtl-")) | .key] | join("|")')
  p5_a=$(_skills_join '[.skills | to_entries[] | select(.value.phase == 5) | select(.value.phase_group == "a") | .key] | join("|")')
  p5_b=$(_skills_join '[.skills | to_entries[] | select(.value.phase == 5) | select(.value.phase_group == "b") | .key] | join("|")')
  p6=$(_skills_join '[.skills | to_entries[] | select(.value.phase == 6) | .key] | join("|")')
  p7=$(_skills_join '[.skills | to_entries[] | select(.value.phase == 7) | .key] | join("|")')
  p1_rat=$(_skills_join '[.skills | to_entries[] | select(.value.phase == 1) | select(.key | test("^rat-")) | .key] | join("|")')
  p4_rat=$(_skills_join '[.skills | to_entries[] | select(.value.phase == 4) | select(.key | test("^rat-")) | .key] | join("|")')
  ppa_opt=$(_skills_join '[.skills | to_entries[] | select(.value.phase == "ppa-opt") | .key] | join("|")')

  # Output with exact spacing to match original file format.
  # The second line (p2) has extra padding for visual alignment with "echo 2".
  printf '    %s) echo 1 ;;\n' "$p1_native"
  printf '    %s)       echo 2 ;;\n' "$p2"
  printf '    %s) echo 3 ;;\n' "$p3"
  printf '    %s) echo 4 ;;\n' "$p4_rtl"
  printf '    %s) echo 5 ;;\n' "$p5_a"
  printf '    %s) echo 5 ;;\n' "$p5_b"
  printf '    %s) echo 6 ;;\n' "$p6"
  printf '    %s) echo 7 ;;\n' "$p7"
  printf '    %s) echo 1 ;;\n' "$p1_rat"
  printf '    %s) echo 4 ;;\n' "$p4_rat"
  [ -n "$ppa_opt" ] && printf '    %s) echo 8 ;;\n' "$ppa_opt"
}

# ── Generator: compliance bootstrap case body ─────────────────────────────────
generate_compliance_bootstrap() {
  # Group primary skills by iron_upstream length (1, 2, or 3 paths).
  # Group 3 uses explicit ordering to match the original bootstrap case layout
  # (by phase: p4-impl → p4-rapid → p4-block → rat-p4p5 → p5 → p6).

  local group1 group2 group3 up1 open1 up2 open2 up3

  group1=$(_skills_join '[.skills | to_entries[] | select(.value.primary == true) | select((.value.iron_upstream | length) == 1) | .key] | join("|")')
  group2=$(_skills_join '[.skills | to_entries[] | select(.value.primary == true) | select((.value.iron_upstream | length) == 2) | .key] | join("|")')
  # Group 3: explicit phase-ordered sort (p4 impl/team → rapid → block → rat → p5 → p6)
  group3=$(_skills_join '
    def phase_order:
      if test("^rtl-p4-implement$") then 0
      elif test("^rtl-p4-implement-team$") then 1
      elif test("^rtl-p4-rapid") then 2
      elif test("^rtl-p4-block") then 3
      elif test("^rat-p4p5") then 4
      elif test("^rtl-p5-verify$") then 5
      elif test("^rtl-p5-verify-team$") then 6
      elif test("^rtl-p5a") then 7
      elif test("^rtl-p5b") then 8
      elif test("^rtl-p6") then 9
      else 99 end;
    [.skills | to_entries[]
     | select(.value.primary == true)
     | select((.value.iron_upstream | length) == 3)
     | {key, sort_idx: (.key | phase_order)}]
    | sort_by(.sort_idx) | [.[].key] | join("|")')

  up1=$(_skills_join '[.skills | to_entries[] | select(.value.primary == true) | select((.value.iron_upstream | length) == 1)][0].value.iron_upstream | map("\"" + . + "\"") | "[" + join(",") + "]"')
  open1=$(_skills_join '[.skills | to_entries[] | select(.value.primary == true) | select((.value.iron_upstream | length) == 1)][0].value.open_requirements')
  up2=$(_skills_join '[.skills | to_entries[] | select(.value.primary == true) | select((.value.iron_upstream | length) == 2)][0].value.iron_upstream | map("\"" + . + "\"") | "[" + join(",") + "]"')
  open2=$(_skills_join '[.skills | to_entries[] | select(.value.primary == true) | select((.value.iron_upstream | length) == 2)][0].value.open_requirements')
  up3=$(_skills_join '[.skills | to_entries[] | select(.value.primary == true) | select((.value.iron_upstream | length) == 3)][0].value.iron_upstream | map("\"" + . + "\"") | "[" + join(",") + "]"')

  cat <<EOF
      $group1)
        _cs_upstream='$up1'
        _cs_open="$open1"
        ;;
      $group2)
        _cs_upstream='$up2'
        _cs_open="$open2"
        ;;
      $group3)
        _cs_upstream='$up3'
        _cs_open=""
        ;;
EOF
}

# ── Generator: agent→skill case body ─────────────────────────────────────────
_agent_line() {
  # Produce "  agent-name)  SKILL_NAME="skill" ;;" with SKILL_NAME at column 35+.
  # Column rule: SKILL_NAME starts at 1-indexed column max(35, agent_len+4).
  # Padding = target_col - 2(indent) - agent_len - 1(paren) = target_col - agent_len - 3.
  local agent="$1" skill="$2"
  local pad=$(( 31 - ${#agent} ))
  if [ "$pad" -lt 1 ]; then
    pad=1
  fi
  printf '  %s)%*sSKILL_NAME="%s" ;;\n' "$agent" "$pad" "" "$skill"
}

generate_agent_skill_map() {
  # Produce agent→skill case branches with column-aligned SKILL_NAME assignments.
  # Non-team agents first, then team agents, each group preceded by a comment.

  echo "  # Non-team orchestrators → non-team skills"
  jq -r '.agents | to_entries[] | select(.key | test("-team-") | not) | "\(.key) \(.value)"' "$REGISTRY" | while read -r agent skill; do
    _agent_line "$agent" "$skill"
  done

  echo "  # Team orchestrators → team skills (1:1 mapping)"
  jq -r '.agents | to_entries[] | select(.key | test("-team-")) | "\(.key) \(.value)"' "$REGISTRY" | while read -r agent skill; do
    _agent_line "$agent" "$skill"
  done
}

# ── Generator: artmap_required()/artmap_optional() case bodies ────────────────
generate_artifact_map() {
  # $1 = required | optional
  # Emit artmap case branches from the registry "phases" section, ordered by
  # integer phase number ("integer_map" overrides non-numeric keys, e.g.
  # ppa-opt → 8). Phases with no entries produce no case branch — the case
  # falls through and emits nothing, matching legacy artifact-map behavior.
  jq -r --arg field "$1" --arg q "'" '
    .phases | to_entries
    | map({num: (.value.integer_map // (.key | tonumber)),
           entries: (.value[$field] // [])})
    | sort_by(.num)
    | .[] | select((.entries | length) > 0)
    | "    \(.num))",
      "      cat <<\($q)EOF\($q)",
      (.entries[] | "\(.path)|\(.role)"),
      "EOF",
      "      ;;"
  ' "$REGISTRY"
}

# ── Replace between markers ──────────────────────────────────────────────────
replace_between_markers() {
  local file="$1"
  local new_content="$2"
  local begin="${3:-$BEGIN_MARKER}"
  local end="${4:-$END_MARKER}"
  local tmpfile="${file}.gen.tmp"

  if [ ! -f "$file" ]; then
    echo "ERROR: Target file not found: $file" >&2
    return 1
  fi

  awk -v begin="$begin" -v end="$end" -v content="$new_content" '
    $0 ~ begin { print; printf "%s\n", content; skip=1; next }
    skip && $0 ~ end { skip=0 }
    !skip { print }
  ' "$file" > "$tmpfile"

  mv "$tmpfile" "$file"
}

# ── Extract between markers ──────────────────────────────────────────────────
extract_between_markers() {
  local file="$1"
  local begin="${2:-$BEGIN_MARKER}"
  local end="${3:-$END_MARKER}"
  awk -v begin="$begin" -v end="$end" '
    $0 ~ begin { found=1; next }
    found && $0 ~ end { found=0; next }
    found { print }
  ' "$file"
}

# ── Main ──────────────────────────────────────────────────────────────────────
MODE="${1:---check}"

case "$MODE" in
  --print)
    echo "=== skill_to_phase ==="
    generate_skill_to_phase
    echo ""
    echo "=== compliance_bootstrap ==="
    generate_compliance_bootstrap
    echo ""
    echo "=== agent_skill_map ==="
    generate_agent_skill_map
    echo ""
    echo "=== artifact_map_required ==="
    generate_artifact_map required
    echo ""
    echo "=== artifact_map_optional ==="
    generate_artifact_map optional
    ;;

  --check)
    ERRORS=0

    # Check skill_to_phase
    GENERATED=$(generate_skill_to_phase)
    CURRENT=$(extract_between_markers "$SPAWN_CTX_UTIL")
    if [ "$GENERATED" != "$CURRENT" ]; then
      echo "DRIFT: $SPAWN_CTX_UTIL skill_to_phase block differs from registry" >&2
      diff <(echo "$CURRENT") <(echo "$GENERATED") >&2 || true
      ERRORS=$((ERRORS + 1))
    fi

    # Check compliance bootstrap
    GENERATED=$(generate_compliance_bootstrap)
    CURRENT=$(extract_between_markers "$BOOTSTRAP_HOOK")
    if [ "$GENERATED" != "$CURRENT" ]; then
      echo "DRIFT: $BOOTSTRAP_HOOK compliance bootstrap block differs from registry" >&2
      diff <(echo "$CURRENT") <(echo "$GENERATED") >&2 || true
      ERRORS=$((ERRORS + 1))
    fi

    # Check agent→skill map
    GENERATED=$(generate_agent_skill_map)
    CURRENT=$(extract_between_markers "$SPAWN_HOOK")
    if [ "$GENERATED" != "$CURRENT" ]; then
      echo "DRIFT: $SPAWN_HOOK agent-skill map block differs from registry" >&2
      diff <(echo "$CURRENT") <(echo "$GENERATED") >&2 || true
      ERRORS=$((ERRORS + 1))
    fi

    # Check artifact map (required + optional blocks)
    GENERATED=$(generate_artifact_map required)
    CURRENT=$(extract_between_markers "$ARTIFACT_MAP" "$ARTMAP_REQ_BEGIN" "$ARTMAP_REQ_END")
    if [ "$GENERATED" != "$CURRENT" ]; then
      echo "DRIFT: $ARTIFACT_MAP artmap_required block differs from registry" >&2
      diff <(echo "$CURRENT") <(echo "$GENERATED") >&2 || true
      ERRORS=$((ERRORS + 1))
    fi

    GENERATED=$(generate_artifact_map optional)
    CURRENT=$(extract_between_markers "$ARTIFACT_MAP" "$ARTMAP_OPT_BEGIN" "$ARTMAP_OPT_END")
    if [ "$GENERATED" != "$CURRENT" ]; then
      echo "DRIFT: $ARTIFACT_MAP artmap_optional block differs from registry" >&2
      diff <(echo "$CURRENT") <(echo "$GENERATED") >&2 || true
      ERRORS=$((ERRORS + 1))
    fi

    if [ "$ERRORS" -gt 0 ]; then
      echo "FAIL: $ERRORS block(s) out of sync with phase-registry.json" >&2
      exit 1
    fi
    echo "OK: All generated blocks match phase-registry.json"
    ;;

  --write)
    echo "Generating skill_to_phase..."
    replace_between_markers "$SPAWN_CTX_UTIL" "$(generate_skill_to_phase)"
    echo "Generating compliance bootstrap..."
    replace_between_markers "$BOOTSTRAP_HOOK" "$(generate_compliance_bootstrap)"
    echo "Generating agent-skill map..."
    replace_between_markers "$SPAWN_HOOK" "$(generate_agent_skill_map)"
    echo "Generating artifact map (required)..."
    replace_between_markers "$ARTIFACT_MAP" "$(generate_artifact_map required)" \
      "$ARTMAP_REQ_BEGIN" "$ARTMAP_REQ_END"
    echo "Generating artifact map (optional)..."
    replace_between_markers "$ARTIFACT_MAP" "$(generate_artifact_map optional)" \
      "$ARTMAP_OPT_BEGIN" "$ARTMAP_OPT_END"
    echo "Done. All target files updated."
    ;;

  *)
    echo "Usage: $0 [--check|--print|--write]" >&2
    exit 1
    ;;
esac
