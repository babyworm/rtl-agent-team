#!/bin/sh
# RTL Skill Activation Hook: PreToolUse:Skill
# Auto-creates completion state when an rtl-agent-team skill is invoked.
# Reads completion criteria from .rtl-agent-team/skill-completion-criteria.json.

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

# Extract skill name from tool input
SKILL_NAME=$(printf '%s' "$INPUT" | sed -n 's/.*"skill"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')

# Only handle rtl-agent-team skills
case "$SKILL_NAME" in
  rtl-agent-team:*)
    SHORT_NAME="${SKILL_NAME#rtl-agent-team:}"
    ;;
  *)
    printf '{"continue":true}'
    exit 0
    ;;
esac

# Setup prerequisite check — exempt categories:
# Category 1 — Self-reference: rtl-setup (cannot check setup before setup)
# Category 2 — Passive policies: *-policy (14 skills, loaded by agents via skills: field, not user-invocable)
# Category 3 — File-extension conventions: systemverilog, systemverilog-assertion, systemc, uvm
# Category 4 — Reference-only: rtl-orchestrate (routing table, no execution)
case "$SHORT_NAME" in
  rtl-setup|*-policy|systemverilog|systemverilog-assertion|systemc|uvm|rtl-orchestrate)
    ;;
  *)
    if [ ! -f "$CWD/.claude/rules/rtl-coding-conventions.md" ]; then
      printf '{"continue":true,"hookSpecificOutput":{"additionalContext":"[SETUP REQUIRED] rtl-setup이 실행되지 않았습니다. 프로젝트 룰(.claude/rules/), 가이드, 디렉토리 구조가 없어 파이프라인이 올바르게 동작하지 않을 수 있습니다. 먼저 /rtl-agent-team:rtl-setup 을 실행하세요."}}'
      exit 0
    fi
    ;;
esac

STATE_DIR="$CWD/.rtl-agent-team/state"
SKILL_STATE="$STATE_DIR/skill-active.json"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
CRITERIA_FILE="$PLUGIN_ROOT/.rtl-agent-team/skill-completion-criteria.json"

# Don't override if already active (re-invocation within same session)
if [ -f "$SKILL_STATE" ]; then
  printf '{"continue":true}'
  exit 0
fi

# Read criteria for this skill from config
if [ ! -f "$CRITERIA_FILE" ]; then
  printf '{"continue":true}'
  exit 0
fi

# Extract criteria for this skill using grep+sed (no jq dependency)
CRITERIA=$(sed -n "s/.*\"${SHORT_NAME}\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$CRITERIA_FILE")

if [ -z "$CRITERIA" ]; then
  # No criteria defined for this skill, allow without loop
  printf '{"continue":true}'
  exit 0
fi

# Create state file
mkdir -p "$STATE_DIR"
TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date +%Y-%m-%dT%H:%M:%S+00:00)
cat > "$SKILL_STATE.tmp" << SKILLEOF
{
  "skill": "${SHORT_NAME}",
  "active": true,
  "iteration": 1,
  "max_iterations": 5,
  "use_escalation_ladder": false,
  "strategy": "primary",
  "dynamic_prompt": "",
  "pending": "${CRITERIA}",
  "all_complete": false,
  "started_at": "${TIMESTAMP}"
}
SKILLEOF
mv "$SKILL_STATE.tmp" "$SKILL_STATE"

printf '{"continue":true,"hookSpecificOutput":{"additionalContext":"[RTL Skill Completion Loop 활성화] %s 스킬이 시작되었습니다. 완료 조건: %s. 모든 조건을 충족할 때까지 세션이 종료되지 않습니다. 완료 시 .rtl-agent-team/state/skill-active.json 의 all_complete 를 true 로 설정하세요."}}' "$SHORT_NAME" "$CRITERIA"
