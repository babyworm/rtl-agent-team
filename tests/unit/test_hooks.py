"""Tests for hook scripts — routing inject, edit tracker, and stop gates."""

import datetime
import json
import os
import re
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from tests.conftest import HOOKS_DIR, REPO_ROOT, run_hook


def _setup_marker(tmp_project):
    """Create the .claude/rules/rtl-coding-conventions.md setup marker."""
    rules_dir = tmp_project / ".claude" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    (rules_dir / "rtl-coding-conventions.md").write_text("# marker")


class TestRtlOrchestratorInject:
    """Tests for hooks/rtl-orchestrator-inject.sh."""

    HOOK = HOOKS_DIR / "rtl-orchestrator-inject.sh"

    def test_no_project_markers_no_injection(self, tmp_path):
        result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
        assert result.get("raw_stdout", "") == ""

    def test_rtl_dir_triggers_injection(self, tmp_path):
        (tmp_path / "rtl").mkdir()
        result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
        output = result.get("raw_stdout", "")
        assert "# RTL Agent Team — Active Project Rules" in output
        assert "/rtl-agent-team:rat-auto-design" in output
        assert "Action Skills first" in output

    def test_docs_dir_triggers_injection(self, tmp_path):
        (tmp_path / "docs").mkdir()
        result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
        output = result.get("raw_stdout", "")
        assert "## Pipeline Rules" in output
        assert "/rtl-agent-team:p1-spec-research" in output

    def test_rtl_state_dir_triggers_injection(self, tmp_path):
        (tmp_path / ".rat").mkdir()
        result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
        output = result.get("raw_stdout", "")
        assert "/rtl-agent-team:rtl-p5-verify" in output
        assert "/rtl-agent-team:rtl-p6-design-review" in output


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

    def test_edit_tracker_session_scoped_in_team_mode(self, tmp_project):
        """In team mode with SESSION_ID, tracking file uses session suffix."""
        self._write_team_config(tmp_project)
        env = {"CLAUDE_SESSION_ID": "worker-abc-123"}
        run_hook(
            self.EDIT_HOOK,
            {"cwd": str(tmp_project), "file_path": "rtl/mod_a.sv"},
            env=env,
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
        """Two different SESSION_IDs write to separate tracking files."""
        self._write_team_config(tmp_project)
        run_hook(
            self.EDIT_HOOK,
            {"cwd": str(tmp_project), "file_path": "rtl/a.sv"},
            env={"CLAUDE_SESSION_ID": "session-1"},
        )
        run_hook(
            self.EDIT_HOOK,
            {"cwd": str(tmp_project), "file_path": "rtl/b.sv"},
            env={"CLAUDE_SESSION_ID": "session-2"},
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
        (state_dir / "rtl-modified-files-worker-1.txt").write_text("rtl/a.sv\n")
        (state_dir / "rtl-modified-files-worker-2.txt").write_text("rtl/b.sv\n")
        # Leader session runs the gate — must match leader_session_id
        result = run_hook(
            self.GATE_HOOK,
            {"cwd": str(tmp_project)},
            env={"CLAUDE_SESSION_ID": "leader-001"},
        )
        # Gate should block because there are unverified files
        assert result["continue"] is False
        ctx = result.get("reason", "")
        # Should mention both files (aggregated)
        assert "2 RTL files" in ctx  # 2 files total

    def test_verify_gate_cleanup_removes_session_files(self, tmp_project):
        """When verify-done exists, gate cleans up all session-scoped files."""
        self._write_team_config(tmp_project, leader_id="leader-001")
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "rtl-modified-files-worker-1.txt").write_text("rtl/a.sv\n")
        (state_dir / "rtl-modified-files-worker-2.txt").write_text("rtl/b.sv\n")
        (state_dir / "rtl-verify-done").touch()
        # Leader session runs the gate — must match leader_session_id
        result = run_hook(
            self.GATE_HOOK,
            {"cwd": str(tmp_project)},
            env={"CLAUDE_SESSION_ID": "leader-001"},
        )
        assert result["continue"] is True
        # All session files should be cleaned up
        assert not (state_dir / "rtl-modified-files-worker-1.txt").exists()
        assert not (state_dir / "rtl-modified-files-worker-2.txt").exists()

    def test_skill_activation_skipped_for_worker(self, tmp_project):
        """Worker sessions should skip skill state management."""
        self._write_team_config(tmp_project, leader_id="leader-001")
        env = {"CLAUDE_SESSION_ID": "worker-session-99", "CLAUDE_PLUGIN_ROOT": str(HOOKS_DIR / "..")}
        result = run_hook(
            self.SKILL_HOOK,
            {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5-verify"},
            env=env,
        )
        assert result["continue"] is True
        # skill-active.json should NOT be created by worker
        skill_state = tmp_project / ".rat" / "state" / "skill-active.json"
        assert not skill_state.exists(), "Worker should not create skill-active.json"


class TestRtlVerifyStopGate:
    """Tests for hooks/rtl-verify-stop-gate.sh."""

    HOOK = HOOKS_DIR / "rtl-verify-stop-gate.sh"

    def test_no_tracked_files_allows_exit(self, tmp_project):
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_empty_tracking_file_allows_exit(self, tmp_project):
        track = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        track.write_text("")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_tracked_files_without_verification_blocks(self, tmp_project):
        track = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        track.write_text("rtl/module/top.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False

    def test_verify_done_allows_exit(self, tmp_project):
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/module/top.sv\n")
        (state_dir / "rtl-verify-done").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_verify_waiver_allows_exit(self, tmp_project):
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/module/top.sv\n")
        (state_dir / "rtl-verify-waiver").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_cleanup_after_verify_done(self, tmp_project):
        state_dir = tmp_project / ".rat" / "state"
        track = state_dir / "rtl-modified-files.txt"
        done = state_dir / "rtl-verify-done"
        track.write_text("rtl/module/top.sv\n")
        done.touch()
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert not track.exists()
        assert not done.exists()

    def test_cleanup_after_waiver(self, tmp_project):
        state_dir = tmp_project / ".rat" / "state"
        track = state_dir / "rtl-modified-files.txt"
        waiver = state_dir / "rtl-verify-waiver"
        track.write_text("rtl/a.sv\nrtl/b.sv\n")
        waiver.touch()
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert not track.exists()
        assert not waiver.exists()

    def test_multiple_files_blocks(self, tmp_project):
        """Multiple tracked files should all be mentioned in block message."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/a.sv\nrtl/b.sv\nrtl/c.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "3 RTL files" in ctx  # 3 files

    def test_fallback_file_blocks_exit(self, tmp_project):
        """Fallback entries from lock failure must block exit even without main track file."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "rtl-modified-files-fallback.txt").write_text("rtl/alu/alu.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "1 RTL files" in ctx

    def test_fallback_merged_with_main_track(self, tmp_project):
        """Fallback and main track entries are both counted."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/a.sv\n")
        (state_dir / "rtl-modified-files-fallback.txt").write_text("rtl/b.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "2 RTL files" in ctx

    def test_verify_done_cleans_fallback(self, tmp_project):
        """Verify-done should clean up fallback file too."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/a.sv\n")
        (state_dir / "rtl-modified-files-fallback.txt").write_text("rtl/b.sv\n")
        (state_dir / "rtl-verify-done").touch()
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
        (state_dir / "rtl-modified-files-fallback.txt").write_text("rtl/c.sv\n")
        result = run_hook(
            self.HOOK,
            {"cwd": str(tmp_project)},
            env={"CLAUDE_SESSION_ID": "leader-001"},
        )
        assert result["continue"] is False

    def test_verify_stop_gate_uses_shared_json_util(self):
        content = (HOOKS_DIR / "rtl-verify-stop-gate.sh").read_text()
        assert "lib/json-util.sh" in content
        assert "lib/team-gate-util.sh" in content
        assert "jsonu_get_input_string" in content
        assert "teamu_should_skip_gate" in content


class TestStopGate:
    """Tests for hooks/stop-gate.sh."""

    HOOK = HOOKS_DIR / "stop-gate.sh"

    def _write_autopilot_state(self, tmp_project, payload):
        state_file = tmp_project / ".rat" / "state" / "rat-auto-design-state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(payload, indent=2))
        return state_file

    def test_no_state_file_allows_exit(self, tmp_project):
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_legacy_state_file_migrated_and_blocks(self, tmp_project):
        """Pre-0.6.10 state file (rtl-autopilot-state.json) should be migrated and still block exit."""
        legacy_file = tmp_project / ".rat" / "state" / "rtl-autopilot-state.json"
        legacy_file.parent.mkdir(parents=True, exist_ok=True)
        legacy_file.write_text(json.dumps({"phase": 3}))
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
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
        assert result["continue"] is False
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
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "primary strategy" in ctx
        assert "p2-quality-gate" in ctx

    def test_fallback_message_includes_dynamic_prompt(self, tmp_project):
        self._write_autopilot_state(
            tmp_project,
            {
                "status": "in_progress",
                "orchestration_control": {
                    "active_gate_id": "p5-5c-gate",
                    "active_gate_retry_limit": 2,
                    "active_gate_primary_attempts": 3,
                    "active_gate_fallback_attempts": 0,
                    "active_gate_last_chance_attempts": 0,
                    "active_gate_strategy": "fallback",
                    "dynamic_prompt_text": "Switch to module-split bugfix strategy.",
                    "needs_user_decision": False
                }
            },
        )
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "fallback strategy" in ctx
        assert "Switch to module-split bugfix strategy." in ctx

    def test_last_chance_message(self, tmp_project):
        self._write_autopilot_state(
            tmp_project,
            {
                "status": "in_progress",
                "orchestration_control": {
                    "active_gate_id": "p5-final-gate",
                    "active_gate_retry_limit": 2,
                    "active_gate_primary_attempts": 3,
                    "active_gate_fallback_attempts": 2,
                    "active_gate_last_chance_attempts": 0,
                    "active_gate_strategy": "last_chance",
                    "needs_user_decision": False
                }
            },
        )
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "last-chance" in ctx.lower()

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
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "Ask user" in ctx or "user" in ctx.lower()

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
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "p3-quality-gate" in ctx
        assert "primary=1" in ctx

    def test_stop_gate_uses_shared_json_util(self):
        content = (HOOKS_DIR / "stop-gate.sh").read_text()
        assert "lib/json-util.sh" in content
        assert "jsonu_get_file_path_string" in content
        assert "jsonu_get_file_path_bool" in content
        assert "jsonu_get_file_path_num" in content


class TestRtlEditTrackerBash:
    """B1: Tests for Bash command RTL detection in hooks/rtl-edit-tracker.sh."""

    HOOK = HOOKS_DIR / "rtl-edit-tracker.sh"

    def test_bash_command_with_sv_file_tracked(self, tmp_project):
        """B1: Bash write command containing .sv file should trigger RTL tracking."""
        stdin = {"cwd": str(tmp_project), "command": "sed -i 's/old/new/' rtl/module/top.sv"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "RTL Verify Gate" in ctx
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert track_file.exists()
        assert "top.sv" in track_file.read_text()

    def test_bash_lint_only_not_tracked(self, tmp_project):
        """B1: verilator --lint-only is read-only and should NOT trigger RTL tracking."""
        stdin = {"cwd": str(tmp_project), "command": "verilator --lint-only rtl/module/top.sv"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert not track_file.exists()

    def test_bash_verible_lint_not_tracked(self, tmp_project):
        """B1: verible-verilog-lint is read-only and should NOT trigger RTL tracking."""
        stdin = {"cwd": str(tmp_project), "command": "verible-verilog-lint rtl/module/top.sv"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert not track_file.exists()

    def test_bash_backgrounded_lint_not_tracked(self, tmp_project):
        """B1: Backgrounded lint-only command should NOT trigger RTL tracking."""
        stdin = {"cwd": str(tmp_project), "command": "verilator --lint-only -Wall rtl/top.sv &"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert not track_file.exists()

    def test_bash_command_without_rtl_passthrough(self, tmp_project):
        """B1: Bash command without RTL extensions should pass through silently."""
        stdin = {"cwd": str(tmp_project), "command": "ls -la docs/"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        assert "hookSpecificOutput" not in result

    def test_bash_mixed_command_lint_plus_write_tracked(self, tmp_project):
        """B1: Mixed command with lint AND write must still trigger RTL tracking."""
        stdin = {"cwd": str(tmp_project), "command": "sed -i 's/x/y/' rtl/top.sv && verilator --lint-only rtl/top.sv"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "RTL Verify Gate" in ctx
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert track_file.exists()

    def test_bash_background_ampersand_mixed_tracked(self, tmp_project):
        """B1: Background & separating lint and write must still trigger tracking."""
        stdin = {"cwd": str(tmp_project), "command": "verilator --lint-only rtl/top.sv & sed -i 's/x/y/' rtl/top.sv"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "RTL Verify Gate" in ctx
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert track_file.exists()

    def test_bash_lint_substring_in_sed_still_tracked(self, tmp_project):
        """B1: sed command containing 'verilator --lint-only' in quoted text must be tracked."""
        stdin = {"cwd": str(tmp_project), "command": "sed -i 's/verilator --lint-only/x/' rtl/top.sv"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "RTL Verify Gate" in ctx
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert track_file.exists()

    def test_bash_adjacent_ampersand_rtl_extracted(self, tmp_project):
        """B1: RTL path adjacent to && should still be extracted by awk tokenizer."""
        stdin = {"cwd": str(tmp_project), "command": "sed -i 's/x/y/' rtl/top.sv&&echo done"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "RTL Verify Gate" in ctx
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert track_file.exists()

    def test_bash_readonly_prefix_with_write_tracked(self, tmp_project):
        """B1: Read-only prefix (grep) followed by write via && must be tracked."""
        stdin = {"cwd": str(tmp_project), "command": "grep foo rtl/top.sv && sed -i 's/x/y/' rtl/top.sv"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "RTL Verify Gate" in ctx
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert track_file.exists()

    def test_bash_redirect_to_rtl_file_tracked(self, tmp_project):
        """B1: Output redirection to RTL file must be tracked even with read-only prefix."""
        stdin = {"cwd": str(tmp_project), "command": "cat /dev/null > rtl/top.sv"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "RTL Verify Gate" in ctx
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert track_file.exists()

    def test_bash_lint_redirect_to_log_not_tracked(self, tmp_project):
        """B1: Lint redirecting to non-RTL log file should NOT be tracked."""
        stdin = {"cwd": str(tmp_project), "command": "verilator --lint-only -Wall rtl/top.sv > lint.log"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert not track_file.exists()

    def test_bash_pipe_readonly_not_tracked(self, tmp_project):
        """B1: Pipe from grep to wc is read-only — should NOT be tracked."""
        stdin = {"cwd": str(tmp_project), "command": "grep foo rtl/top.sv | wc -l"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert not track_file.exists()

    def test_bash_lint_stderr_redirect_not_tracked(self, tmp_project):
        """B1: Lint with 2>&1 is read-only — should NOT be tracked."""
        stdin = {"cwd": str(tmp_project), "command": "verilator --lint-only -Wall rtl/top.sv > lint.log 2>&1"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert not track_file.exists()

    def test_bash_quoted_rtl_path_tracked(self, tmp_project):
        """B1: Bash command with quoted RTL path should still trigger tracking."""
        stdin = {"cwd": str(tmp_project), "command": "sed -i 's/x/y/' 'rtl/top.sv'"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "RTL Verify Gate" in ctx
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert track_file.exists()

    def test_bash_command_with_svh_tracked(self, tmp_project):
        """B1: Bash write command containing .svh file should trigger tracking."""
        stdin = {"cwd": str(tmp_project), "command": "sed -i 's/x/y/' rtl/include/defines.svh"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "RTL Verify Gate" in ctx

    def test_bash_command_with_v_file_tracked(self, tmp_project):
        """B1: Bash command containing .v file should trigger tracking."""
        stdin = {"cwd": str(tmp_project), "command": "iverilog -o sim rtl/legacy/counter.v"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "RTL Verify Gate" in ctx

    def test_bash_empty_command_passthrough(self, tmp_project):
        """B1: Empty command should pass through."""
        stdin = {"cwd": str(tmp_project), "command": ""}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        assert "hookSpecificOutput" not in result

    def test_bash_no_file_path_no_command_passthrough(self, tmp_project):
        """B1: Missing both file_path and command should pass through."""
        stdin = {"cwd": str(tmp_project)}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        assert "hookSpecificOutput" not in result

    def test_bash_multiple_sv_files_tracked(self, tmp_project):
        """B1: Bash write command with multiple RTL files should track all."""
        stdin = {"cwd": str(tmp_project), "command": "sed -i 's/x/y/' rtl/a.sv rtl/b.sv"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        content = track_file.read_text()
        assert "a.sv" in content
        assert "b.sv" in content

    def test_bash_readonly_command_not_tracked(self, tmp_project):
        """B1: Read-only commands (cat, grep, etc.) should not trigger RTL tracking."""
        for cmd in ["cat rtl/top.sv", "grep pattern rtl/mod.sv", "head -20 rtl/block.svh",
                     "diff rtl/a.sv rtl/b.sv", "wc -l rtl/top.sv"]:
            stdin = {"cwd": str(tmp_project), "command": cmd}
            result = run_hook(self.HOOK, stdin)
            assert result["continue"] is True
            ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
            assert "RTL Verify Gate" not in ctx, f"Read-only command should not trigger tracking: {cmd}"
        # Tracking file must not be created by read-only commands
        track_file = tmp_project / ".rat" / "state" / "rtl-modified-files.txt"
        assert not track_file.exists(), "Read-only commands must not create tracking file"

    def test_bash_write_invalidates_verify_done(self, tmp_project):
        """B1: Bash write command must invalidate verify-done/waiver markers."""
        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "rtl-verify-done").touch()
        (state_dir / "rtl-verify-waiver").touch()
        stdin = {"cwd": str(tmp_project), "command": "sed -i 's/x/y/' rtl/mod.sv"}
        run_hook(self.HOOK, stdin)
        assert not (state_dir / "rtl-verify-done").exists(), "Bash RTL write must invalidate verify-done"
        assert not (state_dir / "rtl-verify-waiver").exists(), "Bash RTL write must invalidate verify-waiver"

    def test_bash_phase6_stale_on_rtl_command(self, tmp_project):
        """B1: Bash RTL command should mark Phase 6 stale if full review set exists."""
        p6_dir = tmp_project / "reviews" / "phase-6-review"
        p6_dir.mkdir(parents=True)
        (p6_dir / "code-review.md").write_text("# Code Review")
        (p6_dir / "design-review.md").write_text("# Design Review")
        (p6_dir / "design-note.md").write_text("# Design Note")
        (p6_dir / "improvements.md").write_text("# Improvements")
        stdin = {"cwd": str(tmp_project), "command": "sed -i 's/foo/bar/' rtl/mod.sv"}
        result = run_hook(self.HOOK, stdin)
        stale = tmp_project / ".rat" / "state" / "phase6-stale"
        assert stale.exists()


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
        assert result["continue"] is False
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

    def test_p6_cascade_gate_uses_shared_json_util(self):
        content = (HOOKS_DIR / "rtl-p6-cascade-gate.sh").read_text()
        assert "lib/json-util.sh" in content
        assert "lib/team-gate-util.sh" in content
        assert "jsonu_get_input_string" in content
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
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "not updated" in ctx.lower() or "cascade" in ctx.lower()

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
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "not found" in ctx.lower() or "not updated" in ctx.lower()


class TestSkillCompletionGate:
    """Tests for hooks/rtl-skill-completion-gate.sh."""

    HOOK = HOOKS_DIR / "rtl-skill-completion-gate.sh"

    def _write_skill_state(self, tmp_project, skill="rtl-p4s-bugfix", iteration=1,
                           max_iterations=5, all_complete=False,
                           pending="lint_pass, tb_updated, sim_pass"):
        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)

        state = {
            "skill": skill,
            "active": True,
            "iteration": iteration,
            "max_iterations": max_iterations,
            "pending": pending,
            "all_complete": all_complete,
            "started_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        (state_dir / "skill-active.json").write_text(json.dumps(state, indent=2))

    def test_no_skill_state_allows_exit(self, tmp_project):
        """No skill-active.json → allow exit."""
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_active_skill_blocks_exit(self, tmp_project):
        """Active skill with all_complete=false → block exit."""
        self._write_skill_state(tmp_project)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False

    def test_completed_skill_allows_exit(self, tmp_project):
        """Active skill with all_complete=true → allow exit."""
        self._write_skill_state(tmp_project, all_complete=True)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_completed_skill_cleans_state(self, tmp_project):
        """After allowing exit for completed skill, state file should be removed."""
        self._write_skill_state(tmp_project, all_complete=True)
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        assert not state_file.exists()

    def test_max_iterations_still_blocks_under_ladder(self, tmp_project):
        """At iteration == max_iterations, ladder remains active and blocks exit."""
        self._write_skill_state(tmp_project, iteration=5, max_iterations=5)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "primary" in ctx.lower()

    def test_max_iterations_does_not_clean_state_under_ladder(self, tmp_project):
        """Ladder mode should keep state for fallback/last-chance escalation."""
        self._write_skill_state(tmp_project, iteration=5, max_iterations=5)
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        assert state_file.exists()

    def test_iteration_increments_on_block(self, tmp_project):
        """Each block should increment the iteration counter."""
        self._write_skill_state(tmp_project, iteration=1)
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        content = state_file.read_text()
        assert '"iteration": 2' in content

    def test_sed_script_tempfile_cleaned_up(self, tmp_project):
        """Verify no skill-gate-sed.* tempfiles are left after hook run."""
        import glob
        self._write_skill_state(tmp_project)
        before = set(glob.glob("/tmp/skill-gate-sed.*"))
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        after = set(glob.glob("/tmp/skill-gate-sed.*"))
        assert after == before, f"Leaked tempfiles: {after - before}"

    def test_block_message_includes_skill_name(self, tmp_project):
        """Block message should include the skill name."""
        self._write_skill_state(tmp_project, skill="rtl-p4s-bugfix")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        ctx = result.get("reason", "")
        assert "rtl-p4s-bugfix" in ctx

    def test_block_message_includes_pending(self, tmp_project):
        """Block message should include pending criteria."""
        self._write_skill_state(tmp_project, pending="lint_pass, sim_pass")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        ctx = result.get("reason", "")
        assert "lint_pass" in ctx or "sim_pass" in ctx

    def test_stale_state_allows_exit(self, tmp_project):
        """State older than 2 hours should be treated as stale and cleaned up."""
        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        # Write a state with a timestamp 3 hours ago

        old_time = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = {
            "skill": "rtl-p4s-bugfix",
            "active": True,
            "iteration": 1,
            "max_iterations": 5,
            "pending": "lint_pass",
            "all_complete": False,
            "started_at": old_time
        }
        (state_dir / "skill-active.json").write_text(json.dumps(state, indent=2))
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_ladder_primary_stage_blocks(self, tmp_project):
        self._write_skill_state(tmp_project, iteration=1, max_iterations=2)
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        state = json.loads(state_file.read_text())
        state["use_escalation_ladder"] = True
        state["dynamic_prompt"] = "primary prompt"
        state_file.write_text(json.dumps(state, indent=2))

        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "primary" in ctx.lower()

    def test_ladder_fallback_stage_blocks(self, tmp_project):
        self._write_skill_state(tmp_project, iteration=3, max_iterations=2)
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        state = json.loads(state_file.read_text())
        state["use_escalation_ladder"] = True
        state["dynamic_prompt"] = "fallback prompt"
        state_file.write_text(json.dumps(state, indent=2))

        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "fallback" in ctx.lower()
        assert "fallback prompt" in ctx

    def test_ladder_last_chance_stage_blocks(self, tmp_project):
        self._write_skill_state(tmp_project, iteration=5, max_iterations=2)
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        state = json.loads(state_file.read_text())
        state["use_escalation_ladder"] = True
        state_file.write_text(json.dumps(state, indent=2))

        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "last_chance" in ctx or "last-chance" in ctx

    def test_ladder_after_last_chance_requires_user(self, tmp_project):
        self._write_skill_state(tmp_project, iteration=6, max_iterations=2)
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        state = json.loads(state_file.read_text())
        state["use_escalation_ladder"] = True
        state_file.write_text(json.dumps(state, indent=2))

        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("reason", "")
        assert "사용자" in ctx or "user" in ctx.lower()

    def test_legacy_disabled_ladder_is_migrated_and_still_blocks(self, tmp_project):
        self._write_skill_state(tmp_project, iteration=5, max_iterations=2)
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        state = json.loads(state_file.read_text())
        state["use_escalation_ladder"] = False
        state_file.write_text(json.dumps(state, indent=2))

        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        migrated = json.loads(state_file.read_text())
        assert migrated["use_escalation_ladder"] is True

    def test_skill_completion_gate_uses_shared_json_util(self):
        content = (HOOKS_DIR / "rtl-skill-completion-gate.sh").read_text()
        assert "lib/json-util.sh" in content
        assert "jsonu_get_input_string" in content
        assert "jsonu_get_file_path_string" in content
        assert "jsonu_get_file_path_bool" in content
        assert "jsonu_get_file_path_num" in content


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

        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4s-bugfix"}
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

        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:systemverilog"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        state_file = tmp_project / ".rat" / "state" / "skill-active.json"
        assert not state_file.exists()

    def test_no_criteria_file_no_state(self, tmp_project):
        """Missing criteria file should not create state."""
        _setup_marker(tmp_project)
        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4s-bugfix"}
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

        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4s-bugfix"}
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

        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4s-bugfix"}
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

        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4s-bugfix"}
        result = run_hook(self.HOOK, stdin, env={"CLAUDE_PLUGIN_ROOT": str(tmp_project)})
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "rtl-p4s-bugfix" in ctx

    def test_rtl_setup_bootstrap_installs_template_scripts(self, tmp_project):
        """rat-init-project activation should auto-install run_xxx.sh templates into project."""
        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rat-init-project"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True

        run_sim = tmp_project / "scripts" / "run_sim.sh"
        run_lint = tmp_project / "lint" / "scripts" / "run_lint.sh"
        run_syn = tmp_project / "syn" / "scripts" / "run_syn.sh"
        run_cdc = tmp_project / "lint" / "scripts" / "run_cdc.sh"

        for path in [run_sim, run_lint, run_syn, run_cdc]:
            assert path.exists(), f"Missing auto-installed script: {path}"
            assert os.access(path, os.X_OK), f"Script should be executable: {path}"

        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "SETUP_TEMPLATE_INSTALL" in ctx

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


class TestPhaseStateBootstrap:
    """Tests for hooks/rtl-phase-state-bootstrap.sh."""

    HOOK = HOOKS_DIR / "rtl-phase-state-bootstrap.sh"

    def test_non_target_skill_ignored(self, tmp_project):
        _setup_marker(tmp_project)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4-implement"})
        assert result["continue"] is True
        assert not (tmp_project / ".rat" / "state" / "p4-state.json").exists()

    def test_setup_missing_does_not_bootstrap(self, tmp_project):
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4-rapid-impl"}, env={"HOME": str(tmp_project)})
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
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": skill_name})
        assert result["continue"] is True

        state_path = tmp_project / ".rat" / "state" / state_file
        assert state_path.exists()
        data = json.loads(state_path.read_text())
        assert data["phase"] == phase
        assert "{{TIMESTAMP}}" not in state_path.read_text()

    def test_existing_state_not_overwritten(self, tmp_project):
        _setup_marker(tmp_project)
        state_path = tmp_project / ".rat" / "state" / "p4-state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text('{"phase":"p4","status":"custom"}')

        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4-rapid-impl"})
        assert result["continue"] is True
        assert json.loads(state_path.read_text())["status"] == "custom"

    def test_p5b_blocks_without_p5a_state(self, tmp_project):
        _setup_marker(tmp_project)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "P5B Gate BLOCKED" in ctx
        assert "rtl-p5a-functional-closure" in ctx
        assert not (tmp_project / ".rat" / "state" / "p5b-state.json").exists()

    def test_p5b_blocks_when_p5a_verdict_not_pass(self, tmp_project):
        _setup_marker(tmp_project)
        p5a_state = tmp_project / ".rat" / "state" / "p5a-state.json"
        p5a_state.parent.mkdir(parents=True, exist_ok=True)
        p5a_state.write_text(
            json.dumps({"gates": {"p5a_exit": {"verdict": "fail"}}}, indent=2)
        )

        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "gates.p5a_exit.verdict=fail" in ctx
        assert not (tmp_project / ".rat" / "state" / "p5b-state.json").exists()

    def test_p5b_bootstraps_when_p5a_pass(self, tmp_project):
        _setup_marker(tmp_project)
        p5a_state = tmp_project / ".rat" / "state" / "p5a-state.json"
        p5a_state.parent.mkdir(parents=True, exist_ok=True)
        p5a_state.write_text(
            json.dumps({"gates": {"p5a_exit": {"verdict": "pass"}}}, indent=2)
        )

        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"})
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
        (state_dir / "rtl-modified-files.txt").write_text("rtl/top.sv\n")

        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("permissionDecisionReason", "")
        assert "stale functional closure" in ctx
        assert not (state_dir / "p5b-state.json").exists()

    def test_p5b_allows_when_p5a_newer_than_tracked_rtl_changes(self, tmp_project):
        _setup_marker(tmp_project)

        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        rtl_dir = tmp_project / "rtl"
        rtl_dir.mkdir(parents=True, exist_ok=True)
        (rtl_dir / "top.sv").write_text("module top; endmodule\n")
        (state_dir / "rtl-modified-files.txt").write_text("rtl/top.sv\n")
        os.utime(str(rtl_dir / "top.sv"), (1000000, 1000000))

        p5a_state = state_dir / "p5a-state.json"
        p5a_state.write_text(json.dumps({"gates": {"p5a_exit": {"verdict": "pass"}}}, indent=2))
        # Use explicit mtime: p5a newer than RTL
        os.utime(str(p5a_state), (1000002, 1000002))

        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"})
        assert result["continue"] is True
        assert (state_dir / "p5b-state.json").exists()

    def test_missing_json_parser_emits_setup_hint_with_fallback(self, tmp_project):
        _setup_marker(tmp_project)
        result = run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4-rapid-impl"},
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

        result = run_hook(self.HOOK, raw_input)
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
            assert result.get("continue") is False

        final_state = json.loads((state_dir / "skill-active.json").read_text())
        assert final_state["iteration"] == 4, f"Expected iteration=4, got {final_state['iteration']}"


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
        # Worker session (no CLAUDE_SESSION_ID or different from leader)
        result = run_hook(self.HOOKS["stop-gate"], {"cwd": str(tmp_project)})
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
        # Simulate leader session via env
        import subprocess
        env = {**os.environ, "CLAUDE_SESSION_ID": "leader-abc"}
        result = subprocess.run(
            ["sh", str(self.HOOKS["stop-gate"])],
            capture_output=True, text=True,
            input=json.dumps({"cwd": str(tmp_project)}),
            env=env, timeout=10,
        )
        parsed = json.loads(result.stdout)
        assert parsed["continue"] is False

    def test_worker_bypasses_verify_gate(self, tmp_project):
        """Worker in team mode → verify gate allows exit even with tracked files."""
        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/top.sv\n")
        result = run_hook(self.HOOKS["verify-stop-gate"], {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_worker_bypasses_p6_cascade(self, tmp_project):
        """Worker in team mode → P6 cascade allows exit even with stale marker."""
        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOKS["p6-cascade-gate"], {"cwd": str(tmp_project)})
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
        result = run_hook(self.HOOKS["skill-completion-gate"], {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_leader_session_still_blocked_by_verify_gate(self, tmp_project):
        """Leader session in team mode → verify gate still blocks."""
        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/top.sv\n")
        import subprocess
        env = {**os.environ, "CLAUDE_SESSION_ID": "leader-abc"}
        result = subprocess.run(
            ["sh", str(self.HOOKS["verify-stop-gate"])],
            capture_output=True, text=True,
            input=json.dumps({"cwd": str(tmp_project)}),
            env=env, timeout=10,
        )
        parsed = json.loads(result.stdout)
        assert parsed["continue"] is False

    def test_leader_session_still_blocked_by_p6_cascade(self, tmp_project):
        """Leader session in team mode → P6 cascade gate still blocks."""
        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "phase6-stale").touch()
        import subprocess
        env = {**os.environ, "CLAUDE_SESSION_ID": "leader-abc"}
        result = subprocess.run(
            ["sh", str(self.HOOKS["p6-cascade-gate"])],
            capture_output=True, text=True,
            input=json.dumps({"cwd": str(tmp_project)}),
            env=env, timeout=10,
        )
        parsed = json.loads(result.stdout)
        assert parsed["continue"] is False

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
        import subprocess
        env = {**os.environ, "CLAUDE_SESSION_ID": "leader-abc"}
        result = subprocess.run(
            ["sh", str(self.HOOKS["skill-completion-gate"])],
            capture_output=True, text=True,
            input=json.dumps({"cwd": str(tmp_project)}),
            env=env, timeout=10,
        )
        parsed = json.loads(result.stdout)
        assert parsed["continue"] is False

    def test_empty_leader_id_enforces_gate_fail_closed(self, tmp_project):
        """Empty leader_session_id with team_mode=true → fail-closed, gate enforced for all."""
        self._write_team_config(tmp_project, leader_id="")
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOKS["p6-cascade-gate"], {"cwd": str(tmp_project)})
        assert result["continue"] is False

    def test_stale_team_config_removed_and_gate_applies(self, tmp_project):
        """team-config.json older than 2h → removed, normal gate behavior resumes."""
        state_dir = tmp_project / ".rat" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        stale_config = {
            "team_mode": True,
            "team_name": "p5-verify",
            "leader_session_id": "leader-old",
            "phase": "p5",
            "created_at": "2020-01-01T00:00:00Z"
        }
        (state_dir / "team-config.json").write_text(json.dumps(stale_config, indent=2))
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOKS["p6-cascade-gate"], {"cwd": str(tmp_project)})
        # Stale config removed → gate blocks as normal
        assert result["continue"] is False
        assert not (state_dir / "team-config.json").exists()

    def test_team_mode_false_does_not_bypass(self, tmp_project):
        """team_mode=false → no bypass, normal behavior."""
        self._write_team_config(tmp_project, team_mode=False, leader_id="leader-abc")
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOKS["p6-cascade-gate"], {"cwd": str(tmp_project)})
        assert result["continue"] is False

    def test_stop_hooks_use_shared_team_gate_util(self):
        for _, hook_path in self.HOOKS.items():
            content = hook_path.read_text()
            assert "lib/team-gate-util.sh" in content
            assert "teamu_should_skip_gate" in content


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
        """Active autopilot state → continue=false under sed fallback."""
        state_dir = tmp_project / ".rat" / "state"
        state_file = state_dir / "rat-auto-design-state.json"
        state_file.write_text(json.dumps({"status": "in_progress", "phase": 3}, indent=2))
        result = run_hook(
            self.HOOKS["stop-gate"],
            {"cwd": str(tmp_project)},
            env=self.FALLBACK_ENV,
        )
        assert result["continue"] is False

    # ── verify-stop-gate ─────────────────────────────────────────────────────

    def test_verify_gate_fallback_blocks_unverified(self, tmp_project):
        """Tracked files without verification → continue=false under sed fallback."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/module/top.sv\n")
        result = run_hook(
            self.HOOKS["verify-stop-gate"],
            {"cwd": str(tmp_project)},
            env=self.FALLBACK_ENV,
        )
        assert result["continue"] is False

    def test_verify_gate_fallback_allows_verified(self, tmp_project):
        """Tracked files with verify-done → continue=true under sed fallback."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/module/top.sv\n")
        (state_dir / "rtl-verify-done").touch()
        result = run_hook(
            self.HOOKS["verify-stop-gate"],
            {"cwd": str(tmp_project)},
            env=self.FALLBACK_ENV,
        )
        assert result["continue"] is True

    # ── p6-cascade-gate ──────────────────────────────────────────────────────

    def test_p6_cascade_fallback_blocks_stale(self, tmp_project):
        """phase6-stale marker → continue=false under sed fallback."""
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(
            self.HOOKS["p6-cascade-gate"],
            {"cwd": str(tmp_project)},
            env=self.FALLBACK_ENV,
        )
        assert result["continue"] is False

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
        """Active skill state → continue=false under sed fallback."""

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
        assert result["continue"] is False

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
            {"skill": f"rtl-agent-team:{skill_name}", "cwd": str(tmp_project)},
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
            "schema_version", "generated_at", "generated_by",
            "setup", "pipeline", "upstream_artifacts",
            "staleness", "team", "quality_gates",
        }
        assert required_keys.issubset(set(m.keys()))
        assert "required" in m["upstream_artifacts"]
        assert "optional" in m["upstream_artifacts"]
        assert "all_required_present" in m["upstream_artifacts"]

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
        (state_dir / "rtl-modified-files.txt").write_text("rtl/a.sv\nrtl/b.sv\n")

        self._invoke(tmp_project, "rtl-p4-implement")

        m = self._read_manifest(tmp_project)
        assert m["staleness"]["rtl_modified_count"] == 2
        assert m["staleness"]["rtl_verify_done"] is False

    def test_manifest_staleness_verify_done(self, tmp_project):
        """rtl-verify-done marker → staleness.rtl_verify_done=true."""
        self._setup_project(tmp_project)
        state_dir = tmp_project / ".rat" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/a.sv\n")
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
            {"skill": "other-plugin:some-skill", "cwd": str(tmp_project)},
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


class TestSpawnContextTaskCreate:
    """Tests for rtl-spawn-context.sh (PreToolUse:TaskCreate hook)."""

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

    def test_taskcreate_overwrites_stale_manifest(self, tmp_project):
        """TaskCreate for different agent overwrites existing manifest phase."""
        (tmp_project / ".claude" / "rules").mkdir(parents=True, exist_ok=True)
        (tmp_project / ".claude" / "rules" / "rtl-coding-conventions.md").touch()

        # Write P1 manifest via Skill hook
        run_hook(
            HOOKS_DIR / "rtl-phase-state-bootstrap.sh",
            {"skill": "rtl-agent-team:p1-spec-research", "cwd": str(tmp_project)},
        )
        m1 = self._read_manifest(tmp_project)
        assert m1["pipeline"]["current_phase"] == 1

        # TaskCreate for P6 agent → must overwrite
        self._invoke(tmp_project, "p6-review-orchestrator")
        m2 = self._read_manifest(tmp_project)
        assert m2["pipeline"]["current_phase"] == 6

    def test_taskcreate_non_orchestrator_ignored(self, tmp_project):
        """Non-orchestrator agent type → no manifest written."""
        result = run_hook(
            self.HOOK,
            {"subagent_type": "rtl-agent-team:rtl-coder", "cwd": str(tmp_project)},
        )
        assert result["continue"] is True
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        assert not mpath.exists()

    # ── Robustness: malformed / unexpected input payloads ────────────

    def test_taskcreate_missing_subagent_type(self, tmp_project):
        """No subagent_type field → continue=true, no crash."""
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_taskcreate_empty_input(self, tmp_project):
        """Empty JSON → continue=true, no crash."""
        result = run_hook(self.HOOK, {})
        assert result["continue"] is True

    def test_taskcreate_non_rtl_agent(self, tmp_project):
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
        result = run_hook(self.BOOTSTRAP_HOOK, {})
        assert result["continue"] is True

    def test_bootstrap_missing_skill_field(self, tmp_project):
        """No skill field → continue=true, no crash."""
        result = run_hook(self.BOOTSTRAP_HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_bootstrap_garbage_skill_name(self, tmp_project):
        """Unrecognized skill prefix → continue=true, no manifest."""
        result = run_hook(
            self.BOOTSTRAP_HOOK,
            {"skill": "garbage:not-a-skill", "cwd": str(tmp_project)},
        )
        assert result["continue"] is True
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        assert not mpath.exists()

    def test_bootstrap_rtl_skill_unknown_name(self, tmp_project):
        """rtl-agent-team prefix but unknown skill → continue=true, no manifest."""
        result = run_hook(
            self.BOOTSTRAP_HOOK,
            {"skill": "rtl-agent-team:nonexistent-skill", "cwd": str(tmp_project)},
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
            {"skill": f"rtl-agent-team:{skill}", "cwd": str(tmp_project)},
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

    # ── Orchestrator Step 0 consistency ──────────────────────────────

    # Orchestrators that MUST have manifest-aware Step 0
    MANIFEST_AWARE_ORCHESTRATORS = {
        "autopilot-orchestrator.md",
        "dse-orchestrator.md",
        "p1-research-orchestrator.md",
        "p1-research-team-orchestrator.md",
        "p2-arch-orchestrator.md",
        "p2-arch-team-orchestrator.md",
        "p3-uarch-orchestrator.md",
        "p3-uarch-team-orchestrator.md",
        "p4-implement-orchestrator.md",
        "p4-implement-team-orchestrator.md",
        "p4s-bugfix-orchestrator.md",
        "p4s-unit-test-orchestrator.md",
        "p5-verify-orchestrator.md",
        "p5-verify-team-orchestrator.md",
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
        "spec-to-uarch-team-orchestrator.md",
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
        """Every manifest-aware orchestrator has Glob fallback for backward compat."""
        for fname in self.MANIFEST_AWARE_ORCHESTRATORS:
            content = (self.AGENTS_DIR / fname).read_text()
            assert "rtl-coding-conventions.md" in content, (
                f"{fname} missing Glob fallback"
            )

    # ── Skill-to-phase mapping coverage ──────────────────────────────

    EXPECTED_SKILL_PHASES = {
        "p1-spec-research": 1,
        "rtl-p1-research-team": 1,
        "p2-arch-design": 2,
        "rtl-p2-arch-team": 2,
        "rtl-p3-uarch-design": 3,
        "rtl-p3-uarch-team": 3,
        "rtl-p4-implement": 4,
        "rtl-p4-implement-team": 4,
        "rtl-p4-block-parallel": 4,
        "rtl-p4-rapid-impl": 4,
        "rtl-p4s-bugfix": 4,
        "rtl-p4s-unit-test": 4,
        "rtl-p4s-refactor": 4,
        "rtl-review-refactor": 4,
        "rtl-p5-verify": 5,
        "rtl-p5-verify-team": 5,
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
        "rat-p1p3-spec-uarch": 1,
        "rat-p1p3-spec-uarch-team": 1,
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

    # ── Agent-to-skill mapping in TaskCreate hook ────────────────────

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
        # Team orchestrators → team skills (1:1)
        "p1-research-team-orchestrator": "rtl-p1-research-team",
        "p2-arch-team-orchestrator": "rtl-p2-arch-team",
        "p3-uarch-team-orchestrator": "rtl-p3-uarch-team",
        "p4-implement-team-orchestrator": "rtl-p4-implement-team",
        "p5-verify-team-orchestrator": "rtl-p5-verify-team",
        "spec-to-uarch-team-orchestrator": "rat-p1p3-spec-uarch-team",
        # PPA optimization (post-verify)
        "ppa-optimizer-dc-orchestrator": "rtl-ppa-optimize-dc",
        "ppa-optimizer-dc": "rtl-ppa-optimize-dc",
        "dc-report-parser": "rtl-ppa-optimize-dc",
    }

    def test_taskcreate_agent_mapping_complete(self, tmp_project):
        """All expected orchestrator agents produce correct phase via TaskCreate hook."""
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
            {"skill": "rtl-agent-team:rtl-p4-implement", "cwd": str(tmp_project)},
        )
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        m1 = json.loads(mpath.read_text())

        run_hook(
            self.BOOTSTRAP_HOOK,
            {"skill": "rtl-agent-team:rtl-p4-implement", "cwd": str(tmp_project)},
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
            {"skill": f"rtl-agent-team:{skill}", "cwd": str(tmp_project)},
        )
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        manifest = json.loads(mpath.read_text())
        iron = manifest["upstream_iron"]
        assert isinstance(iron, list), f"upstream_iron must be list, got {type(iron)}"
        assert len(iron) == expected_count, f"{skill} should have {expected_count} upstream iron paths, got {len(iron)}"
        for path in iron:
            assert path.endswith("iron-requirements.json"), f"unexpected path: {path}"

    # ── Full event chain simulation ──────────────────────────────────

    def test_skill_then_taskcreate_chain(self, tmp_project):
        """Skill invoke → manifest → TaskCreate different agent → manifest updated."""
        rules = tmp_project / ".claude" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "rtl-coding-conventions.md").touch()

        # Step 1: Skill invocation writes P1 manifest
        run_hook(
            self.BOOTSTRAP_HOOK,
            {"skill": "rtl-agent-team:p1-spec-research", "cwd": str(tmp_project)},
        )
        mpath = tmp_project / ".rat" / "state" / "spawn-context.json"
        m1 = json.loads(mpath.read_text())
        assert m1["pipeline"]["current_phase"] == 1

        # Step 2: TaskCreate for P4 orchestrator overwrites
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
            {"skill": "rtl-agent-team:rat-init-project", "cwd": str(tmp_project)},
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
        # Find the case "$SHORT_NAME" block inside the compliance bootstrap section
        m = re.search(
            r'case\s+"\$SHORT_NAME"\s+in\s*\n(.*?)esac',
            content, re.DOTALL,
        )
        assert m, "Could not find compliance bootstrap case block"
        block = m.group(1)
        skills = set()
        for line in block.splitlines():
            line = line.strip()
            # Match branch heads like: p2-arch-design|rtl-p2-arch-team)
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
            {"skill": "rtl-agent-team:rtl-p4-implement", "cwd": str(tmp_project)},
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
        track.write_text("rtl/mod.sv\n")
        result = run_hook(
            self.VERIFY_HOOK,
            {"cwd": str(tmp_legacy_project)},
        )
        assert result["continue"] is False

    def test_orchestrator_inject_fires_with_legacy_dir(self, tmp_legacy_project):
        result = run_hook(self.INJECT_HOOK, {"cwd": str(tmp_legacy_project)})
        raw = result.get("raw_stdout", "")
        assert "Routing" in raw or "Pipeline Rules" in raw

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
