from tests.contracts import read_contract, accepted_skill_input
"""Tests for hook scripts — routing inject, edit tracker, and stop gates."""

import datetime
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from tests.conftest import HOOKS_DIR, REPO_ROOT, run_hook


def _record_team_owner(project, leader):
    config=project/'.rat/state/team-config.json'
    run_hook(HOOKS_DIR/'rtl-team-owner.sh',{'cwd':str(project),'session_id':leader,
        'tool_input':{'file_path':str(config)}})


def _budget_path(state, gate):
    candidates=list(state.glob('stop-budget-'+gate+'-*.txt'))
    return candidates[0] if len(candidates)==1 else state/('stop-budget-'+gate+'.txt')


def _track(tracking, content):
    """Write a tracking file and create the HDL it names, as a real edit leaves it.
    The gate needs no evidence for a path that no longer exists."""
    tracking.write_text(content)
    root = tracking.parents[2].resolve()
    for line in content.splitlines():
        path = (root / line.strip()).resolve() if line.strip() else None
        if path and path.is_relative_to(root) and path.suffix in (".sv", ".svh", ".v", ".vh") and not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("module fixture; endmodule\n")


def _record_passing_evidence(project):
    """A runner-result fixture for gate tests; execution itself is tested separately."""
    state = project / ".rat/state"
    sources = {}
    for tracking in state.glob("rtl-modified-files*.txt"):
        for line in tracking.read_text().splitlines():
            if not line.strip():
                continue
            source = (project / line).resolve()
            source.parent.mkdir(parents=True, exist_ok=True)
            if not source.exists():
                source.write_text("module fixture; endmodule\n")
            sources[str(source)] = hashlib.sha256(source.read_bytes()).hexdigest()
    log = state / "passing-simulation.log"
    log.write_text("RAT_SIM_PASS\n")
    record = {"verdict": "PASS", "sources": sources, "log": str(log),
              "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest()}
    (state / "verify-evidence.json").write_text(json.dumps({"schema_version": 1, "runs": [record]}))


def _setup_marker(tmp_project):
    """Create the .claude/rules/rtl-coding-conventions.md setup marker."""
    rules_dir = tmp_project / ".claude" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "rtl-coding-conventions.md").write_text("# marker")


def _assert_stop_blocked(result):
    """A Stop gate blocked the stop and handed Claude a reason to keep working.

    continue=false would end the whole turn and drop the reason (verified live
    on Claude Code 2.1.282), so a Stop gate blocks through decision/reason only.
    """
    assert result.get("continue") is not False, result
    assert result.get("decision") == "block", result
    reason = result.get("reason")
    assert isinstance(reason, str) and reason.strip(), result
    assert "hookSpecificOutput" not in result, result


def _assert_denied(result):
    """A PreToolUse gate refused only this tool call and told Claude why."""
    assert result.get("continue") is not False, result
    hso = result.get("hookSpecificOutput")
    assert isinstance(hso, dict), result
    assert hso.get("hookEventName") == "PreToolUse", result
    assert hso.get("permissionDecision") == "deny", result
    reason = hso.get("permissionDecisionReason")
    assert isinstance(reason, str) and reason.strip(), result


class TestEdaContext:
    hook = HOOKS_DIR / "rtl-eda-context.sh"

    @pytest.mark.parametrize("event", ["SessionStart", "SubagentStart"])
    def test_uninitialized_session_uses_private_settings_without_disclosing_values(self, tmp_path, event):
        project = tmp_path / "uninitialized project"
        project.mkdir()
        data = Path(os.environ["RAT_DATA_DIR"])
        (data / "env-config.json").write_text('{"default_site":"private-fixture"}')
        (data / "sites").mkdir()
        (data / "sites/private-fixture.json").write_text('{"execution":{"host":"synthetic.invalid"}}')
        result = run_hook(self.hook, {"hook_event_name": event, "cwd": str(project)}, cwd=project)
        envelope = result["hookSpecificOutput"]
        assert envelope["hookEventName"] == event
        context = envelope["additionalContext"]
        assert "env-config.json" in context and "eda_runner.py get" in context
        assert "distinct RAT_EXPERIMENT_ID" in context
        assert all(value not in context for value in ["private-fixture", "synthetic.invalid", str(data)])
        assert list(project.iterdir()) == []

    def test_project_config_wins_without_marker_from_nested_directory(self, tmp_path):
        project = tmp_path / "project"
        nested = project / "design"
        nested.mkdir(parents=True)
        (project / "rat_config.json").write_text('{"execution":{"host":"private.invalid"}}')
        (Path(os.environ["RAT_DATA_DIR"]) / "env-config.json").write_text("{}")
        result = run_hook(self.hook, {"hook_event_name": "SubagentStart", "cwd": str(nested)},
                          env={"CLAUDE_PROJECT_DIR": str(project)})
        context = result["hookSpecificOutput"]["additionalContext"]
        assert "project rat_config.json" in context
        assert "env-config.json" not in context and "private.invalid" not in context
        assert not (project / ".rat").exists()

    def test_session_start_hands_the_plugin_data_folder_to_bash(self, tmp_path, monkeypatch):
        monkeypatch.delenv("RAT_DATA_DIR")  # hooks receive only CLAUDE_PLUGIN_DATA
        data = Path(os.environ["CLAUDE_PLUGIN_DATA"])
        (data / "env-config.json").write_text('{"preferences":{"simulator":"fixture-simulator"}}')
        files = {}
        for event in ("SessionStart", "SubagentStart"):
            files[event] = tmp_path / (event + ".env")
            files[event].write_text("")
            result = run_hook(self.hook, {"hook_event_name": event, "cwd": str(tmp_path)}, cwd=tmp_path,
                              env={"CLAUDE_ENV_FILE": str(files[event])})
            assert "env-config.json" in result["hookSpecificOutput"]["additionalContext"]
        assert files["SessionStart"].read_text() == f"export RAT_DATA_DIR='{data}'\n"
        assert files["SubagentStart"].read_text() == ""
        # Bash commands see only the exported folder, never CLAUDE_PLUGIN_DATA.
        bash_env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PLUGIN_DATA"}
        command = (f". '{files['SessionStart']}'; '{sys.executable}' '{REPO_ROOT / 'scripts/eda_runner.py'}' "
                   f"get --root '{tmp_path}' --key preferences.simulator")
        shell = subprocess.run(["bash", "-c", command], env=bash_env, capture_output=True, text=True, timeout=20)
        assert shell.stdout.strip() == "fixture-simulator", shell.stderr

    def test_no_configuration_adds_no_context(self, tmp_path):
        result = run_hook(self.hook, {"hook_event_name": "SessionStart", "cwd": str(tmp_path)}, cwd=tmp_path)
        assert result == {"hookSpecificOutput": {"hookEventName": "SessionStart"}}
        assert list(tmp_path.iterdir()) == []

    def test_machine_preferences_without_default_site_are_available(self, tmp_path):
        (Path(os.environ["RAT_DATA_DIR"]) / "env-config.json").write_text(
            '{"preferences":{"simulator":"fixture-simulator"}}')
        result = run_hook(self.hook, {"hook_event_name": "SessionStart", "cwd": str(tmp_path)}, cwd=tmp_path)
        context = result["hookSpecificOutput"]["additionalContext"]
        assert "env-config.json" in context and "fixture-simulator" not in context


class TestRtlOrchestratorInject:
    """Tests for hooks/rtl-orchestrator-inject.sh."""

    HOOK = HOOKS_DIR / "rtl-orchestrator-inject.sh"

    def test_no_marker_emits_minimal_json(self, tmp_path):
        """Without a RAT marker, the hook emits the minimal SessionStart
        envelope (and no routing block) so Claude Code's hook output schema
        is satisfied without leaking context into unrelated projects."""
        result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
        # No raw markdown output.
        assert result.get("raw_stdout", "") == ""
        # JSON envelope must declare hookEventName and carry no context.
        hso = result.get("hookSpecificOutput", {})
        assert hso.get("hookEventName") == "SessionStart"
        assert "additionalContext" not in hso

    def test_rtl_dir_alone_no_injection(self, tmp_path):
        """`rtl/` is too generic to be a RAT marker — many non-RAT repos
        contain it. Marker check must require .rat/ or .rtl-agent-team/."""
        (tmp_path / "rtl").mkdir()
        result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
        assert result.get("raw_stdout", "") == ""
        assert (
            result.get("hookSpecificOutput", {}).get("hookEventName")
            == "SessionStart"
        )

    def test_docs_dir_alone_no_injection(self, tmp_path):
        """`docs/` is too generic to be a RAT marker."""
        (tmp_path / "docs").mkdir()
        result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
        assert result.get("raw_stdout", "") == ""
        assert (
            result.get("hookSpecificOutput", {}).get("hookEventName")
            == "SessionStart"
        )

    def test_rat_marker_triggers_injection(self, tmp_path):
        """`.rat/` is the canonical RAT marker (created when any rtl-agent-team
        skill, including rat-init-project, runs at least once).

        Since v0.10.3 the hook emits a JSON envelope; routing markdown is
        delivered via `hookSpecificOutput.additionalContext`."""
        (tmp_path / ".rat").mkdir()
        result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
        hso = result.get("hookSpecificOutput", {})
        assert hso.get("hookEventName") == "SessionStart"
        output = hso.get("additionalContext", "")
        assert "# RTL Agent Team — Active Project Rules" in output
        assert "/rtl-agent-team:rat-auto-design" in output
        assert "/rtl-agent-team:rtl-p5-verify" in output
        assert "/rtl-agent-team:rtl-p6-design-review" in output

    def test_legacy_marker_triggers_injection(self, tmp_path):
        """`.rtl-agent-team/` is the legacy marker (v0.8.11 and earlier).
        Honored for backward compatibility with existing user projects.

        Since v0.10.3 the hook emits a JSON envelope; see comment in
        `test_rat_marker_triggers_injection` above."""
        (tmp_path / ".rtl-agent-team").mkdir()
        result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
        hso = result.get("hookSpecificOutput", {})
        assert hso.get("hookEventName") == "SessionStart"
        output = hso.get("additionalContext", "")
        assert "## Pipeline Rules" in output
        assert "/rtl-agent-team:p1-spec-research" in output

    @pytest.mark.parametrize("root_env", ["CLAUDE_PROJECT_DIR", "RAT_PROJECT_ROOT"])
    def test_session_away_from_the_marker_still_gets_the_rules(self, tmp_path, root_env):
        """SessionStart also fires on compaction, when the session may sit in rtl/;
        an external driver may run elsewhere and name the project in RAT_PROJECT_ROOT."""
        (tmp_path / ".rat").mkdir()
        (tmp_path / "rtl").mkdir()
        result = run_hook(self.HOOK, {"cwd": str(tmp_path / "rtl")}, env={root_env: str(tmp_path)})
        output = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "# RTL Agent Team — Active Project Rules" in output


class TestRtlEditTracker:
    """Tests for hooks/rtl-edit-tracker.sh."""

    HOOK = HOOKS_DIR / "rtl-edit-tracker.sh"

    def test_rtl_file_tracked(self, tmp_project):
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/module/top.sv"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        assert "additionalContext" in result.get("hookSpecificOutput", {})

        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert track_file.exists()
        assert "rtl/module/top.sv" in track_file.read_text()

    def test_non_rtl_file_ignored(self, tmp_project):
        stdin = {"cwd": str(tmp_project), "file_path": "docs/readme.md"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        assert "hookSpecificOutput" not in result

    def test_svh_file_tracked(self, tmp_project):
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/include/defines.svh"}
        result = run_hook(self.HOOK, stdin)
        assert "additionalContext" in result.get("hookSpecificOutput", {})

    def test_v_file_tracked(self, tmp_project):
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/legacy/module.v"}
        result = run_hook(self.HOOK, stdin)
        assert "additionalContext" in result.get("hookSpecificOutput", {})

    def test_vh_file_tracked(self, tmp_project):
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/include/header.vh"}
        result = run_hook(self.HOOK, stdin)
        assert "additionalContext" in result.get("hookSpecificOutput", {})

    def test_no_duplicate_tracking(self, tmp_project):
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/module/top.sv"}
        run_hook(self.HOOK, stdin)
        run_hook(self.HOOK, stdin)
        run_hook(self.HOOK, stdin)

        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        lines = [l for l in track_file.read_text().splitlines() if l.strip()]
        assert lines.count("rtl/module/top.sv") == 1

    def test_multiple_files_tracked(self, tmp_project):
        run_hook(self.HOOK, {"cwd": str(tmp_project), "file_path": "rtl/a.sv"})
        run_hook(self.HOOK, {"cwd": str(tmp_project), "file_path": "rtl/b.sv"})

        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        content = track_file.read_text()
        assert "rtl/a.sv" in content
        assert "rtl/b.sv" in content

    def test_py_file_ignored(self, tmp_project):
        stdin = {"cwd": str(tmp_project), "file_path": "sim/test_module.py"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        assert "hookSpecificOutput" not in result

    def test_json_file_ignored(self, tmp_project):
        stdin = {"cwd": str(tmp_project), "file_path": "config.json"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        assert "hookSpecificOutput" not in result

    def test_count_increments(self, tmp_project):
        """Verify count in message reflects actual tracked file count."""
        run_hook(self.HOOK, {"cwd": str(tmp_project), "file_path": "rtl/a.sv"})
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "file_path": "rtl/b.sv"})
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "2 unverified" in ctx  # Should show 2 tracked files

    def test_empty_file_path(self, tmp_project):
        """Empty file_path should not crash."""
        stdin = {"cwd": str(tmp_project), "file_path": ""}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True

    def test_parser_uses_top_level_file_path_key(self, tmp_project):
        raw_input = json.dumps(
            {
                "cwd": str(tmp_project),
                "file_path": "rtl/top_level.sv",
                "meta": {"file_path": "rtl/nested_should_be_ignored.sv"},
            }
        )
        result = run_hook(self.HOOK, raw_input)
        assert result["continue"] is True
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert track_file.exists()
        tracked = track_file.read_text()
        assert "rtl/top_level.sv" in tracked
        assert "rtl/nested_should_be_ignored.sv" not in tracked

    def test_new_edit_invalidates_verify_done(self, tmp_project):
        """New RTL edit must remove rtl-verify-done and rtl-verify-waiver markers."""
        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        # Simulate previous verification
        (state_dir / "rtl-verify-done").touch()
        (state_dir / "rtl-verify-waiver").touch()
        # New RTL edit
        run_hook(self.HOOK, {"cwd": str(tmp_project), "file_path": "rtl/new_module.sv"})
        assert not (state_dir / "rtl-verify-done").exists(), "verify-done must be invalidated on new RTL edit"
        assert not (state_dir / "rtl-verify-waiver").exists(), "verify-waiver must be invalidated on new RTL edit"

    def test_duplicate_edit_also_invalidates_verify_done(self, tmp_project):
        """Re-editing an already-tracked file must still invalidate verify markers."""
        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        # First edit — tracked
        run_hook(self.HOOK, {"cwd": str(tmp_project), "file_path": "rtl/existing.sv"})
        # Simulate verification
        (state_dir / "rtl-verify-done").touch()
        # Same file again — content changed, must invalidate
        run_hook(self.HOOK, {"cwd": str(tmp_project), "file_path": "rtl/existing.sv"})
        assert not (state_dir / "rtl-verify-done").exists(), "verify-done must be invalidated on any RTL edit"


class TestSessionScopedState:
    """Tests for session-scoped state isolation in team mode (Phase A)."""

    EDIT_HOOK = HOOKS_DIR / "rtl-edit-tracker.sh"
    GATE_HOOK = HOOKS_DIR / "rtl-verify-stop-gate.sh"
    SKILL_HOOK = HOOKS_DIR / "rtl-skill-activation.sh"

    def _write_team_config(self, tmp_project, leader_id="leader-session-001"):
        """Create a team-config.json in the project state dir."""

        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "team_mode": True,
            "team_name": "test-team",
            "leader_session_id": leader_id,
            "phase": "p4",
            "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        (state_dir / "team-config.json").write_text(json.dumps(config))
        _record_team_owner(tmp_project, config.get("leader_session_id", ""))

    def test_edit_tracker_session_scoped_in_team_mode(self, tmp_project):
        """In team mode with a session id, tracking file uses session suffix."""
        self._write_team_config(tmp_project)
        run_hook(
            self.EDIT_HOOK,
            {"cwd": str(tmp_project), "file_path": "rtl/mod_a.sv", "session_id": "worker-abc-123"},
        )
        state_dir = tmp_project / ".rat" / "state"
        session_file = state_dir / "rtl-modified-files-worker-abc-123.txt"
        solo_file = state_dir / "rtl-modified-files.txt"
        assert session_file.exists(), "Session-scoped file should be created"
        assert "rtl/mod_a.sv" in session_file.read_text()
        assert not solo_file.exists(), "Solo file should not be created in team mode"

    def test_edit_tracker_solo_mode_unchanged(self, tmp_project):
        """Without team config, tracking uses the solo file as before."""
        run_hook(
            self.EDIT_HOOK,
            {"cwd": str(tmp_project), "file_path": "rtl/mod_b.sv"},
        )
        state_dir = tmp_project / ".rat" / "state"
        solo_file = state_dir / "rtl-modified-files.txt"
        assert solo_file.exists()
        assert "rtl/mod_b.sv" in solo_file.read_text()

    def test_two_sessions_produce_separate_files(self, tmp_project):
        """Two different session ids write to separate tracking files."""
        self._write_team_config(tmp_project)
        run_hook(
            self.EDIT_HOOK,
            {"cwd": str(tmp_project), "file_path": "rtl/a.sv", "session_id": "session-1"},
        )
        run_hook(
            self.EDIT_HOOK,
            {"cwd": str(tmp_project), "file_path": "rtl/b.sv", "session_id": "session-2"},
        )
        state_dir = tmp_project / ".rat" / "state"
        f1 = state_dir / "rtl-modified-files-session-1.txt"
        f2 = state_dir / "rtl-modified-files-session-2.txt"
        assert f1.exists() and f2.exists()
        assert "rtl/a.sv" in f1.read_text()
        assert "rtl/b.sv" in f2.read_text()
        assert "rtl/b.sv" not in f1.read_text()
        assert "rtl/a.sv" not in f2.read_text()

    def test_verify_gate_aggregates_session_files(self, tmp_project):
        """Verify gate merges all session-scoped files for leader gate judgment."""
        self._write_team_config(tmp_project, leader_id="leader-001")
        state_dir = tmp_project / ".rat" / "state"
        # Simulate two workers' tracking files
        _track((state_dir / "rtl-modified-files-worker-1.txt"), "rtl/a.sv\n")
        _track((state_dir / "rtl-modified-files-worker-2.txt"), "rtl/b.sv\n")
        # Leader session runs the gate — must match leader_session_id
        result = run_hook(
            self.GATE_HOOK,
            {"cwd": str(tmp_project), "session_id": "leader-001"},
        )
        # Gate should block because there are unverified files
        _assert_stop_blocked(result)
        ctx = result.get("reason", "")
        # Should mention both files (aggregated)
        assert "2 RTL files" in ctx  # 2 files total

    def test_verify_gate_cleanup_removes_session_files(self, tmp_project):
        """When verify-done exists, gate cleans up all session-scoped files."""
        self._write_team_config(tmp_project, leader_id="leader-001")
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files-worker-1.txt"), "rtl/a.sv\n")
        _track((state_dir / "rtl-modified-files-worker-2.txt"), "rtl/b.sv\n")
        _record_passing_evidence(tmp_project)
        # Leader session runs the gate — must match leader_session_id
        result = run_hook(
            self.GATE_HOOK,
            {"cwd": str(tmp_project), "session_id": "leader-001"},
        )
        assert result["continue"] is True
        # All session files should be cleaned up
        assert not (state_dir / "rtl-modified-files-worker-1.txt").exists()
        assert not (state_dir / "rtl-modified-files-worker-2.txt").exists()

    def test_skill_activation_skipped_for_worker(self, tmp_project):
        """Worker sessions should skip skill state management."""
        _setup_marker(tmp_project)  # without it the hook stops at the setup check
        self._write_team_config(tmp_project, leader_id="leader-001")
        env = {"CLAUDE_PLUGIN_ROOT": str(HOOKS_DIR / "..")}
        result = run_hook(
            self.SKILL_HOOK,
            {"cwd": str(tmp_project), "hook_event_name": "PostToolUse",
             "skill": "rtl-agent-team:rtl-p5-verify", "session_id": "worker-session-99"},
            env=env,
        )
        assert result["continue"] is True
        # skill-active.json should NOT be created by worker
        skill_state = tmp_project / ".rat" / "state" / "skill-active.json"
        assert not skill_state.exists(), "Worker should not create skill-active.json"

    def test_edit_tracker_treats_an_abandoned_team_config_as_solo(self, tmp_project):
        """A config last written 3h ago is no team mode: the edit goes to the solo file,
        and the stale config is removed."""
        self._write_team_config(tmp_project, leader_id="leader-old")
        config = tmp_project / ".rat" / "state" / "team-config.json"
        three_hours_ago = time.time() - 3 * 3600
        os.utime(config, (three_hours_ago, three_hours_ago))
        run_hook(
            self.EDIT_HOOK,
            {"cwd": str(tmp_project), "file_path": "rtl/mod_a.sv", "session_id": "new-session"},
        )
        state_dir = tmp_project / ".rat" / "state"
        assert "rtl/mod_a.sv" in (state_dir / "rtl-modified-files.txt").read_text()
        assert not list(state_dir.glob("rtl-modified-files-*"))
        assert not config.exists()

    @pytest.mark.parametrize("sid", ["../escape", "\u00e9t\u00e9", "a" * 200],
                             ids=["traversal", "non-ascii", "overlong"])
    def test_edit_tracker_ignores_a_session_id_that_is_not_a_plain_token(self, tmp_project, sid):
        """The session id names a file, so anything but a short ASCII token is no session
        id. bash's A-Z range matches é in a UTF-8 locale, and a file name has at most 255
        bytes."""
        self._write_team_config(tmp_project)
        run_hook(
            self.EDIT_HOOK,
            {"cwd": str(tmp_project), "file_path": "rtl/mod_a.sv", "session_id": sid},
        )
        state_dir = tmp_project / ".rat" / "state"
        assert "rtl/mod_a.sv" in (state_dir / "rtl-modified-files.txt").read_text()
        assert not list(state_dir.glob("rtl-modified-files-*"))


class TestRtlVerifyStopGate:
    """Tests for hooks/rtl-verify-stop-gate.sh."""

    HOOK = HOOKS_DIR / "rtl-verify-stop-gate.sh"

    def test_no_tracked_files_allows_exit(self, tmp_project):
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_empty_tracking_file_allows_exit(self, tmp_project):
        track = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        _track(track, "")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_tracked_files_without_verification_blocks(self, tmp_project):
        track = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        _track(track, "rtl/module/top.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        _assert_stop_blocked(result)

    def test_verify_done_allows_exit(self, tmp_project):
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/module/top.sv\n")
        _record_passing_evidence(tmp_project)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_verify_waiver_allows_exit(self, tmp_project):
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/module/top.sv\n")
        (state_dir / "rtl-verify-waiver").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_cleanup_after_verify_done(self, tmp_project):
        state_dir = tmp_project / ".rat" / "state"
        track = state_dir / "rtl-modified-files.txt"
        done = state_dir / "rtl-verify-done"
        _track(track, "rtl/module/top.sv\n")
        done.touch()
        _record_passing_evidence(tmp_project)
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert not track.exists()
        assert not done.exists()

    def test_cleanup_after_waiver(self, tmp_project):
        state_dir = tmp_project / ".rat" / "state"
        track = state_dir / "rtl-modified-files.txt"
        waiver = state_dir / "rtl-verify-waiver"
        _track(track, "rtl/a.sv\nrtl/b.sv\n")
        waiver.touch()
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert not track.exists()
        assert not waiver.exists()

    def test_multiple_files_blocks(self, tmp_project):
        """Multiple tracked files should all be mentioned in block message."""
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/a.sv\nrtl/b.sv\nrtl/c.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        _assert_stop_blocked(result)
        ctx = result.get("reason", "")
        assert "3 RTL files" in ctx  # 3 files

    def test_fallback_file_blocks_exit(self, tmp_project):
        """Fallback entries from lock failure must block exit even without main track file."""
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files-fallback.txt"), "rtl/alu/alu.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        _assert_stop_blocked(result)
        ctx = result.get("reason", "")
        assert "1 RTL files" in ctx

    def test_fallback_merged_with_main_track(self, tmp_project):
        """Fallback and main track entries are both counted."""
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/a.sv\n")
        _track((state_dir / "rtl-modified-files-fallback.txt"), "rtl/b.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        _assert_stop_blocked(result)
        ctx = result.get("reason", "")
        assert "2 RTL files" in ctx

    def test_verify_done_cleans_fallback(self, tmp_project):
        """Verify-done should clean up fallback file too."""
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/a.sv\n")
        _track((state_dir / "rtl-modified-files-fallback.txt"), "rtl/b.sv\n")
        _record_passing_evidence(tmp_project)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True
        assert not (state_dir / "rtl-modified-files-fallback.txt").exists()

    def test_fallback_aggregated_in_team_mode(self, tmp_project):
        """In team mode, fallback file is included via glob aggregation."""

        state_dir = tmp_project / ".rat" / "state"
        config = {
            "team_mode": True,
            "team_name": "test-team",
            "leader_session_id": "leader-001",
            "phase": "p4",
            "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        (state_dir / "team-config.json").write_text(json.dumps(config))
        _record_team_owner(tmp_project, config.get("leader_session_id", ""))
        _track((state_dir / "rtl-modified-files-fallback.txt"), "rtl/c.sv\n")
        result = run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "session_id": "leader-001"},
        )
        _assert_stop_blocked(result)

    def test_verify_stop_gate_uses_shared_json_util(self):
        content = (HOOKS_DIR / "rtl-verify-stop-gate.sh").read_text()
        assert "lib/json-util.sh" in content
        assert "lib/team-gate-util.sh" in content
        assert "jsonu_get_root_string" in content
        assert "teamu_should_skip_gate" in content

    def test_block_leaves_waiver_to_the_user(self, tmp_project):
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/a.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["decision"] == "block"
        assert "touch .rat/state/rtl-verify-waiver" not in result["reason"]
        assert "rtl-verify-waiver" not in result["reason"]
        assert "rtl-modified-files" not in result["reason"]
        assert "ask the user" in result["reason"]

    def test_unchanged_content_is_informational_once_across_prompts(self, tmp_project):
        track = tmp_project / ".rat/state/rtl-modified-files.txt"
        _track(track, "rtl/a.sv\n")
        payload = {"cwd": str(tmp_project), "session_id": "owner", "prompt_id": "p1"}
        _assert_stop_blocked(run_hook(self.HOOK, payload))
        new_prompt = {**payload, "prompt_id": "p2"}
        notice = run_hook(self.HOOK, new_prompt)
        assert notice == {"systemMessage": "Info> Functional verification is pending for 1 RTL file(s)."}
        assert run_hook(self.HOOK, {**new_prompt, "stop_hook_active": True}) == {"continue": True}
        assert run_hook(self.HOOK, {**payload, "prompt_id": "p3"}) == {"continue": True}
        assert track.exists()

    def test_same_path_with_new_content_rearms_verification(self, tmp_project):
        track = tmp_project / ".rat/state/rtl-modified-files.txt"
        source = tmp_project / "rtl/a.sv"
        source.parent.mkdir()
        source.write_text("module original; endmodule\n")
        _track(track, "rtl/a.sv\n")
        payload = {"cwd": str(tmp_project)}
        _assert_stop_blocked(run_hook(self.HOOK, payload))
        chained = {**payload, "stop_hook_active": True}
        assert run_hook(self.HOOK, chained)["systemMessage"].startswith("Info>")
        source.touch()
        assert run_hook(self.HOOK, chained) == {"continue": True}
        source.write_text("module changed; endmodule\n")
        _assert_stop_blocked(run_hook(self.HOOK, chained))
        assert run_hook(self.HOOK, chained)["systemMessage"].startswith("Info>")

    def test_new_content_does_not_reset_the_chain_cap(self, tmp_project):
        track = tmp_project / ".rat/state/rtl-modified-files.txt"
        outcomes = []
        for i in range(8):
            _track(track, f"rtl/source_{i}.sv\n")
            result = run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
            outcomes.append("B" if result.get("decision") == "block" else "N" if "systemMessage" in result else "-")
        assert "".join(outcomes) == "BBBBBBNN"

    def test_worker_stop_keeps_leader_budget(self, tmp_project):
        state_dir = tmp_project / ".rat" / "state"
        config = {
            "team_mode": True,
            "team_name": "test-team",
            "leader_session_id": "leader-001",
            "phase": "p4",
            "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        (state_dir / "team-config.json").write_text(json.dumps(config))
        _record_team_owner(tmp_project, config.get("leader_session_id", ""))
        _track((state_dir / "rtl-modified-files.txt"), "rtl/a.sv\n")
        lead = {"cwd": str(tmp_project), "session_id": "leader-001"}
        run_hook(self.HOOK, lead)
        run_hook(self.HOOK, {**lead, "stop_hook_active": True})
        run_hook(self.HOOK, {"cwd": str(tmp_project), "session_id": "worker-1"})
        assert (_budget_path(state_dir, 'verify')).read_text().startswith("1\n")

    @pytest.mark.parametrize("marker", ["rtl-verify-waiver", "rtl-verify-done"])
    def test_waiver_and_done_clear_the_budget(self, tmp_project, marker):
        state_dir = tmp_project / ".rat" / "state"
        track = state_dir / "rtl-modified-files.txt"
        _track(track, "rtl/a.sv\n")
        results = [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
            for i in range(4)
        ]
        assert "systemMessage" in results[1]
        (state_dir / marker).touch()
        if marker == "rtl-verify-done":
            _record_passing_evidence(tmp_project)
        # A chained Stop, so the chain-start reset cannot be what resets the budget.
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True})
        assert result == {"continue": True}
        lines = (_budget_path(state_dir, 'verify')).read_text().split("\n")
        assert (lines[0], lines[2], lines[3]) == ("0", "5", "0")
        # The cleared gate is not left silent: a new edit in the same chain blocks.
        _track(track, "rtl/b.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True})
        assert result["decision"] == "block"

    @pytest.mark.parametrize("emptied", ["removed", "blank-lines"])
    def test_an_emptied_tracking_file_clears_the_budget(self, tmp_project, emptied):
        # The other two allow paths (no tracking file, blank lines only) clear the budget too.
        state_dir = tmp_project / ".rat" / "state"
        track = state_dir / "rtl-modified-files.txt"
        _track(track, "rtl/a.sv\n")
        results = [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
            for i in range(4)
        ]
        assert "systemMessage" in results[1]
        if emptied == "removed":
            track.unlink()
        else:
            _track(track, "\n\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True})
        assert result == {"continue": True}
        lines = (_budget_path(state_dir, 'verify')).read_text().split("\n")
        assert (lines[0], lines[2], lines[3]) == ("0", "5", "0")
        _track(track, "rtl/b.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True})
        assert result["decision"] == "block"

    def test_legacy_project_notice_uses_resolved_path(self, tmp_legacy_project):
        state_dir = tmp_legacy_project / ".rtl-agent-team" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/a.sv\n")
        results = [
            run_hook(self.HOOK, {"cwd": str(tmp_legacy_project), "stop_hook_active": i > 0})
            for i in range(4)
        ]
        notice = results[1]["systemMessage"]
        assert notice == "Info> Functional verification is pending for 1 RTL file(s)."
        assert str(state_dir / "verify-evidence.json") in results[0]["reason"]

    def test_file_list_is_relative_and_deduplicated(self, tmp_project):
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"),
            f"rtl/a.sv\n{tmp_project}/rtl/a.sv\n./rtl/a.sv\nrtl/b.sv\n"
        )
        reason = run_hook(self.HOOK, {"cwd": str(tmp_project)})["reason"]
        assert "2 RTL files" in reason
        assert "rtl/a.sv, rtl/b.sv" in reason

    def test_file_list_is_relative_to_the_project_root(self, tmp_project):
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"),
            f"{tmp_project}/rtl/a.sv\n"
        )
        elsewhere = tmp_project / "elsewhere"
        elsewhere.mkdir()
        reason = run_hook(
            self.HOOK, {"cwd": str(elsewhere)}, env={"RAT_PROJECT_ROOT": str(tmp_project)}
        )["reason"]
        assert "rtl/a.sv" in reason
        assert f"{tmp_project}/rtl/a.sv" not in reason

    def test_blank_tracking_file_allows_exit(self, tmp_project):
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"), "\n\n")
        assert run_hook(self.HOOK, {"cwd": str(tmp_project)}) == {"continue": True}

    def test_file_list_shows_ten_files_and_counts_the_rest(self, tmp_project):
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"),
            "".join(f"rtl/m{i:02d}.sv\n" for i in range(12))
        )
        reason = run_hook(self.HOOK, {"cwd": str(tmp_project)})["reason"]
        assert "12 RTL files" in reason
        assert ", and 2 more" in reason

    def test_fallback_duplicate_mid_chain_keeps_the_count(self, tmp_project):
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/a.sv\n")
        results = [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
            for i in range(2)
        ]
        # The same file again, recorded by the lock-failure fallback in absolute form.
        _track((state_dir / "rtl-modified-files-fallback.txt"), f"{tmp_project}/rtl/a.sv\n")
        results += [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True})
            for _ in range(2)
        ]
        assert results[0]["decision"] == "block"
        assert results[1]["systemMessage"].startswith("Info>")
        assert results[2:] == [{"continue": True}] * 2

    def test_commands_survive_a_quote_in_the_project_path(self, tmp_path):
        project = tmp_path / "o'brien"
        state_dir = project / ".rat" / "state"
        state_dir.mkdir(parents=True)
        _track((state_dir / "rtl-modified-files.txt"), "rtl/a.sv\n")
        results = [
            run_hook(self.HOOK, {"cwd": str(project), "stop_hook_active": i > 0})
            for i in range(4)
        ]
        assert results[1]["systemMessage"].startswith("Info>")
        assert not (state_dir / "rtl-verify-waiver").exists()
        assert str(state_dir / "verify-evidence.json") in results[0]["reason"].replace("'\\''", "'")
        assert "record it: touch" not in results[0]["reason"]

    def test_allowed_stops_count_toward_the_chain_cap(self, tmp_project):
        state = tmp_project / ".rat" / "state"
        # A budget written earlier for this prompt; allowed Stops must still count, or
        # Stop 7 would trust it. Inputs carry a prompt_id, as production Stops do.
        (_budget_path(state, 'verify')).write_text("0\n\n1\n0\np-1\n")
        for i in range(6):
            stop = {"cwd": str(tmp_project), "stop_hook_active": i > 0, "prompt_id": "p-1"}
            assert run_hook(self.HOOK, stop) == {"continue": True}
        _track((state / "rtl-modified-files.txt"), "rtl/a.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True, "prompt_id": "p-1"})
        assert "decision" not in result
        assert result["systemMessage"].startswith("Info>")

    def test_signal_mid_aggregation_ends_the_gate_after_cleanup(self, tmp_project):
        state = tmp_project / ".rat" / "state"
        # A worker's tracking file makes the gate aggregate through `sort`.
        _track((state / "rtl-modified-files-worker-1.txt"), "rtl/a.sv\n")
        shim = tmp_project / "shim"
        shim.mkdir()
        ready, hold = tmp_project / "sort-started", tmp_project / "hold"
        os.mkfifo(hold)
        # The shim reports that the gate reached `sort`, then blocks on the FIFO.
        (shim / "sort").write_text('#!/bin/sh\n: > "$RAT_TEST_READY"\nread _ < "$RAT_TEST_HOLD"\n')
        (shim / "sort").chmod(0o755)
        env = {**os.environ, "PATH": f"{shim}:{os.environ['PATH']}",
               "RAT_TEST_READY": str(ready), "RAT_TEST_HOLD": str(hold)}
        gate = subprocess.Popen(
            ["sh", str(self.HOOK)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=env, text=True, start_new_session=True,
        )
        try:
            gate.stdin.write(json.dumps({"cwd": str(tmp_project)}))
            gate.stdin.close()
            deadline = time.monotonic() + 10
            while not ready.exists():
                assert time.monotonic() < deadline, "the gate never reached the aggregation"
                time.sleep(0.01)
            os.killpg(gate.pid, signal.SIGTERM)
            out = gate.stdout.read()
            rc = gate.wait(timeout=10)
        finally:
            if gate.poll() is None:
                os.killpg(gate.pid, signal.SIGKILL)
                gate.wait()
        assert rc == 143
        assert out == ""
        assert not list(state.glob("rtl-modified-files-aggregated.*"))

    def test_gate_blocks_while_the_session_is_in_a_subdirectory(self, tmp_project):
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"), "rtl/a.sv\n")
        (tmp_project / "sim").mkdir(exist_ok=True)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project / "sim")},
                          env={"CLAUDE_PROJECT_DIR": str(tmp_project)})
        _assert_stop_blocked(result)
        assert "a.sv" in result["reason"]

    def test_stray_marker_in_a_subdirectory_cannot_waive_verification(self, tmp_project):
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"), "rtl/a.sv\n")
        stray = tmp_project / "rtl" / ".rat" / "state"
        stray.mkdir(parents=True)
        (stray / "rtl-verify-done").touch()  # `touch .rat/state/rtl-verify-done` run from rtl/
        result = run_hook(self.HOOK, {"cwd": str(tmp_project / "rtl")},
                          env={"CLAUDE_PROJECT_DIR": str(tmp_project)})
        _assert_stop_blocked(result)


