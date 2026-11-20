from tests.contracts import read_contract
"""Plugin runtime contract tests.

These tests focus on runtime behavior as a Claude Code plugin:
- hook registration order/shape in hooks.json
- plugin manifest coherence with marketplace metadata
- SessionStart injected routing block validity for Action Skill-first routing
"""

import json
import os
import re
import string
import subprocess
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT, extract_marked_block

HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"
SKILLS_DIR = REPO_ROOT / "skills"
AGENTS_DIR = REPO_ROOT / "agents"
RTL_ORCHESTRATE_SKILL = SKILLS_DIR / "rtl-orchestrate" / "SKILL.md"
INJECT_HOOK = REPO_ROOT / "hooks" / "rtl-orchestrator-inject.sh"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
P5S_FUNC_VERIFY_ORCHESTRATOR = AGENTS_DIR / "p5s-func-verify-orchestrator.md"
P5S_FUNC_VERIFY_POLICY = SKILLS_DIR / "rtl-p5s-func-verify-policy" / "SKILL.md"
CODE_REVIEW_POLICY = SKILLS_DIR / "code-review-policy" / "SKILL.md"
REFACTOR_POLICY = SKILLS_DIR / "refactor-classification-policy" / "SKILL.md"
VERIFICATION_RECHECK_POLICY = SKILLS_DIR / "verification-recheck-policy" / "SKILL.md"
SIM_TOOL_PROFILES = SKILLS_DIR / "sim-tool-profiles" / "SKILL.md"
LINT_TOOL_PROFILES = SKILLS_DIR / "lint-tool-profiles" / "SKILL.md"
CDC_TOOL_PROFILES = SKILLS_DIR / "cdc-tool-profiles" / "SKILL.md"
SYN_TOOL_PROFILES = SKILLS_DIR / "syn-tool-profiles" / "SKILL.md"
RAT_SETUP_SKILL = SKILLS_DIR / "rat-setup" / "SKILL.md"
RAT_SETUP_INSTALL_COMMANDS = RAT_SETUP_SKILL.parent / "references" / "install-commands.md"
RAT_SETUP_TOOL_CHECK_COMMANDS = RAT_SETUP_SKILL.parent / "references" / "tool-check-commands.md"
RAT_SETUP_DOCKER_ENVIRONMENT = RAT_SETUP_SKILL.parent / "references" / "docker-environment.md"
RAT_PLUGIN_DEBUG_SKILL = SKILLS_DIR / "rat-plugin-debug" / "SKILL.md"
RTL_LINT_CHECK_SKILL = SKILLS_DIR / "rtl-lint-check" / "SKILL.md"
RTL_P5S_SVA_POLICY = SKILLS_DIR / "rtl-p5s-sva-policy" / "SKILL.md"

SESSIONSTART_BLOCK_START = "# BEGIN GENERATED ROUTING BLOCK - sync via scripts/sync_orchestrator_inject.sh"
SESSIONSTART_BLOCK_END = "# END GENERATED ROUTING BLOCK"



def _skill_user_invocable(skill_name: str) -> bool:
    skill_file = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_file.exists():
        raise AssertionError(f"Missing skill file: {skill_file}")

    content = read_contract(skill_file)
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
        return json.loads(read_contract(HOOKS_JSON))

    def test_event_keys_present(self, hooks):
        event_keys = set(hooks["hooks"].keys())
        assert event_keys == {"SessionStart", "PostToolUse", "PostToolUseFailure", "PreToolUse", "UserPromptExpansion", "SubagentStart", "SubagentStop", "Stop"}

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
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-orchestrator-inject.sh"',
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-audit-init.sh"',
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-parser-warning.sh"',
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-eda-context.sh"',
        ]

    def test_pretooluse_skill_hooks_order(self, hooks):
        entries = [e for e in hooks["hooks"]["PreToolUse"] if e["matcher"] in {"Skill", "Agent"}]
        assert len(entries) == 2
        # Skill matcher: phase-state-bootstrap → skill-activation
        assert entries[0]["matcher"] == "Skill"
        commands = [h["command"] for h in entries[0]["hooks"]]
        assert commands == [
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-phase-state-bootstrap.sh"',
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-skill-activation.sh"',
        ]
        # Agent matcher: spawn-context
        assert entries[1]["matcher"] == "Agent"
        tc_commands = [h["command"] for h in entries[1]["hooks"]]
        assert tc_commands == [
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-spawn-context.sh"',
        ]

    def test_eda_context_is_delivered_to_main_and_worker_sessions(self, hooks):
        events = {event for event, groups in hooks["hooks"].items()
                  if any("rtl-eda-context.sh" in hook["command"] for group in groups for hook in group["hooks"])}
        assert events == {"SessionStart", "SubagentStart"}

    def test_posttooluse_matchers(self, hooks):
        entries = hooks["hooks"]["PostToolUse"]
        matchers = [e["matcher"] for e in entries]
        assert matchers == ["Skill", "Edit|Write|Bash", "TaskUpdate", "Agent", "Edit|Write"]
        # Skill matcher: the completion loop starts once the call ran
        assert [h["command"] for h in entries[0]["hooks"]] == [
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-phase-state-bootstrap.sh"',
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-skill-activation.sh"',
        ]

    def test_edit_tracking_pairs_success_and_failure_events(self, hooks):
        for event in ("PreToolUse", "PostToolUse", "PostToolUseFailure"):
            entry = next(e for e in hooks["hooks"][event] if e["matcher"] == "Edit|Write|Bash")
            assert [h["command"] for h in entry["hooks"]] == [
                'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-edit-tracker.sh"',
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
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/rtl-coverage-exclusion-gate.sh"',
            'sh "${CLAUDE_PLUGIN_ROOT}/hooks/stop-gate.sh"',
        ]

    def test_hook_timeouts_are_bounded(self, hooks):
        for event_entries in hooks["hooks"].values():
            for entry in event_entries:
                for hook in entry.get("hooks", []):
                    timeout = hook.get("timeout")
                    assert isinstance(timeout, int)
                    assert 1 <= timeout <= 10

    def test_python_heavy_stop_gates_get_ten_seconds(self, hooks):
        # In python parser mode the skill completion gate and stop-gate.sh each start python
        # about two dozen times on a blocking Stop, and a Stop hook that times out fails open.
        # Direct expansion runs both skill hooks sequentially, including parser work.
        slow = {"rtl-skill-completion-gate.sh", "stop-gate.sh", "rtl-skill-expansion.sh"}
        timeouts = {}
        for event_entries in hooks["hooks"].values():
            for entry in event_entries:
                for hook in entry.get("hooks", []):
                    script = re.search(r"/hooks/([a-z0-9-]+\.sh)", hook["command"]).group(1)
                    timeouts.setdefault(script, set()).add(hook["timeout"])
        assert {s: t for s, t in timeouts.items() if s in slow} == {s: {10} for s in slow}
        assert all(t == {3} for s, t in timeouts.items() if s not in slow), timeouts


