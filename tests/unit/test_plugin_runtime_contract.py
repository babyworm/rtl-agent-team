"""Plugin runtime contract tests.

These tests focus on runtime behavior as a Claude Code plugin:
- hook registration order/shape in hooks.json
- plugin manifest coherence with marketplace metadata
- SessionStart injected routing block validity for Action Skill-first routing
"""

import json
import os
import re
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
        assert event_keys == {"SessionStart", "PostToolUse", "PreToolUse", "SubagentStart", "SubagentStop", "Stop"}

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

    def test_posttooluse_matchers(self, hooks):
        entries = hooks["hooks"]["PostToolUse"]
        matchers = [e["matcher"] for e in entries]
        assert matchers == ["Edit|Write|Bash", "TaskUpdate", "TaskCreate"]

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


class TestSpawnContextProjectRootContract:
    """v0.13.x Workflow-drivability contract: the spawn-context manifest ships
    project_root (RAT_PROJECT_ROOT override, CWD fallback) and the two
    manifest-writing hooks honor the override for paths not routed through
    rat_project_dir()."""

    SPAWN_CTX_UTIL = REPO_ROOT / "hooks" / "lib" / "spawn-context-util.sh"
    OVERRIDE_LINE = '[ -d "${RAT_PROJECT_ROOT:-}" ] && CWD="$RAT_PROJECT_ROOT"'

    def test_manifest_emits_project_root_field(self):
        content = self.SPAWN_CTX_UTIL.read_text()
        assert '"project_root":"$SCTX_PROJECT_ROOT_ESC"' in content, (
            "spawn-context manifest must emit a project_root field"
        )
        # Resolution: -d guarded env override, session-CWD fallback (mirrors
        # rat-dir-util.sh semantics).
        assert 'SCTX_PROJECT_ROOT="$SCTX_CWD"' in content
        assert (
            '[ -d "${RAT_PROJECT_ROOT:-}" ] && SCTX_PROJECT_ROOT="$RAT_PROJECT_ROOT"'
            in content
        )

    @pytest.mark.parametrize(
        "hook_name", ["rtl-spawn-context.sh", "rtl-phase-state-bootstrap.sh"]
    )
    def test_manifest_hooks_honor_project_root_override(self, hook_name):
        content = (REPO_ROOT / "hooks" / hook_name).read_text()
        assert self.OVERRIDE_LINE in content, (
            f"{hook_name} must apply the -d guarded RAT_PROJECT_ROOT CWD "
            "override right after CWD resolution"
        )


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
        content = RTL_ORCHESTRATE_SKILL.read_text()
        start_token = "## Expert Review → Agent Delegation"
        end_token = "## Phase-Aware Invocation Cues"
        assert start_token in content
        assert end_token in content
        return content.split(start_token, 1)[1].split(end_token, 1)[0]

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
        assert "lint/scripts/run_cdc.sh --tool structural" in content
        assert "Gate fail when unwaived `VIOLATION` exists." in content

    def test_syn_tool_profiles_include_open_source_invocation(self):
        content = SYN_TOOL_PROFILES.read_text()
        assert "syn/scripts/run_syn.sh --tool yosys" in content
        assert "Gate Criteria" in content


def _rat_setup_delivered_content() -> str:
    """SKILL.md plus its on-demand references/ files.

    Static install/check/template content was extracted to
    skills/rat-setup/references/*.md (loaded via Read at the decision points
    where SKILL.md instructs it). The remediation contract is delivered by the
    combined content, so contract assertions check the combination.
    """
    content = RAT_SETUP_SKILL.read_text()
    refs_dir = RAT_SETUP_SKILL.parent / "references"
    if refs_dir.is_dir():
        for ref in sorted(refs_dir.glob("*.md")):
            content += "\n" + ref.read_text()
    return content


