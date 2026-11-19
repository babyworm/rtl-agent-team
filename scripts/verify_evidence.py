#!/usr/bin/env python3
# rat-version: 2.0.3
"""Content-bound simulation evidence; a zero exit alone is not a functional PASS."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import socket
import sys
import tempfile
import time
import uuid


PASS_PATTERN = r"(?im)^\s*(?:RAT_SIM_PASS|ALL TESTS PASSED|TESTS? PASSED|PASS)(?:\b|:)"
FAIL_PATTERN = r"(?im)(?:^\s*(?:#\s*)?\[?(?:FATAL|FAIL(?:ED|URE|URES)?)\b|%Error(?=[:-])|\bERROR\s*:|\*[EF],|assertion[^\n]*failed|\bFAIL(?:ED|URES?)?\s*[=:]\s*[1-9]\d*)"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    if path.is_symlink():
        raise ValueError(f"refusing symlink evidence target: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, sort_keys=True)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def source_paths(root: Path, sources: list[str], filelist: str = "", details: dict | None = None, extra_includes: list[str] | None = None) -> list[Path]:
    paths: set[Path] = set()
    visited: set[Path] = set()
    include_dirs: list[Path] = []
    ordered_sources: list[Path] = []

    def add_source(path):
        paths.add(path)
        if path not in ordered_sources: ordered_sources.append(path)

    def add_include(path):
        if path not in include_dirs: include_dirs.append(path)
    filelists: set[Path] = set()
    defines: list[str] = []

    def resolve(value: str, base: Path) -> Path:
        value = os.path.expandvars(value)
        if any(character in value for character in ("$", "`", ";", "|", "&", ">", "<", "\n", "\r")):
            raise ValueError(f"shell-unsafe source or filelist path: {value!r}")
        candidate = Path(value)
        if not candidate.is_absolute():
            candidate = base / candidate
            if not candidate.exists() and (root / value).exists():
                candidate = root / value
        return candidate.resolve(strict=True)

    def read_list(path: Path) -> None:
        if path in visited:
            raise ValueError(f"recursive filelist: {path}")
        visited.add(path)
        paths.add(path)
        filelists.add(path)
        lines = [line for line in path.read_text().splitlines()
                 if not line.lstrip().startswith(("//", "#"))]
        tokens = shlex.split("\n".join(lines), comments=True)
        index = 0
        while index < len(tokens):
            token = tokens[index]
            if token in ("-f", "-F"):
                index += 1
                read_list(resolve(tokens[index], path.parent))
            elif token.startswith("+incdir+"):
                [add_include(resolve(part, path.parent)) for part in token[8:].split("+") if part]
            elif token.startswith("+define+"):
                defines.extend(part for part in token[8:].split("+") if part)
            elif token in ("-I", "-y"):
                index += 1
                add_include(resolve(tokens[index], path.parent))
            elif token.startswith("-I"):
                add_include(resolve(token[2:], path.parent))
            elif token == "-v":
                index += 1
                add_source(resolve(tokens[index], path.parent))
            elif token.startswith(("-", "+")):
                raise ValueError(f"unsupported evidence filelist directive: {token}")
            else:
                add_source(resolve(token, path.parent))
            index += 1
        visited.remove(path)

    declared=[]
    config=root/"rat_config.json"
    if config.is_file(): declared=json.loads(config.read_text()).get("verification",{}).get("include_dirs",[])
    if not isinstance(declared,list) or not all(isinstance(value,str) for value in declared):
        raise ValueError("verification.include_dirs must be a list of paths")
    uvm=os.environ.get("UVM_HOME")
    if uvm and (Path(uvm)/"src").is_dir(): declared.append(str(Path(uvm)/"src"))
    [add_include(resolve(path, root)) for path in [*(extra_includes or []),*declared]]
    [add_source(resolve(path, root)) for path in sources]
    if filelist:
        read_list(resolve(filelist, root))
    if details is not None:
        details.update(sources=ordered_sources, includes=include_dirs.copy(),
                       defines=defines, filelists=sorted(filelists))
    # Include files can themselves include another file. Hash their complete
    # search directories conservatively rather than attesting only to the DUT.
    [add_include(path.parent) for path in ordered_sources if path.suffix in (".sv", ".v")]
    for directory in include_dirs:
        for pattern in ("*.svh", "*.vh"):
            paths.update(path.resolve() for path in directory.rglob(pattern) if path.is_file())
    pending = list(paths)
    scanned: set[Path] = set()
    while pending:
        path = pending.pop()
        if path in scanned or path.suffix not in (".sv", ".v", ".svh", ".vh"):
            continue
        scanned.add(path)
        for name in re.findall(r'(?m)^\s*`include\s+"([^"]+)"', path.read_text(errors="replace")):
            candidates = [path.parent / name] + [directory / name for directory in include_dirs]
            included = next((candidate.resolve() for candidate in candidates if candidate.is_file()), None)
            if included is None:
                raise ValueError(f"unresolved include {name!r} in {path}")
            if included not in paths:
                paths.add(included)
                pending.append(included)
    return sorted(paths)


def inputs(args) -> int:
    root = Path(args.root).resolve()
    details = {}
    source_paths(root, args.source, args.filelist, details)
    if args.write_filelist:
        lines = ["+incdir+" + str(path) for path in details["includes"]]
        lines += ["+define+" + value for value in details["defines"]]
        lines += [str(path) for path in details["sources"]]
        for line in lines:
            if any(character in line for character in ("\n", "\r", "\t")):
                raise ValueError("filelist inputs cannot contain control characters")
        Path(args.write_filelist).write_text("\n".join(lines) + "\n")
    for key in ("sources", "includes", "defines", "filelists"):
        for value in details[key]:
            if any(character in str(value) for character in ("\n", "\r", "\t")):
                raise ValueError("input paths cannot contain control characters")
            print(key + "\t" + str(value))
    return 0


def classify(exit_code: int, text: str, pass_pattern: str = PASS_PATTERN) -> str:
    if exit_code == 124 or "RAT_TIMEOUT" in text:
        return "TIMEOUT"
    if "RAT_STALL" in text:
        return "STALL"
    if "RAT_HANG" in text:
        return "HANG"
    for message in re.findall(r"(?im)^\s*(?:#\s*)?UVM_(?:ERROR|FATAL)\b(.*)$", text):
        if not re.fullmatch(r"\s*:\s*0\s*",message): return "FAIL"
    uvm_failures = re.findall(r"(?im)^\s*UVM_(?:ERROR|FATAL)\s*:\s*(\d+)", text)
    if any(int(value) for value in uvm_failures):
        return "FAIL"
    cleaned = re.sub(r"(?i)\b(?:FAIL(?:ED|URES?)?|ERRORS?|FATALS?)\s*[=:]\s*0\b|\b0\s+(?:failed|failures|errors)\b", "", text)
    if exit_code != 0 or re.search(FAIL_PATTERN, cleaned):
        return "FAIL"
    cocotb = re.search(r"TESTS\s*=\s*(\d+)\s+PASS\s*=\s*(\d+)\s+FAIL\s*=\s*0\b", text)
    if re.search(pass_pattern, text) or (cocotb and int(cocotb[1]) > 0 and cocotb[1] == cocotb[2]):
        return "PASS"
    return "INCONCLUSIVE"


def unchanged(sources: dict[str, str]) -> bool:
    return bool(sources) and all(Path(path).is_file() and digest(Path(path)) == expected
                                 for path, expected in sources.items())


def process_identity(pid: int) -> str:
    try:
        stat=Path(f"/proc/{pid}/stat").read_text().rsplit(") ",1)[1].split()
        return "proc:"+stat[19]
    except (OSError,IndexError):
        import subprocess
        result=subprocess.run(["ps","-p",str(pid),"-o","lstart="],capture_output=True,text=True)
        return result.stdout.strip() if result.returncode==0 else ""


def begin(args) -> int:
    root = Path(args.root).resolve()
    outdir = Path(args.outdir).resolve()
    marker = ".rtl-agent-team" if not (root / ".rat").exists() and (root / ".rtl-agent-team").exists() else ".rat"
    state = root / marker / "state"
    if not state.resolve().is_relative_to(root):
        raise ValueError("evidence state directory escapes the project")
    if args.run_only:
        build = json.loads((outdir / ".rat-build.json").read_text())
        if (build["tool"] != args.tool or build["top"] != args.top
                or build.get("context", "") != args.context or not unchanged(build["sources"])):
            raise ValueError("compiled sources changed; compile again before running")
        if not build.get("artifacts") or not unchanged(build["artifacts"]):
            raise ValueError("compiled artifacts changed or are missing; compile again before running")
        sources = build["sources"]
    else:
        sources = {str(path): digest(path) for path in source_paths(root, args.source, args.filelist, extra_includes=args.include_dir)}
        for name in args.dependency:
            dependency = (root / name).resolve(strict=True)
            sources[str(dependency)] = digest(dependency)
    if not sources:
        raise ValueError("simulation evidence requires identifiable source inputs")
    record = {"schema_version": 1, "run_id": uuid.uuid4().hex, "root": str(root),
              "outdir": str(outdir), "state_dir": str(state), "tool": args.tool, "top": args.top,
              "sources": sources, "context": args.context, "verdict": "RUNNING", "started_at": time.time(),
              "runner_pid": args.runner_pid or os.getppid(),
              "runner_identity": process_identity(args.runner_pid or os.getppid()), "host": socket.gethostname(),
              "compile_only": args.compile_only, "artifact_paths": args.artifact}
    target = state / "verify-runs" / (record["run_id"] + ".json")
    atomic_json(target, record)
    print(target)
    return 0


def finish(args) -> int:
    target = Path(args.snapshot)
    record = json.loads(target.read_text())
    log = Path(args.log)
    text = log.read_text(errors="replace") if log.is_file() else ""
    runtime_log=Path(args.runtime_log) if args.runtime_log else None
    runtime_text=runtime_log.read_text(errors="replace") if runtime_log and runtime_log.is_file() else "" if runtime_log else text
    verdict = classify(args.exit_code, runtime_text)
    all_logs=classify(args.exit_code,text)
    if all_logs in ("FAIL","TIMEOUT","STALL","HANG"): verdict=all_logs
    if args.compile_only and args.exit_code == 0 and verdict not in ("FAIL","TIMEOUT","STALL","HANG"):
        verdict = "COMPILED"
    artifacts={}
    for name in record.get("artifact_paths",[]):
        artifact=Path(name)
        files=[artifact] if artifact.is_file() else list(artifact.rglob("*")) if artifact.is_dir() else []
        files=[path for path in files if path.is_file()]
        if not files and verdict in ("PASS","COMPILED"): verdict="INCONCLUSIVE"
        artifacts.update({str(path.resolve()):digest(path) for path in files})
    record["artifacts"]=artifacts
    record["sources_fresh"]=unchanged(record["sources"])
    if not record["sources_fresh"] and verdict in ("PASS","COMPILED"):
        verdict = "INCONCLUSIVE"
    record.update(verdict=verdict, completed_at=time.time(), exit_code=args.exit_code,
                  log=str(log.resolve()), log_sha256=digest(log) if log.is_file() else None)
    if runtime_log:
        record["runtime_log"]={"path":str(runtime_log.resolve()),"sha256":digest(runtime_log) if runtime_log.is_file() else None}
    atomic_json(target, record)
    if verdict in ("PASS", "COMPILED"):
        atomic_json(Path(record["outdir"]) / ".rat-build.json", record)
    index = Path(record["state_dir"]) / "verify-evidence.json"
    lock = index.with_suffix(".lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        data = json.loads(index.read_text()) if index.is_file() else {"schema_version": 1, "runs": []}
        data["runs"].append(record)
        atomic_json(index, data)
    print(f"[run_sim] verdict={verdict}; evidence={target}")
    return args.exit_code if args.exit_code else (0 if verdict in ("PASS", "COMPILED") else 3)


def unverified(args) -> int:
    root = Path(args.root).resolve()
    tracked = {str((root / line.strip()).resolve()) for line in Path(args.track).read_text().splitlines() if line.strip()}
    index = Path(args.track).parent / "verify-evidence.json"
    try:
        records = json.loads(index.read_text())["runs"]
    except (OSError, ValueError, KeyError, TypeError):
        records = []
    for record in records:
        try:
            log = Path(record["log"])
            if (record["verdict"] == "PASS" and log.is_file()
                    and digest(log) == record["log_sha256"] and unchanged(record["sources"])
                    and (not record.get("runtime_log") or
                         (Path(record["runtime_log"]["path"]).is_file() and
                          digest(Path(record["runtime_log"]["path"]))==record["runtime_log"]["sha256"]))):
                tracked.difference_update(record["sources"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
    for path in sorted(tracked):
        candidate = Path(path)
        print(candidate.relative_to(root) if candidate.is_relative_to(root) else candidate)
    return bool(tracked)


def pending_run(args) -> int:
    root = Path(args.root).resolve()
    track = Path(args.track)
    tracked = {str((root / line.strip()).resolve()) for line in track.read_text().splitlines() if line.strip()}
    covered = set()
    for path in (track.parent / "verify-runs").glob("*.json"):
        try:
            record = json.loads(path.read_text())
            if (record["verdict"] != "RUNNING" or record.get("compile_only")
                    or record.get("host") != socket.gethostname()
                    or not record.get("runner_identity")
                    or process_identity(record["runner_pid"]) != record["runner_identity"]
                    or not unchanged(record["sources"])):
                continue
            os.kill(record["runner_pid"], 0)
            covered.update(record["sources"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return 0 if tracked and tracked <= covered else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("begin")
    for name in ("root", "outdir", "tool", "top"):
        start.add_argument("--" + name, required=True)
    start.add_argument("--context", default="")
    start.add_argument("--source", action="append", default=[])
    start.add_argument("--artifact", action="append", default=[])
    start.add_argument("--include-dir", action="append", default=[])
    start.add_argument("--dependency", action="append", default=[])
    start.add_argument("--filelist", default="")
    start.add_argument("--run-only", action="store_true")
    start.add_argument("--compile-only", action="store_true")
    start.add_argument("--runner-pid", type=int, default=0)
    end = sub.add_parser("finish")
    for name in ("snapshot", "log"):
        end.add_argument("--" + name, required=True)
    end.add_argument("--exit-code", type=int, required=True)
    end.add_argument("--runtime-log", default="")
    end.add_argument("--compile-only", action="store_true")
    check = sub.add_parser("unverified")
    check.add_argument("--root", required=True)
    check.add_argument("--track", required=True)
    waiting = sub.add_parser("pending")
    waiting.add_argument("--root", required=True)
    waiting.add_argument("--track", required=True)
    classification = sub.add_parser("classify")
    classification.add_argument("--log", required=True)
    classification.add_argument("--exit-code", type=int, required=True)
    listing = sub.add_parser("inputs")
    listing.add_argument("--root", required=True)
    listing.add_argument("--filelist", default="")
    listing.add_argument("--source", action="append", default=[])
    listing.add_argument("--write-filelist")
    args = parser.parse_args()
    try:
        return {"begin": begin, "finish": finish, "unverified": unverified,
                "pending": pending_run, "inputs": inputs,
                "classify": lambda a: print(classify(a.exit_code, Path(a.log).read_text(errors="replace"))) or 0}[args.command](args)
    except (OSError, ValueError, KeyError, IndexError, TypeError) as exc:
        print(f"verification evidence error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
