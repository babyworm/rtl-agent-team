#!/usr/bin/env python3
"""Measure changes to project HDL across a paired Claude Code tool event."""

import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from verify_evidence import atomic_json, digest


EXTENSIONS = {".sv", ".svh", ".v", ".vh"}
TOOL_EVENTS = {"PreToolUse", "PostToolUse", "PostToolUseFailure"}
OUTPUT_ROOTS = {"syn", "lint", "reviews", "docs"}
IGNORED_DIRS = {".git", ".rat", ".rtl-agent-team", ".claude", ".worktrees",
                ".venv", "node_modules", "obj_dir", "sim_build"}


def is_source(relative):
    return (relative.suffix in EXTENSIONS
            and relative.parts[0] not in OUTPUT_ROOTS
            and not IGNORED_DIRS.intersection(relative.parts)
            and relative.parts[:2] != ("sim", "build")
            and not any(char in str(relative) for char in "\r\n"))


def source_tree(root):
    for folder, dirs, files in os.walk(root):
        directory = Path(folder)
        relative = directory.relative_to(root)
        prune = IGNORED_DIRS | (OUTPUT_ROOTS if directory == root else set())
        if relative.parts == ("sim",):
            prune = prune | {"build"}
        dirs[:] = [name for name in dirs if name not in prune]
        for name in files:
            path = directory / name
            if is_source(path.relative_to(root)):
                yield path


def candidates(root, tool, payload):
    if tool == "Bash":
        return source_tree(root)
    raw = payload.get("tool_input", {}).get("file_path", "")
    if not raw:
        return None
    path = (Path(payload.get("cwd") or root) / raw).resolve()
    if path.is_relative_to(root) and is_source(path.relative_to(root)):
        return [path]
    return None


def snapshot(paths, root):
    values = {}
    for path in paths:
        if not path.is_file() or path.is_symlink():
            continue
        try:
            values[str(path.relative_to(root))] = digest(path)
        except FileNotFoundError:
            # Another tool removed this file while we were reading the tree.
            continue
    return values


def main(root, state):
    payload = json.load(sys.stdin)
    event = payload.get("hook_event_name")
    tool = payload.get("tool_name")
    tool_id = payload.get("tool_use_id", "")
    if event not in TOOL_EVENTS or tool not in {"Bash", "Edit", "Write"}:
        return 0
    if not isinstance(tool_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,160}", tool_id):
        return 1
    key = hashlib.sha256(json.dumps([payload.get("session_id"), tool_id]).encode()).hexdigest()
    directory = state / "rtl-tool-snapshots"
    if directory.is_symlink():
        return 1
    path = directory / (key + ".json")
    paths = candidates(root, tool, payload)
    if paths is None:
        return 0
    if event == "PreToolUse":
        current = snapshot(paths, root)
        # Old snapshots can remain after a tool call is denied or a session is killed.
        for old in directory.glob("*.json"):
            try:
                if time.time() - old.stat().st_mtime > 86400:
                    old.unlink(missing_ok=True)
            except FileNotFoundError:
                continue
        atomic_json(path, current)
        return 0
    if not path.is_file() or path.is_symlink():
        return 1
    before = json.loads(path.read_text())
    after = snapshot(paths, root)
    path.unlink(missing_ok=True)
    for name in sorted(before.keys() | after.keys()):
        if before.get(name) != after.get(name):
            print(root / name)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(Path(sys.argv[1]).resolve(), Path(sys.argv[2])))
    except (OSError, ValueError, TypeError, AttributeError):
        sys.exit(1)
