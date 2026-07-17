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
#   - Container name stored in .rat/state/docker-container.txt
#
# Usage in scripts:
#   source lib/tool-runner.sh
#   run_tool verilator --lint-only -Wall module.sv
#   run_tool yosys -s synth.ys
#
# Environment:
#   RTL_EDA_IMAGE    Docker image name (default: rtl-eda-tools)

RTL_EDA_IMAGE="${RTL_EDA_IMAGE:-rtl-eda-tools}"

_TOOL_RUNNER_PROJECT_ROOT="${RAT_PROJECT_ROOT:-$(pwd -P)}"
if [[ ! -d "$_TOOL_RUNNER_PROJECT_ROOT" ]]; then
  echo "ERROR: tool-runner project root is not a directory: $_TOOL_RUNNER_PROJECT_ROOT" >&2
  if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    exit 1
  fi
  return 1
fi
_TOOL_RUNNER_PROJECT_ROOT=$(cd "$_TOOL_RUNNER_PROJECT_ROOT" && pwd -P)
_TOOL_RUNNER_CONTAINER=""
_TOOL_RUNNER_STATE_FILE="$_TOOL_RUNNER_PROJECT_ROOT/.rat/state/docker-container.txt"
_TOOL_RUNNER_PROJECT_LABEL="rtl-agent-team.project-root"

_tool_runner_container_name() {
  local project_name project_id
  project_name=$(basename "$_TOOL_RUNNER_PROJECT_ROOT" | tr '[:upper:]' '[:lower:]' | tr -cd 'a-z0-9-')
  project_name=${project_name:0:32}
  project_name=${project_name:-project}
  project_id=$(printf '%s' "$_TOOL_RUNNER_PROJECT_ROOT" | cksum | awk '{print $1}')
  printf 'rtl-eda-%s-%s\n' "$project_name" "$project_id"
}

_tool_runner_validate_state_file() {
  local parent
  for parent in \
    "$_TOOL_RUNNER_PROJECT_ROOT/.rat" \
    "$_TOOL_RUNNER_PROJECT_ROOT/.rat/state"; do
    if [[ -L "$parent" || ( -e "$parent" && ! -d "$parent" ) ]]; then
      echo "ERROR: tool-runner state parent is not a directory: $parent" >&2
      return 1
    fi
  done

  if [[ -L "$_TOOL_RUNNER_STATE_FILE" || \
        ( -e "$_TOOL_RUNNER_STATE_FILE" && ! -f "$_TOOL_RUNNER_STATE_FILE" ) ]]; then
    echo "ERROR: tool-runner state destination is not a regular file: $_TOOL_RUNNER_STATE_FILE" >&2
    return 1
  fi
  if [[ -f "$_TOOL_RUNNER_STATE_FILE" ]] && \
     [[ -n "$(find "$_TOOL_RUNNER_STATE_FILE" -type f ! -links 1 -print -quit 2>/dev/null)" ]]; then
    echo "ERROR: refusing hard-linked tool-runner state: $_TOOL_RUNNER_STATE_FILE" >&2
    return 1
  fi
}

_tool_runner_verify_container_owner() {
  local container_name="$1" owner
  if ! owner=$(docker inspect --format \
    '{{ index .Config.Labels "rtl-agent-team.project-root" }}' \
    "$container_name" 2>/dev/null); then
    echo "ERROR: cannot inspect Docker container ownership: $container_name" >&2
    return 1
  fi
  if [[ "$owner" != "$_TOOL_RUNNER_PROJECT_ROOT" ]]; then
    echo "ERROR: refusing Docker container owned by another project: $container_name" >&2
    return 1
  fi
}

# Check if Docker image is available
_tool_runner_has_image() {
  docker images -q "$RTL_EDA_IMAGE" 2>/dev/null | grep -q .
}

# Ensure persistent container is running
_tool_runner_ensure_container() {
  local container_id expected_name
  _tool_runner_validate_state_file || return $?
  mkdir -p "$(dirname "$_TOOL_RUNNER_STATE_FILE")" || return $?
  _tool_runner_validate_state_file || return $?

  expected_name=$(_tool_runner_container_name)
  if [[ -n "$_TOOL_RUNNER_CONTAINER" && \
        "$_TOOL_RUNNER_CONTAINER" != "$expected_name" ]]; then
    echo "ERROR: refusing unexpected Docker container: $_TOOL_RUNNER_CONTAINER" >&2
    return 1
  fi
  _TOOL_RUNNER_CONTAINER="$expected_name"

  if ! container_id=$(docker ps -q -f "name=^${_TOOL_RUNNER_CONTAINER}$" 2>/dev/null); then
    echo "ERROR: cannot query Docker containers." >&2
    return 1
  fi
  if [[ -n "$container_id" ]]; then
    _tool_runner_verify_container_owner "$_TOOL_RUNNER_CONTAINER" || return $?
  else
    if ! container_id=$(docker ps -aq -f "name=^${_TOOL_RUNNER_CONTAINER}$" 2>/dev/null); then
      echo "ERROR: cannot query Docker containers." >&2
      return 1
    fi
    if [[ -n "$container_id" ]]; then
      _tool_runner_verify_container_owner "$_TOOL_RUNNER_CONTAINER" || return $?
      docker start "$_TOOL_RUNNER_CONTAINER" >/dev/null || return $?
    else
      echo "[tool-runner] Starting persistent Docker container: $_TOOL_RUNNER_CONTAINER" >&2
      docker run -d --name "$_TOOL_RUNNER_CONTAINER" \
        --label "$_TOOL_RUNNER_PROJECT_LABEL=$_TOOL_RUNNER_PROJECT_ROOT" \
        --user "$(id -u):$(id -g)" --env HOME=/tmp \
        --mount "type=bind,src=$_TOOL_RUNNER_PROJECT_ROOT,dst=/workspace" \
        --workdir /workspace \
        "$RTL_EDA_IMAGE" tail -f /dev/null >/dev/null || return $?
    fi
  fi

  printf '%s\n' "$_TOOL_RUNNER_CONTAINER" > "$_TOOL_RUNNER_STATE_FILE"
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
    echo "Build: docker build -t $RTL_EDA_IMAGE \"\${CLAUDE_PLUGIN_ROOT}/docker/\"" >&2
    return 127
  fi

  if ! _tool_runner_has_image; then
    echo "ERROR: '$tool' not found locally and Docker image '$RTL_EDA_IMAGE' not built." >&2
    echo "Build: docker build -t $RTL_EDA_IMAGE \"\${CLAUDE_PLUGIN_ROOT}/docker/\"" >&2
    return 127
  fi

  _tool_runner_ensure_container || return $?
  docker exec "$_TOOL_RUNNER_CONTAINER" "$tool" "$@"
}