class TestVerifyGateModes:
    """verification.stop_gate selects block (default), notify or off."""

    HOOK = HOOKS_DIR / "rtl-verify-stop-gate.sh"

    def _pending(self, project, project_mode=None, machine_mode=None):
        _track(project / ".rat/state/rtl-modified-files.txt", "rtl/a.sv\n")
        if project_mode is not None:
            (project / "rat_config.json").write_text(json.dumps({"verification": {"stop_gate": project_mode}}))
        if machine_mode is not None:
            (Path(os.environ["RAT_DATA_DIR"]) / "env-config.json").write_text(
                json.dumps({"verification": {"stop_gate": machine_mode}}))
        return {"cwd": str(project), "prompt_id": "p1"}

    def test_default_blocks_and_names_the_project_runner_route(self, tmp_project):
        result = run_hook(self.HOOK, self._pending(tmp_project))
        _assert_stop_blocked(result)
        assert "eda_runner.py' verify-run" in result["reason"] and "--remote-host" in result["reason"]

    def test_notify_shows_one_notice_and_never_blocks(self, tmp_project):
        stop = self._pending(tmp_project, "notify")
        assert run_hook(self.HOOK, stop) == {"systemMessage": "Info> Functional verification is pending for "
                                             "1 RTL file(s) (verification.stop_gate=notify)."}
        assert run_hook(self.HOOK, {**stop, "prompt_id": "p2"}) == {"continue": True}
        assert (tmp_project / ".rat/state/rtl-modified-files.txt").exists()

    def test_notify_still_clears_verified_files(self, tmp_project):
        stop = self._pending(tmp_project, "notify")
        _record_passing_evidence(tmp_project)
        assert run_hook(self.HOOK, stop) == {"continue": True}
        assert not (tmp_project / ".rat/state/rtl-modified-files.txt").exists()

    def test_off_is_silent_and_block_resumes_the_pending_files(self, tmp_project):
        stop = self._pending(tmp_project, "off")
        assert run_hook(self.HOOK, stop) == {"continue": True}
        assert (tmp_project / ".rat/state/rtl-modified-files.txt").exists()
        (tmp_project / "rat_config.json").write_text(json.dumps({"verification": {"stop_gate": "block"}}))
        _assert_stop_blocked(run_hook(self.HOOK, {**stop, "prompt_id": "p2"}))

    def test_returning_from_notify_to_block_blocks_the_notified_files(self, tmp_project):
        stop = self._pending(tmp_project, "notify")
        assert "systemMessage" in run_hook(self.HOOK, stop)
        (tmp_project / "rat_config.json").write_text(json.dumps({"verification": {"stop_gate": "block"}}))
        _assert_stop_blocked(run_hook(self.HOOK, {**stop, "prompt_id": "p2"}))

    def test_unknown_mode_blocks_and_names_the_value(self, tmp_project):
        result = run_hook(self.HOOK, self._pending(tmp_project, "relaxed"))
        _assert_stop_blocked(result)
        assert "relaxed" in result["reason"] and "block, notify or off" in result["reason"]

    def test_machine_setting_applies_without_project_config(self, tmp_project):
        assert run_hook(self.HOOK, self._pending(tmp_project, machine_mode="off")) == {"continue": True}

    def test_project_config_owns_the_setting(self, tmp_project):
        _assert_stop_blocked(run_hook(self.HOOK, self._pending(tmp_project, "block", machine_mode="off")))


class TestStopGate:
    """Tests for hooks/stop-gate.sh."""

    HOOK = HOOKS_DIR / "stop-gate.sh"
    LOOP_STATE = {"ultraloop": "ultraloop-state.json", "ppa-loop": "ppa-loop-state.json"}
    # How each stopu_gate site starts its reason (block sites) or its notice (notice sites).
    SITE_PREFIX = {
        "ultraloop": "[Ultraloop] auto-continue:",
        "ppa-loop": "[PPA-Opt loop] auto-continue:",
        "upper-spec": "[RAT Auto-Design STOP] Upper-spec violation",
        "user-decision": "[RAT Auto-Design Loop p4-gate] The gate needs your decision",
        "ladder": "[RAT Auto-Design Loop p4-gate] repair work",
    }

    def _write_autopilot_state(self, tmp_project, payload):
        state_file = tmp_project / ".rat" / "state" / "rat-auto-design-state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(payload, indent=2))
        return state_file

    def _write_ladder(self, tmp_project, **control):
        """An in-progress run at gate p4-gate (N=2, one primary attempt), with overrides."""
        control = {"active_gate_id": "p4-gate", "active_gate_retry_limit": 2,
                   "active_gate_primary_attempts": 1, "needs_user_decision": False, **control}
        return self._write_autopilot_state(
            tmp_project, {"status": "in_progress", "orchestration_control": control})

    def _write_loop(self, tmp_project, loop, ts, minutes=30):
        path = tmp_project / ".rat" / "state" / self.LOOP_STATE[loop]
        path.write_text(json.dumps(
            {"mode": loop, "last_cycle_timestamp": ts, "auto_continue_minutes": minutes}))
        return path

    def _stops(self, project, actives):
        """Run one Stop per stop_hook_active value and return the outputs."""
        return [run_hook(self.HOOK, {"cwd": str(project), "stop_hook_active": a}) for a in actives]

    def test_no_state_file_allows_exit(self, tmp_project):
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_legacy_state_file_migrated_and_blocks(self, tmp_project):
        """Pre-0.6.10 state file (rtl-autopilot-state.json) should be migrated and still block exit."""
        legacy_file = tmp_project / ".rat" / "state" / "rtl-autopilot-state.json"
        legacy_file.parent.mkdir(parents=True, exist_ok=True)
        legacy_file.write_text(json.dumps({"phase": 3}))
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        _assert_stop_blocked(result)
        # Legacy file should have been migrated to new name
        new_file = tmp_project / ".rat" / "state" / "rat-auto-design-state.json"
        assert new_file.exists()
        assert not legacy_file.exists()

    def test_legacy_and_new_both_exist_preserves_new(self, tmp_project):
        """When both legacy and new state files exist, new file wins (legacy is not moved)."""
        # Write new state first (completed)
        self._write_autopilot_state(tmp_project, {"status": "completed"})
        # Write legacy state (active run)
        legacy_file = tmp_project / ".rat" / "state" / "rtl-autopilot-state.json"
        legacy_file.write_text(json.dumps({"phase": 3}))
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        # New file says completed → should allow exit (legacy must not overwrite)
        assert result["continue"] is True
        # New file should be unchanged
        new_file = tmp_project / ".rat" / "state" / "rat-auto-design-state.json"
        new_data = json.loads(new_file.read_text())
        assert new_data["status"] == "completed"

    def test_state_file_exists_blocks_exit(self, tmp_project):
        self._write_autopilot_state(tmp_project, {"phase": 3})
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        _assert_stop_blocked(result)
        assert "Auto-Design" in result.get("reason", "")

    def test_completed_state_allows_exit(self, tmp_project):
        self._write_autopilot_state(tmp_project, {"status": "completed"})
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_primary_range_message(self, tmp_project):
        self._write_autopilot_state(
            tmp_project,
            {
                "status": "in_progress",
                "orchestration_control": {
                    "active_gate_id": "p2-quality-gate",
                    "active_gate_retry_limit": 2,
                    "active_gate_primary_attempts": 1,
                    "active_gate_fallback_attempts": 0,
                    "active_gate_last_chance_attempts": 0,
                    "active_gate_strategy": "primary",
                    "needs_user_decision": False
                }
            },
        )
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        _assert_stop_blocked(result)
        ctx = result.get("reason", "")
        assert "repair work" in ctx
        assert "p2-quality-gate" in ctx



    def test_user_decision_message(self, tmp_project):
        self._write_autopilot_state(
            tmp_project,
            {
                "status": "in_progress",
                "orchestration_control": {
                    "active_gate_id": "p5-final-gate",
                    "active_gate_retry_limit": 2,
                    "active_gate_primary_attempts": 4,
                    "active_gate_fallback_attempts": 2,
                    "active_gate_last_chance_attempts": 1,
                    "active_gate_strategy": "user_escalated",
                    "needs_user_decision": True,
                    "dynamic_prompt_text": "Ask user to approve rollback to phase 3."
                }
            },
        )
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert "decision" not in result
        notice = result["systemMessage"]
        assert "Ask user" in notice or "user" in notice.lower()

    def test_nested_orchestration_control_fields_take_precedence(self, tmp_project):
        """Nested orchestration_control values must win over same-name top-level keys."""
        self._write_autopilot_state(
            tmp_project,
            {
                "status": "in_progress",
                "active_gate_id": "top-level-incorrect",
                "active_gate_primary_attempts": 99,
                "orchestration_control": {
                    "active_gate_id": "p3-quality-gate",
                    "active_gate_retry_limit": 2,
                    "active_gate_primary_attempts": 1,
                    "active_gate_fallback_attempts": 0,
                    "active_gate_last_chance_attempts": 0,
                    "active_gate_strategy": "primary",
                    "needs_user_decision": False
                }
            },
        )
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        _assert_stop_blocked(result)
        ctx = result.get("reason", "")
        assert "p3-quality-gate" in ctx
        assert "primary=1" in ctx

    def test_stop_gate_uses_shared_json_util(self):
        content = (HOOKS_DIR / "stop-gate.sh").read_text()
        assert "lib/json-util.sh" in content
        assert "jsonu_get_file_path_string" in content
        assert "jsonu_get_file_path_bool" in content
        assert "jsonu_get_file_path_num" in content

    def test_upper_spec_violation_hands_decision_to_user(self, tmp_project):
        self._write_autopilot_state(
            tmp_project, {"status": "in_progress", "upper_spec_blocking": True}
        )
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert "decision" not in result
        assert "Upper-spec violation" in result["systemMessage"]
        # Once per chain: a chained Stop stays silent.
        assert run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True}) == {"continue": True}

    def test_ladder_without_progress_pauses_in_chain(self, tmp_project):
        self._write_autopilot_state(
            tmp_project,
            {
                "status": "in_progress",
                "orchestration_control": {
                    "active_gate_id": "p4-gate",
                    "active_gate_retry_limit": 2,
                    "active_gate_primary_attempts": 1,
                    "needs_user_decision": False,
                },
            },
        )
        results = [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
            for i in range(4)
        ]
        assert [r.get("decision") for r in results[:3]] == ["block"] * 3
        assert "paused" in results[3]["systemMessage"]

    def test_ultraloop_blocks_while_cycles_advance(self, tmp_project):
        state = tmp_project / ".rat" / "state" / "ultraloop-state.json"

        def write(ts):
            state.write_text(json.dumps(
                {"mode": "ultraloop", "last_cycle_timestamp": ts, "auto_continue_minutes": 30}
            ))

        now = int(time.time())
        write(now)
        for i in range(2):
            chained = run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
            assert chained["decision"] == "block"
        write(now + 1)
        results = [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True})
            for _ in range(4)
        ]
        assert [r.get("decision") for r in results[:3]] == ["block"] * 3
        assert "paused" in results[3]["systemMessage"]

    def test_ultraloop_pause_holds_until_the_next_message(self, tmp_project):
        state = tmp_project / ".rat" / "state" / "ultraloop-state.json"
        now = int(time.time())
        state.write_text(json.dumps(
            {"mode": "ultraloop", "last_cycle_timestamp": now, "auto_continue_minutes": 30}))
        for i in range(4):
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
        state.write_text(json.dumps(
            {"mode": "ultraloop", "last_cycle_timestamp": now + 1, "auto_continue_minutes": 30}))
        assert run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True}) == {"continue": True}
        assert run_hook(self.HOOK, {"cwd": str(tmp_project)})["decision"] == "block"

    def test_new_chain_after_notice_blocks_again(self, tmp_project):
        self._write_autopilot_state(
            tmp_project,
            {"status": "in_progress", "orchestration_control": {"active_gate_id": "p4-gate",
             "active_gate_retry_limit": 2, "active_gate_primary_attempts": 1,
             "needs_user_decision": False}},
        )
        for i in range(5):
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
        assert run_hook(self.HOOK, {"cwd": str(tmp_project)})["decision"] == "block"

    def test_worker_stop_keeps_leader_budget(self, tmp_project):
        state = tmp_project / ".rat" / "state"
        (state / "team-config.json").write_text(json.dumps(
            {"team_mode": True, "leader_session_id": "leader-001"}))
        _record_team_owner(tmp_project, "leader-001")
        self._write_autopilot_state(
            tmp_project,
            {"status": "in_progress", "orchestration_control": {"active_gate_id": "p4-gate",
             "active_gate_retry_limit": 2, "active_gate_primary_attempts": 1,
             "needs_user_decision": False}},
        )
        lead = {"cwd": str(tmp_project), "session_id": "leader-001"}
        run_hook(self.HOOK, lead)
        run_hook(self.HOOK, {**lead, "stop_hook_active": True})
        run_hook(self.HOOK, {"cwd": str(tmp_project), "session_id": "worker-1"})
        assert (_budget_path(state, 'autopilot')).read_text().startswith("2\n")

    def test_allowed_stops_count_toward_the_chain_cap(self, tmp_project):
        # An earlier chain left this gate's budget; another hook then kept a new chain
        # going for six Stops while this gate allowed them.
        (_budget_path(tmp_project / ".rat" / "state", 'autopilot')).write_text("0\n\n1\n0\np-1\n")
        stop = {"cwd": str(tmp_project), "prompt_id": "p-1"}  # production Stops carry a prompt id
        for i in range(6):
            assert run_hook(self.HOOK, {**stop, "stop_hook_active": i > 0}) == {"continue": True}
        self._write_autopilot_state(
            tmp_project,
            {"status": "in_progress", "orchestration_control": {"active_gate_id": "p4-gate",
             "active_gate_retry_limit": 2, "active_gate_primary_attempts": 1,
             "needs_user_decision": False}},
        )
        result = run_hook(self.HOOK, {**stop, "stop_hook_active": True})
        assert "decision" not in result
        assert "paused" in result["systemMessage"]

    def test_ppa_loop_blocks_while_cycles_advance(self, tmp_project):
        state = tmp_project / ".rat" / "state" / "ppa-loop-state.json"

        def write(ts):
            state.write_text(json.dumps(
                {"mode": "ppa-loop", "last_cycle_timestamp": ts, "auto_continue_minutes": 30}
            ))

        now = int(time.time())
        write(now)
        for i in range(2):
            chained = run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
            assert chained["decision"] == "block"
            assert chained["reason"].startswith("[PPA-Opt loop] auto-continue:")
        write(now + 1)
        results = [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True})
            for _ in range(4)
        ]
        assert [r.get("decision") for r in results[:3]] == ["block"] * 3
        assert results[3]["systemMessage"].startswith("[PPA-Opt loop] The loop is paused")

    def test_ppa_loop_pause_holds_until_the_next_message(self, tmp_project):
        state = tmp_project / ".rat" / "state" / "ppa-loop-state.json"
        now = int(time.time())
        state.write_text(json.dumps(
            {"mode": "ppa-loop", "last_cycle_timestamp": now, "auto_continue_minutes": 30}))
        for i in range(4):
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
        state.write_text(json.dumps(
            {"mode": "ppa-loop", "last_cycle_timestamp": now + 1, "auto_continue_minutes": 30}))
        assert run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True}) == {"continue": True}
        assert run_hook(self.HOOK, {"cwd": str(tmp_project)})["decision"] == "block"

    @pytest.mark.parametrize("loop", ["ultraloop", "ppa-loop"])
    def test_loop_notice_command_ends_the_loop_in_a_quoted_path(self, tmp_path, loop):
        project = tmp_path / "o'brien"
        (project / ".rat" / "state").mkdir(parents=True)
        loop_state = self._write_loop(project, loop, int(time.time()))
        results = self._stops(project, [False, True, True, True])
        assert [r.get("decision") for r in results[:3]] == ["block"] * 3
        notice = results[3]["systemMessage"]
        name = {"ultraloop": "[Ultraloop]", "ppa-loop": "[PPA-Opt loop]"}[loop]
        assert notice.startswith(f"{name} The loop is paused: automatic continuation stopped for this turn."
                                 " Say continue to resume, or end the loop: rm ")
        assert notice.endswith(f"{loop_state.name}'")  # the command comes last and can be copied as is
        before = set(tmp_path.rglob("*"))
        subprocess.run(["sh", "-c", notice.split("end the loop: ", 1)[1]], check=True, cwd=tmp_path)
        assert set(tmp_path.rglob("*")) == before - {loop_state}  # exactly the loop state is gone
        # The loop has ended, so the chain's next Stop lets Claude stop.
        assert self._stops(project, [True]) == [{"continue": True}]

    @pytest.mark.parametrize("loop", ["ultraloop", "ppa-loop"])
    def test_allowed_stops_count_toward_the_loop_chain_cap(self, tmp_project, loop):
        # As for the autopilot: another hook kept a new chain going for six Stops while
        # this gate allowed them, and then the loop started.
        (tmp_project / ".rat" / "state" / f"stop-budget-{loop}.txt").write_text("0\n\n1\n0\np-1\n")
        stop = {"cwd": str(tmp_project), "prompt_id": "p-1"}
        for i in range(6):
            assert run_hook(self.HOOK, {**stop, "stop_hook_active": i > 0}) == {"continue": True}
        self._write_loop(tmp_project, loop, int(time.time()))
        result = run_hook(self.HOOK, {**stop, "stop_hook_active": True})
        assert "decision" not in result
        assert "The loop is paused" in result["systemMessage"]

    @pytest.mark.parametrize("site", ["ultraloop", "ppa-loop"])
    def test_progress_on_every_stop_still_hands_over_at_the_chain_cap(self, tmp_project, site):
        now = int(time.time())
        results = []
        for i in range(8):
            if site == "ladder":
                self._write_ladder(tmp_project, active_gate_primary_attempts=i)  # an attempt every Stop
            else:
                self._write_loop(tmp_project, site, now + i)  # a new cycle every Stop
            results += self._stops(tmp_project, [i > 0])
        assert [r.get("decision") for r in results[:6]] == ["block"] * 6
        assert "paused" in results[6]["systemMessage"]
        assert results[7] == {"continue": True}

    @pytest.mark.parametrize("loop", ["ultraloop", "ppa-loop"])
    @pytest.mark.parametrize("offset,minutes", [(-31 * 60, 30), (3600, 0)])
    def test_a_loop_outside_its_window_does_not_block(self, tmp_project, loop, offset, minutes):
        # A future timestamp counts as 0 seconds elapsed, so a 0-minute window pins the
        # boundary: as much time elapsed as the window allows is outside the window.
        self._write_loop(tmp_project, loop, int(time.time()) + offset, minutes=minutes)
        assert run_hook(self.HOOK, {"cwd": str(tmp_project)}) == {"continue": True}

    @pytest.mark.parametrize("loop", ["ultraloop", "ppa-loop"])
    def test_a_loop_inside_its_window_blocks(self, tmp_project, loop):
        # Five minutes into a 30-minute window: the window is counted in minutes, not seconds.
        self._write_loop(tmp_project, loop, int(time.time()) - 300, minutes=30)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["decision"] == "block"
        assert "(threshold=1800s)" in result["reason"]

    def test_upper_spec_notice_tells_the_user_what_to_decide(self, tmp_project):
        self._write_autopilot_state(tmp_project, {'status':'in_progress','upper_spec_blocking':True})
        notice=run_hook(self.HOOK, {'cwd':str(tmp_project)})['systemMessage']
        assert 'Upper-spec violation' in notice
        assert 'amend the requirement or repair the design' in notice
        assert notice.endswith('Tell Claude how to proceed.')

    def test_user_decision_shows_once_per_chain(self, tmp_project):
        # The orchestrator's contract: once the last chance fails, it records needs_user_decision.
        self._write_ladder(tmp_project, needs_user_decision=True)
        results=self._stops(tmp_project,[False,True,True])
        assert results[0].get('systemMessage')
        assert results[1:]==[{'continue':True},{'continue':True}]

    @pytest.mark.parametrize("primary,fallback,last_chance,strategy", [
        (1, 0, 0, "primary"), (3, 0, 0, "fallback"), (3, 2, 0, "last_chance"), (3, 2, 1, "user_escalated"),
    ])
    def test_user_decision_notice_holds_at_every_stage(self, tmp_project, primary, fallback, last_chance,
                                                       strategy):
        # The orchestrator may ask at any ladder stage. The user reads this notice, so none of
        # the stage's instructions to Claude may reach it.
        self._write_ladder(tmp_project, active_gate_primary_attempts=primary,
            active_gate_fallback_attempts=fallback, active_gate_last_chance_attempts=last_chance,
            needs_user_decision=True, dynamic_prompt_text='Pick a strategy')
        notice=run_hook(self.HOOK, {'cwd':str(tmp_project)})['systemMessage']
        assert 'needs your decision' in notice
        assert 'Orchestrator note: Pick a strategy.' in notice
        assert notice.endswith('Tell Claude how to proceed.')

    def test_exhausted_ladder_hands_the_decision_to_the_user(self, tmp_project):
        # N=2 and the last chance is used: the gate escalates on its own.
        self._write_ladder(tmp_project,active_gate_primary_attempts=2)
        results=self._stops(tmp_project,[False,True])
        assert 'two measured repair cycles' in results[0]['systemMessage']
        assert results[1]=={'continue':True}

    @pytest.mark.parametrize("prompt", ["Approve rollback to phase 3?", ""])
    def test_decision_notice_ends_with_the_users_action(self, tmp_project, prompt):
        # The user's action comes last; the orchestrator's note is labelled only when there is one.
        self._write_ladder(tmp_project, active_gate_primary_attempts=2, active_gate_fallback_attempts=2,
                           active_gate_last_chance_attempts=1, needs_user_decision=True,
                           dynamic_prompt_text=prompt)
        notice = run_hook(self.HOOK, {"cwd": str(tmp_project)})["systemMessage"]
        assert notice.endswith(" Tell Claude how to proceed.")
        assert ("Orchestrator note:" in notice) is bool(prompt)

    @pytest.mark.parametrize("note,shown", [
        ("Approve rollback to phase 3", "Approve rollback to phase 3."),
        ("Approve rollback to phase 3?", "Approve rollback to phase 3?"),
        ("Rollback approved by review (see report)", "Rollback approved by review (see report)."),
    ])
    def test_decision_note_ends_as_a_sentence(self, tmp_project, note, shown):
        # The note is the orchestrator's own text; without final punctuation it would run
        # into the user's action.
        self._write_ladder(tmp_project, needs_user_decision=True, dynamic_prompt_text=note)
        notice = run_hook(self.HOOK, {"cwd": str(tmp_project)})["systemMessage"]
        assert notice.endswith(f" Orchestrator note: {shown} Tell Claude how to proceed.")

    def test_no_output_uses_the_old_suggested_context_label(self, tmp_project):
        # One Stop at each ladder stage, all with a dynamic prompt: the decision notice, the
        # fallback and last-chance reasons, and the notice once the ladder is used up.
        self._write_ladder(tmp_project,active_gate_primary_attempts=2,dynamic_prompt_text='Approve rollback?')
        result=run_hook(self.HOOK,{'cwd':str(tmp_project)})
        assert result.get('systemMessage')
        assert 'Suggested context' not in json.dumps(result)

    def test_ladder_pause_notice_holds_for_the_chain(self, tmp_project):
        self._write_ladder(tmp_project,active_gate_primary_attempts=1)
        results=self._stops(tmp_project,[False,True,True,True,True])
        assert results[3].get('systemMessage')
        assert results[4]=={'continue':True}


    def test_prompt_rewrite_without_an_attempt_is_not_progress(self, tmp_project):
        self._write_ladder(tmp_project,active_gate_primary_attempts=1,dynamic_prompt_text='first note')
        first=self._stops(tmp_project,[False,True])
        self._write_ladder(tmp_project,active_gate_primary_attempts=1,dynamic_prompt_text='second note')
        rest=self._stops(tmp_project,[True,True])
        assert [r.get('decision') for r in first+rest[:1]]==['block']*3
        assert rest[1].get('systemMessage')


    def test_a_run_as_old_as_the_stale_bound_is_abandoned(self, tmp_project):
        run_state = self._write_ladder(tmp_project)
        future = time.time() + 3600
        os.utime(run_state, (future, future))  # a future mtime counts as 0 seconds old
        stale = run_hook(self.HOOK, {"cwd": str(tmp_project)}, env={"RAT_STOP_STALE_SECONDS": "0"})
        assert stale == {"continue": True}
        assert run_hook(self.HOOK, {"cwd": str(tmp_project)})["decision"] == "block"  # the 2h default

    @pytest.mark.parametrize("exit_path", ["no_state", "stale_state", "completed"])
    @pytest.mark.parametrize("site", ["ultraloop", "ppa-loop", "upper-spec", "user-decision", "ladder"])
    def test_satisfied_gate_is_not_left_silent(self, tmp_project, site, exit_path):
        state = tmp_project / ".rat" / "state"
        run_state = state / "rat-auto-design-state.json"
        loop = site in self.LOOP_STATE
        notice_only = site in ("upper-spec", "user-decision")  # limit 0: the notice, then silence

        def start():  # the site's condition holds
            if loop:
                self._write_loop(tmp_project, site, int(time.time()))
            elif site == "upper-spec":
                self._write_autopilot_state(tmp_project, {"status": "in_progress", "upper_spec_blocking": True})
            else:
                self._write_ladder(tmp_project, needs_user_decision=site == "user-decision")

        start()
        results = self._stops(tmp_project, [False, True, True, True])
        assert "systemMessage" in results[0 if notice_only else 3]
        # The gate is satisfied, and the chain's next Stop leaves through this exit.
        if loop:
            (state / self.LOOP_STATE[site]).unlink()
        if exit_path == "no_state":
            run_state.unlink(missing_ok=True)
        elif exit_path == "stale_state":
            if not run_state.exists():
                self._write_ladder(tmp_project)
            os.utime(run_state, (1000, 1000))  # abandoned long ago
        else:
            self._write_autopilot_state(tmp_project, {"status": "completed"})
        # A chained Stop, so the chain-start reset cannot be what clears the budget.
        assert self._stops(tmp_project, [True]) == [{"continue": True}]
        budget = state / f"stop-budget-{site if loop else 'autopilot'}.txt"
        lines = budget.read_text().split("\n")
        assert (lines[0], lines[2], lines[3]) == ("0", "5", "0")
        start()  # the same condition comes back later in this chain
        again = self._stops(tmp_project, [True])[0]
        if notice_only:
            assert again["systemMessage"].startswith(self.SITE_PREFIX[site])  # its notice again, not silence
        else:
            assert again["decision"] == "block"
            assert again["reason"].startswith(self.SITE_PREFIX[site])


