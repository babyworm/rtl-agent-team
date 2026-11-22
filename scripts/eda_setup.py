#!/usr/bin/env python3
# rat-version: 2.0.11
"""Discover an EDA site, probe selected tools, and apply a reusable site profile."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import copy
import hashlib
import importlib.util
from itertools import repeat
import json
import math
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

MARKER = "RAT_SETUP_JSON:"
PATH_MARKER = "RAT_TOOL_PATH:"
SMOKE_PASS = "RAT_SETUP_SIM_PASS"
TCL_READY = "RAT_SETUP_TCL_READY"
TOOLS = {
    "simulators": {name: name for name in ("vcs", "xrun", "vsim", "verilator", "iverilog")},
    "synthesis": {name: name for name in ("dc_shell", "genus", "yosys")},
    "lint": {"verilator": "verilator", "verible": "verible-verilog-lint", "slang": "slang", "sg_shell": "sg_shell"},
    "cdc": {"svlens": "svlens", "sg_shell": "sg_shell", "vc_cdc": "vc_static_shell", "questa_cdc": "qverify"},
    "formal": {name: name for name in ("sby", "jg", "vcf")},
    "equivalence": {name: name for name in ("fm_shell", "lec")},
    "sta": {"pt_shell": "pt_shell"},
    "power": {name: name for name in ("pwr_shell", "joules", "voltus", "powerpro")},
    "debug": {name: name for name in ("verdi", "simvision")},
    "coverage": {name: name for name in ("urg", "imc", "vcover")},
    "build": {name: name for name in ("make", "gcc", "clang", "cc", "g++", "clang++", "rsync", "bsub")},
}
PREFERENCES = {"simulator": "simulators", "synthesis": "synthesis", "lint": "lint",
               "formal": "formal", "cdc": "cdc", "equivalence": "equivalence"}
VERSION_ARGS = dict.fromkeys(("verilator", "verible-verilog-lint", "slang", "svlens", "yosys",
                              "make", "gcc", "clang", "cc", "g++", "clang++", "rsync"), "--version")
VERSION_ARGS.update({"vsim": "-version", "iverilog": "-V", "sby": "--help", "urg": "-help"})
SIMULATION_ARGS = {
    "xrun": ("-sv", "-top", "rat_setup_tb", "rat_setup_tb.sv"),
    "vcs": ("-full64", "-sverilog", "-R", "rat_setup_tb.sv"),
}
TCL_ARGS = {
    "dc_shell": ("-64bit", "-f"),
    "fm_shell": ("-64bit", "-f"),
    "genus": ("-batch", "-files"),
    "imc": ("-exec",),
}


def bounded(argv, timeout, **kwargs):
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True, **kwargs)
    try:
        output, _ = process.communicate(timeout=timeout)
        return process.returncode, output.decode(errors="replace")
    except subprocess.TimeoutExpired as exc:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):  # macOS: EPERM once only the zombie leader is left
            pass
        process.stdout.close()
        process.wait()
        return 124, (exc.output or b"").decode(errors="replace") + "\nRAT_TIMEOUT: probe limit reached"


def environment_command(entry, argv):
    source = entry.get("env_source", "")
    if not source:
        return argv
    shell = entry.get("env_shell", "bash")
    if shell in ("csh", "tcsh"):
        return [shell, "-f", "-c", source + "\nif ($status != 0) exit $status\nexec $argv:q", *argv]
    if shell == "bash":
        return [shell, "-c", source + '\nstatus=$?; [ "$status" -eq 0 ] || exit "$status"\nexec "$@"', "rat-setup", *argv]
    raise ValueError("unsupported environment shell: " + shell)


def inspect_site(request):
    tools = {}
    configured = request.get("tools", {})
    environments = {}
    shared = request.get("environment", {})
    for category, entries in TOOLS.items():
        tools[category] = {}
        for key, binary in entries.items():
            entry = configured.get(category, {}).get(key, {})
            environment = entry if entry.get("env_source") else shared
            candidate = entry.get("path") or binary
            measured = {"path": "", "detected": False, "env_source": environment.get("env_source", ""),
                        "env_shell": environment.get("env_shell", "bash")}
            if "setup_check" in entry:
                measured["setup_check"] = entry["setup_check"]
            tools[category][key] = measured
            environment = (measured["env_source"], measured["env_shell"])
            environments.setdefault(environment, []).append((category, key, candidate, measured))
    with ThreadPoolExecutor(max_workers=6) as pool:
        for results in pool.map(resolve_environment, environments.values(), repeat(request.get("probe_timeout", 8))):
            for measured, path, status in results:
                measured.update(path=path, detected=bool(path), setup_status=status)
        if request.get("check_tools"):
            checks, pending = {}, []
            for entries in environments.values():
                for category, key, _, measured in entries:
                    if not measured["detected"]:
                        continue
                    binary = TOOLS[category][key]
                    identity = (tool_fingerprint(measured), binary)
                    if identity not in checks:
                        checks[identity] = pool.submit(check_tool, binary, measured, request["probe_timeout"])
                    pending.append((measured, checks[identity]))
            for measured, check in pending:
                status, evidence = check.result()
                measured["setup_status"] = status
                if evidence:
                    measured["probe"] = evidence
    systemc = bounded(["pkg-config", "--exists", "systemc"], 10)[0] == 0 if shutil.which("pkg-config") else False
    return {"schema_version": 1, "measured_at": time.time(), "hostname": socket.gethostname(),
            "home": str(Path.home()), "login_shell": os.environ.get("SHELL", ""),
            "python": sys.executable, "python_version": list(sys.version_info[:3]),
            "tools": tools, "cocotb": importlib.util.find_spec("cocotb") is not None,
            "systemc": systemc,
            "libraries": {path: Path(path).is_file() for path in request.get("libraries", [])},
            "evidence_level": "tool_readiness" if request.get("check_tools") else "executable_paths",
            "license_checked": False}


def resolve_environment(entries, timeout):
    environment = entries[0][3]
    if not environment["env_source"]:
        results = []
        for _, _, candidate, entry in entries:
            path = shutil.which(candidate)
            results.append((entry, os.path.abspath(path) if path else "", "found" if path else "missing"))
        return results
    candidates = list(dict.fromkeys(candidate for _, _, candidate, _ in entries))
    script = ('for tool do path=$(command -v -- "$tool") || continue; '
              '[ -f "$path" ] && [ -x "$path" ] || continue; '
              'case "$path" in /*) ;; *) path="$PWD/$path" ;; esac; '
              'printf "' + PATH_MARKER + '%s\\t%s\\n" "$tool" "$path"; done; exit 0')
    argv = environment_command(environment, ["/bin/sh", "-c", script, "rat-path", *candidates])
    try:
        code, output = bounded(argv, timeout, stdin=subprocess.DEVNULL)
    except OSError:
        code, output = 127, ""
    paths = dict(line[len(PATH_MARKER):].split("\t", 1) for line in output.splitlines()
                 if line.startswith(PATH_MARKER) and "\t" in line)
    status = "environment_timeout" if code == 124 else "environment_failed" if code else "missing"
    return [(entry, paths.get(candidate, "") if not code else "",
             "found" if not code and candidate in paths else status) for _, _, candidate, entry in entries]


def check_tool(binary, entry, timeout):
    configured = entry.get("setup_check")
    smoke = tcl = False
    if configured is not None:
        check = configured
    elif binary in SIMULATION_ARGS:
        smoke = True
        check = {"args": SIMULATION_ARGS[binary], "expected_line": SMOKE_PASS, "licensed": True}
    elif binary in TCL_ARGS:
        tcl = True
        check = {"args": (*TCL_ARGS[binary], "rat_setup.tcl"), "expected_line": TCL_READY}
    elif binary in VERSION_ARGS:
        check = {"args": [VERSION_ARGS[binary]]}
    else:
        return "unchecked", None
    if not isinstance(check, dict):
        raise ValueError("setup_check must be an object")
    arguments, expected = check.get("args"), check.get("expected_line")
    licensed = check.get("licensed", False)
    if (not isinstance(arguments, (list, tuple)) or not all(isinstance(arg, str) for arg in arguments)
            or (expected is not None and (not isinstance(expected, str) or not expected.strip()))
            or not isinstance(licensed, bool) or (licensed and not expected)):
        raise ValueError("setup_check requires string args and an expected_line for a licensed workload")
    request = {"entry": entry, "tool": binary, "arguments": arguments, "timeout": timeout,
               "expected_line": expected, "licensed": licensed}
    with tempfile.TemporaryDirectory(prefix="rat-eda-setup-") as directory:
        if smoke:
            (Path(directory) / "rat_setup_tb.sv").write_text(
                'module rat_setup_tb; initial begin $display("' + SMOKE_PASS + '"); $finish; end endmodule\n')
        elif tcl:
            (Path(directory) / "rat_setup.tcl").write_text(f"puts {TCL_READY}\nexit\n")
        result = probe_tool(request, cwd=directory)
    summary = {key: value for key, value in result.items() if key not in ("argv", "output")}
    if tcl:
        summary["evidence_level"] = "command_probe"
    if result["status"] == "failed":
        return result["failure"], summary
    return ("workload_passed" if expected and not tcl else "command_passed"), summary


def probe_tool(request, cwd=None):
    entry = request["entry"]
    argv = [entry["path"], *request["arguments"]]
    try:
        status, output = bounded(environment_command(entry, argv), request["timeout"], stdin=subprocess.DEVNULL, cwd=cwd)
    except OSError as exc:
        status, output = 127, str(exc)
    loader_error = bool(re.search(r"error while loading shared libraries|cannot open shared object file|command not found", output, re.I))
    license_error = bool(re.search(r"licensing checkout error|checkout denied|\*[EF],NOLIC[\w]*\b|"
                                   r"(?:failed|unable) to (?:check out|checkout|obtain)[^\n]*license", output, re.I))
    expected = request.get("expected_line")
    failure = ("timeout" if status == 124 else "loader_failed" if loader_error else "license_failed" if license_error else
               "command_failed" if status else
               "workload_unverified" if expected and not any(line.strip().removeprefix("# ") == expected
                                                            for line in output.splitlines()) else None)
    return {"schema_version": 1, "measured_at": time.time(), "tool": request["tool"],
            "argv": argv, "exit_code": status, "output": output[-12000:],
            "configuration_sha256": tool_fingerprint(entry),
            "status": "failed" if failure else "completed", "failure": failure,
            "evidence_level": "workload_probe" if expected else "command_probe",
            "license_checked": not failure and bool(expected and request.get("licensed"))}


def tool_fingerprint(entry):
    fields = {key: entry.get(key, "bash" if key == "env_shell" else "")
              for key in ("path", "env_source", "env_shell")}
    if "setup_check" in entry:
        fields["setup_check"] = entry["setup_check"]
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


def failed_probe(entry):
    probe = entry.get("probe", {})
    return probe.get("status") == "failed" and probe.get("configuration_sha256") == tool_fingerprint(entry)


def validate_host(host):
    if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.@:-]*", host):
        raise ValueError("use an SSH host alias or user@host; keep SSH options in ~/.ssh/config")


def inspect_remote(host, request, timeout=60, python=None):
    validate_host(host)
    # The login shell may be tcsh and python3 may be older than the runtime requires.
    # tcsh rejects literal newlines inside a quoted SSH command.
    selector = (
        'if [ -n "$2" ]; then '
        '"$2" -c \'import sys; sys.exit(sys.version_info < (3,9))\' >/dev/null 2>&1 || exit 2; '
        'exec "$2" - _worker "$1"; fi; '
        'for candidate in python3 python3.14 python3.13 python3.12 python3.11 python3.10 python3.9; do '
        'resolved=$(command -v "$candidate" 2>/dev/null) || continue; '
        'if "$resolved" -c \'import sys; sys.exit(sys.version_info < (3,9))\' >/dev/null 2>&1; then '
        'exec "$resolved" - _worker "$1"; fi; done; '
        'printf "%s\\n" "Remote Python >=3.9 is required" >&2; exit 2'
    )
    command = shlex.join(["sh", "-c", selector, "rat-site", json.dumps(request), python or ""])
    result = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", host, command],
                            input=Path(__file__).read_text(), capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise ValueError("SSH site probe failed: " + (result.stderr or result.stdout)[-3000:])
    records = [line[len(MARKER):] for line in result.stdout.splitlines() if line.startswith(MARKER)]
    if len(records) != 1:
        raise ValueError("SSH site probe did not return one structured result")
    return json.loads(records[0])


def discover(host=None, config=None, timeout=60, *, environment=None, check_tools=False, probe_timeout=8):
    config = config or {}
    tools = {category: {key: {field: entry[field] for field in ("path", "env_source", "env_shell", "setup_check") if field in entry}
                        for key, entry in entries.items() if isinstance(entry, dict)}
             for category, entries in config.get("tools", {}).items() if isinstance(entries, dict)}
    request = {"action": "discover", "tools": tools, "environment": environment or {},
               "check_tools": check_tools, "probe_timeout": probe_timeout,
               "libraries": [config["technology"]["db"]] if config.get("technology", {}).get("db") else []}
    execution = config.get("execution", {})
    remote_python = execution.get("python") if execution.get("backend") in ("ssh", "lsf") and execution.get("host") == host else None
    report = inspect_remote(host, request, timeout, remote_python) if host else inspect_site(request)
    report["execution"] = {"backend": "ssh" if host else "local", "python": report["python"]}
    # The site's default library travels with the profile; `libraries` holds its measured presence.
    technology = {key: value for key, value in config.get("technology", {}).items() if isinstance(value, str) and value}
    if technology:
        report["technology"] = technology
    if host:
        report["execution"]["host"] = host
    return report


def read_json(path):
    value = json.loads(Path(path).read_text())
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object: " + str(path))
    return value


def user_configuration(root):
    # Claude Code's plugin data folder: hooks get CLAUDE_PLUGIN_DATA, Bash gets RAT_DATA_DIR.
    folder = os.environ.get("RAT_DATA_DIR") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if not folder:
        return {}
    data = Path(folder)
    path = data / "env-config.json"
    if not path.is_file():
        return {}
    machine = read_json(path)
    site = machine.get("default_site")
    if site is None or site == "":
        return {key: machine[key] for key in ("execution", "preferences", "tools", "technology", "verification")
                if key in machine}
    if not isinstance(site, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", site) or site in (".", ".."):
        raise ValueError("default_site must name a profile under the private sites directory")
    profile = read_json(data / "sites" / (site + ".json"))
    config = configure(profile, {}, root)
    if "verification" in machine:  # machine policy such as verification.stop_gate, whichever site runs
        config["verification"] = machine["verification"]
    return config


def write_json(path, value):
    path = Path(path).absolute()
    plugin_root = Path(__file__).resolve().parents[1]
    if (plugin_root / ".claude-plugin/plugin.json").is_file() and path.resolve().is_relative_to(plugin_root):
        raise ValueError("private site data must be stored outside the plugin repository; use the per-user data directory")
    if any(parent.is_symlink() for parent in (path, *path.parents)):
        raise ValueError("refusing a symlinked configuration destination")
    if path.exists() and (not path.is_file() or path.stat().st_nlink != 1):
        raise ValueError("configuration destination must be a regular, unlinked file")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(value, stream, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def configure(profile, existing, root, workspace=None, preferences=(), backend=None):
    config = copy.deepcopy(existing)
    execution = copy.deepcopy(profile["execution"])
    if existing.get("execution", {}).get("host") not in (None, "", execution.get("host")):
        raise ValueError("project already uses another site; resolve its tool/path overrides before switching")
    if execution["backend"] == "ssh":
        execution["backend"] = backend or ("lsf" if existing.get("execution", {}).get("backend") == "lsf" else "ssh")
    elif backend:
        raise ValueError("remote backend selection requires an SSH site profile")
    config.setdefault("execution", {}).update(execution)
    if execution["backend"] in ("ssh", "lsf"):
        proposed = workspace or config["execution"].get("workspace")
        if not proposed:
            suffix = hashlib.sha256(str(root.resolve()).encode()).hexdigest()[:10]
            name = re.sub(r"[^A-Za-z0-9_.-]", "_", root.name)
            proposed = profile["home"] + "/.cache/rtl-agent-team/workspaces/" + name + "-" + suffix
        if not Path(proposed).is_absolute() or proposed == "/" or any(c in proposed for c in "\n\r\0"):
            raise ValueError("remote workspace must be an absolute private project directory")
        config["execution"]["workspace"] = proposed
    config["execution"].setdefault("timeout_seconds", 1800)
    for category, entries in profile["tools"].items():
        for key, measured in entries.items():
            if not measured["detected"]:
                continue
            target = config.setdefault("tools", {}).setdefault(category, {}).setdefault(key, {})
            # Existing explicit tool/environment choices take priority over discovery.
            for field, value in measured.items():
                if field not in ("detected", "probe", "setup_status") and not target.get(field):
                    target[field] = value
            probe = measured.get("probe", {})
            matches_probe = probe.get("configuration_sha256") == tool_fingerprint(target)
            if matches_probe:
                target["probe"] = copy.deepcopy(probe)
            target["detected"] = all(target.get(field, "") == measured.get(field, "")
                                     for field in ("path", "env_source", "env_shell"))
            if "setup_status" in measured:
                target["setup_status"] = (measured["setup_status"] if target["detected"] and (not probe or matches_probe)
                                          else "override_unchecked")
    selected = config.setdefault("preferences", {})
    def usable(entry):
        return entry.get("detected") and not failed_probe(entry)
    automatic = selected.get("_auto") if isinstance(selected.get("_auto"), dict) else {}
    for preference, category in PREFERENCES.items():
        # A locally auto-detected choice says nothing about this site's tools.
        if not selected.get(preference) or selected.get(preference) == automatic.get(preference):
            preferred = profile.get("preferences", {}).get(preference)
            if preferred and usable(profile["tools"].get(category, {}).get(preferred, {})):
                selected[preference] = preferred
            else:
                selected[preference] = next((key for key, entry in profile["tools"].get(category, {}).items() if usable(entry)), "")
    for item in preferences:
        key, separator, value = item.partition("=")
        if not separator or key not in PREFERENCES or not usable(profile["tools"].get(PREFERENCES[key], {}).get(value, {})):
            raise ValueError("preference must select a discovered tool: " + item)
        selected[key] = value
    # The site's default library applies only where the project has not named one.
    technology = config.setdefault("technology", {})
    for key, value in profile.get("technology", {}).items():
        if isinstance(value, str) and value and not technology.get(key):
            technology[key] = value
    config["detection"] = {"scope": "remote_path_probe" if execution["backend"] in ("ssh", "lsf") else "local",
                           "host": execution.get("host"), "measured_at": profile["measured_at"],
                           "remote_tools_probed": execution["backend"] in ("ssh", "lsf"), "license_checked": False}
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    discovery = commands.add_parser("discover")
    discovery.add_argument("--host")
    discovery.add_argument("--config", type=Path)
    discovery.add_argument("--env-script", type=Path, help="trusted setup script on the execution host")
    discovery.add_argument("--env-shell", choices=("bash", "csh", "tcsh"), default="bash")
    discovery.add_argument("--paths-only", action="store_true", help="skip tool execution checks")
    discovery.add_argument("--probe-timeout", type=float, default=8, help="maximum seconds per setup or tool check")
    discovery.add_argument("--output", type=Path)
    discovery.add_argument("--timeout", type=float, default=60)
    proposal = commands.add_parser("configure")
    proposal.add_argument("--profile", type=Path, required=True)
    proposal.add_argument("--root", type=Path, required=True)
    proposal.add_argument("--workspace")
    proposal.add_argument("--backend", choices=["ssh", "lsf"])
    proposal.add_argument("--prefer", action="append", default=[])
    proposal.add_argument("--dry-run", action="store_true")
    probe = commands.add_parser("probe")
    probe.add_argument("--profile", type=Path, required=True)
    probe.add_argument("--tool", required=True, help="category.key, e.g. simulators.xrun")
    probe.add_argument("--output", type=Path)
    probe.add_argument("--record", action="store_true", help="save this measured probe in the reusable profile")
    probe.add_argument("--timeout", type=float, default=30)
    probe.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if any(not math.isfinite(limit) or limit <= 0 for limit in
               (getattr(args, "timeout", 1), getattr(args, "probe_timeout", 1))):
            raise ValueError("timeouts must be positive and finite")
        if args.action == "discover":
            environment = {}
            if args.env_script:
                if not args.env_script.is_absolute() or any(c in str(args.env_script) for c in "\n\r\0"):
                    raise ValueError("--env-script must be an absolute path on the execution host")
                environment = {"env_source": "source " + shlex.quote(str(args.env_script)), "env_shell": args.env_shell}
            value = discover(args.host, read_json(args.config) if args.config else None, args.timeout,
                             environment=environment, check_tools=not args.paths_only, probe_timeout=args.probe_timeout)
        elif args.action == "configure":
            destination = args.root / "rat_config.json"
            value = configure(read_json(args.profile), read_json(destination) if destination.exists() else {}, args.root, args.workspace, args.prefer, args.backend)
            if not args.dry_run:
                write_json(destination, value)
        else:
            profile = read_json(args.profile)
            category, key = args.tool.split(".", 1)
            entry = profile["tools"][category][key]
            if not entry["detected"]:
                raise ValueError("tool was not discovered: " + args.tool)
            arguments = args.arguments[1:] if args.arguments[:1] == ["--"] else args.arguments
            if not arguments:
                raise ValueError("supply the site's verified probe arguments after --")
            request = {"action": "probe", "tool": args.tool, "entry": entry, "arguments": arguments, "timeout": args.timeout}
            execution = profile["execution"]
            value = inspect_remote(execution["host"], request, args.timeout + 15, execution["python"]) if execution["backend"] == "ssh" else probe_tool(request)
            if args.record:
                profile["tools"][category][key]["probe"] = value
                write_json(args.profile, profile)
        if getattr(args, "output", None):
            write_json(args.output, value)
        print(json.dumps(value, indent=2))
        return 1 if value.get("status") == "failed" else 0
    except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
        print("EDA setup error: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    if sys.argv[1:2] == ["_worker"]:
        try:
            request = json.loads(sys.argv[2])
            value = inspect_site(request) if request["action"] == "discover" else probe_tool(request)
            print(MARKER + json.dumps(value))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            print("EDA site probe error: " + str(exc), file=sys.stderr)
            sys.exit(2)
    else:
        sys.exit(main())
