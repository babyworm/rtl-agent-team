#!/usr/bin/env python3
"""Replay supported editor events through the installed runner and verification hooks."""

import json
import os
from pathlib import Path
import subprocess
import tempfile

PLUGIN = Path(__file__).resolve().parents[2]
SCAFFOLD = PLUGIN / "evals/unit-mismatch/scaffold.sh"
SOURCE = Path("rtl/incrementer.sv")


def hook(project, env, script, event, **fields):
    payload = dict(cwd=str(project), session_id="eval", hook_event_name=event, **fields)
    result = subprocess.run(
        ["sh", str(PLUGIN / "hooks" / script)], cwd=project, env=env, timeout=30,
        input=json.dumps(payload), text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout)


def check(host, project):
    # Use only the synthetic project and the locally installed simulators.
    env = {
        "PATH": os.environ["PATH"],
        "HOME": str(project),
        "RAT_DATA_DIR": str(project / "plugin-data"),
        "CLAUDE_PLUGIN_ROOT": str(PLUGIN),
    }
    subprocess.run(["bash", str(SCAFFOLD)], cwd=project, env=env, check=True, timeout=60)
    source = project / SOURCE
    before = source.read_text()
    after = before.replace("4'd1", "4'd2")
    if before == after:
        raise ValueError("Fixture does not contain the expected increment.")
    if host == "Claude":
        tool = "Edit"
        tool_input = {"file_path": str(source), "old_string": "4'd1", "new_string": "4'd2"}
    else:
        tool = "apply_patch"
        patch = ("*** Begin Patch\n*** Update File: rtl/incrementer.sv\n@@\n"
                 "-  assign o_value = i_value + 4'd1;\n+  assign o_value = i_value + 4'd2;\n"
                 "*** End Patch")
        tool_input = {"command": patch}
    fields = dict(tool_use_id="edit-1", tool_name=tool, tool_input=tool_input)
    hook(project, env, "rtl-edit-tracker.sh", "PreToolUse", **fields)
    source.write_text(after)
    hook(project, env, "rtl-edit-tracker.sh", "PostToolUse", **fields)

    run = subprocess.run(
        ["bash", "scripts/run_sim.sh", "--sim", "iverilog", "--top", "tb_incrementer",
         "--filelist", "sources.f"], cwd=project, env=env, capture_output=True,
        text=True, timeout=90,
    )
    state = project / ".rat/state"
    evidence = state / "verify-evidence.json"
    if not evidence.exists():
        raise RuntimeError(f"{host}: runner produced no evidence\n{run.stdout}\n{run.stderr}")
    record, = json.loads(evidence.read_text())["runs"]
    runtime_log = Path(record["runtime_log"]["path"]).read_text()
    if (run.returncode == 0 or record["top"] != "tb_incrementer" or record["verdict"] != "FAIL"
            or "REQ-U-001 expected=5 actual=6" not in runtime_log or "unrelated smoke" in runtime_log):
        raise RuntimeError(f"{host}: incorrect simulation evidence\n{run.stdout}\n{run.stderr}")
    stop = hook(project, env, "rtl-verify-stop-gate.sh", "Stop")
    if stop.get("decision") != "block":
        raise RuntimeError(f"{host}: Stop did not block: {stop}")
    pending = (state / "rtl-modified-files.txt").read_text().splitlines()
    if str(SOURCE) not in pending:
        raise RuntimeError(f"{host}: {SOURCE} is missing from the pending RTL list")
    print(f"{host} {tool}: tb_incrementer measured 6, expected 5; FAIL, Stop blocked")


if __name__ == "__main__":
    for host_name in ("Claude", "Codex"):
        with tempfile.TemporaryDirectory(prefix="rat-host-eval-") as directory:
            check(host_name, Path(directory).resolve())
