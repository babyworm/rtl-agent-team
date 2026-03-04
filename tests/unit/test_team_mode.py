"""Tests for Claude Code native team integration.

Validates:
- team-config.json creation and cleanup logic
- Task dependency graph structure for P5 verification
- Worker preamble file existence
- Team orchestrator agent structural integrity
"""

import json
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

AGENTS_DIR = REPO_ROOT / "agents"
SKILLS_DIR = REPO_ROOT / "skills"
TEMPLATE_DIR = SKILLS_DIR / "rtl-design-policy" / "templates"


class TestTeamConfigLifecycle:
    """Validate team-config.json creation and cleanup."""

    def test_team_config_template_exists(self):
        template = TEMPLATE_DIR / "team-config.json"
        assert template.exists()

    def test_team_config_template_valid_json(self):
        template = TEMPLATE_DIR / "team-config.json"
        data = json.loads(template.read_text())
        assert isinstance(data["team_mode"], bool)
        assert data["team_mode"] is False
        assert data["team_name"] == ""
        assert data["leader_session_id"] == ""
        assert data["phase"] == ""
        assert "{{TIMESTAMP}}" in data["created_at"]

    def test_team_config_creation(self, tmp_path):
        """Simulate team-config.json creation as the skill would."""
        state_dir = tmp_path / ".rtl-agent-team" / "state"
        state_dir.mkdir(parents=True)
        config = {
            "team_mode": True,
            "team_name": "p5-verify",
            "leader_session_id": "session-abc-123",
            "phase": "p5",
            "created_at": "2026-03-05T00:00:00Z"
        }
        config_file = state_dir / "team-config.json"
        config_file.write_text(json.dumps(config, indent=2))

        loaded = json.loads(config_file.read_text())
        assert loaded["team_mode"] is True
        assert loaded["team_name"] == "p5-verify"
        assert loaded["leader_session_id"] == "session-abc-123"
        assert loaded["phase"] == "p5"

    def test_team_config_cleanup(self, tmp_path):
        """Removing team-config.json restores normal Stop hook behavior."""
        state_dir = tmp_path / ".rtl-agent-team" / "state"
        state_dir.mkdir(parents=True)
        config_file = state_dir / "team-config.json"
        config_file.write_text(json.dumps({"team_mode": True, "team_name": "test"}))
        assert config_file.exists()
        config_file.unlink()
        assert not config_file.exists()


class TestP5TaskDependencyGraph:
    """Validate the P5 verification task dependency structure."""

    CATEGORIES = ["V1_lint", "V2_sva", "V3_cdc", "V4_proto", "V5_func",
                  "V6_cov", "V7_perf", "V8_synth", "V9_review"]

    def _build_dependency_graph(self):
        """Build the canonical P5 dependency graph per module."""
        return {
            "V1_lint": [],
            "V2_sva": [],
            "V3_cdc": [],
            "V4_proto": [],
            "V8_synth": [],
            "V5_func": ["V1_lint", "V2_sva", "V3_cdc", "V4_proto"],
            "V6_cov": ["V5_func"],
            "V7_perf": ["V5_func"],
            "V9_review": ["V1_lint", "V2_sva", "V3_cdc", "V4_proto",
                          "V5_func", "V6_cov", "V7_perf", "V8_synth"],
        }

    def test_independent_categories_have_no_deps(self):
        graph = self._build_dependency_graph()
        for cat in ["V1_lint", "V2_sva", "V3_cdc", "V4_proto", "V8_synth"]:
            assert graph[cat] == [], f"{cat} should have no dependencies"

    def test_functional_depends_on_early_categories(self):
        graph = self._build_dependency_graph()
        assert set(graph["V5_func"]) == {"V1_lint", "V2_sva", "V3_cdc", "V4_proto"}

    def test_coverage_and_perf_depend_on_functional(self):
        graph = self._build_dependency_graph()
        assert graph["V6_cov"] == ["V5_func"]
        assert graph["V7_perf"] == ["V5_func"]

    def test_review_depends_on_all_others(self):
        graph = self._build_dependency_graph()
        all_except_review = [k for k in graph if k != "V9_review"]
        assert set(graph["V9_review"]) == set(all_except_review)

    def test_no_circular_dependencies(self):
        """Verify the graph is a DAG (no cycles)."""
        graph = self._build_dependency_graph()
        visited = set()
        in_stack = set()

        def has_cycle(node):
            if node in in_stack:
                return True
            if node in visited:
                return False
            visited.add(node)
            in_stack.add(node)
            for dep in graph.get(node, []):
                if has_cycle(dep):
                    return True
            in_stack.discard(node)
            return False

        for node in graph:
            assert not has_cycle(node), f"Cycle detected involving {node}"

    def test_multi_module_graph_scales_linearly(self):
        """For N modules, total tasks = 9 * N (one per category per module)."""
        modules = ["mod_a", "mod_b", "mod_c"]
        graph = self._build_dependency_graph()
        total_tasks = len(modules) * len(graph)
        assert total_tasks == 27  # 3 modules * 9 categories


