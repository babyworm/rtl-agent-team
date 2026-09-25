"""No-progress breaker for Stop gates: hooks/lib/stop-budget-util.sh."""

import json
import os
import subprocess

import pytest

from tests.conftest import HOOKS_DIR

LIB = HOOKS_DIR / "lib"

# Sources the helpers from the directory given as $1 (no path spliced into the
# script text), then drops it so "$@" holds the function's own arguments.
_LOAD_LIB = (
    '. "$1/json-util.sh"; . "$1/hook-output-util.sh"; '
    '. "$1/stop-budget-util.sh"; jsonu_detect_parser; shift; '
)
BLOCK = {"decision": "block", "reason": "keep working"}
NOTICE = {"systemMessage": "your call"}
SILENT = {"continue": True}


def _run(call, *args, env=None):
    return subprocess.run(
        ["sh", "-c", _LOAD_LIB + call, "sh", str(LIB), *args],
        capture_output=True, text=True, timeout=10, check=True,
        env={**os.environ, **(env or {})},
    ).stdout


def _fp(text):
    return _run('stopu_fingerprint "$1"', text)


def _input(active, prompt="prompt-1"):
    """A Stop input; like real Stops it carries a prompt_id unless prompt is None."""
    payload = {"stop_hook_active": active}
    if prompt is not None:
        payload["prompt_id"] = prompt
    return json.dumps(payload)


def _stop(state_dir, active, blocking, gates=("verify",), limit=None, env=None, prompt="prompt-1"):
    """One Stop: every gate counts the chain; gates in `blocking` (gate -> progress) try to block, the rest take their allow path.

    A gate left out of `gates` misses this Stop, as a gate that exits before counting does.
    """
    out = {}
    for gate in gates:
        count = 'STOP_CHAIN=$(stopu_chain_active "$1" "$2" "$3"); '
        if gate in blocking:
            args = [_input(active, prompt), str(state_dir), gate, blocking[gate]]
            if limit is not None:
                args.append(str(limit))
            out[gate] = json.loads(_run(
                count + 'stopu_gate "$3" "$2" "$STOP_CHAIN" "$4" "keep working" "your call" ${5:+"$5"}',
                *args, env=env))
        else:
            _run(count + 'stopu_clear "$3" "$2"', _input(active, prompt), str(state_dir), gate, env=env)
    return out


def _chain(state_dir, progress, gate="verify", **kwargs):
    """One chain where a single gate tries to block on every Stop; returns its outputs."""
    return [
        _stop(state_dir, i > 0, {gate: text}, gates=(gate,), **kwargs)[gate]
        for i, text in enumerate(progress)
    ]


def _start_chain(state_dir, *gates):
    return _run('stopu_chain_active "$@"', _input(False), str(state_dir), *gates)


def _budget(state_dir, gate="verify"):
    return (state_dir / f"stop-budget-{gate}.txt").read_text()


def _missed_start(state_dir, prompt="prompt-1"):
    """p6-cascade blocks a chain's first 4 Stops; the verify gate misses them."""
    for i in range(4):
        _stop(state_dir, i > 0, {"p6-cascade": f"p{i}.md"}, gates=("p6-cascade",), prompt=prompt)


# 1: the per-gate limit
def test_same_progress_hands_over_after_the_limit(tmp_path):
    results = [_stop(tmp_path, False, {"verify": "a.sv"})["verify"]]
    assert _budget(tmp_path) == f"1\n{_fp('a.sv')}\n1\n0\nprompt-1\n"
    results += [_stop(tmp_path, True, {"verify": "a.sv"})["verify"] for _ in range(4)]
    assert results == [BLOCK, BLOCK, BLOCK, NOTICE, SILENT]


# 2: the chain cap
def test_chain_cap_hands_over_before_claude_codes_limit(tmp_path):
    results = _chain(tmp_path, [f"a{i}.sv" for i in range(8)])
    assert results == [BLOCK] * 6 + [NOTICE, SILENT]