class TestRatSetupRuntimeContract:
    """Lock required-tool remediation guidance for rat-setup."""

    def test_rat_setup_requires_install_when_required_tools_missing(self):
        content = _rat_setup_delivered_content()
        assert "Required tool remediation" in content
        assert "installation is required before real design work" in content
        assert "Ready to start: Yes/No (**No** if any required tool is missing)" in content

    def test_rat_setup_includes_user_local_install_fallback(self):
        content = _rat_setup_delivered_content()
        assert "~/.local/bin" in content
        assert '"$RAT_EDA_VENV/bin/python" -m pip install cocotb' in content
        assert 'CMAKE_INSTALL_PREFIX="$HOME/.local"' in content
        assert 'ln -sf "$HOME/tools/oss-cad-suite/bin/yosys" "$HOME/.local/bin/yosys"' in content

    def test_rat_setup_prompts_for_global_local_or_skip(self):
        content = _rat_setup_delivered_content()
        assert "global" in content
        assert "local" in content
        assert "skip" in content
        assert "Before installing missing required tools" in content
        assert "LLM executes directly" in content
        assert "sudo commands for user to run manually" in content

    def test_rat_setup_prefers_upstream_install_for_recent_verilator_and_systemc(self):
        content = _rat_setup_delivered_content()
        assert "distro packages are often outdated" in content
        assert "Actively look up the latest stable version" in content
        assert "VERILATOR_LATEST_TAG" in content
        assert "SYSTEMC_LATEST_TAG" in content
        assert 'git checkout "$VERILATOR_LATEST_TAG"' in content
        assert "git clone https://github.com/verilator/verilator.git" in content
        assert "verilator.org/guide/latest/install.html" in content
        assert "git clone https://github.com/accellera-official/systemc.git" in content

    def test_install_commands_download_verible_archive_before_extracting_it(self):
        content = RAT_SETUP_INSTALL_COMMANDS.read_text()
        download = content.index("github.com/chipsalliance/verible/releases/download")
        extract = content.index("tar xzf", download)
        assert download < extract

    def test_install_commands_resolve_slang_server_from_plugin_root(self):
        content = RAT_SETUP_INSTALL_COMMANDS.read_text()
        assert '${CLAUDE_PLUGIN_ROOT}/scripts/install-slang-server.sh' in content
        assert "bash scripts/install-slang-server.sh" not in content

    def test_docker_build_context_resolves_from_plugin_root(self):
        install_commands = RAT_SETUP_INSTALL_COMMANDS.read_text()
        docker_environment = RAT_SETUP_DOCKER_ENVIRONMENT.read_text()
        assert 'docker build -t rtl-eda-tools "${CLAUDE_PLUGIN_ROOT}/docker/"' in install_commands
        assert '  "${CLAUDE_PLUGIN_ROOT}/docker/"' in docker_environment
        assert '--mount "type=bind,src=$(pwd),dst=/workspace"' in docker_environment

    def test_install_commands_cover_required_open_source_lint_and_cdc_tools(self):
        content = RAT_SETUP_INSTALL_COMMANDS.read_text()
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
                RAT_SETUP_TOOL_CHECK_COMMANDS.read_text(),
                RAT_PLUGIN_DEBUG_SKILL.read_text(),
            ]
        )
        hidden_failure = re.compile(r"\|\s*head\s+-1\s*\|\|\s*echo\s+\"?(?:NOT_FOUND|NO_IMAGE)")
        assert not hidden_failure.search(content)

    def test_plugin_registration_is_read_through_claude_cli(self):
        content = "\n".join(
            [
                RAT_SETUP_SKILL.read_text(),
                RAT_SETUP_TOOL_CHECK_COMMANDS.read_text(),
            ]
        )
        assert "claude plugin list --json" in content
        assert "~/.claude/plugins.json" not in content

    def test_owned_skill_docs_use_canonical_plugin_commands(self):
        content = "\n".join(
            [
                RAT_SETUP_INSTALL_COMMANDS.read_text(),
                RAT_PLUGIN_DEBUG_SKILL.read_text(),
                RTL_LINT_CHECK_SKILL.read_text(),
                RTL_P5S_SVA_POLICY.read_text(),
            ]
        )
        assert "/rtl-agent-team:rat-setup" in content
        assert "/rtl-agent-team:rat-init-project" in content
        assert not re.search(r"`/(?:rat-setup|rat-init-project)`", content)
        assert "pip install slang" not in content
        assert "pip install sbyosys" not in content

    def test_rat_setup_bash_fences_are_syntactically_valid(self):
        content = RAT_SETUP_SKILL.read_text()
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
        content = self.RAT_INIT_PROJECT_SKILL.read_text()
        assert "Non-destructive" in content or "non-destructive" in content

    def test_recommends_rat_setup(self):
        content = self.RAT_INIT_PROJECT_SKILL.read_text()
        assert "rat-setup" in content

    def test_setup_marker_check(self):
        content = self.RAT_INIT_PROJECT_SKILL.read_text()
        assert ".setup-complete" in content

    def test_setup_marker_fallback_path(self):
        content = self.RAT_INIT_PROJECT_SKILL.read_text()
        assert ".config/rtl-agent-team" in content

    def test_directory_structure_defined(self):
        content = self.RAT_INIT_PROJECT_SKILL.read_text()
        for d in ["rtl/", "refc/", "sim/", "docs/", "reviews/", "lint/", "syn/"]:
            assert d in content, f"Missing directory {d} in rat-init-project"

    def test_diagram_rules_fallback(self):
        content = self.RAT_INIT_PROJECT_SKILL.read_text()
        assert "<markdown_diagram_rule>" in content


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


