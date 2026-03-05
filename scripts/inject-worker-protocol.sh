#!/bin/sh
# inject-worker-protocol.sh
# Injects or updates the Team Worker Protocol section in target agent .md files.
# Idempotent: if the section already exists, it is replaced; otherwise appended.
#
# Usage: sh scripts/inject-worker-protocol.sh [agent-name ...]
#   If no arguments, processes all Tier-1 agents.

set -e

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
AGENTS_DIR="$REPO_ROOT/agents"
PROTOCOL_FILE="$AGENTS_DIR/lib/team-worker-protocol.md"

if [ ! -f "$PROTOCOL_FILE" ]; then
  echo "ERROR: Protocol template not found: $PROTOCOL_FILE" >&2
  exit 1
fi

# Tier-1 agents (P4/P5) that should have the Team Worker Protocol
P4_P5_AGENTS="rtl-coder lint-checker rtl-critic testbench-dev eda-runner sva-extractor cdc-checker protocol-checker func-verifier coverage-analyst perf-verifier"

# P1-P3 specialist agents that participate in team mode
P1_P3_AGENTS="spec-analyst vcodec-chief-standard-expert rtl-architect vcodec-architecture-expert arch-designer power-analyzer vcodec-syntax-entropy-expert vcodec-prediction-expert vcodec-transform-quant-expert vcodec-filter-recon-expert video-processing-expert ref-model-dev bfm-dev timing-advisor"

DEFAULT_AGENTS="$P4_P5_AGENTS $P1_P3_AGENTS"

# Use arguments if provided, otherwise defaults
TARGETS="${*:-$DEFAULT_AGENTS}"

# Task type mapping per agent (used in the injected section)
get_task_type() {
  case "$1" in
    rtl-coder)        echo "W1 (Write)" ;;
    lint-checker)     echo "V1 (Lint)" ;;
    rtl-critic)       echo "W4 (Review) or V9 (Code Review)" ;;
    testbench-dev)    echo "V5 (Functional) TB setup" ;;
    eda-runner)       echo "simulation and synthesis" ;;
    sva-extractor)    echo "V2 (SVA/Formal)" ;;
    cdc-checker)      echo "V3 (CDC)" ;;
    protocol-checker) echo "V4 (Protocol) or W8 (Protocol)" ;;
    func-verifier)    echo "V5 (Functional)" ;;
    coverage-analyst) echo "V6 (Coverage)" ;;
    perf-verifier)    echo "V7 (Performance)" ;;
    spec-analyst)     echo "P1 solution tree, requirements merge, or P1 gate review" ;;
    vcodec-chief-standard-expert) echo "P1 tree validation, comparison matrix, or chief review" ;;
    rtl-architect)    echo "P1 candidate deep-dive, P2/P3 review aggregation, or phase gate" ;;
    vcodec-architecture-expert) echo "P1 memory survey, P2 HW evaluation, or P3 algorithm review" ;;
    arch-designer)    echo "P1 interconnect survey, P2 architecture design, or P2 gate review" ;;
    power-analyzer)   echo "P1 power survey" ;;
    vcodec-syntax-entropy-expert) echo "P1 syntax/entropy requirements" ;;
    vcodec-prediction-expert) echo "P1 prediction requirements" ;;
    vcodec-transform-quant-expert) echo "P1 transform/quant requirements" ;;
    vcodec-filter-recon-expert) echo "P1 filter/recon requirements" ;;
    video-processing-expert) echo "P1 signal processing requirements" ;;
    ref-model-dev)    echo "P2 RefC development, P2/P3 model consistency review" ;;
    bfm-dev)          echo "P3 BFM development or P3 BFM correctness review" ;;
    timing-advisor)   echo "P3 timing/pipeline review" ;;
    *)                echo "assigned" ;;
  esac
}

# Check if agent is write-restricted (must use SendMessage-to-leader for file output)
is_write_restricted() {
  case "$1" in
    vcodec-architecture-expert|arch-designer|timing-advisor) return 0 ;;
    *) return 1 ;;
  esac
}

INJECTED=0
SKIPPED=0

for agent in $TARGETS; do
  AGENT_FILE="$AGENTS_DIR/${agent}.md"

  if [ ! -f "$AGENT_FILE" ]; then
    echo "WARN: Agent file not found, skipping: $AGENT_FILE" >&2
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  # Check if section already exists
  if grep -q "## Team Worker Protocol" "$AGENT_FILE"; then
    echo "OK (exists): $agent"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  TASK_TYPE=$(get_task_type "$agent")

  # Build write-restriction note if applicable
  WRITE_NOTE=""
  if is_write_restricted "$agent"; then
    WRITE_NOTE="
5. **Write-restricted**: You cannot write files directly. Send file content via
   \`SendMessage(recipient=leader, content=file_content)\` and the leader will write on your behalf."
  fi

  # Insert before the last </Agent_Prompt>
  if grep -q "</Agent_Prompt>" "$AGENT_FILE"; then
    # Use awk for reliable multi-line insertion (POSIX-compatible)
    awk -v section="
## Team Worker Protocol

When spawned with \`team_name\` parameter as part of a native team:

1. Follow the standard Team Worker Protocol defined in \`agents/lib/team-worker-preamble.md\`
2. Claim ${TASK_TYPE} tasks from TaskList matching your specialty
3. Execute each task, save artifacts, then TaskUpdate(completed) + SendMessage to leader
4. When no more tasks are available, notify leader and wait for shutdown${WRITE_NOTE}

When spawned WITHOUT \`team_name\` (traditional Task() mode), ignore this section entirely." \
      '/^<\/Agent_Prompt>/ && !done { print section; done=1 } { print }' \
      "$AGENT_FILE" > "$AGENT_FILE.tmp" && mv "$AGENT_FILE.tmp" "$AGENT_FILE"
  else
    # No </Agent_Prompt> tag — append at end
    printf '\n\n## Team Worker Protocol\n\nWhen spawned with `team_name` parameter as part of a native team:\n\n1. Follow the standard Team Worker Protocol defined in `agents/lib/team-worker-preamble.md`\n2. Claim %s tasks from TaskList matching your specialty\n3. Execute each task, save artifacts, then TaskUpdate(completed) + SendMessage to leader\n4. When no more tasks are available, notify leader and wait for shutdown%s\n\nWhen spawned WITHOUT `team_name` (traditional Task() mode), ignore this section entirely.\n' "$TASK_TYPE" "$WRITE_NOTE" >> "$AGENT_FILE"
  fi

  INJECTED=$((INJECTED + 1))
  echo "INJECTED: $agent"
done

echo ""
echo "Done. Injected: $INJECTED, Skipped (already present): $SKIPPED"
