#!/bin/sh
# flock-util.sh — POSIX file locking utility using mkdir (atomic on all POSIX systems).
#
# Usage:
#   . "${CLAUDE_PLUGIN_ROOT}/hooks/lib/flock-util.sh"
#   acquire_lock "/path/to/resource"    # blocks up to 5s
#   ... critical section ...
#   release_lock "/path/to/resource"
#
# acquire_lock returns 0 on success, 1 on timeout.
# Callers MUST call release_lock in the same shell to avoid stale locks.
# Stale lock detection: locks older than 30s are forcibly removed.
# Known limitation: PID-based stale detection may fail if the OS reuses the PID
# for an unrelated process. In that case, the lock is reclaimed only after the
# FLOCK_STALE_AGE timeout (default 30s). This is inherent to userspace locking
# without kernel-level flock(2).

FLOCK_TIMEOUT=${FLOCK_TIMEOUT:-5}
FLOCK_STALE_AGE=${FLOCK_STALE_AGE:-30}

acquire_lock() {
  [ -z "$1" ] && return 1
  _lock_path="$1.lock"
  _waited=0

  while [ "$_waited" -lt "$FLOCK_TIMEOUT" ]; do
    if mkdir "$_lock_path" 2>/dev/null; then
      # Store PID for stale detection
      echo "$$" > "$_lock_path/pid" 2>/dev/null
      return 0
    fi

    # Stale lock detection: if lock dir exists but is older than FLOCK_STALE_AGE seconds
    if [ -d "$_lock_path" ]; then
      _lock_pid_file="$_lock_path/pid"
      if [ -f "$_lock_pid_file" ]; then
        _lock_pid=$(cat "$_lock_pid_file" 2>/dev/null)
        # If the holding process is gone, reclaim
        if [ -n "$_lock_pid" ] && ! kill -0 "$_lock_pid" 2>/dev/null; then
          rmdir "$_lock_path" 2>/dev/null || rm -rf "$_lock_path" 2>/dev/null
          continue
        fi
      fi
    fi

    sleep 1
    _waited=$((_waited + 1))
  done

  # Timeout — last resort: check age via stat if available
  if [ -d "$_lock_path" ]; then
    _now=$(date +%s 2>/dev/null)
    _lock_mtime=$(stat -c %Y "$_lock_path" 2>/dev/null || stat -f %m "$_lock_path" 2>/dev/null || echo "")
    if [ -n "$_now" ] && [ -n "$_lock_mtime" ]; then
      _age=$((_now - _lock_mtime))
      if [ "$_age" -gt "$FLOCK_STALE_AGE" ]; then
        rm -rf "$_lock_path" 2>/dev/null
        if mkdir "$_lock_path" 2>/dev/null; then
          echo "$$" > "$_lock_path/pid" 2>/dev/null
          return 0
        fi
      fi
    fi
  fi

  return 1
}

release_lock() {
  _lock_path="$1.lock"
  rm -f "$_lock_path/pid" 2>/dev/null
  rmdir "$_lock_path" 2>/dev/null || rm -rf "$_lock_path" 2>/dev/null
}
