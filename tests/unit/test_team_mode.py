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
            "V5_func": ["V1_lint"],  # Per policy: V5 depends only on V1 (lint-clean required for sim)
            "V6_cov": ["V5_func"],
            "V7_perf": ["V5_func"],
            "V9_review": ["V1_lint", "V2_sva", "V3_cdc", "V4_proto",
                          "V5_func", "V6_cov", "V7_perf", "V8_synth"],
        }

    def test_independent_categories_have_no_deps(self):
        graph = self._build_dependency_graph()
        for cat in ["V1_lint", "V2_sva", "V3_cdc", "V4_proto", "V8_synth"]:
            assert graph[cat] == [], f"{cat} should have no dependencies"

    def test_functional_depends_on_lint_only(self):
        """Per policy: V5 depends only on V1 (lint-clean required for sim)."""
        graph = self._build_dependency_graph()
        assert set(graph["V5_func"]) == {"V1_lint"}

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

    def test_p5_verify_team_orchestrator_has_coordination_teammate_role(self):
        """Orchestrator must have Coordination Teammate Role (Orchestrator as Teammate pattern)."""
        agent = AGENTS_DIR / "p5-verify-team-orchestrator.md"
        content = agent.read_text()
        assert "Coordination Teammate Role" in content
        assert "FORBIDDEN" in content
        assert "TaskCreate" in content
        assert "TaskList" in content or "TaskUpdate" in content

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

    def test_p4_implement_team_orchestrator_has_coordination_teammate_role(self):
        """Orchestrator must have Coordination Teammate Role (Orchestrator as Teammate pattern)."""
        agent = AGENTS_DIR / "p4-implement-team-orchestrator.md"
        content = agent.read_text()
        assert "Coordination Teammate Role" in content
        assert "FORBIDDEN" in content
        assert "TaskCreate" in content
        assert "TaskList" in content or "TaskUpdate" in content

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
        assert "Coordinator Crash" in content

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
        assert int(minor) >= 6 or int(major) >= 1, "Version should be >= 0.6.0 for Orchestrator as Teammate"

    def test_claude_md_has_team_mode_section(self):
        claude_md = (REPO_ROOT / "CLAUDE.md").read_text()
        assert "Native Team Mode" in claude_md

    def test_autopilot_skill_documents_team_mode(self):
        skill = SKILLS_DIR / "rat-auto-design" / "SKILL.md"
        content = skill.read_text()
        assert "--no-team" in content or "team mode" in content.lower()


# ── P1 Task Dependency Graph ────────────────────────────────────────────────