class TestRtlEditTrackerBash:
    HOOK = HOOKS_DIR / "rtl-edit-tracker.sh"

    def execute(self, project, command, cwd=None):
        folder = cwd or project
        payload = {"cwd": str(folder), "session_id": "author", "tool_use_id": "tool-fixture",
                   "tool_name": "Bash", "tool_input": {"command": command}}
        env = {"CLAUDE_PROJECT_DIR": str(project)}
        assert run_hook(self.HOOK, {**payload, "hook_event_name": "PreToolUse"}, env=env) == {"continue": True}
        process = subprocess.run(["bash", "-c", command], cwd=folder, capture_output=True, timeout=10)
        event = "PostToolUseFailure" if process.returncode else "PostToolUse"
        assert run_hook(self.HOOK, {**payload, "hook_event_name": event}, env=env) == {"continue": True}
        track = project / ".rat/state/rtl-modified-files.txt"
        return track.read_text().splitlines() if track.exists() else []

    @pytest.fixture
    def project_sources(self, tmp_project):
        for name in ("rtl/top.sv", "rtl/second.sv", "syn/netlist.v", "sim/build/model.v"):
            path = tmp_project / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("module old; endmodule\n")
        return tmp_project

    @pytest.mark.parametrize("command", [
        "sed -n '1p' rtl/top.sv && cat rtl/second.sv",
        "find rtl -name '*.sv'",
        "find syn -name '*.v' && wc -l syn/netlist.v",
        "cp rtl/top.sv syn/new.v && cp rtl/second.sv sim/build/next.v",
        "touch rtl/top.sv",
        "cat rtl/top.sv > read.log; false",
    ])
    def test_read_and_build_output_do_not_track(self, project_sources, command):
        assert self.execute(project_sources, command) == []
        assert run_hook(HOOKS_DIR / "rtl-verify-stop-gate.sh", {"cwd": str(project_sources)}) == {"continue": True}

    @pytest.mark.parametrize("command,expected", [
        ("grep module rtl/top.sv && printf 'module edited; endmodule' > rtl/second.sv", ["rtl/second.sv"]),
        ("cp -r rtl another_source_dir", ["another_source_dir/second.sv", "another_source_dir/top.sv"]),
        ("cp rtl/top.sv 'rtl/space name.svh'", ["rtl/space name.svh"]),
        ("rm rtl/top.sv", ["rtl/top.sv"]),
        ("printf 'module edited; endmodule' > rtl/top.sv; false", ["rtl/top.sv"]),
    ])
    def test_detects_only_content_changes_even_after_tool_failure(self, project_sources, command, expected):
        state = project_sources / ".rat/state"
        waiver = state / "rtl-verify-waiver"
        waiver.touch()
        assert self.execute(project_sources, command) == expected
        assert not waiver.exists()

    def test_deduplicates_changes_from_a_subdirectory(self, project_sources):
        for module in ("first", "second"):
            assert self.execute(project_sources, f"printf 'module {module}; endmodule' > ./top.sv",
                                cwd=project_sources / "rtl") == ["rtl/top.sv"]

    def test_identical_write_is_quiet(self, project_sources):
        path = project_sources / "rtl/top.sv"
        payload = {"cwd": str(project_sources), "tool_name": "Write", "tool_use_id": "tool-noop",
                   "tool_input": {"file_path": str(path)}}
        run_hook(self.HOOK, {**payload, "hook_event_name": "PreToolUse"})
        path.write_bytes(path.read_bytes())
        assert run_hook(self.HOOK, {**payload, "hook_event_name": "PostToolUse"}) == {"continue": True}
        assert not (project_sources / ".rat/state/rtl-modified-files.txt").exists()


class TestRtlEditTrackerPhase6:
    """Tests for Phase 6 stale detection in hooks/rtl-edit-tracker.sh."""

    HOOK = HOOKS_DIR / "rtl-edit-tracker.sh"

    def test_no_phase6_no_stale_marker(self, tmp_project):
        """No phase 6 review dir → no stale marker created."""
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/module/top.sv"}
        run_hook(self.HOOK, stdin)
        stale = tmp_project / ".rat" / "state" / "phase6-stale"
        assert not stale.exists()

    def test_phase6_exists_creates_stale_marker(self, tmp_project):
        """Phase 6 review with full deliverable set → stale marker created on RTL edit."""
        p6_dir = tmp_project / "reviews" / "phase-6-review"
        p6_dir.mkdir(parents=True)
        (p6_dir / "code-review.md").write_text("# Code Review\nverdict: PASS")
        (p6_dir / "design-review.md").write_text("# Design Review")
        (p6_dir / "design-note.md").write_text("# Design Note")
        (p6_dir / "improvements.md").write_text("# Improvements")
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/module/top.sv"}
        run_hook(self.HOOK, stdin)
        stale = tmp_project / ".rat" / "state" / "phase6-stale"
        assert stale.exists()

    def test_phase6_empty_dir_no_stale(self, tmp_project):
        """Phase 6 dir exists but no .md files → no stale marker."""
        p6_dir = tmp_project / "reviews" / "phase-6-review"
        p6_dir.mkdir(parents=True)
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/module/top.sv"}
        run_hook(self.HOOK, stdin)
        stale = tmp_project / ".rat" / "state" / "phase6-stale"
        assert not stale.exists()

    def test_phase6_partial_deliverables_no_stale(self, tmp_project):
        """Phase 6 with only some deliverables (in-progress) → no stale marker."""
        p6_dir = tmp_project / "reviews" / "phase-6-review"
        p6_dir.mkdir(parents=True)
        (p6_dir / "code-review.md").write_text("# Partial — P6 in progress")
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/module/top.sv"}
        run_hook(self.HOOK, stdin)
        stale = tmp_project / ".rat" / "state" / "phase6-stale"
        assert not stale.exists(), "Partial P6 deliverables should not trigger staleness"

    def test_phase6_stale_message_in_output(self, tmp_project):
        """Phase 6 stale detection should include message in output."""
        p6_dir = tmp_project / "reviews" / "phase-6-review"
        p6_dir.mkdir(parents=True)
        (p6_dir / "code-review.md").write_text("# Code Review")
        (p6_dir / "design-review.md").write_text("# Design Review")
        (p6_dir / "design-note.md").write_text("# Design Note")
        (p6_dir / "improvements.md").write_text("# Improvements")
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/module/top.sv"}
        result = run_hook(self.HOOK, stdin)
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "Phase 6" in ctx or "phase6" in ctx.lower() or "stale" in ctx.lower()

    def test_non_rtl_file_no_stale(self, tmp_project):
        """Non-RTL file edit should never create stale marker even with Phase 6 dir."""
        p6_dir = tmp_project / "reviews" / "phase-6-review"
        p6_dir.mkdir(parents=True)
        (p6_dir / "code-review.md").write_text("# Review")
        stdin = {"cwd": str(tmp_project), "file_path": "docs/readme.md"}
        run_hook(self.HOOK, stdin)
        stale = tmp_project / ".rat" / "state" / "phase6-stale"
        assert not stale.exists()

    def test_trackfile_recorded_despite_lock_timeout(self, tmp_project):
        """Fail-closed: RTL file must be tracked in fallback when TRACK_FILE lock fails."""
        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        # Pre-create lock dir with live PID to prevent stale reclaim
        lock_dir = state_dir / "rtl-modified-files.txt.lock"
        lock_dir.mkdir()
        (lock_dir / "pid").write_text(str(os.getpid()))
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/alu/alu.sv"}
        result = run_hook(self.HOOK, stdin, env={"FLOCK_TIMEOUT": "1"})
        fallback_file = state_dir / "rtl-modified-files-fallback.txt"
        assert fallback_file.exists(), "Fallback file must be created on lock timeout (fail-closed)"
        assert "rtl/alu/alu.sv" in fallback_file.read_text()
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "RTL Verify Gate" in ctx

    def test_phase6_stale_created_despite_lock_timeout(self, tmp_project):
        """Fail-closed: stale marker must be created even when lock acquisition fails."""
        p6_dir = tmp_project / "reviews" / "phase-6-review"
        p6_dir.mkdir(parents=True)
        (p6_dir / "code-review.md").write_text("# Review")
        (p6_dir / "design-review.md").write_text("# Design Review")
        (p6_dir / "design-note.md").write_text("# Design Note")
        (p6_dir / "improvements.md").write_text("# Improvements")
        # Pre-create lock dir to simulate a held lock (causes acquire_lock timeout)
        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        lock_dir = state_dir / "phase6-stale.lock"
        lock_dir.mkdir()
        # Write current process PID — a live process so stale detection cannot reclaim the lock
        (lock_dir / "pid").write_text(str(os.getpid()))
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/module/top.sv"}
        result = run_hook(self.HOOK, stdin, env={"FLOCK_TIMEOUT": "1"})
        stale = state_dir / "phase6-stale"
        assert stale.exists(), "Stale marker must be created even on lock timeout (fail-closed)"
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "stale" in ctx.lower() or "Phase 6" in ctx


