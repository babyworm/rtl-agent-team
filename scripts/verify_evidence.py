#!/usr/bin/env python3
# rat-version: 1.0.0-pre20
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
CHECK_POINT = re.compile(r"RAT_CHECK_POINT ([A-Za-z0-9_.:\[\]-]+) ([0-9]+) ([0-9]+)")


def check_point_error(line: str) -> str:
    if not line.startswith("RAT_CHECK_POINT"):
        return ""
    record = CHECK_POINT.fullmatch(line)
    if not record:
        return f"malformed check record: {line}"
    if record[3].strip("0"):
        return f"{record[1]}: {record[3]} failed checks"
    return ""


def log_has_failed_point(lines) -> bool:
    return any(check_point_error(line.strip().removeprefix("# ")) for line in lines)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


HDL_SUFFIXES = (".sv", ".svh", ".v", ".vh")
# Escaped identifiers (\name ending at whitespace) may contain // or /*; keep them opaque.
HDL_SPLIT = re.compile(r'(\\\S+|"(?:\\.|[^"\\\n])*"|//[^\n]*|/\*.*?\*/|\s+)', re.S)
# Tool directives live in comments, so a pragma edit is still a source change. Underscores
# count as boundaries so prefixed directives such as rtl_synthesis stay significant.
PRAGMA = re.compile(r"(?i)(?<![a-z0-9])(?:synopsys|synthesis|pragma|translate_o(?:n|ff)|verilator|cadence|ambit|"
                    r"spyglass|lint_o(?:n|ff)|coverage|full_case|parallel_case)(?![a-z0-9])")


def hdl_text(text: str) -> str:
    """HDL without ordinary comments or indentation; string literals and line breaks stay."""
    pieces: list[str] = []
    gap = ""
    for index, part in enumerate(HDL_SPLIT.split(text)):
        if not part:
            continue
        if index % 2 and (part[0].isspace() or part[:2] in ("//", "/*")) and not PRAGMA.search(part):
            gap = "\n" if "\n" in part or gap == "\n" else " "
            continue
        if pieces and gap:
            pieces.append(gap)
        pieces.append(part)
        gap = ""
    return "".join(pieces)


HDL_IDENTITY_LIMIT = 2_000_000  # larger HDL is generated; its raw hash is its identity


def source_digest(path: Path) -> str:
    """Behavioral identity of a source; comment-only HDL edits keep it. Slower than digest()."""
    if path.suffix not in HDL_SUFFIXES or path.stat().st_size > HDL_IDENTITY_LIMIT:
        return digest(path)
    text = hdl_text(path.read_bytes().decode("utf-8", "surrogateescape"))
    return hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest()


def source_identity(sources) -> dict[str, str]:
    return {name: source_digest(Path(name)) for name in sources if Path(name).suffix in HDL_SUFFIXES}


def source_matches(path: Path, expected: str, identity: str | None = None) -> bool:
    # The raw hash is the fast path; an HDL file whose comments or indentation
    # changed still matches its recorded behavioral identity.
    if not path.is_file():
        return False
    return digest(path) == expected or (bool(identity) and path.suffix in HDL_SUFFIXES
                                        and source_digest(path) == identity)


def seed_log_sizes(paths: list[str], runtime_digest: str) -> list[int]:
    combined = hashlib.sha256()
    sizes = []
    seen = set()
    for name in paths:
        with Path(name).open("rb") as stream:
            stat = os.fstat(stream.fileno())
            identity = (stat.st_dev, stat.st_ino)
            if identity in seen:
                raise ValueError(f"duplicate seed log: {name}")
            seen.add(identity)
            size = 0
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                combined.update(chunk)
                size += len(chunk)
            if not size:
                raise ValueError(f"empty seed log: {name}")
            sizes.append(size)
    if combined.hexdigest() != runtime_digest:
        raise ValueError("seed logs must concatenate to the runtime log in the supplied order")
    return sizes