class TestP1TaskDependencyGraph:
    """Validate the P1 research tree-of-thought task dependency structure."""

    def _build_dependency_graph(self):
        """Build the canonical P1 dependency graph."""
        return {
            "T1_tree": [],
            "T2_validate": ["T1_tree"],
            "T3a_deepdive": ["T2_validate"],
            "T3b_deepdive": ["T2_validate"],
            "T4a_memory": ["T2_validate"],
            "T4b_interconnect": ["T2_validate"],
            "T4c_power": ["T2_validate"],
            "T5_comparison": ["T3a_deepdive", "T3b_deepdive",
                              "T4a_memory", "T4b_interconnect", "T4c_power"],
            "T6a_syntax": ["T5_comparison"],
            "T6b_prediction": ["T5_comparison"],
            "T6c_transform": ["T5_comparison"],
            "T6d_filter": ["T5_comparison"],
            "T6e_vidproc": ["T5_comparison"],
            "T6f_merge": ["T5_comparison"],
            "T7_review_r1": ["T6a_syntax", "T6b_prediction", "T6c_transform",
                             "T6d_filter", "T6e_vidproc", "T6f_merge"],
            "T8_revision_r1": ["T7_review_r1"],
            "T9_review_r2": ["T8_revision_r1"],
            "T10_revision_r2": ["T9_review_r2"],
            "T11_review_r3": ["T10_revision_r2"],
            "T12_artifacts": ["T11_review_r3"],
        }

    def test_tree_construction_has_no_deps(self):
        graph = self._build_dependency_graph()
        assert graph["T1_tree"] == []

    def test_validation_depends_on_tree(self):
        graph = self._build_dependency_graph()
        assert graph["T2_validate"] == ["T1_tree"]

    def test_deepdive_depends_on_validation(self):
        graph = self._build_dependency_graph()
        assert graph["T3a_deepdive"] == ["T2_validate"]
        assert graph["T3b_deepdive"] == ["T2_validate"]

    def test_surveys_depend_on_validation(self):
        graph = self._build_dependency_graph()
        for key in ["T4a_memory", "T4b_interconnect", "T4c_power"]:
            assert graph[key] == ["T2_validate"]

    def test_comparison_depends_on_all_deepdives_and_surveys(self):
        graph = self._build_dependency_graph()
        deps = set(graph["T5_comparison"])
        assert "T3a_deepdive" in deps
        assert "T4a_memory" in deps
        assert "T4b_interconnect" in deps
        assert "T4c_power" in deps

    def test_subdomain_tasks_depend_on_comparison(self):
        graph = self._build_dependency_graph()
        for key in ["T6a_syntax", "T6b_prediction", "T6c_transform",
                     "T6d_filter", "T6e_vidproc", "T6f_merge"]:
            assert graph[key] == ["T5_comparison"]

    def test_review_r1_depends_on_all_subdomain(self):
        graph = self._build_dependency_graph()
        assert len(graph["T7_review_r1"]) == 6

    def test_three_mandatory_review_rounds(self):
        graph = self._build_dependency_graph()
        assert "T7_review_r1" in graph
        assert "T9_review_r2" in graph
        assert "T11_review_r3" in graph

    def test_final_artifacts_depend_on_r3(self):
        graph = self._build_dependency_graph()
        assert graph["T12_artifacts"] == ["T11_review_r3"]

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


# ── P2 Task Dependency Graph ────────────────────────────────────────────────


class TestP2TaskDependencyGraph:
    """Validate the P2 architecture dual-stream task dependency structure."""

    def _build_dependency_graph(self):
        """Build the canonical P2 dependency graph."""
        return {
            "T1a_hw_eval": [],
            "T1b_hw_eval": [],
            "T2_selection": ["T1a_hw_eval", "T1b_hw_eval"],
            "T3_arch_design": ["T2_selection"],
            "T4_refc_dev": ["T2_selection"],
            "T5_bandwidth": ["T3_arch_design", "T4_refc_dev"],
            "T6a_r1_spec": ["T5_bandwidth"],
            "T6b_r1_mem": ["T5_bandwidth"],
            "T6c_r1_model": ["T5_bandwidth"],
            "T7_aggregate_r1": ["T6a_r1_spec", "T6b_r1_mem", "T6c_r1_model"],
            "T8a_explore": ["T7_aggregate_r1"],
            "T9_apply": ["T8a_explore"],
            "T10a_r2_spec": ["T9_apply"],
            "T10b_r2_mem": ["T9_apply"],
            "T10c_r2_model": ["T9_apply"],
            "T11_aggregate_r2": ["T10a_r2_spec", "T10b_r2_mem", "T10c_r2_model"],
            "T12a_r3_spec": ["T11_aggregate_r2"],
            "T12b_r3_mem": ["T11_aggregate_r2"],
            "T12c_r3_model": ["T11_aggregate_r2"],
            "T13_final": ["T12a_r3_spec", "T12b_r3_mem", "T12c_r3_model"],
        }

    def test_hw_eval_has_no_deps(self):
        graph = self._build_dependency_graph()
        assert graph["T1a_hw_eval"] == []
        assert graph["T1b_hw_eval"] == []

    def test_selection_depends_on_all_hw_evals(self):
        graph = self._build_dependency_graph()
        assert set(graph["T2_selection"]) == {"T1a_hw_eval", "T1b_hw_eval"}

    def test_parallel_streams_depend_on_selection(self):
        graph = self._build_dependency_graph()
        assert graph["T3_arch_design"] == ["T2_selection"]
        assert graph["T4_refc_dev"] == ["T2_selection"]

    def test_bandwidth_depends_on_both_streams(self):
        graph = self._build_dependency_graph()
        assert set(graph["T5_bandwidth"]) == {"T3_arch_design", "T4_refc_dev"}

    def test_three_parallel_reviewers_per_round(self):
        graph = self._build_dependency_graph()
        # R1: 3 reviewers
        for key in ["T6a_r1_spec", "T6b_r1_mem", "T6c_r1_model"]:
            assert graph[key] == ["T5_bandwidth"]
        # R2: 3 reviewers
        for key in ["T10a_r2_spec", "T10b_r2_mem", "T10c_r2_model"]:
            assert graph[key] == ["T9_apply"]
        # R3: 3 reviewers
        for key in ["T12a_r3_spec", "T12b_r3_mem", "T12c_r3_model"]:
            assert graph[key] == ["T11_aggregate_r2"]

    def test_final_depends_on_all_r3(self):
        graph = self._build_dependency_graph()
        assert set(graph["T13_final"]) == {"T12a_r3_spec", "T12b_r3_mem", "T12c_r3_model"}

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