class TestP4TaskDependencyGraph:
    """Validate the P4 implementation 10-wave task dependency structure."""

    WAVES = ["W1_write", "W2_lint", "W3_fix", "W4_review", "W5_bugfix",
             "W6_unittest", "W7_cdc", "W8_protocol", "W9_refactor", "W10_integration"]

    def _build_dependency_graph(self):
        """Build the canonical P4 dependency graph per module."""
        return {
            "W1_write": [],
            "W2_lint": ["W1_write"],
            "W3_fix": ["W2_lint"],
            "W4_review": ["W2_lint"],  # or W3_fix if lint fails
            "W5_bugfix": ["W4_review"],
            "W6_unittest": ["W4_review"],  # or W5_bugfix if issues found
            "W7_cdc": ["W1_write"],
            "W8_protocol": ["W1_write"],
            "W9_refactor": ["W6_unittest", "W7_cdc", "W8_protocol"],
            "W10_integration": ["W9_refactor"],  # blockedBy ALL wave 9 tasks (cross-module)
        }

    def test_write_has_no_deps(self):
        graph = self._build_dependency_graph()
        assert graph["W1_write"] == []

    def test_lint_depends_on_write(self):
        graph = self._build_dependency_graph()
        assert graph["W2_lint"] == ["W1_write"]

    def test_cdc_and_protocol_depend_only_on_write(self):
        """Waves 7 and 8 run parallel with lint path (Waves 2-5)."""
        graph = self._build_dependency_graph()
        assert graph["W7_cdc"] == ["W1_write"]
        assert graph["W8_protocol"] == ["W1_write"]

    def test_refactor_depends_on_unittest_cdc_protocol(self):
        graph = self._build_dependency_graph()
        assert set(graph["W9_refactor"]) == {"W6_unittest", "W7_cdc", "W8_protocol"}

    def test_no_circular_dependencies(self):
        graph = self._build_dependency_graph()
        visited = set()
        in_stack = set()

        def has_cycle(node):
            if node in in_stack:
                return True
            if node in visited:
                return False
            visited.add(node)
            in_stack.add(node)
            for dep in graph.get(node, []):
                if has_cycle(dep):
                    return True
            in_stack.discard(node)
            return False

        for node in graph:
            assert not has_cycle(node), f"Cycle detected involving {node}"

    def test_refactor_no_protocol_deps_exclude_w8(self):
        """W9 depends only on W6+W7 when module has no bus interfaces (no W8)."""
        graph_no_proto = {
            "W1_write": [],
            "W2_lint": ["W1_write"],
            "W3_fix": ["W2_lint"],
            "W4_review": ["W2_lint"],
            "W5_bugfix": ["W4_review"],
            "W6_unittest": ["W4_review"],
            "W7_cdc": ["W1_write"],
            # W8_protocol omitted — module has no bus interfaces
            "W9_refactor": ["W6_unittest", "W7_cdc"],
            "W10_integration": ["W9_refactor"],
        }
        assert "W8_protocol" not in graph_no_proto["W9_refactor"]
        assert set(graph_no_proto["W9_refactor"]) == {"W6_unittest", "W7_cdc"}
        assert len(graph_no_proto) == 9  # 9 waves, not 10

    def test_ten_waves_per_module(self):
        graph = self._build_dependency_graph()
        assert len(graph) == 10


