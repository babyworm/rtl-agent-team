"""Resolve phase review opt-in and run one read-only Codex exchange."""

import argparse
from contextlib import suppress
import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

SKILL = Path(__file__).resolve().parents[1]
MODEL_RESOLVER = SKILL.parents[1] / "scripts" / "resolve_agent_model.py"
PHASE_IDS = ("1", "2", "3", "4", "5", "5a", "5b", "6", "7")


def enabled(root, choice, phase):
    if choice in {"on", "off"}:
        return choice == "on"
    if choice != "project":
        selected = set(choice.split(","))
        if not phase or selected.difference(PHASE_IDS):
            raise ValueError("phase-specific review requires --phase and a comma-separated list of phase IDs")
        return phase in selected or (phase in {"5a", "5b"} and "5" in selected)
    config = root / "rat_config.json"
    if not config.is_file():
        return False
    with config.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or not isinstance(data.get("review", {}), dict):
        raise ValueError("rat_config.json review must be an object")
    value = data.get("review", {}).get("codex_cross_review", False)
    if not isinstance(value, bool):
        raise ValueError("review.codex_cross_review must be true or false")
    return value


def read_response(output):
    response = json.loads(output.read_text(encoding="utf-8"))
    schema = json.loads((SKILL / "review-schema.json").read_text(encoding="utf-8"))
    fields = schema["properties"]
    if (not isinstance(response, dict) or set(response) != set(fields)
            or response["verdict"] not in fields["verdict"]["enum"]
            or not isinstance(response["findings"], list)
            or response["resolved_items"] != [] or not isinstance(response["summary"], str)):
        raise ValueError("Codex returned an invalid first-pass review")
    finding_fields = fields["findings"]["items"]["properties"]
    types = {str: "string", int: "integer", type(None): "null"}
    for finding in response["findings"]:
        if not isinstance(finding, dict) or set(finding) != set(finding_fields):
            raise ValueError("Codex returned an incomplete finding")
        for key, spec in finding_fields.items():
            allowed = spec["type"] if isinstance(spec["type"], list) else [spec["type"]]
            value = finding[key]
            if types.get(type(value)) not in allowed or ("enum" in spec and value not in spec["enum"]):
                raise ValueError(f"Codex returned an invalid finding field: {key}")
    return response


def run(args):
    folder = args.root / ".rat" / "cross-review" / f"phase-{args.phase}"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / ".review.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise ValueError("another review owns this phase") from error
        marker = args.root / ".rat" / "state" / f"cross-review-phase-{args.phase}-done"
        marker.unlink(missing_ok=True)
        prompt = (folder / "prompt-round-1.txt").read_text(encoding="utf-8")
        if not prompt.strip():
            raise ValueError("review prompt is empty")
        resolver = [sys.executable, str(MODEL_RESOLVER), "--host", "codex", "--tier", args.tier]
        if args.model:
            resolver.extend(["--model", args.model])
        model = subprocess.check_output(resolver, cwd=args.root, text=True, timeout=30).strip()
        command = ["codex", "exec", "--ephemeral", "-s", "read-only", "--output-schema", str(SKILL / "review-schema.json")]
        if model:
            command.extend(["-m", model])
        with tempfile.TemporaryDirectory(dir=folder) as tmp:
            output = Path(tmp) / "response.json"
            log = folder / "round-1-log.txt"
            with log.open("w", encoding="utf-8") as stream:
                pane = None
                if os.environ.get("TMUX") and shutil.which("tmux"):
                    # Watch the single process even when a tmux pane cannot be created.
                    with suppress(OSError, subprocess.SubprocessError):
                        pane = subprocess.check_output(
                            ["tmux", "split-window", "-dP", "-F", "#{pane_id}", "tail", "-n", "+1", "-f", str(log)],
                            stderr=subprocess.DEVNULL, text=True, timeout=5,
                        ).strip()
                try:
                    subprocess.run(command + ["-o", str(output), "-"], cwd=args.root, input=prompt,
                                   stdout=stream, stderr=subprocess.STDOUT, text=True, check=True, timeout=1200)
                finally:
                    if pane:
                        with suppress(OSError, subprocess.SubprocessError):
                            subprocess.run(["tmux", "kill-pane", "-t", pane], capture_output=True, timeout=5)
            response = read_response(output)
            output.replace(folder / "round-1.json")
            print(f"{response['verdict']} ({model or 'Codex session model'}): {folder / 'round-1.json'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--root", type=Path, default=Path.cwd())
    shared.add_argument("--choice", type=str.lower, default="project",
                        help="project, on, off, or comma-separated phase IDs such as 2,3")
    probe = sub.add_parser("enabled", parents=[shared])
    probe.add_argument("--phase", choices=PHASE_IDS, type=str.lower)
    execute = sub.add_parser("run", parents=[shared])
    execute.add_argument("--phase", choices=PHASE_IDS, type=str.lower, required=True)
    execute.add_argument("--model")
    execute.add_argument("--tier", choices=("complex", "design", "straightforward", "trivial"), default="design")
    args = parser.parse_args()
    args.root = args.root.resolve()
    try:
        active = enabled(args.root, args.choice, args.phase)
        if args.action == "enabled":
            print("on" if active else "off")
        elif active:
            run(args)
        else:
            print("skipped (Codex review disabled)")
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.exit(1, f"Codex review incomplete: {error}\n")


if __name__ == "__main__":
    main()