# Stop and remove the persistent container
tool_runner_cleanup() {
  local container_id container_name="" expected_name
  _tool_runner_validate_state_file || return $?

  if [[ -n "$_TOOL_RUNNER_CONTAINER" ]]; then
    container_name="$_TOOL_RUNNER_CONTAINER"
  elif [[ -f "$_TOOL_RUNNER_STATE_FILE" ]]; then
    IFS= read -r container_name < "$_TOOL_RUNNER_STATE_FILE" || true
  else
    return 0
  fi

  expected_name=$(_tool_runner_container_name)
  if [[ "$container_name" != "$expected_name" ]]; then
    echo "[tool-runner] Refusing cleanup for unexpected container: $container_name" >&2
    rm -f "$_TOOL_RUNNER_STATE_FILE"
    return 0
  fi

  if ! container_id=$(docker ps -aq -f "name=^${container_name}$" 2>/dev/null); then
    echo "ERROR: cannot query Docker containers; preserving cleanup state." >&2
    return 1
  fi
  if [[ -n "$container_id" ]]; then
    _tool_runner_verify_container_owner "$container_name" || return $?
    echo "[tool-runner] Stopping container: $container_name" >&2
    if ! docker stop "$container_name" 2>/dev/null; then
      echo "ERROR: cannot stop Docker container; preserving cleanup state: $container_name" >&2
      return 1
    fi
    if ! docker rm "$container_name" 2>/dev/null; then
      echo "ERROR: cannot remove Docker container; preserving cleanup state: $container_name" >&2
      return 1
    fi
  fi
  rm -f "$_TOOL_RUNNER_STATE_FILE"
  _TOOL_RUNNER_CONTAINER=""
}

# --- Tool Availability & Licensing Utilities ---

# Check if a tool binary is available (local or Docker)
# Usage: check_tool_available verilator && echo "found"
check_tool_available() {
  local tool="$1"
  if command -v "$tool" >/dev/null 2>&1; then
    return 0
  fi
  # Check Docker fallback
  if command -v docker >/dev/null 2>&1 && _tool_runner_has_image; then
    docker run --rm --user "$(id -u):$(id -g)" --env HOME=/tmp \
      "$RTL_EDA_IMAGE" sh -c 'command -v "$1"' sh "$tool" >/dev/null 2>&1
    return $?
  fi
  return 1
}

# Check if a commercial tool has an active license
# Returns 0 if licensed, 1 if not. Probes tool-specific license check.
check_tool_licensed() {
  local tool="$1"
  case "$tool" in
    dc_shell|design_compiler)
      dc_shell -help </dev/null >/dev/null 2>&1; return $? ;;
    genus)
      genus -help </dev/null >/dev/null 2>&1; return $? ;;
    vcs)
      vcs -ID </dev/null >/dev/null 2>&1; return $? ;;
    xrun|xcelium)
      xrun -version </dev/null >/dev/null 2>&1; return $? ;;
    vsim|questa)
      vsim -version </dev/null >/dev/null 2>&1; return $? ;;
    sg_shell|spyglass)
      sg_shell -help </dev/null >/dev/null 2>&1; return $? ;;
    *)
      # Open-source tools: no license needed, just availability
      check_tool_available "$tool"; return $? ;;
  esac
}

# Determine synthesis tool tier
# Returns: "commercial" | "oss" | "none" (printed to stdout)
get_synthesis_tier() {
  if check_tool_available dc_shell || check_tool_available genus; then
    echo "commercial"
  elif check_tool_available yosys; then
    echo "oss"
  else
    echo "none"
  fi
}

# Determine formal verification tool tier
# Returns: "commercial" | "oss" | "none" (printed to stdout)
get_formal_tier() {
  if check_tool_available vcformal || check_tool_available jg; then
    echo "commercial"
  elif check_tool_available sby; then
    echo "oss"
  else
    echo "none"
  fi
}

# rat-version: 0.14.1