POINT_PLAN = Path("sim/verification-points.json")
MODEL_SUFFIX = r"(?:c(?:pp|xx|c)?|h(?:pp|xx|h)?)"
MODEL_CITATION = re.compile(
    rf"`([^`\n]+?\.{MODEL_SUFFIX})(?:[#:][^`\n]*)?`|"
    rf"(?<![\w./-])([\w./-]+\.{MODEL_SUFFIX})(?=$|[\s#:`,;)\]]|\.(?:\s|$))", re.I)
MODEL_MENTION = re.compile(r"\b(?:ref[- ]?c|reference c model|c (?:reference )?model)\b", re.I)
MODEL_REVISION = re.compile(r"\b(?:[0-9a-f]{40}|[0-9a-f]{64})\b", re.I)
CITED_MODEL_REVISION = re.compile(
    MODEL_MENTION.pattern + r"\s*(?:at\s+|@\s*|(?:commit|revision|sha256)\s*[:=]?\s*)" + MODEL_REVISION.pattern,
    re.I)


def point_fingerprint(root: Path, point: dict, input_hashes: dict[Path, str] | None = None) -> str:
    """Bind a measurement to what was observed and the oracle used for that point."""
    contract = {key: point[key] for key in ("id", "kind", "requirement", "source", "trigger", "expected_result")}
    inputs = point.get("inputs", [])
    if not isinstance(inputs, list):
        raise ValueError("inputs must be a list of project-relative files")
    source = point["source"]
    revision = point.get("oracle_revision")
    if revision is not None:
        if not isinstance(revision, str) or not MODEL_REVISION.fullmatch(revision):
            raise ValueError(f"{point['id']}: oracle_revision needs the full commit ID or SHA-256")
        contract["oracle_revision"] = revision.lower()
    pinned = revision or CITED_MODEL_REVISION.search(source)
    url = r"\b[\w+.-]+://[^\s`]+"
    local_source = re.sub(url, "", source)
    cites_model = bool(MODEL_MENTION.search(source) or
                       any(MODEL_CITATION.search(uri) for uri in re.findall(url, source)))
    local_inputs = list(inputs)
    for match in MODEL_CITATION.finditer(local_source):
        quoted, plain = match.groups()
        name = quoted or plain
        # A bare token such as Table A.1.c is also a legal C filename.
        if not (quoted or "/" in name or re.match(r"#\w|:\d", local_source[match.end():])
                or (root / name).is_file()):
            continue
        cites_model = True
        path = (root / name).resolve()
        if path.is_relative_to(root):
            local_inputs.append(str(path.relative_to(root)) if Path(name).is_absolute() else name)
        elif not pinned:
            raise ValueError(f"{point['id']}: pin the external refC source with oracle_revision")
    files = {}
    if input_hashes is None:
        input_hashes = {}
    for name in local_inputs:
        if not isinstance(name, str) or not name.strip() or Path(name).is_absolute():
            raise ValueError("inputs must name project-relative files")
        path = (root / name).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f"invalid point input: {name}")
        if path not in input_hashes:
            input_hashes[path] = digest(path)
        files[name] = input_hashes[path]
    has_model = any(re.fullmatch(MODEL_SUFFIX, Path(name).suffix[1:], re.I) for name in files)
    if cites_model and not (has_model or pinned):
        raise ValueError(f"{point['id']}: cite the local refC source in inputs or pin the external oracle_revision")
    contract["inputs"] = files
    return hashlib.sha256(json.dumps(contract, sort_keys=True).encode()).hexdigest()


