#!/usr/bin/env python3
# rat-version: 1.0.0-pre19
"""Execute configured EDA commands with bounded time and explicit transport results."""

from __future__ import annotations

import argparse
import base64
from contextlib import ExitStack
import fcntl
import functools
import json
import os
from pathlib import Path
import re
import select
import selectors
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid

from verify_evidence import (atomic_json, classify, digest, unchanged, pre_init_state_root, process_identity,
                             runtime_state_root, source_paths, state_within_bounds)


def configuration(root: Path) -> dict:
    from eda_setup import read_json, user_configuration

    helpers = os.environ.get("RAT_RUNTIME_HELPERS")
    if os.environ.get("RAT_REMOTE_ACTIVE") == "1" and helpers:
        return read_json(Path(helpers) / "dispatch-config.json")
    path = root / "rat_config.json"
    return read_json(path) if path.is_file() else user_configuration(root)


def backend(config: dict) -> str:
    if os.environ.get("RAT_EXECUTION_LOCAL") == "1":
        return "local"
    value = config.get("execution", {}).get("backend", "auto")
    if value not in ("auto", "local", "docker", "ssh", "lsf"):
        raise ValueError(f"unknown execution backend: {value}")
    return value


def tool_configuration(config: dict, tool: str, category_override: str | None = None) -> tuple[str, dict]:
    name = Path(tool).name
    aliases = {"verible-verilog-lint": "verible", "vc_static_shell": "vc_cdc", "qverify": "questa_cdc",
               "vvp": "iverilog", "vlog": "vsim", "vopt": "vsim", "vlib": "vsim"}
    key = aliases.get(name, name)
    categories = config.get("tools", {})
    category = category_override if category_override is not None else os.environ.get("RAT_TOOL_CATEGORY")
    entries = [categories.get(category, {})] if category else [v for v in categories.values() if isinstance(v, dict)]
    for group in entries:
        entry = group.get(key)
        if isinstance(entry, dict):
            resolved = os.environ.get(re.sub(r"[^A-Z0-9_]", "_", key.upper())) or entry.get("path") or tool
            if key != name and key in ("iverilog", "vsim") and entry.get("path"):
                resolved = str(Path(resolved).with_name(name))
            return resolved, entry
    return tool, {}


def execute(argv: list[str], root: Path, log: Path, timeout: float, stall: float = 0,
            cwd: Path | None = None, env: dict | None = None) -> int:
    if timeout <= 0 or stall < 0:
        raise ValueError("timeout must be positive; stall timeout must be nonnegative")
    log.parent.mkdir(parents=True, exist_ok=True)
    started = last_output = time.monotonic()
    termination = "exit"
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    class Interrupted(Exception):
        def __init__(self, number): self.number=number
    def interrupt(number, frame): raise Interrupted(number)
    handlers={number:signal.signal(number,interrupt) for number in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP)}
    interrupted=0
    # On the execution host stdout is the SSH channel: once it closes, nobody waits for
    # this run, so stop the tool instead of leaving it running without a limit.
    remote = os.environ.get("RAT_REMOTE_ACTIVE") == "1"
    console, watch = sys.stdout.buffer, None
    if remote:
        try:
            watch = select.poll()
            watch.register(console.fileno(), select.POLLOUT)
        except (AttributeError, OSError, ValueError):
            watch = None

    def echo(data):
        nonlocal console
        if console is None:
            return
        try:
            console.write(data)
            console.flush()
        except (BrokenPipeError, OSError):
            console = None  # a local reader such as `| head` left; keep running and logging
            quiet = os.open(os.devnull, os.O_WRONLY)  # so the exit flush of buffered output cannot fail
            os.dup2(quiet, sys.stdout.fileno())
            os.close(quiet)
            if remote:
                raise Interrupted(signal.SIGHUP)
    try:
        with log.open("wb") as stream:
            # Some license launchers close their output before they start waiting.
            while selector.get_map() or process.poll() is None:
                now = time.monotonic()
                reason = "TIMEOUT" if now - started >= timeout else "STALL" if stall and now - last_output >= stall else ""
                if reason and termination == "exit":
                    termination = reason
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except (ProcessLookupError, PermissionError):  # macOS: EPERM once only the zombie leader is left
                        pass
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        pass
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass
                    marker = f"\nRAT_{reason}: execution limit reached\n".encode()
                    stream.write(marker)
                    echo(marker)
                    break
                if watch and any(event & (select.POLLERR | select.POLLHUP) for _, event in watch.poll(0)):
                    raise Interrupted(signal.SIGHUP)
                if not selector.get_map():
                    time.sleep(0.05)
                    continue
                for key, _ in selector.select(timeout=0.05):
                    data = os.read(key.fd, 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    stream.write(data)
                    echo(data)
                    last_output = time.monotonic()
    except Interrupted as event:
        interrupted=event.number
        termination="DISCONNECTED" if event.number == signal.SIGHUP else "INTERRUPTED"
        try: os.killpg(process.pid,signal.SIGTERM)
        except (ProcessLookupError, PermissionError): pass
        try: process.wait(timeout=1)
        except subprocess.TimeoutExpired: pass
        try: os.killpg(process.pid,signal.SIGKILL)
        except (ProcessLookupError, PermissionError): pass
    finally:
        for number,handler in handlers.items(): signal.signal(number,handler)
    selector.close()
    process.stdout.close()
    status = process.wait()
    if interrupted:
        status = 128 + interrupted
    elif termination == "TIMEOUT":
        status = 124
    elif termination == "STALL":
        status = 125
    elif status < 0:
        status = 128 - status
    atomic_json(log.with_suffix(log.suffix + ".result.json"), {
        "schema_version": 1, "argv": argv, "host": socket.gethostname(),
        "project_root": str(root), "exit_code": status, "termination": termination,
        "elapsed_seconds": time.monotonic() - started, "log": str(log),
    })
    return status


# 124: execute() hit its time limit. 255: ssh lost the connection. 129/130/143: this
# process got SIGHUP/SIGINT/SIGTERM. bsub -K runs in its own session, so a hangup
# of the terminal is 129 here and never ssh's 255. The batch job is still running.
LSF_WAITER_LOST = (124, 255, 129, 130, 143)


def cancel_lsf_job(ssh: list[str], job_name: str) -> None:
    """Stop a job whose waiter did not come back. A failed cancel must not hide the status file."""
    try:
        cancelled = subprocess.run([*ssh, "bkill -J " + shlex.quote(job_name)],
                                   timeout=15, capture_output=True, text=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"WARNING: could not cancel LSF job {job_name}: {exc}", file=sys.stderr)
        return
    if cancelled.returncode:
        detail = (cancelled.stderr or cancelled.stdout or "").strip()
        print(f"WARNING: bkill -J {job_name} exited {cancelled.returncode}"
              + (f": {detail}" if detail else ""), file=sys.stderr)


def available(args, config: dict) -> int:
    resolved, entry = tool_configuration(config, args.tool, getattr(args, "category", None))
    if backend(config) in ("ssh", "lsf"):
        from eda_setup import failed_probe
        return 0 if entry.get("detected") and not failed_probe(entry) else 1
    source = entry.get("env_source", "")
    container = backend(config) == "docker"
    if container and not source:
        argv = ["sh", "-c", 'command -v -- "$1"', "rat-probe", resolved]
    elif source:
        shell = entry.get("env_shell", "bash")
        if shell in ("csh", "tcsh"):
            argv = [shell, "-f", "-c", source + "\nif ($status != 0) exit $status\nwhich $argv:q", resolved]
        elif shell == "bash":
            argv = ["bash", "-c", source + '\nstatus=$?; [ "$status" -eq 0 ] || exit "$status"\ncommand -v -- "$1"', "rat-probe", resolved]
        else:
            raise ValueError(f"unsupported environment shell: {shell}")
    if source or container:
        if container:
            image=config.get("execution",{}).get("docker_image", "rtl-eda-tools")
            argv=["docker","run","--rm","--user",f"{os.getuid()}:{os.getgid()}","--env","HOME=/tmp",image,*argv]
        try:
            return subprocess.run(argv, capture_output=True, timeout=10).returncode
        except (OSError, subprocess.TimeoutExpired):
            return 1
    return 0 if (Path(resolved).is_file() and os.access(resolved, os.X_OK) if "/" in resolved else shutil.which(resolved)) else 1


def config_value(config: dict, key: str):
    value = config
    for part in key.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def verdict(args, config: dict) -> int:
    log = Path(args.log)
    text = log.read_text(errors="replace") if log.is_file() else ""
    value = classify(args.exit_code, text)
    counts = []
    if args.purpose == "goals" and value not in ("FAIL", "TIMEOUT", "STALL", "HANG"):
        counts = [int(number) for number in re.findall(
            r"(?im)^\s*(?:Total\s+)?(?:Errors?|Violations?|Fatals?)\s*[:=]\s*(\d+)\s*$", text)]
        custom = config.get("execution", {}).get("verdicts", {}).get(args.tool, {})
        if any(counts) or (custom.get("failure_pattern") and re.search(custom["failure_pattern"], text)):
            value = "FAIL"
        elif args.completion in text and (counts or (custom.get("success_pattern") and re.search(custom["success_pattern"], text))):
            value = "PASS"
        else:
            value = "INCONCLUSIVE"
    atomic_json(log.with_suffix(log.suffix + ".verdict.json"), {
        "schema_version": 1, "verdict": value, "tool": args.tool, "exit_code": args.exit_code,
        "log": str(log), "log_sha256": digest(log) if log.is_file() else None, "goal_counts": counts,
    })
    print(f"[EDA verdict] {args.tool}: {value}")
    return args.exit_code or (0 if value == "PASS" else 3 if value == "INCONCLUSIVE" else 1)


def capabilities(args, config: dict) -> int:
    phase = args.phase.lower()
    aliases = {"1": "p1", "2": "p2", "3": "p3", "4": "p4", "5": "p5", "research": "p1", "silicon": "p5b"}
    phase = aliases.get(phase, phase)
    if phase not in ("p1", "p2", "p3", "p4", "p5", "p5a", "p5b", "all"):
        raise ValueError(f"unknown readiness phase: {phase}")
    missing = []
    found = {}
    remote = backend(config) in ("ssh", "lsf")
    measured = None
    if remote and not getattr(args, "probe_remote", False):
        print(json.dumps({"ready": False, "scope": "remote_unprobed", "phase": phase,
                          "missing": ["remote tool readiness has not been measured"]}))
        return 1
    if remote:
        from eda_setup import discover, validate_host
        validate_host(config.get("execution", {}).get("host", ""))
        measured = discover(config.get("execution", {}).get("host", ""), config)

    def need(label, names, category="build", preference=None):
        selected = config.get("preferences", {}).get(preference) if preference else None
        if selected:
            aliases = {"spyglass": "sg_shell", "verible": "verible-verilog-lint", "vc_cdc": "vc_static_shell", "questa_cdc": "qverify"}
            names = [aliases.get(selected, selected)]
        for name in names:
            from eda_setup import failed_probe
            _, entry = tool_configuration(config, name, category if category != "build" else None)
            if failed_probe(entry):
                continue
            if measured:
                from eda_setup import TOOLS
                group = measured["tools"].get(category, {})
                ready = any(entry["detected"] for key, entry in group.items() if TOOLS[category].get(key) == name)
            else:
                probe = argparse.Namespace(tool=name, category=category if category != "build" else "")
                ready = available(probe, config) == 0
            if ready:
                found[label] = name
                return name
        missing.append(label)
        return None

    def probe_in_runtime(cmd: list[str]) -> bool:
        if backend(config) == "docker":
            image = config.get("execution", {}).get("docker_image", os.environ.get("RTL_EDA_IMAGE", "rtl-eda-tools"))
            argv = ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "--env", "HOME=/tmp", image, *cmd]
        else:
            argv = cmd
        try:
            return subprocess.run(argv, capture_output=True, timeout=15).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    if remote and backend(config) == "lsf":
        need("LSF scheduler", ["bsub"])
    if phase not in ("p1", "1", "research"):
        need("build system", ["make"])
    if phase in ("p2", "p3", "all"):
        need("C/C++ compiler", ["gcc", "clang", "cc", "g++"])
    if args.bfm:
        has_systemc = measured["systemc"] if measured else (
            probe_in_runtime(["pkg-config", "--exists", "systemc"])
            if backend(config) == "docker" or shutil.which("pkg-config") else False
        )
        if not has_systemc:
            missing.append("SystemC for the requested TLM BFM")
    if phase in ("p4", "p5", "p5a", "all"):
        simulator = need("simulator", ["vcs", "xrun", "vsim", "verilator", "iverilog"], "simulators", "simulator")
        need("linter", ["verilator", "verible-verilog-lint", "slang", "sg_shell"], "lint", "lint")
        if simulator == "verilator":
            need("C++ compiler for Verilator", ["g++", "clang++"])
        framework = args.framework
        if framework == "cocotb" or (framework == "auto" and simulator in ("iverilog", "verilator")):
            has_cocotb = measured["cocotb"] if measured else probe_in_runtime(
                ["python3" if backend(config) == "docker" else sys.executable, "-c", "import cocotb"]
            )
            if not has_cocotb:
                missing.append("cocotb for functional verification")
    if phase in ("p5b", "all"):
        need("synthesis", ["dc_shell", "genus", "yosys", "vivado"], "synthesis", "synthesis")
    if args.multiclock:
        need("CDC analysis", ["svlens", "sg_shell", "vc_static_shell", "qverify"], "cdc", "cdc")
    if args.signoff:
        need("static timing analysis", ["pt_shell"], "sta")
        library = config.get("technology", {}).get("db")
        if not library or (measured and not measured["libraries"].get(library)):
            missing.append("technology.db for timing signoff")
    print(json.dumps({"ready": not missing, "scope": backend(config) if remote or backend(config)=="docker" else "local", "phase": phase,
                      "capabilities": found, "missing": missing, "python": measured["python"] if measured else sys.executable,
                      "evidence_level": "executable_paths", "license_checked": False}))
    return 1 if missing else 0


