#!/usr/bin/env python3
"""SessionStart envelope for hooks/rtl-orchestrator-inject.sh.

Reads the export block of skills/rtl-orchestrate/SKILL.md when the session starts, so the
routing rules need no generated copy. Prints nothing unless the whole envelope is ready.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

PLUGIN = Path(__file__).resolve().parents[2]
SKILL = PLUGIN / "skills" / "rtl-orchestrate" / "SKILL.md"
START = "<!-- SESSIONSTART_HOOK_EXPORT_START -->"
END = "<!-- SESSIONSTART_HOOK_EXPORT_END -->"


def export_block(text: str) -> str:
    """The lines strictly between the markers, each ending with a newline."""
    lines = text.splitlines()
    start = lines.index(START)
    block = lines[start + 1:lines.index(END, start + 1)]
    if not any(line.strip() for line in block):
        raise ValueError(f"empty SessionStart export block in {SKILL}")
    return "\n".join(block) + "\n"


def envelope(skill: Path = SKILL) -> str:
    context = export_block(skill.read_text(encoding="utf-8"))
    return json.dumps({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": context}},
                      ensure_ascii=False)


def main() -> int:
    try:
        output = envelope()
    except (OSError, ValueError) as exc:
        print(f"session_inject: {exc}", file=sys.stderr)
        return 1
    sys.stdout.buffer.write(output.encode("utf-8"))  # UTF-8 whatever the session's locale
    return 0


if __name__ == "__main__":
    sys.exit(main())
