#!/usr/bin/env bash
# lib/tool-runner.sh — Docker-aware transparent tool runner
#
# Provides run_tool() function that executes EDA tools locally when available,
# falling back to a persistent Docker container when tools are not installed.
#
# Persistent container lifecycle:
#   - Created on first run_tool() call when a local tool is missing
#   - Reused across all subsequent run_tool() calls in the same project
#   - Stopped via tool_runner_cleanup() (called at Phase 5 exit)
#   - Container name stored in .rtl-agent-team/state/docker-container.txt
#
# Usage in scripts:
#   source lib/tool-runner.sh
#   run_tool verilator --lint-only -Wall module.sv
#   run_tool yosys -s synth.ys
#
# Environment:
#   RTL_EDA_IMAGE    Docker image name (default: rtl-eda-tools)

RTL_EDA_IMAGE="${RTL_EDA_IMAGE:-rtl-eda-tools}"

_TOOL_RUNNER_CONTAINER=""
_TOOL_RUNNER_STATE_FILE=".rtl-agent-team/state/docker-container.txt"

# Derive container name from project directory
_tool_runner_container_name() {
  local project_name
  project_name=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-')
  echo "rtl-eda-${project_name}"
}

# Check if Docker image is available
_tool_runner_has_image() {
  docker images -q "$RTL_EDA_IMAGE" 2>/dev/null | grep -q .
}

# Ensure persistent container is running
_tool_runner_ensure_container() {
  if [[ -n "$_TOOL_RUNNER_CONTAINER" ]]; then
    if docker ps -q -f "name=^${_TOOL_RUNNER_CONTAINER}$" 2>/dev/null | grep -q .; then
      return 0
    fi
  fi

  _TOOL_RUNNER_CONTAINER=$(_tool_runner_container_name)

  # Container already running?
  if docker ps -q -f "name=^${_TOOL_RUNNER_CONTAINER}$" 2>/dev/null | grep -q .; then
    return 0
  fi

  # Container exists but stopped?
  if docker ps -aq -f "name=^${_TOOL_RUNNER_CONTAINER}$" 2>/dev/null | grep -q .; then
    docker start "$_TOOL_RUNNER_CONTAINER" >/dev/null
    return 0
  fi

  # Create new persistent container
  echo "[tool-runner] Starting persistent Docker container: $_TOOL_RUNNER_CONTAINER" >&2
  docker run -d --name "$_TOOL_RUNNER_CONTAINER" \
    -v "$(pwd)":/workspace -w /workspace \
    "$RTL_EDA_IMAGE" tail -f /dev/null >/dev/null

  # Record container name for cleanup
  mkdir -p "$(dirname "$_TOOL_RUNNER_STATE_FILE")"
  echo "$_TOOL_RUNNER_CONTAINER" > "$_TOOL_RUNNER_STATE_FILE"
}

# Run a tool: local binary first, Docker fallback if missing
run_tool() {
  local tool="$1"
  shift

  # Try local first
  if command -v "$tool" >/dev/null 2>&1; then
    "$tool" "$@"
    return $?
  fi

  # Docker fallback
  if ! command -v docker >/dev/null 2>&1; then
    echo "ERROR: '$tool' not found locally and Docker is not installed." >&2
    echo "Install '$tool' or build Docker image: docker build -t $RTL_EDA_IMAGE docker/" >&2
    return 127
  fi

  if ! _tool_runner_has_image; then
    echo "ERROR: '$tool' not found locally and Docker image '$RTL_EDA_IMAGE' not built." >&2
    echo "Build: docker build -t $RTL_EDA_IMAGE \"\${CLAUDE_PLUGIN_ROOT}/docker/\"" >&2
    return 127
  fi

  _tool_runner_ensure_container
  docker exec "$_TOOL_RUNNER_CONTAINER" "$tool" "$@"
}

# Stop and remove the persistent container
tool_runner_cleanup() {
  local container_name
  if [[ -n "$_TOOL_RUNNER_CONTAINER" ]]; then
    container_name="$_TOOL_RUNNER_CONTAINER"
  elif [[ -f "$_TOOL_RUNNER_STATE_FILE" ]]; then
    container_name=$(cat "$_TOOL_RUNNER_STATE_FILE")
  else
    container_name=$(_tool_runner_container_name)
  fi

  if docker ps -aq -f "name=^${container_name}$" 2>/dev/null | grep -q .; then
    echo "[tool-runner] Stopping container: $container_name" >&2
    docker stop "$container_name" 2>/dev/null || true
    docker rm "$container_name" 2>/dev/null || true
  fi
  rm -f "$_TOOL_RUNNER_STATE_FILE"
}
