"""Tests for JSON configuration file validation."""

import json
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT


class TestHooksJson:
    """Validate hooks/hooks.json structure."""

    @pytest.fixture
    def hooks_config(self):
        path = REPO_ROOT / "hooks" / "hooks.json"
        assert path.exists(), f"hooks.json not found at {path}"
        return json.loads(path.read_text())

    def test_top_level_hooks_key(self, hooks_config):
        assert "hooks" in hooks_config

    def test_post_tool_use_events(self, hooks_config):
        assert "PostToolUse" in hooks_config["hooks"]
        ptu = hooks_config["hooks"]["PostToolUse"]
        assert isinstance(ptu, list)
        assert len(ptu) >= 2  # Edit and Write

    def test_stop_events(self, hooks_config):
        assert "Stop" in hooks_config["hooks"]
        stop = hooks_config["hooks"]["Stop"]
        assert isinstance(stop, list)

    def test_hook_entries_have_required_fields(self, hooks_config):
        for event_type, entries in hooks_config["hooks"].items():
            for entry in entries:
                assert "matcher" in entry, f"Missing matcher in {event_type}"
                assert "hooks" in entry, f"Missing hooks in {event_type}"
                for hook in entry["hooks"]:
                    assert "type" in hook
                    assert "command" in hook

    def test_edit_tracker_referenced(self, hooks_config):
        commands = []
        for entries in hooks_config["hooks"].values():
            for entry in entries:
                for hook in entry["hooks"]:
                    commands.append(hook["command"])
        assert any("rtl-edit-tracker" in c for c in commands)

    def test_stop_gate_referenced(self, hooks_config):
        commands = []
        for entry in hooks_config["hooks"].get("Stop", []):
            for hook in entry["hooks"]:
                commands.append(hook["command"])
        assert any("stop-gate" in c for c in commands)
        assert any("rtl-verify-stop-gate" in c for c in commands)


class TestPluginJson:
    """Validate .claude-plugin/plugin.json structure."""

    @pytest.fixture
    def plugin_config(self):
        path = REPO_ROOT / ".claude-plugin" / "plugin.json"
        assert path.exists(), f"plugin.json not found at {path}"
        return json.loads(path.read_text())

    def test_has_skills(self, plugin_config):
        assert "skills" in plugin_config or "skillsDir" in plugin_config

    def test_valid_json(self):
        path = REPO_ROOT / ".claude-plugin" / "plugin.json"
        # Should not raise
        json.loads(path.read_text())


class TestPackageJson:
    """Validate package.json structure."""

    @pytest.fixture
    def pkg(self):
        path = REPO_ROOT / "package.json"
        assert path.exists()
        return json.loads(path.read_text())

    def test_has_name(self, pkg):
        assert "name" in pkg
        assert pkg["name"] == "rtl-agent-team"

    def test_has_version(self, pkg):
        assert "version" in pkg

    def test_files_listed(self, pkg):
        assert "files" in pkg
        assert isinstance(pkg["files"], list)
        assert len(pkg["files"]) > 0

    def test_required_dirs_in_files(self, pkg):
        files = pkg["files"]
        for required in ["skills", "hooks", "scripts"]:
            assert required in files, f"'{required}' missing from package.json files"


class TestDomainManifest:
    """Validate domain-packages/video-codec/manifest.json."""

    @pytest.fixture
    def manifest(self):
        path = REPO_ROOT / "domain-packages" / "video-codec" / "manifest.json"
        if not path.exists():
            pytest.skip("Video codec domain package not present")
        return json.loads(path.read_text())

    def test_has_domain(self, manifest):
        assert "domain" in manifest

    def test_has_experts(self, manifest):
        experts = manifest.get("experts", manifest.get("agents", []))
        assert len(experts) > 0, "No experts defined"

    def test_has_standards(self, manifest):
        assert "standards" in manifest or "supported_standards" in manifest


class TestAutopilotStateTemplate:
    """Validate autopilot state template."""

    @pytest.fixture
    def state_template(self):
        # Search for it
        candidates = list(REPO_ROOT.rglob("autopilot-state.json"))
        if not candidates:
            pytest.skip("autopilot-state.json template not found")
        return json.loads(candidates[0].read_text())

    def test_has_phases(self, state_template):
        assert "phases" in state_template or "current_phase" in state_template

    def test_valid_json(self):
        candidates = list(REPO_ROOT.rglob("autopilot-state.json"))
        for path in candidates:
            json.loads(path.read_text())  # Should not raise


class TestAllJsonFilesValid:
    """Ensure all .json files in the repo parse without errors."""

    def test_all_json_parseable(self):
        errors = []
        for json_file in REPO_ROOT.rglob("*.json"):
            # Skip node_modules, .git, and test fixtures
            if any(p in json_file.parts for p in ("node_modules", ".git", "tests")):
                continue
            try:
                json.loads(json_file.read_text())
            except json.JSONDecodeError as e:
                errors.append(f"{json_file}: {e}")
        assert not errors, f"Invalid JSON files:\n" + "\n".join(errors)


class TestP4P5StateTemplates:
    """Validate new phase state templates for P4/P5A/P5B."""

    @pytest.mark.parametrize(
        "relpath",
        [
            "skills/rtl-design-policy/templates/p4-state.json",
            "skills/rtl-functional-verify-policy/templates/p5a-state.json",
            "skills/rtl-silicon-validation-policy/templates/p5b-state.json",
        ],
    )
    def test_state_template_exists_and_valid_json(self, relpath):
        path = REPO_ROOT / relpath
        assert path.exists(), f"Missing state template: {path}"
        data = json.loads(path.read_text())
        assert "schema_version" in data
        assert "phase" in data
        assert "gates" in data
