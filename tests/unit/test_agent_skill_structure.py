"""Tests for agent and skill structural integrity.

Validates:
- Agent YAML frontmatter (name, model, description)
- Skill SKILL.md files (name, description)
- Cross-references: CLAUDE.md delegation table ↔ actual agents/skills
- hooks.json structure
- plugin.json structure
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AGENTS_DIR = REPO_ROOT / "agents"
SKILLS_DIR = REPO_ROOT / "skills"
HOOKS_JSON = REPO_ROOT / "hooks" / "hooks.json"
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
RTL_ORCHESTRATE_SKILL = SKILLS_DIR / "rtl-orchestrate" / "SKILL.md"
ORCHESTRATOR_INJECT_HOOK = REPO_ROOT / "hooks" / "rtl-orchestrator-inject.sh"


def _read_frontmatter(path: Path) -> str:
    content = path.read_text()
    parts = content.split("---", 2)
    assert len(parts) >= 3, f"Missing YAML frontmatter: {path}"
    return parts[1]


def _extract_marked_block(path: Path, start_marker: str, end_marker: str) -> str:
    lines = path.read_text().splitlines()
    in_block = False
    out = []

    for line in lines:
        if line == start_marker:
            in_block = True
            continue
        if in_block and line == end_marker:
            return "\n".join(out).strip()
        if in_block:
            out.append(line)

    raise AssertionError(f"Markers not found in {path}: {start_marker} ... {end_marker}")


# ── Agent definition tests ──────────────────────────────────────────────────


class TestAgentDefinitions:
    """Validate agent Markdown files in agents/."""

    @pytest.fixture
    def agent_files(self):
        return sorted(AGENTS_DIR.glob("*.md"))

    def test_agents_dir_exists(self):
        assert AGENTS_DIR.is_dir(), "agents/ directory must exist"

    def test_at_least_40_agents(self, agent_files):
        assert len(agent_files) >= 40, f"Expected ≥40 agents, got {len(agent_files)}"

    def test_all_agents_have_yaml_frontmatter(self, agent_files):
        """Every agent .md must start with --- YAML frontmatter ---."""
        missing = []
        for f in agent_files:
            content = f.read_text()
            if not content.startswith("---"):
                missing.append(f.name)
        assert missing == [], f"Agents missing YAML frontmatter: {missing}"

    def test_all_agents_have_name(self, agent_files):
        missing = []
        for f in agent_files:
            content = f.read_text()
            # Extract YAML between first --- and second ---
            parts = content.split("---", 2)
            if len(parts) < 3:
                missing.append(f.name)
                continue
            yaml_block = parts[1]
            if "name:" not in yaml_block:
                missing.append(f.name)
        assert missing == [], f"Agents missing 'name:' in frontmatter: {missing}"

    def test_all_agents_have_model(self, agent_files):
        missing = []
        for f in agent_files:
            content = f.read_text()
            parts = content.split("---", 2)
            if len(parts) < 3:
                missing.append(f.name)
                continue
            yaml_block = parts[1]
            if "model:" not in yaml_block:
                missing.append(f.name)
        assert missing == [], f"Agents missing 'model:' in frontmatter: {missing}"

    def test_all_agents_have_description(self, agent_files):
        missing = []
        for f in agent_files:
            content = f.read_text()
            parts = content.split("---", 2)
            if len(parts) < 3:
                missing.append(f.name)
                continue
            yaml_block = parts[1]
            if "description:" not in yaml_block:
                missing.append(f.name)
        assert missing == [], f"Agents missing 'description:' in frontmatter: {missing}"

    def test_agent_name_matches_filename(self, agent_files):
        """Agent name in YAML should match the filename (without .md)."""
        mismatches = []
        for f in agent_files:
            content = f.read_text()
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue
            yaml_block = parts[1]
            match = re.search(r'name:\s*(\S+)', yaml_block)
            if match:
                name = match.group(1).strip().strip('"').strip("'")
                expected = f.stem
                if name != expected:
                    mismatches.append(f"{f.name}: name={name}, expected={expected}")
        assert mismatches == [], f"Agent name/filename mismatches: {mismatches}"

    def test_no_empty_agent_files(self, agent_files):
        empty = [f.name for f in agent_files if f.stat().st_size < 50]
        assert empty == [], f"Near-empty agent files: {empty}"

    def test_all_agents_have_rat_protocol_reference(self, agent_files):
        """Every agent .md must reference the audit output protocol."""
        missing = []
        for f in agent_files:
            content = f.read_text()
            if "audit-output-protocol.md" not in content:
                missing.append(f.name)
        assert missing == [], f"Agents missing RAT protocol reference: {missing}"

    def test_audit_output_protocol_exists(self):
        """The shared audit output protocol file must exist."""
        protocol = AGENTS_DIR / "lib" / "audit-output-protocol.md"
        assert protocol.exists(), "agents/lib/audit-output-protocol.md must exist"
        content = protocol.read_text()
        assert "RAT" in content
        assert "DECISION" in content
        assert "USER_CONFIRMED" in content


# ── Skill definition tests ──────────────────────────────────────────────────


class TestSkillDefinitions:
    """Validate skill SKILL.md files in skills/."""

    @pytest.fixture
    def skill_dirs(self):
        return sorted([d for d in SKILLS_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')])

    @pytest.fixture
    def skill_files(self, skill_dirs):
        return [d / "SKILL.md" for d in skill_dirs if (d / "SKILL.md").exists()]

    def test_skills_dir_exists(self):
        assert SKILLS_DIR.is_dir(), "skills/ directory must exist"

    def test_at_least_30_skills(self, skill_dirs):
        assert len(skill_dirs) >= 30, f"Expected ≥30 skill dirs, got {len(skill_dirs)}"

    def test_every_skill_dir_has_skill_md(self, skill_dirs):
        missing = [d.name for d in skill_dirs if not (d / "SKILL.md").exists()]
        assert missing == [], f"Skill dirs missing SKILL.md: {missing}"

    def test_all_skills_have_yaml_frontmatter(self, skill_files):
        missing = []
        for f in skill_files:
            content = f.read_text()
            if not content.startswith("---"):
                missing.append(f.parent.name)
        assert missing == [], f"Skills missing YAML frontmatter: {missing}"

    def test_all_skills_have_name(self, skill_files):
        missing = []
        for f in skill_files:
            content = f.read_text()
            parts = content.split("---", 2)
            if len(parts) < 3:
                missing.append(f.parent.name)
                continue
            if "name:" not in parts[1]:
                missing.append(f.parent.name)
        assert missing == [], f"Skills missing 'name:' in frontmatter: {missing}"

    def test_skill_name_matches_dirname(self, skill_files):
        """Skill name in YAML should match its directory name."""
        mismatches = []
        for f in skill_files:
            content = f.read_text()
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue
            match = re.search(r'name:\s*["\']?(\S+?)["\']?\s*$', parts[1], re.MULTILINE)
            if match:
                name = match.group(1)
                expected = f.parent.name
                if name != expected:
                    mismatches.append(f"{f.parent.name}: name={name}")
        assert mismatches == [], f"Skill name/dirname mismatches: {mismatches}"

    def test_skills_with_scripts_have_executables(self):
        """Skills with scripts/ dir should have .sh or .py files."""
        empty_script_dirs = []
        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir():
                continue
            script_dir = skill_dir / "scripts"
            if script_dir.is_dir():
                scripts = list(script_dir.glob("*.sh")) + list(script_dir.glob("*.py"))
                if not scripts:
                    empty_script_dirs.append(skill_dir.name)
        assert empty_script_dirs == [], f"Skills with empty scripts/: {empty_script_dirs}"


# ── Cross-reference: CLAUDE.md ↔ agents ↔ skills ────────────────────────────


class TestCrossReferences:
    """Validate cross-references between CLAUDE.md, agents/, and skills/."""

    @pytest.fixture
    def claude_md_content(self):
        return CLAUDE_MD.read_text()

    @pytest.fixture
    def agent_names(self):
        return {f.stem for f in AGENTS_DIR.glob("*.md")}

    @pytest.fixture
    def skill_names(self):
        return {d.name for d in SKILLS_DIR.iterdir() if d.is_dir() and (d / "SKILL.md").exists()}

    def test_delegation_agents_exist(self, claude_md_content, agent_names):
        """Agents referenced in CLAUDE.md delegation table should exist."""
        # Match patterns like `rtl-agent-team:agent-name`
        refs = re.findall(r'rtl-agent-team:([a-z0-9-]+)', claude_md_content)
        # Filter to delegation table entries (agent names, not skill names)
        # Agent names are in the "Delegated Agent" column
        missing = []
        for ref in set(refs):
            if ref in agent_names:
                continue
            # It might be a skill reference, not an agent — skip those
            skill_match = any(ref == s for s in [d.name for d in SKILLS_DIR.iterdir() if d.is_dir()])
            if not skill_match:
                missing.append(ref)
        assert missing == [], f"Unknown rtl-agent-team references in CLAUDE.md: {sorted(set(missing))}"

    def test_action_skill_to_orchestrator_policy_chain(self):
        """Action Skill → Orchestrator Agent → Policy Skill mapping must be intact."""
        chains = [
            ("rtl-autopilot", "autopilot-orchestrator", "rtl-autopilot-policy"),
            ("p1-spec-research", "p1-research-orchestrator", "p1-spec-research-policy"),
            ("p2-arch-design", "p2-arch-orchestrator", "p2-arch-design-policy"),
            ("rtl-p3-uarch-design", "p3-uarch-orchestrator", "rtl-p3-uarch-policy"),
            ("rtl-p4-implement", "p4-implement-orchestrator", "rtl-p4-implement-policy"),
            ("rtl-p4-implement-team", "p4-implement-team-orchestrator", "rtl-p4-implement-policy"),
            ("rtl-p4-rapid-impl", "p4-rtl-sanity-orchestrator", "rtl-design-policy"),
            ("rtl-p4s-bugfix", "p4s-bugfix-orchestrator", "rtl-p4s-bugfix-policy"),
            ("rtl-p4s-refactor", "p4s-refactor-orchestrator", "rtl-p4s-refactor-policy"),
            ("rtl-p4s-unit-test", "p4s-unit-test-orchestrator", "rtl-p4s-unit-test-policy"),
            ("rtl-p5-verify", "p5-verify-orchestrator", "rtl-p5-verify-policy"),
            ("rtl-p5-verify-team", "p5-verify-team-orchestrator", "rtl-p5-verify-policy"),
            ("rtl-p5a-functional-closure", "p5a-functional-closure-orchestrator", "rtl-functional-verify-policy"),
            ("rtl-p5b-silicon-validation", "p5b-silicon-validation-orchestrator", "rtl-silicon-validation-policy"),
            ("rtl-p5s-func-verify", "p5s-func-verify-orchestrator", "rtl-p5s-func-verify-policy"),
            ("rtl-p5s-integration-test", "p5s-integration-orchestrator", "rtl-p5s-integration-test-policy"),
            ("rtl-p5s-sva-check", "p5s-sva-orchestrator", "rtl-p5s-sva-policy"),
            ("rtl-p5s-cdc-verify", "p5s-cdc-orchestrator", "rtl-p5s-cdc-policy"),
            ("rtl-p5s-protocol-verify", "p5s-protocol-orchestrator", "rtl-p5s-protocol-policy"),
            ("rtl-p5s-perf-verify", "p5s-perf-orchestrator", "rtl-p5s-perf-policy"),
            ("rtl-p5s-coverage-analyze", "p5s-coverage-orchestrator", "rtl-p5s-coverage-policy"),
            ("rtl-p5s-uvm-verify", "p5s-uvm-orchestrator", "rtl-p5s-uvm-policy"),
            ("rtl-p6-design-review", "p6-review-orchestrator", "rtl-p6-design-review-policy"),
            ("rtl-p7-exploration", "p7-exploration-orchestrator", "rtl-p7-exploration-policy"),
            ("rtl-review-refactor", "review-refactor-orchestrator", "code-review-policy"),
            ("rtl-dse", "dse-orchestrator", "rtl-dse-policy"),
            ("rtl-spec-to-uarch", "spec-to-uarch-orchestrator", "rtl-spec-to-uarch-policy"),
            ("rtl-uarch-to-verify", "uarch-to-verify-orchestrator", "rtl-uarch-to-verify-policy"),
            # P1-P5 team mode orchestrators (v0.5.0)
            ("rtl-p1-research-team", "p1-research-team-orchestrator", "p1-spec-research-policy"),
            ("rtl-p2-arch-team", "p2-arch-team-orchestrator", "p2-arch-design-policy"),
            ("rtl-p3-uarch-team", "p3-uarch-team-orchestrator", "rtl-p3-uarch-policy"),
            ("rtl-spec-to-uarch-team", "spec-to-uarch-team-orchestrator", "rtl-spec-to-uarch-policy"),
        ]

        for action_skill, orchestrator, policy_skill in chains:
            action_file = SKILLS_DIR / action_skill / "SKILL.md"
            assert action_file.exists(), f"Missing action skill: {action_skill}"
            action_frontmatter = _read_frontmatter(action_file)
            assert re.search(r"^user-invocable:\s*true\s*$", action_frontmatter, re.MULTILINE), (
                f"Action skill must be user-invocable: {action_skill}"
            )

            action_content = action_file.read_text()
            task_pattern = rf'Task\(subagent_type="rtl-agent-team:{re.escape(orchestrator)}"'
            assert re.search(task_pattern, action_content), (
                f"{action_skill} must delegate to orchestrator {orchestrator}"
            )

            agent_file = AGENTS_DIR / f"{orchestrator}.md"
            assert agent_file.exists(), f"Missing orchestrator agent: {orchestrator}"
            agent_frontmatter = _read_frontmatter(agent_file)
            skills_pattern = rf"^skills:\s*\[[^\]]*\b{re.escape(policy_skill)}\b[^\]]*\]\s*$"
            assert re.search(skills_pattern, agent_frontmatter, re.MULTILINE), (
                f"{orchestrator} must load policy skill {policy_skill}"
            )

            policy_file = SKILLS_DIR / policy_skill / "SKILL.md"
            assert policy_file.exists(), f"Missing policy skill: {policy_skill}"
            policy_frontmatter = _read_frontmatter(policy_file)
            assert re.search(r"^user-invocable:\s*false\s*$", policy_frontmatter, re.MULTILINE), (
                f"Policy skill must not be user-invocable: {policy_skill}"
            )

    def test_convention_skills_are_non_user_invocable(self):
        convention_skills = ["systemverilog", "systemverilog-assertion", "systemc", "uvm"]
        for skill_name in convention_skills:
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            assert skill_file.exists(), f"Missing convention skill: {skill_name}"
            frontmatter = _read_frontmatter(skill_file)
            assert re.search(r"^user-invocable:\s*false\s*$", frontmatter, re.MULTILINE), (
                f"Convention skill must be non-user-invocable: {skill_name}"
            )

    def test_review_refactor_orchestrator_loads_all_required_policies(self):
        action_skill = "rtl-review-refactor"
        orchestrator = "review-refactor-orchestrator"
        required_policies = [
            "code-review-policy",
            "refactor-policy",
            "verification-recheck-policy",
        ]

        action_file = SKILLS_DIR / action_skill / "SKILL.md"
        assert action_file.exists(), f"Missing action skill: {action_skill}"
        action_content = action_file.read_text()
        assert re.search(r'Task\(subagent_type="rtl-agent-team:review-refactor-orchestrator"', action_content)

        agent_file = AGENTS_DIR / f"{orchestrator}.md"
        assert agent_file.exists(), f"Missing orchestrator agent: {orchestrator}"
        agent_frontmatter = _read_frontmatter(agent_file)

        for policy in required_policies:
            skills_pattern = rf"^skills:\s*\[[^\]]*\b{re.escape(policy)}\b[^\]]*\]\s*$"
            assert re.search(skills_pattern, agent_frontmatter, re.MULTILINE), (
                f"{orchestrator} must load policy skill {policy}"
            )

            policy_file = SKILLS_DIR / policy / "SKILL.md"
            assert policy_file.exists(), f"Missing policy skill: {policy}"
            policy_frontmatter = _read_frontmatter(policy_file)
            assert re.search(r"^user-invocable:\s*false\s*$", policy_frontmatter, re.MULTILINE), (
                f"Policy skill must not be user-invocable: {policy}"
            )

    def test_p4_state_module_population_contract_is_explicit(self):
        p4_template = SKILLS_DIR / "rtl-design-policy" / "templates" / "p4-state.json"
        assert p4_template.exists(), "Missing p4-state template"
        template_text = p4_template.read_text()
        assert "{{module_name}}" not in template_text, (
            "p4-state template should not keep unresolved {{module_name}} placeholders"
        )

        p4_orchestrator = AGENTS_DIR / "p4-rtl-sanity-orchestrator.md"
        assert p4_orchestrator.exists(), "Missing p4-rtl-sanity-orchestrator agent"
        orchestrator_text = p4_orchestrator.read_text()
        assert re.search(r"modules?.*empty", orchestrator_text, re.IGNORECASE | re.DOTALL), (
            "p4 orchestrator should explain that template modules map starts empty"
        )
        assert re.search(r"populate\s+`?modules`?\s+map", orchestrator_text, re.IGNORECASE), (
            "p4 orchestrator should state runtime population of modules map"
        )

    def test_p5_legacy_and_split_relationships_are_documented(self):
        p5_legacy = (SKILLS_DIR / "rtl-p5-verify" / "SKILL.md").read_text()
        p5a = (SKILLS_DIR / "rtl-p5a-functional-closure" / "SKILL.md").read_text()
        p5b = (SKILLS_DIR / "rtl-p5b-silicon-validation" / "SKILL.md").read_text()

        assert "rtl-p5a-functional-closure" in p5_legacy
        assert "rtl-p5b-silicon-validation" in p5_legacy
        assert "rtl-p5-verify" in p5a
        assert "rtl-p5b-silicon-validation" in p5a
        assert "rtl-p5-verify" in p5b
        assert "rtl-p5a-functional-closure" in p5b

    def test_p5_verify_prereqs_reference_both_p4_entry_paths(self):
        p5_legacy = (SKILLS_DIR / "rtl-p5-verify" / "SKILL.md").read_text()
        assert "rtl-p4-rapid-impl" in p5_legacy
        assert "rtl-p4-implement" in p5_legacy
        assert "gates.p4_exit.verdict" in p5_legacy

    def test_p5b_precondition_is_state_based(self):
        p5b_orchestrator = (AGENTS_DIR / "p5b-silicon-validation-orchestrator.md").read_text()
        assert ".rtl-agent-team/state/p5a-state.json" in p5b_orchestrator
        assert "gates.p5a_exit.verdict" in p5b_orchestrator
        assert "precondition.p5a_functional_closure_pass" in p5b_orchestrator

    def test_review_refactor_is_marked_cross_cutting_not_phase_replacement(self):
        skill_file = SKILLS_DIR / "rtl-review-refactor" / "SKILL.md"
        assert skill_file.exists(), "Missing rtl-review-refactor skill"
        content = skill_file.read_text()
        assert "cross-cutting" in content
        assert re.search(r"not\s+a\s+replacement.*phase pipeline", content, re.IGNORECASE | re.DOTALL)
        assert re.search(r"P1\s*-\s*P6|P1-P6", content)

    def test_rtl_orchestrate_hook_export_is_synced(self):
        skill_block = _extract_marked_block(
            RTL_ORCHESTRATE_SKILL,
            "<!-- SESSIONSTART_HOOK_EXPORT_START -->",
            "<!-- SESSIONSTART_HOOK_EXPORT_END -->",
        )
        hook_block = _extract_marked_block(
            ORCHESTRATOR_INJECT_HOOK,
            "# BEGIN GENERATED ROUTING BLOCK - sync via scripts/sync_orchestrator_inject.sh",
            "# END GENERATED ROUTING BLOCK",
        )
        assert skill_block, "Export block in rtl-orchestrate must not be empty"
        assert skill_block == hook_block, (
            "Hook routing block is out of sync with skills/rtl-orchestrate/SKILL.md. "
            "Run: sh scripts/sync_orchestrator_inject.sh"
        )

    def test_key_agents_exist(self, agent_names):
        """Core agents listed in CLAUDE.md delegation table must exist."""
        core_agents = [
            "spec-analyst", "arch-designer", "rtl-architect",
            "uarch-designer", "rtl-coder", "rtl-critic",
            "testbench-dev", "func-verifier", "eda-runner",
            "lint-checker", "sva-extractor", "coverage-analyst",
        ]
        missing = [a for a in core_agents if a not in agent_names]
        assert missing == [], f"Core agents missing from agents/: {missing}"

    def test_key_skills_exist(self, skill_names):
        """Core skills listed in CLAUDE.md skill table must exist."""
        core_skills = [
            "rtl-autopilot", "rtl-p4-implement", "rtl-p4s-bugfix",
            "rtl-p5s-func-verify", "rtl-lint-check", "rtl-synth-check",
            "p1-spec-research", "p2-arch-design", "rtl-p3-uarch-design",
            "systemverilog", "uvm",
        ]
        missing = [s for s in core_skills if s not in skill_names]
        assert missing == [], f"Core skills missing from skills/: {missing}"


# ── hooks.json structure tests ───────────────────────────────────────────────


class TestHooksJson:
    """Validate hooks/hooks.json structure."""

    @pytest.fixture
    def hooks_data(self):
        return json.loads(HOOKS_JSON.read_text())

    def test_hooks_json_exists(self):
        assert HOOKS_JSON.exists()

    def test_has_hooks_key(self, hooks_data):
        assert "hooks" in hooks_data

    def test_has_post_tool_use(self, hooks_data):
        assert "PostToolUse" in hooks_data["hooks"]

    def test_has_stop_hooks(self, hooks_data):
        assert "Stop" in hooks_data["hooks"]

    def test_post_tool_use_tracks_edit_and_write(self, hooks_data):
        matchers = [h["matcher"] for h in hooks_data["hooks"]["PostToolUse"]]
        assert "Edit" in matchers
        assert "Write" in matchers

    def test_stop_hooks_have_both_gates(self, hooks_data):
        """Stop hooks should include both stop-gate and rtl-verify-stop-gate."""
        stop_hooks = hooks_data["hooks"]["Stop"]
        assert len(stop_hooks) > 0
        all_commands = " ".join(
            h.get("command", "") for entry in stop_hooks for h in entry.get("hooks", [])
        )
        assert "stop-gate.sh" in all_commands
        assert "rtl-verify-stop-gate.sh" in all_commands

    def test_hook_scripts_exist(self, hooks_data):
        """All hook scripts referenced in hooks.json must exist."""
        hooks_dir = REPO_ROOT / "hooks"
        missing = []
        for event_hooks in hooks_data["hooks"].values():
            for entry in event_hooks:
                for hook in entry.get("hooks", []):
                    cmd = hook.get("command", "")
                    # Extract script filename from command
                    match = re.search(r'hooks/([a-z0-9-]+\.sh)', cmd)
                    if match:
                        script = hooks_dir / match.group(1)
                        if not script.exists():
                            missing.append(match.group(1))
        assert missing == [], f"Missing hook scripts: {missing}"


# ── plugin.json structure tests ──────────────────────────────────────────────


class TestPluginJson:
    """Validate .claude-plugin/plugin.json structure."""

    @pytest.fixture
    def plugin_data(self):
        return json.loads(PLUGIN_JSON.read_text())

    def test_plugin_json_exists(self):
        assert PLUGIN_JSON.exists()

    def test_has_name(self, plugin_data):
        assert "name" in plugin_data
        assert plugin_data["name"] == "rtl-agent-team"

    def test_has_version(self, plugin_data):
        assert "version" in plugin_data

    def test_has_description(self, plugin_data):
        assert "description" in plugin_data
        assert len(plugin_data["description"]) > 10
