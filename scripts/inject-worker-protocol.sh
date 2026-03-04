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

# Tier-1 agents that should have the Team Worker Protocol
DEFAULT_AGENTS="rtl-coder lint-checker rtl-critic testbench-dev eda-runner sva-extractor cdc-checker protocol-checker func-verifier coverage-analyst perf-verifier"

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
    *)                echo "assigned" ;;
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

  # Append before closing </Agent_Prompt> tag
  # Use sed to insert before the last </Agent_Prompt>
  SECTION="\\
\\
## Team Worker Protocol\\
\\
When spawned with \`team_name\` parameter as part of a native team:\\
\\
1. Follow the standard Team Worker Protocol defined in \`agents/lib/team-worker-preamble.md\`\\
2. Claim ${TASK_TYPE} tasks from TaskList matching your specialty\\
3. Execute each task, save artifacts, then TaskUpdate(completed) + SendMessage to leader\\
4. When no more tasks are available, notify leader and wait for shutdown\\
\\
When spawned WITHOUT \`team_name\` (traditional Task() mode), ignore this section entirely."

  # Insert before the last </Agent_Prompt>
  if grep -q "</Agent_Prompt>" "$AGENT_FILE"; then
    # Use awk for reliable multi-line insertion (POSIX-compatible)
    awk -v section="
## Team Worker Protocol

When spawned with \`team_name\` parameter as part of a native team:

1. Follow the standard Team Worker Protocol defined in \`agents/lib/team-worker-preamble.md\`
2. Claim ${TASK_TYPE} tasks from TaskList matching your specialty
3. Execute each task, save artifacts, then TaskUpdate(completed) + SendMessage to leader
4. When no more tasks are available, notify leader and wait for shutdown

When spawned WITHOUT \`team_name\` (traditional Task() mode), ignore this section entirely." \
      '/^<\/Agent_Prompt>/ && !done { print section; done=1 } { print }' \
      "$AGENT_FILE" > "$AGENT_FILE.tmp" && mv "$AGENT_FILE.tmp" "$AGENT_FILE"
  else
    # No </Agent_Prompt> tag — append at end
    printf '\n\n## Team Worker Protocol\n\nWhen spawned with `team_name` parameter as part of a native team:\n\n1. Follow the standard Team Worker Protocol defined in `agents/lib/team-worker-preamble.md`\n2. Claim %s tasks from TaskList matching your specialty\n3. Execute each task, save artifacts, then TaskUpdate(completed) + SendMessage to leader\n4. When no more tasks are available, notify leader and wait for shutdown\n\nWhen spawned WITHOUT `team_name` (traditional Task() mode), ignore this section entirely.\n' "$TASK_TYPE" >> "$AGENT_FILE"
  fi

  INJECTED=$((INJECTED + 1))
  echo "INJECTED: $agent"
done

echo ""
echo "Done. Injected: $INJECTED, Skipped (already present): $SKIPPED"