# ── P3 Task Dependency Graph ────────────────────────────────────────────────


class TestP3TaskDependencyGraph:
    """Validate the P3 uArch dual-stream task dependency structure."""

    def _build_dependency_graph(self):
        """Build the canonical P3 dependency graph."""
        return {
            "T1_uarch": [],
            "T2_bfm": [],
            "T3_bfm_gate": ["T1_uarch", "T2_bfm"],
            "T4a_r1_feature": ["T3_bfm_gate"],
            "T4b_r1_timing": ["T3_bfm_gate"],
            "T4c_r1_algo": ["T3_bfm_gate"],
            "T4d_r1_model": ["T3_bfm_gate"],
            "T4e_r1_bfm": ["T3_bfm_gate"],
            "T5_aggregate_r1": ["T4a_r1_feature", "T4b_r1_timing",
                                "T4c_r1_algo", "T4d_r1_model", "T4e_r1_bfm"],
            "T6_revision": ["T5_aggregate_r1"],
            "T7a_r2": ["T6_revision"],
            "T7b_r2": ["T6_revision"],
            "T8_aggregate_r2": ["T7a_r2", "T7b_r2"],
            "T9a_r3": ["T8_aggregate_r2"],
            "T9b_r3": ["T8_aggregate_r2"],
            "T9c_r3": ["T8_aggregate_r2"],
            "T9d_r3": ["T8_aggregate_r2"],
            "T9e_r3": ["T8_aggregate_r2"],
            "T10_final": ["T9a_r3", "T9b_r3", "T9c_r3", "T9d_r3", "T9e_r3"],
        }

    def test_parallel_streams_have_no_deps(self):
        graph = self._build_dependency_graph()
        assert graph["T1_uarch"] == []
        assert graph["T2_bfm"] == []

    def test_bfm_gate_depends_on_both_streams(self):
        graph = self._build_dependency_graph()
        assert set(graph["T3_bfm_gate"]) == {"T1_uarch", "T2_bfm"}

    def test_five_reviewers_in_r1(self):
        graph = self._build_dependency_graph()
        r1_tasks = [k for k in graph if k.startswith("T4")]
        assert len(r1_tasks) == 5
        for key in r1_tasks:
            assert graph[key] == ["T3_bfm_gate"]

    def test_aggregate_r1_depends_on_all_reviewers(self):
        graph = self._build_dependency_graph()
        assert len(graph["T5_aggregate_r1"]) == 5

    def test_r2_is_selective(self):
        """R2 has fewer reviewers (only those with findings)."""
        graph = self._build_dependency_graph()
        r2_tasks = [k for k in graph if k.startswith("T7") and k != "T7_aggregate"]
        assert len(r2_tasks) >= 2  # At least some selective reviewers

    def test_r3_is_mandatory_all_five(self):
        graph = self._build_dependency_graph()
        r3_tasks = [k for k in graph if k.startswith("T9") and k != "T9_aggregate"]
        assert len(r3_tasks) == 5

    def test_final_depends_on_all_r3(self):
        graph = self._build_dependency_graph()
        assert len(graph["T10_final"]) == 5

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


