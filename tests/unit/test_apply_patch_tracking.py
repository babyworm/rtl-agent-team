"""Codex patch events go through the same RTL verification gate as Claude edits."""

from tests.conftest import HOOKS_DIR, run_hook


def patch_event(project, event, patch):
    return run_hook(HOOKS_DIR / "rtl-edit-tracker.sh", {
        "cwd": str(project), "session_id": "codex", "tool_use_id": "patch-1",
        "hook_event_name": event, "tool_name": "apply_patch", "tool_input": {"command": patch},
    })


def test_multifile_patch_tracks_changes_and_blocks_stop(tmp_project):
    rtl = tmp_project / "rtl"
    rtl.mkdir()
    for name in ("dut.sv", "old name.sv", "removed.v", "comment.svh"):
        (rtl / name).write_text("wire a;\n")
    patch = """*** Begin Patch
*** Update File: rtl/dut.sv
@@
-wire a;
+wire b;
*** Add File: rtl/helper.v
+wire b;
*** Update File: rtl/old name.sv
*** Move to: rtl/new name.sv
@@
-wire a;
+wire b;
*** Delete File: rtl/removed.v
*** Update File: rtl/comment.svh
@@
-wire a;
+wire a; // unchanged
*** Add File: syn/generated.v
+wire b;
*** End Patch"""
    state = tmp_project / ".rat/state"
    (state / "rtl-verify-waiver").touch()
    patch_event(tmp_project, "PreToolUse", patch)
    for name in ("dut.sv", "helper.v"):
        (rtl / name).write_text("wire b;\n")
    (rtl / "old name.sv").rename(rtl / "new name.sv")
    (rtl / "new name.sv").write_text("wire b;\n")
    (rtl / "removed.v").unlink()
    (rtl / "comment.svh").write_text("wire a; // unchanged\n")
    (tmp_project / "syn").mkdir()
    (tmp_project / "syn/generated.v").write_text("wire b;\n")
    patch_event(tmp_project, "PostToolUse", patch)

    tracked = (state / "rtl-modified-files.txt").read_text().splitlines()
    assert set(tracked) == {"rtl/dut.sv", "rtl/helper.v", "rtl/old name.sv", "rtl/new name.sv", "rtl/removed.v"}
    assert not (state / "rtl-verify-waiver").exists()
    stop = run_hook(HOOKS_DIR / "rtl-verify-stop-gate.sh", {"cwd": str(tmp_project)})
    assert stop["decision"] == "block"
    for name in ("rtl/dut.sv", "rtl/helper.v", "rtl/new name.sv"):
        assert name in stop["reason"]
    for name in ("rtl/removed.v", "rtl/old name.sv"):
        assert name not in stop["reason"]
