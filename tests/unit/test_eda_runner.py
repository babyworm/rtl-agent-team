"""Execution, configuration, and transport contracts using controlled processes."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT

RUNNER = REPO_ROOT / "scripts/eda_runner.py"


def executable(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)
    return path


def invoke(root, *arguments, env=None):
    return subprocess.run([sys.executable, str(RUNNER), *arguments, "--root", str(root)],
                          cwd=root, env={**os.environ, **(env or {})}, capture_output=True, text=True, timeout=15)


def test_configured_executable_and_environment_are_consumed(tmp_path):
    tool = executable(tmp_path / "vendor tools/check", '#!/bin/sh\nprintf "%s:%s\\n" "$SITE_VALUE" "$1"\n')
    (tmp_path / "rat_config.json").write_text(json.dumps({
        "execution": {"backend": "local"},
        "tools": {"lint": {"verilator": {"path": str(tool), "env_source": "export SITE_VALUE=ready"}}},
    }))
    result = invoke(tmp_path, "run", "--shell-command", "verilator --lint-only", env={"RAT_TOOL_CATEGORY": "lint"})
    assert result.returncode == 0, result.stderr
    assert "ready:--lint-only" in result.stdout


def test_failed_environment_does_not_execute_tool(tmp_path):
    tool = executable(tmp_path / "tool", '#!/bin/sh\ntouch "$RAT_PROJECT_ROOT/unexpected"\n')
    (tmp_path / "rat_config.json").write_text(json.dumps({"tools": {"lint": {
        "check": {"path": str(tool), "env_source": "exit 17"}}}}))
    result = invoke(tmp_path, "run", "--shell-command", "check")
    assert result.returncode == 17
    assert not (tmp_path / "unexpected").exists()


@pytest.mark.parametrize("flags,command,expected,termination", [
    (["--timeout", "0.15"], "sleep 5", 124, "TIMEOUT"),
    (["--stall", "0.15"], "printf hello; sleep 5", 125, "STALL"),
    ([], "sh -c 'exit 13'", 13, "exit"),
])
def test_process_results_and_limits_are_preserved(tmp_path, flags, command, expected, termination):
    result = invoke(tmp_path, "run", *flags, "--shell-command", command)
    assert result.returncode == expected, result.stderr
    report = next((tmp_path / ".rat/tool-runs").glob("*.result.json"))
    assert json.loads(report.read_text())["termination"] == termination


def test_timeout_kills_descendant_that_holds_stdout_after_parent_exits(tmp_path):
    command = f'''{sys.executable} -c 'import subprocess; subprocess.Popen(["sleep", "5"])' '''
    result = invoke(tmp_path, "run", "--timeout", "0.15", "--shell-command", command)
    assert result.returncode == 124


def test_docker_mount_preserves_absolute_project_paths(tmp_path):
    binary = executable(tmp_path / "bin/docker", '#!/usr/bin/env python3\nimport json,sys\nprint(json.dumps(sys.argv[1:]))\n')
    (tmp_path / "rat_config.json").write_text('{"execution":{"backend":"docker"}}')
    result = invoke(tmp_path, "run", "--shell-command", "verilator --version",
                    env={"PATH": str(binary.parent) + os.pathsep + os.environ["PATH"]})
    assert result.returncode == 0, result.stderr
    assert f"src={tmp_path},dst={tmp_path}" in result.stdout
    assert "HOME=/tmp" in result.stdout


@pytest.fixture
def remote_project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    remote = tmp_path / "remote project"
    tools = tmp_path / "bin"
    ssh = executable(tools / "ssh", '''#!/usr/bin/env python3
import base64, os, re, subprocess, sys
command = sys.argv[-1]
assert "\\n" not in command, "SSH command must support a tcsh login shell"
encoded=re.search(r"printf %s ([A-Za-z0-9+/=]+) \\| base64 -d",command)
script=base64.b64decode(encoded.group(1)).decode() if encoded else command
if os.environ.get("FAKE_SKIP_JOB") and command.startswith("sh -c") and "RAT_REMOTE_ACTIVE" in script:
    raise SystemExit(0)
raise SystemExit(subprocess.call(command, shell=True))
''')
    executable(tools / "rsync", '''#!/usr/bin/env python3
import shutil, sys
from pathlib import Path
args=sys.argv[1:]
source,destination=args[-2:]
if ":" in source: source=source.split(":",1)[1]
if ":" in destination: destination=destination.split(":",1)[1]
if "/./" in source:
    source,relative=source.split("/./",1)
    source=str(Path(source)/relative)
    destination=str(Path(destination)/relative)
src,dst=Path(source),Path(destination)
if not src.exists(): raise SystemExit(23)
if src.is_dir():
    dst.mkdir(parents=True,exist_ok=True)
    shutil.copytree(src,dst,dirs_exist_ok=True,ignore=shutil.ignore_patterns(".rat", ".git", ".claude") if any(a.startswith("--exclude") for a in args) else None)
else:
    dst.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(src,dst)
''')
    executable(tools / "bsub", '''#!/usr/bin/env python3
import subprocess,sys
args=sys.argv[1:]
while args and args[0].startswith("-"):
    option=args.pop(0)
    if option!="-K": args.pop(0)
print("Job <123> is submitted",flush=True)
subprocess.call(args)
raise SystemExit(0)
''')
    wrapper = executable(tmp_path / "test_wrapper.sh", '''#!/bin/bash
mkdir -p "$RAT_PROJECT_ROOT/out"
printf '%s\\n' "$1" > "$RAT_PROJECT_ROOT/out/mapped.txt"
exit "${FAKE_JOB_EXIT:-0}"
''')
    env = {"PATH": str(tools) + os.pathsep + os.environ["PATH"]}
    return root, remote, wrapper, env


@pytest.mark.parametrize("selected", ["ssh", "lsf"])
@pytest.mark.parametrize("job_exit", [0, 7])
def test_remote_wrapper_maps_inputs_fetches_outputs_and_uses_job_status(remote_project, selected, job_exit):
    root, remote, wrapper, env = remote_project
    (root / "rat_config.json").write_text(json.dumps({"execution": {
        "backend": selected, "host": "fixture-host", "workspace": str(remote), "outputs": ["out"]}}))
    result = subprocess.run([sys.executable, str(RUNNER), "dispatch", "--root", str(root),
                             "--wrapper", str(wrapper), "--", str(root / "rtl/input.sv")],
                            cwd=root, env={**os.environ, **env, "FAKE_JOB_EXIT": str(job_exit)},
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == job_exit, result.stdout + result.stderr
    assert (root / "out/mapped.txt").read_text().strip() == str(remote / "rtl/input.sv")
    report = next((root / ".rat/remote-runs").glob("*/result.json"))
    assert json.loads(report.read_text())["exit_code"] == job_exit


def test_remote_submission_without_exit_artifact_is_inconclusive(remote_project):
    root, remote, wrapper, env = remote_project
    (root / "rat_config.json").write_text(json.dumps({"execution": {
        "backend": "lsf", "host": "fixture-host", "workspace": str(remote), "outputs": []}}))
    result = invoke(root, "dispatch", "--wrapper", str(wrapper), env={**env, "FAKE_SKIP_JOB": "1"})
    assert result.returncode == 3, result.stdout + result.stderr