def run(args, root: Path, config: dict) -> int:
    settings = config.get("execution", {})
    selected = backend(config)
    if selected in ("ssh", "lsf"):
        raise ValueError("remote execution requires dispatching the whole wrapper")
    if args.shell_command:
        first, _, rest = args.shell_command.partition(" ")
        tool = first
    else:
        if not args.argv:
            raise ValueError("missing tool command")
        tool, *rest_args = args.argv
    resolved, entry = tool_configuration(config, tool)
    context = os.environ.get("RAT_CONTEXT_TOOL")
    shims = None
    if context:
        context = {"icarus": "iverilog", "questa": "vsim", "xcelium": "xrun", "spyglass": "sg_shell", "vc_cdc": "vc_static_shell", "questa_cdc": "qverify"}.get(context, context)
        _, entry = tool_configuration(config, context)
        shim_parent = runtime_state_root(root) / "tool-shims"
        shim_parent.mkdir(parents=True, exist_ok=True)
        shims = tempfile.TemporaryDirectory(prefix="run-", dir=shim_parent)
        names = [context, "vvp"] if context == "iverilog" else ["vsim", "vlog", "vopt", "vlib"] if context == "vsim" else [context]
        for name in names:
            target, _ = tool_configuration(config, name)
            target = str(Path(target).resolve()) if "/" in target else shutil.which(target)
            if target and Path(target).is_file():
                (Path(shims.name) / name).symlink_to(target)
    wait_args = entry.get("license_wait_args", [])
    if context:
        wait_args = []
    if not isinstance(wait_args, list) or not all(isinstance(arg, str) for arg in wait_args):
        raise ValueError("license_wait_args must be an explicit argument list")
    if args.shell_command:
        command = " ".join([shlex.quote(resolved), *(shlex.quote(arg) for arg in wait_args), rest])
        argv = ["bash", "-e", "-o", "pipefail", "-c", command]
    else:
        argv = [resolved, *wait_args, *rest_args]
    env = {**os.environ, "RAT_PROJECT_ROOT": str(root)}
    if shims:
        env["PATH"] = shims.name + os.pathsep + env["PATH"]
    source = entry.get("env_source", "")
    if source:
        shell = entry.get("env_shell", "bash")
        if shell in ("csh", "tcsh"):
            prefix = "\nsetenv PATH " + shlex.quote(shims.name) + ':"$PATH"' if shims else ""
            argv = [shell, "-f", "-c", source + "\nif ($status != 0) exit $status" + prefix + "\nexec $argv:q", *argv]
        elif shell == "bash":
            prefix = "\nexport PATH=" + shlex.quote(shims.name) + ':"$PATH"' if shims else ""
            argv = ["bash", "-c", source + '\nstatus=$?; [ "$status" -eq 0 ] || exit "$status"' + prefix + '\nexec "$@"', "rat-env", *argv]
        else:
            raise ValueError(f"unsupported environment shell: {shell}")
    missing = not (Path(resolved).is_file() if "/" in resolved else shutil.which(resolved))
    if selected == "docker" or (selected == "auto" and missing and not source):
        cwd = Path.cwd().resolve()
        if not cwd.is_relative_to(root):
            raise ValueError("Docker working directory must be inside the project")
        image = settings.get("docker_image", os.environ.get("RTL_EDA_IMAGE", "rtl-eda-tools"))
        mounts=["--mount",f"type=bind,src={root},dst={root}"]
        helpers=Path(__file__).resolve().parent
        if not helpers.is_relative_to(root): mounts += ["--mount",f"type=bind,src={helpers},dst={helpers},readonly"]
        if shims and not Path(shims.name).is_relative_to(root):  # pre-init shims live in the plugin data folder
            mounts += ["--mount", f"type=bind,src={shims.name},dst={shims.name},readonly"]
        # Preserve the container's own PATH (e.g. /opt/oss-cad-suite/bin); only prepend shims when needed.
        container_argv = (["sh", "-c", 'export PATH="$1:$PATH"; shift; exec "$@"', "rat-docker", shims.name, *argv]
                          if shims else argv)
        argv = ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "--env", "HOME=/tmp",
                "--env", f"RAT_PROJECT_ROOT={root}", "--env", "RAT_EXECUTION_LOCAL=1",
                *mounts, "--workdir", str(cwd), image, *container_argv]
    stamp = uuid.uuid4().hex
    log = Path(args.log) if args.log else runtime_state_root(root) / "tool-runs" / (stamp + ".log")
    timeout = args.timeout if args.timeout is not None else float(os.environ.get("RAT_TOOL_TIMEOUT_SECONDS", settings.get("timeout_seconds", 1800)))
    stall = args.stall if args.stall is not None else float(settings.get("stall_seconds", 0))
    try:
        return execute(argv, root, log, timeout, stall, env=env)
    finally:
        if shims:
            shims.cleanup()