# 3: another plugin's Stop hook keeps the chain going
def test_stops_blocked_by_other_hooks_count_toward_the_cap(tmp_path):
    for i in range(4):
        assert _stop(tmp_path, i > 0, {}) == {}
    results = [_stop(tmp_path, True, {"verify": f"v{i}.sv"})["verify"] for i in range(3)]
    assert results == [BLOCK, BLOCK, NOTICE]


# 4
@pytest.mark.parametrize("gates", [
    ("verify", "p6-cascade"),
    ("verify", "p6-cascade", "skill-completion"),
])
def test_gates_that_block_together_keep_their_own_limit(tmp_path, gates):
    blocking = {gate: f"{gate}.txt" for gate in gates}
    stops = [_stop(tmp_path, i > 0, blocking, gates=gates) for i in range(4)]
    for gate in gates:
        assert [stop[gate] for stop in stops] == [BLOCK, BLOCK, BLOCK, NOTICE]


# 5
def test_chain_start_ignores_files_left_from_an_earlier_chain(tmp_path):
    (tmp_path / "stop-budget-verify.txt").write_text(f"3\n{_fp('a.sv')}\n6\n1\n")
    (tmp_path / "stop-budget-p6-cascade.txt").write_text(f"3\n{_fp('b.md')}\n6\n0\n")
    assert _stop(tmp_path, False, {"verify": "a.sv"})["verify"] == BLOCK


# 6
def test_missed_chain_start_takes_the_worst_case(tmp_path):
    assert _stop(tmp_path, True, {"verify": "a.sv"})["verify"] == NOTICE


# 7
def test_clear_keeps_the_chain_count(tmp_path):
    results = [
        _stop(tmp_path, False, {"verify": "a.sv"})["verify"],
        _stop(tmp_path, True, {"verify": "a.sv"})["verify"],
    ]
    assert _stop(tmp_path, True, {}) == {}
    results += [_stop(tmp_path, True, {"verify": f"b{i}.sv"})["verify"] for i in range(4)]
    assert results == [BLOCK] * 5 + [NOTICE]


# 8
def test_notice_holds_for_the_rest_of_the_chain_despite_progress(tmp_path):
    assert _chain(tmp_path, ["a.sv"] * 4) == [BLOCK, BLOCK, BLOCK, NOTICE]
    assert _stop(tmp_path, True, {"verify": "b.sv"})["verify"] == SILENT


def test_progress_restarts_the_count_before_the_notice(tmp_path):
    results = _chain(tmp_path, ["a.sv", "a.sv", "b.sv", "b.sv", "b.sv", "b.sv"])
    assert results == [BLOCK] * 5 + [NOTICE]


def test_new_chain_after_a_notice_blocks_again(tmp_path):
    assert _chain(tmp_path, ["a.sv"] * 5) == [BLOCK, BLOCK, BLOCK, NOTICE, SILENT]
    assert _stop(tmp_path, False, {"verify": "a.sv"})["verify"] == BLOCK


def test_gate_ids_are_isolated(tmp_path):
    gates = ("verify", "p6-cascade")
    spent = [_stop(tmp_path, i > 0, {"p6-cascade": "a.md"}, gates=gates)["p6-cascade"] for i in range(4)]
    assert spent == [BLOCK, BLOCK, BLOCK, NOTICE]
    both = _stop(tmp_path, True, {"verify": "a.sv", "p6-cascade": "a.md"}, gates=gates)
    assert both == {"verify": BLOCK, "p6-cascade": SILENT}


def test_staggered_gates_hand_over_at_the_seventh_stop(tmp_path):
    gates = ("verify", "p6-cascade")
    results = [_stop(tmp_path, i > 0, {"verify": f"v{i}.sv"}, gates=gates)["verify"] for i in range(3)]
    results += [_stop(tmp_path, True, {"p6-cascade": f"p{i}.md"}, gates=gates)["p6-cascade"] for i in range(4)]
    assert results == [BLOCK] * 6 + [NOTICE]


def test_chain_start_resets_named_budgets(tmp_path):
    _chain(tmp_path, ["a.sv"] * 4)
    assert _start_chain(tmp_path, "verify", "p6-cascade") == "false"
    assert _budget(tmp_path) == "0\n\n1\n0\nprompt-1\n"
    assert _budget(tmp_path, "p6-cascade") == "0\n\n1\n0\nprompt-1\n"