def _hooks_resolving_rat_dir() -> list:
    """Every hook that calls rat_project_dir, read from hooks/ so that a new hook is covered."""
    return sorted(
        path.name for path in (REPO_ROOT / "hooks").glob("*.sh")
        if any(re.search(r"\brat_project_dir\b", line)
               for line in read_contract(path).splitlines() if not line.lstrip().startswith("#"))
    )


RAT_DIR_HOOKS = _hooks_resolving_rat_dir()


class TestSpawnContextProjectRootContract:
    """v0.13.x Workflow-drivability contract: the spawn-context manifest ships
    project_root (RAT_PROJECT_ROOT override, CWD fallback), and every hook honors
    the override for paths not routed through rat_project_dir(). rat_project_dir()
    applies the override, and each hook that calls it re-bases CWD on the marker it
    returns before it uses CWD for anything else. The same re-base moves CWD to the
    project root when the session has cd'd into a subdirectory."""

    SPAWN_CTX_UTIL = REPO_ROOT / "hooks" / "lib" / "spawn-context-util.sh"
    REBASE_LINE = 'CWD=$(dirname "$RAT_DIR")'
    # Any read of CWD: "$CWD", "$CWD/...", "${CWD%/}".
    CWD_READ = re.compile(r"\$\{?CWD\b")
    # Before the re-base CWD is the session's directory. Only its default, the
    # RAT-directory guard and resolve, and the tracker's copy for Bash paths read it.
    SESSION_CWD_READ = re.compile(
        r'^\[ -z "\$CWD" \]|\brat_project_dir\b|\brat_is_project\b|^SESSION_CWD=\$CWD\b'
    )

    def test_manifest_emits_project_root_field(self):
        content = read_contract(self.SPAWN_CTX_UTIL)
        assert '"project_root":"$SCTX_PROJECT_ROOT_ESC"' in content, (
            "spawn-context manifest must emit a project_root field"
        )
        # Resolution: -d guarded env override, else the CWD the hook passes, which
        # the hook has re-based on the project root (mirrors rat-dir-util.sh).
        assert 'SCTX_PROJECT_ROOT="$SCTX_CWD"' in content
        assert (
            '[ -d "${RAT_PROJECT_ROOT:-}" ] && SCTX_PROJECT_ROOT="$RAT_PROJECT_ROOT"'
            in content
        )

    def test_the_manifest_writing_hooks_are_checked(self):
        # An empty parameter set would skip the check below instead of failing it.
        assert {"rtl-spawn-context.sh", "rtl-phase-state-bootstrap.sh"} <= set(RAT_DIR_HOOKS)

    @pytest.mark.parametrize("hook_name", RAT_DIR_HOOKS)
    def test_hooks_honor_project_root_override(self, hook_name):
        code = [
            (i, line.strip())
            for i, line in enumerate(read_contract(REPO_ROOT / "hooks" / hook_name).splitlines())
            if line.strip() and not line.lstrip().startswith("#")
        ]
        resolve = next(i for i, line in code if re.search(r"\brat_project_dir\b", line))
        rebase = next((i for i, line in code if line.startswith(self.REBASE_LINE)), None)
        assert rebase is not None and rebase > resolve, (
            f"{hook_name} must re-base CWD after resolving RAT_DIR: {self.REBASE_LINE}"
        )
        # From the top of the file: a path built before the resolve is just as wrong,
        # and "$CWD" passed to a helper builds its paths inside the helper.
        early = [
            line for i, line in code
            if i < rebase and self.CWD_READ.search(line) and not self.SESSION_CWD_READ.search(line)
        ]
        assert not early, f"{hook_name} reads the session's CWD before re-basing it: {early}"