def relative_output(value: str) -> str:
    """A project-relative output in normal form: "sim/out/" is sim/out; "./", "./." and "" name the root."""
    path = Path(value)
    # Normal form matters: openrsync fetches from the output's parent, so "sim/out/" would land in sim/,
    # and a root value would sync the whole workspace (with --delete) onto the project.
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError(f"remote output must be project-relative: {value}")
    if path.parts[0] in RESERVED_OUTPUTS:
        raise ValueError(f"reserved remote output: {value}")
    return path.as_posix()


# Regenerable outputs too large to bring back by default; `fetch` pulls them on request.
HEAVY_RESULTS = ("*.fsdb", "*.vcd", "*.evcd", "*.vpd", "*.wlf", "*.trn", "*.dsn", "*.shm/", "xcelium.d/",
                 "INCA_libs/", "csrc/", "*.daidir/", "obj_dir/", "xlib/", "*.o", "*.so", "*.a")
RESULT_MODES = ("experiment", "merge", "sync")
BUNDLED_WRAPPERS = ("run_sim.sh", "run_syn.sh", "run_lint.sh", "run_cdc.sh", "run_formality.sh",
                    "run_conformal.sh", "run_regression.sh", "run_regression_uvm.sh")
NEVER_SENT = ("experiment/", ".rat/", ".rtl-agent-team/", ".git/", ".claude/")
RESERVED_OUTPUTS = (".git", ".claude", ".rat", ".rtl-agent-team")  # never fetched over the project


def upload_manifest(root: Path, inputs, patterns) -> list[str] | None:
    """Project-relative files to send: Git-visible files, filelist inputs and execution.inputs.

    None when the root is not a Git work tree; the caller then mirrors the folder.
    """
    listing = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
                             capture_output=True)
    if listing.returncode != 0:
        return None
    names = set()
    for name in listing.stdout.decode(errors="surrogateescape").split("\0"):
        path = root / name
        if not name or not (path.exists() or path.is_symlink()):
            continue  # index entries deleted from the work tree
        if path.is_dir() and not path.is_symlink():  # submodule
            names.update(name + "/" + inner for inner in upload_manifest(path, (), ()) or ())
        else:
            names.add(name)
    files = [Path(path) for path in inputs]
    if not isinstance(patterns, list):
        raise ValueError("execution.inputs must be a list of project-relative patterns")
    for pattern in patterns:
        if not isinstance(pattern, str) or not pattern or Path(pattern).is_absolute() or ".." in Path(pattern).parts:
            raise ValueError(f"execution.inputs must be project-relative patterns: {pattern!r}")
        for match in root.glob(pattern):
            files += [match] if match.is_file() else [path for path in match.rglob("*") if path.is_file()]
    for path in files:
        # Ship only data inside the project, even when a link points elsewhere.
        if path.is_file() and path.resolve().is_relative_to(root) and path.absolute().is_relative_to(root):
            names.add(str(path.absolute().relative_to(root)))
    return sorted(name for name in names if not name.startswith(NEVER_SENT) and name != ".git")


def prune_sent(workspace: Path, listing: Path) -> list[str]:
    """On the host: delete files an earlier dispatch sent that this one no longer sends.

    Only paths named in the previous send list are candidates, so build outputs stay.
    """
    record = workspace / ".rat/sent.list"

    def names(path):
        return {name for name in path.read_bytes().decode(errors="surrogateescape").split("\0") if name} if path.is_file() else set()

    base, removed = workspace.resolve(), []
    for name in sorted(names(record) - names(listing)):
        relative = Path(name)
        target = workspace / relative
        if relative.is_absolute() or ".." in relative.parts or not target.parent.resolve().is_relative_to(base):
            continue  # never follow a path or a linked folder out of the workspace
        if target.is_symlink() or target.is_file():
            target.unlink()
            removed.append(name)
    record.parent.mkdir(parents=True, exist_ok=True)
    pending = record.with_name("sent.list.tmp")
    shutil.copyfile(listing, pending)
    os.replace(pending, record)  # the new list is written last
    return removed


def install_generated_ignore(directory: Path, patterns: str) -> None:
    if directory.resolve() != directory:
        raise ValueError(f"generated directory cannot be symlinked: {directory}")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    ignore = directory / ".gitignore"
    # Link a complete ignore file atomically so simultaneous starters cannot see a partial file.
    if not ignore.exists():
        with tempfile.NamedTemporaryFile(dir=directory) as pending:
            pending.write(patterns.encode())
            pending.flush()
            try:
                os.link(pending.name, ignore)
            except FileExistsError:
                pass
    if ignore.is_symlink() or not ignore.is_file():
        raise ValueError(f"generated directory needs a regular .gitignore: {ignore}")