def test_chained_stop_advances_the_stop_count(tmp_path):
    _stop(tmp_path, False, {"verify": "a.sv"})
    assert _run('stopu_chain_active "$@"', _input(True), str(tmp_path), "verify") == "true"
    assert _budget(tmp_path) == f"1\n{_fp('a.sv')}\n2\n0\nprompt-1\n"


def test_chain_start_keeps_other_gates_budgets(tmp_path):
    assert _chain(tmp_path, ["a.md"] * 4, gate="p6-cascade") == [BLOCK, BLOCK, BLOCK, NOTICE]
    spent = _budget(tmp_path, "p6-cascade")
    _start_chain(tmp_path, "verify")
    assert _budget(tmp_path, "p6-cascade") == spent
    assert _stop(tmp_path, True, {"p6-cascade": "a.md"}, gates=("p6-cascade",))["p6-cascade"] == SILENT


def test_clear_restores_the_budget(tmp_path):
    assert _chain(tmp_path, ["a.sv"] * 4) == [BLOCK, BLOCK, BLOCK, NOTICE]
    _stop(tmp_path, True, {})
    assert _stop(tmp_path, True, {"verify": "a.sv"})["verify"] == BLOCK


# Missed chain starts and the prompt_id (line 5)
@pytest.mark.parametrize("notice_shown", ["0", "1"])
def test_missed_chain_start_is_detected_by_the_prompt_id(tmp_path, notice_shown):
    # The previous prompt's chain ended normally (or with a notice) and left this file.
    (tmp_path / "stop-budget-verify.txt").write_text(f"1\n{_fp('a.sv')}\n1\n{notice_shown}\nprompt-0\n")
    _missed_start(tmp_path)
    assert _stop(tmp_path, True, {"verify": "a.sv"})["verify"] == NOTICE


def test_without_a_prompt_id_a_leftover_count_is_trusted(tmp_path):
    # The documented limit: without prompt_id a missed chain start cannot be told apart.
    (tmp_path / "stop-budget-verify.txt").write_text(f"1\n{_fp('a.sv')}\n1\n0\nprompt-0\n")
    _missed_start(tmp_path, prompt=None)
    assert _stop(tmp_path, True, {"verify": "a.sv"}, prompt=None)["verify"] == BLOCK


def test_prompt_change_mid_chain_takes_the_worst_case(tmp_path):
    assert _stop(tmp_path, False, {"verify": "a.sv"}, prompt="prompt-1")["verify"] == BLOCK
    assert _stop(tmp_path, True, {"verify": "a.sv"}, prompt="prompt-2")["verify"] == NOTICE


@pytest.mark.parametrize("prompt", ["a/../b", "x y"])
def test_unsafe_prompt_id_is_ignored(tmp_path, prompt):
    (tmp_path / "stop-budget-verify.txt").write_text(f"1\n{_fp('a.sv')}\n1\n0\nprompt-0\n")
    _missed_start(tmp_path, prompt=prompt)
    assert _stop(tmp_path, True, {"verify": "a.sv"}, prompt=prompt)["verify"] == BLOCK
    assert _budget(tmp_path).split("\n")[4] == ""


@pytest.mark.parametrize("prompt,expected", [
    ("3f2b9a1c-7d4e-4b8a-9c21-0a1b2c3d4e5f", "3f2b9a1c-7d4e-4b8a-9c21-0a1b2c3d4e5f"),
    ("a/../b", ""),
    ("x y", ""),
    ("", ""),
    (None, ""),
])
def test_prompt_id_accepts_only_plain_tokens(prompt, expected):
    assert _run('stopu_prompt_id "$1"', _input(True, prompt)) == expected


def test_gate_without_a_chain_count_takes_the_worst_case(tmp_path):
    # A gate that breaks the contract (no stopu_chain_active call) still hands over.
    out = _run('stopu_gate verify "$1" true a.sv "keep working" "your call"', str(tmp_path))
    assert json.loads(out) == NOTICE


