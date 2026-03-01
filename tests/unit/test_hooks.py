"""Tests for hook scripts — edit tracker, verify stop gate, autopilot stop gate."""

import json
import os
from pathlib import Path

import pytest

from tests.conftest import HOOKS_DIR, run_hook


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

    def test_no_state_file_allows_exit(self, tmp_project):
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_state_file_exists_blocks_exit(self, tmp_project):
        state_file = tmp_project / ".rtl-agent-team" / "state" / "rtl-autopilot-state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text('{"phase": 3}')
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
        assert "Autopilot" in result.get("hookSpecificOutput", {}).get("additionalContext", "")
