"""Plugin runtime contract tests.

These tests focus on runtime behavior as a Claude Code plugin:
- hook registration order/shape in hooks.json
- plugin manifest coherence with marketplace metadata
- SessionStart injected routing block validity for Action Skill-first routing
"""

import json
import re
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
SKILLS_DIR = REPO_ROOT / "skills"
AGENTS_DIR = REPO_ROOT / "agents"
RTL_ORCHESTRATE_SKILL = SKILLS_DIR / "rtl-orchestrate" / "SKILL.md"
INJECT_HOOK = REPO_ROOT / "hooks" / "rtl-orchestrator-inject.sh"
P5S_FUNC_VERIFY_ORCHESTRATOR = AGENTS_DIR / "p5s-func-verify-orchestrator.md"
P5S_FUNC_VERIFY_POLICY = SKILLS_DIR / "rtl-p5s-func-verify-policy" / "SKILL.md"
CODE_REVIEW_POLICY = SKILLS_DIR / "code-review-policy" / "SKILL.md"
REFACTOR_POLICY = SKILLS_DIR / "refactor-policy" / "SKILL.md"
VERIFICATION_RECHECK_POLICY = SKILLS_DIR / "verification-recheck-policy" / "SKILL.md"
SIM_TOOL_PROFILES = SKILLS_DIR / "sim-tool-profiles" / "SKILL.md"
LINT_TOOL_PROFILES = SKILLS_DIR / "lint-tool-profiles" / "SKILL.md"
CDC_TOOL_PROFILES = SKILLS_DIR / "cdc-tool-profiles" / "SKILL.md"
SYN_TOOL_PROFILES = SKILLS_DIR / "syn-tool-profiles" / "SKILL.md"

SESSIONSTART_BLOCK_START = "# BEGIN GENERATED ROUTING BLOCK - sync via scripts/sync_orchestrator_inject.sh"
SESSIONSTART_BLOCK_END = "# END GENERATED ROUTING BLOCK"


def _extract_block(path: Path, start_marker: str, end_marker: str) -> str:
    lines = path.read_text().splitlines()
    in_block = False
    out = []

    for line in lines:
        if line == start_marker:
            in_block = True
            continue
        if in_block and line == end_marker:
            return "\n".join(out)
        if in_block:
            out.append(line)

    raise AssertionError(f"Markers not found in {path}: {start_marker} ... {end_marker}")


def _skill_user_invocable(skill_name: str) -> bool:
    skill_file = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_file.exists():
        raise AssertionError(f"Missing skill file: {skill_file}")

    content = skill_file.read_text()
    parts = content.split("---", 2)
    if len(parts) < 3:
        raise AssertionError(f"Missing YAML frontmatter: {skill_file}")
    frontmatter = parts[1]

    match = re.search(r"^user-invocable:\s*(true|false)\s*$", frontmatter, re.MULTILINE)
    if not match:
        raise AssertionError(f"Missing user-invocable field in: {skill_file}")
    return match.group(1) == "true"


