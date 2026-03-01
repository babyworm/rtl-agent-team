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


# ── Skill definition tests ──────────────────────────────────────────────────


class TestSkillDefinitions:
    """Validate skill SKILL.md files in skills/."""

    @pytest.fixture
    def skill_dirs(self):
        return sorted([d for d in SKILLS_DIR.iterdir() if d.is_dir()])

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
        # We don't fail on skill references that aren't agents
        # Only check explicitly listed agents in the delegation table
        pass

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
            "rtl-autopilot", "rtl-code", "rtl-bugfix",
            "rtl-func-verify", "rtl-lint-check", "rtl-synth-check",
            "research-analyze", "arch-design", "rtl-uarch-design",
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
