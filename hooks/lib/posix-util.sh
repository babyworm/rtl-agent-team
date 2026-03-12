#!/bin/sh
# posix-util.sh — Portable POSIX utility helpers shared across hooks.

# Get file/directory mtime as epoch seconds. Prints empty string if not found.
# Tries GNU stat first, then BSD stat.
get_mtime_epoch() {
  [ ! -e "$1" ] && return 0
  stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || printf ''
}