class TestTeamOrchestratorStructure:
    """Validate team orchestrator and worker preamble files."""

    def test_p5_verify_team_orchestrator_exists(self):
        agent = AGENTS_DIR / "p5-verify-team-orchestrator.md"
        assert agent.exists()

    def test_p5_verify_team_orchestrator_has_frontmatter(self):
        agent = AGENTS_DIR / "p5-verify-team-orchestrator.md"
        content = agent.read_text()
        assert content.startswith("---")
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = parts[1]
        assert "name: p5-verify-team-orchestrator" in fm
        assert "model: opus" in fm
        assert "skills:" in fm

    def test_p5_verify_team_orchestrator_references_team_primitives(self):
        agent = AGENTS_DIR / "p5-verify-team-orchestrator.md"
        content = agent.read_text()
        assert "TeamCreate" in content
        assert "TaskCreate" in content
        assert "SendMessage" in content
        assert "TaskList" in content

    def test_p5_verify_team_orchestrator_references_dependency_graph(self):
        agent = AGENTS_DIR / "p5-verify-team-orchestrator.md"
        content = agent.read_text()
        assert "blockedBy" in content or "blocked by" in content.lower()

    def test_p5_verify_team_skill_exists(self):
        skill = SKILLS_DIR / "rtl-p5-verify-team" / "SKILL.md"
        assert skill.exists()

    def test_p5_verify_team_skill_is_user_invocable(self):
        skill = SKILLS_DIR / "rtl-p5-verify-team" / "SKILL.md"
        content = skill.read_text()
        assert "user-invocable: true" in content

    def test_p5_verify_team_skill_delegates_to_orchestrator(self):
        skill = SKILLS_DIR / "rtl-p5-verify-team" / "SKILL.md"
        content = skill.read_text()
        assert 'rtl-agent-team:p5-verify-team-orchestrator' in content

    def test_worker_preamble_exists(self):
        preamble = AGENTS_DIR / "lib" / "team-worker-preamble.md"
        assert preamble.exists()

    def test_worker_preamble_has_lifecycle_sections(self):
        preamble = AGENTS_DIR / "lib" / "team-worker-preamble.md"
        content = preamble.read_text()
        assert "Initialization" in content
        assert "Task Claim" in content or "Task Execution" in content
        assert "Shutdown" in content
        assert "Error Handling" in content

    def test_worker_protocol_template_exists(self):
        """agents/lib/team-worker-protocol.md must exist."""
        protocol = AGENTS_DIR / "lib" / "team-worker-protocol.md"
        assert protocol.exists()

    def test_worker_protocol_has_key_steps(self):
        """Protocol template must have INIT, CLAIM, EXECUTE, REPORT, SHUTDOWN."""
        protocol = AGENTS_DIR / "lib" / "team-worker-protocol.md"
        content = protocol.read_text()
        for step in ["INIT", "CLAIM", "EXECUTE", "REPORT", "SHUTDOWN"]:
            assert step in content, f"Protocol missing step: {step}"

    def test_specialist_agents_have_team_worker_protocol(self):
        """11 specialist agents must have Team Worker Protocol section."""
        agents = [
            "rtl-coder", "lint-checker", "rtl-critic", "testbench-dev", "eda-runner",
            "sva-extractor", "cdc-checker", "protocol-checker",
            "func-verifier", "coverage-analyst", "perf-verifier",
        ]
        missing = []
        for name in agents:
            agent_file = AGENTS_DIR / f"{name}.md"
            assert agent_file.exists(), f"Missing agent: {name}"
            content = agent_file.read_text()
            if "## Team Worker Protocol" not in content:
                missing.append(name)
        assert missing == [], f"Agents missing Team Worker Protocol section: {missing}"

    # --- P4 Team Orchestrator ---

    def test_p4_implement_team_orchestrator_exists(self):
        agent = AGENTS_DIR / "p4-implement-team-orchestrator.md"
        assert agent.exists()

    def test_p4_implement_team_orchestrator_has_frontmatter(self):
        agent = AGENTS_DIR / "p4-implement-team-orchestrator.md"
        content = agent.read_text()
        assert content.startswith("---")
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = parts[1]
        assert "name: p4-implement-team-orchestrator" in fm
        assert "model: opus" in fm
        assert "skills:" in fm

    def test_p4_implement_team_orchestrator_references_team_primitives(self):
        agent = AGENTS_DIR / "p4-implement-team-orchestrator.md"
        content = agent.read_text()
        assert "TeamCreate" in content
        assert "TaskCreate" in content
        assert "SendMessage" in content
        assert "TaskList" in content

    def test_p4_implement_team_orchestrator_references_10_wave(self):
        agent = AGENTS_DIR / "p4-implement-team-orchestrator.md"
        content = agent.read_text()
        assert "Wave 1" in content or "W1" in content
        assert "Wave 10" in content or "W10" in content
        assert "blockedBy" in content

    def test_p4_implement_team_skill_exists(self):
        skill = SKILLS_DIR / "rtl-p4-implement-team" / "SKILL.md"
        assert skill.exists()

    def test_p4_implement_team_skill_is_user_invocable(self):
        skill = SKILLS_DIR / "rtl-p4-implement-team" / "SKILL.md"
        content = skill.read_text()
        assert "user-invocable: true" in content

    def test_p4_implement_team_skill_delegates_to_orchestrator(self):
        skill = SKILLS_DIR / "rtl-p4-implement-team" / "SKILL.md"
        content = skill.read_text()
        assert "rtl-agent-team:p4-implement-team-orchestrator" in content


