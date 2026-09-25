"""Hook output contract (v2.0.0 Phase 1a).

Claude Code gives ``continue: false`` precedence over ``decision: "block"`` and
``permissionDecision: "deny"``: the turn ends and the reason never reaches
Claude (verified live on CLI 2.1.282). Gates therefore block through
``decision``/``permissionDecision`` only, and hand user decisions over with a
``systemMessage`` notice.
"""

import json
import re
import shutil
import subprocess

import pytest

from tests.conftest import HOOKS_DIR

LIB = HOOKS_DIR / "lib"

# A ``continue`` key whose value is anything but the literal ``true``: plain,
# escaped and split-quoted JSON, printf/jq variables, jq object syntax, and
# Python's ``False``. The whitespace after the colon sits inside the lookahead
# so that ``"continue": true`` cannot match by backtracking.
CONTINUE_NOT_TRUE = re.compile(
    r'\\?"continue\\?"\s*:(?!\s*true\b)'
    r'|[{,]\s*continue\s*:\s*(?:false|\$)'
    r'|"continue"\s*:\s*False'
)

# Sources the helpers from the directory given as $1, so no path is spliced
# into the script text.
_LOAD_LIB = '. "$1/json-util.sh"; . "$1/hook-output-util.sh"; jsonu_detect_parser; '


def _emit(func: str, message: str) -> dict:
    out = subprocess.run(
        ["sh", "-c", _LOAD_LIB + f'{func} "$2"', "sh", str(LIB), message],
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout
    return json.loads(out)


def test_stop_block_returns_reason_to_claude():
    out = _emit("emit_stop_block", 'run "verification" first')
    assert out == {"decision": "block", "reason": 'run "verification" first'}


def test_pretooluse_deny_refuses_only_the_call():
    out = _emit("emit_block", "prerequisite missing")
    assert out == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "prerequisite missing",
        }
    }


def test_stop_notice_lets_claude_stop_and_informs_user():
    out = _emit("emit_stop_notice", "waiver needs your decision")
    assert out == {"systemMessage": "waiver needs your decision"}


def test_sed_fallback_escaper_keeps_json_valid(tmp_path):
    """With neither jq nor python on PATH, jsonu_escape falls back to sed + tr.

    That branch must still emit valid JSON when the message carries control
    bytes such as ESC (colored tool output), BEL and VT.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for tool in ("sed", "tr", "cat"):
        target = shutil.which(tool)
        assert target, f"{tool} not found"
        (bin_dir / tool).symlink_to(target)
    message = 'say "hi" C:\\tmp\tcol\nnext \x1b[31mred\x1b[0m bell\x07 vt\x0b end'
    script = _LOAD_LIB + 'printf %s "$JSONU_PARSER_MODE" >&2; emit_stop_block "$2"'
    proc = subprocess.run(
        ["/bin/sh", "-c", script, "sh", str(LIB), message],
        capture_output=True, text=True, timeout=10, check=True,
        env={"PATH": str(bin_dir)},
    )
    # jq and python were not found, so jsonu_escape took its sed branch too.
    assert proc.stderr == "sed"
    out = json.loads(proc.stdout)
    assert out["decision"] == "block"
    assert 'say "hi" C:\\tmp\tcol' in out["reason"]


@pytest.mark.parametrize(
    ("snippet", "flagged"),
    [
        pytest.param(r'echo "{\"continue\":false}"', True, id="escaped-quotes"),
        pytest.param(r'''printf '{"continue":%s}' "$C"''', True, id="printf-variable"),
        pytest.param(r"""printf '{"continue":'"false"'}'""", True, id="split-quoting"),
        pytest.param("jq -n '{continue: false}'", True, id="jq-object-key"),
        pytest.param(r"""jq -n --argjson c false '{"continue": $c}'""", True, id="jq-argjson"),
        pytest.param('json.dumps({"continue": False})', True, id="python-False"),
        pytest.param(r"""printf '{"continue":true}'""", False, id="literal-true"),
        pytest.param(r"""printf '{"continue": true}'""", False, id="literal-true-spaced"),
        pytest.param(r'echo "{\"continue\":true}"', False, id="escaped-true"),
        pytest.param("auto-continue: 12s elapsed", False, id="prose"),
    ],
)
def test_continue_scan_pattern(snippet, flagged):
    assert bool(CONTINUE_NOT_TRUE.search(snippet)) is flagged


def test_no_hook_emits_continue_false():
    offenders = sorted(
        str(p.relative_to(HOOKS_DIR))
        for p in HOOKS_DIR.rglob("*.sh")
        if CONTINUE_NOT_TRUE.search(p.read_text())
    )
    assert offenders == []
