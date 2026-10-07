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


def test_post_context_uses_the_posttooluse_envelope():
    out = _emit("emit_post_context", "loop started")
    assert out == {
        "continue": True,
        "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "loop started"},
    }


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


# Stop gates and the budget ids each counts (hooks/lib/stop-budget-util.sh).
STOP_GATES = {
    "rtl-verify-stop-gate.sh": ["verify"],
    "rtl-p6-cascade-gate.sh": ["p6-cascade"],
    "rtl-skill-completion-gate.sh": ["skill-completion"],
    "stop-gate.sh": ["ultraloop", "ppa-loop", "autopilot"],
    "rtl-coverage-exclusion-gate.sh": ["coverage-exclusion"],
}


def _code_lines(name):
    return [
        (i, line) for i, line in enumerate((HOOKS_DIR / name).read_text().splitlines())
        if not line.lstrip().startswith("#")
    ]


# Stop hooks that never block, so the breaker contract does not apply to them (none today).
STOP_NON_GATES = set()

# A line that ends the script: an emit_* helper, exit, or stopu_gate, which always exits.
EXIT = re.compile(r"\bemit_\w+|\bexit\b|\bstopu_gate\b")


def test_stop_gate_list_matches_hooks_json():
    config = json.loads((HOOKS_DIR / "hooks.json").read_text())
    registered = set()
    for entry in config["hooks"]["Stop"]:
        for hook in entry["hooks"]:
            match = re.search(r"hooks/([\w.-]+\.sh)", hook.get("command", ""))
            assert match, f"a Stop hook this contract cannot check: {hook}"
            registered.add(match.group(1))
    assert registered - STOP_NON_GATES == set(STOP_GATES)


def _allowed_early_exits(lines, chain):
    """The RAT-directory guard's exit and the team skip's exit: the first exit on the
    condition's own line or on the next code line (blank lines and comments skipped)."""
    code = [(i, line.strip()) for i, line in lines if i < chain and line.strip()]
    allowed = []
    for n, (_, line) in enumerate(code):
        if re.match(r'(if )?\[ -z "\$RAT_DIR" \]', line) or "teamu_should_skip_gate" in line:
            allowed += [i for i, later in code[n:n + 2] if EXIT.search(later)][:1]
    return allowed


@pytest.mark.parametrize("name", sorted(STOP_GATES))
def test_stop_gate_counts_every_stop_before_any_other_exit(name):
    lines = _code_lines(name)
    chain = next(i for i, line in lines if line.startswith("STOP_CHAIN=$(stopu_chain_active"))
    call = re.fullmatch(
        r'STOP_CHAIN=\$\(stopu_chain_active "\$INPUT" "[^"]+" ([\w -]+)\)', dict(lines)[chain])
    assert call and call.group(1).split() == STOP_GATES[name]
    # stopu_gate always exits, so it counts as an exit too (Task 7 follow-up).
    early = [i for i, line in lines if i < chain and EXIT.search(line)]
    skips = [i for i, line in lines if i < chain and "teamu_should_skip_gate" in line]
    assert skips, "the team skip must come before the chain count"
    assert early == _allowed_early_exits(lines, chain)
    assert any(i >= skips[0] for i in early), "the team skip must exit"


@pytest.mark.parametrize("name", sorted(STOP_GATES))
def test_stop_gate_yields_to_a_background_agent_right_after_the_chain_count(name):
    # The Stop is counted first, so the chain cap holds across yielded Stops, and nothing
    # between the count and the yield can spend the budget.
    code = [re.sub(r"\s+#.*", "", line).strip() for _, line in _code_lines(name) if line.strip()]
    chain = next(n for n, line in enumerate(code) if line.startswith("STOP_CHAIN=$(stopu_chain_active"))
    assert code[chain + 1] == 'stopu_background_agent_pending "$INPUT" && emit_post_continue'
    assert sum("stopu_background_agent_pending" in line for line in code) == 1


@pytest.mark.parametrize("name", sorted(STOP_GATES))
def test_stop_gate_budget_ids_match_its_chain_count(name):
    # A typo in an id silently removes the chain cap for that call (Task 4 review).
    code = "\n".join(line for _, line in _code_lines(name))
    used = re.findall(r"\bstopu_(?:gate|clear|decision|renotify)\b[ \t]*(\S*)", code)
    # Literal ids only: an id in a variable, or on a continuation line, would escape this check.
    assert used and all(re.fullmatch(r"[\w-]+", u) for u in used), used
    assert set(used) <= set(STOP_GATES[name])


@pytest.mark.parametrize("name", sorted(STOP_GATES))
def test_stop_gate_blocks_only_through_the_breaker(name):
    code = "\n".join(line for _, line in _code_lines(name))
    assert "emit_stop_block" not in code
    assert "emit_stop_notice" not in code  # a direct notice would repeat on every chained Stop
    assert not re.search(r'\\?"decision\\?"\s*:', code)
    # Raw JSON built in the gate, as a printf'd notice or a jq object, bypasses the breaker too.
    assert "systemMessage" not in code
    assert not re.search(r"[{,]\s*decision\s*:", code)
