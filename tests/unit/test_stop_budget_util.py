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


def _gate(state_dir, chain, progress, limit=None, env=None, gate="verify"):
    args = [gate, str(state_dir), chain, progress, "keep working", "your call"]
    if limit is not None:
        args.append(str(limit))
    return json.loads(_run('stopu_gate "$@"', *args, env=env))


def _start_chain(state_dir, *gates):
    return _run('stopu_chain_active "$@"', '{"stop_hook_active": false}', str(state_dir), *gates)


def _budget(state_dir, gate="verify"):
    return (state_dir / f"stop-budget-{gate}.txt").read_text()


def test_first_stop_blocks_and_records_budget(tmp_path):
    assert _gate(tmp_path, "false", "a.sv") == BLOCK
    assert _budget(tmp_path) == f"1\n{_fp('a.sv')}\n"


def test_chain_without_progress_releases_after_limit(tmp_path):
    results = [_gate(tmp_path, "false", "a.sv")]
    results += [_gate(tmp_path, "true", "a.sv") for _ in range(3)]
    assert results == [BLOCK, BLOCK, BLOCK, NOTICE]


def test_notice_is_shown_once_per_chain(tmp_path):
    results = [_gate(tmp_path, "true", "a.sv") for _ in range(6)]
    assert results == [BLOCK, BLOCK, BLOCK, NOTICE, SILENT, SILENT]


def test_progress_restarts_a_full_budget(tmp_path):
    for _ in range(4):
        _gate(tmp_path, "true", "a.sv")
    results = [_gate(tmp_path, "true", "a.sv b.sv") for _ in range(4)]
    assert results == [BLOCK, BLOCK, BLOCK, NOTICE]


def test_chain_start_resets_named_budgets(tmp_path):
    for _ in range(4):
        _gate(tmp_path, "true", "a.sv")
    assert _start_chain(tmp_path, "verify", "p6-cascade") == "false"
    assert not (tmp_path / "stop-budget-verify.txt").exists()
    assert _gate(tmp_path, "true", "a.sv") == BLOCK


def test_chained_stop_keeps_budgets(tmp_path):
    _gate(tmp_path, "false", "a.sv")
    out = _run('stopu_chain_active "$@"', '{"stop_hook_active": true}', str(tmp_path), "verify")
    assert out == "true"
    assert (tmp_path / "stop-budget-verify.txt").exists()


def test_gate_ids_are_isolated(tmp_path):
    for _ in range(4):
        _gate(tmp_path, "true", "a.sv")
    assert _gate(tmp_path, "true", "a.sv", gate="p6-cascade") == BLOCK


def test_per_call_limit(tmp_path):
    assert _gate(tmp_path, "false", "a.sv", limit=1) == BLOCK
    assert _gate(tmp_path, "true", "a.sv", limit=1) == NOTICE


def test_env_limit_zero_turns_blocks_into_notices(tmp_path):
    env = {"RAT_STOP_BLOCK_LIMIT": "0"}
    assert _gate(tmp_path, "false", "a.sv", env=env) == NOTICE
    assert _gate(tmp_path, "false", "a.sv", limit=1, env=env) == NOTICE


def test_per_call_limit_cannot_raise_the_env_limit(tmp_path):
    env = {"RAT_STOP_BLOCK_LIMIT": "1"}
    assert _gate(tmp_path, "false", "a.sv", limit=3, env=env) == BLOCK
    assert _gate(tmp_path, "true", "a.sv", limit=3, env=env) == NOTICE


def test_clear_restores_the_budget(tmp_path):
    for _ in range(4):
        _gate(tmp_path, "true", "a.sv")
    _run('stopu_clear verify "$1"', str(tmp_path))
    assert _gate(tmp_path, "true", "a.sv") == BLOCK


def test_missing_state_dir_is_created(tmp_path):
    state = tmp_path / "missing" / "state"
    assert _gate(state, "false", "a.sv") == BLOCK
    assert _budget(state) == f"1\n{_fp('a.sv')}\n"


def test_unwritable_state_dir_hands_over_instead_of_looping(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root can write to a read-only directory")
    state = tmp_path / "state"
    state.mkdir()
    state.chmod(0o555)
    try:
        assert _gate(state, "false", "a.sv") == NOTICE
    finally:
        state.chmod(0o755)


@pytest.mark.parametrize("count", ["abc", "08", "1234567"])
def test_corrupt_count_is_treated_as_zero(tmp_path, count):
    (tmp_path / "stop-budget-verify.txt").write_text(f"{count}\n{_fp('a.sv')}\n")
    assert _gate(tmp_path, "true", "a.sv") == BLOCK
    assert _budget(tmp_path) == f"1\n{_fp('a.sv')}\n"


@pytest.mark.parametrize("limit", ["x", "99999999999999999999"])
def test_invalid_env_limit_falls_back_to_default(tmp_path, limit):
    env = {"RAT_STOP_BLOCK_LIMIT": limit}
    results = [_gate(tmp_path, "false", "a.sv", env=env)]
    results += [_gate(tmp_path, "true", "a.sv", env=env) for _ in range(3)]
    assert results == [BLOCK, BLOCK, BLOCK, NOTICE]


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


def test_chain_start_keeps_other_gates_budgets(tmp_path):
    for _ in range(4):
        _gate(tmp_path, "true", "a.sv", gate="p6-cascade")
    _start_chain(tmp_path, "verify")
    assert _gate(tmp_path, "true", "a.sv", gate="p6-cascade") == SILENT