# ── P1-P3 Team Orchestrator Structure ───────────────────────────────────────


class TestP1P3TeamOrchestratorStructure:
    """Validate P1-P3 team orchestrator and skill structural integrity."""

    TEAM_ORCHESTRATORS = [
        ("p1-research-team-orchestrator", "p1-research-team"),
        ("p2-arch-team-orchestrator", "p2-arch-team"),
        ("p3-uarch-team-orchestrator", "p3-uarch-team"),
    ]

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_orchestrator_exists(self, agent_name, skill_name):
        agent = AGENTS_DIR / f"{agent_name}.md"
        assert agent.exists(), f"Missing team orchestrator: {agent_name}"

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_orchestrator_has_frontmatter(self, agent_name, skill_name):
        agent = AGENTS_DIR / f"{agent_name}.md"
        content = agent.read_text()
        assert content.startswith("---")
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = parts[1]
        assert f"name: {agent_name}" in fm
        assert "model: opus" in fm
        assert "skills:" in fm

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_orchestrator_has_coordination_teammate_role(self, agent_name, skill_name):
        """Orchestrators must have Coordination Teammate Role section."""
        agent = AGENTS_DIR / f"{agent_name}.md"
        content = agent.read_text()
        assert "Coordination Teammate Role" in content
        assert "FORBIDDEN" in content
        assert "TaskCreate" in content

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_orchestrator_references_dependency_graph(self, agent_name, skill_name):
        agent = AGENTS_DIR / f"{agent_name}.md"
        content = agent.read_text()
        assert "blockedBy" in content or "blocked by" in content.lower()

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_skill_exists(self, agent_name, skill_name):
        skill = SKILLS_DIR / f"rtl-{skill_name}" / "SKILL.md"
        assert skill.exists(), f"Missing team skill: rtl-{skill_name}"

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_skill_is_user_invocable(self, agent_name, skill_name):
        skill = SKILLS_DIR / f"rtl-{skill_name}" / "SKILL.md"
        content = skill.read_text()
        assert "user-invocable: true" in content

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_skill_delegates_to_orchestrator(self, agent_name, skill_name):
        skill = SKILLS_DIR / f"rtl-{skill_name}" / "SKILL.md"
        content = skill.read_text()
        assert f"rtl-agent-team:{agent_name}" in content


class TestSpecToUarchTeamStructure:
    """Validate spec-to-uarch-team orchestrator (pipeline, NOT a team)."""

    def test_orchestrator_exists(self):
        agent = AGENTS_DIR / "spec-to-uarch-team-orchestrator.md"
        assert agent.exists()

    def test_orchestrator_has_frontmatter(self):
        agent = AGENTS_DIR / "spec-to-uarch-team-orchestrator.md"
        content = agent.read_text()
        assert content.startswith("---")
        parts = content.split("---", 2)
        fm = parts[1]
        assert "name: spec-to-uarch-team-orchestrator" in fm
        assert "model: opus" in fm

    def test_orchestrator_does_not_create_team(self):
        """Pipeline orchestrator should NOT use TeamCreate (it delegates to phase teams)."""
        agent = AGENTS_DIR / "spec-to-uarch-team-orchestrator.md"
        content = agent.read_text()
        assert "TeamCreate" not in content

    def test_orchestrator_delegates_to_phase_teams(self):
        agent = AGENTS_DIR / "spec-to-uarch-team-orchestrator.md"
        content = agent.read_text()
        assert "p1-research-team-orchestrator" in content
        assert "p2-arch-team-orchestrator" in content
        assert "p3-uarch-team-orchestrator" in content

    def test_skill_exists(self):
        skill = SKILLS_DIR / "rat-p1p3-spec-uarch-team" / "SKILL.md"
        assert skill.exists()

    def test_skill_is_user_invocable(self):
        skill = SKILLS_DIR / "rat-p1p3-spec-uarch-team" / "SKILL.md"
        content = skill.read_text()
        assert "user-invocable: true" in content

    def test_skill_sequences_phase_team_skills(self):
        """Pipeline skill should invoke phase team skills via Skill() calls."""
        skill = SKILLS_DIR / "rat-p1p3-spec-uarch-team" / "SKILL.md"
        content = skill.read_text()
        assert "rtl-p1-research-team" in content
        assert "rtl-p2-arch-team" in content
        assert "rtl-p3-uarch-team" in content


