"""Direct unit tests for hooks/lib/json-util.sh parser functions."""

import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.conftest import HOOKS_DIR

JSON_UTIL = HOOKS_DIR / "lib" / "json-util.sh"

# ── Parser mode parametrization ───────────────────────────────────────────────

PARSER_ENVS = [
    pytest.param({}, id="default-parser"),
    pytest.param({"RTL_FORCE_JSON_FALLBACK": "1"}, id="sed-fallback"),
    pytest.param({"RTL_FORCE_PYTHON_PARSER": "1"}, id="python-mode"),
]


# ── Low-level helpers ─────────────────────────────────────────────────────────

def _run_sh(script, stdin_data=None, env_override=None, timeout=10):
    """Run a sh script fragment; return (stdout_stripped, returncode)."""
    merged_env = {**os.environ, **(env_override or {})}
    result = subprocess.run(
        ["sh", "-c", script],
        capture_output=True,
        text=True,
        input=stdin_data,
        env=merged_env,
        timeout=timeout,
    )
    return result.stdout.strip(), result.returncode


def _preamble(env=None):
    """Return the source + detect preamble lines used by every helper."""
    return f'. "{JSON_UTIL}"\njsonu_detect_parser\n'


def _escape(value, env=None):
    """Call jsonu_escape with the given value literal (already shell-quoted)."""
    script = _preamble(env) + f"jsonu_escape {value}"
    out, _ = _run_sh(script, env_override=env)
    return out


def _input_string(json_str, key, env=None):
    """Call jsonu_get_input_string reading JSON from stdin."""
    script = _preamble(env) + 'INPUT=$(cat)\njsonu_get_input_string "$INPUT" ' + f'"{key}"'
    out, _ = _run_sh(script, stdin_data=json_str, env_override=env)
    return out


def _file_string(tmp_path, data, key_path, env=None):
    """Write data to a temp JSON file; call jsonu_get_file_path_string."""
    f = tmp_path / "test.json"
    f.write_text(json.dumps(data) if isinstance(data, dict) else data)
    script = _preamble(env) + f'jsonu_get_file_path_string "{f}" "{key_path}"'
    out, _ = _run_sh(script, env_override=env)
    return out


def _file_bool(tmp_path, data, key_path, env=None):
    """Write data to a temp JSON file; call jsonu_get_file_path_bool."""
    f = tmp_path / "test.json"
    f.write_text(json.dumps(data) if isinstance(data, dict) else data)
    script = _preamble(env) + f'jsonu_get_file_path_bool "{f}" "{key_path}"'
    out, _ = _run_sh(script, env_override=env)
    return out


def _file_num(tmp_path, data, key_path, env=None):
    """Write data to a temp JSON file; call jsonu_get_file_path_num."""
    f = tmp_path / "test.json"
    f.write_text(json.dumps(data) if isinstance(data, dict) else data)
    script = _preamble(env) + f'jsonu_get_file_path_num "{f}" "{key_path}"'
    out, _ = _run_sh(script, env_override=env)
    return out


# ── TestJsonuEscape ────────────────────────────────────────────────────────────

class TestJsonuEscape:
    """Tests for jsonu_escape."""

    def test_plain_string(self):
        result = _escape("'hello world'")
        assert result == "hello world"

    def test_double_quotes_escaped(self):
        # Pass a string containing a double-quote; use a variable to avoid
        # shell quoting ambiguity with $'...' syntax in subprocess
        script = _preamble() + 'V=\'say "hello"\'\njsonu_escape "$V"'
        out, _ = _run_sh(script)
        assert out == r'say \"hello\"'

    def test_backslash_escaped(self):
        # A single backslash in the input must become two backslashes
        script = _preamble() + "jsonu_escape " + r"""$'back\\slash'"""
        out, _ = _run_sh(script)
        assert "\\\\" in out

    def test_tab_escaped(self):
        script = _preamble() + "jsonu_escape " + r"""$'tab\there'"""
        out, _ = _run_sh(script)
        assert "\\t" in out

    def test_empty_string(self):
        result = _escape('""')
        assert result == ""

    def test_newline_replaced_with_space(self):
        # Newlines should become spaces
        script = _preamble() + "jsonu_escape " + r"""$'line1\nline2'"""
        out, _ = _run_sh(script)
        assert "\n" not in out
        assert "line1" in out
        assert "line2" in out


# ── TestJsonuDetectParser ─────────────────────────────────────────────────────

class TestJsonuDetectParser:
    """Tests for jsonu_detect_parser."""

    def test_default_mode_is_valid(self):
        script = _preamble() + "printf '%s' \"$JSONU_PARSER_MODE\""
        out, rc = _run_sh(script)
        assert rc == 0
        assert out in ("jq", "python", "sed")

    def test_forced_fallback_sets_sed(self):
        script = _preamble({"RTL_FORCE_JSON_FALLBACK": "1"}) + "printf '%s' \"$JSONU_PARSER_MODE\""
        out, rc = _run_sh(script, env_override={"RTL_FORCE_JSON_FALLBACK": "1"})
        assert rc == 0
        assert out == "sed"

    def test_forced_fallback_clears_py_bin(self):
        script = _preamble() + "printf '%s' \"${JSONU_PY_BIN:-empty}\""
        out, rc = _run_sh(script, env_override={"RTL_FORCE_JSON_FALLBACK": "1"})
        assert rc == 0
        assert out == "empty"


