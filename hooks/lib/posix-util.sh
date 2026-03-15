#!/bin/sh
# posix-util.sh — Portable POSIX utility helpers shared across hooks.

# Get file/directory mtime as epoch seconds. Prints empty string if not found.
# Tries GNU stat first, then BSD stat.
get_mtime_epoch() {
  [ ! -e "$1" ] && return 0
  stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || printf ''
}

# Compute elapsed seconds between a given epoch timestamp and now.
# Usage: posix_elapsed_seconds <epoch_timestamp>
# Prints elapsed seconds to stdout. Prints 0 if input is empty or invalid.
posix_elapsed_seconds() {
  _ts="$1"
  [ -z "$_ts" ] && printf '0' && return 0
  _now=$(date +%s 2>/dev/null)
  [ -z "$_now" ] && printf '0' && return 0
  _elapsed=$((_now - _ts))
  [ "$_elapsed" -lt 0 ] && _elapsed=0
  printf '%s' "$_elapsed"
}