class TestHookRuntimeContract:
    """Validate runtime hook registration behavior."""

    @pytest.fixture
    def hooks(self):
        return json.loads(HOOKS_JSON.read_text())

    def test_event_keys_present(self, hooks):
        event_keys = set(hooks["hooks"].keys())
        assert event_keys == {"SessionStart", "PostToolUse", "PreToolUse", "Stop"}

    def test_hook_commands_use_plugin_root(self, hooks):
        for event_entries in hooks["hooks"].values():
            for entry in event_entries:
                for hook in entry.get("hooks", []):
                    command = hook.get("command", "")
                    assert command.startswith('sh "${CLAUDE_PLUGIN_ROOT}/hooks/')
                    assert command.endswith('.sh"')
                    script_match = re.search(r"/hooks/([a-z0-9-]+\.sh)", command)
                    assert script_match, f"Unable to parse hook script from command: {command}"
                    script_path = REPO_ROOT / "hooks" / script_match.group(1)
                    assert script_path.exists(), f"Missing hook script: {script_path}"

    def test_session_start_order(self, hooks):
        entries = hooks["hooks"]["SessionStart"]
        assert len(entries) == 1
        assert entries[0]["matcher"] == "*"
        commands = [h["command"] for h in entries[0]["hooks"]]
        assert commands == [
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-project-init-advisor.sh"',
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-orchestrator-inject.sh"',
        ]

    def test_pretooluse_skill_hooks_order(self, hooks):
        entries = hooks["hooks"]["PreToolUse"]
        assert len(entries) == 2
        # Skill matcher: phase-state-bootstrap → skill-activation
        assert entries[0]["matcher"] == "Skill"
        commands = [h["command"] for h in entries[0]["hooks"]]
        assert commands == [
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-phase-state-bootstrap.sh"',
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-skill-activation.sh"',
        ]
        # TaskCreate matcher: spawn-context (experimental)
        assert entries[1]["matcher"] == "TaskCreate"
        tc_commands = [h["command"] for h in entries[1]["hooks"]]
        assert tc_commands == [
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-spawn-context.sh"',
        ]

    def test_stop_order_matches_gate_contract(self, hooks):
        entries = hooks["hooks"]["Stop"]
        assert len(entries) == 1
        assert entries[0]["matcher"] == "*"
        commands = [h["command"] for h in entries[0]["hooks"]]
        assert commands == [
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-verify-stop-gate.sh"',
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-p6-cascade-gate.sh"',
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-skill-completion-gate.sh"',
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/stop-gate.sh"',
        ]

    def test_hook_timeouts_are_bounded(self, hooks):
        for event_entries in hooks["hooks"].values():
            for entry in event_entries:
                for hook in entry.get("hooks", []):
                    timeout = hook.get("timeout")
                    assert isinstance(timeout, int)
                    assert 1 <= timeout <= 10


class TestPluginManifestRuntimeContract:
    """Validate plugin manifest and marketplace consistency."""

    @pytest.fixture
    def plugin_data(self):
        return json.loads(PLUGIN_JSON.read_text())

    @pytest.fixture
    def marketplace_data(self):
        return json.loads(MARKETPLACE_JSON.read_text())

    @pytest.fixture
    def marketplace_plugin(self, marketplace_data):
        for plugin in marketplace_data.get("plugins", []):
            if plugin.get("name") == "rtl-agent-team":
                return plugin
        raise AssertionError("rtl-agent-team entry not found in marketplace.json")

    def test_plugin_version_matches_marketplace(self, plugin_data, marketplace_plugin):
        assert plugin_data["version"] == marketplace_plugin["version"]

    def test_marketplace_metadata_version_matches_plugin(self, plugin_data, marketplace_data):
        assert marketplace_data["metadata"]["version"] == plugin_data["version"]

    def test_marketplace_source_is_repo_root(self, marketplace_plugin):
        assert marketplace_plugin["source"] == "./"

    def test_repository_and_homepage_consistent(self, plugin_data, marketplace_plugin):
        assert plugin_data["repository"] == marketplace_plugin["repository"]
        assert plugin_data["homepage"] == marketplace_plugin["homepage"]

    def test_runtime_paths_exist(self, plugin_data):
        skills_path = (REPO_ROOT / plugin_data["skills"]).resolve()
        lsp_path = (REPO_ROOT / plugin_data["lspServers"]).resolve()
        assert skills_path.is_dir(), f"skills path does not exist: {skills_path}"
        assert lsp_path.exists(), f"lspServers path does not exist: {lsp_path}"


