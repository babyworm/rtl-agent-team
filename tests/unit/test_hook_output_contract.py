"""Hook output contract (v2.0.0 Phase 1a).

Claude Code gives ``continue: false`` precedence over ``decision: "block"`` and
``permissionDecision: "deny"``: the turn ends and the reason never reaches
Claude (verified live on CLI 2.1.282). Gates therefore block through
``decision``/``permissionDecision`` only, and hand user decisions over with a
``systemMessage`` notice.
"""

import json
import re
import subprocess

from tests.conftest import HOOKS_DIR

LIB = HOOKS_DIR / "lib"


def _emit(func: str, message: str) -> dict:
    script = (
        f'. "{LIB}/json-util.sh"; . "{LIB}/hook-output-util.sh"; '
        f'jsonu_detect_parser; {func} "$1"'
    )
    out = subprocess.run(
        ["sh", "-c", script, "sh", message],
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout
    return json.loads(out)


def test_stop_block_returns_reason_to_claude():
    out = _emit("emit_stop_block", 'run "verification" first')
    assert out == {"decision": "block", "reason": 'run "verification" first'}


def test_pretooluse_deny_refuses_only_the_call():
    out = _emit("emit_block", "prerequisite missing")
    assert "continue" not in out
    hso = out["hookSpecificOutput"]
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert hso["permissionDecisionReason"] == "prerequisite missing"


def test_stop_notice_lets_claude_stop_and_informs_user():
    out = _emit("emit_stop_notice", "waiver needs your decision")
    assert out == {"systemMessage": "waiver needs your decision"}


def test_no_hook_emits_continue_false():
    pattern = re.compile(r'"continue"\s*:\s*false')
    offenders = sorted(
        str(p.relative_to(HOOKS_DIR))
        for p in HOOKS_DIR.rglob("*.sh")
        if pattern.search(p.read_text())
    )
    assert offenders == []
