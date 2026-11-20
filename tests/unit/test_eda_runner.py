"""Execution, configuration, and transport contracts using controlled processes."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from tests.conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from verify_evidence import runtime_state_root  # noqa: E402  same lookup the runner uses

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
    assert not (tmp_path / ".rat").exists()  # a run before init leaves the folder uninitialized
    report = next((runtime_state_root(tmp_path) / "tool-runs").glob("*.result.json"))
    assert json.loads(report.read_text())["termination"] == termination


def test_timeout_kills_descendant_that_holds_stdout_after_parent_exits(tmp_path):
    command = f'''{sys.executable} -c 'import subprocess; subprocess.Popen(["sleep", "5"])' '''
    result = invoke(tmp_path, "run", "--timeout", "0.15", "--shell-command", command)
    assert result.returncode == 124


def test_wall_timeout_survives_closed_output(tmp_path):
    tool = executable(tmp_path / "licence_wait", "#!/bin/sh\nexec 1>&- 2>&-\nexec sleep 5\n")
    result = invoke(tmp_path, "run", "--timeout", "0.15", "--shell-command", str(tool))
    assert result.returncode == 124
    assert "RAT_TIMEOUT" in result.stdout


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
    skips=[".rat", ".git", ".claude"]
    if "--exclude=/experiment/" in args: skips.append("experiment")
    shutil.copytree(src,dst,dirs_exist_ok=True,ignore=shutil.ignore_patterns(*skips) if any(a.startswith("--exclude") for a in args) else None)
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
    report = next((runtime_state_root(root) / "remote-runs").glob("*/result.json"))
    assert json.loads(report.read_text())["exit_code"] == job_exit


def test_remote_submission_without_exit_artifact_is_inconclusive(remote_project):
    root, remote, wrapper, env = remote_project
    (root / "rat_config.json").write_text(json.dumps({"execution": {
        "backend": "lsf", "host": "fixture-host", "workspace": str(remote), "outputs": []}}))
    result = invoke(root, "dispatch", "--wrapper", str(wrapper), env={**env, "FAKE_SKIP_JOB": "1"})
    assert result.returncode == 3, result.stdout + result.stderr


def test_experiment_namespace_before_init(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    env = {**os.environ, "RAT_EXPERIMENT_ID": "sweep-1"}
    def output(value, **updates):
        return subprocess.run([sys.executable, str(RUNNER), "experiment-output", "--root", str(tmp_path), "--", value],
                              env={**env, **updates}, capture_output=True, text=True)

    directory = tmp_path / "experiment/sweep-1"
    for value in ("sim/build", "experiment/sweep-1/sim/build", str(directory / "sim/build")):
        assert output(value).stdout.strip() == str(directory / "sim/build")
    assert subprocess.run(["git", "-C", str(tmp_path), "check-ignore", "-q", "experiment/sweep-1/sim/build"]).returncode == 0
    (directory / "escape").symlink_to(tmp_path)
    for value in ("../other", "/tmp/build", "experiment/other/seed", "escape/build"):
        assert output(value).returncode == 2
    assert output(".", RAT_EXPERIMENT_ID="../bad").returncode == 2


def test_parallel_experiments_separate_workspaces_and_allow_sequential_reuse(remote_project):
    root, remote, wrapper, env = remote_project
    (root / "rat_config.json").write_text(json.dumps({"execution": {
        "backend": "ssh", "host": "fixture", "workspace": str(remote), "outputs": ["out"]}}))
    wrapper.write_text('''#!/bin/sh
set -eu
test "$RAT_EXPERIMENT_ACTIVE" = 1
test -z "${RAT_EXPERIMENT_ID:-}"
test ! -d "$RAT_PROJECT_ROOT/experiment"
mkdir -p out
printf '%s' "$1" >> out/steps
while [ -n "${FIXTURE_RELEASE:-}" ] && [ ! -f "$FIXTURE_RELEASE" ]; do sleep .02; done
''')
    command = [sys.executable, str(RUNNER), "dispatch", "--root", str(root), "--wrapper", str(wrapper), "--"]
    release = root.parent / "continue"
    def start(name, label):
        return subprocess.Popen([*command, label], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, env={**os.environ, **env, "RAT_EXPERIMENT_ID": name,
                                                "FIXTURE_RELEASE": str(release)})

    first, other = start("left", "a"), start("right", "b")
    try:
        deadline = time.monotonic() + 10
        while len(list(remote.glob(".rat/experiments/*/work/out/steps"))) < 2 and time.monotonic() < deadline:
            time.sleep(.025)
        assert len(list(remote.glob(".rat/experiments/*/work/out/steps"))) == 2
        duplicate = start("left", "bad")
        assert "experiment already running" in duplicate.communicate(timeout=4)[1]
        assert duplicate.returncode == 2
    finally:
        release.touch()
        for process in (first, other):
            stdout, stderr = process.communicate(timeout=7)
            assert process.returncode == 0, stdout + stderr
    later = start("left", "c")
    stdout, stderr = later.communicate(timeout=7)
    assert later.returncode == 0, stdout + stderr
    assert (root / "experiment/left/out/steps").read_text() == "ac"
    assert (root / "experiment/right/out/steps").read_text() == "b"
    assert not (root / "out").exists()
    assert not list(remote.glob(".rat/experiments/*/active"))


def test_missing_remote_job_status_keeps_experiment_reserved(remote_project):
    root, remote, wrapper, env = remote_project
    (root / "rat_config.json").write_text(json.dumps({"execution": {
        "backend": "lsf", "host": "fixture", "workspace": str(remote), "outputs": []}}))
    env = {**env, "RAT_EXPERIMENT_ID": "pending"}
    missing = invoke(root, "dispatch", "--wrapper", str(wrapper), env={**env, "FAKE_SKIP_JOB": "1"})
    assert missing.returncode == 3 and "reservation retained" in missing.stderr
    retry = invoke(root, "dispatch", "--wrapper", str(wrapper), env=env)
    assert retry.returncode == 2 and "could not reserve" in retry.stderr


def test_namespaced_evidence_uses_fetched_logs_and_original_inputs(remote_project):
    root, remote, wrapper, env = remote_project
    (root / "rat_config.json").write_text(json.dumps({"execution": {
        "backend": "ssh", "host": "fixture", "workspace": str(remote)}}))
    (root / "design.v").write_text("module design; endmodule")
    wrapper = executable(wrapper.with_name("run_sim.sh"), '''#!/bin/bash
set -eu
out="$2"
mkdir -p "$out"
echo PASS > "$out/sim.log"
if [[ "$3" = simulate ]]; then
    base="$RAT_RUNTIME_HELPERS/verify_evidence.py"
    snapshot=$(python3 "$base" begin --root "$PWD" --outdir "$out" --tool xrun --top design --source design.v)
    python3 "$base" finish --snapshot "$snapshot" --exit-code 0 --log "$out/sim.log"
fi
''')
    env = {**os.environ, **env, "RAT_EXPERIMENT_ID": "trial"}
    destination = root / "experiment/trial/custom"
    command = [sys.executable, str(RUNNER), "dispatch", "--root", str(root), "--wrapper", str(wrapper),
               "--", "--outdir", str(destination)]
    run = subprocess.run([*command, "simulate"], cwd=root, env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr + run.stdout
    index = runtime_state_root(root) / "state/verify-evidence.json"
    record, = json.loads(index.read_text())["runs"]
    assert record["verdict"] == "PASS" and record["experiment_id"] == "trial"
    assert list(record["sources"]) == [str(root / "design.v")]
    assert record["log"] == str(destination / "sim.log")
    assert not (root / "custom").exists()
    stale = subprocess.run([*command, "skip"], cwd=root, env=env, capture_output=True, text=True)
    assert stale.returncode == 3
    assert len(json.loads(index.read_text())["runs"]) == 1


def test_remote_compile_and_run_only_reuse_private_build_before_init(remote_project, monkeypatch):
    root, remote, _, env = remote_project
    remote = remote.with_name("server")
    tools = root.parent / "bin"
    compiler = executable(tools / "iverilog", '''#!/bin/sh
test "$VENDOR_READY" = 1 || exit 15
while [ "$1" != -o ]; do shift; done
printf 'compiled\n' > "$2"
''')
    executable(tools / "vvp", '#!/bin/sh\ntest -s "$1" && echo RAT_SIM_PASS\n')
    data = root.parent / "machine"
    data.mkdir()
    (data / "env-config.json").write_text(json.dumps({
        "execution": {"backend": "ssh", "workspace": str(remote), "host": "fixture"},
        "preferences": {"simulator": "iverilog"},
        "tools": {"simulators": {"iverilog": {"path": str(compiler), "env_source": "export VENDOR_READY=1",
                                             "probe": {"output": "fixture-only raw report"}}}},
    }))
    (root / "sample.v").write_text("module sample; endmodule")
    (root / "sim").mkdir()
    (root / "sim/maintained-test-input").write_text("source")
    env = {**os.environ, **env, "RAT_PROJECT_ROOT": str(root), "RAT_EXPERIMENT_ID": "split",
           "RAT_DATA_DIR": str(data)}
    for step in ("--compile-only", "--run-only"):
        result = subprocess.run(["bash", str(RUNNER.with_name("run_sim.sh")), "--top", "sample", step, "sample.v"],
                                cwd=root, env=env, text=True, capture_output=True, timeout=25)
        assert result.returncode == 0, result.stderr + result.stdout
    destination = root / "experiment/split"
    assert (destination / "sim/build/sample").is_file()
    assert not (destination / "sim/maintained-test-input").exists()
    assert not (root / "sim/build").exists() and not (root / "rat_config.json").exists()
    assert not list(root.rglob(".rat"))  # not even inside experiment/<id>/
    monkeypatch.setenv("RAT_DATA_DIR", env["RAT_DATA_DIR"])  # resolve where the runs wrote
    index = runtime_state_root(root) / "state/verify-evidence.json"
    assert [item["verdict"] for item in json.loads(index.read_text())["runs"]] == ["COMPILED", "PASS"]
    assert not list(root.rglob("dispatch-config.json"))
    snapshot, *_ = remote.rglob("dispatch-config.json")
    assert "fixture-only raw report" not in snapshot.read_text()


@pytest.mark.parametrize("relative", [".", ".."])
def test_dispatch_never_mirrors_a_home_directory_or_its_parent(tmp_path, relative):
    data = tmp_path / "data"
    data.mkdir()
    (data / "env-config.json").write_text(json.dumps({"execution": {
        "backend": "ssh", "host": "eda.example.invalid", "workspace": "/remote/ws"}}))
    home = tmp_path / "home"
    home.mkdir()
    root = (home / relative).resolve()
    before = sorted(root.rglob("*"))
    env = {**os.environ, "HOME": str(home), "RAT_DATA_DIR": str(data), "RAT_PROJECT_ROOT": str(root)}
    result = subprocess.run([sys.executable, str(RUNNER), "dispatch", "--root", str(root), "--wrapper", "run_sim.sh", "--"],
                            env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 2 and "home directory" in result.stderr
    assert sorted(root.rglob("*")) == before


@pytest.mark.parametrize("folder", ["scratch", ".config/scratch"])
def test_dispatch_mirrors_only_a_recognizable_project(tmp_path, folder):
    data = tmp_path / "data"
    data.mkdir()
    (data / "env-config.json").write_text(json.dumps({"execution": {
        "backend": "ssh", "host": "eda.example.invalid", "workspace": "/remote/ws"}}))
    home = tmp_path / "home"
    root = home / folder
    root.mkdir(parents=True)
    env = {**os.environ, "HOME": str(home), "RAT_DATA_DIR": str(data)}
    env.pop("RAT_PROJECT_ROOT", None)
    result = subprocess.run([sys.executable, str(RUNNER), "dispatch", "--root", str(root), "--wrapper", "run_sim.sh", "--"],
                            env=env, capture_output=True, text=True, timeout=20)
    assert result.returncode == 2
    assert ("hidden directory" if folder.startswith(".") else "project root") in result.stderr
    assert not any(root.iterdir())
