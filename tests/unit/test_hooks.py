"""Tests for hook scripts — routing inject, edit tracker, and stop gates."""

import json
import os
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
        result = run_hook(self.HOOK, stdin)
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
        result = run_hook(self.HOOK, stdin)
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "rtl-p4s-bugfix" in ctx