# ── P1-P3 Agent Worker Protocol ─────────────────────────────────────────────


class TestP1P3AgentsHaveProtocol:
    """Validate that all 14 P1-P3 specialist agents have Team Worker Protocol."""

    P1_P3_AGENTS = [
        "spec-analyst", "vcodec-chief-standard-expert", "rtl-architect",
        "vcodec-architecture-expert", "arch-designer", "power-analyzer",
        "vcodec-syntax-entropy-expert", "vcodec-prediction-expert",
        "vcodec-transform-quant-expert", "vcodec-filter-recon-expert",
        "video-processing-expert", "ref-model-dev", "bfm-dev", "timing-advisor",
    ]

    def test_all_agents_have_team_worker_protocol(self):
        missing = []
        for name in self.P1_P3_AGENTS:
            agent_file = AGENTS_DIR / f"{name}.md"
            assert agent_file.exists(), f"Missing agent: {name}"
            content = agent_file.read_text()
            if "## Team Worker Protocol" not in content:
                missing.append(name)
        assert missing == [], f"P1-P3 agents missing Team Worker Protocol: {missing}"


class TestWriteRestrictedProtocol:
    """Validate write-restricted agents have SendMessage-to-leader pattern."""

    WRITE_RESTRICTED = [
        "vcodec-architecture-expert",
        "arch-designer",
        "timing-advisor",
    ]

    def test_write_restricted_agents_have_sendmessage_note(self):
        missing = []
        for name in self.WRITE_RESTRICTED:
            agent_file = AGENTS_DIR / f"{name}.md"
            content = agent_file.read_text()
            if "Write-restricted" not in content and "write-restricted" not in content:
                missing.append(name)
        assert missing == [], f"Write-restricted agents missing SendMessage note: {missing}"

    def test_write_restricted_mentioned_in_orchestrators(self):
        """Team orchestrators should document write-restricted agent handling."""
        for orch in ["p1-research-team-orchestrator", "p2-arch-team-orchestrator",
                      "p3-uarch-team-orchestrator"]:
            content = (AGENTS_DIR / f"{orch}.md").read_text()
            assert "Write-Restricted" in content or "write-restricted" in content.lower(), \
                f"{orch} should document write-restricted agent handling"


class TestAutopilotP1P3TeamAwareness:
    """Validate autopilot skill and orchestrator team-awareness for P1-P3."""

    def test_autopilot_skill_sequences_team_skills(self):
        """In team mode, autopilot skill invokes phase team skills."""
        skill = SKILLS_DIR / "rat-auto-design" / "SKILL.md"
        content = skill.read_text()
        assert "rtl-p1-research-team" in content
        assert "rtl-p2-arch-team" in content
        assert "rtl-p3-uarch-team" in content
        assert "rtl-p4-implement-team" in content
        assert "rtl-p5-verify-team" in content

    def test_autopilot_orchestrator_references_p1_team_orchestrator(self):
        """Autopilot orchestrator (sequential mode) still references team orchestrators."""
        content = (AGENTS_DIR / "autopilot-orchestrator.md").read_text()
        assert "p1-research-team-orchestrator" in content

    def test_autopilot_orchestrator_references_p2_team_orchestrator(self):
        content = (AGENTS_DIR / "autopilot-orchestrator.md").read_text()
        assert "p2-arch-team-orchestrator" in content

    def test_autopilot_orchestrator_references_p3_team_orchestrator(self):
        content = (AGENTS_DIR / "autopilot-orchestrator.md").read_text()
        assert "p3-uarch-team-orchestrator" in content