def planned_fingerprints(root: Path) -> dict:
    # An unfinished plan can still run simulations. Closure validates the plan.
    try:
        points = json.loads((root / POINT_PLAN).read_text())["points"]
    except (OSError, ValueError, KeyError, TypeError):
        return {}
    if not isinstance(points, list):
        return {}
    fingerprints = {}
    input_hashes: dict[Path, str] = {}
    for point in points:
        try:
            fingerprints[point["id"]] = point_fingerprint(root, point, input_hashes)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError):
            continue
    return fingerprints


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
    filelist_args: list[str] = []

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
                directories = [resolve(part, path.parent) for part in token[8:].split("+") if part]
                for directory in directories:
                    add_include(directory)
                filelist_args.append("+incdir+" + "+".join(map(str, directories)))
            elif token.startswith("+define+"):
                defines.extend(part for part in token[8:].split("+") if part)
                filelist_args.append(token)
            elif token in ("-I", "-y"):
                index += 1
                directory = resolve(tokens[index], path.parent)
                add_include(directory)
                filelist_args.extend((token, str(directory)))
            elif token.startswith("-I"):
                directory = resolve(token[2:], path.parent)
                add_include(directory)
                filelist_args.append("-I" + str(directory))
            elif token == "-v":
                index += 1
                library = resolve(tokens[index], path.parent)
                add_source(library)
                filelist_args.extend(("-v", str(library)))
            elif token.startswith(("-", "+")):
                raise ValueError(f"unsupported evidence filelist directive: {token}")
            else:
                source = resolve(token, path.parent)
                add_source(source)
                filelist_args.append(str(source))
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
                       defines=defines, filelists=sorted(filelists), filelist_args=filelist_args)
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
    details: dict = {}
    source_paths(root, args.source, args.filelist, details)
    if args.relocate_filelist:
        # Keep library search (-y), library file (-v) and macro ordering intact.
        lines = [json.dumps(arg) if any(c.isspace() for c in arg) else arg for arg in details["filelist_args"]]
        Path(args.relocate_filelist).write_text("\n".join(lines) + "\n")
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


def classify(exit_code: int, text: str, pass_pattern: str = PASS_PATTERN, *, check_points: bool = True) -> str:
    if exit_code == 124 or "RAT_TIMEOUT" in text:
        return "TIMEOUT"
    if "RAT_STALL" in text:
        return "STALL"
    if "RAT_HANG" in text:
        return "HANG"
    if check_points and "RAT_CHECK_POINT" in text and log_has_failed_point(text.splitlines()):
        return "FAIL"
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


def unchanged(sources: dict[str, str], identity: dict[str, str] | None = None) -> bool:
    identity = identity if isinstance(identity, dict) else {}
    return bool(sources) and all(source_matches(Path(path), expected, identity.get(path))
                                 for path, expected in sources.items())


def process_identity(pid: int) -> str:
    try:
        stat=Path(f"/proc/{pid}/stat").read_text().rsplit(") ",1)[1].split()
        return "proc:"+stat[19]
    except (OSError,IndexError):
        import subprocess
        try:
            result=subprocess.run(["ps","-p",str(pid),"-o","lstart="],capture_output=True,text=True)
            return result.stdout.strip() if result.returncode==0 else ""
        except (OSError, subprocess.SubprocessError):
            # Sandboxed macOS (Seatbelt) may block setuid /bin/ps with EPERM.
            # Fall back to checking process liveness via signal 0.
            try:
                os.kill(pid, 0)
                return f"pid:{pid}"
            except OSError:
                return ""


def pre_init_state_root(root: Path) -> Path | None:
    # Hooks treat any .rat/ as a RAT project. Before rat-init-project, keep run records
    # in the plugin data folder so that running a tool does not initialize the folder.
    root = root.resolve()
    folder = os.environ.get("RAT_DATA_DIR") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if not folder or (root / ".rat").exists() or (root / ".rtl-agent-team").exists():
        return None
    name = re.sub(r"[^A-Za-z0-9_.-]", "-", root.name) or "root"
    return Path(folder) / "projects" / (name + "-" + hashlib.sha256(str(root).encode()).hexdigest()[:12])


def runtime_state_root(root: Path) -> Path:
    legacy = root / ".rtl-agent-team"
    if legacy.is_dir() and not (root / ".rat").exists():
        return legacy
    return pre_init_state_root(root) or root / ".rat"