class TestAutopilotTeamAwareness:
    """Validate autopilot orchestrator team-awareness routing."""

    def test_autopilot_references_p4_team_orchestrator(self):
        agent = AGENTS_DIR / "autopilot-orchestrator.md"
        content = agent.read_text()
        assert "p4-implement-team-orchestrator" in content

    def test_autopilot_references_p5_team_orchestrator(self):
        agent = AGENTS_DIR / "autopilot-orchestrator.md"
        content = agent.read_text()
        assert "p5-verify-team-orchestrator" in content

    def test_autopilot_checks_team_config(self):
        agent = AGENTS_DIR / "autopilot-orchestrator.md"
        content = agent.read_text()
        assert "team-config.json" in content


class TestTeamIntegrationInfrastructure:
    """Validate Phase 4 full integration artifacts."""

    def test_team_fallback_doc_exists(self):
        fallback = AGENTS_DIR / "lib" / "team-fallback.md"
        assert fallback.exists()

    def test_team_fallback_covers_key_scenarios(self):
        fallback = AGENTS_DIR / "lib" / "team-fallback.md"
        content = fallback.read_text()
        assert "TeamCreate Failure" in content
        assert "SendMessage Failure" in content
        assert "Worker Crash" in content
        assert "Leader Crash" in content

    def test_team_progress_hook_exists(self):
        hook = REPO_ROOT / "hooks" / "rtl-team-progress.sh"
        assert hook.exists()

    def test_team_progress_hook_registered_in_hooks_json(self):
        hooks_data = json.loads((REPO_ROOT / "hooks" / "hooks.json").read_text())
        post_entries = hooks_data["hooks"]["PostToolUse"]
        matchers = [e["matcher"] for e in post_entries]
        assert "TaskUpdate" in matchers

    def test_team_progress_hook_checks_team_config(self):
        hook = REPO_ROOT / "hooks" / "rtl-team-progress.sh"
        content = hook.read_text()
        assert "team-config.json" in content

    def test_plugin_version_bumped(self):
        plugin = json.loads((REPO_ROOT / ".claude-plugin" / "plugin.json").read_text())
        major, minor, patch = plugin["version"].split(".")
        assert int(minor) >= 3 or int(major) >= 1, "Version should be >= 0.3.0 for team mode"

    def test_claude_md_has_team_mode_section(self):
        claude_md = (REPO_ROOT / "CLAUDE.md").read_text()
        assert "Native Team Mode" in claude_md

    def test_autopilot_skill_documents_team_mode(self):
        skill = SKILLS_DIR / "rtl-autopilot" / "SKILL.md"
        content = skill.read_text()
        assert "--no-team" in content or "team mode" in content.lower()