class TestSpecCascadeMarkerLifecycle:
    """Tests for the spec-cascade-stale marker lifecycle in
    hooks/rtl-edit-tracker.sh: transition-edge warning, silent marker
    refresh, and auto-clear on contract-validator PASS report."""

    HOOK = HOOKS_DIR / "rtl-edit-tracker.sh"

    def _add_downstream(self, tmp_project):
        rtl_dir = tmp_project / "rtl" / "module"
        rtl_dir.mkdir(parents=True, exist_ok=True)
        (rtl_dir / "top.sv").write_text("module top; endmodule\n")

    def _doc_edit(self, tmp_project, rel="docs/phase-3-uarch/pipeline.md"):
        doc = tmp_project / rel
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# spec\n")
        # Cascade case patterns match */docs/phase-*/* — absolute path required.
        return run_hook(self.HOOK, {"cwd": str(tmp_project), "file_path": str(doc)})

    def test_marker_created_with_warning_on_first_doc_edit(self, tmp_project):
        """First upstream doc edit with downstream RTL present → marker + warning."""
        self._add_downstream(tmp_project)
        result = self._doc_edit(tmp_project)
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "[SPEC CASCADE" in ctx
        assert "cross-phase-contract-validator" in ctx
        marker = tmp_project / ".rat" / "state" / "spec-cascade-stale-p3"
        assert marker.exists()

    def test_no_marker_without_downstream(self, tmp_project):
        """Normal forward flow: no downstream artifacts → no marker, no warning."""
        result = self._doc_edit(tmp_project)
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "[SPEC CASCADE" not in ctx
        marker = tmp_project / ".rat" / "state" / "spec-cascade-stale-p3"
        assert not marker.exists()

    def test_second_edit_no_duplicate_warning_marker_refreshed(self, tmp_project):
        """Marker already set → silent mtime refresh, no repeated [SPEC CASCADE]."""
        self._add_downstream(tmp_project)
        self._doc_edit(tmp_project)
        marker = tmp_project / ".rat" / "state" / "spec-cascade-stale-p3"
        assert marker.exists()
        # Backdate the marker to detect the mtime refresh.
        os.utime(marker, (1000000, 1000000))
        result = self._doc_edit(tmp_project, rel="docs/phase-3-uarch/other.md")
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "[SPEC CASCADE" not in ctx, "warn only on marker creation (transition edge)"
        assert marker.exists()
        assert marker.stat().st_mtime > 1000000, "marker mtime must be refreshed silently"

    def test_json_doc_edit_critical_severity(self, tmp_project):
        """Structured requirements (.json) → CRITICAL cascade severity."""
        self._add_downstream(tmp_project)
        result = self._doc_edit(
            tmp_project, rel="docs/phase-3-uarch/iron-requirements.json"
        )
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "[SPEC CASCADE CRITICAL]" in ctx

    def test_marker_cleared_on_validator_pass_report(self, tmp_project):
        """Writing the contract-validation report with Verdict: PASS clears markers."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "spec-cascade-stale-p1").touch()
        (state_dir / "spec-cascade-stale-p3").touch()
        report = tmp_project / "reviews" / "cross-phase-contract-validation.md"
        report.parent.mkdir(parents=True)
        report.write_text(
            "# Cross-Phase Contract Validation\n"
            "- Boundary: P3→P4\n"
            "- Verdict: PASS\n"
        )
        result = run_hook(
            self.HOOK, {"cwd": str(tmp_project), "file_path": str(report)}
        )
        assert not (state_dir / "spec-cascade-stale-p1").exists()
        assert not (state_dir / "spec-cascade-stale-p3").exists()
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "SPEC CASCADE RESOLVED" in ctx

    def test_marker_kept_on_validator_fail_report(self, tmp_project):
        """FAIL verdict keeps markers even when table rows contain PASS cells."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "spec-cascade-stale-p3").touch()
        report = tmp_project / "reviews" / "cross-phase-contract-validation.md"
        report.parent.mkdir(parents=True)
        report.write_text(
            "# Cross-Phase Contract Validation\n"
            "- Verdict: FAIL\n"
            "| 1 | Port width consistency | PASS | ok |\n"
            "| 2 | Memory classification | FAIL | rtl/module/top.sv:10 |\n"
        )
        result = run_hook(
            self.HOOK, {"cwd": str(tmp_project), "file_path": str(report)}
        )
        assert (state_dir / "spec-cascade-stale-p3").exists()
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "SPEC CASCADE RESOLVED" not in ctx

    def test_other_review_write_does_not_clear(self, tmp_project):
        """Unrelated reviews/ writes never clear cascade markers."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "spec-cascade-stale-p2").touch()
        other = tmp_project / "reviews" / "phase-6-review" / "code-review.md"
        other.parent.mkdir(parents=True)
        other.write_text("Verdict: PASS\n")
        run_hook(self.HOOK, {"cwd": str(tmp_project), "file_path": str(other)})
        assert (state_dir / "spec-cascade-stale-p2").exists()

    def test_pass_report_without_markers_plain_continue(self, tmp_project):
        """PASS report with no markers present → plain continue (no RESOLVED msg)."""
        report = tmp_project / "reviews" / "cross-phase-contract-validation.md"
        report.parent.mkdir(parents=True)
        report.write_text("- Verdict: PASS\n")
        result = run_hook(
            self.HOOK, {"cwd": str(tmp_project), "file_path": str(report)}
        )
        assert result["continue"] is True

    def test_marker_created_under_rat_project_root_override(
        self, tmp_project, tmp_path
    ):
        """External Workflow driver: payload cwd elsewhere + RAT_PROJECT_ROOT set →
        downstream detection and marker creation resolve against the override root."""
        self._add_downstream(tmp_project)
        driver_cwd = tmp_path / "driver"
        driver_cwd.mkdir()
        doc = tmp_project / "docs" / "phase-3-uarch" / "pipeline.md"
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text("# spec\n")
        result = run_hook(
            self.HOOK,
            {"cwd": str(driver_cwd), "file_path": str(doc)},
            env={"RAT_PROJECT_ROOT": str(tmp_project)},
        )
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "[SPEC CASCADE" in ctx
        marker = tmp_project / ".rat" / "state" / "spec-cascade-stale-p3"
        assert marker.exists(), "marker must land under the override root"
        assert not (driver_cwd / ".rat").exists(), "no .rat leak into driver cwd"

    def test_marker_cleared_on_pass_report_under_override_root(
        self, tmp_project, tmp_path
    ):
        """Validator PASS report written from a foreign cwd with RAT_PROJECT_ROOT
        set still clears the markers under the override root."""
        driver_cwd = tmp_path / "driver"
        driver_cwd.mkdir()
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "spec-cascade-stale-p3").touch()
        report = tmp_project / "reviews" / "cross-phase-contract-validation.md"
        report.parent.mkdir(parents=True)
        report.write_text("- Verdict: PASS\n")
        result = run_hook(
            self.HOOK,
            {"cwd": str(driver_cwd), "file_path": str(report)},
            env={"RAT_PROJECT_ROOT": str(tmp_project)},
        )
        assert not (state_dir / "spec-cascade-stale-p3").exists()
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "SPEC CASCADE RESOLVED" in ctx

    def test_only_existing_canonical_project_report_can_clear_markers(
        self, tmp_project, tmp_path
    ):
        state_dir = tmp_project / ".rat" / "state"
        marker = state_dir / "spec-cascade-stale-p3"
        marker.touch()

        external_report = (
            tmp_path / "external" / "reviews" / "cross-phase-contract-validation.md"
        )
        external_report.parent.mkdir(parents=True)
        external_report.write_text("- Verdict: PASS\n")
        run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "file_path": str(external_report)},
        )
        assert marker.exists(), "a PASS report outside the active project is untrusted"

        missing_report = (
            tmp_project / "reviews" / "cross-phase-contract-validation.md"
        )
        run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "file_path": str(missing_report)},
        )
        assert marker.exists(), "a missing canonical report cannot clear active state"

        external_report_target = tmp_path / "external-pass.md"
        external_report_target.write_text("- Verdict: PASS\n")
        missing_report.parent.mkdir(parents=True, exist_ok=True)
        missing_report.symlink_to(external_report_target)
        run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "file_path": str(missing_report)},
        )
        assert marker.exists(), "a symlinked report cannot clear active state"

    def test_report_under_symlinked_reviews_parent_cannot_clear_markers(
        self, tmp_project, tmp_path
    ):
        state_dir = tmp_project / ".rat" / "state"
        marker = state_dir / "spec-cascade-stale-p3"
        marker.touch()
        external_reviews = tmp_path / "external-reviews"
        external_reviews.mkdir()
        external_report = external_reviews / "cross-phase-contract-validation.md"
        external_report.write_text("- Verdict: PASS\n")
        (tmp_project / "reviews").symlink_to(external_reviews, target_is_directory=True)
        report = tmp_project / "reviews" / "cross-phase-contract-validation.md"

        run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "file_path": str(report)},
        )

        assert marker.exists(), "a symlinked reviews parent cannot clear active state"

    def test_hard_linked_validation_report_cannot_clear_markers(
        self, tmp_project, tmp_path
    ):
        state_dir = tmp_project / ".rat" / "state"
        marker = state_dir / "spec-cascade-stale-p3"
        marker.touch()
        external_report = tmp_path / "external-pass.md"
        external_report.write_text("- Verdict: PASS\n")
        report = tmp_project / "reviews" / "cross-phase-contract-validation.md"
        report.parent.mkdir(parents=True)
        report.hardlink_to(external_report)

        run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "file_path": str(report)},
        )

        assert marker.exists(), "a hard-linked report cannot clear active state"


class TestP6CascadeGate:
    """Tests for hooks/rtl-p6-cascade-gate.sh."""

    HOOK = HOOKS_DIR / "rtl-p6-cascade-gate.sh"

    def test_no_stale_marker_allows_exit(self, tmp_project):
        """No phase6-stale marker → allow exit."""
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_stale_marker_blocks_exit(self, tmp_project):
        """phase6-stale exists without cascade-done → block exit."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        _assert_stop_blocked(result)
        ctx = result.get("reason", "")
        assert "Phase 6" in ctx

    def test_cascade_done_allows_exit(self, tmp_project):
        """Both markers + updated docs → clean up and allow exit."""
        state_dir = tmp_project / ".rat" / "state"
        review_dir = tmp_project / "reviews" / "phase-6-review"
        review_dir.mkdir(parents=True)
        # Stale marker with old mtime
        (state_dir / "phase6-stale").touch()
        os.utime(state_dir / "phase6-stale", (1000, 1000))
        # Full P6 deliverable set with current (newer) mtime
        (review_dir / "design-note.md").write_text("# Updated")
        (review_dir / "code-review.md").write_text("# Updated")
        (review_dir / "design-review.md").write_text("# Updated")
        (review_dir / "improvements.md").write_text("# Updated")
        (state_dir / "phase6-cascade-done").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_cascade_done_cleans_markers(self, tmp_project):
        """After allowing exit with cascade-done + updated docs, both markers should be removed."""
        state_dir = tmp_project / ".rat" / "state"
        review_dir = tmp_project / "reviews" / "phase-6-review"
        review_dir.mkdir(parents=True)
        stale = state_dir / "phase6-stale"
        done = state_dir / "phase6-cascade-done"
        # Stale marker with old mtime
        stale.touch()
        os.utime(stale, (1000, 1000))
        # Full P6 deliverable set with current (newer) mtime
        (review_dir / "design-note.md").write_text("# Updated")
        (review_dir / "code-review.md").write_text("# Updated")
        (review_dir / "design-review.md").write_text("# Updated")
        (review_dir / "improvements.md").write_text("# Updated")
        done.touch()
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert not stale.exists()
        assert not done.exists()

    def test_block_message_content(self, tmp_project):
        """Block message should mention lint and all 4 P6 deliverables."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        ctx = result.get("reason", "")
        assert "lint" in ctx.lower()
        assert "code-review" in ctx.lower() or "code_review" in ctx.lower()
        assert "design-review" in ctx.lower() or "design_review" in ctx.lower()
        assert "design-note" in ctx.lower() or "design_note" in ctx.lower()
        assert "improvements" in ctx.lower()
        assert "/rtl-agent-team:rtl-p6-design-review" in ctx

    def test_p6_cascade_gate_uses_shared_json_util(self):
        content = (HOOKS_DIR / "rtl-p6-cascade-gate.sh").read_text()
        assert "lib/json-util.sh" in content
        assert "lib/team-gate-util.sh" in content
        assert "jsonu_get_root_string" in content
        assert "teamu_should_skip_gate" in content

    def test_cascade_done_blocks_when_docs_older_than_stale(self, tmp_project):
        """G5: cascade-done present but docs mtime older than stale marker → block."""
        state_dir = tmp_project / ".rat" / "state"
        review_dir = tmp_project / "reviews" / "phase-6-review"
        review_dir.mkdir(parents=True)
        # Create full P6 deliverable set with explicitly old mtime
        (review_dir / "design-note.md").write_text("# Old Design Note")
        (review_dir / "code-review.md").write_text("# Old Code Review")
        (review_dir / "design-review.md").write_text("# Old Design Review")
        (review_dir / "improvements.md").write_text("# Old Improvements")
        for doc in [review_dir / "design-note.md", review_dir / "code-review.md",
                     review_dir / "design-review.md", review_dir / "improvements.md"]:
            os.utime(doc, (1000, 1000))
        # Stale marker gets current time (much newer than docs)
        (state_dir / "phase6-stale").touch()
        (state_dir / "phase6-cascade-done").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        _assert_stop_blocked(result)
        ctx = result.get("reason", "")
        assert "not updated" in ctx.lower() or "cascade" in ctx.lower()

    @pytest.mark.parametrize("doc", ["code-review.md", "design-note.md"])
    def test_cascade_done_blocks_when_a_doc_shares_the_stale_markers_second(self, tmp_project, doc):
        """G5: a document written in the same second as the last RTL change is not newer."""
        state_dir = tmp_project / ".rat" / "state"
        review_dir = tmp_project / "reviews" / "phase-6-review"
        review_dir.mkdir(parents=True)
        (state_dir / "phase6-stale").touch()
        os.utime(state_dir / "phase6-stale", (2000, 2000))
        for name in ("code-review.md", "design-review.md", "improvements.md", "design-note.md"):
            (review_dir / name).write_text("reviewed")
            os.utime(review_dir / name, (3000, 3000))
        os.utime(review_dir / doc, (2000, 2000))
        (state_dir / "phase6-cascade-done").touch()
        _assert_stop_blocked(run_hook(self.HOOK, {"cwd": str(tmp_project)}))

    def test_cascade_done_allows_when_docs_newer_than_stale(self, tmp_project):
        """G5: cascade-done with docs newer than stale marker → allow and clean up."""
        state_dir = tmp_project / ".rat" / "state"
        review_dir = tmp_project / "reviews" / "phase-6-review"
        review_dir.mkdir(parents=True)
        # Stale marker with explicitly old mtime
        (state_dir / "phase6-stale").touch()
        os.utime(state_dir / "phase6-stale", (1000, 1000))
        # Full P6 deliverable set with current time (much newer than stale marker)
        (review_dir / "design-note.md").write_text("# Updated Design Note")
        (review_dir / "code-review.md").write_text("# Updated Code Review")
        (review_dir / "design-review.md").write_text("# Updated Design Review")
        (review_dir / "improvements.md").write_text("# Updated Improvements")
        (state_dir / "phase6-cascade-done").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True
        # Markers should be cleaned up
        assert not (state_dir / "phase6-stale").exists()
        assert not (state_dir / "phase6-cascade-done").exists()

    def test_cascade_done_no_docs_blocks_exit(self, tmp_project):
        """G5: cascade-done without review docs → block exit (stale marker proves docs once existed)."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "phase6-stale").touch()
        (state_dir / "phase6-cascade-done").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        _assert_stop_blocked(result)
        ctx = result.get("reason", "")
        assert "not found" in ctx.lower() or "not updated" in ctx.lower()

    def test_stale_docs_without_progress_pause_in_chain(self, tmp_project):
        (tmp_project / ".rat" / "state" / "phase6-stale").touch()
        results = [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
            for i in range(4)
        ]
        assert [r.get("decision") for r in results[:3]] == ["block"] * 3
        notice = results[3]["systemMessage"]
        assert "/rtl-agent-team:rtl-p6-design-review" in notice
        assert notice.endswith("phase6-cascade-done'")  # the command can be copied as is
        assert "decision" not in results[3]
        assert "is not asking Claude to continue in this turn" in notice
        assert "updated review documents are not yet recorded" in notice

    def test_doc_update_before_the_notice_restarts_the_count(self, tmp_project):
        (tmp_project / ".rat" / "state" / "phase6-stale").touch()
        for i in range(2):
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
        review = tmp_project / "reviews" / "phase-6-review"
        review.mkdir(parents=True)
        (review / "code-review.md").write_text("updated")
        results = [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True})
            for _ in range(4)
        ]
        assert [r.get("decision") for r in results[:3]] == ["block"] * 3
        assert "systemMessage" in results[3]

    def test_notice_holds_for_the_chain_despite_a_doc_update(self, tmp_project):
        (tmp_project / ".rat" / "state" / "phase6-stale").touch()
        for i in range(4):
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
        review = tmp_project / "reviews" / "phase-6-review"
        review.mkdir(parents=True)
        (review / "code-review.md").write_text("updated")
        assert run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True}) == {"continue": True}

    def test_new_chain_after_notice_blocks_again(self, tmp_project):
        (tmp_project / ".rat" / "state" / "phase6-stale").touch()
        for i in range(5):
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
        assert run_hook(self.HOOK, {"cwd": str(tmp_project)})["decision"] == "block"

    def test_worker_stop_keeps_leader_budget(self, tmp_project):
        state = tmp_project / ".rat" / "state"
        (state / "team-config.json").write_text(json.dumps(
            {"team_mode": True, "leader_session_id": "leader-001"}))
        _record_team_owner(tmp_project, "leader-001")
        (tmp_project / ".rat" / "state" / "phase6-stale").touch()
        lead = {"cwd": str(tmp_project), "session_id": "leader-001"}
        run_hook(self.HOOK, lead)
        run_hook(self.HOOK, {**lead, "stop_hook_active": True})
        run_hook(self.HOOK, {"cwd": str(tmp_project), "session_id": "worker-1"})
        assert (_budget_path(state, 'p6-cascade')).read_text().startswith("2\n")

    def test_allowed_stops_count_toward_the_chain_cap(self, tmp_project):
        # An earlier chain left this gate's budget; another hook then kept a new chain
        # going for six Stops while this gate allowed them.
        (_budget_path(tmp_project / ".rat" / "state", 'p6-cascade')).write_text("0\n\n1\n0\np-1\n")
        stop = {"cwd": str(tmp_project), "prompt_id": "p-1"}  # production Stops carry a prompt id
        for i in range(6):
            assert run_hook(self.HOOK, {**stop, "stop_hook_active": i > 0}) == {"continue": True}
        (tmp_project / ".rat" / "state" / "phase6-stale").touch()
        result = run_hook(self.HOOK, {**stop, "stop_hook_active": True})
        assert "decision" not in result
        assert "rtl-p6-design-review" in result["systemMessage"]

    @pytest.mark.parametrize("satisfy", ["cascade_done", "marker_removed"])
    def test_satisfied_gate_is_not_left_silent(self, tmp_project, satisfy):
        state = tmp_project / ".rat" / "state"
        stale = state / "phase6-stale"
        stale.touch()
        os.utime(stale, (1000, 1000))
        results = [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
            for i in range(4)
        ]
        assert "systemMessage" in results[3]
        if satisfy == "cascade_done":
            review = tmp_project / "reviews" / "phase-6-review"
            review.mkdir(parents=True)
            for name in ("code-review.md", "design-review.md", "improvements.md", "design-note.md"):
                (review / name).write_text("updated")
            (state / "phase6-cascade-done").touch()
        else:
            stale.unlink()
        # A chained Stop, so the chain-start reset cannot be what clears the budget.
        assert run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True}) == {"continue": True}
        lines = (_budget_path(state, 'p6-cascade')).read_text().split("\n")
        assert (lines[0], lines[2], lines[3]) == ("0", "5", "0")
        stale.touch()  # a new RTL edit later in the same chain
        assert run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True})["decision"] == "block"

    def test_ppa_result_newer_than_the_design_note_is_bounded(self, tmp_project):
        state = tmp_project / ".rat" / "state"
        review = tmp_project / "reviews" / "phase-6-review"
        review.mkdir(parents=True)
        (review / "design-note.md").write_text("# before PPA")
        os.utime(review / "design-note.md", (1000, 1000))
        (state / "phase6-stale").touch()
        (state / "ppa-opt-done").write_text("converge cycle 3\n")
        results = [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
            for i in range(4)
        ]
        assert [r.get("decision") for r in results[:3]] == ["block"] * 3
        assert "PPA" in results[0]["reason"]
        assert "/rtl-agent-team:rtl-p6-design-review" in results[0]["reason"]
        assert results[0]["reason"].endswith("phase6-cascade-done'")
        assert "decision" not in results[3]
        assert "systemMessage" in results[3]

    @pytest.mark.parametrize("cascade_done", [False, True])
    @pytest.mark.parametrize("doc", ["code-review.md", "design-review.md", "improvements.md", "design-note-top.md"])
    def test_updating_an_existing_document_restarts_the_count(self, tmp_project, doc, cascade_done):
        state = tmp_project / ".rat" / "state"
        review = tmp_project / "reviews" / "phase-6-review"
        review.mkdir(parents=True)
        for name in ("code-review.md", "design-review.md", "improvements.md", "design-note-top.md"):
            (review / name).write_text("old")
            os.utime(review / name, (1000, 1000))
        (state / "phase6-stale").touch()
        if cascade_done:
            (state / "phase6-cascade-done").touch()
        results = [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0})
            for i in range(2)
        ]
        os.utime(review / doc, (2000, 2000))  # rewritten, and still older than the stale marker
        results += [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True})
            for _ in range(4)
        ]
        assert [r.get("decision") for r in results[:5]] == ["block"] * 5
        assert "systemMessage" in results[5]

    def test_retouching_the_marker_alone_is_not_progress(self, tmp_project):
        state = tmp_project / ".rat" / "state"
        (state / "phase6-stale").touch()
        done = state / "phase6-cascade-done"
        done.touch()
        results = []
        for i in range(4):
            os.utime(done, (3000 + i, 3000 + i))  # touched again, documents unchanged
            results.append(run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": i > 0}))
        assert [r.get("decision") for r in results[:3]] == ["block"] * 3
        assert "touch" not in results[0]["reason"]
        assert "stays in place" in results[0]["reason"]
        assert "systemMessage" in results[3]
        notice = results[3]["systemMessage"]
        assert "recorded as updated" in notice and "touch" not in notice  # the marker already exists

    def test_commands_survive_a_quote_in_the_project_path(self, tmp_path):
        project = tmp_path / "o'brien"
        state = project / ".rat" / "state"
        state.mkdir(parents=True)
        (state / "phase6-stale").touch()
        results = [
            run_hook(self.HOOK, {"cwd": str(project), "stop_hook_active": i > 0})
            for i in range(4)
        ]
        done = state / "phase6-cascade-done"
        commands = [
            results[0]["reason"].split("When done: ", 1)[1],
            results[3]["systemMessage"].split("then record it: ", 1)[1],
        ]
        # PPA-Opt finished after the design note was written.
        review = project / "reviews" / "phase-6-review"
        review.mkdir(parents=True)
        (review / "design-note.md").write_text("# before PPA")
        os.utime(review / "design-note.md", (1000, 1000))
        (state / "ppa-opt-done").touch()
        commands.append(run_hook(self.HOOK, {"cwd": str(project)})["reason"].split("then record it: ", 1)[1])
        for command in commands:
            done.unlink(missing_ok=True)
            before = set(tmp_path.rglob("*"))
            subprocess.run(["sh", "-c", command], check=True, cwd=tmp_path)
            assert set(tmp_path.rglob("*")) - before == {done}  # exactly the marker

    def test_cascade_done_does_not_bypass_a_newer_ppa_result(self, tmp_project):
        state = tmp_project / ".rat" / "state"
        review = tmp_project / "reviews" / "phase-6-review"
        review.mkdir(parents=True)
        stale, done = state / "phase6-stale", state / "phase6-cascade-done"
        stale.touch()
        os.utime(stale, (1000, 1000))
        for name in ("code-review.md", "design-review.md", "improvements.md", "design-note.md"):
            (review / name).write_text("reviewed before PPA-Opt")
            os.utime(review / name, (2000, 2000))
        (state / "ppa-opt-done").touch()
        os.utime(state / "ppa-opt-done", (3000, 3000))
        done.touch()
        results = [run_hook(self.HOOK, {"cwd": str(tmp_project)})]
        assert "PPA-Opt" in results[0]["reason"]
        assert stale.exists() and done.exists()
        results += [
            run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True})
            for _ in range(3)
        ]
        assert [r.get("decision") for r in results] == ["block"] * 3 + [None]
        assert "systemMessage" in results[3]
        os.utime(review / "design-note.md", (4000, 4000))  # the review re-ran after PPA-Opt
        assert run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True}) == {"continue": True}
        assert not stale.exists() and not done.exists()

    def test_a_symlinked_cwd_is_not_progress(self, tmp_path):
        project = tmp_path / "project"
        (project / ".rat" / "state").mkdir(parents=True)
        (project / ".rat" / "state" / "phase6-stale").touch()
        link = tmp_path / "link"
        link.symlink_to(project)
        # One chain whose input cwd alternates between the project and a symlink to it.
        results = [
            run_hook(self.HOOK, {"cwd": str(link if i % 2 else project), "stop_hook_active": i > 0})
            for i in range(4)
        ]
        assert [r.get("decision") for r in results] == ["block"] * 3 + [None]
        assert "systemMessage" in results[3]

    @pytest.mark.parametrize("cascade_done", [False, True])
    def test_a_design_note_as_new_as_the_ppa_result_is_current(self, tmp_project, cascade_done):
        # The PPA branch and the cascade-done check must agree on a same-second tie.
        state = tmp_project / ".rat" / "state"
        review = tmp_project / "reviews" / "phase-6-review"
        review.mkdir(parents=True)
        (state / "phase6-stale").touch()
        os.utime(state / "phase6-stale", (1000, 1000))
        for name in ("code-review.md", "design-review.md", "improvements.md", "design-note.md"):
            (review / name).write_text("reviewed")
            os.utime(review / name, (3000, 3000))
        (state / "ppa-opt-done").touch()
        os.utime(state / "ppa-opt-done", (3000, 3000))
        if cascade_done:
            (state / "phase6-cascade-done").touch()
            assert run_hook(self.HOOK, {"cwd": str(tmp_project)}) == {"continue": True}
        else:
            assert "PPA" not in run_hook(self.HOOK, {"cwd": str(tmp_project)})["reason"]

    @pytest.mark.parametrize("cascade_done", [False, True])
    def test_a_design_note_one_second_older_than_the_ppa_result_is_stale(self, tmp_project, cascade_done):
        # The other side of the same-second tie: one second older is already stale.
        state = tmp_project / ".rat" / "state"
        review = tmp_project / "reviews" / "phase-6-review"
        review.mkdir(parents=True)
        (state / "phase6-stale").touch()
        os.utime(state / "phase6-stale", (1000, 1000))
        for name in ("code-review.md", "design-review.md", "improvements.md", "design-note.md"):
            (review / name).write_text("reviewed")
            os.utime(review / name, (3000, 3000))
        os.utime(review / "design-note.md", (2999, 2999))
        (state / "ppa-opt-done").touch()
        os.utime(state / "ppa-opt-done", (3000, 3000))
        if cascade_done:
            (state / "phase6-cascade-done").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        _assert_stop_blocked(result)
        assert "PPA" in result["reason"]

    def test_every_split_design_note_must_postdate_the_ppa_result(self, tmp_project):
        state = tmp_project / ".rat" / "state"
        review = tmp_project / "reviews" / "phase-6-review"
        review.mkdir(parents=True)
        (state / "phase6-stale").touch()
        os.utime(state / "phase6-stale", (1000, 1000))
        for name in ("code-review.md", "design-review.md", "improvements.md",
                     "design-note-overview.md", "design-note-top.md"):
            (review / name).write_text("reviewed")
            os.utime(review / name, (4000, 4000))
        os.utime(review / "design-note-top.md", (2000, 2000))  # one split note predates PPA-Opt
        (state / "ppa-opt-done").touch()
        os.utime(state / "ppa-opt-done", (3000, 3000))
        (state / "phase6-cascade-done").touch()
        assert run_hook(self.HOOK, {"cwd": str(tmp_project)})["decision"] == "block"

    def test_session_in_a_subdirectory_checks_the_project_review_documents(self, tmp_project):
        state = tmp_project / ".rat" / "state"
        review = tmp_project / "reviews" / "phase-6-review"
        review.mkdir(parents=True)
        docs = [review / name for name in
                ("code-review.md", "design-review.md", "design-note.md", "improvements.md")]
        for doc in docs:
            doc.write_text("reviewed")
            os.utime(doc, (1000, 1000))
        (state / "phase6-stale").touch()
        os.utime(state / "phase6-stale", (2000, 2000))
        (state / "phase6-cascade-done").touch()
        (tmp_project / "rtl").mkdir()
        stdin = {"cwd": str(tmp_project / "rtl")}
        env = {"CLAUDE_PROJECT_DIR": str(tmp_project)}
        result = run_hook(self.HOOK, stdin, env=env)
        _assert_stop_blocked(result)
        for name in ("code-review.md", "design-review.md", "design-note", "improvements.md"):
            assert name in result["reason"]
        # The documents are read from the project root, not rtl/reviews/: updating them passes.
        for doc in docs:
            os.utime(doc, (3000, 3000))
        assert run_hook(self.HOOK, stdin, env=env) == {"continue": True}


class TestSkillCompletionGate:
    """One bounded missing-work reminder, without an automatic review ladder."""
    HOOK = HOOKS_DIR / 'rtl-skill-completion-gate.sh'

    def _write_skill_state(self, root, **overrides):
        state={'skill':'rtl-p4-implement','started_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'pending':'unit-test-pass','all_complete':False,'iteration':1,'max_iterations':5,
               'use_escalation_ladder':True,'strategy':'primary',**overrides}
        path=root/'.rat/state/skill-active.json';path.write_text(json.dumps(state));return path

    def test_no_state_allows_exit(self,tmp_project):
        assert run_hook(self.HOOK,{'cwd':str(tmp_project)})=={'continue':True}

    @pytest.mark.parametrize('updates',[{'all_complete':True},{'pending':''}])
    def test_completed_state_is_removed(self,tmp_project,updates):
        path=self._write_skill_state(tmp_project,**updates)
        assert run_hook(self.HOOK,{'cwd':str(tmp_project)})=={'continue':True}
        assert not path.exists()

    def test_missing_work_blocks_once_then_notifies(self,tmp_project):
        self._write_skill_state(tmp_project)
        first=run_hook(self.HOOK,{'cwd':str(tmp_project)})
        _assert_stop_blocked(first)
        assert 'unit-test-pass' in first['reason']
        assert 'Do not repeat successful reviews' in first['reason']
        second=run_hook(self.HOOK,{'cwd':str(tmp_project),'stop_hook_active':True})
        assert second.get('systemMessage')
        assert run_hook(self.HOOK,{'cwd':str(tmp_project),'stop_hook_active':True})=={'continue':True}

    @pytest.mark.parametrize('iteration',[1,5,11,12,100])
    def test_legacy_iteration_count_never_schedules_another_review(self,tmp_project,iteration):
        path=self._write_skill_state(tmp_project,iteration=iteration)
        result=run_hook(self.HOOK,{'cwd':str(tmp_project)})
        _assert_stop_blocked(result)
        assert json.loads(path.read_text())['iteration']==iteration
        assert 'last_chance' not in result['reason']
        assert 'switching' not in result['reason']

    def test_stale_pending_state_notifies_instead_of_silent_completion(self,tmp_project):
        path=self._write_skill_state(tmp_project,started_at='2020-01-01T00:00:00Z')
        os.utime(path,(1000000000,1000000000))
        result=run_hook(self.HOOK,{'cwd':str(tmp_project)})
        assert result.get('systemMessage')
        assert 'not been marked complete' in result['systemMessage']
        assert not path.exists()

    def test_background_activity_refreshes_the_loop(self,tmp_project):
        path=self._write_skill_state(tmp_project,started_at='2020-01-01T00:00:00Z')
        os.utime(path,(1000000000,1000000000))
        result=run_hook(self.HOOK,{'cwd':str(tmp_project),'background_tasks':[{'type':'subagent'}]})
        assert result=={'continue':True}
        assert time.time()-path.stat().st_mtime<5

    def test_user_decision_is_not_hidden_by_a_skill(self,tmp_project):
        self._write_skill_state(tmp_project)
        (tmp_project/'.rat/state/rat-auto-design-state.json').write_text(json.dumps({
            'status':'in_progress','orchestration_control':{'needs_user_decision':True}}))
        result=run_hook(self.HOOK,{'cwd':str(tmp_project)})
        assert result.get('systemMessage')
        assert result.get('decision')!='block'

    @pytest.mark.parametrize("active_skill", ["rat-refc-to-p5", "p1-spec-research", "rtl-lint-check"])
    def test_refc_pipeline_waits_only_for_its_active_phase(self, tmp_project, active_skill):
        self._write_skill_state(tmp_project, skill=active_skill, pending="phase-gate-passed")
        state = tmp_project / ".rat/state/rat-refc-to-p5-state.json"
        state.write_text(json.dumps({
            "status": "in_progress", "current_skill": "p1-spec-research",
            "orchestration_control": {"needs_user_decision": True},
        }))
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        if active_skill == "rtl-lint-check":
            _assert_stop_blocked(result)
        else:
            assert result == {"systemMessage": "Info> rat-refc-to-p5 is waiting for your decision."}
            assert run_hook(self.HOOK, {"cwd": str(tmp_project), "stop_hook_active": True}) == {"continue": True}

    def test_infeasibility_notifies_without_another_attempt(self,tmp_project):
        self._write_skill_state(tmp_project,strategy='upstream_challenge',pending='compliance-pass')
        (tmp_project/'.rat/state/compliance-report.json').write_text(json.dumps({
            'verdict':'VIOLATION','summary':{'max_violation_authority':1,'infeasibility_detected':'true'}}))
        result=run_hook(self.HOOK,{'cwd':str(tmp_project)})
        assert result.get('systemMessage')
        assert result.get('decision')!='block'

    def test_new_pending_work_rearms_before_the_notice(self,tmp_project):
        path=self._write_skill_state(tmp_project)
        assert run_hook(self.HOOK,{'cwd':str(tmp_project)}).get('decision')=='block'
        data=json.loads(path.read_text());data['pending']='new-failed-check';path.write_text(json.dumps(data))
        assert run_hook(self.HOOK,{'cwd':str(tmp_project),'stop_hook_active':True}).get('decision')=='block'


