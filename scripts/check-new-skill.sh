#!/bin/bash
# check-new-skill.sh — Validate skill registration across all 8 locations.
# Usage: scripts/check-new-skill.sh <skill-short-name>
#
# Checks:
#   1. skills/{name}/SKILL.md exists
#   2. hooks/lib/spawn-context-util.sh sctx_skill_to_phase() contains the skill
#   3. hooks/rtl-phase-state-bootstrap.sh case contains the skill (P2+ primary)
#   4. hooks/rtl-spawn-context.sh agent mapping references this skill
#   5. skills/rtl-orchestrate/SKILL.md routing table contains the skill
#   6. hooks/rtl-orchestrator-inject.sh contains the skill
#   7. skill-completion-criteria.json contains the skill
#   8. tests/unit/test_hooks.py EXPECTED_SKILL_PHASES contains the skill

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "$0")/.." && pwd)

if [ $# -ne 1 ] || [ -z "$1" ]; then
  echo "usage: $0 <skill-short-name>" >&2
  echo "example: $0 rtl-p4-block-parallel" >&2
  exit 1
fi

SKILL="$1"

PASS=0
FAIL=0
SKIP=0

# Print result line and update counters
report() {
  local status="$1"
  local label="$2"
  local detail="${3:-}"

  case "$status" in
    FOUND)
      printf "  [FOUND]   %s" "$label"
      PASS=$((PASS + 1))
      ;;
    MISSING)
      printf "  [MISSING] %s" "$label"
      FAIL=$((FAIL + 1))
      ;;
    SKIP)
      printf "  [SKIP]    %s" "$label"
      SKIP=$((SKIP + 1))
      ;;
  esac

  if [ -n "$detail" ]; then
    printf "  (%s)" "$detail"
  fi
  printf "\n"
}

echo "Checking skill registration: $SKILL"
echo ""

# 1. skills/{name}/SKILL.md
if [ -f "$ROOT_DIR/skills/$SKILL/SKILL.md" ]; then
  report FOUND "skills/$SKILL/SKILL.md"
else
  report MISSING "skills/$SKILL/SKILL.md"
fi

# 2. Phase mapper: hooks/lib/spawn-context-util.sh sctx_skill_to_phase()
SPAWN_UTIL="$ROOT_DIR/hooks/lib/spawn-context-util.sh"
if grep -q "$SKILL" "$SPAWN_UTIL" 2>/dev/null; then
  report FOUND "spawn-context-util.sh phase mapper"
else
  report MISSING "spawn-context-util.sh phase mapper"
fi

# 3. Compliance bootstrap: hooks/rtl-phase-state-bootstrap.sh
# Only required for P2+ primary skills (not P1, not sub-skills, not pipelines)
BOOTSTRAP="$ROOT_DIR/hooks/rtl-phase-state-bootstrap.sh"
case "$SKILL" in
  p1-*|rtl-p1-*|rat-*)
    report SKIP "rtl-phase-state-bootstrap.sh" "P1/pipeline skill — compliance bootstrap not required"
    ;;
  *)
    if grep -q "$SKILL" "$BOOTSTRAP" 2>/dev/null; then
      report FOUND "rtl-phase-state-bootstrap.sh compliance case"
    else
      report MISSING "rtl-phase-state-bootstrap.sh compliance case"
    fi
    ;;
esac

# 4. Spawn context agent mapping: hooks/rtl-spawn-context.sh
SPAWN_HOOK="$ROOT_DIR/hooks/rtl-spawn-context.sh"
if grep -q "$SKILL" "$SPAWN_HOOK" 2>/dev/null; then
  report FOUND "rtl-spawn-context.sh agent mapping"
else
  report MISSING "rtl-spawn-context.sh agent mapping"
fi

# 5. Routing table: skills/rtl-orchestrate/SKILL.md
ROUTING="$ROOT_DIR/skills/rtl-orchestrate/SKILL.md"
if grep -q "$SKILL" "$ROUTING" 2>/dev/null; then
  report FOUND "rtl-orchestrate/SKILL.md routing table"
else
  report MISSING "rtl-orchestrate/SKILL.md routing table"
fi

# 6. Hook injection: hooks/rtl-orchestrator-inject.sh
INJECT="$ROOT_DIR/hooks/rtl-orchestrator-inject.sh"
if grep -q "$SKILL" "$INJECT" 2>/dev/null; then
  report FOUND "rtl-orchestrator-inject.sh hook injection"
else
  report MISSING "rtl-orchestrator-inject.sh hook injection"
fi

# 7. Completion criteria: skill-completion-criteria.json
CRITERIA="$ROOT_DIR/skill-completion-criteria.json"
if grep -q "\"$SKILL\"" "$CRITERIA" 2>/dev/null; then
  report FOUND "skill-completion-criteria.json"
else
  report MISSING "skill-completion-criteria.json"
fi

# 8. Test coverage: tests/unit/test_hooks.py EXPECTED_SKILL_PHASES
TEST_FILE="$ROOT_DIR/tests/unit/test_hooks.py"
if grep -q "\"$SKILL\"" "$TEST_FILE" 2>/dev/null; then
  report FOUND "test_hooks.py EXPECTED_SKILL_PHASES"
else
  report MISSING "test_hooks.py EXPECTED_SKILL_PHASES"
fi

echo ""
echo "Summary: $PASS found, $FAIL missing, $SKIP skipped"

if [ "$FAIL" -gt 0 ]; then
  exit 1
fi

exit 0