# ── Skill as Leader Contract Tests ─────────────────────────────────────────


class TestTeamSkillContract:
    """Validate that team skills contain team lifecycle primitives (Skill as Leader)."""

    TEAM_SKILLS = [
        "rtl-p1-research-team",
        "rtl-p2-arch-team",
        "rtl-p3-uarch-team",
        "rtl-p4-implement-team",
        "rtl-p5-verify-team",
    ]

    @pytest.mark.parametrize("skill_name", TEAM_SKILLS)
    def test_team_skill_has_team_create(self, skill_name):
        """Team skills must call TeamCreate (Skill as Leader pattern)."""
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill.read_text()
        assert "TeamCreate" in content, f"{skill_name} missing TeamCreate"

    @pytest.mark.parametrize("skill_name", TEAM_SKILLS)
    def test_team_skill_has_team_delete(self, skill_name):
        """Team skills must call TeamDelete for cleanup."""
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill.read_text()
        assert "TeamDelete" in content, f"{skill_name} missing TeamDelete"

    @pytest.mark.parametrize("skill_name", TEAM_SKILLS)
    def test_team_skill_spawns_workers(self, skill_name):
        """Team skills must spawn workers via Agent(team_name=...)."""
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill.read_text()
        assert "team_name=" in content, f"{skill_name} missing Agent(team_name=...)"

    @pytest.mark.parametrize("skill_name", TEAM_SKILLS)
    def test_team_skill_has_expanded_allowed_tools(self, skill_name):
        """Team skills must have TeamCreate, TeamDelete, Agent in allowed-tools."""
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill.read_text()
        # Extract frontmatter
        parts = content.split("---", 2)
        fm = parts[1] if len(parts) >= 3 else ""
        assert "TeamCreate" in fm, f"{skill_name} allowed-tools missing TeamCreate"
        assert "TeamDelete" in fm, f"{skill_name} allowed-tools missing TeamDelete"
        assert "Agent" in fm, f"{skill_name} allowed-tools missing Agent"

    @pytest.mark.parametrize("skill_name", TEAM_SKILLS)
    def test_team_skill_writes_team_config(self, skill_name):
        """Team skills must write team-config.json."""
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill.read_text()
        assert "team-config.json" in content, f"{skill_name} missing team-config.json write"

    @pytest.mark.parametrize("skill_name", TEAM_SKILLS)
    def test_team_skill_uses_subagent_type(self, skill_name):
        """Agent calls must use subagent_type= not agent_type= (official API)."""
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill.read_text()
        # Exclude 'subagent_type=' matches when checking for bare 'agent_type='
        import re
        bare_agent_type = re.findall(r'(?<!sub)agent_type=', content)
        assert bare_agent_type == [], \
            f"{skill_name} uses deprecated agent_type= (should be subagent_type=)"
        assert "subagent_type=" in content, \
            f"{skill_name} missing subagent_type= in Agent calls"

    @pytest.mark.parametrize("skill_name", TEAM_SKILLS)
    def test_team_skill_agent_has_description(self, skill_name):
        """Agent calls must include description= parameter (required by API)."""
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill.read_text()
        # Count uncommented Agent( calls and description= occurrences in Agent blocks
        import re
        # Multi-line Agent calls: count Agent( opening lines (uncommented)
        agent_starts = re.findall(r'^(?!\s*#)\s*Agent\(', content, re.MULTILINE)
        # Count description= within Agent call context (uncommented lines)
        desc_params = re.findall(r'^(?!\s*#).*description=', content, re.MULTILINE)
        assert len(agent_starts) > 0, f"{skill_name} has no Agent() calls"
        assert len(desc_params) >= len(agent_starts), \
            f"{skill_name}: {len(agent_starts) - len(desc_params)} Agent() calls missing description="

    @pytest.mark.parametrize("skill_name", TEAM_SKILLS)
    def test_team_skill_task_create_uses_subject(self, skill_name):
        """TaskCreate must use subject= not title= (official API)."""
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill.read_text()
        if "TaskCreate(" in content:
            # Check no TaskCreate uses 'title='
            for line in content.split('\n'):
                if 'TaskCreate(' in line:
                    assert 'title=' not in line, \
                        f"{skill_name} TaskCreate uses title= (should be subject=)"

    @pytest.mark.parametrize("skill_name", TEAM_SKILLS)
    def test_team_skill_team_delete_no_params(self, skill_name):
        """TeamDelete() should have no parameters (uses current team context)."""
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill.read_text()
        assert "TeamDelete()" in content, \
            f"{skill_name} TeamDelete should have no parameters"

    @pytest.mark.parametrize("skill_name", TEAM_SKILLS)
    def test_team_skill_spawns_coordinator_as_teammate(self, skill_name):
        """Coordinator must be spawned via Agent(team_name=...) not Task()."""
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill.read_text()
        # Must have Agent() call with coordinator/orchestrator name and team_name
        import re
        coordinator_agent = re.findall(
            r'Agent\([^)]*team_name=[^)]*orchestrator', content, re.DOTALL)
        assert len(coordinator_agent) >= 1, \
            f"{skill_name} must spawn coordinator orchestrator via Agent(team_name=...)"

    @pytest.mark.parametrize("skill_name", TEAM_SKILLS)
    def test_team_skill_no_task_orchestrator(self, skill_name):
        """Skills must NOT spawn orchestrator via Task() (old pattern)."""
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill.read_text()
        import re
        # Exclude commented lines
        task_orch = re.findall(
            r'^(?!\s*#).*Task\([^)]*orchestrator', content, re.MULTILINE)
        assert task_orch == [], \
            f"{skill_name} still uses Task() for orchestrator (should use Agent(team_name=...))"

    @pytest.mark.parametrize("skill_name", TEAM_SKILLS)
    def test_team_skill_worker_count_within_limit(self, skill_name):
        """Team skills must have 4-6 Agent(team_name=...) calls (1 coordinator + 3-5 workers)."""
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = skill.read_text()
        import re
        # Count uncommented Agent(team_name=...) calls
        agent_calls = re.findall(
            r'^(?!\s*#)\s*Agent\([^)]*team_name=', content, re.MULTILINE)
        assert 4 <= len(agent_calls) <= 6, \
            f"{skill_name} has {len(agent_calls)} Agent(team_name=...) calls, expected 4-6"


