#!/bin/sh
# flock-util.sh — POSIX file locking utility using mkdir (atomic on all POSIX systems).
#
# Usage:
#   . "${CLAUDE_PLUGIN_ROOT}/hooks/lib/flock-util.sh"
#   acquire_lock "/path/to/resource"    # blocks up to FLOCK_TIMEOUT s (default 2)
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

# Default acquire timeout is kept BELOW the per-hook 3s budget in hooks/hooks.json
# so a contended lock cannot sleep past the budget and get the hook SIGKILLed
# mid-wait (which would leave the lock dir behind). All callers treat a failed
# acquire_lock as non-fatal (they fall back to a lock-free path), so a short
# timeout only trades a rare skipped critical section for guaranteed liveness.
FLOCK_TIMEOUT=${FLOCK_TIMEOUT:-2}
FLOCK_STALE_AGE=${FLOCK_STALE_AGE:-30}

# Poll granularity: fine-grained polling lets several hooks that contend for the
# same lock (each holding it only briefly) all acquire within FLOCK_TIMEOUT,
# instead of serializing at most one per second. POSIX sleep only guarantees
# integer seconds, but GNU/BSD/busybox all accept fractions — probe once and
# fall back to whole-second polling where fractions are unsupported.
if sleep 0.001 2>/dev/null; then
  _FLOCK_POLL_SLEEP=0.05
  _FLOCK_POLLS_PER_SEC=20
else
  _FLOCK_POLL_SLEEP=1
  _FLOCK_POLLS_PER_SEC=1
fi

acquire_lock() {
  [ -z "$1" ] && return 1
  _lock_path="$1.lock"
  _attempt=0
  _max_attempts=$((FLOCK_TIMEOUT * _FLOCK_POLLS_PER_SEC))
  [ "$_max_attempts" -lt 1 ] && _max_attempts=1

  while [ "$_attempt" -lt "$_max_attempts" ]; do
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
          if rm -rf "$_lock_path" 2>/dev/null; then
            continue  # Retry mkdir immediately on successful removal
          fi
          # rm failed — fall through to sleep to avoid CPU spin
        fi
      fi
    fi

    sleep "$_FLOCK_POLL_SLEEP"
    _attempt=$((_attempt + 1))
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
  [ -z "$1" ] && return 0
  _lock_path="$1.lock"
  rm -f "$_lock_path/pid" 2>/dev/null
  rmdir "$_lock_path" 2>/dev/null || rm -rf "$_lock_path" 2>/dev/null
}