def state_within_bounds(root: Path, path: Path) -> bool:
    outside = pre_init_state_root(root)
    path = path.resolve()
    return path.is_relative_to(root.resolve()) or (outside is not None and path.is_relative_to(outside.resolve()))


def begin(args) -> int:
    print(begin_record(args))
    return 0


def begin_record(args) -> Path:
    root = Path(args.root).resolve()
    outdir = Path(args.outdir).resolve()
    state = runtime_state_root(root) / "state"
    if not state_within_bounds(root, state):
        raise ValueError("evidence state directory escapes the project")
    if args.run_only:
        build = json.loads((outdir / ".rat-build.json").read_text())
        if (build["tool"] != args.tool or build["top"] != args.top
                or build.get("context", "") != args.context
                or not unchanged(build["sources"], build.get("source_identity"))):
            raise ValueError("compiled sources changed; compile again before running")
        if not build.get("artifacts") or not unchanged(build["artifacts"]):
            raise ValueError("compiled artifacts changed or are missing; compile again before running")
        sources = build["sources"]
        identity = build.get("source_identity", {})
    else:
        sources = {str(path): digest(path) for path in source_paths(root, args.source, args.filelist, extra_includes=args.include_dir)}
        for name in args.dependency:
            dependency = (root / name).resolve(strict=True)
            sources[str(dependency)] = digest(dependency)
        identity = source_identity(sources)
    if not sources:
        raise ValueError("simulation evidence requires identifiable source inputs")
    record = {"schema_version": 1, "run_id": uuid.uuid4().hex, "root": str(root),
              "outdir": str(outdir), "state_dir": str(state), "tool": args.tool, "top": args.top,
              "sources": sources, "source_identity": identity, "context": args.context, "verdict": "RUNNING", "started_at": time.time(),
              "runner_pid": args.runner_pid or os.getppid(),
              "runner_identity": process_identity(args.runner_pid or os.getppid()), "host": socket.gethostname(),
              "compile_only": args.compile_only, "artifact_paths": args.artifact}
    if getattr(args, "seeds", None) is not None:
        record["seeds"] = args.seeds.split()
        record["runtime_args"] = getattr(args, "runtime_args", "")
    if os.environ.get("RAT_EXPERIMENT_ID"):
        record["experiment_id"] = os.environ["RAT_EXPERIMENT_ID"]
    if not args.compile_only and (root / POINT_PLAN).is_file():
        record["point_fingerprints"] = planned_fingerprints(root)
    target = state / "verify-runs" / (record["run_id"] + ".json")
    atomic_json(target, record)
    return target