class TestSkillActivation:
    """Tests for hooks/rtl-skill-activation.sh."""

    HOOK = HOOKS_DIR / "rtl-skill-activation.sh"

    def test_non_rtl_skill_ignored(self, tmp_project):
        """Non rtl-agent-team skills should be ignored."""
        stdin = {"cwd": str(tmp_project), "skill": "oh-my-claudecode:ultrawork"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        assert not state_file.exists()

    def test_rtl_skill_creates_state(self, tmp_project):
        """rtl-agent-team skill with criteria should create state file."""
        _setup_marker(tmp_project)
        # Create criteria config
        criteria = {"rtl-p4s-bugfix": "lint_pass, tb_updated, sim_pass"}
        (tmp_project / "skill-completion-criteria.json").write_text(json.dumps(criteria))

        stdin = {"cwd": str(tmp_project), "hook_event_name": "PostToolUse",
                 "skill": "rtl-agent-team:rtl-p4s-bugfix"}
        result = run_hook(self.HOOK, stdin, env={"CLAUDE_PLUGIN_ROOT": str(tmp_project)})
        assert result["continue"] is True
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert state["skill"] == "rtl-p4s-bugfix"
        assert state["all_complete"] is False
        assert "lint_pass" in state["pending"]
        assert state["use_escalation_ladder"] is True

    def test_rtl_skill_no_criteria_no_state(self, tmp_project):
        """rtl-agent-team skill without criteria in config should not create state."""
        _setup_marker(tmp_project)
        criteria = {"rtl-p4s-bugfix": "lint_pass"}
        (tmp_project / "skill-completion-criteria.json").write_text(json.dumps(criteria))

        stdin = {"cwd": str(tmp_project), "hook_event_name": "PostToolUse",
                 "skill": "rtl-agent-team:systemverilog"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        assert not state_file.exists()

    def test_no_criteria_file_no_state(self, tmp_project):
        """Missing criteria file should not create state."""
        _setup_marker(tmp_project)
        stdin = {"cwd": str(tmp_project), "hook_event_name": "PostToolUse",
                 "skill": "rtl-agent-team:rtl-p4s-bugfix"}
        result = run_hook(self.HOOK, stdin, env={"CLAUDE_PLUGIN_ROOT": str(tmp_project)})
        assert result["continue"] is True
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        assert not state_file.exists()

    def test_different_skill_state_not_overridden(self, tmp_project):
        """G6: Different skill invocation should NOT override existing state."""
        _setup_marker(tmp_project)
        criteria = {"rtl-p4s-bugfix": "lint_pass, tb_updated, sim_pass"}
        (tmp_project / "skill-completion-criteria.json").write_text(json.dumps(criteria))

        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        existing = {"skill": "rtl-p4-implement", "iteration": 3, "all_complete": False, "pending": "something"}
        (state_dir / "skill-active.json").write_text(json.dumps(existing))

        stdin = {"cwd": str(tmp_project), "hook_event_name": "PostToolUse",
                 "skill": "rtl-agent-team:rtl-p4s-bugfix"}
        result = run_hook(self.HOOK, stdin)
        # State should NOT be overridden (different skill)
        state = json.loads((state_dir / "skill-active.json").read_text())
        assert state["skill"] == "rtl-p4-implement"  # Original, not rtl-p4s-bugfix
        assert state["iteration"] == 3

    def test_same_skill_reinvocation_resets_counter(self, tmp_project):
        """G6: Re-invoking the same skill should reset iteration counter."""
        _setup_marker(tmp_project)
        criteria = {"rtl-p4s-bugfix": "lint_pass, tb_updated, sim_pass"}
        (tmp_project / "skill-completion-criteria.json").write_text(json.dumps(criteria))

        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        existing = {"skill": "rtl-p4s-bugfix", "iteration": 3, "all_complete": False, "pending": "sim_pass"}
        (state_dir / "skill-active.json").write_text(json.dumps(existing))

        stdin = {"cwd": str(tmp_project), "hook_event_name": "PostToolUse",
                 "skill": "rtl-agent-team:rtl-p4s-bugfix"}
        result = run_hook(self.HOOK, stdin, env={"CLAUDE_PLUGIN_ROOT": str(tmp_project)})
        assert result["continue"] is True
        state = json.loads((state_dir / "skill-active.json").read_text())
        assert state["skill"] == "rtl-p4s-bugfix"
        assert state["iteration"] == 1  # Reset to 1, not 3

    def test_activation_message(self, tmp_project):
        """Activation should include skill name in additionalContext."""
        _setup_marker(tmp_project)
        criteria = {"rtl-p4s-bugfix": "lint_pass, sim_pass"}
        (tmp_project / "skill-completion-criteria.json").write_text(json.dumps(criteria))

        stdin = {"cwd": str(tmp_project), "hook_event_name": "PostToolUse",
                 "skill": "rtl-agent-team:rtl-p4s-bugfix"}
        result = run_hook(self.HOOK, stdin, env={"CLAUDE_PLUGIN_ROOT": str(tmp_project)})
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "rtl-p4s-bugfix" in ctx

    def test_rtl_setup_preflight_does_not_install_templates(self, tmp_project):
        """Loading a setup skill is not permission to run the installer in a hook."""
        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rat-init-project"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True

        run_sim = tmp_project / "scripts" / "run_sim.sh"
        run_lint = tmp_project / "lint" / "scripts" / "run_lint.sh"
        run_syn = tmp_project / "syn" / "scripts" / "run_syn.sh"
        run_cdc = tmp_project / "lint" / "scripts" / "run_cdc.sh"

        for path in [run_sim, run_lint, run_syn, run_cdc]:
            assert not path.exists(), f"Preflight unexpectedly installed: {path}"

        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "explicit template installer" in ctx

    def test_rtl_setup_bootstrap_is_non_destructive(self, tmp_project):
        """Existing scripts should not be overwritten by rat-init-project bootstrap."""
        run_sim = tmp_project / "scripts" / "run_sim.sh"
        run_sim.parent.mkdir(parents=True, exist_ok=True)
        run_sim.write_text("#!/usr/bin/env bash\necho custom\n")
        run_sim.chmod(0o755)

        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rat-init-project"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        assert run_sim.read_text() == "#!/usr/bin/env bash\necho custom\n"

    def test_parser_uses_top_level_skill_key(self, tmp_project):
        _setup_marker(tmp_project)
        criteria = {"rtl-p4s-bugfix": "lint_pass, sim_pass"}
        (tmp_project / "skill-completion-criteria.json").write_text(json.dumps(criteria))

        raw_input = json.dumps(
            {
                "cwd": str(tmp_project),
                "hook_event_name": "PostToolUse",
                "skill": "rtl-agent-team:rtl-p4s-bugfix",
                "meta": {"skill": "rtl-agent-team:rat-setup"},
            }
        )

        result = run_hook(self.HOOK, raw_input, env={"CLAUDE_PLUGIN_ROOT": str(tmp_project)})
        assert result["continue"] is True
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert state["skill"] == "rtl-p4s-bugfix"

    def _invoke_in_team(self, tmp_project, leader, age_hours=0, **ids):
        """Invoke rtl-p4s-bugfix, as test_rtl_skill_creates_state does, while a team whose
        leader is `leader` is active (None: no leader key, as autopilot writes it) and whose
        config was last written `age_hours` ago. Returns whether the completion loop started."""
        _setup_marker(tmp_project)
        criteria = {"rtl-p4s-bugfix": "lint_pass, tb_updated, sim_pass"}
        (tmp_project / "skill-completion-criteria.json").write_text(json.dumps(criteria))
        config = {"team_mode": True}
        if leader is not None:
            config["leader_session_id"] = leader
        path = tmp_project / ".rat" / "state" / "team-config.json"
        path.write_text(json.dumps(config))
        if leader is not None: _record_team_owner(tmp_project, leader)
        written = time.time() - age_hours * 3600
        os.utime(path, (written, written))
        stdin = {"cwd": str(tmp_project), "hook_event_name": "PostToolUse",
                 "skill": "rtl-agent-team:rtl-p4s-bugfix", **ids}
        run_hook(self.HOOK, stdin, env={"CLAUDE_PLUGIN_ROOT": str(tmp_project)})
        return (tmp_project / ".rat" / "state" / "skill-active.json").exists()

    @pytest.mark.parametrize("ids", [{"session_id": "leader-abc", "agent_id": "teammate-1"},
                                     {"session_id": "worker-1"}], ids=["in-process", "tmux"])
    def test_teammate_reinvoking_the_leaders_skill_keeps_its_loop(self, tmp_project, ids):
        # G6 resets the loop of a re-invoked skill, so the team check must stop a teammate first.
        state = tmp_project / ".rat" / "state" / "skill-active.json"
        state.write_text(json.dumps({"skill": "rtl-p4s-bugfix", "iteration": 3}))
        assert self._invoke_in_team(tmp_project, "leader-abc", **ids)
        assert json.loads(state.read_text())["iteration"] == 3

    def test_in_process_teammate_does_not_start_the_leaders_loop(self, tmp_project):
        # An in-process teammate runs in the leader's session; only its agent_id tells it apart.
        assert not self._invoke_in_team(tmp_project, "leader-abc",
                                        session_id="leader-abc", agent_id="teammate-1")

    def test_leader_starts_its_loop_in_team_mode(self, tmp_project):
        assert self._invoke_in_team(tmp_project, "leader-abc", session_id="leader-abc")

    def test_unknown_session_starts_the_loop_in_team_mode(self, tmp_project):
        # No session_id in the input and (conftest) no session env: the session may be the
        # leader, so the loop starts, as the Stop gates enforce for an unknown session.
        assert self._invoke_in_team(tmp_project, "leader-abc")

    @pytest.mark.parametrize("leader", ["<current_session_id>", "${CLAUDE_SESSION_ID}", ""])
    def test_placeholder_leader_leaves_each_session_its_own_loop(self, tmp_project, leader):
        assert self._invoke_in_team(tmp_project, leader, session_id="worker-1")

    def test_abandoned_team_config_lets_a_new_session_start_its_loop(self, tmp_project):
        # A config last written 3h ago is no team mode, whatever leader it names: the new
        # session's main thread starts its loop, and the stale config is removed.
        assert self._invoke_in_team(tmp_project, "leader-old", age_hours=3, session_id="new-session")
        assert not (tmp_project / ".rat" / "state" / "team-config.json").exists()

    @pytest.mark.parametrize("ids, starts", [({"agent_id": "t1"}, False), ({}, True)],
                             ids=["agent_id", "main-thread"])
    def test_leaderless_team_keeps_agents_off_the_loop(self, tmp_project, ids, starts):
        # Autopilot writes {"team_mode": true} without a leader. An agent_id still never
        # drives the loop; the main thread still manages its own.
        assert self._invoke_in_team(tmp_project, None, **ids) is starts

    @pytest.mark.parametrize("config", [None, {"team_mode": False}], ids=["no-config", "team-mode-false"])
    def test_subagent_outside_team_mode_starts_the_loop(self, tmp_project, config):
        # The agent_id check protects the leader's loop only while a team is active;
        # autopilot's --no-team run writes {"team_mode": false}.
        _setup_marker(tmp_project)
        if config is not None:
            (tmp_project / ".rat" / "state" / "team-config.json").write_text(json.dumps(config))
        criteria = {"rtl-p4s-bugfix": "lint_pass, tb_updated, sim_pass"}
        (tmp_project / "skill-completion-criteria.json").write_text(json.dumps(criteria))
        stdin = {"cwd": str(tmp_project), "hook_event_name": "PostToolUse",
                 "skill": "rtl-agent-team:rtl-p4s-bugfix",
                 "session_id": "leader-abc", "agent_id": "subagent-1"}
        run_hook(self.HOOK, stdin, env={"CLAUDE_PLUGIN_ROOT": str(tmp_project)})
        assert (tmp_project / ".rat" / "state" / "skill-active.json").exists()

    def _criteria_env(self, tmp_project):
        _setup_marker(tmp_project)
        (tmp_project / "skill-completion-criteria.json").write_text(
            json.dumps({"rtl-p4s-bugfix": "lint_pass, tb_updated, sim_pass"})
        )
        return {"CLAUDE_PLUGIN_ROOT": str(tmp_project)}

    def _skill_input(self, tmp_project, event):
        return {
            "cwd": str(tmp_project),
            "hook_event_name": event,
            "tool_name": "Skill",
            "tool_input": {"skill": "rtl-agent-team:rtl-p4s-bugfix"},
        }

    def test_pretooluse_creates_no_state(self, tmp_project):
        env = self._criteria_env(tmp_project)
        result = run_hook(self.HOOK, self._skill_input(tmp_project, "PreToolUse"), env=env)
        assert result["continue"] is True
        assert not (tmp_project / ".rat" / "state" / "skill-active.json").exists()

    def test_posttooluse_creates_state_and_announces_loop(self, tmp_project):
        env = self._criteria_env(tmp_project)
        result = run_hook(self.HOOK, self._skill_input(tmp_project, "PostToolUse"), env=env)
        hso = result["hookSpecificOutput"]
        assert hso["hookEventName"] == "PostToolUse"
        assert "Completion Loop ACTIVATED" in hso["additionalContext"]
        state = json.loads((tmp_project / ".rat" / "state" / "skill-active.json").read_text())
        assert state["skill"] == "rtl-p4s-bugfix"

    def test_announcement_names_the_project_state_file_from_a_subdirectory(self, tmp_project):
        # A relative .rat/state path would send Claude, working in rtl/, to a stray rtl/.rat
        # that the completion gate never reads.
        env = {**self._criteria_env(tmp_project), "CLAUDE_PROJECT_DIR": str(tmp_project)}
        (tmp_project / "rtl").mkdir()
        stdin = {**self._skill_input(tmp_project, "PostToolUse"), "cwd": str(tmp_project / "rtl")}
        result = run_hook(self.HOOK, stdin, env=env)
        state = tmp_project / ".rat" / "state" / "skill-active.json"
        assert result["hookSpecificOutput"]["additionalContext"].endswith(f"set all_complete to true in {state}")
        assert state.exists()

    @pytest.mark.parametrize("missing", ["setup-marker", "rat-dir"])
    def test_posttooluse_before_setup_starts_no_loop(self, tmp_project, missing):
        # PreToolUse only advised setup, so the skill ran. No loop starts, and the answer
        # is a plain PostToolUse continue, without PreToolUse's initialization hint.
        env = {**self._criteria_env(tmp_project), "HOME": str(tmp_project)}
        if missing == "setup-marker":
            (tmp_project / ".claude" / "rules" / "rtl-coding-conventions.md").unlink()
        else:
            shutil.rmtree(tmp_project / ".rat")
        result = run_hook(self.HOOK, self._skill_input(tmp_project, "PostToolUse"), env=env)
        assert result == {"continue": True}
        assert not (tmp_project / ".rat" / "state" / "skill-active.json").exists()


class TestDeniedSkillStartsNoLoop:
    """A Skill call denied at PreToolUse must not leave a completion loop behind."""

    def test_p5b_denied_without_p5a_leaves_no_state(self, tmp_project):
        _setup_marker(tmp_project)
        stdin = {
            "cwd": str(tmp_project),
            "hook_event_name": "PreToolUse",
            "tool_name": "Skill",
            "tool_input": {"skill": "rtl-agent-team:rtl-p5b-silicon-validation"},
        }
        bootstrap = run_hook(HOOKS_DIR / "rtl-phase-state-bootstrap.sh", stdin)
        activation = run_hook(HOOKS_DIR / "rtl-skill-activation.sh", stdin)
        _assert_denied(bootstrap)
        assert "ask the user" in bootstrap["hookSpecificOutput"]["permissionDecisionReason"]
        assert activation["continue"] is True
        assert not (tmp_project / ".rat" / "state" / "skill-active.json").exists()


class TestPhaseStateBootstrap:
    """Tests for hooks/rtl-phase-state-bootstrap.sh."""

    HOOK = HOOKS_DIR / "rtl-phase-state-bootstrap.sh"

    def test_non_target_skill_ignored(self, tmp_project):
        _setup_marker(tmp_project)
        result = run_hook(self.HOOK, accepted_skill_input({"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4-implement"}))
        assert result["continue"] is True
        assert not (tmp_project / ".rat" / "state" / "p4-state.json").exists()

    def test_setup_missing_does_not_bootstrap(self, tmp_project):
        result = run_hook(self.HOOK, accepted_skill_input({"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4-rapid-impl"}), env={"HOME": str(tmp_project)})
        assert result["continue"] is True
        assert not (tmp_project / ".rat" / "state" / "p4-state.json").exists()

    @pytest.mark.parametrize(
        "skill_name,state_file,phase",
        [
            ("rtl-agent-team:rtl-p4-rapid-impl", "p4-state.json", "p4"),
            ("rtl-agent-team:rtl-p5a-functional-closure", "p5a-state.json", "p5a"),
        ],
    )
    def test_target_skill_bootstraps_state(self, tmp_project, skill_name, state_file, phase):
        _setup_marker(tmp_project)
        result = run_hook(self.HOOK, accepted_skill_input({"cwd": str(tmp_project), "skill": skill_name}))
        assert result["continue"] is True

        state_path = tmp_project / ".rat" / "state" / state_file
        assert state_path.exists()
        data = json.loads(state_path.read_text())
        assert data["phase"] == phase
        assert "{{TIMESTAMP}}" not in state_path.read_text()

    def test_same_skill_reinvocation_refreshes_marker_and_drops_prior_report(self, tmp_project):
        """Same-skill re-invocation must (a) refresh compliance-state.json mtime and
        (b) delete any prior-run compliance-report.json outright, so the completion
        gate cannot auto-satisfy compliance-pass from the previous run's PASS
        (regression: phase-only equality + same-second mtime let stale PASS slip)."""
        _setup_marker(tmp_project)
        skill = "rtl-agent-team:rtl-p3-uarch-design"
        run_hook(self.HOOK, accepted_skill_input({"cwd": str(tmp_project), "skill": skill}))
        cs = tmp_project / ".rat" / "state" / "compliance-state.json"
        assert cs.exists(), "compliance-state.json must be bootstrapped for a P3 skill"
        first = json.loads(cs.read_text())
        # Simulate a prior run's compliance report, then age the marker.
        report = tmp_project / ".rat" / "state" / "compliance-report.json"
        report.write_text('{"phase":"rtl-p3-uarch-design","summary":{"verdict":"PASS"}}')
        old = cs.stat().st_mtime - 1000
        os.utime(cs, (old, old))
        # Re-invoke the SAME skill.
        run_hook(self.HOOK, accepted_skill_input({"cwd": str(tmp_project), "skill": skill}))
        assert cs.stat().st_mtime > old, "compliance-state mtime must refresh on re-invocation"
        assert not report.exists(), "prior-run compliance-report.json must be invalidated"
        assert json.loads(cs.read_text())["phase"] == first["phase"]

    def test_phase_change_invalidates_prior_report(self, tmp_project):
        """Switching phase rewrites compliance-state AND drops the prior phase's
        compliance-report.json (no cross-phase auto-satisfy of compliance-pass)."""
        _setup_marker(tmp_project)
        run_hook(self.HOOK, accepted_skill_input({"cwd": str(tmp_project), "skill": "rtl-agent-team:p2-arch-design"}))
        report = tmp_project / ".rat" / "state" / "compliance-report.json"
        report.write_text('{"phase":"p2-arch-design","summary":{"verdict":"PASS"}}')
        # Move to a P3 skill.
        run_hook(self.HOOK, accepted_skill_input({"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p3-uarch-design"}))
        assert not report.exists(), "prior-phase compliance-report.json must be invalidated"
        cs = tmp_project / ".rat" / "state" / "compliance-state.json"
        assert json.loads(cs.read_text())["phase"] == "rtl-p3-uarch-design"

    def test_existing_state_not_overwritten(self, tmp_project):
        _setup_marker(tmp_project)
        state_path = tmp_project / ".rat" / "state" / "p4-state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text('{"phase":"p4","status":"custom"}')

        result = run_hook(self.HOOK, accepted_skill_input({"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4-rapid-impl"}))
        assert result["continue"] is True
        assert json.loads(state_path.read_text())["status"] == "custom"

    def test_p5b_blocks_without_p5a_state(self, tmp_project):
        _setup_marker(tmp_project)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"})
        _assert_denied(result)
        ctx = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "P5B Gate BLOCKED" in ctx
        assert "rtl-p5a-functional-closure" in ctx
        assert not (tmp_project / ".rat" / "state" / "p5b-state.json").exists()

    def test_p5b_deny_from_a_subdirectory_names_the_project_state_file(self, tmp_project):
        # A relative .rat/state path would send Claude, working in rtl/, to a stray rtl/.rat.
        _setup_marker(tmp_project)
        (tmp_project / "rtl").mkdir()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project / "rtl"),
                                      "skill": "rtl-agent-team:rtl-p5b-silicon-validation"},
                          env={"CLAUDE_PROJECT_DIR": str(tmp_project)})
        _assert_denied(result)
        state = tmp_project / ".rat" / "state" / "p5a-state.json"
        assert f"state file {state} not found" in result["hookSpecificOutput"]["permissionDecisionReason"]

    def test_p5b_before_setup_is_not_gated(self, tmp_project):
        # Before rat-init-project the setup advisory speaks; like the template bootstrap,
        # the P5B gate applies only once the project is set up.
        result = run_hook(self.HOOK, accepted_skill_input({"cwd": str(tmp_project),
                                      "skill": "rtl-agent-team:rtl-p5b-silicon-validation"}),
                          env={"HOME": str(tmp_project)})
        assert result["continue"] is True
        assert "permissionDecision" not in result.get("hookSpecificOutput", {})

    def test_p5b_denied_leaves_state_untouched(self, tmp_project):
        """The P5B gate runs before the bootstrap writes: a call it denies keeps the
        current compliance phase and report, and writes no spawn-context manifest."""
        _setup_marker(tmp_project)
        rat = tmp_project / ".rat"
        compliance = rat / "state" / "compliance-state.json"
        compliance.write_text(json.dumps({
            "phase": "p2-arch-design",
            "upstream_iron_paths": ["docs/phase-1-research/iron-requirements.json"],
            "open_requirements_path": "docs/phase-1-research/open-requirements.json",
        }))
        (rat / "state" / "compliance-report.json").write_text('{"verdict": "PASS"}')
        before = compliance.read_bytes()
        snapshot = {p: p.read_bytes() for p in rat.rglob("*") if p.is_file()}
        result = run_hook(self.HOOK, {
            "cwd": str(tmp_project),
            "hook_event_name": "PreToolUse",
            "tool_name": "Skill",
            "tool_input": {"skill": "rtl-agent-team:rtl-p5b-silicon-validation"},
        })
        _assert_denied(result)
        assert "ask the user" in result["hookSpecificOutput"]["permissionDecisionReason"]
        assert compliance.read_bytes() == before
        assert (rat / "state" / "compliance-report.json").exists()
        assert not (rat / "state" / "spawn-context.json").exists()
        assert {p: p.read_bytes() for p in rat.rglob("*") if p.is_file()} == snapshot

    def test_p5b_blocks_when_p5a_verdict_not_pass(self, tmp_project):
        _setup_marker(tmp_project)
        p5a_state = tmp_project / ".rat" / "state" / "p5a-state.json"
        p5a_state.parent.mkdir(parents=True, exist_ok=True)
        p5a_state.write_text(
            json.dumps({"gates": {"p5a_exit": {"verdict": "fail"}}}, indent=2)
        )

        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"})
        _assert_denied(result)
        ctx = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "gates.p5a_exit.verdict=fail" in ctx
        assert "ask the user" in ctx.lower()
        assert not (tmp_project / ".rat" / "state" / "p5b-state.json").exists()

    def test_p5b_bootstraps_when_p5a_pass(self, tmp_project):
        _setup_marker(tmp_project)
        p5a_state = tmp_project / ".rat" / "state" / "p5a-state.json"
        p5a_state.parent.mkdir(parents=True, exist_ok=True)
        p5a_state.write_text(
            json.dumps({"gates": {"p5a_exit": {"verdict": "pass"}}}, indent=2)
        )

        result = run_hook(self.HOOK, accepted_skill_input({"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"}))
        assert result["continue"] is True
        state_path = tmp_project / ".rat" / "state" / "p5b-state.json"
        assert state_path.exists()
        assert json.loads(state_path.read_text())["phase"] == "p5b"

    def test_p5b_blocks_when_rtl_changed_after_p5a_pass(self, tmp_project):
        _setup_marker(tmp_project)

        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        p5a_state = state_dir / "p5a-state.json"
        p5a_state.write_text(json.dumps({"gates": {"p5a_exit": {"verdict": "pass"}}}, indent=2))
        # Use explicit mtime to avoid flaky time.sleep
        os.utime(str(p5a_state), (1000000, 1000000))

        rtl_dir = tmp_project / "rtl"
        rtl_dir.mkdir(parents=True, exist_ok=True)
        (rtl_dir / "top.sv").write_text("module top; endmodule\n")
        os.utime(str(rtl_dir / "top.sv"), (1000002, 1000002))
        _track((state_dir / "rtl-modified-files.txt"), "rtl/top.sv\n")

        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"})
        _assert_denied(result)
        ctx = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "stale functional closure" in ctx
        assert "ask the user" in ctx.lower()
        assert not (state_dir / "p5b-state.json").exists()

    def test_p5b_allows_when_p5a_newer_than_tracked_rtl_changes(self, tmp_project):
        _setup_marker(tmp_project)

        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        rtl_dir = tmp_project / "rtl"
        rtl_dir.mkdir(parents=True, exist_ok=True)
        (rtl_dir / "top.sv").write_text("module top; endmodule\n")
        _track((state_dir / "rtl-modified-files.txt"), "rtl/top.sv\n")
        os.utime(str(rtl_dir / "top.sv"), (1000000, 1000000))

        p5a_state = state_dir / "p5a-state.json"
        p5a_state.write_text(json.dumps({"gates": {"p5a_exit": {"verdict": "pass"}}}, indent=2))
        # Use explicit mtime: p5a newer than RTL
        os.utime(str(p5a_state), (1000002, 1000002))

        result = run_hook(self.HOOK, accepted_skill_input({"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"}))
        assert result["continue"] is True
        assert (state_dir / "p5b-state.json").exists()

    def test_missing_json_parser_emits_setup_hint_with_fallback(self, tmp_project):
        _setup_marker(tmp_project)
        result = run_hook(
            self.HOOK,
            accepted_skill_input({"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4-rapid-impl"}),
            env={"RTL_FORCE_JSON_FALLBACK": "1"},
        )
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "fallback" in ctx
        assert "/rtl-agent-team:rat-init-project" in ctx

    def test_parser_uses_top_level_skill_key(self, tmp_project):
        _setup_marker(tmp_project)
        raw_input = json.dumps(
            {
                "cwd": str(tmp_project),
                "skill": "rtl-agent-team:rtl-p4-rapid-impl",
                "meta": {"skill": "rtl-agent-team:rtl-p5b-silicon-validation"},
            }
        )

        result = run_hook(self.HOOK, accepted_skill_input(raw_input))
        assert result["continue"] is True
        assert (tmp_project / ".rat" / "state" / "p4-state.json").exists()
        assert not (tmp_project / ".rat" / "state" / "p5b-state.json").exists()


class TestHookConcurrency:
    """Tests for concurrent hook execution with flock-util protection."""

    EDIT_TRACKER = HOOKS_DIR / "rtl-edit-tracker.sh"
    SKILL_GATE = HOOKS_DIR / "rtl-skill-completion-gate.sh"

    def test_concurrent_edit_tracker_no_duplicates(self, tmp_project):
        """5 parallel edit-tracker calls for different files → no lost entries."""
        files = [f"rtl/mod_{i}.sv" for i in range(5)]

        def track_file(f):
            return run_hook(self.EDIT_TRACKER, {"cwd": str(tmp_project), "file_path": f})

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(track_file, f) for f in files]
            results = [fut.result() for fut in as_completed(futures)]

        # All should succeed
        for r in results:
            assert r.get("continue") is True

        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert track_file.exists()
        lines = sorted(l for l in track_file.read_text().splitlines() if l.strip())
        assert lines == sorted(files), f"Expected {sorted(files)}, got {lines}"

    def test_concurrent_edit_tracker_same_file_no_duplicates(self, tmp_project):
        """5 parallel edit-tracker calls for the SAME file → exactly 1 entry."""
        def track_same():
            return run_hook(self.EDIT_TRACKER, {"cwd": str(tmp_project), "file_path": "rtl/top.sv"})

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = [pool.submit(track_same) for _ in range(5)]
            [fut.result() for fut in as_completed(futures)]

        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        lines = [l for l in track_file.read_text().splitlines() if l.strip()]
        assert lines.count("rtl/top.sv") == 1

    def test_concurrent_skill_completion_gate_counter_accuracy(self, tmp_project):
        """3 parallel skill-completion-gate calls → iteration increments correctly."""

        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        state = {
            "skill": "rtl-p4s-bugfix",
            "active": True,
            "iteration": 1,
            "max_iterations": 10,
            "pending": "lint_pass",
            "all_complete": False,
            "started_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "use_escalation_ladder": True,
            "strategy": "primary"
        }
        (state_dir / "skill-active.json").write_text(json.dumps(state, indent=2))

        def run_gate():
            return run_hook(self.SKILL_GATE, {"cwd": str(tmp_project)})

        # Run 3 calls sequentially (parallel would be racy by design — we test lock correctness)
        for _ in range(3):
            result = run_gate()
            _assert_stop_blocked(result)

        final_state = json.loads((state_dir / "skill-active.json").read_text())
        assert final_state["iteration"] == 1, "A Stop reminder must not schedule another iteration"