def test_clear_keeps_the_prompt_id(tmp_path):
    assert _stop(tmp_path, False, {"verify": "a.sv"})["verify"] == BLOCK
    _run('stopu_clear verify "$1"', str(tmp_path))
    assert _budget(tmp_path) == "0\n\n1\n0\nprompt-1\n"


# 9: limits, corrupt counts, state dir, chain detection, fingerprint
def test_per_call_limit(tmp_path):
    assert _stop(tmp_path, False, {"verify": "a.sv"}, limit=1)["verify"] == BLOCK
    assert _stop(tmp_path, True, {"verify": "a.sv"}, limit=1)["verify"] == NOTICE


def test_env_limit_zero_turns_blocks_into_notices(tmp_path):
    env = {"RAT_STOP_BLOCK_LIMIT": "0"}
    assert _stop(tmp_path, False, {"verify": "a.sv"}, env=env)["verify"] == NOTICE
    assert _stop(tmp_path, False, {"verify": "a.sv"}, limit=1, env=env)["verify"] == NOTICE


def test_per_call_limit_cannot_raise_the_env_limit(tmp_path):
    env = {"RAT_STOP_BLOCK_LIMIT": "1"}
    assert _stop(tmp_path, False, {"verify": "a.sv"}, limit=3, env=env)["verify"] == BLOCK
    assert _stop(tmp_path, True, {"verify": "a.sv"}, limit=3, env=env)["verify"] == NOTICE


@pytest.mark.parametrize("limit", ["x", "99999999999999999999"])
def test_invalid_env_limit_falls_back_to_default(tmp_path, limit):
    env = {"RAT_STOP_BLOCK_LIMIT": limit}
    assert _chain(tmp_path, ["a.sv"] * 4, env=env) == [BLOCK, BLOCK, BLOCK, NOTICE]


@pytest.mark.parametrize("count", ["abc", "08", "1234567"])
def test_corrupt_count_is_treated_as_zero(tmp_path, count):
    (tmp_path / "stop-budget-verify.txt").write_text(f"{count}\n{_fp('a.sv')}\n1\n0\nprompt-1\n")
    assert _stop(tmp_path, True, {"verify": "a.sv"})["verify"] == BLOCK
    assert _budget(tmp_path) == f"1\n{_fp('a.sv')}\n2\n0\nprompt-1\n"


@pytest.mark.parametrize("stops", ["", "abc", "0"])
def test_corrupt_stop_count_takes_the_worst_case(tmp_path, stops):
    (tmp_path / "stop-budget-verify.txt").write_text(f"0\n\n{stops}\n0\nprompt-1\n")
    assert _stop(tmp_path, True, {"verify": "a.sv"})["verify"] == NOTICE


def test_missing_state_dir_is_created(tmp_path):
    state = tmp_path / "missing" / "state"
    assert _stop(state, False, {"verify": "a.sv"})["verify"] == BLOCK
    assert _budget(state) == f"1\n{_fp('a.sv')}\n1\n0\nprompt-1\n"


def test_unwritable_state_dir_hands_over_instead_of_looping(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root can write to a read-only directory")
    state = tmp_path / "state"
    state.mkdir()
    state.chmod(0o555)
    try:
        assert _stop(state, False, {"verify": "a.sv"})["verify"] == NOTICE
    finally:
        state.chmod(0o755)


@pytest.mark.parametrize("payload,expected", [
    ('{"stop_hook_active":true}', "true"),
    ('{"cwd": "/x", "stop_hook_active": true}', "true"),
    ('{"stop_hook_active":false}', "false"),
    ('{"cwd": "/x"}', "false"),
    ('{"stop_hook_active": false, "last_assistant_message": "quoted \\"stop_hook_active\\": true"}', "false"),
])
def test_chain_active_detection(payload, expected):
    assert _run('stopu_chain_active "$1"', payload) == expected


def test_fingerprint_is_one_token_deterministic_and_sensitive():
    first = _fp("a.sv\nb.sv\n")
    assert first and "\n" not in first and " " not in first
    assert _fp("a.sv\nb.sv\n") == first
    assert _fp("a.sv\nc.sv\n") != first