def finish(args) -> int:
    target = Path(args.snapshot)
    record = json.loads(target.read_text())
    log = Path(args.log)
    text = log.read_text(errors="replace") if log.is_file() else ""
    runtime_log=Path(args.runtime_log) if args.runtime_log else None
    runtime_text=runtime_log.read_text(errors="replace") if runtime_log and runtime_log.is_file() else "" if runtime_log else text
    verdict = classify(args.exit_code, runtime_text, getattr(args, "pass_pattern", PASS_PATTERN))
    all_logs=classify(args.exit_code,text,check_points=False)
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
    record["sources_fresh"]=unchanged(record["sources"], record.get("source_identity"))
    if not record["sources_fresh"] and verdict in ("PASS","COMPILED"):
        verdict = "INCONCLUSIVE"
    # Wrapped runners (eda_runner.py verify-run) name a binding they could not establish.
    unbound = getattr(args, "unbound", "")
    if unbound:
        record["unbound_reason"] = unbound
        if verdict in ("PASS", "COMPILED"):
            verdict = "INCONCLUSIVE"
    record.update(getattr(args, "extra", None) or {})
    record.update(verdict=verdict, completed_at=time.time(), exit_code=args.exit_code,
                  log=str(log.resolve()), log_sha256=digest(log) if log.is_file() else None)
    failed_seeds = getattr(args, "failed_seeds", "").split()
    if failed_seeds and set(failed_seeds) <= set(record.get("seeds", [])):
        record["failed_seeds"] = failed_seeds
    if runtime_log:
        record["runtime_log"]={"path":str(runtime_log.resolve()),"sha256":digest(runtime_log) if runtime_log.is_file() else None}
    record["check_points_classified"] = True
    if args.seed_log:
        try:
            expected = record["runtime_log"]["sha256"] if runtime_log else record["log_sha256"]
            record["seed_log_sizes"] = seed_log_sizes(args.seed_log, expected)
        except (OSError, ValueError) as exc:
            record["seed_log_error"] = str(exc)
            print(f"[run_sim] {exc}", file=sys.stderr)
            if verdict in ("PASS", "COMPILED"):
                record["verdict"] = verdict = "INCONCLUSIVE"
    atomic_json(target, record)
    if verdict in ("PASS", "COMPILED"):
        atomic_json(Path(record["outdir"]) / ".rat-build.json", record)
    index = Path(record["state_dir"]) / "verify-evidence.json"
    lock = index.with_suffix(".lock")
    descriptor = os.open(lock, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        data: dict = json.loads(index.read_text()) if index.is_file() else {"schema_version": 1, "runs": []}
        data["runs"].append(record)
        atomic_json(index, data)
    print(f"[{getattr(args, 'label', 'run_sim')}] verdict={verdict}; evidence={target}")
    return args.exit_code if args.exit_code else (0 if verdict in ("PASS", "COMPILED") else 3)


def tracked_paths(root: Path, lines) -> set[str]:
    # A deleted or renamed file has no behavior left to verify; legacy entries that
    # were parsed from command text name no file at all.
    paths = {(root / line.strip()).resolve() for line in lines if line.strip()}
    results = (root / "experiment").resolve()  # run results, also in tracking files written before this rule
    return {str(path) for path in paths if path.is_file() and not path.is_relative_to(results)}


def tracked_files(root: Path, track: Path) -> set[str]:
    return tracked_paths(root, track.read_text().splitlines())


def logged_verdict(record: dict) -> str:
    """A PASS needs intact logs; a recorded failure survives log rotation."""
    if record["verdict"] != "PASS":
        return record["verdict"]
    log = Path(record["log"])
    if not log.is_file() or digest(log) != record["log_sha256"]:
        return "INVALID"
    runtime = record.get("runtime_log")
    if runtime:
        log = Path(runtime["path"])
        if not log.is_file() or digest(log) != runtime["sha256"]:
            return "INVALID"
    if record.get("check_points_classified") is not True:
        with log.open(encoding="utf-8", errors="replace") as stream:
            if log_has_failed_point(stream):
                return "FAIL"
    return "PASS"


def has_implicit_top(record: dict) -> bool:
    """Identify old run_sim records that compiled without selecting the stated top."""
    tool, top, context = (record.get(field, "") for field in ("tool", "top", "context"))
    flag = {"iverilog": "-s", "vcs": "-top"}.get(tool)
    return bool(flag and context.startswith(tool + "|") and not context.endswith(f"|{flag} {top}"))


def assess_records(tracked: set[str], records: list) -> tuple[set[str], list, list]:
    """Clear current files with an intact PASS and no unresolved failed case."""
    remaining = set(tracked)
    used = []
    passed_at: dict[tuple, float] = {}
    failed = []
    unresolved = []
    for record in records if isinstance(records, list) else ():
        try:
            sources = record["sources"]
            hit = tracked.intersection(sources)
            if not hit or record.get("compile_only") or has_implicit_top(record):
                continue
            if not unchanged(sources, record.get("source_identity")):
                continue
            verdict = logged_verdict(record)
            if verdict not in ("PASS", "FAIL", "TIMEOUT", "STALL", "HANG", "INCONCLUSIVE"):
                continue
            case = (record.get("tool"), record.get("top"), record.get("context"),
                    record.get("runtime_args", ""), tuple(sorted(sources)),
                    tuple(record.get("argv", [])), record.get("remote_host"), record.get("remote_root"))
            seeds = record.get("seeds") or [None]
            if verdict == "PASS":
                for seed in seeds:
                    key = (case, seed)
                    passed_at[key] = max(passed_at.get(key, 0), record.get("started_at", 0))
                if remaining & hit:
                    used.append((record, remaining & hit))
                    remaining -= hit
            else:
                for seed in record.get("failed_seeds") or seeds:
                    # Older bundled records omitted seed identity, so a new passing seed
                    # cannot certify the old failing seed. verify-run already stored argv.
                    known = "seeds" in record or record.get("origin") == "verify-run"
                    failed.append(((case, seed), record, hit, known))
        except (AttributeError, OSError, ValueError, KeyError, TypeError):
            continue
    for key, record, hit, known in failed:
        # An overlapping PASS that started before the failure finished is not a rerun.
        finished = record.get("completed_at")
        if known and isinstance(finished, (int, float)) and passed_at.get(key, -1) >= finished:
            continue
        remaining.update(hit)
        unresolved.append((record, key[1]))
    return remaining, used, unresolved


def clearing(root: Path, tracked: set[str], index: Path, failures=None) -> tuple[set[str], list]:
    try:
        records = json.loads(index.read_text())["runs"]
    except (OSError, ValueError, KeyError, TypeError):
        records = []
    remaining, used, unresolved = assess_records(tracked, records)
    if failures is not None:
        failures.extend(unresolved)
    return remaining, used


def failed_case_labels(failures) -> str:
    labels = []
    for record, seed in failures:
        case = record.get("top") or " ".join(record.get("argv", [])) or record.get("tool", "simulation")
        if seed is not None:
            case += f" seed {seed}"
        elif "seeds" not in record and record.get("origin") != "verify-run":
            case += " (legacy run with unknown seed)"
        if record.get("runtime_args"):
            case += " " + record["runtime_args"]
        labels.append(case)
    return ", ".join(dict.fromkeys(labels))[:400]


def unverified(args) -> int:
    root = Path(args.root).resolve()
    remaining, _ = clearing(root, tracked_files(root, Path(args.track)), Path(args.track).parent / "verify-evidence.json")
    for path in sorted(remaining):
        candidate = Path(path)
        print(candidate.relative_to(root) if candidate.is_relative_to(root) else candidate)
    return bool(remaining)


def running_cover(root: Path, tracked: set[str], runs: Path) -> bool:
    """True when live runs on this host, over unchanged inputs, cover every tracked file."""
    covered = set()
    for path in runs.glob("*.json"):
        try:
            record = json.loads(path.read_text())
            if (record["verdict"] != "RUNNING" or record.get("compile_only")
                    or record.get("host") != socket.gethostname()
                    or not record.get("runner_identity")
                    or process_identity(record["runner_pid"]) != record["runner_identity"]
                    or not unchanged(record["sources"], record.get("source_identity"))):
                continue
            os.kill(record["runner_pid"], 0)
            covered.update(record["sources"])
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return bool(tracked) and tracked <= covered


def pending_run(args) -> int:
    root = Path(args.root).resolve()
    track = Path(args.track)
    return 0 if running_cover(root, tracked_files(root, track), track.parent / "verify-runs") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("begin")
    for name in ("root", "outdir", "tool", "top"):
        start.add_argument("--" + name, required=True)
    start.add_argument("--context", default="")
    start.add_argument("--seeds", default="")
    start.add_argument("--runtime-args", default="")
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
    end.add_argument("--seed-log", action="append", default=[])
    end.add_argument("--failed-seeds", default="")
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
    listing.add_argument("--relocate-filelist")
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