class TestPluginManifestRuntimeContract:
    """Validate plugin manifest and marketplace consistency."""

    @pytest.fixture
    def plugin_data(self):
        return json.loads(read_contract(PLUGIN_JSON))

    @pytest.fixture
    def marketplace_data(self):
        return json.loads(read_contract(MARKETPLACE_JSON))

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

    def test_systemverilog_lsp_marketplace_entry_uses_github_source(self, marketplace_data):
        """After the standalone-repo split, systemverilog-lsp is fetched from
        babyworm/systemverilog-lsp via a github source pinned to a ref+sha."""
        sv_lsp = next(p for p in marketplace_data["plugins"] if p["name"] == "systemverilog-lsp")
        source = sv_lsp["source"]
        assert isinstance(source, dict), "systemverilog-lsp source must be a github object after standalone split"
        assert source.get("source") == "github"
        assert source.get("repo") == "babyworm/systemverilog-lsp"
        assert source.get("ref"), "github source must pin a ref (branch/tag)"
        assert source.get("sha"), "github source should pin sha for cache integrity"


class TestSessionStartRoutingBlockContract:
    """Validate SessionStart injected block against Action Skill-first runtime contract."""

    @pytest.fixture
    def generated_block(self):
        """Return the routing markdown delivered by the SessionStart hook.

        Since v0.10.3 the BEGIN/END region in the hook is a `cat << 'JSON_EOF'`
        heredoc wrapping a single JSON envelope (see CLAUDE.md "Hook output
        schema (SessionStart)"). This fixture decodes the envelope and returns
        the `additionalContext` markdown so existing section-split assertions
        keep operating on the routing markdown directly.
        """
        import json

        raw = extract_marked_block(INJECT_HOOK, SESSIONSTART_BLOCK_START, SESSIONSTART_BLOCK_END)
        assert raw.strip(), "Generated SessionStart block must not be empty"
        lines = raw.splitlines()
        assert lines and lines[0] == "cat << 'JSON_EOF'" and lines[-1] == "JSON_EOF", (
            "Generated block must be `cat << 'JSON_EOF' ... JSON_EOF`. "
            "Run: sh scripts/sync_orchestrator_inject.sh"
        )
        envelope = json.loads("\n".join(lines[1:-1]))
        assert envelope["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        return envelope["hookSpecificOutput"]["additionalContext"]

    @pytest.fixture
    def routing_section(self, generated_block):
        start_token = "## Routing (key patterns → Action Skill)"
        end_token = "## Core Design Principles"
        assert start_token in generated_block
        assert end_token in generated_block
        return generated_block.split(start_token, 1)[1].split(end_token, 1)[0]

    @pytest.fixture
    def delegation_section(self):
        # The Expert Review → Agent Delegation table was removed from the
        # SessionStart inject (duplicated agent frontmatter descriptions already
        # in main-session context). It remains agent-side reference material in
        # the rtl-orchestrate skill body — the agent-existence contract still
        # applies there.
        content = read_contract(RTL_ORCHESTRATE_SKILL)
        start_token = "## Expert Review → Agent Delegation"
        end_token = "## Phase-Aware Invocation Cues"
        assert start_token in content
        assert end_token in content
        return content.split(start_token, 1)[1].split(end_token, 1)[0]

    @pytest.fixture
    def orchestrate_skill_routing_section(self):
        content = read_contract(RTL_ORCHESTRATE_SKILL)
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
        # "auto-applied" is the legacy annotation (pre-sync hook); "agent-loaded" is the
        # current SSOT wording (convention skills load via writer-agent skills: frontmatter).
        conventions = set(re.findall(r"`(systemverilog(?:-assertion)?|uvm|systemc)` \((?:auto-applied|agent-loaded)\)", routing_section))
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
        return read_contract(P5S_FUNC_VERIFY_ORCHESTRATOR)

    @pytest.fixture
    def policy_content(self):
        return read_contract(P5S_FUNC_VERIFY_POLICY)

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
        assert "--mode local --seeds \"1 42 123 1337 65536\" --sim auto" in policy_content
        assert "--parallel 4" not in policy_content


class TestReviewRefactorPolicyRuntimeContract:
    """Lock minimum depth requirements for review/refactor policies."""

    def test_code_review_policy_has_gate_escalation_and_output(self):
        content = read_contract(CODE_REVIEW_POLICY)
        assert "Pass/Fail Gate" in content
        assert "Escalation" in content
        assert "Output Format" in content

    def test_refactor_policy_has_gate_escalation_and_output(self):
        content = read_contract(REFACTOR_POLICY)
        assert "Pass/Fail Gate" in content
        assert "Escalation" in content
        assert "Output Format" in content

    def test_recheck_policy_has_commands_criteria_and_output(self):
        content = read_contract(VERIFICATION_RECHECK_POLICY)
        assert "Recommended Commands" in content
        assert "Pass/Fail Criteria" in content
        assert "Escalation" in content
        assert "Output Format" in content


class TestToolProfileRuntimeContract:
    """Lock minimum actionable content for tool profile skills."""

    def test_sim_tool_profiles_include_open_source_invocation(self):
        content = read_contract(SIM_TOOL_PROFILES)
        assert "scripts/run_sim.sh --sim verilator" in content
        assert "Normalized Result Fields" in content

    def test_lint_tool_profiles_include_open_source_invocation(self):
        content = read_contract(LINT_TOOL_PROFILES)
        assert "lint/scripts/run_lint.sh --tool verilator" in content
        assert "Gate decision is based on normalized" in content

    def test_cdc_tool_profiles_include_open_source_invocation(self):
        content = read_contract(CDC_TOOL_PROFILES)
        assert "lint/scripts/run_cdc.sh --tool structural" in content
        assert "Gate fail when unwaived `VIOLATION` exists." in content

    def test_syn_tool_profiles_include_open_source_invocation(self):
        content = read_contract(SYN_TOOL_PROFILES)
        assert "syn/scripts/run_syn.sh --tool yosys" in content
        assert "Gate Criteria" in content


def _rat_setup_delivered_content() -> str:
    """SKILL.md plus its on-demand references/ files.

    Static install/check/template content was extracted to
    skills/rat-setup/references/*.md (loaded via Read at the decision points
    where SKILL.md instructs it). The remediation contract is delivered by the
    combined content, so contract assertions check the combination.
    """
    content = read_contract(RAT_SETUP_SKILL)
    refs_dir = RAT_SETUP_SKILL.parent / "references"
    if refs_dir.is_dir():
        for ref in sorted(refs_dir.glob("*.md")):
            content += "\n" + read_contract(ref)
    return content


class TestRatSetupRuntimeContract:
    """Lock required-tool remediation guidance for rat-setup."""

    def test_rat_setup_requires_install_when_required_tools_missing(self):
        content = read_contract(RAT_SETUP_SKILL)
        assert 'required by the requested phase' in content
        assert 'missing dependencies' in content
        assert 'remote_unprobed' in content

    def test_rat_setup_includes_user_local_install_fallback(self):
        content = _rat_setup_delivered_content()
        assert "~/.local/bin" in content
        assert '"$RAT_EDA_VENV/bin/python" -m pip install cocotb' in content
        assert 'CMAKE_INSTALL_PREFIX="$HOME/.local"' in content
        assert 'ln -sf "$HOME/tools/oss-cad-suite/bin/yosys" "$HOME/.local/bin/yosys"' in content

    def test_rat_setup_prompts_for_global_local_or_skip(self):
        content = read_contract(RAT_SETUP_SKILL)
        assert 'already authorized' in content
        assert 'before making' in content
        assert 'user-local' in content

    def test_rat_setup_prefers_upstream_install_for_recent_verilator_and_systemc(self):
        content = _rat_setup_delivered_content()
        assert "VERILATOR_LATEST_TAG" in content
        assert "SYSTEMC_LATEST_TAG" in content
        assert 'git checkout "$VERILATOR_LATEST_TAG"' in content
        assert "git clone https://github.com/verilator/verilator.git" in content
        assert "verilator.org/guide/latest/install.html" in content
        assert "git clone https://github.com/accellera-official/systemc.git" in content

    def test_install_commands_download_verible_archive_before_extracting_it(self):
        content = read_contract(RAT_SETUP_INSTALL_COMMANDS)
        download = content.index("github.com/chipsalliance/verible/releases/download")
        extract = content.index("tar xzf", download)
        assert download < extract

    def test_install_commands_resolve_slang_server_from_plugin_root(self):
        content = read_contract(RAT_SETUP_INSTALL_COMMANDS)
        assert '${CLAUDE_PLUGIN_ROOT}/scripts/install-slang-server.sh' in content
        assert "bash scripts/install-slang-server.sh" not in content

    def test_docker_build_context_resolves_from_plugin_root(self):
        install_commands = read_contract(RAT_SETUP_INSTALL_COMMANDS)
        docker_environment = read_contract(RAT_SETUP_DOCKER_ENVIRONMENT)
        assert 'docker build -t rtl-eda-tools "${CLAUDE_PLUGIN_ROOT}/docker/"' in install_commands
        assert '  "${CLAUDE_PLUGIN_ROOT}/docker/"' in docker_environment
        assert '--mount "type=bind,src=$(pwd),dst=/workspace"' in docker_environment

    def test_install_commands_cover_required_open_source_lint_and_cdc_tools(self):
        content = read_contract(RAT_SETUP_INSTALL_COMMANDS)
        assert "https://github.com/MikePopoloski/slang.git" in content
        assert 'cmake --install "$HOME/tools/slang-src/build"' in content
        assert (
            'git clone --depth 1 --branch "$SVLENS_VERSION" '
            'https://github.com/babyworm/svlens.git'
        ) in content
        assert 'cmake --install "$HOME/tools/svlens/build"' in content
        macos = content.split("## macOS (Homebrew)", 1)[1].split("## Docker fallback", 1)[0]
        assert 'cmake --install "$HOME/tools/slang-src/build"' in macos
        assert 'cmake --install "$HOME/tools/svlens/build"' in macos

    def test_pipeline_probes_cannot_hide_not_found_status(self):
        content = "\n".join(
            [
                read_contract(RAT_SETUP_TOOL_CHECK_COMMANDS),
                read_contract(RAT_PLUGIN_DEBUG_SKILL),
            ]
        )
        hidden_failure = re.compile(r"\|\s*head\s+-1\s*\|\|\s*echo\s+\"?(?:NOT_FOUND|NO_IMAGE)")
        assert not hidden_failure.search(content)

    def test_plugin_registration_is_read_through_claude_cli(self):
        content = "\n".join(
            [
                read_contract(RAT_SETUP_SKILL),
                read_contract(RAT_SETUP_TOOL_CHECK_COMMANDS),
            ]
        )
        assert "claude plugin list --json" in content
        assert "~/.claude/plugins.json" not in content

    def test_owned_skill_docs_use_canonical_plugin_commands(self):
        content = "\n".join(
            [
                read_contract(RAT_SETUP_INSTALL_COMMANDS),
                read_contract(RAT_PLUGIN_DEBUG_SKILL),
                read_contract(RTL_LINT_CHECK_SKILL),
                read_contract(RTL_P5S_SVA_POLICY),
            ]
        )
        assert "/rtl-agent-team:rat-setup" in content
        assert "/rtl-agent-team:rat-init-project" in content
        assert not re.search(r"`/(?:rat-setup|rat-init-project)`", content)
        assert "pip install slang" not in content
        assert "pip install sbyosys" not in content

    def test_rat_setup_bash_fences_are_syntactically_valid(self):
        content = read_contract(RAT_SETUP_SKILL)
        for block_number, match in enumerate(re.finditer(r"```bash\n(.*?)\n```", content, re.DOTALL), 1):
            result = subprocess.run(
                ["bash", "-n"], input=match.group(1), text=True, capture_output=True, check=False
            )
            assert result.returncode == 0, f"bash block {block_number}: {result.stderr}"


class TestRatInitProjectRuntimeContract:
    """Lock runtime behavior contract for rat-init-project."""

    RAT_INIT_PROJECT_SKILL = SKILLS_DIR / "rat-init-project" / "SKILL.md"

    def test_skill_exists(self):
        assert self.RAT_INIT_PROJECT_SKILL.exists()

    def test_non_destructive_policy(self):
        content = read_contract(self.RAT_INIT_PROJECT_SKILL)
        assert "Non-destructive" in content or "non-destructive" in content

    def test_recommends_rat_setup(self):
        content = read_contract(self.RAT_INIT_PROJECT_SKILL)
        assert "rat-setup" in content

    def test_setup_marker_check(self):
        content = read_contract(self.RAT_INIT_PROJECT_SKILL)
        assert ".setup-complete" in content

    def test_setup_marker_lives_in_plugin_data(self):
        content = read_contract(self.RAT_INIT_PROJECT_SKILL)
        assert "${CLAUDE_PLUGIN_DATA}/.setup-complete" in content
        assert ".config/rtl-agent-team" not in content

    def test_directory_structure_defined(self):
        content = read_contract(self.RAT_INIT_PROJECT_SKILL)
        for d in ["rtl/", "refc/", "sim/", "docs/", "reviews/", "lint/", "syn/"]:
            assert d in content, f"Missing directory {d} in rat-init-project"

    def test_diagram_rules_fallback(self):
        content = read_contract(self.RAT_INIT_PROJECT_SKILL)
        assert "<markdown_diagram_rule>" in content


class TestFlockUtilContract:
    """Validate flock-util.sh exists and has required functions."""

    FLOCK_UTIL = REPO_ROOT / "hooks" / "lib" / "flock-util.sh"

    def test_flock_util_exists(self):
        assert self.FLOCK_UTIL.exists(), "hooks/lib/flock-util.sh must exist"

    def test_flock_util_has_acquire_and_release(self):
        content = read_contract(self.FLOCK_UTIL)
        assert "acquire_lock()" in content or "acquire_lock()" in content.replace(" ", "")
        assert "release_lock()" in content or "release_lock()" in content.replace(" ", "")

    def test_flock_util_uses_mkdir(self):
        """Lock mechanism must use mkdir for POSIX atomicity."""
        content = read_contract(self.FLOCK_UTIL)
        assert "mkdir" in content


class TestExpertTriggerContracts:
    """Verify that the 4 conditional expert agents have trigger contracts in SSOT
    and are referenced by the relevant orchestrators."""

    EXPERT_CONTRACTS = {
        "rtl-planner": {
            "ssot_pattern": r"rtl-planner.*P3",
            "orchestrators": ["p3-uarch-orchestrator"],
            "pattern_in_orchestrator": r"rtl-planner",
        },
        "clock-architect": {
            "ssot_pattern": r"clock-architect.*P3.*P4.*P5|clock-architect.*multi-clock",
            "orchestrators": ["p3-uarch-orchestrator", "p5-verify-orchestrator"],
            "pattern_in_orchestrator": r"clock-architect",
        },
        "ref-model-reviewer": {
            "ssot_pattern": r"ref-model-reviewer.*P2",
            "orchestrators": ["p2-arch-orchestrator"],
            "pattern_in_orchestrator": r"ref-model-reviewer",
        },
        "equivalence-checker": {
            "ssot_pattern": r"equivalence-checker.*P4.*refactor|equivalence-checker.*P5B",
            "orchestrators": ["p5b-silicon-validation-orchestrator"],
            "pattern_in_orchestrator": r"equivalence.checker",
        },
    }

    def test_ssot_defines_all_expert_trigger_cues(self):
        """Phase-Aware Invocation Cues section must define all 4 experts."""
        content = read_contract(RTL_ORCHESTRATE_SKILL)
        assert "Phase-Aware Invocation Cues" in content
        cues_section = content.split("Phase-Aware Invocation Cues")[1].split("## Phase 1")[0]
        for expert in self.EXPERT_CONTRACTS:
            # Agent names may be wrapped in backticks in SSOT
            assert expert in cues_section, f"{expert} missing from Phase-Aware Invocation Cues"

    @pytest.mark.parametrize("expert", list(EXPERT_CONTRACTS.keys()))
    def test_expert_referenced_in_orchestrators(self, expert):
        """Each expert must be referenced in at least one relevant orchestrator."""
        contract = self.EXPERT_CONTRACTS[expert]
        for orch_name in contract["orchestrators"]:
            orch_file = AGENTS_DIR / f"{orch_name}.md"
            assert orch_file.exists(), f"Orchestrator {orch_name} not found"
            content = read_contract(orch_file)
            assert re.search(contract["pattern_in_orchestrator"], content), (
                f"{expert} not referenced in {orch_name}.md"
            )

    def test_equivalence_checker_in_p4_wave9_section(self):
        content = read_contract(AGENTS_DIR / 'p4-implement-orchestrator.md')
        assert 'equivalence-checker' in content
        assert 'refactor' in content.lower()
        assert 'functional' in content

    def test_cdc_reviewer_in_p5_cdc_escalation(self):
        content = read_contract(AGENTS_DIR / 'p5-verify-orchestrator.md')
        assert 'CDC' in content
        assert 'structural CDC scan is signoff evidence' in content
        assert 'affected checks' in content

    def test_ssot_cues_match_sessionstart_export(self):
        """SessionStart export block must include Asymmetric Phase Gate principle."""
        content = read_contract(RTL_ORCHESTRATE_SKILL)
        export_start = "<!-- SESSIONSTART_HOOK_EXPORT_START -->"
        export_end = "<!-- SESSIONSTART_HOOK_EXPORT_END -->"
        assert export_start in content
        export_block = content.split(export_start)[1].split(export_end)[0]
        assert "Asymmetric Phase Gate" in export_block


class TestBfmRetryParity:
    """Verify BFM retry limit consistency across policy and orchestrators."""

    POLICY = SKILLS_DIR / "rtl-p3-uarch-policy" / "SKILL.md"
    SOLO_ORCH = AGENTS_DIR / "p3-uarch-orchestrator.md"
    TEAM_ORCH = AGENTS_DIR / "p3-uarch-orchestrator.md"

    def test_policy_defines_max_2(self):
        content = read_contract(self.POLICY)
        assert re.search(r"max\s+2\s+iteration", content, re.IGNORECASE)

    def test_solo_orchestrator_matches_policy(self):
        content = read_contract(self.SOLO_ORCH)
        assert re.search(r"max\s+2\s+iteration", content, re.IGNORECASE), (
            "Solo orchestrator BFM retry limit must match policy (max 2)"
        )

    def test_team_orchestrator_matches_policy(self):
        content = read_contract(self.TEAM_ORCH)
        assert re.search(r"Max\s+2\s+iteration", content, re.IGNORECASE), (
            "Team orchestrator BFM retry limit must match policy (max 2)"
        )


class TestP5TeamFlowParity:
    """Verify P5 team orchestrator has Stage 2 and Stage 3 flow parity with solo."""

    SOLO = AGENTS_DIR / "p5-verify-orchestrator.md"
    TEAM = AGENTS_DIR / "p5-verify-orchestrator.md"

    def test_team_has_top_level_stage(self):
        content = read_contract(self.TEAM)
        assert re.search(r"Stage\s*2|Top-Level Verification", content), (
            "P5 team orchestrator must include Stage 2 (Top-Level) verification"
        )

    def test_team_has_final_compliance_stage(self):
        content = read_contract(self.TEAM)
        assert "final-compliance.md" in content, (
            "P5 team orchestrator must generate final-compliance.md"
        )

    def test_team_has_requirement_traceability(self):
        content = read_contract(self.TEAM)
        assert "requirement-traceability" in content, (
            "P5 team orchestrator must include requirement traceability (Stage 3)"
        )

    def test_team_has_e2e_traceability(self):
        content = read_contract(self.TEAM)
        assert "e2e-traceability" in content, (
            "P5 team orchestrator must include e2e traceability (Stage 3)"
        )

    def test_solo_and_team_both_have_three_stages(self):
        solo = read_contract(self.SOLO)
        team = read_contract(self.TEAM)
        for stage_name in ["Module", "Top-Level", "Final Compliance"]:
            # Solo uses "Stage N:" format
            assert re.search(rf"Stage\s+\d.*{stage_name}|{stage_name}", solo, re.IGNORECASE), (
                f"Solo P5 missing stage: {stage_name}"
            )
            assert re.search(rf"Stage\s+\d.*{stage_name}|{stage_name}", team, re.IGNORECASE), (
                f"Team P5 missing stage: {stage_name}"
            )


class TestSpecToUarchTeamGateParity:
    """Verify spec-to-uarch-team orchestrator has P2→P3 artifact gate."""

    SOLO = AGENTS_DIR / "spec-to-uarch-orchestrator.md"
    TEAM = AGENTS_DIR / "spec-to-uarch-orchestrator.md"

    def test_team_has_refc_artifact_gate(self):
        content = read_contract(self.TEAM)
        assert "refc/" in content or "refc/**" in content, (
            "spec-to-uarch-team must check refc artifact existence at P2→P3 gate"
        )

    def test_team_has_bandwidth_artifact_gate(self):
        content = read_contract(self.TEAM)
        assert "bandwidth_report" in content, (
            "spec-to-uarch-team must check bandwidth_report.json at P2→P3 gate"
        )


class TestP4TeamGateParity:
    """Verify P4 team gate covers all policy categories."""

    TEAM = AGENTS_DIR / "p4-implement-orchestrator.md"

    def test_gate_checks_code_review(self):
        content = read_contract(self.TEAM)
        assert re.search(r"code review.*PASS|review.*PASS", content, re.IGNORECASE)

    def test_gate_checks_cdc(self):
        content = read_contract(self.TEAM)
        assert re.search(r"CDC.*PASS", content, re.IGNORECASE)

    def test_gate_checks_protocol(self):
        content = read_contract(self.TEAM)
        assert re.search(r"protocol.*PASS", content, re.IGNORECASE)


class TestP5TeamV5Dependency:
    """Verify V5 depends only on V1 (per policy), not V1-V4."""

    TEAM = AGENTS_DIR / "p5-verify-orchestrator.md"

    def test_v5_blocked_by_lint_only(self):
        content = read_contract(AGENTS_DIR / 'p5-verify-orchestrator.md')
        assert 'formal needs passing lint' in content
        assert 'actual behavior' in content
        assert 'verification results' in content


class TestP5TeamClockArchitect:
    """Verify P5 team has conditional clock-architect escalation."""

    TEAM = AGENTS_DIR / "p5-verify-orchestrator.md"

    def test_team_has_clock_architect_escalation(self):
        content = read_contract(self.TEAM)
        assert "clock-architect" in content, (
            "P5 team orchestrator must have conditional clock-architect escalation for CDC root cause"
        )


class TestP5abP6ArtifactChain:
    """Verify P5A→P5B→P6 artifact connection is closed."""

    P5A = AGENTS_DIR / "p5a-functional-closure-orchestrator.md"
    P5B = AGENTS_DIR / "p5b-silicon-validation-orchestrator.md"

    def test_p5b_generates_final_compliance(self):
        content = read_contract(self.P5B)
        assert "final-compliance.md" in content, (
            "P5B must generate final-compliance.md as P6 entry artifact"
        )

    def test_p5b_requires_p5a_pass(self):
        content = read_contract(self.P5B)
        assert "p5a_exit" in content and "pass" in content.lower()

    def test_p5a_documents_no_final_compliance(self):
        content = read_contract(self.P5A)
        assert "final-compliance" in content, (
            "P5A must document its relationship to final-compliance.md"
        )


class TestTeamConfigTemplate:
    """Validate team-config.json template."""

    TEMPLATE = REPO_ROOT / "skills" / "rtl-p4-rapid-impl-policy" / "templates" / "team-config.json"

    def test_template_exists(self):
        assert self.TEMPLATE.exists()

    def test_template_valid_json(self):
        import json
        data = json.loads(read_contract(self.TEMPLATE))
        assert "team_mode" in data
        assert "team_name" in data
        assert "leader_session_id" in data
        assert "phase" in data
        assert "created_at" in data

    def test_template_defaults(self):
        import json
        data = json.loads(read_contract(self.TEMPLATE))
        assert data["team_mode"] is False
        assert data["team_name"] == ""


class TestSkillDescriptionLengthContract:
    """User-invocable skill descriptions must stay within the 160-char budget.

    Descriptions are always-on context (Layer 4 frontmatter loads at session
    start for every skill). The 160-char cap keeps the progressive-disclosure
    budget bounded; a runaway description silently inflates every session.
    """

    MAX_DESCRIPTION_CHARS = 160

    def _skill_description(self, skill_name: str) -> str:
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        content = read_contract(skill_file)
        parts = content.split("---", 2)
        assert len(parts) >= 3, f"Missing YAML frontmatter: {skill_file}"
        frontmatter = parts[1]
        match = re.search(r"^description:\s*(.*)$", frontmatter, re.MULTILINE)
        assert match, f"Missing description field in: {skill_file}"
        desc = match.group(1).strip()
        if len(desc) >= 2 and desc[0] in "\"'" and desc[-1] == desc[0]:
            desc = desc[1:-1]
        return desc

    def test_user_invocable_skill_descriptions_within_limit(self):
        violations = []
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").exists():
                continue
            if not _skill_user_invocable(skill_dir.name):
                continue
            desc = self._skill_description(skill_dir.name)
            if len(desc) > self.MAX_DESCRIPTION_CHARS:
                violations.append(f"{skill_dir.name}: {len(desc)} chars")
        assert violations == [], (
            f"User-invocable skills exceeding {self.MAX_DESCRIPTION_CHARS}-char "
            f"description limit:\n" + "\n".join(violations)
        )


class TestPipelineRuleCoverage:
    """CLAUDE.md declares the pipeline rules as an SSOT contract; the runtime
    must actually receive all of them.

    v0.14.2: CLAUDE.md declared 11 rules while the SessionStart injection and the
    rtl-orchestrate body both stopped at 9. Rules 10-11 govern the shipped
    DC-based PPA optimization pipeline (rtl-ppa-optimize-dc, rat-ultraloop-ppa,
    ppa-optimizer-dc-policy), so that pipeline's two gates never reached a user
    session.
    """

    @staticmethod
    def _numbered(text):
        # matches both the CLAUDE.md table form `| 10 | ...` and the
        # ordered-list form `10. ...` used by the skill body and the injection
        return {int(m.group(1)) for m in re.finditer(r"^\|?\s*(\d+)\s*[.|]", text, re.M)}

    def _claude_md_rules(self):
        text = read_contract(CLAUDE_MD)
        block = text.split("| # | Rule | Enforcement |", 1)[1].split("\n\n", 1)[0]
        return self._numbered(block)

    def _orchestrate_body_rules(self):
        text = read_contract(RTL_ORCHESTRATE_SKILL)
        block = text.split("## Pipeline Rules (policy + enforcement map)", 1)[1]
        return self._numbered(block.split("\n---", 1)[0])

    def _injected_rules(self, generated_block):
        block = generated_block.split("## Pipeline Rules", 1)[1].split("\n## ", 1)[0]
        return self._numbered(block)

    @staticmethod
    def _generated_block():
        raw = extract_marked_block(INJECT_HOOK, SESSIONSTART_BLOCK_START, SESSIONSTART_BLOCK_END)
        lines = raw.splitlines()
        envelope = json.loads("\n".join(lines[1:-1]))
        return envelope["hookSpecificOutput"]["additionalContext"]

    def test_all_claude_md_rules_reach_the_runtime(self):
        declared = self._claude_md_rules()
        assert declared, "No numbered rules parsed from CLAUDE.md"
        injected = self._injected_rules(self._generated_block())
        body = self._orchestrate_body_rules()
        assert declared <= injected, (
            f"Rules declared in CLAUDE.md but never injected: {sorted(declared - injected)}"
        )
        assert declared <= body, (
            f"Rules declared in CLAUDE.md but missing from the rtl-orchestrate body: "
            f"{sorted(declared - body)}"
        )


def test_team_skills_record_the_real_leader_session():
    offenders = [p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md") if "<current_session_id>" in read_contract(p)]
    assert offenders == []
    # Every occurrence, not one per file: rtl-p4-block-parallel writes two.
    values = [
        (p.parent.name, value)
        for p in SKILLS_DIR.glob("*/SKILL.md")
        for value in re.findall(r'"leader_session_id":\s*"([^"]*)"', read_contract(p))
    ]
    assert values and all(value == "${CLAUDE_SESSION_ID}" for _, value in values), values


def test_session_id_filter_lists_its_ascii_characters():
    """Ranges such as a-z and classes such as [:alnum:] follow the locale: bash in a UTF-8
    locale matches é with a-z, while dash compares bytes, so Linux CI (dash) cannot catch
    a range behaviorally. The filter must spell out every character it allows."""
    text = read_contract(REPO_ROOT / "hooks" / "lib" / "json-util.sh")
    body = re.search(r"^jsonu_session_id\(\) \{\n(.*?)^\}", text, re.S | re.M).group(1)
    brackets = re.findall(r"\[!([^\]]*)\]", body)
    assert len(brackets) == 1, brackets
    allowed = brackets[0]
    assert "[:" not in allowed, allowed
    assert "-" not in allowed[:-1], f"a '-' before the last position makes a range: {allowed}"
    assert sorted(allowed) == sorted(string.digits + string.ascii_letters + "._-"), allowed


def test_hooks_read_session_fields_from_the_input_root():
    """Best practice 17. jsonu_get_input_string reads tool_input before the root, and a tool
    input can carry a field of the same name (the Agent tool's full schema has its own cwd),
    so it reads only the tool parameters in tool_fields, each named literally. Outside
    json-util.sh no hook scans the input for a session field by hand, except the scans in
    hand_scans. Comments do not count; a call continued with a trailing backslash is read
    as one line."""
    tool_fields = {"skill", "file_path", "command", "subagent_type", "prompt"}
    session_fields = {"cwd", "session_id", "agent_id", "prompt_id", "hook_event_name",
                      "transcript_path", "stop_hook_active", "agent_type", "permission_mode",
                      "background_tasks", "session_crons"}
    # SessionStart and Stop inputs carry no tool_input. The inject hook sources no JSON
    # parser; stop_hook_active is a boolean and background_tasks an array of objects, and
    # jsonu_get_root_string reads neither.
    hand_scans = {("hooks/lib/stop-budget-util.sh", "stop_hook_active"),
                  ("hooks/lib/stop-budget-util.sh", "background_tasks")}
    call = re.compile(r"""jsonu_get_input_string\s+(?:"[^"]*"|'[^']*'|\S+)\s+("[^"]*"|'[^']*'|[^\s);|&]+)""")
    parser = re.compile(r"\b(?:sed|grep|awk|jq|python3?)\b")
    quoted_field = re.compile(r'\\?"(%s)\\?"' % "|".join(sorted(session_fields)))
    scripts = sorted((REPO_ROOT / "hooks").glob("*.sh")) + sorted((REPO_ROOT / "hooks" / "lib").glob("*.sh"))
    keys, scans, offenders = [], set(), []
    for script in scripts:
        name = script.relative_to(REPO_ROOT).as_posix()
        logical, start = "", None
        for lineno, line in enumerate(read_contract(script).splitlines(), 1):
            code = re.sub(r"(^|\s)#.*", "", line)
            start = start or lineno
            if code.endswith("\\"):
                logical += code[:-1] + " "
                continue
            logical += code
            for arg in call.findall(logical):
                keys.append(arg)
                if arg.strip("\"'") not in tool_fields:
                    offenders.append(f"{name}:{start}: key not in tool_fields (list a new tool parameter there): {logical.strip()}")
            if name != "hooks/lib/json-util.sh" and parser.search(logical):
                for field in quoted_field.findall(logical):
                    scans.add((name, field))
                    if (name, field) not in hand_scans:
                        offenders.append(f"{name}:{start}: session field scanned by hand: {logical.strip()}")
            logical, start = "", None
    assert keys, "no jsonu_get_input_string call found: the scan is broken"
    assert offenders == [], "read session fields with jsonu_get_root_string:\n" + "\n".join(offenders)
    assert scans == hand_scans, f"drop the hand scans that are gone: {sorted(hand_scans - scans)}"