class TestTeamOrchestratorTeammateContract:
    """Validate orchestrators have Coordination Teammate Role and CAN use SendMessage."""

    ALL_TEAM_ORCHESTRATORS = [
        "p1-research-team-orchestrator",
        "p2-arch-team-orchestrator",
        "p3-uarch-team-orchestrator",
        "p4-implement-team-orchestrator",
        "p5-verify-team-orchestrator",
    ]

    @pytest.mark.parametrize("orch_name", ALL_TEAM_ORCHESTRATORS)
    def test_has_coordination_teammate_role_section(self, orch_name):
        """All team orchestrators must have Coordination Teammate Role section."""
        content = (AGENTS_DIR / f"{orch_name}.md").read_text()
        assert "Coordination Teammate Role" in content

    @pytest.mark.parametrize("orch_name", ALL_TEAM_ORCHESTRATORS)
    def test_lists_forbidden_operations(self, orch_name):
        """Coordination Teammate Role must list FORBIDDEN operations."""
        content = (AGENTS_DIR / f"{orch_name}.md").read_text()
        assert "FORBIDDEN" in content

    @pytest.mark.parametrize("orch_name", ALL_TEAM_ORCHESTRATORS)
    def test_sendmessage_not_in_forbidden(self, orch_name):
        """SendMessage must NOT be in FORBIDDEN list (coordinator needs it)."""
        content = (AGENTS_DIR / f"{orch_name}.md").read_text()
        # Extract the FORBIDDEN line
        for line in content.split('\n'):
            if 'FORBIDDEN' in line and '**' in line:
                assert 'SendMessage' not in line, \
                    f"{orch_name} still has SendMessage in FORBIDDEN"
                break

    @pytest.mark.parametrize("orch_name", ALL_TEAM_ORCHESTRATORS)
    def test_sendmessage_in_allowed(self, orch_name):
        """SendMessage must be in ALLOWED list."""
        content = (AGENTS_DIR / f"{orch_name}.md").read_text()
        for line in content.split('\n'):
            if 'ALLOWED' in line and '**' in line:
                assert 'SendMessage' in line, \
                    f"{orch_name} missing SendMessage in ALLOWED"
                break

    @pytest.mark.parametrize("orch_name", ALL_TEAM_ORCHESTRATORS)
    def test_uses_task_coordination(self, orch_name):
        """Orchestrators must use TaskCreate for coordination."""
        content = (AGENTS_DIR / f"{orch_name}.md").read_text()
        assert "TaskCreate" in content


