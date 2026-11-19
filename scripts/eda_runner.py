#!/usr/bin/env python3
# rat-version: 2.0.6
"""Execute configured EDA commands with bounded time and explicit transport results."""

from __future__ import annotations

import argparse
import base64
import fcntl
import json
import os
from pathlib import Path
import re
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

from verify_evidence import atomic_json, classify, digest, unchanged, process_identity, source_paths


def configuration(root: Path) -> dict:
    path = root / "rat_config.json"
    return json.loads(path.read_text()) if path.is_file() else {}


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
    handlers={number:signal.signal(number,interrupt) for number in (signal.SIGINT,signal.SIGTERM)}
    interrupted=0
    try:
        with log.open("wb") as stream:
            while selector.get_map():
                now = time.monotonic()
                reason = "TIMEOUT" if now - started >= timeout else "STALL" if stall and now - last_output >= stall else ""
                if reason and termination == "exit":
                    termination = reason
                    try:
                        os.killpg(process.pid, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        pass
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    marker = f"\nRAT_{reason}: execution limit reached\n".encode()
                    stream.write(marker)
                    sys.stdout.buffer.write(marker)
                    sys.stdout.buffer.flush()
                for key, _ in selector.select(timeout=0.05):
                    data = os.read(key.fd, 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    stream.write(data)
                    sys.stdout.buffer.write(data)
                    sys.stdout.buffer.flush()
                    last_output = time.monotonic()
    except Interrupted as event:
        interrupted=event.number
        termination="INTERRUPTED"
        try: os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError: pass
        try: process.wait(timeout=1)
        except subprocess.TimeoutExpired: pass
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
    finally:
        for number,handler in handlers.items(): signal.signal(number,handler)
    selector.close()
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


def available(args, config: dict) -> int:
    resolved, entry = tool_configuration(config, args.tool, getattr(args, "category", None))
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
        return subprocess.run(argv, capture_output=True, timeout=10).returncode
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

    if remote and backend(config) == "lsf":
        need("LSF scheduler", ["bsub"])
    if phase not in ("p1", "1", "research"):
        need("build system", ["make"])
    if phase in ("p2", "p3", "all"):
        need("C/C++ compiler", ["gcc", "clang", "cc", "g++"])
    if args.bfm:
        check = subprocess.run(["pkg-config", "--exists", "systemc"], capture_output=True) if not measured and shutil.which("pkg-config") else None
        if not (measured["systemc"] if measured else check is not None and check.returncode == 0):
            missing.append("SystemC for the requested TLM BFM")
    if phase in ("p4", "p5", "p5a", "all"):
        simulator = need("simulator", ["vcs", "xrun", "vsim", "verilator", "iverilog"], "simulators", "simulator")
        need("linter", ["verilator", "verible-verilog-lint", "slang", "sg_shell"], "lint", "lint")
        if simulator == "verilator":
            need("C++ compiler for Verilator", ["g++", "clang++"])
        framework = args.framework
        if framework == "cocotb" or (framework == "auto" and simulator in ("iverilog", "verilator")):
            check = subprocess.run([sys.executable, "-c", "import cocotb"], capture_output=True) if not measured else None
            if not (measured["cocotb"] if measured else check.returncode == 0):
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
        shim_parent = root / ".rat/tool-shims"
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
        argv = ["docker", "run", "--rm", "--user", f"{os.getuid()}:{os.getgid()}", "--env", "HOME=/tmp",
                "--env", f"RAT_PROJECT_ROOT={root}", "--env", "RAT_EXECUTION_LOCAL=1", "--env", "PATH=" + env["PATH"],
                *mounts, "--workdir", str(cwd), image, *argv]
    stamp = uuid.uuid4().hex
    log = Path(args.log) if args.log else root / ".rat/tool-runs" / (stamp + ".log")
    timeout = args.timeout if args.timeout is not None else float(os.environ.get("RAT_TOOL_TIMEOUT_SECONDS", settings.get("timeout_seconds", 1800)))
    stall = args.stall if args.stall is not None else float(settings.get("stall_seconds", 0))
    try:
        return execute(argv, root, log, timeout, stall, env=env)
    finally:
        if shims:
            shims.cleanup()


def relative_output(value: str) -> str:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or value in ("", "."):
        raise ValueError(f"remote output must be project-relative: {value}")
    return value


def remote_shell_command(script: str) -> str:
    # tcsh cannot parse literal newlines in the outer SSH command's quotes.
    payload = base64.b64encode(script.encode()).decode()
    return "sh -c " + shlex.quote('payload=$(printf %s ' + payload + ' | base64 -d) || exit 2; eval "$payload"')


def import_remote_evidence(path: Path, root: Path, workspace: str, since: float) -> int:
    data = json.loads(path.read_text())
    records = []
    prefix = workspace.rstrip("/") + "/"

    def local_path(value):
        if not value.startswith(prefix):
            raise ValueError(f"remote artifact is outside synchronized workspace: {value}")
        return str(root / value[len(prefix):])

    for remote_record in data.get("runs", []):
        if remote_record.get("started_at", 0) < since:
            continue
        record = dict(remote_record)
        record["sources"] = {local_path(key): value for key, value in record["sources"].items()}
        record["log"] = local_path(record["log"])
        if record.get("runtime_log"): record["runtime_log"]["path"]=local_path(record["runtime_log"]["path"])
        record["outdir"] = local_path(record["outdir"])
        record["root"] = str(root)
        record["state_dir"] = str(root / ".rat/state")
        record["remote_workspace"] = workspace
        log = Path(record["log"])
        if record["verdict"] == "PASS" and (not unchanged(record["sources"]) or not log.is_file()
                                               or digest(log) != record["log_sha256"]):
            record["verdict"] = "INCONCLUSIVE"
        records.append(record)
    index = root / ".rat/state/verify-evidence.json"
    if not index.parent.resolve().is_relative_to(root):
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


def dispatch(args, root: Path, config: dict) -> int:
    snapshot=None
    filelist=""
    sources=[]
    for index,token in enumerate(args.argv):
        if token in ("-f","--filelist") and index+1<len(args.argv): filelist=args.argv[index+1]
        elif token.endswith((".sv",".v",".svh",".vh")) and (root/token).is_file(): sources.append(token)
    if not filelist:
        candidate=config.get("project",{}).get("filelist", "rtl/filelist_top.f")
        if candidate and (root/candidate).is_file(): filelist=candidate
    try:
        inputs=source_paths(root,sources,filelist) if sources or filelist else []
    except (OSError,ValueError):
        inputs=[]
    if inputs:
        run_id=uuid.uuid4().hex
        snapshot=root/".rat/state/verify-runs"/(run_id+".json")
        record={"schema_version":1,"run_id":run_id,"root":str(root),"tool":"remote-wrapper",
                "sources":{str(path):digest(path) for path in inputs},"verdict":"RUNNING",
                "started_at":time.time(),"runner_pid":os.getpid(),"runner_identity":process_identity(os.getpid()),
                "host":socket.gethostname(),"compile_only":"--compile-only" in args.argv}
        atomic_json(snapshot,record)
    try:
        return _dispatch(args,root,config)
    finally:
        if snapshot:
            record.update(verdict="TRANSPORT_COMPLETE",completed_at=time.time())
            atomic_json(snapshot,record)


def _dispatch(args, root: Path, config: dict) -> int:
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
            if token in ("-f","-F") and index+1<len(tokens):
                nested=filelist.parent/tokens[index+1]
                if not nested.is_file(): nested=root/tokens[index+1]
                filelists.append(nested.resolve())
    run_id = uuid.uuid4().hex
    cache = root / ".rat/remote-runs" / run_id
    cache.mkdir(parents=True)
    started = time.monotonic()
    started_wall = time.time()
    limit = float(settings.get("timeout_seconds", 1800))
    ssh_options = settings.get("ssh_options", [])
    if not isinstance(ssh_options, list) or not all(isinstance(value, str) for value in ssh_options):
        raise ValueError("ssh_options must be an argument list")
    ssh = ["ssh", *ssh_options, host]

    def step(argv, name):
        remaining = limit - (time.monotonic() - started)
        if remaining <= 0:
            return 124
        return execute(argv, root, cache / (name + ".log"), remaining)

    def remote(script, name):
        return step([*ssh, remote_shell_command(script)], name)

    if remote("mkdir -p " + shlex.quote(workspace), "mkdir"):
        return 2
    transport = ["rsync", "-a", "--protect-args", "-e", shlex.join(["ssh", *ssh_options])]
    sync = [*transport, "--exclude=.git", "--exclude=.claude", "--exclude=.rat/state",
            "--exclude=.rat/audit", "--exclude=.rat/remote-runs", str(root) + "/", host + ":" + workspace + "/"]
    status = step(sync, "sync")
    if status:
        return status
    wrapper = Path(args.wrapper).resolve()
    package = cache / "runtime"
    target = package / "syn/scripts" / wrapper.name
    target.parent.mkdir(parents=True)
    shutil.copy2(wrapper, target)
    library = package / "lib"
    library.mkdir()
    helper_root = Path(__file__).parent
    for name in ("eda_runner.py", "verify_evidence.py", "regression_evidence.py", "eda_setup.py"):
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
    remote_runtime = workspace + "/.rat/runner-runtime/" + run_id
    if remote("mkdir -p " + shlex.quote(remote_runtime), "runtime-mkdir"):
        return 2
    if step([*transport, str(package) + "/", host + ":" + remote_runtime + "/"], "runtime-sync"):
        return 2
    mapped = []
    for value in args.argv:
        if value == str(root) or value.startswith(str(root) + "/"):
            value = workspace + value[len(str(root)):]
        mapped.append(value)
    remote_wrapper = remote_runtime + "/syn/scripts/" + wrapper.name
    status_file = remote_runtime + "/exit-status"
    remote_python = settings.get("python", "python3")
    guarded_wrapper = [remote_python, remote_runtime + "/lib/eda_runner.py", "run", "--root", workspace,
                       "--timeout", str(max(1, limit - (time.monotonic() - started))), "--", "bash", remote_wrapper, *mapped]
    job = ("export RAT_PROJECT_ROOT=" + shlex.quote(workspace) + " RAT_REMOTE_ACTIVE=1 RAT_EXECUTION_LOCAL=1"
           + " RAT_RUNTIME_LIB=" + shlex.quote(remote_runtime + "/lib/tool-runner.sh")
           + " RAT_RUNTIME_HELPERS=" + shlex.quote(remote_runtime + "/lib") + "\n"
           + "cd " + shlex.quote(workspace) + " || exit 2\n"
           + shlex.join(guarded_wrapper) + "\nstatus=$?\n"
           + "printf '%s\\n' \"$status\" > " + shlex.quote(status_file) + "\nexit \"$status\"")
    job_name = "rat-" + run_id
    if selected == "lsf":
        batch = ["bsub", "-K", "-J", job_name, "-oo", remote_runtime + "/job.log", "-eo", remote_runtime + "/job.err"]
        if settings.get("queue"):
            batch += ["-q", settings["queue"]]
        command = shlex.join(batch) + " bash -c " + shlex.quote(job)
    else:
        command = "bash -c " + shlex.quote(job)
    status = remote(command, "execution")
    if status == 124 and selected == "lsf":
        subprocess.run([*ssh, "bkill -J " + shlex.quote(job_name)], timeout=15, capture_output=True)
    observed = subprocess.run([*ssh, "cat " + shlex.quote(status_file)], capture_output=True, text=True, timeout=15)
    if observed.returncode == 0 and re.fullmatch(r"\d+\s*", observed.stdout) and 0 <= int(observed.stdout.strip()) <= 255:
        status = int(observed.stdout.strip())
    elif status != 124:
        status = 3
    outputs = settings.get("outputs")
    if outputs is None:
        default = "syn" if wrapper.name in ("run_syn.sh", "run_formality.sh", "run_conformal.sh") else "lint" if wrapper.name in ("run_lint.sh", "run_cdc.sh") else "sim"
        outputs = [default]
    if not isinstance(outputs, list):
        raise ValueError("execution.outputs must be a list")
    for index, value in enumerate(outputs):
        value = relative_output(value)
        result = step([*transport, "--relative", host + ":" + workspace + "/./" + value, str(root) + "/"], f"fetch-{index}")
        if result and status == 0:
            status = 3
    evidence_path = workspace + "/.rat/state/verify-evidence.json"
    present = subprocess.run([*ssh, "test -f " + shlex.quote(evidence_path)], capture_output=True, timeout=15)
    if present.returncode == 0:
        downloaded = cache / "remote-evidence.json"
        result = step([*transport, host + ":" + evidence_path, str(downloaded)], "fetch-evidence")
        if result == 0:
            imported = import_remote_evidence(downloaded, root, workspace, started_wall)
            if wrapper.name == "run_sim.sh" and not imported and status == 0:
                status = 3
        elif status == 0:
            status = 3
    elif wrapper.name == "run_sim.sh" and status == 0:
        status = 3
    atomic_json(cache / "result.json", {"backend": selected, "host": host, "workspace": workspace,
                                        "exit_code": status, "outputs": outputs, "run_id": run_id})
    return status


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
    remote = sub.add_parser("dispatch")
    remote.add_argument("--root", required=True)
    remote.add_argument("--wrapper", required=True)
    remote.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if hasattr(args, "argv") and args.argv[:1] == ["--"]:
        args.argv = args.argv[1:]
    root = Path(args.root).resolve()
    try:
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
        return run(args, root, config) if args.command == "run" else dispatch(args, root, config)
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print(f"EDA execution error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
