#!/bin/sh
# rat-dir-util.sh — POSIX sh utility to resolve the RAT project state directory.
#
# Primary directory: .rat (v0.8.12+)
# Legacy fallback:   .rtl-agent-team (v0.8.11 and earlier)
#
# Usage:
#   . "$SCRIPT_DIR/lib/rat-dir-util.sh"
#   if rat_is_project "$CWD"; then
#     RAT_DIR=$(rat_project_dir "$CWD")
#   fi

# Optional override: when RAT_PROJECT_ROOT is set AND points at an existing
# directory, it replaces the caller-supplied directory for the marker check.
# This lets an external driver (e.g. a Workflow orchestrator whose subagents
# default to a different CWD) point all hooks at the real project root.
# When RAT_PROJECT_ROOT is unset, empty, OR not a directory, resolution follows
# the rules in rat_project_dir below. Only when CLAUDE_PROJECT_DIR is unset too
# is that the legacy CWD-based logic, unchanged.
# The existence contract (return 1 when no marker) is preserved: if an overriding
# RAT_PROJECT_ROOT directory has no .rat/.rtl-agent-team marker, resolution still
# fails exactly as before. The `-d` test is set -u safe (it reads ${..:-}) and
# set -e safe (a failing `if` condition does not trigger errexit).

# State/audit trees never accept repository-supplied links as write targets.
ratu_safe_tree() {
  for _RST_PATH in "$1" "$1/state" "$1/audit"; do
    if [ -L "$_RST_PATH" ]; then
      printf '%s\n' "[RAT] refusing symlinked state path: $_RST_PATH" >&2
      return 1
    fi
  done
  for _RST_DIR in "$1/state" "$1/audit"; do
    [ -d "$_RST_DIR" ] || continue
    if [ -n "$(find "$_RST_DIR" -type l -print -quit 2>/dev/null)" ]; then
      printf '%s\n' "[RAT] refusing symlinked state file under $_RST_DIR" >&2
      return 1
    fi
  done
}

# Atomic replacement also refuses a linked target. Call with data on stdin.
ratu_state_write() {
  [ ! -L "$1" ] || return 1
  _RSW_TMP=$(mktemp "${1}.XXXXXX") || return 1
  if cat > "$_RSW_TMP" && mv -f "$_RSW_TMP" "$1"; then return 0; fi
  rm -f "$_RSW_TMP"
  return 1
}

ratu_normalize_path() {
  awk -v base="$2" -v root="$3" -v value="$1" 'BEGIN {
    sub(/^[A-Za-z_][A-Za-z0-9_]*=/,"",value)
    if (substr(value,1,1)!="/") value=base "/" value
    n=split(value,a,"/"); k=0
    for(i=1;i<=n;i++) {
      if(a[i]=="" || a[i]==".") continue
      if(a[i]=="..") {if(k>0) k--; continue}
      b[++k]=a[i]
    }
    out="";for(i=1;i<=k;i++) out=out "/" b[i]
    if(index(out,root "/")==1) out=substr(out,length(root)+2)
    print out
  }'
}

# Print the marker directory (.rat, else legacy .rtl-agent-team) inside $1, or
# return 1 when $1 has neither.
_rat_marker_dir() {
  if [ -d "$1/.rat" ]; then
    ratu_safe_tree "$1/.rat" || return 1
    printf '%s' "$1/.rat"
  elif [ -d "$1/.rtl-agent-team" ]; then
    ratu_safe_tree "$1/.rtl-agent-team" || return 1
    printf '%s' "$1/.rtl-agent-team"
  else
    return 1
  fi
}

# Print the RAT state directory for a hook whose working directory is $1.
# Claude Code reports the session's current directory as the hook cwd, and a
# `cd rtl` persists, so the project's marker is often above $1. In order:
#   1. RAT_PROJECT_ROOT's marker, when that variable names a directory;
#   2. the marker at the Claude Code project root ($CLAUDE_PROJECT_DIR);
#   3. walking up from $1 to the project root, the nearest marker whose directory
#      also holds rat_config.json (a project rat-init-project initialized);
#   4. the same walk, the nearest marker of any kind (older projects).
# The walk never goes above the project root; without CLAUDE_PROJECT_DIR only $1
# itself is checked. A relative `.rat/state/...` write made from a subdirectory
# leaves a stray marker there, and rules 2 and 3 keep it from capturing the
# project. Prints nothing and returns 1 when no marker is found.
rat_project_dir() {
  if [ -d "${RAT_PROJECT_ROOT:-}" ]; then
    _rat_marker_dir "$RAT_PROJECT_ROOT"
    return
  fi
  _RPD_ROOT=${CLAUDE_PROJECT_DIR:-}
  _RPD_ROOT=${_RPD_ROOT%/}
  [ -n "$_RPD_ROOT" ] && _rat_marker_dir "$_RPD_ROOT" && return 0
  _RPD_TOP=$1
  if [ -n "$_RPD_ROOT" ]; then
    case "$1/" in "$_RPD_ROOT"/*) _RPD_TOP=$_RPD_ROOT ;; esac
  fi
  _rat_walk "$1" "$_RPD_TOP" initialized || _rat_walk "$1" "$_RPD_TOP" any
}

# Walk up from $1 to $2 inclusive and print the first marker directory found.
# With "initialized", only a marker whose directory holds rat_config.json counts.
# The walk ends at the first directory outside $2, so a trailing slash in $1
# cannot carry it past $2.
_rat_walk() {
  _RW=$1
  while :; do
    if [ "$3" = "any" ] || [ -f "$_RW/rat_config.json" ]; then
      _rat_marker_dir "$_RW" && return 0
    fi
    _RW_UP=$(dirname "$_RW")
    case "$_RW_UP/" in "$2"/*) ;; *) return 1 ;; esac
    [ "$_RW_UP" = "$_RW" ] && return 1
    _RW=$_RW_UP
  done
}

# Return 0 when rat_project_dir finds a marker for $1.
rat_is_project() {
  rat_project_dir "$1" > /dev/null
}