class TestTeamAwarenessGuard:
    """Tests for team-awareness guard in Stop hooks."""

    HOOKS = {
        "stop-gate": HOOKS_DIR / "stop-gate.sh",
        "verify-stop-gate": HOOKS_DIR / "rtl-verify-stop-gate.sh",
        "p6-cascade-gate": HOOKS_DIR / "rtl-p6-cascade-gate.sh",
        "skill-completion-gate": HOOKS_DIR / "rtl-skill-completion-gate.sh",
    }

    def _write_team_config(self, tmp_project, team_mode=True, leader_id="leader-session-123"):

        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "team_mode": team_mode,
            "team_name": "test-team",
            "leader_session_id": leader_id,
            "phase": "p5",
            "created_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        (state_dir / "team-config.json").write_text(json.dumps(config, indent=2))
        _record_team_owner(tmp_project, leader_id)

    def test_no_team_config_normal_behavior_stop_gate(self, tmp_project):
        """Without team config, stop-gate works normally (allow exit when no state)."""
        result = run_hook(self.HOOKS["stop-gate"], {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_no_team_config_normal_behavior_verify(self, tmp_project):
        """Without team config, verify gate works normally."""
        result = run_hook(self.HOOKS["verify-stop-gate"], {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_no_team_config_normal_behavior_p6(self, tmp_project):
        """Without team config, P6 cascade gate works normally."""
        result = run_hook(self.HOOKS["p6-cascade-gate"], {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_no_team_config_normal_behavior_skill(self, tmp_project):
        """Without team config, skill completion gate works normally."""
        result = run_hook(self.HOOKS["skill-completion-gate"], {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_worker_session_bypasses_stop_gate(self, tmp_project):
        """Worker (non-leader) in team mode → stop gate allows exit."""
        self._write_team_config(tmp_project, leader_id="leader-abc")
        # Create blocking state
        state_dir = tmp_project / ".rat" / "state"
        state = {"status": "in_progress", "orchestration_control": {
            "active_gate_id": "test", "active_gate_retry_limit": 2,
            "active_gate_primary_attempts": 0, "active_gate_fallback_attempts": 0,
            "active_gate_last_chance_attempts": 0, "needs_user_decision": False
        }}
        (state_dir / "rat-auto-design-state.json").write_text(json.dumps(state))
        # Worker session (its session id differs from the leader's)
        result = run_hook(self.HOOKS["stop-gate"], {"cwd": str(tmp_project), "session_id": "worker-1"})
        assert result["continue"] is True

    def test_leader_session_still_blocked_by_stop_gate(self, tmp_project):
        """Leader session in team mode → stop gate still blocks."""
        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rat" / "state"
        state = {"status": "in_progress", "orchestration_control": {
            "active_gate_id": "test", "active_gate_retry_limit": 2,
            "active_gate_primary_attempts": 0, "active_gate_fallback_attempts": 0,
            "active_gate_last_chance_attempts": 0, "needs_user_decision": False
        }}
        (state_dir / "rat-auto-design-state.json").write_text(json.dumps(state))
        result = run_hook(self.HOOKS["stop-gate"], {"cwd": str(tmp_project), "session_id": "leader-abc"})
        _assert_stop_blocked(result)

    def test_worker_bypasses_verify_gate(self, tmp_project):
        """Worker in team mode → verify gate allows exit even with tracked files."""
        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/top.sv\n")
        result = run_hook(self.HOOKS["verify-stop-gate"], {"cwd": str(tmp_project), "session_id": "worker-1"})
        assert result["continue"] is True

    def test_worker_bypasses_p6_cascade(self, tmp_project):
        """Worker in team mode → P6 cascade allows exit even with stale marker."""
        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOKS["p6-cascade-gate"], {"cwd": str(tmp_project), "session_id": "worker-1"})
        assert result["continue"] is True

    def test_worker_bypasses_skill_completion(self, tmp_project):
        """Worker in team mode → skill completion gate allows exit."""

        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rat" / "state"
        skill_state = {
            "skill": "rtl-p4s-bugfix", "active": True, "iteration": 1,
            "max_iterations": 5, "pending": "lint_pass", "all_complete": False,
            "started_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        (state_dir / "skill-active.json").write_text(json.dumps(skill_state))
        result = run_hook(self.HOOKS["skill-completion-gate"], {"cwd": str(tmp_project), "session_id": "worker-1"})
        assert result["continue"] is True

    def test_leader_session_still_blocked_by_verify_gate(self, tmp_project):
        """Leader session in team mode → verify gate still blocks."""
        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/top.sv\n")
        result = run_hook(self.HOOKS["verify-stop-gate"], {"cwd": str(tmp_project), "session_id": "leader-abc"})
        _assert_stop_blocked(result)

    def test_leader_session_still_blocked_by_p6_cascade(self, tmp_project):
        """Leader session in team mode → P6 cascade gate still blocks."""
        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOKS["p6-cascade-gate"], {"cwd": str(tmp_project), "session_id": "leader-abc"})
        _assert_stop_blocked(result)

    def test_leader_session_still_blocked_by_skill_completion(self, tmp_project):
        """Leader session in team mode → skill completion gate still blocks."""

        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rat" / "state"
        skill_state = {
            "skill": "rtl-p4s-bugfix", "active": True, "iteration": 1,
            "max_iterations": 5, "pending": "lint_pass", "all_complete": False,
            "started_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        (state_dir / "skill-active.json").write_text(json.dumps(skill_state))
        result = run_hook(self.HOOKS["skill-completion-gate"], {"cwd": str(tmp_project), "session_id": "leader-abc"})
        _assert_stop_blocked(result)

    def test_empty_leader_id_enforces_gate_fail_closed(self, tmp_project):
        """Empty leader_session_id with team_mode=true → fail-closed, gate enforced for all."""
        self._write_team_config(tmp_project, leader_id="")
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOKS["p6-cascade-gate"], {"cwd": str(tmp_project), "session_id": "worker-1"})
        _assert_stop_blocked(result)

    @pytest.mark.parametrize("created_at", [None, "<ISO_TIMESTAMP>", "2020-01-01T00:00:00Z"],
                             ids=["no-created_at", "placeholder", "old-utc"])
    def test_stale_team_config_removed_and_gate_applies(self, tmp_project, created_at):
        """team-config.json last written over 2h ago → removed, normal gate behavior resumes.
        The age is the file's mtime: the model-written created_at may be missing, a
        placeholder or local time."""
        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        stale_config = {
            "team_mode": True,
            "team_name": "p5-verify",
            "leader_session_id": "leader-old",
            "phase": "p5",
        }
        if created_at is not None:
            stale_config["created_at"] = created_at
        config = state_dir / "team-config.json"
        config.write_text(json.dumps(stale_config, indent=2))
        three_hours_ago = time.time() - 3 * 3600
        os.utime(config, (three_hours_ago, three_hours_ago))
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOKS["p6-cascade-gate"], {"cwd": str(tmp_project), "session_id": "new-session"})
        # Stale config removed → gate blocks as normal
        _assert_stop_blocked(result)
        assert not config.exists()

    def test_config_refreshed_during_the_staleness_check_is_kept(self, tmp_project):
        """A team skill that rewrites a stale config while the gate judges it must not lose
        the new config: the gate re-reads the mtime before removing the file."""
        config = tmp_project / ".rat" / "state" / "team-config.json"
        config.write_text(json.dumps({"team_mode": True, "leader_session_id": "leader-abc"}))
        _record_team_owner(tmp_project, "leader-abc")
        three_hours_ago = time.time() - 3 * 3600
        os.utime(config, (three_hours_ago, three_hours_ago))
        # get_mtime_epoch as in posix-util.sh, except that the writer refreshes the config
        # right after the gate's first read.
        script = f"""
. "{HOOKS_DIR}/lib/json-util.sh"
. "{HOOKS_DIR}/lib/posix-util.sh"
. "{HOOKS_DIR}/lib/team-gate-util.sh"
jsonu_detect_parser
get_mtime_epoch() {{
  _m=$(stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null)
  [ -e "$1.refreshed" ] || {{ : > "$1.refreshed"; touch "$1"; }}
  printf '%s' "$_m"
}}
teamu_should_skip_gate "{config.parent}" '{{"session_id":"worker-1"}}'
echo "rc=$?"
"""
        result = subprocess.run(["sh", "-c", script], capture_output=True, text=True, timeout=10)
        assert result.stdout.strip() == "rc=1", result  # judged stale: enforced this once
        assert config.exists()

    @pytest.mark.parametrize("age_hours", [0, 1.5])
    def test_fresh_team_config_stays_despite_an_old_created_at(self, tmp_project, age_hours):
        """A config last written under 2h ago is team mode whatever its created_at says."""
        state_dir = tmp_project / ".rat" / "state"
        config = state_dir / "team-config.json"
        config.write_text(json.dumps({"team_mode": True, "leader_session_id": "leader-abc",
                                      "created_at": "2020-01-01T00:00:00Z"}))
        _record_team_owner(tmp_project, "leader-abc")
        written = time.time() - age_hours * 3600
        os.utime(config, (written, written))
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOKS["p6-cascade-gate"], {"cwd": str(tmp_project), "session_id": "worker-1"})
        assert result == {"continue": True}
        assert config.exists()

    def test_team_mode_false_does_not_bypass(self, tmp_project):
        """team_mode=false → no bypass, normal behavior."""
        self._write_team_config(tmp_project, team_mode=False, leader_id="leader-abc")
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOKS["p6-cascade-gate"], {"cwd": str(tmp_project), "session_id": "worker-1"})
        _assert_stop_blocked(result)

    def test_stop_hooks_use_shared_team_gate_util(self):
        for _, hook_path in self.HOOKS.items():
            content = hook_path.read_text()
            assert "lib/team-gate-util.sh" in content
            assert "teamu_should_skip_gate" in content

    def test_team_skip_callers_source_posix_util_first(self):
        # The teamu_* helpers read the config's mtime with the posix-util.sh helpers.
        callers = [p for p in sorted(HOOKS_DIR.glob("*.sh")) if "teamu_" in p.read_text()]
        assert {p.name for p in callers} >= {"rtl-edit-tracker.sh", "rtl-skill-activation.sh"}
        for path in callers:
            lines = path.read_text().splitlines()
            call = next(i for i, line in enumerate(lines)
                        if "teamu_" in line and not line.lstrip().startswith("#"))
            for lib in ("posix-util.sh", "team-gate-util.sh"):
                assert lines.index(f'. "$SCRIPT_DIR/lib/{lib}"') < call, (path.name, lib)

    def test_leader_from_the_hook_input_is_enforced(self, tmp_project):
        self._write_team_config(tmp_project, leader_id="leader-abc")
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"), "rtl/a.sv\n")
        result = run_hook(self.HOOKS["verify-stop-gate"],
                          {"cwd": str(tmp_project), "session_id": "leader-abc"})
        _assert_stop_blocked(result)

    def test_worker_from_the_hook_input_skips(self, tmp_project):
        self._write_team_config(tmp_project, leader_id="leader-abc")
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"), "rtl/a.sv\n")
        result = run_hook(self.HOOKS["verify-stop-gate"],
                          {"cwd": str(tmp_project), "session_id": "worker-1"})
        assert result == {"continue": True}

    def test_session_from_claude_code_env_when_the_input_has_none(self, tmp_project):
        self._write_team_config(tmp_project, leader_id="leader-abc")
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"), "rtl/a.sv\n")
        result = run_hook(self.HOOKS["verify-stop-gate"], {"cwd": str(tmp_project)},
                          env={"CLAUDE_CODE_SESSION_ID": "leader-abc"})
        _assert_stop_blocked(result)

    @pytest.mark.parametrize("var", ["CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID"])
    def test_worker_from_the_env_skips(self, tmp_project, var):
        # The gate enforces a leader and an unknown session alike, so only a worker shows
        # that the env was read.
        self._write_team_config(tmp_project, leader_id="leader-abc")
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"), "rtl/a.sv\n")
        result = run_hook(self.HOOKS["verify-stop-gate"], {"cwd": str(tmp_project)},
                          env={var: "worker-1"})
        assert result == {"continue": True}

    @pytest.mark.parametrize("stdin, env", [
        ({"session_id": "leader-abc"}, {"CLAUDE_CODE_SESSION_ID": "worker-1"}),
        ({}, {"CLAUDE_CODE_SESSION_ID": "leader-abc", "CLAUDE_SESSION_ID": "worker-1"}),
    ])
    def test_session_sources_in_order(self, tmp_project, stdin, env):
        # The input's session_id, then CLAUDE_CODE_SESSION_ID, then the legacy CLAUDE_SESSION_ID.
        # The first source present names the leader, so the gate must block.
        self._write_team_config(tmp_project, leader_id="leader-abc")
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"), "rtl/a.sv\n")
        result = run_hook(self.HOOKS["verify-stop-gate"], {"cwd": str(tmp_project), **stdin},
                          env=env)
        _assert_stop_blocked(result)

    def test_unknown_session_enforces_the_gate(self, tmp_project):
        self._write_team_config(tmp_project, leader_id="leader-abc")
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"), "rtl/a.sv\n")
        result = run_hook(self.HOOKS["verify-stop-gate"], {"cwd": str(tmp_project)})
        _assert_stop_blocked(result)

    @pytest.mark.parametrize("leader", ["<current_session_id>", "${CLAUDE_SESSION_ID}", ""])
    def test_placeholder_leader_enforces_for_everyone(self, tmp_project, leader):
        self._write_team_config(tmp_project, leader_id=leader)
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"), "rtl/a.sv\n")
        result = run_hook(self.HOOKS["verify-stop-gate"],
                          {"cwd": str(tmp_project), "session_id": "worker-1"})
        _assert_stop_blocked(result)


class TestSedFallbackContract:
    """Contract tests verifying all 4 stop hooks work correctly under sed fallback mode.

    RTL_FORCE_JSON_FALLBACK=1 forces json-util.sh to use sed-only parsing,
    ensuring hooks degrade gracefully when jq/python are unavailable.
    """

    FALLBACK_ENV = {"RTL_FORCE_JSON_FALLBACK": "1"}

    HOOKS = {
        "stop-gate": HOOKS_DIR / "stop-gate.sh",
        "verify-stop-gate": HOOKS_DIR / "rtl-verify-stop-gate.sh",
        "p6-cascade-gate": HOOKS_DIR / "rtl-p6-cascade-gate.sh",
        "skill-completion-gate": HOOKS_DIR / "rtl-skill-completion-gate.sh",
    }

    # ── stop-gate ────────────────────────────────────────────────────────────

    def test_stop_gate_fallback_allows_clean_exit(self, tmp_project):
        """No autopilot state → continue=true under sed fallback."""
        result = run_hook(
            self.HOOKS["stop-gate"],
            {"cwd": str(tmp_project)},
            env=self.FALLBACK_ENV,
        )
        assert result["continue"] is True

    def test_stop_gate_fallback_blocks_active(self, tmp_project):
        """Active autopilot state → blocked under sed fallback."""
        state_dir = tmp_project / ".rat" / "state"
        state_file = state_dir / "rat-auto-design-state.json"
        state_file.write_text(json.dumps({"status": "in_progress", "phase": 3}, indent=2))
        result = run_hook(
            self.HOOKS["stop-gate"],
            {"cwd": str(tmp_project)},
            env=self.FALLBACK_ENV,
        )
        _assert_stop_blocked(result)

    # ── verify-stop-gate ─────────────────────────────────────────────────────

    def test_verify_gate_fallback_blocks_unverified(self, tmp_project):
        """Tracked files without verification → blocked under sed fallback."""
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/module/top.sv\n")
        result = run_hook(
            self.HOOKS["verify-stop-gate"],
            {"cwd": str(tmp_project)},
            env=self.FALLBACK_ENV,
        )
        _assert_stop_blocked(result)

    def test_verify_gate_fallback_allows_verified(self, tmp_project):
        """Tracked files with verify-done → continue=true under sed fallback."""
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/module/top.sv\n")
        _record_passing_evidence(tmp_project)
        result = run_hook(
            self.HOOKS["verify-stop-gate"],
            {"cwd": str(tmp_project)},
            env=self.FALLBACK_ENV,
        )
        assert result["continue"] is True

    # ── p6-cascade-gate ──────────────────────────────────────────────────────

    def test_p6_cascade_fallback_blocks_stale(self, tmp_project):
        """phase6-stale marker → blocked under sed fallback."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(
            self.HOOKS["p6-cascade-gate"],
            {"cwd": str(tmp_project)},
            env=self.FALLBACK_ENV,
        )
        _assert_stop_blocked(result)

    def test_p6_cascade_fallback_allows_clean(self, tmp_project):
        """No stale marker → continue=true under sed fallback."""
        result = run_hook(
            self.HOOKS["p6-cascade-gate"],
            {"cwd": str(tmp_project)},
            env=self.FALLBACK_ENV,
        )
        assert result["continue"] is True

    # ── skill-completion-gate ────────────────────────────────────────────────

    def test_skill_completion_fallback_blocks_active(self, tmp_project):
        """Active skill state → blocked under sed fallback."""

        state_dir = tmp_project / ".rat" / "state"
        state = {
            "skill": "rtl-p4s-bugfix",
            "active": True,
            "iteration": 1,
            "max_iterations": 5,
            "pending": "lint_pass, sim_pass",
            "all_complete": False,
            "started_at": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        }
        (state_dir / "skill-active.json").write_text(json.dumps(state, indent=2))
        result = run_hook(
            self.HOOKS["skill-completion-gate"],
            {"cwd": str(tmp_project)},
            env=self.FALLBACK_ENV,
        )
        _assert_stop_blocked(result)

    def test_skill_completion_fallback_allows_complete(self, tmp_project):
        """all_complete=true → continue=true under sed fallback."""

        state_dir = tmp_project / ".rat" / "state"
        state = {
            "skill": "rtl-p4s-bugfix",
            "active": True,
            "iteration": 3,
            "max_iterations": 5,
            "pending": "",
            "all_complete": True,
            "started_at": datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        }
        (state_dir / "skill-active.json").write_text(json.dumps(state, indent=2))
        result = run_hook(
            self.HOOKS["skill-completion-gate"],
            {"cwd": str(tmp_project)},
            env=self.FALLBACK_ENV,
        )
        assert result["continue"] is True


class TestSpawnContextManifest:
    """Tests for spawn context manifest written by rtl-phase-state-bootstrap.sh."""

    HOOK = HOOKS_DIR / "rtl-phase-state-bootstrap.sh"

    def _invoke(self, tmp_project, skill_name, env=None):
        return run_hook(
            self.HOOK,
            accepted_skill_input({"skill": f"rtl-agent-team:{skill_name}", "cwd": str(tmp_project)}),
            env=env,
        )

    def _read_manifest(self, tmp_project):
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        assert mpath.exists(), "spawn-context.json not written"
        return json.loads(mpath.read_text())

    def _setup_project(self, tmp_project):
        """Create setup marker so setup.completed=true."""
        rules = tmp_project / ".claude" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "rtl-coding-conventions.md").touch()

    # ── Core manifest tests ──────────────────────────────────────────────

    def test_manifest_written_for_p4_skill(self, tmp_project):
        """P4 skill invocation writes spawn-context.json."""
        self._setup_project(tmp_project)
        (tmp_project / "docs" / "phase-3-uarch").mkdir(parents=True)
        (tmp_project / "docs" / "phase-3-uarch" / "module.md").touch()
        (tmp_project / "docs" / "phase-1-research").mkdir(parents=True)
        (tmp_project / "docs" / "phase-1-research" / "io_definition.json").write_text("{}")

        result = self._invoke(tmp_project, "rtl-p4-implement")
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "[Spawn Context]" in ctx

        m = self._read_manifest(tmp_project)
        assert m["schema_version"] == "1.0"
        assert m["pipeline"]["current_phase"] == 4
        assert m["pipeline"]["skill_invoked"] == "rtl-p4-implement"

    def test_manifest_schema_valid(self, tmp_project):
        """Manifest contains all required top-level keys."""
        self._setup_project(tmp_project)
        self._invoke(tmp_project, "rtl-p5-verify")

        m = self._read_manifest(tmp_project)
        required_keys = {
            "schema_version", "generated_at", "generated_by", "plugin_root",
            "project_root", "setup", "pipeline", "upstream_artifacts",
            "staleness", "team", "quality_gates",
        }
        assert required_keys.issubset(set(m.keys()))
        assert "required" in m["upstream_artifacts"]
        assert "optional" in m["upstream_artifacts"]
        assert "all_required_present" in m["upstream_artifacts"]

    def test_manifest_plugin_root_is_absolute_path(self, tmp_project):
        """v0.12.0: manifest exposes plugin_root as a non-empty absolute path
        string (derived from CLAUDE_PLUGIN_ROOT or the hooks/ parent)."""
        self._setup_project(tmp_project)
        self._invoke(
            tmp_project, "rtl-p4-implement",
            env={"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)},
        )
        m = self._read_manifest(tmp_project)
        assert isinstance(m["plugin_root"], str)
        assert m["plugin_root"], "plugin_root must be non-empty"
        assert os.path.isabs(m["plugin_root"]), (
            f"plugin_root must be an absolute path: {m['plugin_root']!r}"
        )

    def test_manifest_project_root_defaults_to_cwd(self, tmp_project):
        """v0.13.x: without RAT_PROJECT_ROOT, project_root is the project root the
        hook resolved (here also the session CWD). Empty env value counts as unset
        (${RAT_PROJECT_ROOT:-} guard)."""
        self._setup_project(tmp_project)
        self._invoke(
            tmp_project, "rtl-p4-implement", env={"RAT_PROJECT_ROOT": ""},
        )
        m = self._read_manifest(tmp_project)
        assert m["project_root"] == str(tmp_project)

    def test_manifest_project_root_honors_env_override(
        self, tmp_project, tmp_path_factory
    ):
        """v0.13.x: RAT_PROJECT_ROOT set to an existing project dir → manifest
        lands under the override root with project_root carrying the override,
        even when the hook's session cwd points elsewhere (external Workflow
        driver scenario)."""
        self._setup_project(tmp_project)
        elsewhere = tmp_path_factory.mktemp("driver-cwd")
        result = run_hook(
            self.HOOK,
            accepted_skill_input({"skill": "rtl-agent-team:rtl-p4-implement", "cwd": str(elsewhere)}),
            env={"RAT_PROJECT_ROOT": str(tmp_project)},
        )
        assert result["continue"] is True
        m = self._read_manifest(tmp_project)
        assert m["project_root"] == str(tmp_project)
        # Setup marker resolved against the override root, not the driver cwd.
        assert m["setup"]["completed"] is True
        # Nothing leaked into the driver cwd.
        assert not (elsewhere / ".rat").exists()

    def test_manifest_project_root_bogus_env_falls_back(self, tmp_project):
        """v0.13.x: RAT_PROJECT_ROOT pointing at a non-directory is ignored
        (-d guard, matching rat-dir-util.sh) — identical to unset."""
        self._setup_project(tmp_project)
        self._invoke(
            tmp_project, "rtl-p4-implement",
            env={"RAT_PROJECT_ROOT": str(tmp_project / "does-not-exist")},
        )
        m = self._read_manifest(tmp_project)
        assert m["project_root"] == str(tmp_project)

    def test_manifest_detects_missing_artifacts(self, tmp_project):
        """Missing required upstream → all_required_present=false."""
        self._setup_project(tmp_project)
        # P6 requires reviews/phase-5-verify/final-compliance.md — not created
        self._invoke(tmp_project, "rtl-p6-design-review")

        m = self._read_manifest(tmp_project)
        assert m["upstream_artifacts"]["all_required_present"] is False
        missing = [a for a in m["upstream_artifacts"]["required"] if not a["exists"]]
        assert len(missing) > 0
        assert any("final-compliance" in a["path"] for a in missing)

    def test_manifest_detects_present_artifacts(self, tmp_project):
        """All required upstream present → all_required_present=true."""
        self._setup_project(tmp_project)
        p5dir = tmp_project / "reviews" / "phase-5-verify"
        p5dir.mkdir(parents=True)
        (p5dir / "final-compliance.md").write_text("verdict: PASS")

        self._invoke(tmp_project, "rtl-p6-design-review")

        m = self._read_manifest(tmp_project)
        assert m["upstream_artifacts"]["all_required_present"] is True

    def test_manifest_staleness_populated(self, tmp_project):
        """RTL tracking file → staleness section reflects modified count."""
        self._setup_project(tmp_project)
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/a.sv\nrtl/b.sv\n")

        self._invoke(tmp_project, "rtl-p4-implement")

        m = self._read_manifest(tmp_project)
        assert m["staleness"]["rtl_modified_count"] == 2
        assert m["staleness"]["rtl_verify_done"] is False

    def test_manifest_staleness_verify_done(self, tmp_project):
        """rtl-verify-done marker → staleness.rtl_verify_done=true."""
        self._setup_project(tmp_project)
        state_dir = tmp_project / ".rat" / "state"
        _track((state_dir / "rtl-modified-files.txt"), "rtl/a.sv\n")
        (state_dir / "rtl-verify-done").touch()

        self._invoke(tmp_project, "rtl-p4-implement")

        m = self._read_manifest(tmp_project)
        assert m["staleness"]["rtl_verify_done"] is True

    def test_manifest_team_mode(self, tmp_project):
        """team-config.json present → team section populated."""
        self._setup_project(tmp_project)
        state_dir = tmp_project / ".rat" / "state"
        team_cfg = {
            "team_mode": True,
            "leader_session_id": "sess-abc-123",
            "created_at": "2026-03-05T12:00:00Z",
        }
        (state_dir / "team-config.json").write_text(json.dumps(team_cfg))

        self._invoke(tmp_project, "rtl-p4-implement")

        m = self._read_manifest(tmp_project)
        assert m["team"]["active"] is True
        assert m["team"]["leader_session_id"] == "sess-abc-123"

    def test_manifest_not_written_for_non_rtl_skill(self, tmp_project):
        """Non-rtl-agent-team skill → no manifest, no crash."""
        result = run_hook(
            self.HOOK,
            accepted_skill_input({"skill": "other-plugin:some-skill", "cwd": str(tmp_project)}),
        )
        assert result["continue"] is True
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        assert not mpath.exists()

    def test_manifest_not_written_for_non_phase_skill(self, tmp_project):
        """RTL skill without phase mapping (e.g. lint-check) → no manifest."""
        self._setup_project(tmp_project)
        self._invoke(tmp_project, "rtl-lint-check")

        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        assert not mpath.exists()

    def test_manifest_setup_false_when_marker_missing(self, tmp_project):
        """No setup marker → setup.completed=false in manifest."""
        self._invoke(tmp_project, "rtl-p4-implement", env={"HOME": str(tmp_project)})

        m = self._read_manifest(tmp_project)
        assert m["setup"]["completed"] is False

    def test_manifest_quality_gates(self, tmp_project):
        """Quality gates reflect phase artifact existence."""
        self._setup_project(tmp_project)
        # Create P1 + P2 artifacts
        p1 = tmp_project / "docs" / "phase-1-research"
        p1.mkdir(parents=True)
        (p1 / "requirements.json").write_text("{}")
        p2 = tmp_project / "docs" / "phase-2-architecture"
        p2.mkdir(parents=True)
        (p2 / "architecture.md").touch()

        self._invoke(tmp_project, "rtl-p4-implement")

        m = self._read_manifest(tmp_project)
        assert m["quality_gates"]["p1_passed"] is True
        assert m["quality_gates"]["p2_passed"] is True
        assert m["quality_gates"]["p3_passed"] is False
        assert m["quality_gates"]["p4_passed"] is False

    def test_manifest_performance(self, tmp_project):
        """Hook execution completes within 3s timeout."""
        self._setup_project(tmp_project)
        start = time.time()
        self._invoke(tmp_project, "rtl-p4-implement")
        elapsed = time.time() - start
        assert elapsed < 3.0, f"Hook took {elapsed:.2f}s, exceeds 3s budget"

    def test_manifest_overwrites_on_subsequent_invoke(self, tmp_project):
        """Second skill invocation overwrites the manifest."""
        self._setup_project(tmp_project)
        self._invoke(tmp_project, "p1-spec-research")
        m1 = self._read_manifest(tmp_project)
        assert m1["pipeline"]["current_phase"] == 1

        self._invoke(tmp_project, "rtl-p4-implement")
        m2 = self._read_manifest(tmp_project)
        assert m2["pipeline"]["current_phase"] == 4

    def test_manifest_p5a_verdict_from_state(self, tmp_project):
        """p5a_verdict populated from p5a-state.json."""
        self._setup_project(tmp_project)
        state_dir = tmp_project / ".rat" / "state"
        p5a_state = {
            "gates": {"p5a_exit": {"verdict": "pass"}},
        }
        (state_dir / "p5a-state.json").write_text(json.dumps(p5a_state))

        self._invoke(tmp_project, "rtl-p6-design-review")

        m = self._read_manifest(tmp_project)
        assert m["quality_gates"]["p5a_verdict"] == "pass"

    def test_manifest_setup_refreshed_after_rtl_setup(self, tmp_project):
        """rat-init-project skill refreshes existing manifest with setup.completed=true."""
        # First: invoke P4 without setup marker → setup.completed=false
        self._invoke(tmp_project, "rtl-p4-implement", env={"HOME": str(tmp_project)})
        m1 = self._read_manifest(tmp_project)
        assert m1["setup"]["completed"] is False
        assert m1["pipeline"]["current_phase"] == 4

        # Simulate rat-init-project creating the marker
        self._setup_project(tmp_project)

        # Invoke rat-init-project skill → should refresh existing manifest
        result = self._invoke(tmp_project, "rat-init-project")
        m2 = self._read_manifest(tmp_project)
        assert m2["setup"]["completed"] is True
        # Phase context preserved from original invocation
        assert m2["pipeline"]["current_phase"] == 4
        assert m2["pipeline"]["skill_invoked"] == "rtl-p4-implement"
        # Summary message must show actual phase, not empty
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "Phase 4" in ctx
        assert "setup=OK" in ctx


class TestSpawnContextAgent:
    """Tests for rtl-spawn-context.sh (PreToolUse:Agent hook)."""

    HOOK = HOOKS_DIR / "rtl-spawn-context.sh"

    def _invoke(self, tmp_project, agent_type):
        return run_hook(
            self.HOOK,
            {"subagent_type": f"rtl-agent-team:{agent_type}", "cwd": str(tmp_project)},
        )

    def _read_manifest(self, tmp_project):
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        assert mpath.exists(), "spawn-context.json not written"
        return json.loads(mpath.read_text())

    def test_agent_spawn_overwrites_stale_manifest(self, tmp_project):
        """An Agent spawn of a different agent overwrites the existing manifest phase."""
        (tmp_project / ".claude" / "rules").mkdir(parents=True, exist_ok=True)
        (tmp_project / ".claude" / "rules" / "rtl-coding-conventions.md").touch()

        # Write P1 manifest via Skill hook
        run_hook(
            HOOKS_DIR / "rtl-phase-state-bootstrap.sh",
            {"skill": "rtl-agent-team:p1-spec-research", "cwd": str(tmp_project), "hook_event_name": "PostToolUse"},
        )
        m1 = self._read_manifest(tmp_project)
        assert m1["pipeline"]["current_phase"] == 1

        # Agent spawn of the P6 orchestrator → must overwrite
        self._invoke(tmp_project, "p6-review-orchestrator")
        m2 = self._read_manifest(tmp_project)
        assert m2["pipeline"]["current_phase"] == 6

    def test_agent_spawn_project_root_override(self, tmp_project, tmp_path_factory):
        """v0.13.x: RAT_PROJECT_ROOT redirects manifest writes for direct
        Agent spawns whose session cwd is not the project root."""
        (tmp_project / ".claude" / "rules").mkdir(parents=True, exist_ok=True)
        (tmp_project / ".claude" / "rules" / "rtl-coding-conventions.md").touch()
        elsewhere = tmp_path_factory.mktemp("driver-cwd")
        result = run_hook(
            self.HOOK,
            {
                "subagent_type": "rtl-agent-team:p6-review-orchestrator",
                "cwd": str(elsewhere),
            },
            env={"RAT_PROJECT_ROOT": str(tmp_project)},
        )
        assert result["continue"] is True
        m = self._read_manifest(tmp_project)
        assert m["pipeline"]["current_phase"] == 6
        assert m["project_root"] == str(tmp_project)
        assert not (elsewhere / ".rat").exists()

    def test_agent_spawn_from_a_subdirectory_ships_the_project_root(self, tmp_project):
        """Spawned agents treat project_root as authoritative, so a session that has
        cd'd into rtl/ must still ship the project root."""
        (tmp_project / "rtl").mkdir(exist_ok=True)
        result = run_hook(
            self.HOOK,
            {"subagent_type": "rtl-agent-team:p6-review-orchestrator", "cwd": str(tmp_project / "rtl")},
            env={"CLAUDE_PROJECT_DIR": str(tmp_project)},
        )
        assert result["continue"] is True
        assert self._read_manifest(tmp_project)["project_root"] == str(tmp_project)
        assert not (tmp_project / "rtl" / ".rat").exists()

    def test_agent_spawn_non_orchestrator_ignored(self, tmp_project):
        """Non-orchestrator agent type → no manifest written."""
        result = run_hook(
            self.HOOK,
            {"subagent_type": "rtl-agent-team:rtl-coder", "cwd": str(tmp_project)},
        )
        assert result["continue"] is True
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        assert not mpath.exists()

    # ── Robustness: malformed / unexpected input payloads ────────────

    def test_agent_spawn_missing_subagent_type(self, tmp_project):
        """No subagent_type field → continue=true, no crash."""
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_agent_spawn_empty_input(self, tmp_project):
        """Empty JSON → continue=true, no crash."""
        result = run_hook(self.HOOK, {})
        assert result["continue"] is True

    def test_agent_spawn_non_rtl_agent(self, tmp_project):
        """Non-rtl-agent-team subagent_type → continue=true, no manifest."""
        result = run_hook(
            self.HOOK,
            {"subagent_type": "other-plugin:some-agent", "cwd": str(tmp_project)},
        )
        assert result["continue"] is True
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        assert not mpath.exists()


class TestSpawnContextInputRobustness:
    """Robustness tests: hooks handle malformed/unexpected input gracefully."""

    BOOTSTRAP_HOOK = HOOKS_DIR / "rtl-phase-state-bootstrap.sh"
    SPAWN_HOOK = HOOKS_DIR / "rtl-spawn-context.sh"

    def test_bootstrap_empty_input(self, tmp_project):
        """Empty JSON input → continue=true, no crash."""
        result = run_hook(self.BOOTSTRAP_HOOK, accepted_skill_input({}))
        assert result["continue"] is True

    def test_bootstrap_missing_skill_field(self, tmp_project):
        """No skill field → continue=true, no crash."""
        result = run_hook(self.BOOTSTRAP_HOOK, accepted_skill_input({"cwd": str(tmp_project)}))
        assert result["continue"] is True

    def test_bootstrap_garbage_skill_name(self, tmp_project):
        """Unrecognized skill prefix → continue=true, no manifest."""
        result = run_hook(
            self.BOOTSTRAP_HOOK,
            accepted_skill_input({"skill": "garbage:not-a-skill", "cwd": str(tmp_project)}),
        )
        assert result["continue"] is True
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        assert not mpath.exists()

    def test_bootstrap_rtl_skill_unknown_name(self, tmp_project):
        """rtl-agent-team prefix but unknown skill → continue=true, no manifest."""
        result = run_hook(
            self.BOOTSTRAP_HOOK,
            accepted_skill_input({"skill": "rtl-agent-team:nonexistent-skill", "cwd": str(tmp_project)}),
        )
        assert result["continue"] is True
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        assert not mpath.exists()

    def test_spawn_hook_invalid_json(self):
        """Completely invalid input → no crash (graceful fallback)."""
        import subprocess
        result = subprocess.run(
            ["sh", str(self.SPAWN_HOOK)],
            input="not-json-at-all",
            capture_output=True, text=True, timeout=10,
        )
        # Should not crash — exit 0 with continue=true
        assert result.returncode == 0
        assert "continue" in result.stdout or result.stdout == ""


class TestSpawnContextStructuralContracts:
    """Structural contract tests for spawn context — refactoring safety net."""

    BOOTSTRAP_HOOK = HOOKS_DIR / "rtl-phase-state-bootstrap.sh"
    SPAWN_HOOK = HOOKS_DIR / "rtl-spawn-context.sh"
    AGENTS_DIR = HOOKS_DIR.parent / "agents"
    SPAWN_CTX_UTIL = HOOKS_DIR / "lib" / "spawn-context-util.sh"
    ARTIFACT_MAP = HOOKS_DIR / "lib" / "artifact-map.sh"

    # ── Manifest schema stability ────────────────────────────────────

    MANIFEST_REQUIRED_SCHEMA = {
        "schema_version": str,
        "generated_at": str,
        "generated_by": str,
        "plugin_root": str,
        "project_root": str,
        "setup": dict,
        "pipeline": dict,
        "upstream_artifacts": dict,
        "staleness": dict,
        "team": dict,
        "quality_gates": dict,
    }

    def _setup_and_invoke(self, tmp_project, skill="rtl-p4-implement"):
        rules = tmp_project / ".claude" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "rtl-coding-conventions.md").touch()
        run_hook(
            self.BOOTSTRAP_HOOK,
            accepted_skill_input({"skill": f"rtl-agent-team:{skill}", "cwd": str(tmp_project)}),
        )
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        return json.loads(mpath.read_text())

    def test_manifest_schema_types(self, tmp_project):
        """All top-level manifest keys have expected types."""
        m = self._setup_and_invoke(tmp_project)
        for key, expected_type in self.MANIFEST_REQUIRED_SCHEMA.items():
            assert key in m, f"Missing key: {key}"
            assert isinstance(m[key], expected_type), (
                f"{key}: expected {expected_type.__name__}, got {type(m[key]).__name__}"
            )

    def test_manifest_setup_subkeys(self, tmp_project):
        """setup section has completed (bool) and marker (str)."""
        m = self._setup_and_invoke(tmp_project)
        assert isinstance(m["setup"]["completed"], bool)
        assert isinstance(m["setup"]["marker"], str)

    def test_manifest_pipeline_subkeys(self, tmp_project):
        """pipeline section has current_phase (int) and skill_invoked (str)."""
        m = self._setup_and_invoke(tmp_project)
        assert isinstance(m["pipeline"]["current_phase"], int)
        assert isinstance(m["pipeline"]["skill_invoked"], str)

    def test_manifest_artifacts_subkeys(self, tmp_project):
        """upstream_artifacts has required (list), optional (list), all_required_present (bool)."""
        m = self._setup_and_invoke(tmp_project)
        ua = m["upstream_artifacts"]
        assert isinstance(ua["required"], list)
        assert isinstance(ua["optional"], list)
        assert isinstance(ua["all_required_present"], bool)

    def test_manifest_artifact_entry_schema(self, tmp_project):
        """Each artifact entry has path, exists, mtime_epoch, role."""
        m = self._setup_and_invoke(tmp_project)
        for entry in m["upstream_artifacts"]["required"] + m["upstream_artifacts"]["optional"]:
            assert "path" in entry and isinstance(entry["path"], str)
            assert "exists" in entry and isinstance(entry["exists"], bool)
            assert "mtime_epoch" in entry and isinstance(entry["mtime_epoch"], int)
            assert "role" in entry and isinstance(entry["role"], str)

    def test_manifest_staleness_subkeys(self, tmp_project):
        """staleness has rtl_modified_count (int), rtl_verify_done (bool), phase6_stale (bool)."""
        m = self._setup_and_invoke(tmp_project)
        s = m["staleness"]
        assert isinstance(s["rtl_modified_count"], int)
        assert isinstance(s["rtl_verify_done"], bool)
        assert isinstance(s["phase6_stale"], bool)

    def test_manifest_team_subkeys(self, tmp_project):
        """team has active (bool) and leader_session_id (str)."""
        m = self._setup_and_invoke(tmp_project)
        t = m["team"]
        assert isinstance(t["active"], bool)
        assert isinstance(t["leader_session_id"], str)

    def test_manifest_quality_gates_subkeys(self, tmp_project):
        """quality_gates has p1-p4 passed (bool) and p5a_verdict (str or null)."""
        m = self._setup_and_invoke(tmp_project)
        qg = m["quality_gates"]
        for key in ("p1_passed", "p2_passed", "p3_passed", "p4_passed"):
            assert isinstance(qg[key], bool), f"{key} should be bool"
        assert qg["p5a_verdict"] is None or isinstance(qg["p5a_verdict"], str)

    # ── Artifact map completeness ────────────────────────────────────

    def test_artifact_map_all_phases_have_required(self):
        """Every phase 1-6 has at least one required artifact defined."""
        import subprocess
        artmap = str(HOOKS_DIR / "lib" / "artifact-map.sh")
        for phase in range(1, 7):
            result = subprocess.run(
                ["sh", "-c", f'. "{artmap}" && artmap_required {phase}'],
                capture_output=True, text=True, timeout=5,
            )
            lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
            assert len(lines) >= 1, f"Phase {phase} has no required artifacts"

    def test_artifact_map_entries_have_role(self):
        """Every artifact entry has path|role format."""
        import subprocess
        artmap = str(HOOKS_DIR / "lib" / "artifact-map.sh")
        for phase in range(1, 7):
            for fn in ("artmap_required", "artmap_optional"):
                result = subprocess.run(
                    ["sh", "-c", f'. "{artmap}" && {fn} {phase}'],
                    capture_output=True, text=True, timeout=5,
                )
                for line in result.stdout.strip().splitlines():
                    if not line.strip():
                        continue
                    parts = line.split("|")
                    assert len(parts) == 2, f"Bad format in {fn}({phase}): {line!r}"
                    assert parts[0].strip(), f"Empty path in {fn}({phase})"
                    assert parts[1].strip(), f"Empty role in {fn}({phase})"

    def test_artifact_map_phase2_includes_feature_census_artifacts(self):
        """v0.12.0: Phase 2 requires the feature-coverage.md census diff and lists
        the spec-feature-inventory.json census as optional upstream context."""
        import subprocess
        artmap = str(HOOKS_DIR / "lib" / "artifact-map.sh")
        req = subprocess.run(
            ["sh", "-c", f'. "{artmap}" && artmap_required 2'],
            capture_output=True, text=True, timeout=5,
        ).stdout
        opt = subprocess.run(
            ["sh", "-c", f'. "{artmap}" && artmap_optional 2'],
            capture_output=True, text=True, timeout=5,
        ).stdout
        req_lines = [l.strip() for l in req.splitlines() if l.strip()]
        opt_lines = [l.strip() for l in opt.splitlines() if l.strip()]
        assert "docs/phase-1-research/feature-coverage.md|p1-feature-coverage" in req_lines, (
            f"artmap_required 2 missing feature-coverage.md entry: {req_lines}"
        )
        assert (
            "docs/phase-1-research/spec-feature-inventory.json|p1-spec-feature-inventory"
            in opt_lines
        ), f"artmap_optional 2 missing spec-feature-inventory.json entry: {opt_lines}"

    def test_artifact_map_phase8_ppa_opt_entries(self):
        """ppa-opt (integer phase 8) lists final-compliance.md and docs/ppa-opt as
        optional upstream context; required is empty by design (post-P5 loop)."""
        import subprocess
        artmap = str(HOOKS_DIR / "lib" / "artifact-map.sh")
        opt = subprocess.run(
            ["sh", "-c", f'. "{artmap}" && artmap_optional 8'],
            capture_output=True, text=True, timeout=5,
        ).stdout
        opt_lines = [l.strip() for l in opt.splitlines() if l.strip()]
        assert "reviews/phase-5-verify/final-compliance.md|p5-compliance" in opt_lines, (
            f"artmap_optional 8 missing final-compliance entry: {opt_lines}"
        )
        assert "docs/ppa-opt|ppa-iteration-artifacts" in opt_lines, (
            f"artmap_optional 8 missing ppa-iteration-artifacts entry: {opt_lines}"
        )
        req = subprocess.run(
            ["sh", "-c", f'. "{artmap}" && artmap_required 8'],
            capture_output=True, text=True, timeout=5,
        ).stdout
        assert req.strip() == "", (
            f"artmap_required 8 must be empty (ppa-opt required is [] in registry): {req!r}"
        )

    def test_artifact_map_is_generated_from_registry(self):
        """artifact-map.sh case bodies carry GENERATED markers so
        generate-phase-maps.sh --check enforces registry parity."""
        content = (HOOKS_DIR / "lib" / "artifact-map.sh").read_text()
        for marker in (
            "# BEGIN GENERATED ARTMAP_REQUIRED",
            "# END GENERATED ARTMAP_REQUIRED",
            "# BEGIN GENERATED ARTMAP_OPTIONAL",
            "# END GENERATED ARTMAP_OPTIONAL",
        ):
            assert marker in content, f"missing marker: {marker}"

    # ── Orchestrator Step 0 consistency ──────────────────────────────

    # Orchestrators that MUST have manifest-aware Step 0
    MANIFEST_AWARE_ORCHESTRATORS = {
        "autopilot-orchestrator.md",
        "dse-orchestrator.md",
        "p1-research-orchestrator.md",
        "p1-research-orchestrator.md",
        "p2-arch-orchestrator.md",
        "p2-arch-orchestrator.md",
        "p3-uarch-orchestrator.md",
        "p3-uarch-orchestrator.md",
        "p4-implement-orchestrator.md",
        "p4-implement-orchestrator.md",
        "p4s-bugfix-orchestrator.md",
        "p4s-unit-test-orchestrator.md",
        "p5-verify-orchestrator.md",
        "p5-verify-orchestrator.md",
        "p5s-cdc-orchestrator.md",
        "p5s-coverage-orchestrator.md",
        "p5s-func-verify-orchestrator.md",
        "p5s-integration-orchestrator.md",
        "p5s-perf-orchestrator.md",
        "p5s-protocol-orchestrator.md",
        "p5s-sva-orchestrator.md",
        "p5s-uvm-orchestrator.md",
        "p6-review-orchestrator.md",
        "p7-exploration-orchestrator.md",
        "spec-to-uarch-orchestrator.md",
        "spec-to-uarch-orchestrator.md",
        "uarch-to-verify-orchestrator.md",
        "p4-rtl-sanity-orchestrator.md",
        "p4s-refactor-orchestrator.md",
    }

    def test_all_manifest_aware_orchestrators_have_new_step0(self):
        """Every manifest-aware orchestrator contains spawn-context.json read."""
        for fname in self.MANIFEST_AWARE_ORCHESTRATORS:
            fpath = self.AGENTS_DIR / fname
            assert fpath.exists(), f"Missing orchestrator: {fname}"
            content = fpath.read_text()
            assert "spawn-context.json" in content, (
                f"{fname} missing manifest-aware Step 0"
            )

    def test_all_manifest_aware_orchestrators_have_fallback(self):
        for agent in self.AGENTS_DIR.glob('*.md'):
            content=read_contract(agent)
            if 'Step 0: Context Bootstrap' in content:
                assert 'rtl-coding-conventions.md' in content
            elif 'runtime/workflows/' in content:
                assert 'spawn-context' in content
                assert 'process CWD' not in content or 'CWD' in content

    # ── Skill-to-phase mapping coverage ──────────────────────────────

    EXPECTED_SKILL_PHASES = {
        "p1-spec-research": 1,
        "p2-arch-design": 2,
        "rtl-p3-uarch-design": 3,
        "rtl-p4-implement": 4,
        "rtl-p4-block-parallel": 4,
        "rtl-p4-rapid-impl": 4,
        "rtl-p4s-bugfix": 4,
        "rtl-p4s-unit-test": 4,
        "rtl-p4s-refactor": 4,
        "rtl-review-refactor": 4,
        "rtl-p5-verify": 5,
        "rtl-p5a-functional-closure": 5,
        "rtl-p5b-silicon-validation": 5,
        "rtl-p5s-func-verify": 5,
        "rtl-p5s-integration-test": 5,
        "rtl-p5s-sva-check": 5,
        "rtl-p5s-cdc-verify": 5,
        "rtl-p5s-protocol-verify": 5,
        "rtl-p5s-perf-verify": 5,
        "rtl-p5s-coverage-analyze": 5,
        "rtl-p5s-uvm-verify": 5,
        "rtl-p6-design-review": 6,
        "rtl-p7-exploration": 7,
        "rat-auto-design": 1,
        "rat-refc-to-p5": 1,
        "rat-p1p3-spec-uarch": 1,
        "rat-dse": 1,
        "rat-p4p5-impl-verify": 4,
        # PPA optimization (post-verify; phase 8 represents post-P5/pre-P6 slot)
        "rtl-ppa-optimize-dc": 8,
        "rat-ultraloop-ppa": 8,
    }

    def test_skill_to_phase_mapping_complete(self):
        """All expected skills map to correct phases via sctx_skill_to_phase."""
        import subprocess
        json_util = str(HOOKS_DIR / "lib" / "json-util.sh")
        spawn_util = str(HOOKS_DIR / "lib" / "spawn-context-util.sh")
        hooks_dir = str(HOOKS_DIR)
        for skill, expected_phase in self.EXPECTED_SKILL_PHASES.items():
            result = subprocess.run(
                ["sh", "-c",
                 f'SCRIPT_DIR="{hooks_dir}" . "{json_util}" && '
                 f'jsonu_detect_parser && '
                 f'. "{spawn_util}" && '
                 f'sctx_skill_to_phase "{skill}"'],
                capture_output=True, text=True, timeout=5,
            )
            actual = result.stdout.strip()
            assert actual == str(expected_phase), (
                f"sctx_skill_to_phase({skill!r}) = {actual!r}, expected {expected_phase}"
            )

    # ── Agent-to-skill mapping in the spawn-context hook ─────────────

    EXPECTED_AGENT_MAPPINGS = {
        # Non-team orchestrators
        "p1-research-orchestrator": "p1-spec-research",
        "p2-arch-orchestrator": "p2-arch-design",
        "p3-uarch-orchestrator": "rtl-p3-uarch-design",
        "p4-implement-orchestrator": "rtl-p4-implement",
        "p4s-bugfix-orchestrator": "rtl-p4s-bugfix",
        "p4s-refactor-orchestrator": "rtl-p4s-refactor",
        "p4-rtl-sanity-orchestrator": "rtl-p4-rapid-impl",
        "p4-block-parallel-coordinator": "rtl-p4-block-parallel",
        "p4s-unit-test-orchestrator": "rtl-p4s-unit-test",
        "p5-verify-orchestrator": "rtl-p5-verify",
        "p5s-func-verify-orchestrator": "rtl-p5s-func-verify",
        "p5s-integration-orchestrator": "rtl-p5s-integration-test",
        "p5a-functional-closure-orchestrator": "rtl-p5a-functional-closure",
        "p5b-silicon-validation-orchestrator": "rtl-p5b-silicon-validation",
        "p5s-sva-orchestrator": "rtl-p5s-sva-check",
        "p5s-cdc-orchestrator": "rtl-p5s-cdc-verify",
        "p5s-protocol-orchestrator": "rtl-p5s-protocol-verify",
        "p5s-perf-orchestrator": "rtl-p5s-perf-verify",
        "p5s-coverage-orchestrator": "rtl-p5s-coverage-analyze",
        "p5s-uvm-orchestrator": "rtl-p5s-uvm-verify",
        "p6-review-orchestrator": "rtl-p6-design-review",
        "p7-exploration-orchestrator": "rtl-p7-exploration",
        "autopilot-orchestrator": "rat-auto-design",
        "spec-to-uarch-orchestrator": "rat-p1p3-spec-uarch",
        "uarch-to-verify-orchestrator": "rat-p4p5-impl-verify",
        "dse-orchestrator": "rat-dse",
        "review-refactor-orchestrator": "rtl-review-refactor",
        # Team orchestrators map to the merged phase skill
        "p1-research-orchestrator": "p1-spec-research",
        "p2-arch-orchestrator": "p2-arch-design",
        "p3-uarch-orchestrator": "rtl-p3-uarch-design",
        "p4-implement-orchestrator": "rtl-p4-implement",
        "p5-verify-orchestrator": "rtl-p5-verify",
        "spec-to-uarch-orchestrator": "rat-p1p3-spec-uarch",
        # PPA optimization (post-verify)
        "ppa-optimizer-dc-orchestrator": "rtl-ppa-optimize-dc",
        "ppa-optimizer-dc": "rtl-ppa-optimize-dc",
            }

    def test_agent_spawn_mapping_complete(self, tmp_project):
        """All expected orchestrator agents produce correct phase via the spawn-context hook."""
        rules = tmp_project / ".claude" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "rtl-coding-conventions.md").touch()

        for agent, expected_skill in self.EXPECTED_AGENT_MAPPINGS.items():
            result = run_hook(
                self.SPAWN_HOOK,
                {"subagent_type": f"rtl-agent-team:{agent}",
                 "cwd": str(tmp_project)},
            )
            assert result["continue"] is True
            mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
            assert mpath.exists(), f"No manifest for agent {agent}"
            m = json.loads(mpath.read_text())
            assert m["pipeline"]["skill_invoked"] == expected_skill, (
                f"Agent {agent}: expected skill {expected_skill}, "
                f"got {m['pipeline']['skill_invoked']}"
            )
            # Clean up for next iteration
            mpath.unlink()

    # ── Manifest idempotency ─────────────────────────────────────────

    def test_manifest_idempotent_structure(self, tmp_project):
        """Same skill invoked twice → structurally identical (except timestamp)."""
        rules = tmp_project / ".claude" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "rtl-coding-conventions.md").touch()

        run_hook(
            self.BOOTSTRAP_HOOK,
            accepted_skill_input({"skill": "rtl-agent-team:rtl-p4-implement", "cwd": str(tmp_project)}),
        )
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        m1 = json.loads(mpath.read_text())

        run_hook(
            self.BOOTSTRAP_HOOK,
            accepted_skill_input({"skill": "rtl-agent-team:rtl-p4-implement", "cwd": str(tmp_project)}),
        )
        m2 = json.loads(mpath.read_text())

        # Timestamps may differ, compare everything else
        m1.pop("generated_at")
        m2.pop("generated_at")
        assert m1 == m2

    @pytest.mark.parametrize("skill,expected_count", [
        ("rtl-p4-implement", 3),
        ("rtl-p6-design-review", 3),
    ])
    def test_upstream_iron_valid_json_array(self, tmp_project, skill, expected_count):
        """upstream_iron must be a valid JSON array for P4+ primary entry skills."""
        rules = tmp_project / ".claude" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "rtl-coding-conventions.md").touch()

        run_hook(
            self.BOOTSTRAP_HOOK,
            accepted_skill_input({"skill": f"rtl-agent-team:{skill}", "cwd": str(tmp_project)}),
        )
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        manifest = json.loads(mpath.read_text())
        iron = manifest["upstream_iron"]
        assert isinstance(iron, list), f"upstream_iron must be list, got {type(iron)}"
        assert len(iron) == expected_count, f"{skill} should have {expected_count} upstream iron paths, got {len(iron)}"
        for path in iron:
            assert path.endswith("iron-requirements.json"), f"unexpected path: {path}"

    # ── Full event chain simulation ──────────────────────────────────

    def test_skill_then_agent_spawn_chain(self, tmp_project):
        """Skill invoke → manifest → Agent spawn of a different agent → manifest updated."""
        rules = tmp_project / ".claude" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "rtl-coding-conventions.md").touch()

        # Step 1: Skill invocation writes P1 manifest
        run_hook(
            self.BOOTSTRAP_HOOK,
            accepted_skill_input({"skill": "rtl-agent-team:p1-spec-research", "cwd": str(tmp_project)}),
        )
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        m1 = json.loads(mpath.read_text())
        assert m1["pipeline"]["current_phase"] == 1

        # Step 2: an Agent spawn of the P4 orchestrator overwrites
        run_hook(
            self.SPAWN_HOOK,
            {"subagent_type": "rtl-agent-team:p4-implement-orchestrator",
             "cwd": str(tmp_project)},
        )
        m2 = json.loads(mpath.read_text())
        assert m2["pipeline"]["current_phase"] == 4
        assert m2["setup"]["completed"] is True

        # Step 3: rat-init-project refreshes with preserved context
        run_hook(
            self.BOOTSTRAP_HOOK,
            accepted_skill_input({"skill": "rtl-agent-team:rat-init-project", "cwd": str(tmp_project)}),
        )
        m3 = json.loads(mpath.read_text())
        assert m3["pipeline"]["current_phase"] == 4  # Preserved
        assert m3["setup"]["completed"] is True


