#!/usr/bin/env python3
"""Rule 5 decision inputs for hooks/rtl-verify-stop-gate.sh.

The launcher keeps the Stop budget (stop-budget-util.sh, shared by every Stop gate); this module
reads tracking, configuration and evidence and prints shell assignments the launcher evals:

  VG_ACTION  continue | clear | cleared | gate
  VG_NOTICE  notice for a cleared gate, or the gate's hand-over notice
  VG_MODE, VG_SIM_PRESENT, VG_MSG, VG_NOTIFY_NOTICE, VG_NOSIM_NOTICE, VG_PROGRESS  (gate only)

Every value is single-quoted for POSIX sh. Nothing is printed before the decision is complete,
so a crash leaves no partial assignments and the launcher falls back to blocking.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import rat_compat  # noqa: E402

rat_compat.require()
from eda_runner import backend, config_value, configuration  # noqa: E402
from verify_evidence import clearing, failed_case_labels, running_cover, tracked_paths  # noqa: E402

SIMULATORS = ("iverilog", "verilator", "vcs", "xrun", "vsim")
MODES = ("block", "notify", "off")


def shq(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def lines_of(path: Path) -> list[str]:
    try:
        return path.read_text(errors="replace").splitlines()
    except OSError:
        return []


def tracking(state: Path) -> list[str]:
    """Tracked lines from the solo file, worker session files and the lock-failure fallback."""
    solo = state / "rtl-modified-files.txt"
    fallback = state / "rtl-modified-files-fallback.txt"
    sessions = sorted(state.glob("rtl-modified-files-*.txt"))
    try:
        team = json.loads((state / "team-config.json").read_text()).get("team_mode") is True
    except (OSError, ValueError, AttributeError):
        team = False
    # Team skills delete team-config.json before the leader's first Stop, so leftover worker
    # files alone also mean aggregation; otherwise worker edits would escape the gate.
    if team or any(path != fallback for path in sessions):
        return lines_of(solo) + [line for path in sessions for line in lines_of(path)]
    lines = lines_of(solo)
    if fallback.is_file() and fallback.stat().st_size:
        # Atomically claim the fallback file before reading so concurrent appends
        # create a fresh fallback file instead of being lost at unlink().
        claimed = state / f"rtl-modified-files-fallback.{os.getpid()}.tmp"
        try:
            os.replace(fallback, claimed)
        except OSError:
            return lines
        else:
            try:
                text = claimed.read_text(errors="replace")
                with solo.open("a") as stream:
                    stream.write(text)
                lines += text.splitlines()
            finally:
                claimed.unlink(missing_ok=True)
    return lines


def load_configuration(root: Path) -> dict | None:
    try:
        return configuration(root)
    except Exception:  # an unreadable configuration must never open the gate
        return None


def gate_mode(config: dict | None) -> tuple[str, str]:
    value = config_value(config, "verification.stop_gate") if config is not None else None
    if value in (None, "") or value == "block":
        return "block", ""
    if value in MODES:
        return value, ""
    text = json.dumps(value) if isinstance(value, (dict, list, bool)) else str(value)
    shown = "".join(char for char in text if " " <= char <= "~")[:40]
    return "block", f" verification.stop_gate is {shown}, not block, notify or off, so the gate blocks."


def simulator_present(config: dict | None) -> bool:
    if os.environ.get("SIM"):
        return True  # run_sim.sh honors the same variable
    if config is not None:
        if config_value(config, "preferences.simulator") not in (None, ""):
            return True
        try:
            if backend(config) in ("docker", "ssh", "lsf"):
                return True
        except Exception:  # a malformed execution block names no backend
            pass
    return any(shutil.which(tool) for tool in SIMULATORS)


def relative(root: Path, path: str) -> str:
    candidate = Path(path)
    return str(candidate.relative_to(root)) if candidate.is_relative_to(root) else path


def remove_tracking(state: Path) -> None:
    for path in [state / "rtl-modified-files.txt", *state.glob("rtl-modified-files-*.txt")]:
        path.unlink(missing_ok=True)


def cleanup(state: Path) -> None:
    for name in ("rtl-modified-files.txt", "rtl-verify-done", "rtl-verify-waiver", "rtl-modified-files-fallback.txt"):
        (state / name).unlink(missing_ok=True)
    for path in state.glob("rtl-modified-files-*.txt"):
        path.unlink(missing_ok=True)


def cleared_notice(root: Path, used) -> str:
    """Name the project runners whose verify-run evidence cleared the gate."""
    files, runs = set(), []
    for record, hit in used:
        if record.get("origin") != "verify-run":
            continue
        files |= hit
        argv = [str(value) for value in record.get("argv") or []]
        if argv and Path(argv[0]).is_absolute():
            argv[0] = relative(root, str(Path(argv[0]).resolve()))  # root is resolved, e.g. /private/tmp
        command = " ".join(argv)
        command = command if len(command) <= 100 else command[:97] + "..."
        label = command + (f" on {record['remote_host']}" if record.get("remote_host") else "")
        if label not in runs:
            runs.append(label)
    if not runs:
        return ""
    shown = "; ".join(runs[:3]) + (f"; and {len(runs) - 3} more" if len(runs) > 3 else "")
    return f"Info> Rule 5 cleared for {len(files)} RTL file(s) by verify-run: {shown}."


def decide(root: Path, state: Path, plugin: str) -> dict[str, str]:
    lines = tracking(state)
    if not any(line.strip() for line in lines):
        remove_tracking(state)  # blank lines only: nothing to verify, and no Python start next time
        return {"VG_ACTION": "clear"}
    config = load_configuration(root)
    mode, note = gate_mode(config)
    if mode == "off":
        return {"VG_ACTION": "continue"}  # tracking stays, so block resumes the pending files
    resolved = root.resolve()
    tracked = tracked_paths(resolved, lines)
    if running_cover(resolved, tracked, state / "verify-runs"):
        return {"VG_ACTION": "continue"}  # a live run covers every file; its completion decides
    failures: list[tuple[dict, str | None]] = []
    remaining, used = clearing(resolved, tracked, state / "verify-evidence.json", failures)
    if not remaining or (state / "rtl-verify-waiver").exists():
        notice = "" if remaining else cleared_notice(resolved, used)  # before cleanup, so a failure keeps tracking
        cleanup(state)
        return {"VG_ACTION": "cleared", "VG_NOTICE": notice}
    shown = sorted(relative(resolved, path) for path in remaining)
    count = len(shown)
    files = ", ".join(shown[:10]) + (f", and {count - 10} more" if count > 10 else "")
    runner = shq(plugin + "/scripts/eda_runner.py")
    evidence = shq(str(state / "verify-evidence.json"))
    retry = f"Rerun the unresolved failing case(s): {failed_case_labels(failures)}. " if failures else ""
    message = (
        f"[RTL Verify Gate BLOCKED] {count} RTL {'file needs' if count == 1 else 'files need'} "
        f"passing functional verification: {files}. {retry}"
        "Run functional verification for the affected modules through scripts/run_sim.sh; --sim auto uses the "
        "configured or an installed simulator (for example /rtl-agent-team:rtl-p4s-unit-test, or the project's "
        "regression skill for its configured simulator). A passing testbench emits RAT_SIM_PASS or a recognized "
        f"test summary; the runner records fresh source and log hashes in {evidence}. A touched marker is "
        "insufficient. A project's own runner (a local script, or one that reaches a remote simulator through "
        f"rsync/ssh or LSF) records the same evidence through {runner} verify-run --root <project> -f <filelist> "
        "[--log <summary file>] [--remote-host <host> --remote-root <dir>] -- <runner>; the runner must print "
        "RAT_SIM_PASS or TESTS=<n> PASS=<n> FAIL=0, and --remote-host hashes the inputs on that host after the run."
        f"{note} If verification cannot run here, report what is missing and ask the user with AskUserQuestion "
        "whether to waive it; a waiver is the user's decision."
    )
    progress = "\n".join(shown)
    for path in sorted(remaining):
        try:
            progress += "|" + hashlib.sha256(Path(path).read_bytes()).hexdigest()
        except OSError:
            pass
    pending = f"Functional verification is pending for {count} RTL file(s)"
    return {
        "VG_ACTION": "gate", "VG_MODE": mode, "VG_SIM_PRESENT": "true" if simulator_present(config) else "false",
        "VG_MSG": message, "VG_NOTICE": f"Info> {pending}.",
        "VG_NOTIFY_NOTICE": f"Info> {pending} (verification.stop_gate=notify).",
        "VG_NOSIM_NOTICE": f"Info> {pending}, but no simulator is configured or on PATH. "
                           "Run /rtl-agent-team:rat-setup to configure one.",
        "VG_PROGRESS": progress,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", required=True, help="project root (the launcher's CWD)")
    parser.add_argument("--state", required=True)
    parser.add_argument("--plugin", required=True, help="plugin root, as the launcher spells it")
    args = parser.parse_args()
    values = decide(Path(args.root), Path(args.state), args.plugin)
    sys.stdout.write("".join(f"{name}={shq(value)}\n" for name, value in values.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
