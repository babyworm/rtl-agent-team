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


def _run(call, *args, env=None):
    return subprocess.run(
        ["sh", "-c", _LOAD_LIB + call, "sh", str(LIB), *args],
        capture_output=True, text=True, timeout=10, check=True,
        env={**os.environ, **(env or {})},
    ).stdout


def _gate(state_dir, chain, fingerprint, limit=None, env=None):
    args = ["verify", str(state_dir), chain, fingerprint, "keep working", "your call"]
    if limit is not None:
        args.append(str(limit))
    return json.loads(_run('stopu_gate "$@"', *args, env=env))


def test_first_stop_blocks_and_records_budget(tmp_path):
    assert _gate(tmp_path, "false", "fp1") == BLOCK
    assert (tmp_path / "stop-budget-verify.txt").read_text() == "1\nfp1\n"


def test_chain_without_progress_releases_after_limit(tmp_path):
    results = [_gate(tmp_path, "false", "fp1")]
    results += [_gate(tmp_path, "true", "fp1") for _ in range(3)]
    assert results == [BLOCK, BLOCK, BLOCK, NOTICE]


def test_progress_restarts_the_count(tmp_path):
    for _ in range(3):
        _gate(tmp_path, "true", "fp1")
    assert _gate(tmp_path, "true", "fp2") == BLOCK


def test_new_chain_restarts_the_count(tmp_path):
    for _ in range(4):
        _gate(tmp_path, "true", "fp1")
    assert _gate(tmp_path, "false", "fp1") == BLOCK


def test_released_gate_stays_released_for_the_rest_of_the_chain(tmp_path):
    for _ in range(4):
        _gate(tmp_path, "true", "fp1")
    assert _gate(tmp_path, "true", "fp1") == NOTICE


def test_per_call_limit(tmp_path):
    assert _gate(tmp_path, "false", "fp1", limit=1) == BLOCK
    assert _gate(tmp_path, "true", "fp1", limit=1) == NOTICE


def test_env_limit_zero_turns_blocks_into_notices(tmp_path):
    assert _gate(tmp_path, "false", "fp1", env={"RAT_STOP_BLOCK_LIMIT": "0"}) == NOTICE


def test_clear_forgets_the_budget(tmp_path):
    _gate(tmp_path, "false", "fp1")
    _run('stopu_clear verify "$1"', str(tmp_path))
    assert not (tmp_path / "stop-budget-verify.txt").exists()


def test_missing_state_dir_is_created(tmp_path):
    state = tmp_path / "missing" / "state"
    assert _gate(state, "false", "fp1") == BLOCK
    assert (state / "stop-budget-verify.txt").read_text() == "1\nfp1\n"


def test_unwritable_state_dir_hands_over_instead_of_looping(tmp_path):
    if os.geteuid() == 0:
        pytest.skip("root can write to a read-only directory")
    state = tmp_path / "state"
    state.mkdir()
    state.chmod(0o555)
    try:
        assert _gate(state, "false", "fp1") == NOTICE
    finally:
        state.chmod(0o755)


def test_corrupt_count_is_treated_as_zero(tmp_path):
    (tmp_path / "stop-budget-verify.txt").write_text("abc\nfp1\n")
    assert _gate(tmp_path, "true", "fp1") == BLOCK
    assert (tmp_path / "stop-budget-verify.txt").read_text() == "1\nfp1\n"


def test_non_numeric_env_limit_falls_back_to_default(tmp_path):
    env = {"RAT_STOP_BLOCK_LIMIT": "x"}
    results = [_gate(tmp_path, "false", "fp1", env=env)]
    results += [_gate(tmp_path, "true", "fp1", env=env) for _ in range(3)]
    assert results == [BLOCK, BLOCK, BLOCK, NOTICE]


@pytest.mark.parametrize("payload,expected", [
    ('{"stop_hook_active":true}', "true"),
    ('{"cwd": "/x", "stop_hook_active": true}', "true"),
    ('{"stop_hook_active":false}', "false"),
    ('{"cwd": "/x"}', "false"),
])
def test_chain_active_detection(payload, expected):
    assert _run('stopu_chain_active "$1"', payload) == expected


def test_fingerprint_is_one_token():
    out = _run('stopu_fingerprint "$1"', "a.sv\nb.sv\n")
    assert out and "\n" not in out and " " not in out