# ── TestJsonuGetInputString ───────────────────────────────────────────────────

class TestJsonuGetInputString:
    """Tests for jsonu_get_input_string (JSON from positional arg)."""

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_simple_key(self, env):
        stdin = json.dumps({"cwd": "/home/user/project"})
        assert _input_string(stdin, "cwd", env) == "/home/user/project"

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_key_with_spaces_in_value(self, env):
        stdin = json.dumps({"msg": "hello world"})
        assert _input_string(stdin, "msg", env) == "hello world"

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_missing_key_returns_empty(self, env):
        stdin = json.dumps({"other": "value"})
        assert _input_string(stdin, "missing_key", env) == ""

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_empty_json_object_returns_empty(self, env):
        assert _input_string("{}", "anykey", env) == ""

    # ── tool_input nesting (real Claude Code hook payload shape) ──────────────
    # Claude Code delivers tool parameters nested under `.tool_input`; only
    # session-level fields (cwd, session_id, tool_name) sit at the root. These
    # tests lock the nested-first + root-fallback contract across ALL parser
    # modes so a jq/python environment can no longer silently read empty (the
    # bug that left Rule 5 unarmed when jq/python were installed).

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_tool_input_nested_file_path(self, env):
        stdin = json.dumps({
            "cwd": "/proj", "tool_name": "Edit",
            "tool_input": {"file_path": "rtl/top.sv"},
        })
        assert _input_string(stdin, "file_path", env) == "rtl/top.sv"

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_tool_input_nested_command(self, env):
        stdin = json.dumps({
            "cwd": "/proj", "tool_name": "Bash",
            "tool_input": {"command": "verilator --lint-only top.sv"},
        })
        assert _input_string(stdin, "command", env) == "verilator --lint-only top.sv"

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_tool_input_nested_skill(self, env):
        stdin = json.dumps({
            "cwd": "/proj", "tool_name": "Skill",
            "tool_input": {"skill": "rtl-agent-team:rtl-p5-verify"},
        })
        assert _input_string(stdin, "skill", env) == "rtl-agent-team:rtl-p5-verify"

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_root_cwd_alongside_tool_input(self, env):
        # cwd is a root field; must still resolve when tool_input is present.
        stdin = json.dumps({
            "cwd": "/proj", "tool_name": "Edit",
            "tool_input": {"file_path": "x.sv"},
        })
        assert _input_string(stdin, "cwd", env) == "/proj"

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_flat_payload_still_works(self, env):
        # Legacy/flat shape (no tool_input) must keep resolving via root fallback.
        stdin = json.dumps({"cwd": "/proj", "file_path": "rtl/top.sv"})
        assert _input_string(stdin, "file_path", env) == "rtl/top.sv"

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_non_object_tool_input_falls_back_to_root(self, env):
        # A malformed non-object tool_input must not error/blank out root fields
        # (jq guards the type; python guards with isinstance; sed scans anyway).
        stdin = json.dumps({"cwd": "/proj", "tool_input": "bad"})
        assert _input_string(stdin, "cwd", env) == "/proj"

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_null_tool_input_falls_back_to_root(self, env):
        stdin = json.dumps({"cwd": "/proj", "tool_input": None})
        assert _input_string(stdin, "cwd", env) == "/proj"

    def test_non_string_value_returns_empty_python_mode(self):
        # python mode: isinstance(str) check means non-string values return empty.
        stdin = json.dumps({"nested": {"inner": "val"}})
        out = _input_string(stdin, "nested", {"RTL_FORCE_JSON_FALLBACK": "0",
                                               "PATH": os.environ.get("PATH", "")})
        # Force python mode by masking jq
        script = (
            f'. "{JSON_UTIL}"\n'
            'JSONU_PARSER_MODE=python\n'
            'JSONU_PY_BIN=python3\n'
            'INPUT=$(cat)\n'
            'jsonu_get_input_string "$INPUT" "nested"'
        )
        out, _ = _run_sh(script, stdin_data=stdin)
        assert out == ""


# ── TestJsonuGetFilePathString ────────────────────────────────────────────────

