"""Direct slash commands must obey the same prerequisites and completion state."""

import json

import pytest

from tests.conftest import HOOKS_DIR, REPO_ROOT, run_hook


@pytest.fixture(params=[{}, {"RTL_FORCE_PYTHON_PARSER": "1"}, {"RTL_FORCE_JSON_FALLBACK": "1"}])
def expansion_env(request, tmp_project):
    marker = tmp_project / ".claude/rules/rtl-coding-conventions.md"
    marker.parent.mkdir(parents=True)
    marker.write_text("# project conventions\n")
    return {"HOME": str(tmp_project / "home"), "CLAUDE_PLUGIN_ROOT": str(REPO_ROOT), **request.param}


def expand(project, env, command="rtl-agent-team:rtl-p4-rapid-impl", **fields):
    payload = {
        "cwd": str(project), "session_id": "expansion-session",
        "hook_event_name": "UserPromptExpansion", "expansion_type": "slash_command",
        "command_name": command, "command_source": "plugin",
        "prompt": f"/{command} example", **fields,
    }
    return run_hook(HOOKS_DIR / "rtl-skill-expansion.sh", payload, env=env)


def test_expansion_creates_phase_and_completion_state(tmp_project, expansion_env):
    result = expand(tmp_project, expansion_env)
    assert result["hookSpecificOutput"]["hookEventName"] == "UserPromptExpansion"
    assert "Completion criteria" in result["hookSpecificOutput"]["additionalContext"]
    state = tmp_project / ".rat/state"
    assert json.loads((state / "skill-active.json").read_text())["skill"] == "rtl-p4-rapid-impl"
    assert json.loads((state / "compliance-state.json").read_text())["phase"] == "rtl-p4-rapid-impl"
    assert (state / "p4-state.json").exists()
    assert (state / "spawn-context.json").exists()


@pytest.mark.parametrize("fields", [
    {"command": "another-plugin:rtl-p4-rapid-impl"},
    {"command": "rtl-p4-rapid-impl", "prompt": "/rtl-p4-rapid-impl"},
    {"expansion_type": "mcp_prompt"},
    {"command": "another-plugin:run", "tool_input": {"skill": "rtl-agent-team:rtl-p4-rapid-impl"}},
])
def test_foreign_expansions_leave_no_rat_state(tmp_project, expansion_env, fields):
    before = list((tmp_project / ".rat/state").iterdir())
    assert expand(tmp_project, expansion_env, **fields) == {"continue": True}
    assert list((tmp_project / ".rat/state").iterdir()) == before


def test_qualified_prompt_disambiguates_short_command_name(tmp_project, expansion_env):
    result = expand(tmp_project, expansion_env, command="rtl-p4-rapid-impl",
                    prompt="/rtl-agent-team:rtl-p4-rapid-impl example")
    assert result["hookSpecificOutput"]["hookEventName"] == "UserPromptExpansion"
    assert (tmp_project / ".rat/state/skill-active.json").exists()


def test_p5b_denial_preserves_prior_phase_state(tmp_project, expansion_env):
    state = tmp_project / ".rat/state"
    (state / "compliance-state.json").write_text('{"phase":"previous"}')
    (state / "compliance-report.json").write_text('{"verdict":"PASS"}')
    snapshot = {p.name: p.read_bytes() for p in state.iterdir()}
    result = expand(tmp_project, expansion_env, "rtl-agent-team:rtl-p5b-silicon-validation")
    assert result["decision"] == "block"
    assert "P5A" in result["reason"]
    assert result.get("continue") is not False
    assert {p.name: p.read_bytes() for p in state.iterdir()} == snapshot


@pytest.mark.parametrize("gates", [
    {"lint": {"verdict": "pass"}},
    {"p5a_exit": {}, "regression": {"verdict": "pass"}},
    {"p5a_exit": {"verdict": "pass\nfail"}},
    {"p5a_exit": {"verdict": ["pass"]}},
])
def test_p5b_rejects_pass_outside_the_exact_exit_verdict(tmp_project, expansion_env, gates):
    state = tmp_project / ".rat/state"
    (state / "p5a-state.json").write_text(json.dumps({"gates": gates}, indent=2))
    result = expand(tmp_project, expansion_env, "rtl-agent-team:rtl-p5b-silicon-validation")
    assert result["decision"] == "block"
    assert not (state / "p5b-state.json").exists()
    assert not (state / "skill-active.json").exists()


def test_p5b_requires_a_structured_parser_for_a_valid_exit_verdict(tmp_project, expansion_env):
    state = tmp_project / ".rat/state"
    (state / "p5a-state.json").write_text('{"gates":{"p5a_exit":{"verdict":"pass"}}}')
    result = expand(tmp_project, expansion_env, "rtl-agent-team:rtl-p5b-silicon-validation")
    if expansion_env.get("RTL_FORCE_JSON_FALLBACK"):
        assert result["decision"] == "block"
        assert not (state / "p5b-state.json").exists()
    else:
        assert result["hookSpecificOutput"]["hookEventName"] == "UserPromptExpansion"
        assert (state / "p5b-state.json").exists()


def test_expansion_without_setup_advises_without_completion_loop(tmp_path):
    result = expand(tmp_path, {"HOME": str(tmp_path / "home")})
    assert result["hookSpecificOutput"]["hookEventName"] == "UserPromptExpansion"
    assert "without project initialization" in result["hookSpecificOutput"]["additionalContext"]
    assert not (tmp_path / ".rat").exists()


def test_tool_preflight_preserves_phase_until_the_skill_succeeds(tmp_project, expansion_env):
    state = tmp_project / ".rat/state"
    prior = state / "compliance-report.json"
    prior.write_text('{"verdict":"PASS","phase":"previous"}')
    payload = {"cwd": str(tmp_project), "hook_event_name": "PreToolUse",
               "tool_input": {"skill": "rtl-agent-team:rtl-p4-rapid-impl"}}
    run_hook(HOOKS_DIR / "rtl-phase-state-bootstrap.sh", payload, env=expansion_env)
    assert prior.exists()
    assert not (state / "p4-state.json").exists()
    payload["hook_event_name"] = "PostToolUse"
    result = run_hook(HOOKS_DIR / "rtl-phase-state-bootstrap.sh", payload, env=expansion_env)
    assert not prior.exists()
    assert (state / "p4-state.json").exists()
    assert result["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