# ── Team progress hook behavioral tests ─────────────────────────────────────


class TestTeamProgressHook:
    """Behavioral tests for rtl-team-progress.sh PostToolUse:TaskUpdate hook."""

    HOOK = HOOKS_DIR / "rtl-team-progress.sh"

    def test_noop_without_team_config(self, tmp_project):
        """When no team-config.json exists, hook outputs JSON and exits cleanly."""
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result.get("continue") is True

    def test_noop_when_team_mode_false(self, tmp_project):
        """When team_mode is false, hook outputs JSON and exits cleanly."""
        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "team-config.json").write_text(
            json.dumps({"team_mode": False, "team_name": "test"})
        )
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result.get("continue") is True

    def test_noop_without_progress_file(self, tmp_project):
        """When team mode is active but no progress file, hook exits cleanly."""
        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "team-config.json").write_text(
            json.dumps({"team_mode": True, "team_name": "test-team"})
        )
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result.get("continue") is True

    def test_updates_timestamp_in_progress_file(self, tmp_project):
        """When team mode is active and progress file exists, last_updated is refreshed."""
        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "team-config.json").write_text(
            json.dumps({"team_mode": True, "team_name": "test-team"})
        )
        progress = {"last_updated": "2020-01-01T00:00:00Z", "tasks_completed": 0}
        (state_dir / "team-progress.json").write_text(json.dumps(progress))

        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result.get("continue") is True

        updated = json.loads((state_dir / "team-progress.json").read_text())
        assert updated["last_updated"] != "2020-01-01T00:00:00Z"

    def _stale_team(self, tmp_project, leader):
        """A team-config.json last written 3h ago (None: no leader key)."""
        config = tmp_project / ".rat" / "state" / "team-config.json"
        team = {"team_mode": True, "team_name": "test-team"}
        if leader is not None:
            team["leader_session_id"] = leader
        config.write_text(json.dumps(team))
        if leader is not None: _record_team_owner(tmp_project, leader)
        three_hours_ago = time.time() - 3 * 3600
        os.utime(config, (three_hours_ago, three_hours_ago))
        return config

    def test_teammate_activity_keeps_the_team_fresh(self, tmp_project):
        # The 2h bound measures time since the team was last active: a TaskUpdate from an
        # in-process teammate (the leader's session id plus an agent_id) refreshes the config.
        self._stale_team(tmp_project, "leader-abc")
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"), "rtl/a.sv\n")
        run_hook(self.HOOK, {"cwd": str(tmp_project), "session_id": "leader-abc",
                             "agent_id": "coordinator"})
        result = run_hook(HOOKS_DIR / "rtl-verify-stop-gate.sh",
                          {"cwd": str(tmp_project), "session_id": "worker-1"})
        assert result == {"continue": True}

    @pytest.mark.parametrize("parser_env", [{}, {"RTL_FORCE_PYTHON_PARSER": "1"},
                                            {"RTL_FORCE_JSON_FALLBACK": "1"}],
                             ids=["default", "python", "sed"])
    def test_session_id_comes_from_the_hook_input_root(self, tmp_project, parser_env):
        # A session id is session information: a tool_input field of the same name must not
        # replace the root's, so the leader's teammate still keeps the team fresh.
        config = self._stale_team(tmp_project, "leader-abc")
        before = config.stat().st_mtime
        run_hook(
            self.HOOK,
            {
                "session_id": "leader-abc",
                "cwd": str(tmp_project),
                "agent_id": "coordinator",
                "hook_event_name": "PostToolUse",
                "tool_name": "TaskUpdate",
                "tool_input": {"taskId": "1", "status": "completed", "session_id": "stranger"},
            },
            env=parser_env,
        )
        assert config.stat().st_mtime > before

    @pytest.mark.parametrize("leader, session, agent", [("leader-abc", "other-session", "t1"),
                                                        ("leader-abc", "leader-abc", None),
                                                        ("<current_session_id>", "leader-abc", "t1"),
                                                        (None, "leader-abc", "t1"),
                                                        (None, None, None)],
                             ids=["other-session", "leader-main-thread", "placeholder-leader",
                                  "no-leader", "no-leader-no-session"])
    def test_other_activity_does_not_revive_the_team(self, tmp_project, leader, session, agent):
        # TaskUpdate is not team-only: another session's task list, or the leader's own after
        # an abandoned run, must not keep the team alive; without a known leader no call is
        # team activity.
        config = self._stale_team(tmp_project, leader)
        _track((tmp_project / ".rat" / "state" / "rtl-modified-files.txt"), "rtl/a.sv\n")
        before = config.stat().st_mtime
        stdin = {"cwd": str(tmp_project)}
        if session is not None:
            stdin["session_id"] = session
        if agent is not None:
            stdin["agent_id"] = agent
        run_hook(self.HOOK, stdin)
        assert config.stat().st_mtime == before
        # The config stays stale, so the session's next Stop removes it and enforces the gate.
        _assert_stop_blocked(run_hook(HOOKS_DIR / "rtl-verify-stop-gate.sh", stdin))
        assert not config.exists()

    def test_activity_before_any_team_creates_no_config(self, tmp_project):
        run_hook(self.HOOK, {"cwd": str(tmp_project), "session_id": "leader-abc",
                             "agent_id": "coordinator"})
        assert not (tmp_project / ".rat" / "state" / "team-config.json").exists()

    @pytest.mark.skipif(shutil.which("jq") is None, reason="the race is staged through jq")
    def test_heartbeat_does_not_recreate_a_config_removed_meanwhile(self, tmp_project):
        # A gate may remove the stale config between this hook's read of the leader and its
        # touch; a plain touch would then leave an empty team-config.json behind.
        config = self._stale_team(tmp_project, "leader-abc")
        shim = tmp_project / "bin"
        shim.mkdir()
        (shim / "jq").write_text(
            "#!/bin/sh\n"
            f'"{shutil.which("jq")}" "$@"; rc=$?\n'
            'for a in "$@"; do case "$a" in */team-config.json)\n'
            '  [ -e "$a.gone" ] || { rm -f "$a"; : > "$a.gone"; } ;; esac; done\n'
            "exit $rc\n")
        (shim / "jq").chmod(0o755)
        run_hook(self.HOOK, {"cwd": str(tmp_project), "session_id": "leader-abc",
                             "agent_id": "coordinator"},
                 env={"PATH": f"{shim}:{os.environ['PATH']}"})
        assert not config.exists()


# ── P1-1 Mapping Drift Detection ────────────────────────────────────────────