class TestExpertTriggerContracts:
    """Verify that the 4 conditional expert agents have trigger contracts in SSOT
    and are referenced by the relevant orchestrators."""

    EXPERT_CONTRACTS = {
        "rtl-planner": {
            "ssot_pattern": r"rtl-planner.*P3",
            "orchestrators": ["p3-uarch-team-orchestrator"],
            "pattern_in_orchestrator": r"rtl-planner",
        },
        "clock-architect": {
            "ssot_pattern": r"clock-architect.*P3.*P4.*P5|clock-architect.*multi-clock",
            "orchestrators": ["p3-uarch-team-orchestrator", "p5-verify-orchestrator"],
            "pattern_in_orchestrator": r"clock-architect",
        },
        "ref-model-reviewer": {
            "ssot_pattern": r"ref-model-reviewer.*P2",
            "orchestrators": ["p2-arch-team-orchestrator"],
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
        content = RTL_ORCHESTRATE_SKILL.read_text()
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
            content = orch_file.read_text()
            assert re.search(contract["pattern_in_orchestrator"], content), (
                f"{expert} not referenced in {orch_name}.md"
            )

    def test_equivalence_checker_in_p4_wave9_section(self):
        """equivalence-checker must appear in P4 orchestrator's Wave 9 section, not just anywhere."""
        content = (AGENTS_DIR / "p4-implement-orchestrator.md").read_text()
        # Find Wave 9 section
        assert "Wave 9" in content, "P4 orchestrator must have Wave 9 section"
        wave9_start = content.index("Wave 9")
        wave9_section = content[wave9_start:wave9_start + 1500]
        assert "equivalence-checker" in wave9_section, (
            "equivalence-checker must be in Wave 9 section (not just anywhere in file)"
        )

    def test_cdc_reviewer_in_p5_cdc_escalation(self):
        """cdc-reviewer must appear alongside clock-architect in P5 CDC escalation."""
        for fname in ["p5-verify-orchestrator.md", "p5-verify-team-orchestrator.md"]:
            content = (AGENTS_DIR / fname).read_text()
            # Find CDC escalation section (different wording in solo vs team)
            cdc_idx = content.find("CDC findings indicate clock-architecture root cause")
            if cdc_idx == -1:
                cdc_idx = content.find("clock-architect Escalation")
            if cdc_idx == -1:
                cdc_idx = content.find("CDC root cause points to clock architecture")
            assert cdc_idx != -1, f"{fname} missing CDC escalation section"
            escalation_section = content[cdc_idx:cdc_idx + 800]
            assert "cdc-reviewer" in escalation_section, (
                f"{fname}: cdc-reviewer must be in CDC escalation section (per policy)"
            )
            assert "clock-architect" in escalation_section, (
                f"{fname}: clock-architect must be in CDC escalation section (per policy)"
            )

    def test_ssot_cues_match_sessionstart_export(self):
        """SessionStart export block must include Asymmetric Phase Gate principle."""
        content = RTL_ORCHESTRATE_SKILL.read_text()
        export_start = "<!-- SESSIONSTART_HOOK_EXPORT_START -->"
        export_end = "<!-- SESSIONSTART_HOOK_EXPORT_END -->"
        assert export_start in content
        export_block = content.split(export_start)[1].split(export_end)[0]
        assert "Asymmetric Phase Gate" in export_block


class TestBfmRetryParity:
    """Verify BFM retry limit consistency across policy and orchestrators."""

    POLICY = SKILLS_DIR / "rtl-p3-uarch-policy" / "SKILL.md"
    SOLO_ORCH = AGENTS_DIR / "p3-uarch-orchestrator.md"
    TEAM_ORCH = AGENTS_DIR / "p3-uarch-team-orchestrator.md"

    def test_policy_defines_max_2(self):
        content = self.POLICY.read_text()
        assert re.search(r"max\s+2\s+iteration", content, re.IGNORECASE)

    def test_solo_orchestrator_matches_policy(self):
        content = self.SOLO_ORCH.read_text()
        assert re.search(r"max\s+2\s+iteration", content, re.IGNORECASE), (
            "Solo orchestrator BFM retry limit must match policy (max 2)"
        )

    def test_team_orchestrator_matches_policy(self):
        content = self.TEAM_ORCH.read_text()
        assert re.search(r"Max\s+2\s+iteration", content, re.IGNORECASE), (
            "Team orchestrator BFM retry limit must match policy (max 2)"
        )


class TestP5TeamFlowParity:
    """Verify P5 team orchestrator has Stage 2 and Stage 3 flow parity with solo."""

    SOLO = AGENTS_DIR / "p5-verify-orchestrator.md"
    TEAM = AGENTS_DIR / "p5-verify-team-orchestrator.md"

    def test_team_has_top_level_stage(self):
        content = self.TEAM.read_text()
        assert re.search(r"Stage\s*2|Top-Level Verification", content), (
            "P5 team orchestrator must include Stage 2 (Top-Level) verification"
        )

    def test_team_has_final_compliance_stage(self):
        content = self.TEAM.read_text()
        assert "final-compliance.md" in content, (
            "P5 team orchestrator must generate final-compliance.md"
        )

    def test_team_has_requirement_traceability(self):
        content = self.TEAM.read_text()
        assert "requirement-traceability" in content, (
            "P5 team orchestrator must include requirement traceability (Stage 3)"
        )

    def test_team_has_e2e_traceability(self):
        content = self.TEAM.read_text()
        assert "e2e-traceability" in content, (
            "P5 team orchestrator must include e2e traceability (Stage 3)"
        )

    def test_solo_and_team_both_have_three_stages(self):
        solo = self.SOLO.read_text()
        team = self.TEAM.read_text()
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
    TEAM = AGENTS_DIR / "spec-to-uarch-team-orchestrator.md"

    def test_team_has_refc_artifact_gate(self):
        content = self.TEAM.read_text()
        assert "refc/" in content or "refc/**" in content, (
            "spec-to-uarch-team must check refc artifact existence at P2→P3 gate"
        )

    def test_team_has_bandwidth_artifact_gate(self):
        content = self.TEAM.read_text()
        assert "bandwidth_report" in content, (
            "spec-to-uarch-team must check bandwidth_report.json at P2→P3 gate"
        )


class TestP4TeamGateParity:
    """Verify P4 team gate covers all policy categories."""

    TEAM = AGENTS_DIR / "p4-implement-team-orchestrator.md"

    def test_gate_checks_code_review(self):
        content = self.TEAM.read_text()
        assert re.search(r"code review.*PASS|review.*PASS", content, re.IGNORECASE)

    def test_gate_checks_cdc(self):
        content = self.TEAM.read_text()
        assert re.search(r"CDC.*PASS", content, re.IGNORECASE)

    def test_gate_checks_protocol(self):
        content = self.TEAM.read_text()
        assert re.search(r"protocol.*PASS", content, re.IGNORECASE)


class TestP5TeamV5Dependency:
    """Verify V5 depends only on V1 (per policy), not V1-V4."""

    TEAM = AGENTS_DIR / "p5-verify-team-orchestrator.md"

    def test_v5_blocked_by_lint_only(self):
        content = self.TEAM.read_text()
        # Match TaskCreate for V5 specifically (not the category table header)
        v5_match = re.search(r'TaskCreate\(subject=.*?V5:.*?blockedBy=\[([^\]]+)\]', content, re.DOTALL)
        assert v5_match, "V5 TaskCreate with blockedBy not found"
        blocked_by = v5_match.group(1)
        assert "t_lint" in blocked_by, "V5 must depend on lint"
        assert "t_sva" not in blocked_by, "V5 should not depend on SVA (per policy)"
        assert "t_cdc" not in blocked_by, "V5 should not depend on CDC (per policy)"
        assert "t_proto" not in blocked_by, "V5 should not depend on protocol (per policy)"


class TestP5TeamClockArchitect:
    """Verify P5 team has conditional clock-architect escalation."""

    TEAM = AGENTS_DIR / "p5-verify-team-orchestrator.md"

    def test_team_has_clock_architect_escalation(self):
        content = self.TEAM.read_text()
        assert "clock-architect" in content, (
            "P5 team orchestrator must have conditional clock-architect escalation for CDC root cause"
        )


class TestP5abP6ArtifactChain:
    """Verify P5A→P5B→P6 artifact connection is closed."""

    P5A = AGENTS_DIR / "p5a-functional-closure-orchestrator.md"
    P5B = AGENTS_DIR / "p5b-silicon-validation-orchestrator.md"
    P6 = AGENTS_DIR / "p6-review-orchestrator.md"

    def test_p5b_generates_final_compliance(self):
        content = self.P5B.read_text()
        assert "final-compliance.md" in content, (
            "P5B must generate final-compliance.md as P6 entry artifact"
        )

    def test_p5b_requires_p5a_pass(self):
        content = self.P5B.read_text()
        assert "p5a_exit" in content and "pass" in content.lower()

    def test_p6_documents_both_paths(self):
        content = self.P6.read_text()
        assert "P5A" in content or "p5a" in content or "P5B" in content or "p5b" in content, (
            "P6 must document awareness of P5A/P5B split path"
        )

    def test_p5a_documents_no_final_compliance(self):
        content = self.P5A.read_text()
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


class TestSkillDescriptionLengthContract:
    """User-invocable skill descriptions must stay within the 160-char budget.

    Descriptions are always-on context (Layer 4 frontmatter loads at session
    start for every skill). The 160-char cap keeps the progressive-disclosure
    budget bounded; a runaway description silently inflates every session.
    """

    MAX_DESCRIPTION_CHARS = 160

    def _skill_description(self, skill_name: str) -> str:
        skill_file = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill_file.read_text()
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
        text = CLAUDE_MD.read_text()
        block = text.split("| # | Rule | Enforcement |", 1)[1].split("\n\n", 1)[0]
        return self._numbered(block)

    def _orchestrate_body_rules(self):
        text = RTL_ORCHESTRATE_SKILL.read_text()
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