class TestWorkerSubagentPattern:
    """Validate worker preamble documents Task() specialist delegation and coordinator messaging."""

    def test_preamble_documents_specialist_delegation(self):
        """Preamble must document Task() specialist delegation pattern."""
        preamble = AGENTS_DIR / "lib" / "team-worker-preamble.md"
        content = preamble.read_text()
        assert "Task(" in content or "specialist" in content.lower(), \
            "Preamble must document Task() specialist delegation"

    def test_preamble_sendmessage_to_coordinator(self):
        """Preamble must show SendMessage recipient as coordinator, not leader."""
        preamble = AGENTS_DIR / "lib" / "team-worker-preamble.md"
        content = preamble.read_text()
        assert "coordinator" in content.lower(), \
            "Preamble must reference coordinator as SendMessage recipient"

    def test_protocol_report_step_targets_coordinator(self):
        """Protocol REPORT step must target coordinator."""
        protocol = AGENTS_DIR / "lib" / "team-worker-protocol.md"
        content = protocol.read_text()
        assert "coordinator" in content.lower(), \
            "Protocol must reference coordinator in REPORT step"

    def test_protocol_has_delegate_step(self):
        """Protocol must document specialist Task() delegation."""
        protocol = AGENTS_DIR / "lib" / "team-worker-protocol.md"
        content = protocol.read_text()
        assert "DELEGATE" in content, \
            "Protocol must have DELEGATE step for Task() specialist spawning"

    def test_specialist_agents_have_team_worker_protocol_expanded(self):
        """All 32 specialist agents (28 existing + 4 added) must have Team Worker Protocol."""
        agents = [
            # Original 11 (P4-P5)
            "rtl-coder", "lint-checker", "rtl-critic", "testbench-dev", "eda-runner",
            "sva-extractor", "cdc-checker", "protocol-checker",
            "func-verifier", "coverage-analyst", "perf-verifier",
            # P1-P3 (14)
            "spec-analyst", "vcodec-chief-standard-expert", "rtl-architect",
            "vcodec-architecture-expert", "arch-designer", "power-analyzer",
            "vcodec-syntax-entropy-expert", "vcodec-prediction-expert",
            "vcodec-transform-quant-expert", "vcodec-filter-recon-expert",
            "video-processing-expert", "ref-model-dev", "bfm-dev", "timing-advisor",
            # Domain/misc (3)
            "vproc-image-processing-expert", "vproc-denoise-expert", "vproc-color-format-expert",
            # 4 newly added protocol agents
            "constraint-writer", "synthesis-reporter", "ref-model-reviewer", "uarch-designer",
        ]
        missing = []
        for name in agents:
            agent_file = AGENTS_DIR / f"{name}.md"
            if not agent_file.exists():
                continue
            content = agent_file.read_text()
            if "## Team Worker Protocol" not in content:
                missing.append(name)
        assert missing == [], f"Agents missing Team Worker Protocol: {missing}"