class TestMappingSyncParity:
    """Detect drift between phase mapper, compliance bootstrap, agent mappings,
    test expectations, and skill-completion-criteria.json."""

    SPAWN_CTX_UTIL = HOOKS_DIR / "lib" / "spawn-context-util.sh"
    BOOTSTRAP_HOOK = HOOKS_DIR / "rtl-phase-state-bootstrap.sh"
    SPAWN_HOOK = HOOKS_DIR / "rtl-spawn-context.sh"
    CRITERIA_FILE = REPO_ROOT / "skill-completion-criteria.json"
    SKILLS_DIR = REPO_ROOT / "skills"

    # ── Helpers: extract sets from shell case statements ──────────

    @staticmethod
    def _extract_phase_mapper_skills(path):
        """Parse sctx_skill_to_phase() case branches from spawn-context-util.sh.
        Returns a dict {skill_name: phase_int}."""
        content = path.read_text()
        # Extract the case block for sctx_skill_to_phase
        m = re.search(
            r'sctx_skill_to_phase\(\)\s*\{.*?case\s+"\$1"\s+in(.*?)\*\)\s+echo\s+""\s*;;',
            content, re.DOTALL,
        )
        assert m, "Could not find sctx_skill_to_phase case block"
        block = m.group(1)
        result = {}
        for line in block.splitlines():
            line = line.strip()
            # Match patterns like: skill1|skill2) echo N ;;
            branch = re.match(r'^([a-z0-9|_-]+)\)\s+echo\s+(\d+)\s*;;', line)
            if branch:
                skills_str, phase = branch.group(1), int(branch.group(2))
                for skill in skills_str.split("|"):
                    skill = skill.strip()
                    if skill:
                        result[skill] = phase
        return result

    @staticmethod
    def _extract_compliance_bootstrap_skills(path):
        """Parse the compliance state bootstrap case in rtl-phase-state-bootstrap.sh.
        Returns a set of skill short-names that have compliance entries."""
        content = path.read_text()
        # The compliance map is the file's generated PHASE_MAP block. Reading the first
        # case on $SHORT_NAME instead would let an earlier case (a gate) stand in for it.
        m = re.search(
            r'# BEGIN GENERATED PHASE_MAP\n(.*?)# END GENERATED PHASE_MAP',
            content, re.DOTALL,
        )
        assert m, "Could not find the compliance bootstrap's generated PHASE_MAP block"
        block = m.group(1)
        skills = set()
        for line in block.splitlines():
            line = line.strip()
            # Match branch heads like: p2-arch-design)
            branch = re.match(r'^([a-z0-9|_-]+)\)', line)
            if branch:
                for skill in branch.group(1).split("|"):
                    skill = skill.strip()
                    if skill and skill != "*":
                        skills.add(skill)
        return skills

    @staticmethod
    def _extract_agent_mappings(path):
        """Parse agent-to-skill case branches from rtl-spawn-context.sh.
        Returns a dict {agent_short_name: skill_name}."""
        content = path.read_text()
        # Find the case "$SHORT_NAME" block with agent mappings
        m = re.search(
            r'SKILL_NAME=""\s*\ncase\s+"\$SHORT_NAME"\s+in(.*?)\*\)',
            content, re.DOTALL,
        )
        assert m, "Could not find agent mapping case block"
        block = m.group(1)
        result = {}
        for line in block.splitlines():
            line = line.strip()
            # Match: agent-name) SKILL_NAME="skill-name" ;;
            branch = re.match(
                r'^([a-z0-9_-]+)\)\s+SKILL_NAME="([^"]+)"\s*;;', line
            )
            if branch:
                result[branch.group(1)] = branch.group(2)
        return result

    # ── Tests ─────────────────────────────────────────────────────

    def test_compliance_bootstrap_subset_of_phase_mapper(self):
        """Every skill in compliance bootstrap must exist in phase mapper."""
        phase_mapper = self._extract_phase_mapper_skills(self.SPAWN_CTX_UTIL)
        bootstrap_skills = self._extract_compliance_bootstrap_skills(
            self.BOOTSTRAP_HOOK
        )
        missing = bootstrap_skills - set(phase_mapper.keys())
        assert not missing, (
            f"Compliance bootstrap has skills not in phase mapper: {sorted(missing)}"
        )

    def test_agent_mapping_skills_in_phase_mapper(self):
        """Every target skill in agent mapping must exist in phase mapper."""
        phase_mapper = self._extract_phase_mapper_skills(self.SPAWN_CTX_UTIL)
        agent_mappings = self._extract_agent_mappings(self.SPAWN_HOOK)
        target_skills = set(agent_mappings.values())
        missing = target_skills - set(phase_mapper.keys())
        assert not missing, (
            f"Agent mapping targets skills not in phase mapper: {sorted(missing)}"
        )

    def test_expected_skill_phases_matches_phase_mapper(self):
        """EXPECTED_SKILL_PHASES in TestSpawnContextStructuralContracts must
        match the actual phase mapper exactly."""
        actual = self._extract_phase_mapper_skills(self.SPAWN_CTX_UTIL)
        expected = TestSpawnContextStructuralContracts.EXPECTED_SKILL_PHASES
        # Check both directions
        missing_from_test = set(actual.keys()) - set(expected.keys())
        extra_in_test = set(expected.keys()) - set(actual.keys())
        assert not missing_from_test, (
            f"Phase mapper has skills not in EXPECTED_SKILL_PHASES: {sorted(missing_from_test)}"
        )
        assert not extra_in_test, (
            f"EXPECTED_SKILL_PHASES has skills not in phase mapper: {sorted(extra_in_test)}"
        )
        for skill in actual:
            assert actual[skill] == expected[skill], (
                f"Phase mismatch for {skill}: mapper={actual[skill]}, test={expected[skill]}"
            )

    def test_expected_agent_mappings_matches_spawn_context(self):
        """EXPECTED_AGENT_MAPPINGS in TestSpawnContextStructuralContracts must
        match the actual agent mapping in rtl-spawn-context.sh exactly."""
        actual = self._extract_agent_mappings(self.SPAWN_HOOK)
        expected = TestSpawnContextStructuralContracts.EXPECTED_AGENT_MAPPINGS
        missing_from_test = set(actual.keys()) - set(expected.keys())
        extra_in_test = set(expected.keys()) - set(actual.keys())
        assert not missing_from_test, (
            f"Spawn context has agents not in EXPECTED_AGENT_MAPPINGS: {sorted(missing_from_test)}"
        )
        assert not extra_in_test, (
            f"EXPECTED_AGENT_MAPPINGS has agents not in spawn context: {sorted(extra_in_test)}"
        )
        for agent in actual:
            assert actual[agent] == expected[agent], (
                f"Skill mismatch for {agent}: spawn-context={actual[agent]}, "
                f"test={expected[agent]}"
            )

    def test_completion_criteria_skills_exist(self):
        """Every key in skill-completion-criteria.json (except _comment) must
        have a corresponding skills/{name}/SKILL.md."""
        criteria = json.loads(self.CRITERIA_FILE.read_text())
        missing = []
        for skill_name in criteria:
            if skill_name == "_comment":
                continue
            skill_md = self.SKILLS_DIR / skill_name / "SKILL.md"
            if not skill_md.exists():
                missing.append(skill_name)
        assert not missing, (
            f"Completion criteria references skills without SKILL.md: {sorted(missing)}"
        )


# ── P3-10 Phase Registry Sync ───────────────────────────────────────────────


class TestPhaseRegistrySync:
    """Verify phase-registry.json stays in sync with generated shell code.
    Runs scripts/generate-phase-maps.sh --check which exits non-zero on drift."""

    GENERATOR = REPO_ROOT / "scripts" / "generate-phase-maps.sh"
    REGISTRY = REPO_ROOT / "phase-registry.json"

    def test_registry_exists(self):
        """phase-registry.json must exist at repo root."""
        assert self.REGISTRY.exists(), "phase-registry.json not found"

    def test_registry_valid_json(self):
        """phase-registry.json must be valid JSON with expected top-level keys."""
        data = json.loads(self.REGISTRY.read_text())
        assert "_schema_version" in data
        assert "skills" in data
        assert "agents" in data
        assert "phases" in data

    @pytest.mark.skipif(
        not REPO_ROOT.joinpath("scripts/generate-phase-maps.sh").exists(),
        reason="generator script not found",
    )
    def test_phase_registry_sync(self):
        """Generated blocks must match current file content (no drift)."""
        if not shutil.which("jq"):
            pytest.skip("jq not available")
        result = subprocess.run(
            ["bash", str(self.GENERATOR), "--check"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Phase registry out of sync with generated files:\n{result.stderr}"
        )


# ── P2-5 Hook Integration Chain ─────────────────────────────────────────────


class TestHookIntegrationChain:
    """Test the multi-hook chain: skill-activation -> phase-state-bootstrap
    -> spawn-context for a full agent spawn lifecycle."""

    ACTIVATION_HOOK = HOOKS_DIR / "rtl-skill-activation.sh"
    BOOTSTRAP_HOOK = HOOKS_DIR / "rtl-phase-state-bootstrap.sh"
    SPAWN_HOOK = HOOKS_DIR / "rtl-spawn-context.sh"

    def _setup_project(self, tmp_project):
        """Set up a project with setup marker and completion criteria."""
        rules = tmp_project / ".claude" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "rtl-coding-conventions.md").touch()

    def test_full_chain_p4_implement(self, tmp_project):
        """Skill activation -> bootstrap -> spawn context produces correct manifest."""
        self._setup_project(tmp_project)

        # Step 1: skill activation
        result1 = run_hook(
            self.ACTIVATION_HOOK,
            {"skill": "rtl-agent-team:rtl-p4-implement", "cwd": str(tmp_project)},
            env={"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)},
        )
        assert result1.get("continue") is True

        # Step 2: phase state bootstrap
        result2 = run_hook(
            self.BOOTSTRAP_HOOK,
            accepted_skill_input({"skill": "rtl-agent-team:rtl-p4-implement", "cwd": str(tmp_project)}),
        )
        assert result2.get("continue") is True

        # Step 3: spawn context for orchestrator
        result3 = run_hook(
            self.SPAWN_HOOK,
            {
                "subagent_type": "rtl-agent-team:p4-implement-orchestrator",
                "cwd": str(tmp_project),
            },
        )
        assert result3.get("continue") is True

        # Verify spawn-context.json
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        assert mpath.exists(), "spawn-context.json not written"
        manifest = json.loads(mpath.read_text())

        assert manifest["pipeline"]["current_phase"] == 4
        assert manifest["setup"]["completed"] is True
        assert isinstance(manifest["upstream_iron"], list)
        assert len(manifest["upstream_iron"]) == 3
        for path in manifest["upstream_iron"]:
            assert "iron-requirements.json" in path


# ── P2-6 Flock Util Stale Lock ──────────────────────────────────────────────


class TestFlockUtilStaleLock:
    """Tests for flock-util.sh stale lock detection and cleanup."""

    FLOCK_UTIL = HOOKS_DIR / "lib" / "flock-util.sh"

    def _run_flock(self, script, env=None):
        """Source flock-util.sh and run a shell snippet."""
        import subprocess

        preamble = f'. "{self.FLOCK_UTIL}"\n'
        merged_env = {**os.environ, **(env or {})}
        result = subprocess.run(
            ["sh", "-c", preamble + script],
            capture_output=True,
            text=True,
            env=merged_env,
            timeout=15,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode

    def test_stale_lock_nonexistent_pid(self, tmp_path):
        """Lock dir with non-existent PID should be reclaimed by new acquire."""
        resource = tmp_path / "test-resource"
        lock_dir = tmp_path / "test-resource.lock"
        lock_dir.mkdir()
        pid_file = lock_dir / "pid"
        # Use a PID that almost certainly does not exist
        pid_file.write_text("999999999")

        stdout, _, rc = self._run_flock(
            f'FLOCK_TIMEOUT=3 acquire_lock "{resource}" && echo ACQUIRED || echo FAILED'
        )
        assert "ACQUIRED" in stdout

    def test_lock_dir_cleanup_on_release(self, tmp_path):
        """After release_lock, the lock directory should be removed."""
        resource = tmp_path / "test-resource"

        stdout, _, rc = self._run_flock(
            f'acquire_lock "{resource}" && '
            f'release_lock "{resource}" && '
            f'[ ! -d "{resource}.lock" ] && echo CLEANED || echo REMAINS'
        )
        assert "CLEANED" in stdout


# ── rat-dir-util.sh unit tests ───────────────────────────────────────────────


class TestRatDirUtil:
    """Direct unit tests for hooks/lib/rat-dir-util.sh functions."""

    def _run(self, cwd, cmd):
        script = f'. "{HOOKS_DIR}/lib/rat-dir-util.sh"\n{cmd}'
        result = subprocess.run(
            ["sh", "-c", script],
            capture_output=True, text=True, cwd=str(cwd),
        )
        return result.stdout.strip(), result.returncode

    def test_is_project_true_with_rat(self, tmp_path):
        (tmp_path / ".rat").mkdir()
        _, rc = self._run(tmp_path, f'rat_is_project "{tmp_path}"')
        assert rc == 0

    def test_is_project_true_with_legacy(self, tmp_path):
        (tmp_path / ".rtl-agent-team").mkdir()
        _, rc = self._run(tmp_path, f'rat_is_project "{tmp_path}"')
        assert rc == 0

    def test_is_project_false_with_neither(self, tmp_path):
        _, rc = self._run(tmp_path, f'rat_is_project "{tmp_path}"')
        assert rc == 1

    def test_project_dir_prefers_rat(self, tmp_path):
        (tmp_path / ".rat").mkdir()
        (tmp_path / ".rtl-agent-team").mkdir()
        out, rc = self._run(tmp_path, f'rat_project_dir "{tmp_path}"')
        assert rc == 0
        assert out == f"{tmp_path}/.rat"

    def test_project_dir_falls_back_to_legacy(self, tmp_path):
        (tmp_path / ".rtl-agent-team").mkdir()
        out, rc = self._run(tmp_path, f'rat_project_dir "{tmp_path}"')
        assert rc == 0
        assert out == f"{tmp_path}/.rtl-agent-team"

    def test_project_dir_returns_1_when_neither(self, tmp_path):
        out, rc = self._run(tmp_path, f'rat_project_dir "{tmp_path}"')
        assert rc == 1
        assert out == ""

    def test_env_override_honored_when_set(self, tmp_path):
        # RAT_PROJECT_ROOT points at a real project; the $1 arg points elsewhere.
        root = tmp_path / "real"
        (root / ".rat").mkdir(parents=True)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        out, rc = self._run(
            elsewhere,
            f'RAT_PROJECT_ROOT="{root}" rat_project_dir "{elsewhere}"',
        )
        assert rc == 0
        assert out == f"{root}/.rat"

    def test_is_project_env_override_honored_when_set(self, tmp_path):
        root = tmp_path / "real"
        (root / ".rat").mkdir(parents=True)
        elsewhere = tmp_path / "elsewhere"  # no marker
        elsewhere.mkdir()
        _, rc = self._run(
            elsewhere,
            f'RAT_PROJECT_ROOT="{root}" rat_is_project "{elsewhere}"',
        )
        assert rc == 0

    def test_env_override_ignored_when_empty(self, tmp_path):
        # Empty RAT_PROJECT_ROOT ⇒ byte-identical to legacy $1-based behavior.
        (tmp_path / ".rat").mkdir()
        out, rc = self._run(
            tmp_path,
            f'RAT_PROJECT_ROOT="" rat_project_dir "{tmp_path}"',
        )
        assert rc == 0
        assert out == f"{tmp_path}/.rat"

    def test_env_override_preserves_existence_contract(self, tmp_path):
        # RAT_PROJECT_ROOT set but has no marker ⇒ still returns 1 (contract kept).
        no_marker = tmp_path / "no_marker"
        no_marker.mkdir()
        has_marker = tmp_path / "has_marker"
        (has_marker / ".rat").mkdir(parents=True)
        out, rc = self._run(
            has_marker,
            f'RAT_PROJECT_ROOT="{no_marker}" rat_project_dir "{has_marker}"',
        )
        assert rc == 1
        assert out == ""

    def _resolve(self, start, project_dir=None):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"}
        if project_dir is not None:
            env["CLAUDE_PROJECT_DIR"] = str(project_dir)
        result = subprocess.run(
            ["sh", "-c", f'. "{HOOKS_DIR}/lib/rat-dir-util.sh"\nrat_project_dir "$1"', "sh", str(start)],
            capture_output=True, text=True, env=env,
        )
        return result.stdout.strip(), result.returncode

    def test_subdirectory_resolves_to_the_project(self, tmp_path):
        (tmp_path / ".rat").mkdir()
        (tmp_path / "rtl" / "core").mkdir(parents=True)
        assert self._resolve(tmp_path / "rtl" / "core", tmp_path) == (f"{tmp_path}/.rat", 0)

    def test_root_marker_wins_over_a_stray_nested_one(self, tmp_path):
        (tmp_path / ".rat").mkdir()
        (tmp_path / "rtl" / ".rat" / "state").mkdir(parents=True)  # a relative write made from rtl/
        assert self._resolve(tmp_path / "rtl", tmp_path) == (f"{tmp_path}/.rat", 0)

    def test_without_a_root_marker_the_nearest_initialized_project_wins(self, tmp_path):
        ip = tmp_path / "ip"
        (ip / ".rat").mkdir(parents=True)
        (ip / "rat_config.json").write_text("{}")
        (ip / "rtl" / ".rat").mkdir(parents=True)                   # stray, not initialized
        assert self._resolve(ip / "rtl", tmp_path) == (f"{ip}/.rat", 0)

    def test_without_a_root_marker_a_legacy_project_is_still_found(self, tmp_path):
        ip = tmp_path / "ip"
        (ip / ".rtl-agent-team").mkdir(parents=True)
        (ip / "rtl").mkdir()
        assert self._resolve(ip / "rtl", tmp_path) == (f"{ip}/.rtl-agent-team", 0)

    def test_walk_stops_at_the_project_root(self, tmp_path):
        (tmp_path / ".rat").mkdir()                      # stray marker above the project
        project = tmp_path / "work" / "proj"
        (project / "rtl").mkdir(parents=True)
        assert self._resolve(project / "rtl", project) == ("", 1)

    def test_a_trailing_slash_does_not_carry_the_walk_above_the_project_root(self, tmp_path):
        (tmp_path / ".rat").mkdir()                      # stray marker above the project
        project = tmp_path / "proj"
        project.mkdir()
        assert self._resolve(f"{project}/", project) == ("", 1)

    @pytest.mark.parametrize("start", ["elsewhere/sub", "proj2/rtl"])
    def test_a_start_outside_the_project_checks_only_itself(self, tmp_path, start):
        (tmp_path / ".rat").mkdir()                      # marker above the start
        (tmp_path / "proj").mkdir()
        (tmp_path / start).mkdir(parents=True)           # proj2 only shares the project's prefix
        assert self._resolve(tmp_path / start, tmp_path / "proj") == ("", 1)

    def test_a_trailing_slash_in_the_project_dir_still_bounds_the_walk(self, tmp_path):
        ip = tmp_path / "ip"
        (ip / ".rat").mkdir(parents=True)
        (ip / "rat_config.json").write_text("{}")
        (ip / "rtl").mkdir()
        assert self._resolve(ip / "rtl", f"{tmp_path}/") == (f"{ip}/.rat", 0)

    def test_cwd_outside_the_project_falls_back_to_the_project_root(self, tmp_path):
        project = tmp_path / "proj"
        (project / ".rat").mkdir(parents=True)
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        assert self._resolve(elsewhere, project) == (f"{project}/.rat", 0)

    def test_without_project_dir_only_the_cwd_counts(self, tmp_path):
        (tmp_path / ".rat").mkdir()
        (tmp_path / "rtl").mkdir()
        assert self._resolve(tmp_path / "rtl") == ("", 1)


# ── Legacy .rtl-agent-team fallback integration tests ────────────────────────


class TestLegacyDirFallback:
    """Verify hooks work with legacy .rtl-agent-team directories (no .rat)."""

    EDIT_HOOK = HOOKS_DIR / "rtl-edit-tracker.sh"
    VERIFY_HOOK = HOOKS_DIR / "rtl-verify-stop-gate.sh"
    INJECT_HOOK = HOOKS_DIR / "rtl-orchestrator-inject.sh"

    def test_edit_tracker_works_with_legacy_dir(self, tmp_legacy_project):
        result = run_hook(
            self.EDIT_HOOK,
            {"cwd": str(tmp_legacy_project), "file_path": "rtl/mod.sv"},
        )
        assert result["continue"] is True
        track = tmp_legacy_project / ".rtl-agent-team" / "state" / "rtl-modified-files.txt"
        assert track.exists()
        assert "rtl/mod.sv" in track.read_text()

    def test_verify_gate_blocks_with_legacy_dir(self, tmp_legacy_project):
        track = tmp_legacy_project / ".rtl-agent-team" / "state" / "rtl-modified-files.txt"
        _track(track, "rtl/mod.sv\n")
        result = run_hook(
            self.VERIFY_HOOK,
            {"cwd": str(tmp_legacy_project)},
        )
        _assert_stop_blocked(result)

    def test_orchestrator_inject_fires_with_legacy_dir(self, tmp_legacy_project):
        # Since v0.10.3 the hook emits a JSON envelope; routing markdown is
        # delivered via `hookSpecificOutput.additionalContext`.
        result = run_hook(self.INJECT_HOOK, {"cwd": str(tmp_legacy_project)})
        hso = result.get("hookSpecificOutput", {})
        assert hso.get("hookEventName") == "SessionStart"
        ctx = hso.get("additionalContext", "")
        assert "Routing" in ctx or "Pipeline Rules" in ctx

    def test_hooks_exit_cleanly_in_non_project(self, tmp_path):
        """Hooks should emit {"continue":true} when no .rat or .rtl-agent-team exists."""
        for hook_name in ["rtl-verify-stop-gate.sh", "stop-gate.sh",
                          "rtl-p6-cascade-gate.sh", "rtl-skill-completion-gate.sh"]:
            result = run_hook(
                HOOKS_DIR / hook_name,
                {"cwd": str(tmp_path)},
            )
            assert result.get("continue") is True, (
                f"{hook_name} did not emit continue:true in non-project dir, got: {result}"
            )
            # No state directory should be created
            assert not (tmp_path / ".rat").exists(), (
                f"{hook_name} created .rat in non-project dir"
            )


class TestCoverageExclusionGate:
    """Approval applies to an explicit current set, with bounded user handoff."""
    HOOK=HOOKS_DIR/'rtl-coverage-exclusion-gate.sh'

    def _write_exclusions(self,root):
        folder=root/'reviews/phase-5-verify';folder.mkdir(parents=True,exist_ok=True)
        path=folder/'alu-coverage-exclusions.md'
        path.write_text('| Bin | Category |\n|---|---|\n| debug | Unimplemented feature |\n')
        return path

    def test_asks_once_then_hands_over(self,tmp_project):
        self._write_exclusions(tmp_project)
        assert run_hook(self.HOOK,{'cwd':str(tmp_project)}).get('decision')=='block'
        second=run_hook(self.HOOK,{'cwd':str(tmp_project),'stop_hook_active':True})
        assert second.get('systemMessage')
        assert 'confirmation' in second['systemMessage']
        assert run_hook(self.HOOK,{'cwd':str(tmp_project),'stop_hook_active':True})=={'continue':True}

    def test_bare_approval_marker_is_insufficient(self,tmp_project):
        self._write_exclusions(tmp_project)
        (tmp_project/'.rat/state/coverage-exclusion-approved').touch()
        assert run_hook(self.HOOK,{'cwd':str(tmp_project)}).get('decision')=='block'

    def test_approved_set_passes_but_changed_set_blocks(self,tmp_project):
        path=self._write_exclusions(tmp_project)
        result=subprocess.run([sys.executable,str(REPO_ROOT/'scripts/coverage_approval.py'),'approve',
            '--root',str(tmp_project),'--decision','User approved the debug exclusion'],capture_output=True)
        assert result.returncode==0
        assert run_hook(self.HOOK,{'cwd':str(tmp_project)})=={'continue':True}
        path.write_text(path.read_text()+'| mode | Ambiguous |\n')
        assert run_hook(self.HOOK,{'cwd':str(tmp_project)}).get('decision')=='block'

    @pytest.mark.parametrize('category',['Out-of-scope','Spec ambiguity','UNIMPLEMENTED FEATURES','Ambiguous spec applicability'])
    def test_category_column_accepts_supported_spellings(self,tmp_project,category):
        path=self._write_exclusions(tmp_project)
        path.write_text('| Bin | Reason | Category |\n|---|---|---|\n| x | pending | '+category+' |\n')
        assert run_hook(self.HOOK,{'cwd':str(tmp_project)}).get('decision')=='block'

    def test_reason_keyword_is_not_a_nonstandard_category(self,tmp_project):
        path=self._write_exclusions(tmp_project)
        path.write_text('| Bin | Reason | Category |\n|---|---|---|\n| x | not ambiguous | Parameter guards |\n')
        assert run_hook(self.HOOK,{'cwd':str(tmp_project)})=={'continue':True}

    def test_subdirectory_uses_the_project_approval(self,tmp_project):
        self._write_exclusions(tmp_project);sub=tmp_project/'rtl';sub.mkdir()
        assert run_hook(self.HOOK,{'cwd':str(sub)},env={'CLAUDE_PROJECT_DIR':str(tmp_project)}).get('decision')=='block'

    def test_forced_sed_mode_still_uses_the_evidence_parser(self,tmp_project):
        self._write_exclusions(tmp_project)
        assert run_hook(self.HOOK,{'cwd':str(tmp_project)},env={'RTL_FORCE_JSON_FALLBACK':'1'}).get('decision')=='block'


def _verify_blocks(project):
    _track((project / ".rat" / "state" / "rtl-modified-files.txt"), "rtl/alu.sv\n")


def _p6_cascade_blocks(project):
    (project / ".rat" / "state" / "phase6-stale").touch()


def _skill_completion_blocks(project):
    started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (project / ".rat" / "state" / "skill-active.json").write_text(json.dumps({
        "skill": "rtl-p4s-bugfix", "active": True, "iteration": 1, "max_iterations": 5,
        "pending": "lint_pass, sim_pass", "all_complete": False, "started_at": started}))


def _autopilot_blocks(project):
    (project / ".rat" / "state" / "rat-auto-design-state.json").write_text(
        json.dumps({"status": "in_progress", "phase": 3}))


def _coverage_exclusion_blocks(project):
    review = project / "reviews" / "phase-5-verify"
    review.mkdir(parents=True)
    (review / "alu-coverage-exclusions.md").write_text(
        "| Bin | Category |\n|---|---|\n| cp_mode.dbg | Unimplemented feature |\n")


class TestStopGatesYieldToBackgroundAgents:
    """Agents run in the background by default (CLI 2.1.282), so the leader's Stop comes while
    its orchestrator still works. Every Stop gate lets that Stop through, silently and without
    spending its budget; the agent's completion wakes the session, and the gates enforce at
    that turn's Stop."""

    # Each gate, the budget ids its chain count names, and a setup that makes it block.
    GATES = {
        "rtl-verify-stop-gate.sh": (("verify",), _verify_blocks),
        "rtl-p6-cascade-gate.sh": (("p6-cascade",), _p6_cascade_blocks),
        "rtl-skill-completion-gate.sh": (("skill-completion",), _skill_completion_blocks),
        "stop-gate.sh": (("ultraloop", "ppa-loop", "autopilot"), _autopilot_blocks),
        "rtl-coverage-exclusion-gate.sh": (("coverage-exclusion",), _coverage_exclusion_blocks),
    }
    # Background work as Claude Code 2.1.282 writes it into a Stop input.
    AGENT = {"id": "a6480a3838dc76cfa", "type": "subagent", "status": "running",
             "description": "Run the Phase 4 orchestrator",
             "agent_type": "rtl-agent-team:p4-implement-orchestrator"}
    SHELL = {"id": "b2f1c9d0e4", "type": "shell", "status": "running",
             "description": "Serve the waveform viewer", "command": "python3 -m http.server 8000"}
    CRON = {"id": "c7d3e1", "schedule": "*/5 * * * *", "recurring": True,
            "prompt": "Check the regression"}

    def _stop(self, project, gate, active, tasks, crons=(), prompt="p-1"):
        return run_hook(HOOKS_DIR / gate, {
            "cwd": str(project), "prompt_id": prompt, "hook_event_name": "Stop",
            "stop_hook_active": active, "last_assistant_message": "Launched the orchestrator.",
            "background_tasks": list(tasks), "session_crons": list(crons)})

    def _seed_budgets(self, project, ids, notice):
        """Earlier blocks in this chain spent part of each budget, and maybe showed the notice."""
        for budget_id in ids:
            (project / ".rat" / "state" / f"stop-budget-{budget_id}.txt").write_text(
                f"1\nfp-x\n2\n{notice}\np-1\n")

    @staticmethod
    def _snapshot(project):
        return {str(p.relative_to(project)): p.read_bytes() for p in project.rglob("*") if p.is_file()}

    @pytest.mark.parametrize("notice", ["0", "1"])
    @pytest.mark.parametrize("gate", sorted(GATES))
    def test_agent_in_flight_lets_the_stop_through_without_spending_the_budget(self, tmp_project, gate, notice):
        ids, blocks = self.GATES[gate]
        blocks(tmp_project)
        self._seed_budgets(tmp_project, ids, notice)
        before = self._snapshot(tmp_project)
        assert self._stop(tmp_project, gate, True, [self.SHELL, self.AGENT], [self.CRON]) == {"continue": True}
        after = self._snapshot(tmp_project)
        # Only each budget's line 3, the chain's Stop count, moved; line 6 records the yield.
        for budget_id in ids:
            name = f".rat/state/stop-budget-{budget_id}.txt"
            assert after.pop(name).decode() == f"1\nfp-x\n3\n{notice}\np-1\nyield\n"
            before.pop(name)
        assert after == before

    @pytest.mark.parametrize("tasks,crons", [([], []), ([SHELL], [CRON])],
                             ids=["nothing-in-flight", "shell-and-cron"])
    @pytest.mark.parametrize("gate", sorted(GATES))
    def test_the_same_stop_without_an_agent_blocks(self, tmp_project, gate, tasks, crons):
        ids, blocks = self.GATES[gate]
        blocks(tmp_project)
        self._seed_budgets(tmp_project, ids, "0")
        _assert_stop_blocked(self._stop(tmp_project, gate, True, tasks, crons))

    @pytest.mark.parametrize("gate", sorted(GATES))
    def test_gate_enforces_at_the_stop_after_the_agent_finished(self, tmp_project, gate):
        ids, blocks = self.GATES[gate]
        blocks(tmp_project)
        # The leader's turn ends right after it launched the agent.
        assert self._stop(tmp_project, gate, False, [self.AGENT]) == {"continue": True}
        for budget_id in ids:
            budget = tmp_project / ".rat" / "state" / f"stop-budget-{budget_id}.txt"
            assert budget.read_text() == "0\n\n1\n0\np-1\nyield\n"
        # The completion notification starts a new turn; at its Stop nothing is in flight.
        _assert_stop_blocked(self._stop(tmp_project, gate, False, [], prompt="p-2"))

    @pytest.mark.parametrize("gate", sorted(GATES))
    def test_handing_the_work_to_new_background_agents_still_reaches_the_notice(self, tmp_project, gate):
        # Each completion turn starts a new chain. If the gate blocks there and Claude hands
        # the work to another background agent, the chain ends in a yield; the next chain
        # keeps the count, so the user still gets the notice after the usual blocks.
        ids, blocks = self.GATES[gate]
        blocks(tmp_project)
        outcomes = []
        for turn in range(1, 6):
            result = self._stop(tmp_project, gate, False, [], prompt=f"p-{turn}")
            if "systemMessage" in result:
                outcomes.append("notice")
                break
            _assert_stop_blocked(result)
            outcomes.append("block")
            assert self._stop(tmp_project, gate, True, [self.AGENT], prompt=f"p-{turn}") == {"continue": True}
        assert outcomes[-1] == "notice", outcomes
        assert outcomes.count("block") <= 3, outcomes