def experiment_directory(root: Path) -> Path:
    name = os.environ.get("RAT_EXPERIMENT_ID", "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name):
        raise ValueError("RAT_EXPERIMENT_ID must be 1–64 letters, digits, dots, dashes or underscores, starting with a letter or digit")
    directory = root / "experiment" / name
    install_generated_ignore(directory, "*\n")
    # Gates share the project evidence index. Keep those generated files out of Git too.
    if pre_init_state_root(root) is None:  # records outside the project need no ignore rule
        install_generated_ignore(runtime_state_root(root), "/.gitignore\n/audit/\n/tool-runs/\n/tool-shims/\n/source-probes/\n"
                                     "/state/verify-runs/\n/state/verify-evidence.json\n/state/verify-evidence.lock\n")
    return directory


def experiment_output(directory: Path, value: str) -> Path:
    path = Path(value)
    if not value or ".." in path.parts:
        raise ValueError(f"invalid experiment output: {value}")
    if not path.is_absolute():
        path = (directory.parent.parent if path.parts[:1] == ("experiment",) else directory) / path
    if not path.is_relative_to(directory) or path.resolve() != path:
        raise ValueError(f"output must stay inside {directory}: {value}")
    if path.relative_to(directory).parts[:1] in ((".git",), (".gitignore",), (".rat",)):
        raise ValueError(f"reserved experiment output: {value}")
    return path


def remote_shell_command(script: str) -> str:
    # tcsh cannot parse literal newlines in the outer SSH command's quotes.
    payload = base64.b64encode(script.encode()).decode()
    return "sh -c " + shlex.quote('payload=$(printf %s ' + payload + ' | base64 -d) || exit 2; eval "$payload"')


@functools.lru_cache(maxsize=None)
def rsync_features(rsync: str | None) -> tuple[bool, bool]:
    """(--protect-args, the /./ marker of --relative), probed once per rsync binary. GNU rsync 3 has
    both; GNU rsync 2.6.9 lacks --protect-args; macOS openrsync lacks both. An rsync that does not
    answer --version keeps the GNU argv."""
    if not rsync:
        return True, True
    try:
        version = subprocess.run([rsync, "--version"], capture_output=True, text=True, timeout=15)
        if version.returncode:
            return True, True
        protect = subprocess.run([rsync, "--protect-args", "--version"], capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return True, True
    return protect.returncode == 0, "openrsync" not in version.stdout


def rsync_transport(ssh_options: list[str], *options: str):
    """rsync argv prefix, and a host:path builder that keeps a remote path one argument.
    Without --protect-args the remote login shell splits the path, so it is quoted for that shell."""
    protected = rsync_features(shutil.which("rsync"))[0]
    argv = ["rsync", "-a", *(["--protect-args"] if protected else []), *options, "-e", shlex.join(["ssh", *ssh_options])]
    return argv, lambda host, path: host + ":" + (path if protected else shlex.quote(path))


def rsync_relative(remote_root: str, value: str, destination: Path):
    """Options, remote source, local target and transfer-root prefix that copy remote_root/value to
    destination/value. openrsync ignores the /./ marker, so there the transfer starts at the parent
    of value, and anchored filter rules drop that prefix."""
    if rsync_features(shutil.which("rsync"))[1]:
        return ["--relative"], remote_root + "/./" + value, destination, ""
    parent = Path(value).parent
    return [], remote_root + "/" + value, destination / parent, "" if parent == Path(".") else parent.as_posix() + "/"


def make_target(target: Path) -> list[Path]:
    """Create a fetch target; returns the folders this call created, deepest last."""
    created = []
    for folder in (*reversed(target.parents), target):
        if folder.is_dir():
            continue
        try:
            folder.mkdir()  # one level at a time: a folder another process made is not ours
        except FileExistsError:
            continue
        created.append(folder)
    return created


def remove_if_empty(created: list[Path]) -> None:
    """A failed fetch leaves no empty folders it made itself."""
    for folder in reversed(created):
        try:
            folder.rmdir()
        except OSError:
            break  # not empty: the transfer put something there


def import_remote_evidence(path: Path, root: Path, workspace: str, since: float,
                           experiment: Path | None = None, remote_outputs: str | None = None) -> int:
    data = json.loads(path.read_text())
    records = []
    state = runtime_state_root(root) / "state" if experiment else (pre_init_state_root(root) or root / ".rat") / "state"

    def local_path(value, destination, source=workspace):
        if value == source:
            return str(destination)
        prefix = source.rstrip("/") + "/"
        if not value.startswith(prefix) or ".." in Path(value).parts:
            raise ValueError(f"remote artifact is outside synchronized workspace: {value}")
        return str(destination / value[len(prefix):])

    for remote_record in data.get("runs", []):
        if remote_record.get("started_at", 0) < since:
            continue
        record = dict(remote_record)
        generated = experiment or root
        for field in ("sources", "source_identity"):
            if field in record:
                record[field] = {local_path(key, root): value for key, value in record[field].items()}
        output_root = remote_outputs or workspace
        record["log"] = local_path(record["log"], generated, output_root)
        if record.get("runtime_log"):
            record["runtime_log"] = dict(record["runtime_log"])
            record["runtime_log"]["path"] = local_path(record["runtime_log"]["path"], generated, output_root)
        record["outdir"] = local_path(record["outdir"], generated, output_root)
        if experiment:
            record["experiment_id"] = experiment.name
            record["artifacts"] = {local_path(key, generated, output_root): value for key, value in record.get("artifacts", {}).items()}
            record["artifact_paths"] = [local_path(key, generated, output_root) for key in record.get("artifact_paths", [])]
        record["root"] = str(root)
        record["state_dir"] = str(state)
        record["remote_workspace"] = workspace
        log = Path(record["log"])
        runtime_entry = record.get("runtime_log")
        runtime_ok = (not runtime_entry or (
            isinstance(runtime_entry, dict) and isinstance(runtime_entry.get("path"), str)
            and Path(runtime_entry["path"]).is_file()
            and digest(Path(runtime_entry["path"])) == runtime_entry.get("sha256")
        ))
        if record["verdict"] == "PASS" and (
            not unchanged(record["sources"], record.get("source_identity"))
            or not log.is_file() or digest(log) != record["log_sha256"] or not runtime_ok
        ):
            record["verdict"] = "INCONCLUSIVE"
        records.append(record)
    index = state / "verify-evidence.json"
    if not state_within_bounds(root, index.parent):
        raise ValueError("local evidence directory escapes project")
    index.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(index.with_suffix(".lock"), os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(descriptor, "w") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        current = json.loads(index.read_text()) if index.is_file() else {"schema_version": 1, "runs": []}
        known = {record["run_id"] for record in current["runs"]}
        current["runs"].extend(record for record in records if record["run_id"] not in known)
        atomic_json(index, current)
    return len(records)


def require_relative_filelists(root: Path, filelists: list[Path], variables: bool = True) -> None:
    """The execution host opens filelist entries itself, so they must name project-relative paths."""
    checked=set()
    while filelists:
        filelist=filelists.pop()
        if filelist in checked:continue
        checked.add(filelist)
        tokens=shlex.split(filelist.read_text(),comments=True)
        for index,token in enumerate(tokens):
            paths=token[8:].split("+") if token.startswith("+incdir+") else [token[2:]] if token.startswith("-I") else [token]
            if any(path.startswith("/") and not path.startswith("//") for path in paths):
                raise ValueError(f"remote filelists require project-relative inputs: {filelist}")
            if not variables and "$" in token:  # expanded here, but the host may expand it differently
                raise ValueError(f"remote filelists cannot use environment variables: {filelist}: {token}")
            if token in ("-f","-F") and index+1<len(tokens):
                nested=filelist.parent/tokens[index+1]
                if not nested.is_file(): nested=root/tokens[index+1]
                filelists.append(nested.resolve())


def require_project_root(root: Path) -> None:
    # Dispatch mirrors the whole root to the remote host, and without a project config
    # the root is just the current directory. Never mirror a home directory (keys, tokens).
    home = Path.home().resolve()
    if root == home or home.is_relative_to(root):
        raise ValueError("refusing to synchronize the home directory or a parent of it; run from the project root")
    if root.is_relative_to(home) and root.relative_to(home).parts[0].startswith("."):
        raise ValueError("refusing to synchronize a hidden directory under the home directory (~/.ssh, ~/.config, ...)")
    named = os.environ.get("RAT_PROJECT_ROOT")
    markers = ("rat_config.json", ".rat", ".rtl-agent-team", ".git")
    if not any((root / name).exists() for name in markers) and not (named and Path(named).resolve() == root):
        raise ValueError("remote execution mirrors the whole folder: run from a project root (a Git work tree or "
                         "a folder with rat_config.json) or name the folder with RAT_PROJECT_ROOT")


def dispatch(args, root: Path, config: dict) -> int:
    require_project_root(root)
    mode = config.get("execution", {}).get("results", "experiment")
    if mode not in RESULT_MODES:
        raise ValueError("execution.results must be experiment, merge or sync")
    if not os.environ.get("RAT_EXPERIMENT_ID") and mode == "experiment":
        # Results land only under experiment/<id>/, never over the project's sources.
        os.environ["RAT_EXPERIMENT_ID"] = time.strftime("run-%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    if os.environ.get("RAT_EXPERIMENT_ID"):
        print(f"Experiment ID: {os.environ['RAT_EXPERIMENT_ID']}", file=sys.stderr)
    with ExitStack() as cleanup:
        experiment = None
        if os.environ.get("RAT_EXPERIMENT_ID"):
            experiment = experiment_directory(root)
            fd = os.open(experiment, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            cleanup.callback(os.close, fd)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError(f"experiment already running: {experiment.name}") from exc
        return _dispatch_tracked(args, root, config, experiment, cleanup)


def _dispatch_tracked(args, root: Path, config: dict, experiment: Path | None, cleanup: ExitStack) -> int:
    snapshot=None
    filelist=""
    sources=[]
    named=False
    for index,token in enumerate(args.argv):
        if token in ("-f","--filelist") and index+1<len(args.argv): filelist,named=args.argv[index+1],True
        elif token.endswith((".sv",".v",".svh",".vh")) and (root/token).is_file(): sources.append(token)
    if not filelist:
        candidate=config.get("project",{}).get("filelist", "rtl/filelist_top.f")
        if candidate and (root/candidate).is_file(): filelist=candidate
    resolved=True
    try:
        inputs=source_paths(root,sources,filelist) if sources or filelist else []
    except (OSError,ValueError) as exc:
        # A bundled wrapper parses the same filelist on the host; fail here with the reason.
        # A project runner's -f may mean something else, so only warn for it.
        if named and Path(args.wrapper).name in BUNDLED_WRAPPERS and (root/filelist).is_file():
            raise ValueError(f"cannot resolve filelist {filelist}: {exc}") from exc
        print(f"WARNING: inputs of {filelist or 'the named sources'} were not resolved ({exc}); ignored files they "
              "name are not sent, and files left from earlier runs stay on the host", file=sys.stderr)
        inputs,resolved=[],False
    if inputs:
        run_id=uuid.uuid4().hex
        marker = runtime_state_root(root) if experiment else pre_init_state_root(root) or root / ".rat"
        snapshot=marker/"state/verify-runs"/(run_id+".json")
        record={"schema_version":1,"run_id":run_id,"root":str(root),"tool":"remote-wrapper",
                "sources":{str(path):digest(path) for path in inputs},"verdict":"RUNNING",
                "started_at":time.time(),"runner_pid":os.getpid(),"runner_identity":process_identity(os.getpid()),
                "host":socket.gethostname(),"compile_only":"--compile-only" in args.argv}
        atomic_json(snapshot,record)
    try:
        return _dispatch(args, root, config, experiment, cleanup, inputs, resolved)
    finally:
        if snapshot:
            record.update(verdict="TRANSPORT_COMPLETE",completed_at=time.time())
            atomic_json(snapshot,record)


def _dispatch(args, root: Path, config: dict, experiment: Path | None, cleanup: ExitStack, inputs=(),
              resolved=True) -> int:
    settings = config.get("execution", {})
    selected = backend(config)
    if selected not in ("ssh", "lsf"):
        raise ValueError("dispatch requires the ssh or lsf backend")
    host = settings.get("host", "")
    workspace = settings.get("workspace", "")
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@:-]*", host) or not Path(workspace).is_absolute():
        raise ValueError("remote execution requires a valid host and absolute workspace")
    if not workspace.strip("/") or any(char in workspace for char in ("\n", "\r", "\0")):
        raise ValueError("invalid remote workspace")
    # Validate only input lists, never generated absolute lists in old build outputs.
    filelists=[]
    for index,token in enumerate(args.argv):
        if token in ("-f","--filelist") and index+1<len(args.argv): filelists.append((root/args.argv[index+1]).resolve())
    if not filelists:
        default=root/config.get("project",{}).get("filelist", "rtl/filelist_top.f")
        if default.is_file(): filelists=[default]
    require_relative_filelists(root, filelists)
    run_id = uuid.uuid4().hex
    cache = (pre_init_state_root(root) or (experiment or root) / ".rat") / "remote-runs" / run_id
    if experiment and cache.resolve() != cache:
        raise ValueError("experiment transport directory cannot be symlinked")
    cache.mkdir(parents=True)
    started = time.monotonic()
    started_wall = time.time()
    limit = float(settings.get("timeout_seconds", 1800))
    ssh_options = settings.get("ssh_options", [])
    if not isinstance(ssh_options, list) or not all(isinstance(value, str) for value in ssh_options):
        raise ValueError("ssh_options must be an argument list")
    ssh = ["ssh", *ssh_options, "--", host]

    def step(argv, name):
        remaining = limit - (time.monotonic() - started)
        if remaining <= 0:
            return 124
        return execute(argv, root, cache / (name + ".log"), remaining)

    def remote(script, name):
        return step([*ssh, remote_shell_command(script)], name)

    if experiment:
        namespace = workspace.rstrip("/") + "/.rat/experiments/" + experiment.name
        workspace = namespace + "/work"
        reservation = shlex.quote(namespace + "/active")
        create = "umask 077; mkdir -p " + shlex.quote(workspace) + " && mkdir " + reservation
        may_release = True

        def release():
            if may_release:
                try:
                    code = subprocess.run([*ssh, "rmdir " + reservation], timeout=10, capture_output=True).returncode
                    if code == 0:
                        return
                except (OSError, subprocess.TimeoutExpired):
                    pass
            print(f"Experiment reservation retained at {namespace}/active; confirm the remote job ended before reusing this ID.",
                  file=sys.stderr)

        if remote(create, "reserve"):
            raise ValueError(f"could not reserve remote experiment {experiment.name}; check its active status")
        cleanup.callback(release)
    elif remote("mkdir -p " + shlex.quote(workspace), "mkdir"):
        return 2
    transport, remote_operand = rsync_transport(ssh_options)
    manifest = upload_manifest(root, inputs, settings.get("inputs", []))
    mode = settings.get("results", "experiment")
    if not experiment and manifest is None:
        raise ValueError(f"execution.results={mode} needs a Git work tree so that fetched results never "
                         "overwrite sources; use experiment or run inside a Git work tree")
    if manifest is None:  # not a Git work tree: mirror the folder
        print(f"Sending the whole folder to {host} (not a Git work tree; build outputs are copied too)", file=sys.stderr)
        sync = [*transport, "--exclude=.git", "--exclude=.claude", "--exclude=.rat/state",
                "--exclude=.rat/audit", "--exclude=.rat/remote-runs", "--exclude=/experiment/",
                "--exclude=/.rat/experiments/", *(["--exclude=/.rtl-agent-team/"] if experiment else []),
                str(root) + "/", remote_operand(host, workspace + "/")]
    else:
        listing = cache / "upload.list"
        listing.write_bytes(b"".join(name.encode(errors="surrogateescape") + b"\0" for name in manifest))
        size = sum((root / name).lstat().st_size for name in manifest)
        print(f"Sending {len(manifest)} files ({size / 1e6:.1f} MB) to {host}", file=sys.stderr)
        sync = [*transport, "--from0", f"--files-from={listing}", str(root) + "/", remote_operand(host, workspace + "/")]
    status = step(sync, "sync")
    if status:
        return status
    wrapper = Path(args.wrapper).resolve()
    package = Path(cleanup.enter_context(tempfile.TemporaryDirectory(prefix="rat-runtime-")))
    target = package / "syn/scripts" / wrapper.name
    target.parent.mkdir(parents=True)
    shutil.copy2(wrapper, target)
    library = package / "lib"
    library.mkdir()
    execution_keys = ("timeout_seconds", "stall_seconds", "verdicts")
    remote_config = {key: config[key] for key in ("technology", "preferences", "verification", "project") if key in config}
    remote_config["execution"] = {key: settings[key] for key in execution_keys if key in settings}
    tool_keys = ("path", "env_source", "env_shell", "license_wait_args")
    remote_config["tools"] = {
        group: {name: {key: entry[key] for key in tool_keys if key in entry} for name, entry in entries.items()
                if isinstance(entry, dict)}
        for group, entries in config.get("tools", {}).items() if isinstance(entries, dict)
    }
    atomic_json(library / "dispatch-config.json", remote_config)
    helper_root = Path(__file__).parent
    for name in ("eda_runner.py", "verify_evidence.py", "regression_evidence.py", "eda_setup.py", "merge_coverpoint_logs.py"):
        shutil.copy2(helper_root / name, library / name)
    selector = helper_root / "python-util.sh"
    if not selector.is_file():
        selector = helper_root.parent / "hooks/lib/python-util.sh"
    if selector.is_file():
        shutil.copy2(selector, library / selector.name)
    shim = helper_root / "tool-runner.sh"
    if not shim.is_file():
        shim = helper_root.parent / "skills/rat-init-project/templates/lib/tool-runner.sh"
    shutil.copy2(shim, library / shim.name)
    if manifest is not None:
        shutil.copyfile(cache / "upload.list", package / "sent.list")
    remote_runtime = workspace + "/.rat/runner-runtime/" + run_id
    if remote("umask 077; mkdir -p " + shlex.quote(remote_runtime), "runtime-mkdir"):
        return 2
    if step([*transport, str(package) + "/", remote_operand(host, remote_runtime + "/")], "runtime-sync"):
        return 2
    if manifest is not None and resolved:
        # Unresolved inputs shrink the list, so pruning would delete inputs the run needs.
        prune = [settings.get("python", "python3"), remote_runtime + "/lib/eda_runner.py", "prune-sent",
                 "--workspace", workspace, "--list", remote_runtime + "/sent.list"]
        if remote(shlex.join(prune), "prune"):
            print(f"WARNING: could not remove files deleted since the last run from {host}", file=sys.stderr)
    supported = wrapper.name in BUNDLED_WRAPPERS
    remote_outputs = workspace + "/experiment/" + experiment.name if experiment and supported else workspace
    mapped = []
    explicit_outputs = []
    output_option = False
    for value in args.argv:
        if experiment and output_option:
            relative = experiment_output(experiment, value).relative_to(experiment)
            explicit_outputs.append(str(relative) if supported else relative_output(str(relative)))
            value = str(Path(remote_outputs) / relative)
        elif experiment and (Path(value).is_relative_to(experiment) or Path(value).parts[:2] == ("experiment", experiment.name)):
            relative = experiment_output(experiment, value).relative_to(experiment)
            value = str(Path(remote_outputs) / relative)
        elif value == str(root) or value.startswith(str(root) + "/"):
            value = workspace + value[len(str(root)):]
        mapped.append(value)
        output_option = value in ("--outdir", "--syn-root")
    remote_wrapper = remote_runtime + "/syn/scripts/" + wrapper.name
    status_file = remote_runtime + "/exit-status"
    evidence_path = workspace + "/.rat/state/verify-evidence.json"
    capture_evidence = ""
    if experiment:
        previous = shlex.quote(evidence_path)
        evidence_path = remote_runtime + "/experiment-evidence.json"
        # The reserved workspace can be reused for run-only. Export just this invocation's verdicts.
        experiment_start = f"if [ -f {previous} ]; then mv {previous} {shlex.quote(remote_runtime + '/prior-evidence.json')} || exit 2; fi\n"
        capture_evidence = f"if [ -f {previous} ]; then mv {previous} {shlex.quote(evidence_path)} || exit 2; fi\n"
    else:
        experiment_start = ""
    remote_python = settings.get("python", "python3")
    guarded_wrapper = [remote_python, remote_runtime + "/lib/eda_runner.py", "run", "--root", workspace,
                       "--timeout", str(max(1, limit - (time.monotonic() - started))), "--", "bash", remote_wrapper, *mapped]
    experiment_env = ""
    if experiment:
        experiment_env = "unset RAT_EXPERIMENT_ID\nexport RAT_EXPERIMENT_ACTIVE=1\n"
        if supported:
            experiment_env += "export RAT_EXPERIMENT_ID=" + shlex.quote(experiment.name) + "\n"
        if wrapper.name in ("run_regression.sh", "run_regression_uvm.sh"):
            for variable in ("RESULTS_DIR", "COVERAGE_DIR"):
                if os.environ.get(variable):
                    relative = experiment_output(experiment, os.environ[variable]).relative_to(experiment)
                    explicit_outputs.append(str(relative))
                    experiment_env += "export " + variable + "=" + shlex.quote(remote_outputs + "/" + str(relative)) + "\n"
    job = (experiment_start + experiment_env + "export RAT_PROJECT_ROOT=" + shlex.quote(workspace) + " RAT_REMOTE_ACTIVE=1 RAT_EXECUTION_LOCAL=1"
           + " RAT_RUNTIME_LIB=" + shlex.quote(remote_runtime + "/lib/tool-runner.sh")
           + " RAT_RUNTIME_HELPERS=" + shlex.quote(remote_runtime + "/lib") + "\n"
           + "cd " + shlex.quote(workspace) + " || exit 2\n"
           + shlex.join(guarded_wrapper) + "\nstatus=$?\n" + capture_evidence
           + "printf '%s\\n' \"$status\" > " + shlex.quote(status_file) + "\nexit \"$status\"")
    job_name = "rat-" + run_id
    if selected == "lsf":
        batch = ["bsub", "-K", "-J", job_name, "-oo", remote_runtime + "/job.log", "-eo", remote_runtime + "/job.err"]
        if settings.get("queue"):
            batch += ["-q", settings["queue"]]
        command = shlex.join(batch) + " bash -c " + shlex.quote(job)
    else:
        command = "bash -c " + shlex.quote(job)
    may_release = False
    status = remote(command, "execution")
    if selected == "lsf" and status in LSF_WAITER_LOST:
        cancel_lsf_job(ssh, job_name)
    try:
        observed = subprocess.run([*ssh, "cat " + shlex.quote(status_file)], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        observed = None
    if observed is not None and observed.returncode == 0 and re.fullmatch(r"\d+\s*", observed.stdout) and 0 <= int(observed.stdout.strip()) <= 255:
        status = int(observed.stdout.strip())
        may_release = True
    elif status != 124:
        status = 3
    outputs = settings.get("outputs")
    if outputs is None:
        default = "syn" if wrapper.name in ("run_syn.sh", "run_formality.sh", "run_conformal.sh") else "lint" if wrapper.name in ("run_lint.sh", "run_cdc.sh") else "sim"
        outputs = [] if explicit_outputs and wrapper.name not in ("run_regression.sh", "run_regression_uvm.sh") else [default]
    if not isinstance(outputs, list):
        raise ValueError("execution.outputs must be a list")
    destination = experiment or root
    skip = [f"--exclude={pattern}" for pattern in HEAVY_RESULTS]
    if experiment:
        outputs = [relative_output(str(experiment_output(experiment, value).relative_to(experiment))) for value in outputs]
        outputs.extend(value for value in explicit_outputs if not any(Path(value).is_relative_to(parent) for parent in outputs))
        if "." in outputs:
            outputs = ["."]
    for index, value in enumerate(outputs):
        created = []
        if experiment and supported and value == ".":
            options = ["--safe-links", "--exclude=/.gitignore", "--exclude=/.rat/", *skip]
            source, target = remote_outputs + "/", destination
        else:
            value = relative_output(value)
            relative, source, target, prefix = rsync_relative(remote_outputs, value, destination)
            created = make_target(target)
            if experiment:
                options = ["--safe-links", *relative, *skip]
            else:
                # merge/sync land results in place; sent files (sources) are never overwritten or deleted.
                # ponytail: names containing *, ? or [ act as patterns here; rare in HDL projects.
                protect = cache / "protect.list"
                protect.write_text("".join("/" + name[len(prefix):] + "\n" for name in manifest if name.startswith(prefix)))
                # Excluded names are also kept by --delete: a nested .git (a submodule) survives a sync.
                options = [*relative, *skip, "--exclude=.git", "--exclude=.claude", f"--exclude-from={protect}",
                           *(["--delete"] if mode == "sync" else [])]
        result = step([*transport, *options, remote_operand(host, source), str(target) + "/"], f"fetch-{index}")
        if result:
            remove_if_empty(created)
        if result and status == 0:
            status = 3
    try:
        present = subprocess.run([*ssh, "test -f " + shlex.quote(evidence_path)], capture_output=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        present = None
    if present is not None and present.returncode == 0:
        downloaded = cache / "remote-evidence.json"
        result = step([*transport, remote_operand(host, evidence_path), str(downloaded)], "fetch-evidence")
        if result == 0:
            imported = import_remote_evidence(downloaded, root, workspace, 0 if experiment else started_wall,
                                              experiment, remote_outputs)
            if wrapper.name == "run_sim.sh" and not imported and status == 0:
                status = 3
        elif status == 0:
            status = 3
    elif wrapper.name == "run_sim.sh" and status == 0:
        status = 3
    atomic_json(cache / "result.json", {"backend": selected, "host": host, "workspace": workspace,
                                        "exit_code": status, "outputs": outputs, "run_id": run_id,
                                        "experiment": experiment.name if experiment else None,
                                        "remote_outputs": remote_outputs, "left_on_host": list(HEAVY_RESULTS)})
    if not experiment:
        print(f"Results: {'synced' if mode == 'sync' else 'merged'} into the project; sent sources were left untouched",
              file=sys.stderr)
    if experiment:
        print(f"Results: {experiment.relative_to(root)}/ (waveforms and compiled databases stay on {host}; pull one with "
              f"eda_runner.py fetch --root <project> --experiment {experiment.name} <path>)", file=sys.stderr)
    return status


def locked_experiments(root: Path) -> list[str]:
    """IDs a dispatcher still has locked. The lock is held until the result fetch returns."""
    parent = root / "experiment"
    if not parent.is_dir():
        return []
    locked = []
    for path in parent.iterdir():
        if not path.is_dir() or path.is_symlink() or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", path.name):
            continue
        try:
            fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        except OSError:
            continue
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            locked.append(path.name)
        else:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)
    return locked


def clean(args, root: Path, config: dict) -> int:
    """Remove experiment folders on the execution host, and locally with --local, when the user asks."""
    names = args.experiment or []
    if not names and not args.all:
        raise ValueError("name experiments with --experiment or pass --all")
    if any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name) for name in names):
        raise ValueError("invalid experiment ID")
    settings = config.get("execution", {})
    busy, removed = set(), []
    if backend(config) in ("ssh", "lsf"):
        from eda_setup import validate_host
        host, workspace = settings.get("host", ""), settings.get("workspace", "")
        validate_host(host)
        if not Path(workspace).is_absolute() or not workspace.strip("/") or any(c in workspace for c in "\n\r\0"):
            raise ValueError("invalid remote workspace")
        ssh_options = settings.get("ssh_options", [])
        if not isinstance(ssh_options, list) or not all(isinstance(value, str) for value in ssh_options):
            raise ValueError("ssh_options must be an argument list")
        targets = " ".join(shlex.quote(name) for name in names) if names else "*"
        # The job writes exit-status while the dispatcher is still fetching, so a newer
        # status means "abandoned" only when this project no longer holds the lock.
        # A reservation with no newer status is a job that may still be running.
        held = " ".join(sorted(locked_experiments(root)))
        script = (f"keep={shlex.quote(held)}\n"
                  f"cd {shlex.quote(workspace + '/.rat/experiments')} 2>/dev/null || exit 0\n"
                  f"for id in {targets}; do\n  [ -d \"$id\" ] || continue\n"
                  '  latest=$(ls -td "$id"/work/.rat/runner-runtime/*/ 2>/dev/null | head -n 1)\n'
                  '  if [ -e "$id/active" ] && ! { [ -n "$latest" ] && [ "${latest}exit-status" -nt "$id/active" ]; }; then\n'
                  '    echo "busy $id"; continue\n  fi\n'
                  '  case " $keep " in *" $id "*) echo "busy $id"; continue ;; esac\n'
                  '  rm -rf -- "$id" && echo "removed $id"\ndone\n')
        result = subprocess.run(["ssh", *ssh_options, "--", host, remote_shell_command(script)],
                                capture_output=True, text=True, timeout=600)
        for line in result.stdout.splitlines():
            state, _, name = line.partition(" ")
            if state == "busy":
                busy.add(name)
            elif state == "removed":
                removed.append(name)
        print(f"{host}: removed {len(removed)} experiment folder(s)" + (f", kept running: {', '.join(sorted(busy))}" if busy else ""),
              file=sys.stderr)
        if result.returncode:
            print(result.stderr.strip(), file=sys.stderr)
            return 3
    if args.local:
        parent = root / "experiment"
        local = names or sorted(path.name for path in parent.glob("*") if path.is_dir() and not path.is_symlink())
        for name in local:
            directory = parent / name
            if name in busy or not directory.is_dir() or directory.is_symlink():
                continue
            fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)  # a local run of this ID holds the lock
            except BlockingIOError:
                print(f"kept running local experiment: {name}", file=sys.stderr)
                continue
            finally:
                os.close(fd)
            shutil.rmtree(directory)
    return 0


def fetch(args, root: Path, config: dict) -> int:
    """Pull named results of an earlier remote run into experiment/<id>/, never elsewhere."""
    name = args.experiment
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", name):
        raise ValueError("invalid experiment ID")
    paths = [relative_output(value) for value in args.paths]
    runs = [*(runtime_state_root(root) / "remote-runs").glob("*/result.json"),
            *(root / "experiment" / name / ".rat/remote-runs").glob("*/result.json")]
    records = [json.loads(path.read_text()) for path in sorted(runs, key=lambda path: path.stat().st_mtime)]
    record = next((item for item in reversed(records) if item.get("experiment") == name), None)
    if not record:
        raise ValueError(f"no remote run is recorded for experiment {name}")
    from eda_setup import validate_host
    validate_host(record["host"])
    ssh_options = config.get("execution", {}).get("ssh_options", [])
    if not isinstance(ssh_options, list) or not all(isinstance(value, str) for value in ssh_options):
        raise ValueError("ssh_options must be an argument list")
    destination = root / "experiment" / name
    install_generated_ignore(destination, "*\n")
    failed = []
    for value in paths:
        relative, source, target, _ = rsync_relative(record["remote_outputs"], value, destination)
        created = make_target(target)
        transport, remote_operand = rsync_transport(ssh_options, "--safe-links", *relative)
        if subprocess.run([*transport, remote_operand(record["host"], source), str(target) + "/"]).returncode:
            remove_if_empty(created)
            failed.append(value)
    for value in failed:
        print(f"could not fetch {value}", file=sys.stderr)
    return 3 if failed else 0


# The execution host's Python may predate the runtime; coreutils or perl hash the inputs there.
REMOTE_HASH = ('if command -v sha256sum >/dev/null 2>&1; then rat_hash() { sha256sum -- "$@"; }\n'
               'elif command -v shasum >/dev/null 2>&1; then rat_hash() { shasum -a 256 -- "$@"; }\n'
               "else echo 'RAT_NO_SHA256: neither sha256sum nor shasum on the execution host' >&2; exit 2; fi\n")
MANIFEST_LINE = re.compile(r"([0-9a-f]{64}) [ *](.+)")
# verify-run accepts only the completion lines it documents; a bare "PASS:" may be anything.
VERIFY_RUN_PASS = r"(?m)^\s*RAT_SIM_PASS\b"
# Commands that print text but run nothing; a runner that only echoes a token proves nothing.
NOT_RUNNERS = {"echo", "printf", "true", "false", ":", "cat", "yes", "test", "["}
INTERPRETERS = {"sh", "bash", "dash", "ksh", "zsh", "csh", "tcsh", "python", "python3", "perl", "tclsh"}
# A summary fetched with rsync -a keeps the host's mtime; allow this much clock skew between hosts.
SUMMARY_SKEW_SECONDS = 120


def remote_input_mismatches(root: Path, names: list[str], host: str, remote_root: str, ssh_options: list[str],
                            manifest: Path, timeout: float) -> str:
    """Hash project-relative inputs on the host the runner used; an empty result means every digest matches."""
    # The script travels on stdin: no argument-length limit, and no login-shell quoting.
    script = ("cd -- " + shlex.quote(remote_root) + " || exit 2\n" + REMOTE_HASH
              + "rat_hash " + " ".join(shlex.quote(name) for name in names) + "\n")
    try:
        result = subprocess.run(["ssh", "-o", "BatchMode=yes", *ssh_options, "--", host, "sh -s"],
                                input=script.encode(), capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"hashing the inputs on {host} timed out"
    except OSError as exc:
        return f"hashing the inputs on {host} failed: {exc}"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_bytes(result.stdout)
    remote = {}
    for line in result.stdout.decode(errors="replace").split("\n"):
        match = MANIFEST_LINE.fullmatch(line)
        if match:
            remote[match[2]] = match[1]
    # 1 is the hash tool's "some file is missing"; with no output at all the step itself failed.
    if result.returncode not in (0, 1) or not remote:
        detail = result.stderr.decode(errors="replace").strip().splitlines()[-1:]
        return f"hashing the inputs on {host} failed (status {result.returncode})" + (": " + detail[0] if detail else "")
    missing = [name for name in names if name not in remote]
    differs = [name for name in names if name in remote and remote[name] != digest(root / name)]
    problems = [f"missing on {host}: " + ", ".join(missing)] if missing else []
    problems += [f"differs on {host}: " + ", ".join(differs)] if differs else []
    return "; ".join(problems)


def git_state(root: Path) -> dict:
    """Commit metadata only: the execution host's copy is no checkout, so a hash there proves nothing."""
    try:
        head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=15)
        if head.returncode:
            return {}
        dirty = subprocess.run(["git", "--no-optional-locks", "-C", str(root), "status", "--porcelain",
                                "--untracked-files=no"], capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return {}
    return {"git_head": head.stdout.strip(), "git_dirty": bool(dirty.stdout.strip())}


def change_stamp(path: Path) -> int | None:
    # ctime: a write or rename sets it to the local clock; rsync -a can copy mtime, never ctime.
    try:
        return path.stat().st_ctime_ns
    except FileNotFoundError:
        return None


def runner_files(root: Path, argv: list[str]) -> list[str]:
    """The runner script, and the script an interpreter runs, are part of what the evidence covers."""
    found = []
    candidates = [argv[0]]
    if Path(argv[0]).name in INTERPRETERS:
        candidates += [value for value in argv[1:] if not value.startswith("-")][:1]
    for value in candidates:
        path = Path(value) if Path(value).is_absolute() else root / value
        if path.is_file() and path.resolve().is_relative_to(root):
            found.append(str(path.resolve()))
    return found


def verify_run(args, root: Path, config: dict) -> int:
    """Run a project's own runner unchanged and record evidence bound to its inputs."""
    from verify_evidence import begin_record, finish  # an older project helper must not break other commands

    if not args.argv:
        raise ValueError("verify-run needs the runner command after --")
    if not args.filelist and not args.source:
        raise ValueError("verify-run needs the runner's inputs: -f <filelist> or --source <file>")
    command = args.argv[0]
    if Path(command).name in NOT_RUNNERS:
        raise ValueError(f"{command} runs no simulation; pass the runner that does")
    executable_path = Path(command) if Path(command).is_absolute() else root / command
    if not (executable_path.is_file() and os.access(executable_path, os.X_OK) if "/" in command else shutil.which(command)):
        raise ValueError(f"runner not found or not executable: {command}")
    if bool(args.remote_host) != bool(args.remote_root):
        raise ValueError("--remote-host and --remote-root go together")
    settings = config.get("execution", {})
    ssh_options = settings.get("ssh_options", [])
    if args.remote_host:
        from eda_setup import validate_host
        validate_host(args.remote_host)
        if (not args.remote_root.startswith("/") or not args.remote_root.strip("/")
                or any(char in args.remote_root for char in "\n\r\0")):
            raise ValueError("--remote-root must be an absolute directory on the execution host")
        if not isinstance(ssh_options, list) or not all(isinstance(value, str) for value in ssh_options):
            raise ValueError("ssh_options must be an argument list")
    timeout = args.timeout if args.timeout is not None else float(
        os.environ.get("RAT_TOOL_TIMEOUT_SECONDS", settings.get("timeout_seconds", 1800)))
    stall = args.stall if args.stall is not None else float(settings.get("stall_seconds", 0))
    if timeout <= 0 or stall < 0:
        raise ValueError("timeout must be positive; stall timeout must be nonnegative")
    details = {}
    inputs = source_paths(root, args.source, args.filelist, details)
    remote_names = []
    if args.remote_host:
        require_relative_filelists(root, list(details["filelists"]), variables=False)
        # UVM library headers come from each host's own installation; only project files are compared.
        library = Path(os.environ["UVM_HOME"]).resolve() / "src" if os.environ.get("UVM_HOME") else None
        outside = [str(path) for path in inputs if not path.is_relative_to(root)
                   and not (library and path.is_relative_to(library))]
        if outside:
            raise ValueError("remote hashing covers project files only; outside the project: " + ", ".join(outside))
        remote_names = [str(path.relative_to(root)) for path in inputs if path.is_relative_to(root)]
        unsafe = [name for name in remote_names if "\\" in name or not name.isprintable()]
        if unsafe:
            raise ValueError("cannot hash paths with a backslash or control character remotely: " + ", ".join(unsafe))
    summary = None
    if args.log:
        summary = Path(args.log) if Path(args.log).is_absolute() else root / args.log
    outdir = runtime_state_root(root) / "tool-runs" / ("verify-run-" + uuid.uuid4().hex)
    snapshot = begin_record(argparse.Namespace(
        root=str(root), outdir=str(outdir), tool=args.tool, top="", context="verify-run: " + Path(command).name,
        source=args.source, filelist=args.filelist, include_dir=[], dependency=runner_files(root, args.argv),
        artifact=[], run_only=False, compile_only=False, runner_pid=os.getpid()))  # a live run keeps the gate waiting
    before = change_stamp(summary) if summary else None
    started = time.time()
    console = outdir / "console.log"
    status = execute(list(args.argv), root, console, timeout, stall, cwd=root,
                     env={**os.environ, "RAT_PROJECT_ROOT": str(root)})
    reasons = []
    runtime_log = ""
    extra = {"origin": "verify-run", "argv": list(args.argv), **git_state(root)}
    try:  # a failure after the run still finishes the record, so it never stays RUNNING
        if summary:
            stat = summary.stat() if summary.is_file() else None
            if stat is None or change_stamp(summary) == before:
                reasons.append(f"the runner did not write {args.log} during this run")
            elif stat.st_mtime < started - SUMMARY_SKEW_SECONDS:
                reasons.append(f"{args.log} was written during this run but carries an older time; "
                               "it may be a copy of an earlier result")
            else:
                copy = outdir / ("summary-" + summary.name)  # a later run may overwrite the project's file
                shutil.copyfile(summary, copy)
                runtime_log = str(copy)
        if args.remote_host:
            extra.update(remote_host=args.remote_host, remote_root=args.remote_root)
            if status == 0:  # a failed run is FAIL whatever the remote copy holds
                manifest = outdir / "remote-manifest.txt"
                reason = remote_input_mismatches(root, remote_names, args.remote_host, args.remote_root,
                                                 ssh_options, manifest, min(timeout, 300))
                if manifest.is_file():
                    extra["remote_manifest_sha256"] = digest(manifest)
                if reason:
                    reasons.append(reason)
    except OSError as exc:
        reasons.append(f"could not check the run's results: {exc}")
    if status in (124, 125):
        print("[verify-run] the runner hit its time limit; a remote job it started may still be running", file=sys.stderr)
    for reason in reasons:
        print("[verify-run] " + reason, file=sys.stderr)
    return finish(argparse.Namespace(snapshot=str(snapshot), log=str(console), exit_code=status,
                                     runtime_log=runtime_log, seed_log=[], compile_only=False,
                                     unbound="; ".join(reasons), extra=extra, pass_pattern=VERIFY_RUN_PASS,
                                     label="verify-run"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    query = sub.add_parser("backend")
    query.add_argument("--root", required=True)
    probe = sub.add_parser("available")
    probe.add_argument("--root", required=True)
    probe.add_argument("--tool", required=True)
    get = sub.add_parser("get")
    get.add_argument("--root", required=True)
    get.add_argument("--key", required=True)
    output = sub.add_parser("experiment-output")
    output.add_argument("--root", required=True)
    output.add_argument("path")
    readiness = sub.add_parser("capabilities")
    readiness.add_argument("--root", required=True)
    readiness.add_argument("--phase", default="p1")
    readiness.add_argument("--framework", choices=["auto", "cocotb", "uvm", "sv"], default="auto")
    readiness.add_argument("--bfm", action="store_true")
    readiness.add_argument("--multiclock", action="store_true")
    readiness.add_argument("--signoff", action="store_true")
    readiness.add_argument("--probe-remote", action="store_true", help="measure paths/frameworks on the configured SSH host")
    assessment = sub.add_parser("verdict")
    assessment.add_argument("--root", required=True)
    assessment.add_argument("--log", required=True)
    assessment.add_argument("--tool", required=True)
    assessment.add_argument("--purpose", choices=["simulation", "goals"], default="simulation")
    assessment.add_argument("--completion", default="RAT_TOOL_COMPLETE")
    assessment.add_argument("--exit-code", type=int, required=True)
    command = sub.add_parser("run")
    command.add_argument("--root", required=True)
    command.add_argument("--log")
    command.add_argument("--timeout", type=float)
    command.add_argument("--stall", type=float)
    command.add_argument("--shell-command")
    command.add_argument("argv", nargs=argparse.REMAINDER)
    trim = sub.add_parser("prune-sent", help=argparse.SUPPRESS)
    trim.add_argument("--workspace", required=True)
    trim.add_argument("--list", required=True)
    tidy = sub.add_parser("clean", help="remove experiment folders on the execution host (and locally with --local)")
    tidy.add_argument("--root", required=True)
    tidy.add_argument("--experiment", action="append")
    tidy.add_argument("--all", action="store_true")
    tidy.add_argument("--local", action="store_true")
    pull = sub.add_parser("fetch", help="pull results of an earlier remote run into experiment/<id>/")
    pull.add_argument("--root", required=True)
    pull.add_argument("--experiment", required=True)
    pull.add_argument("paths", nargs="+")
    wrapped = sub.add_parser("verify-run", help="run a project's own runner and record evidence bound to its inputs")
    wrapped.add_argument("--root", required=True)
    wrapped.add_argument("-f", "--filelist", default="")
    wrapped.add_argument("--source", action="append", default=[])
    wrapped.add_argument("--log", default="", help="summary file the runner writes; judged instead of the console")
    wrapped.add_argument("--tool", default="project-runner")
    wrapped.add_argument("--timeout", type=float)
    wrapped.add_argument("--stall", type=float)
    wrapped.add_argument("--remote-host", default="", help="host the runner executed on; its copy is hashed after the run")
    wrapped.add_argument("--remote-root", default="", help="absolute project directory on that host")
    wrapped.add_argument("argv", nargs=argparse.REMAINDER)
    remote = sub.add_parser("dispatch")
    remote.add_argument("--root", required=True)
    remote.add_argument("--wrapper", required=True)
    remote.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == "prune-sent":
        removed = prune_sent(Path(args.workspace), Path(args.list))
        print(f"removed {len(removed)} file(s) deleted since the last run")
        return 0
    if hasattr(args, "argv") and args.argv[:1] == ["--"]:
        args.argv = args.argv[1:]
    root = Path(args.root).resolve()
    try:
        if args.command == "experiment-output":
            print(experiment_output(experiment_directory(root), args.path))
            return 0
        config = configuration(root)
        if args.command == "backend":
            print(backend(config))
            return 0
        if args.command == "available":
            return available(args, config)
        if args.command == "get":
            value = config_value(config, args.key)
            if value is not None:
                print(json.dumps(value) if isinstance(value, (dict, list, bool)) else value)
            return 0
        if args.command == "capabilities":
            return capabilities(args, config)
        if args.command == "verdict":
            return verdict(args, config)
        if args.command == "fetch":
            return fetch(args, root, config)
        if args.command == "clean":
            return clean(args, root, config)
        if args.command == "verify-run":
            return verify_run(args, root, config)
        return run(args, root, config) if args.command == "run" else dispatch(args, root, config)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(f"EDA execution error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