class TestSessionStartRoutingBlockContract:
    """Validate SessionStart injected block against Action Skill-first runtime contract."""

    @pytest.fixture
    def generated_block(self):
        block = _extract_block(INJECT_HOOK, SESSIONSTART_BLOCK_START, SESSIONSTART_BLOCK_END)
        assert block.strip(), "Generated SessionStart block must not be empty"
        return block

    @pytest.fixture
    def routing_section(self, generated_block):
        start_token = "## Routing (key patterns → Action Skill)"
        end_token = "## Expert Review → Agent Delegation"
        assert start_token in generated_block
        assert end_token in generated_block
        return generated_block.split(start_token, 1)[1].split(end_token, 1)[0]

    @pytest.fixture
    def delegation_section(self, generated_block):
        start_token = "## Expert Review → Agent Delegation"
        end_token = "## Core Design Principles"
        assert start_token in generated_block
        assert end_token in generated_block
        return generated_block.split(start_token, 1)[1].split(end_token, 1)[0]

    @pytest.fixture
    def orchestrate_skill_routing_section(self):
        content = RTL_ORCHESTRATE_SKILL.read_text()
        start_token = "## Skill Routing Table"
        end_token = "### Action Skill → Orchestrator Agent Mapping (internal)"
        assert start_token in content
        assert end_token in content
        return content.split(start_token, 1)[1].split(end_token, 1)[0]

    def test_action_skill_first_statement_present(self, routing_section):
        assert "Action Skills first" in routing_section

    def test_no_direct_orchestrator_routes(self, routing_section):
        assert "-orchestrator" not in routing_section

    def test_no_user_invocable_rtl_orchestrate_route(self, generated_block):
        assert "/rtl-agent-team:rtl-orchestrate" not in generated_block

    def test_action_skill_routes_exist_and_are_user_invocable(self, routing_section):
        routed_skills = set(re.findall(r"/rtl-agent-team:([a-z0-9-]+)", routing_section))
        assert routed_skills, "No routed Action Skills found in SessionStart block"

        for skill_name in routed_skills:
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            assert skill_file.exists(), f"Missing routed skill: {skill_name}"
            assert _skill_user_invocable(skill_name), (
                f"Routed Action Skill must be user-invocable: {skill_name}"
            )

    def test_sessionstart_routes_stay_synced_with_orchestrate_skill_table(
        self, routing_section, orchestrate_skill_routing_section
    ):
        exported_routes = set(re.findall(r"/rtl-agent-team:([a-z0-9-]+)", routing_section))
        skill_table_routes = set(re.findall(r"/rtl-agent-team:([a-z0-9-]+)", orchestrate_skill_routing_section))
        # Internal reference route is intentionally not user-invocable.
        assert "rtl-orchestrate" in orchestrate_skill_routing_section
        assert "/rtl-agent-team:rtl-orchestrate" not in routing_section
        assert exported_routes == skill_table_routes, (
            "SessionStart routing block is out of sync with skills/rtl-orchestrate/SKILL.md "
            "Skill Routing Table."
        )

    def test_convention_routes_are_non_user_invocable(self, routing_section):
        conventions = set(re.findall(r"`(systemverilog(?:-assertion)?|uvm|systemc)` \(auto-applied\)", routing_section))
        assert conventions == {"systemverilog", "systemverilog-assertion", "uvm", "systemc"}
        for skill_name in conventions:
            assert not _skill_user_invocable(skill_name), (
                f"Convention skill must be non-user-invocable: {skill_name}"
            )

    def test_delegation_section_references_existing_agents(self, delegation_section):
        delegated_agents = set(re.findall(r"`([a-z0-9-]+)`", delegation_section))
        assert delegated_agents, "No delegated agents found in SessionStart delegation section"

        for agent_name in delegated_agents:
            agent_file = AGENTS_DIR / f"{agent_name}.md"
            assert agent_file.exists(), f"Delegated agent does not exist: {agent_name}"
            # Delegation table must route to agents, not skills.
            assert not (SKILLS_DIR / agent_name).exists(), (
                f"Delegation entry resolves to skill dir, expected agent: {agent_name}"
            )


class TestP5sFuncVerifyRuntimePolicyContract:
    """Lock p5s functional verification runtime policy for plugin behavior."""

    @pytest.fixture
    def orchestrator_content(self):
        return P5S_FUNC_VERIFY_ORCHESTRATOR.read_text()

    @pytest.fixture
    def policy_content(self):
        return P5S_FUNC_VERIFY_POLICY.read_text()

    def test_orchestrator_declares_local_first_runtime(self, orchestrator_content):
        assert "Default execution mode is local (`--mode local`) on the current host." in orchestrator_content
        assert "Default worker budget is `max(1, nproc-2)`." in orchestrator_content
        assert "`aws-batch` is allowed only when the user explicitly asks to use AWS." in orchestrator_content

    def test_policy_declares_local_first_runtime(self, policy_content):
        assert "- **Local-first runtime**: default to local execution on current host (`--mode local`)" in policy_content
        assert "- **Default parallel budget**: use `max(1, nproc-2)` unless user explicitly overrides `--parallel`" in policy_content
        assert "- **AWS usage policy**: `aws-batch` is allowed only when the user explicitly asks to use AWS" in policy_content

    def test_orchestrator_regression_command_uses_local_mode_without_fixed_parallel(
        self, orchestrator_content
    ):
        assert "--mode local --seeds '1 42 123 1337 65536' --sim verilator." in orchestrator_content
        assert "--parallel 4" not in orchestrator_content

    def test_policy_examples_do_not_hardcode_parallel_4(self, policy_content):
        assert "--mode local --seeds \"1 42 123 1337 65536\" --sim verilator" in policy_content
        assert "--parallel 4" not in policy_content


