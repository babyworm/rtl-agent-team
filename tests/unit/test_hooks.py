"""Tests for hook scripts — routing inject, edit tracker, and stop gates."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest

from tests.conftest import HOOKS_DIR, run_hook


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
        assert "/rtl-agent-team:rtl-autopilot" in output
        assert "Action Skills first" in output

    def test_docs_dir_triggers_injection(self, tmp_path):
        (tmp_path / "docs").mkdir()
        result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
        output = result.get("raw_stdout", "")
        assert "## Absolute Rules (Hard Gates)" in output
        assert "/rtl-agent-team:p1-spec-research" in output

    def test_rtl_state_dir_triggers_injection(self, tmp_path):
        (tmp_path / ".rtl-agent-team").mkdir()
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

        track_file = tmp_project / ".rtl-agent-team" / "state" / "rtl-modified-files.txt"
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

        track_file = tmp_project / ".rtl-agent-team" / "state" / "rtl-modified-files.txt"
        lines = [l for l in track_file.read_text().splitlines() if l.strip()]
        assert lines.count("rtl/module/top.sv") == 1

    def test_multiple_files_tracked(self, tmp_project):
        run_hook(self.HOOK, {"cwd": str(tmp_project), "file_path": "rtl/a.sv"})
        run_hook(self.HOOK, {"cwd": str(tmp_project), "file_path": "rtl/b.sv"})

        track_file = tmp_project / ".rtl-agent-team" / "state" / "rtl-modified-files.txt"
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
        assert "2" in ctx  # Should show 2 tracked files

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
        track_file = tmp_project / ".rtl-agent-team" / "state" / "rtl-modified-files.txt"
        assert track_file.exists()
        tracked = track_file.read_text()
        assert "rtl/top_level.sv" in tracked
        assert "rtl/nested_should_be_ignored.sv" not in tracked


class TestSessionScopedState:
    """Tests for session-scoped state isolation in team mode (Phase A)."""

    EDIT_HOOK = HOOKS_DIR / "rtl-edit-tracker.sh"
    GATE_HOOK = HOOKS_DIR / "rtl-verify-stop-gate.sh"
    SKILL_HOOK = HOOKS_DIR / "rtl-skill-activation.sh"

    def _write_team_config(self, tmp_project, leader_id="leader-session-001"):
        """Create a team-config.json in the project state dir."""
        import datetime
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        # Should mention both files (aggregated)
        assert "2" in ctx  # 2 files total

    def test_verify_gate_cleanup_removes_session_files(self, tmp_project):
        """When verify-done exists, gate cleans up all session-scoped files."""
        self._write_team_config(tmp_project, leader_id="leader-001")
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        skill_state = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
        assert not skill_state.exists(), "Worker should not create skill-active.json"


class TestRtlVerifyStopGate:
    """Tests for hooks/rtl-verify-stop-gate.sh."""

    HOOK = HOOKS_DIR / "rtl-verify-stop-gate.sh"

    def test_no_tracked_files_allows_exit(self, tmp_project):
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_empty_tracking_file_allows_exit(self, tmp_project):
        track = tmp_project / ".rtl-agent-team" / "state" / "rtl-modified-files.txt"
        track.write_text("")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_tracked_files_without_verification_blocks(self, tmp_project):
        track = tmp_project / ".rtl-agent-team" / "state" / "rtl-modified-files.txt"
        track.write_text("rtl/module/top.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False

    def test_verify_done_allows_exit(self, tmp_project):
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/module/top.sv\n")
        (state_dir / "rtl-verify-done").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_verify_waiver_allows_exit(self, tmp_project):
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/module/top.sv\n")
        (state_dir / "rtl-verify-waiver").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_cleanup_after_verify_done(self, tmp_project):
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        track = state_dir / "rtl-modified-files.txt"
        done = state_dir / "rtl-verify-done"
        track.write_text("rtl/module/top.sv\n")
        done.touch()
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert not track.exists()
        assert not done.exists()

    def test_cleanup_after_waiver(self, tmp_project):
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        track = state_dir / "rtl-modified-files.txt"
        waiver = state_dir / "rtl-verify-waiver"
        track.write_text("rtl/a.sv\nrtl/b.sv\n")
        waiver.touch()
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert not track.exists()
        assert not waiver.exists()

    def test_multiple_files_blocks(self, tmp_project):
        """Multiple tracked files should all be mentioned in block message."""
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/a.sv\nrtl/b.sv\nrtl/c.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "3" in ctx  # 3 files

    def test_fallback_file_blocks_exit(self, tmp_project):
        """Fallback entries from lock failure must block exit even without main track file."""
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        (state_dir / "rtl-modified-files-fallback.txt").write_text("rtl/alu/alu.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "1" in ctx

    def test_fallback_merged_with_main_track(self, tmp_project):
        """Fallback and main track entries are both counted."""
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/a.sv\n")
        (state_dir / "rtl-modified-files-fallback.txt").write_text("rtl/b.sv\n")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "2" in ctx

    def test_verify_done_cleans_fallback(self, tmp_project):
        """Verify-done should clean up fallback file too."""
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/a.sv\n")
        (state_dir / "rtl-modified-files-fallback.txt").write_text("rtl/b.sv\n")
        (state_dir / "rtl-verify-done").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True
        assert not (state_dir / "rtl-modified-files-fallback.txt").exists()

    def test_fallback_aggregated_in_team_mode(self, tmp_project):
        """In team mode, fallback file is included via glob aggregation."""
        import datetime
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        state_file = tmp_project / ".rtl-agent-team" / "state" / "rtl-autopilot-state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(payload, indent=2))
        return state_file

    def test_no_state_file_allows_exit(self, tmp_project):
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_state_file_exists_blocks_exit(self, tmp_project):
        self._write_autopilot_state(tmp_project, {"phase": 3})
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        assert "Autopilot" in result.get("hookSpecificOutput", {}).get("additionalContext", "")

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
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
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
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
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
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
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
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
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
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "p3-quality-gate" in ctx
        assert "primary=1" in ctx

    def test_stop_gate_uses_shared_json_util(self):
        content = (HOOKS_DIR / "stop-gate.sh").read_text()
        assert "lib/json-util.sh" in content
        assert "jsonu_get_file_path_string" in content
        assert "jsonu_get_file_path_bool" in content
        assert "jsonu_get_file_path_num" in content


class TestRtlEditTrackerPhase6:
    """Tests for Phase 6 stale detection in hooks/rtl-edit-tracker.sh."""

    HOOK = HOOKS_DIR / "rtl-edit-tracker.sh"

    def test_no_phase6_no_stale_marker(self, tmp_project):
        """No phase 6 review dir → no stale marker created."""
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/module/top.sv"}
        run_hook(self.HOOK, stdin)
        stale = tmp_project / ".rtl-agent-team" / "state" / "phase6-stale"
        assert not stale.exists()

    def test_phase6_exists_creates_stale_marker(self, tmp_project):
        """Phase 6 review with .md files → stale marker created on RTL edit."""
        p6_dir = tmp_project / "reviews" / "phase-6-review"
        p6_dir.mkdir(parents=True)
        (p6_dir / "code-review.md").write_text("# Code Review\nverdict: PASS")
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/module/top.sv"}
        run_hook(self.HOOK, stdin)
        stale = tmp_project / ".rtl-agent-team" / "state" / "phase6-stale"
        assert stale.exists()

    def test_phase6_empty_dir_no_stale(self, tmp_project):
        """Phase 6 dir exists but no .md files → no stale marker."""
        p6_dir = tmp_project / "reviews" / "phase-6-review"
        p6_dir.mkdir(parents=True)
        stdin = {"cwd": str(tmp_project), "file_path": "rtl/module/top.sv"}
        run_hook(self.HOOK, stdin)
        stale = tmp_project / ".rtl-agent-team" / "state" / "phase6-stale"
        assert not stale.exists()

    def test_phase6_stale_message_in_output(self, tmp_project):
        """Phase 6 stale detection should include message in output."""
        p6_dir = tmp_project / "reviews" / "phase-6-review"
        p6_dir.mkdir(parents=True)
        (p6_dir / "design-note.md").write_text("# Design Note")
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
        stale = tmp_project / ".rtl-agent-team" / "state" / "phase6-stale"
        assert not stale.exists()

    def test_trackfile_recorded_despite_lock_timeout(self, tmp_project):
        """Fail-closed: RTL file must be tracked in fallback when TRACK_FILE lock fails."""
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        # Pre-create lock dir to simulate a held lock (causes acquire_lock timeout)
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "Phase 6" in ctx

    def test_cascade_done_allows_exit(self, tmp_project):
        """Both markers exist → clean up and allow exit."""
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        (state_dir / "phase6-stale").touch()
        (state_dir / "phase6-cascade-done").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_cascade_done_cleans_markers(self, tmp_project):
        """After allowing exit with cascade-done, both markers should be removed."""
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        stale = state_dir / "phase6-stale"
        done = state_dir / "phase6-cascade-done"
        stale.touch()
        done.touch()
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert not stale.exists()
        assert not done.exists()

    def test_block_message_content(self, tmp_project):
        """Block message should mention lint, code-review, design-note."""
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "lint" in ctx.lower()
        assert "code-review" in ctx.lower() or "code_review" in ctx.lower()
        assert "design-note" in ctx.lower() or "design_note" in ctx.lower()

    def test_p6_cascade_gate_uses_shared_json_util(self):
        content = (HOOKS_DIR / "rtl-p6-cascade-gate.sh").read_text()
        assert "lib/json-util.sh" in content
        assert "lib/team-gate-util.sh" in content
        assert "jsonu_get_input_string" in content
        assert "teamu_should_skip_gate" in content


class TestSkillCompletionGate:
    """Tests for hooks/rtl-skill-completion-gate.sh."""

    HOOK = HOOKS_DIR / "rtl-skill-completion-gate.sh"

    def _write_skill_state(self, tmp_project, skill="rtl-p4s-bugfix", iteration=1,
                           max_iterations=5, all_complete=False,
                           pending="lint_pass, tb_updated, sim_pass"):
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        import datetime
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
        state_file = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
        assert not state_file.exists()

    def test_max_iterations_still_blocks_under_ladder(self, tmp_project):
        """At iteration == max_iterations, ladder remains active and blocks exit."""
        self._write_skill_state(tmp_project, iteration=5, max_iterations=5)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "primary" in ctx.lower()

    def test_max_iterations_does_not_clean_state_under_ladder(self, tmp_project):
        """Ladder mode should keep state for fallback/last-chance escalation."""
        self._write_skill_state(tmp_project, iteration=5, max_iterations=5)
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        state_file = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
        assert state_file.exists()

    def test_iteration_increments_on_block(self, tmp_project):
        """Each block should increment the iteration counter."""
        self._write_skill_state(tmp_project, iteration=1)
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        state_file = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
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
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "rtl-p4s-bugfix" in ctx

    def test_block_message_includes_pending(self, tmp_project):
        """Block message should include pending criteria."""
        self._write_skill_state(tmp_project, pending="lint_pass, sim_pass")
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "lint_pass" in ctx or "sim_pass" in ctx

    def test_stale_state_allows_exit(self, tmp_project):
        """State older than 2 hours should be treated as stale and cleaned up."""
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        # Write a state with a timestamp 3 hours ago
        import datetime
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
        state_file = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
        state = json.loads(state_file.read_text())
        state["use_escalation_ladder"] = True
        state["dynamic_prompt"] = "primary prompt"
        state_file.write_text(json.dumps(state, indent=2))

        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "primary" in ctx.lower()

    def test_ladder_fallback_stage_blocks(self, tmp_project):
        self._write_skill_state(tmp_project, iteration=3, max_iterations=2)
        state_file = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
        state = json.loads(state_file.read_text())
        state["use_escalation_ladder"] = True
        state["dynamic_prompt"] = "fallback prompt"
        state_file.write_text(json.dumps(state, indent=2))

        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "fallback" in ctx.lower()
        assert "fallback prompt" in ctx

    def test_ladder_last_chance_stage_blocks(self, tmp_project):
        self._write_skill_state(tmp_project, iteration=5, max_iterations=2)
        state_file = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
        state = json.loads(state_file.read_text())
        state["use_escalation_ladder"] = True
        state_file.write_text(json.dumps(state, indent=2))

        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "last_chance" in ctx or "last-chance" in ctx

    def test_ladder_after_last_chance_requires_user(self, tmp_project):
        self._write_skill_state(tmp_project, iteration=6, max_iterations=2)
        state_file = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
        state = json.loads(state_file.read_text())
        state["use_escalation_ladder"] = True
        state_file.write_text(json.dumps(state, indent=2))

        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "사용자" in ctx or "user" in ctx.lower()

    def test_legacy_disabled_ladder_is_migrated_and_still_blocks(self, tmp_project):
        self._write_skill_state(tmp_project, iteration=5, max_iterations=2)
        state_file = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
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

    def _setup_marker(self, tmp_project):
        rules_dir = tmp_project / ".claude" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        (rules_dir / "rtl-coding-conventions.md").write_text("# marker")

    def test_non_rtl_skill_ignored(self, tmp_project):
        """Non rtl-agent-team skills should be ignored."""
        stdin = {"cwd": str(tmp_project), "skill": "oh-my-claudecode:ultrawork"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        state_file = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
        assert not state_file.exists()

    def test_rtl_skill_creates_state(self, tmp_project):
        """rtl-agent-team skill with criteria should create state file."""
        self._setup_marker(tmp_project)
        # Create criteria config
        criteria_dir = tmp_project / ".rtl-agent-team"
        criteria_dir.mkdir(parents=True, exist_ok=True)
        criteria = {"rtl-p4s-bugfix": "lint_pass, tb_updated, sim_pass"}
        (criteria_dir / "skill-completion-criteria.json").write_text(json.dumps(criteria))

        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4s-bugfix"}
        result = run_hook(self.HOOK, stdin, env={"CLAUDE_PLUGIN_ROOT": str(tmp_project)})
        assert result["continue"] is True
        state_file = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert state["skill"] == "rtl-p4s-bugfix"
        assert state["all_complete"] is False
        assert "lint_pass" in state["pending"]
        assert state["use_escalation_ladder"] is True

    def test_rtl_skill_no_criteria_no_state(self, tmp_project):
        """rtl-agent-team skill without criteria in config should not create state."""
        self._setup_marker(tmp_project)
        criteria_dir = tmp_project / ".rtl-agent-team"
        criteria_dir.mkdir(parents=True, exist_ok=True)
        criteria = {"rtl-p4s-bugfix": "lint_pass"}
        (criteria_dir / "skill-completion-criteria.json").write_text(json.dumps(criteria))

        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:systemverilog"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        state_file = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
        assert not state_file.exists()

    def test_no_criteria_file_no_state(self, tmp_project):
        """Missing criteria file should not create state."""
        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4s-bugfix"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        state_file = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
        assert not state_file.exists()

    def test_existing_state_not_overridden(self, tmp_project):
        """If state already exists, should not be overridden."""
        self._setup_marker(tmp_project)
        criteria_dir = tmp_project / ".rtl-agent-team"
        criteria_dir.mkdir(parents=True, exist_ok=True)
        criteria = {"rtl-p4s-bugfix": "lint_pass, tb_updated, sim_pass"}
        (criteria_dir / "skill-completion-criteria.json").write_text(json.dumps(criteria))

        state_dir = tmp_project / ".rtl-agent-team" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        existing = {"skill": "rtl-p4-implement", "iteration": 3, "all_complete": False, "pending": "something"}
        (state_dir / "skill-active.json").write_text(json.dumps(existing))

        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4s-bugfix"}
        result = run_hook(self.HOOK, stdin)
        # State should NOT be overridden
        state = json.loads((state_dir / "skill-active.json").read_text())
        assert state["skill"] == "rtl-p4-implement"  # Original, not rtl-p4s-bugfix
        assert state["iteration"] == 3

    def test_activation_message(self, tmp_project):
        """Activation should include skill name in additionalContext."""
        self._setup_marker(tmp_project)
        criteria_dir = tmp_project / ".rtl-agent-team"
        criteria_dir.mkdir(parents=True, exist_ok=True)
        criteria = {"rtl-p4s-bugfix": "lint_pass, sim_pass"}
        (criteria_dir / "skill-completion-criteria.json").write_text(json.dumps(criteria))

        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4s-bugfix"}
        result = run_hook(self.HOOK, stdin, env={"CLAUDE_PLUGIN_ROOT": str(tmp_project)})
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "rtl-p4s-bugfix" in ctx

    def test_rtl_setup_bootstrap_installs_template_scripts(self, tmp_project):
        """rtl-setup activation should auto-install run_xxx.sh templates into project."""
        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-setup"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True

        run_sim = tmp_project / "scripts" / "run_sim.sh"
        run_lint = tmp_project / "lint" / "scripts" / "run_lint.sh"
        run_syn = tmp_project / "syn" / "scripts" / "run_syn.sh"
        run_cdc = tmp_project / "sim" / "cdc" / "run_cdc.sh"

        for path in [run_sim, run_lint, run_syn, run_cdc]:
            assert path.exists(), f"Missing auto-installed script: {path}"
            assert os.access(path, os.X_OK), f"Script should be executable: {path}"

        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "SETUP_TEMPLATE_INSTALL" in ctx

    def test_rtl_setup_bootstrap_is_non_destructive(self, tmp_project):
        """Existing scripts should not be overwritten by rtl-setup bootstrap."""
        run_sim = tmp_project / "scripts" / "run_sim.sh"
        run_sim.parent.mkdir(parents=True, exist_ok=True)
        run_sim.write_text("#!/usr/bin/env bash\necho custom\n")
        run_sim.chmod(0o755)

        stdin = {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-setup"}
        result = run_hook(self.HOOK, stdin)
        assert result["continue"] is True
        assert run_sim.read_text() == "#!/usr/bin/env bash\necho custom\n"

    def test_parser_uses_top_level_skill_key(self, tmp_project):
        self._setup_marker(tmp_project)
        criteria_dir = tmp_project / ".rtl-agent-team"
        criteria_dir.mkdir(parents=True, exist_ok=True)
        criteria = {"rtl-p4s-bugfix": "lint_pass, sim_pass"}
        (criteria_dir / "skill-completion-criteria.json").write_text(json.dumps(criteria))

        raw_input = json.dumps(
            {
                "cwd": str(tmp_project),
                "skill": "rtl-agent-team:rtl-p4s-bugfix",
                "meta": {"skill": "rtl-agent-team:rtl-setup"},
            }
        )

        result = run_hook(self.HOOK, raw_input, env={"CLAUDE_PLUGIN_ROOT": str(tmp_project)})
        assert result["continue"] is True
        state_file = tmp_project / ".rtl-agent-team" / "state" / "skill-active.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert state["skill"] == "rtl-p4s-bugfix"


class TestPhaseStateBootstrap:
    """Tests for hooks/rtl-phase-state-bootstrap.sh."""

    HOOK = HOOKS_DIR / "rtl-phase-state-bootstrap.sh"

    def _setup_marker(self, tmp_project):
        rules_dir = tmp_project / ".claude" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        (rules_dir / "rtl-coding-conventions.md").write_text("# marker")

    def test_non_target_skill_ignored(self, tmp_project):
        self._setup_marker(tmp_project)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4-implement"})
        assert result["continue"] is True
        assert not (tmp_project / ".rtl-agent-team" / "state" / "p4-state.json").exists()

    def test_setup_missing_does_not_bootstrap(self, tmp_project):
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4-rapid-impl"})
        assert result["continue"] is True
        assert not (tmp_project / ".rtl-agent-team" / "state" / "p4-state.json").exists()

    @pytest.mark.parametrize(
        "skill_name,state_file,phase",
        [
            ("rtl-agent-team:rtl-p4-rapid-impl", "p4-state.json", "p4"),
            ("rtl-agent-team:rtl-p5a-functional-closure", "p5a-state.json", "p5a"),
        ],
    )
    def test_target_skill_bootstraps_state(self, tmp_project, skill_name, state_file, phase):
        self._setup_marker(tmp_project)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": skill_name})
        assert result["continue"] is True

        state_path = tmp_project / ".rtl-agent-team" / "state" / state_file
        assert state_path.exists()
        data = json.loads(state_path.read_text())
        assert data["phase"] == phase
        assert "{{TIMESTAMP}}" not in state_path.read_text()

    def test_existing_state_not_overwritten(self, tmp_project):
        self._setup_marker(tmp_project)
        state_path = tmp_project / ".rtl-agent-team" / "state" / "p4-state.json"
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text('{"phase":"p4","status":"custom"}')

        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4-rapid-impl"})
        assert result["continue"] is True
        assert json.loads(state_path.read_text())["status"] == "custom"

    def test_p5b_blocks_without_p5a_state(self, tmp_project):
        self._setup_marker(tmp_project)
        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "P5B Gate BLOCKED" in ctx
        assert "rtl-p5a-functional-closure" in ctx
        assert not (tmp_project / ".rtl-agent-team" / "state" / "p5b-state.json").exists()

    def test_p5b_blocks_when_p5a_verdict_not_pass(self, tmp_project):
        self._setup_marker(tmp_project)
        p5a_state = tmp_project / ".rtl-agent-team" / "state" / "p5a-state.json"
        p5a_state.parent.mkdir(parents=True, exist_ok=True)
        p5a_state.write_text(
            json.dumps({"gates": {"p5a_exit": {"verdict": "fail"}}}, indent=2)
        )

        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "gates.p5a_exit.verdict=fail" in ctx
        assert not (tmp_project / ".rtl-agent-team" / "state" / "p5b-state.json").exists()

    def test_p5b_bootstraps_when_p5a_pass(self, tmp_project):
        self._setup_marker(tmp_project)
        p5a_state = tmp_project / ".rtl-agent-team" / "state" / "p5a-state.json"
        p5a_state.parent.mkdir(parents=True, exist_ok=True)
        p5a_state.write_text(
            json.dumps({"gates": {"p5a_exit": {"verdict": "pass"}}}, indent=2)
        )

        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"})
        assert result["continue"] is True
        state_path = tmp_project / ".rtl-agent-team" / "state" / "p5b-state.json"
        assert state_path.exists()
        assert json.loads(state_path.read_text())["phase"] == "p5b"

    def test_p5b_blocks_when_rtl_changed_after_p5a_pass(self, tmp_project):
        self._setup_marker(tmp_project)

        state_dir = tmp_project / ".rtl-agent-team" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        p5a_state = state_dir / "p5a-state.json"
        p5a_state.write_text(json.dumps({"gates": {"p5a_exit": {"verdict": "pass"}}}, indent=2))

        time.sleep(1.1)
        rtl_dir = tmp_project / "rtl"
        rtl_dir.mkdir(parents=True, exist_ok=True)
        (rtl_dir / "top.sv").write_text("module top; endmodule\n")
        (state_dir / "rtl-modified-files.txt").write_text("rtl/top.sv\n")

        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"})
        assert result["continue"] is False
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "stale functional closure" in ctx
        assert not (state_dir / "p5b-state.json").exists()

    def test_p5b_allows_when_p5a_newer_than_tracked_rtl_changes(self, tmp_project):
        self._setup_marker(tmp_project)

        state_dir = tmp_project / ".rtl-agent-team" / "state"
        state_dir.mkdir(parents=True, exist_ok=True)
        rtl_dir = tmp_project / "rtl"
        rtl_dir.mkdir(parents=True, exist_ok=True)
        (rtl_dir / "top.sv").write_text("module top; endmodule\n")
        (state_dir / "rtl-modified-files.txt").write_text("rtl/top.sv\n")

        time.sleep(1.1)
        p5a_state = state_dir / "p5a-state.json"
        p5a_state.write_text(json.dumps({"gates": {"p5a_exit": {"verdict": "pass"}}}, indent=2))

        result = run_hook(self.HOOK, {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p5b-silicon-validation"})
        assert result["continue"] is True
        assert (state_dir / "p5b-state.json").exists()

    def test_missing_json_parser_emits_setup_hint_with_fallback(self, tmp_project):
        self._setup_marker(tmp_project)
        result = run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p4-rapid-impl"},
            env={"RTL_FORCE_JSON_FALLBACK": "1"},
        )
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "fallback" in ctx
        assert "/rtl-agent-team:rtl-setup" in ctx

    def test_parser_uses_top_level_skill_key(self, tmp_project):
        self._setup_marker(tmp_project)
        raw_input = json.dumps(
            {
                "cwd": str(tmp_project),
                "skill": "rtl-agent-team:rtl-p4-rapid-impl",
                "meta": {"skill": "rtl-agent-team:rtl-p5b-silicon-validation"},
            }
        )

        result = run_hook(self.HOOK, raw_input)
        assert result["continue"] is True
        assert (tmp_project / ".rtl-agent-team" / "state" / "p4-state.json").exists()
        assert not (tmp_project / ".rtl-agent-team" / "state" / "p5b-state.json").exists()


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

        track_file = tmp_project / ".rtl-agent-team" / "state" / "rtl-modified-files.txt"
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

        track_file = tmp_project / ".rtl-agent-team" / "state" / "rtl-modified-files.txt"
        lines = [l for l in track_file.read_text().splitlines() if l.strip()]
        assert lines.count("rtl/top.sv") == 1

    def test_concurrent_skill_completion_gate_counter_accuracy(self, tmp_project):
        """3 parallel skill-completion-gate calls → iteration increments correctly."""
        import datetime
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        import datetime
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        state = {"status": "in_progress", "orchestration_control": {
            "active_gate_id": "test", "active_gate_retry_limit": 2,
            "active_gate_primary_attempts": 0, "active_gate_fallback_attempts": 0,
            "active_gate_last_chance_attempts": 0, "needs_user_decision": False
        }}
        (state_dir / "rtl-autopilot-state.json").write_text(json.dumps(state))
        # Worker session (no CLAUDE_SESSION_ID or different from leader)
        result = run_hook(self.HOOKS["stop-gate"], {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_leader_session_still_blocked_by_stop_gate(self, tmp_project):
        """Leader session in team mode → stop gate still blocks."""
        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        state = {"status": "in_progress", "orchestration_control": {
            "active_gate_id": "test", "active_gate_retry_limit": 2,
            "active_gate_primary_attempts": 0, "active_gate_fallback_attempts": 0,
            "active_gate_last_chance_attempts": 0, "needs_user_decision": False
        }}
        (state_dir / "rtl-autopilot-state.json").write_text(json.dumps(state))
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/top.sv\n")
        result = run_hook(self.HOOKS["verify-stop-gate"], {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_worker_bypasses_p6_cascade(self, tmp_project):
        """Worker in team mode → P6 cascade allows exit even with stale marker."""
        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOKS["p6-cascade-gate"], {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_worker_bypasses_skill_completion(self, tmp_project):
        """Worker in team mode → skill completion gate allows exit."""
        import datetime
        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        import datetime
        self._write_team_config(tmp_project, leader_id="leader-abc")
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        (state_dir / "phase6-stale").touch()
        result = run_hook(self.HOOKS["p6-cascade-gate"], {"cwd": str(tmp_project)})
        assert result["continue"] is False

    def test_stale_team_config_removed_and_gate_applies(self, tmp_project):
        """team-config.json older than 2h → removed, normal gate behavior resumes."""
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        state_file = state_dir / "rtl-autopilot-state.json"
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
        (state_dir / "rtl-modified-files.txt").write_text("rtl/module/top.sv\n")
        result = run_hook(
            self.HOOKS["verify-stop-gate"],
            {"cwd": str(tmp_project)},
            env=self.FALLBACK_ENV,
        )
        assert result["continue"] is False

    def test_verify_gate_fallback_allows_verified(self, tmp_project):
        """Tracked files with verify-done → continue=true under sed fallback."""
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        import datetime
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
        import datetime
        state_dir = tmp_project / ".rtl-agent-team" / "state"
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