class TestJsonuGetFilePathString:
    """Tests for jsonu_get_file_path_string."""

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_flat_key(self, tmp_path, env):
        assert _file_string(tmp_path, {"status": "completed"}, "status", env) == "completed"

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_missing_key_returns_empty(self, tmp_path, env):
        assert _file_string(tmp_path, {"other": "x"}, "nope", env) == ""

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_missing_file_returns_empty(self, tmp_path, env):
        f = tmp_path / "nonexistent.json"
        script = _preamble(env) + f'jsonu_get_file_path_string "{f}" "key"'
        out, _ = _run_sh(script, env_override=env)
        assert out == ""

    def test_numeric_value_as_string_default_parser(self, tmp_path):
        # jq/python: tostring/str() converts numeric to string representation
        result = _file_string(tmp_path, {"count": 42}, "count", {})
        assert result == "42"

    def test_numeric_value_as_string_sed_returns_empty(self, tmp_path):
        # sed fallback only matches quoted string values; unquoted numbers return empty
        result = _file_string(tmp_path, {"count": 42}, "count",
                              {"RTL_FORCE_JSON_FALLBACK": "1"})
        assert result == ""

    def test_nested_key_default_parser(self, tmp_path):
        # Deep nested path only reliable with jq/python
        result = _file_string(tmp_path, {"a": {"b": {"c": "deep"}}}, "a.b.c", {})
        assert result == "deep"

    def test_nested_key_sed_fails_closed(self, tmp_path):
        # sed fallback returns empty for nested paths (fail-closed: prevents shadowed key risk)
        data = {"wrapper": {"unique_leaf": "found"}}
        result = _file_string(tmp_path, data, "wrapper.unique_leaf",
                              {"RTL_FORCE_JSON_FALLBACK": "1"})
        assert result == ""


# ── TestJsonuGetFilePathBool ──────────────────────────────────────────────────

class TestJsonuGetFilePathBool:
    """Tests for jsonu_get_file_path_bool."""

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_true_value(self, tmp_path, env):
        assert _file_bool(tmp_path, {"active": True}, "active", env) == "true"

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_false_value(self, tmp_path, env):
        assert _file_bool(tmp_path, {"active": False}, "active", env) == "false"

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_string_value_returns_empty(self, tmp_path, env):
        # A string is not a boolean — should return empty
        assert _file_bool(tmp_path, {"active": "yes"}, "active", env) == ""

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_missing_key_returns_empty(self, tmp_path, env):
        assert _file_bool(tmp_path, {"other": True}, "missing", env) == ""

    def test_nested_bool_default_parser(self, tmp_path):
        result = _file_bool(tmp_path, {"team": {"active": True}}, "team.active", {})
        assert result == "true"

    def test_nested_bool_sed_fails_closed(self, tmp_path):
        # sed fallback returns empty for nested paths (fail-closed: prevents shadowed key risk)
        data = {"team": {"team_enabled": True}}
        result = _file_bool(tmp_path, data, "team.team_enabled",
                            {"RTL_FORCE_JSON_FALLBACK": "1"})
        assert result == ""


# ── TestJsonuGetFilePathNum ───────────────────────────────────────────────────

class TestJsonuGetFilePathNum:
    """Tests for jsonu_get_file_path_num."""

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_integer(self, tmp_path, env):
        assert _file_num(tmp_path, {"count": 5}, "count", env) == "5"

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_zero(self, tmp_path, env):
        assert _file_num(tmp_path, {"count": 0}, "count", env) == "0"

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_string_value_returns_empty(self, tmp_path, env):
        assert _file_num(tmp_path, {"count": "five"}, "count", env) == ""

    @pytest.mark.parametrize("env", PARSER_ENVS)
    def test_missing_key_returns_empty(self, tmp_path, env):
        assert _file_num(tmp_path, {"other": 3}, "missing", env) == ""

    def test_float_non_integer_returns_empty_default_parser(self, tmp_path):
        # 3.14 is not an integer — jq/python should return empty
        result = _file_num(tmp_path, {"val": 3.14}, "val", {})
        assert result == ""

    def test_float_whole_number_returns_integer_default_parser(self, tmp_path):
        # 5.0 is a whole number — python returns "5"; jq may return "5" or "5.0"
        result = _file_num(tmp_path, {"val": 5.0}, "val", {})
        assert result in ("5", "5.0")

    def test_nested_num_default_parser(self, tmp_path):
        result = _file_num(tmp_path, {"phase": {"step": 3}}, "phase.step", {})
        assert result == "3"

    def test_nested_num_sed_fails_closed(self, tmp_path):
        # sed fallback returns empty for nested paths (fail-closed: prevents shadowed key risk)
        data = {"phase": {"phase_step": 7}}
        result = _file_num(tmp_path, data, "phase.phase_step",
                           {"RTL_FORCE_JSON_FALLBACK": "1"})
        assert result == ""


# ── TestPythonModeArraySerialization ────────────────────────────────────────


class TestPythonModeArraySerialization:
    """Tests for python parser mode array value handling."""

    def test_python_mode_array_serialization(self, tmp_path):
        """Python mode should return array values as valid JSON."""
        env = {"RTL_FORCE_PYTHON_PARSER": "1"}
        result = _file_string(tmp_path, {"items": ["a", "b", "c"]}, "items", env)
        assert result == '["a","b","c"]' or result == '["a", "b", "c"]'
        # Verify it is valid JSON
        parsed = json.loads(result)
        assert parsed == ["a", "b", "c"]