class TestReviewRefactorPolicyRuntimeContract:
    """Lock minimum depth requirements for review/refactor policies."""

    def test_code_review_policy_has_gate_escalation_and_output(self):
        content = CODE_REVIEW_POLICY.read_text()
        assert "Pass/Fail Gate" in content
        assert "Escalation" in content
        assert "Output Format" in content

    def test_refactor_policy_has_gate_escalation_and_output(self):
        content = REFACTOR_POLICY.read_text()
        assert "Pass/Fail Gate" in content
        assert "Escalation" in content
        assert "Output Format" in content

    def test_recheck_policy_has_commands_criteria_and_output(self):
        content = VERIFICATION_RECHECK_POLICY.read_text()
        assert "Recommended Commands" in content
        assert "Pass/Fail Criteria" in content
        assert "Escalation" in content
        assert "Output Format" in content


class TestToolProfileRuntimeContract:
    """Lock minimum actionable content for tool profile skills."""

    def test_sim_tool_profiles_include_open_source_invocation(self):
        content = SIM_TOOL_PROFILES.read_text()
        assert "scripts/run_sim.sh --sim verilator" in content
        assert "Normalized Result Fields" in content

    def test_lint_tool_profiles_include_open_source_invocation(self):
        content = LINT_TOOL_PROFILES.read_text()
        assert "lint/scripts/run_lint.sh --tool verilator" in content
        assert "Gate decision is based on normalized" in content

    def test_cdc_tool_profiles_include_open_source_invocation(self):
        content = CDC_TOOL_PROFILES.read_text()
        assert "sim/cdc/run_cdc.sh --tool structural" in content
        assert "Gate fail when unwaived `VIOLATION` exists." in content

    def test_syn_tool_profiles_include_open_source_invocation(self):
        content = SYN_TOOL_PROFILES.read_text()
        assert "syn/scripts/run_syn.sh --tool yosys" in content
        assert "Gate Criteria" in content


class TestFlockUtilContract:
    """Validate flock-util.sh exists and has required functions."""

    FLOCK_UTIL = REPO_ROOT / "hooks" / "lib" / "flock-util.sh"

    def test_flock_util_exists(self):
        assert self.FLOCK_UTIL.exists(), "hooks/lib/flock-util.sh must exist"

    def test_flock_util_has_acquire_and_release(self):
        content = self.FLOCK_UTIL.read_text()
        assert "acquire_lock()" in content or "acquire_lock()" in content.replace(" ", "")
        assert "release_lock()" in content or "release_lock()" in content.replace(" ", "")

    def test_flock_util_uses_mkdir(self):
        """Lock mechanism must use mkdir for POSIX atomicity."""
        content = self.FLOCK_UTIL.read_text()
        assert "mkdir" in content


class TestTeamConfigTemplate:
    """Validate team-config.json template."""

    TEMPLATE = REPO_ROOT / "skills" / "rtl-design-policy" / "templates" / "team-config.json"

    def test_template_exists(self):
        assert self.TEMPLATE.exists()

    def test_template_valid_json(self):
        import json
        data = json.loads(self.TEMPLATE.read_text())
        assert "team_mode" in data
        assert "team_name" in data
        assert "leader_session_id" in data
        assert "phase" in data
        assert "created_at" in data

    def test_template_defaults(self):
        import json
        data = json.loads(self.TEMPLATE.read_text())
        assert data["team_mode"] is False
        assert data["team_name"] == ""
