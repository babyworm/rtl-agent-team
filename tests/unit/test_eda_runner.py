"""Execution, configuration, and transport contracts using controlled processes."""

import json
import re
import os
from pathlib import Path
import shutil
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
    # Without an ID the run gets one; results land only under experiment/<id>/.
    experiment = re.search(r"Experiment ID: (\S+)", result.stderr).group(1)
    work = remote / ".rat/experiments" / experiment / "work"
    assert (root / "experiment" / experiment / "out/mapped.txt").read_text().strip() == str(work / "rtl/input.sv")
    assert not (root / "out").exists()
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
    # Apple's system Python keeps bytecode under ~/Library/Caches; the runner itself writes nothing there.
    env = {**os.environ, "HOME": str(home), "RAT_DATA_DIR": str(data), "RAT_PROJECT_ROOT": str(root),
           "PYTHONDONTWRITEBYTECODE": "1"}
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


@pytest.mark.skipif(not (shutil.which("rsync") and shutil.which("git")), reason="needs rsync and git")
def test_transport_sends_inputs_only_and_keeps_results_in_the_experiment(tmp_path):
    tools = tmp_path / "bin"
    executable(tools / "ssh", '''#!/usr/bin/env python3
import subprocess, sys
args = sys.argv[1:]
while args and args[0].startswith("-"):
    if args.pop(0) == "--":
        break
args.pop(0)  # host; the rest runs locally as the remote command
raise SystemExit(subprocess.call(args[0], shell=True) if len(args) == 1 else subprocess.call(args))
''')
    root, remote = tmp_path / "project", tmp_path / "remote"
    for folder in ("rtl", "build", "vec"):
        (root / folder).mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("build/\nvec/\n")
    (root / "rtl/dut.sv").write_text("module dut; endmodule\n")
    (root / "build/huge.bin").write_bytes(b"0" * 4096)
    (root / "vec/in.hex").write_text("00\n")
    (root / "rat_config.json").write_text(json.dumps({"execution": {
        "backend": "ssh", "host": "fixture-host", "workspace": str(remote), "inputs": ["vec/**"]}}))
    wrapper = executable(root / "tool.sh", '''#!/usr/bin/env bash
set -e
test -f vec/in.hex && test -f rtl/dut.sv && test ! -e build   # inputs arrived, build outputs did not
mkdir -p "$2"
echo PASS > "$2/report.log"
echo wave > "$2/run.fsdb"
''')
    before = sorted(path for path in root.rglob("*") if ".git" not in path.parts)
    env = {**os.environ, "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}"}
    env.pop("RAT_EXPERIMENT_ID", None)
    result = subprocess.run([sys.executable, str(RUNNER), "dispatch", "--root", str(root), "--wrapper", str(wrapper),
                             "--", "--outdir", "out"], cwd=root, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Sending 5 files" in result.stderr  # .gitignore, rtl/dut.sv, rat_config.json, tool.sh, vec/in.hex
    experiment = re.search(r"Experiment ID: (\S+)", result.stderr).group(1)
    results = root / "experiment" / experiment / "out"
    assert (results / "report.log").read_text() == "PASS\n"
    assert not (results / "run.fsdb").exists()  # heavy results stay on the host
    after = sorted(path for path in root.rglob("*") if ".git" not in path.parts and "experiment" not in path.parts)
    assert after == before  # nothing outside experiment/<id>/ changed

    pulled = subprocess.run([sys.executable, str(RUNNER), "fetch", "--root", str(root), "--experiment", experiment,
                             "out/run.fsdb"], env=env, capture_output=True, text=True, timeout=60)
    assert pulled.returncode == 0, pulled.stderr
    assert (results / "run.fsdb").read_text() == "wave\n"
    escape = subprocess.run([sys.executable, str(RUNNER), "fetch", "--root", str(root), "--experiment", experiment,
                             "../outside"], env=env, capture_output=True, text=True, timeout=60)
    assert escape.returncode == 2 and "project-relative" in escape.stderr


def test_extra_inputs_must_stay_inside_the_project(tmp_path):
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from eda_runner import upload_manifest
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for pattern in ("../secret/**", "/etc/passwd", ""):
        with pytest.raises(ValueError):
            upload_manifest(tmp_path, (), [pattern])
    outside = tmp_path.parent / "outside-data"
    outside.mkdir(exist_ok=True)
    (outside / "key").write_text("secret")
    (tmp_path / "linked").symlink_to(outside)
    assert "linked/key" not in upload_manifest(tmp_path, (), ["linked/**"])


def test_clean_removes_finished_experiments_on_both_sides(remote_project):
    root, remote, _, env = remote_project
    (root / "rat_config.json").write_text(json.dumps({"execution": {
        "backend": "ssh", "host": "fixture-host", "workspace": str(remote)}}))
    experiments = remote / ".rat/experiments"
    for name in ("done", "running", "other"):
        (experiments / name / "work").mkdir(parents=True)
    (experiments / "running/active").mkdir()
    for name in ("done", "running", "local-only"):
        (root / "experiment" / name).mkdir(parents=True)

    def clean(*flags):
        return subprocess.run([sys.executable, str(RUNNER), "clean", "--root", str(root), *flags],
                              env={**os.environ, **env}, capture_output=True, text=True, timeout=30)

    named = clean("--experiment", "done")
    assert named.returncode == 0, named.stderr
    assert sorted(p.name for p in experiments.iterdir()) == ["other", "running"]
    assert (root / "experiment/done").is_dir()  # local results stay without --local
    everything = clean("--all", "--local")
    assert everything.returncode == 0 and "kept running: running" in everything.stderr
    assert [p.name for p in experiments.iterdir()] == ["running"]
    assert [p.name for p in (root / "experiment").iterdir()] == ["running"]
    assert clean("--experiment", "../x").returncode == 2
    assert clean().returncode == 2  # nothing named, no --all


@pytest.mark.skipif(not (shutil.which("rsync") and shutil.which("git")), reason="needs rsync and git")
@pytest.mark.parametrize("mode", ["merge", "sync"])
def test_in_place_results_never_touch_sent_sources(tmp_path, mode):
    tools = tmp_path / "bin"
    executable(tools / "ssh", '''#!/usr/bin/env python3
import subprocess, sys
args = sys.argv[1:]
while args and args[0].startswith("-"):
    if args.pop(0) == "--":
        break
args.pop(0)
raise SystemExit(subprocess.call(args[0], shell=True) if len(args) == 1 else subprocess.call(args))
''')
    root, remote = tmp_path / "project", tmp_path / "remote"
    (root / "sim/out").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    (root / ".gitignore").write_text("sim/out/\n")
    (root / "sim/tb.sv").write_text("module tb; endmodule // local edit\n")
    (root / "sim/out/stale.log").write_text("old\n")
    (root / "rat_config.json").write_text(json.dumps({"execution": {
        "backend": "ssh", "host": "fixture-host", "workspace": str(remote), "results": mode}}))
    wrapper = executable(root / "tool.sh", '''#!/usr/bin/env bash
set -e
echo "// remote copy" > sim/tb.sv     # the remote copy of a source changes
mkdir -p sim/out                      # ignored outputs are not sent, so the run creates them
echo PASS > sim/out/report.log
''')
    env = {**os.environ, "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}"}
    env.pop("RAT_EXPERIMENT_ID", None)
    result = subprocess.run([sys.executable, str(RUNNER), "dispatch", "--root", str(root), "--wrapper", str(wrapper), "--"],
                            cwd=root, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Experiment ID" not in result.stderr and not (root / "experiment").exists()
    assert (root / "sim/out/report.log").read_text() == "PASS\n"
    assert (root / "sim/tb.sv").read_text() == "module tb; endmodule // local edit\n"
    assert (root / "sim/out/stale.log").exists() == (mode == "merge")


def test_in_place_results_need_git(remote_project):
    root, remote, wrapper, env = remote_project
    (root / "rat_config.json").write_text(json.dumps({"execution": {
        "backend": "ssh", "host": "fixture-host", "workspace": str(remote), "results": "sync"}}))
    result = invoke(root, "dispatch", "--wrapper", str(wrapper), env=env)
    assert result.returncode == 2 and "needs a Git work tree" in result.stderr


# verify-run: a project's own runner, unchanged, recorded as content-bound evidence.
EVIDENCE = REPO_ROOT / "scripts/verify_evidence.py"


def verify_run(root, *arguments, env=None):
    return subprocess.run([sys.executable, str(RUNNER), "verify-run", "--root", str(root), *arguments],
                          cwd=root, env={**os.environ, **(env or {})}, capture_output=True, text=True, timeout=30)


def project_runner(root, body):
    return executable(root / "regress.sh", "#!/bin/sh\n" + body)


def add_rtl(root):
    (root / ".rat/state").mkdir(parents=True, exist_ok=True)
    (root / "rtl").mkdir(exist_ok=True)
    (root / "rtl/top.sv").write_text("module top; endmodule\n")
    (root / "rtl/files.f").write_text("top.sv\n")
    return root


@pytest.fixture
def runner_project(tmp_path):
    return add_rtl(tmp_path / "project")


def pending_files(root):
    track = root / ".rat/state/rtl-modified-files.txt"
    track.write_text("rtl/top.sv\n")
    result = subprocess.run([sys.executable, str(EVIDENCE), "unverified", "--root", str(root), "--track", str(track)],
                            capture_output=True, text=True, timeout=15)
    return result.stdout.split()


def last_record(root):
    return json.loads((root / ".rat/state/verify-evidence.json").read_text())["runs"][-1]


def test_verify_run_records_a_project_runner_the_gate_accepts(runner_project):
    from tests.conftest import run_hook
    root = runner_project
    regress = project_runner(root, 'echo "TESTS=2 PASS=2 FAIL=0"\n')
    result = verify_run(root, "-f", "rtl/files.f", "--", str(regress))
    assert result.returncode == 0, result.stdout + result.stderr
    record = last_record(root)
    assert (record["verdict"], record["origin"], record["argv"]) == ("PASS", "verify-run", [str(regress)])
    assert pending_files(root) == []
    # The user sees which runner cleared Rule 5; a runner can only print a token so much.
    assert run_hook(REPO_ROOT / "hooks/rtl-verify-stop-gate.sh", {"cwd": str(root)}) == {
        "systemMessage": "Info> Rule 5 cleared for 1 RTL file(s) by verify-run: regress.sh."}
    assert run_hook(REPO_ROOT / "hooks/rtl-verify-stop-gate.sh", {"cwd": str(root)}) == {"continue": True}


@pytest.mark.parametrize("body,code,verdict", [
    ('echo "*E,ELBERR: elaboration failed"\n', 3, "FAIL"),
    ('echo "regression finished"\n', 3, "INCONCLUSIVE"),
    ('echo "TESTS=1 PASS=1 FAIL=0"; exit 5\n', 5, "FAIL"),
])
def test_verify_run_judges_the_runner_output(runner_project, body, code, verdict):
    result = verify_run(runner_project, "-f", "rtl/files.f", "--", str(project_runner(runner_project, body)))
    assert result.returncode == code, result.stdout + result.stderr
    assert last_record(runner_project)["verdict"] == verdict
    assert pending_files(runner_project) == ["rtl/top.sv"]


def test_summary_file_must_be_written_by_this_run(runner_project):
    root = runner_project
    summary = root / "results/regress.txt"
    summary.parent.mkdir()
    summary.write_text("TESTS=1 PASS=1 FAIL=0\n")  # left by an earlier run
    stale = verify_run(root, "-f", "rtl/files.f", "--log", "results/regress.txt", "--",
                       str(project_runner(root, "true\n")))
    assert stale.returncode == 3
    record = last_record(root)
    assert record["verdict"] == "INCONCLUSIVE" and "results/regress.txt" in record["unbound_reason"]
    fresh = project_runner(root, 'printf "TESTS=23 PASS=23 FAIL=0\\n" > results/regress.txt\n')
    result = verify_run(root, "-f", "rtl/files.f", "--log", "results/regress.txt", "--", str(fresh))
    assert result.returncode == 0, result.stdout + result.stderr
    summary.write_text("overwritten by a later run\n")
    assert pending_files(root) == []  # the evidence keeps its own copy of the summary


def test_failure_in_the_console_overrides_a_passing_summary(runner_project):
    root = runner_project
    (root / "results").mkdir()
    body = 'echo "*F,INTERR: simulator crashed"\nprintf "TESTS=1 PASS=1 FAIL=0\\n" > results/regress.txt\n'
    result = verify_run(root, "-f", "rtl/files.f", "--log", "results/regress.txt", "--", str(project_runner(root, body)))
    assert result.returncode == 3
    assert last_record(root)["verdict"] == "FAIL"


def test_local_edit_during_the_run_is_inconclusive(runner_project):
    body = 'echo "module extra; endmodule" >> rtl/top.sv\necho "TESTS=1 PASS=1 FAIL=0"\n'
    result = verify_run(runner_project, "-f", "rtl/files.f", "--", str(project_runner(runner_project, body)))
    assert result.returncode == 3
    assert last_record(runner_project)["verdict"] == "INCONCLUSIVE"


def test_remote_manifest_binds_the_copy_the_host_ran(remote_project):
    root, remote, _, env = remote_project
    add_rtl(root)
    shutil.copytree(root / "rtl", remote / "rtl")  # the project's own runner synchronized it
    flags = ["-f", "rtl/files.f", "--remote-host", "fixture", "--remote-root", str(remote), "--",
             str(project_runner(root, 'echo "TESTS=4 PASS=4 FAIL=0"\n'))]
    passed = verify_run(root, *flags, env=env)
    assert passed.returncode == 0, passed.stdout + passed.stderr
    record = last_record(root)
    assert record["remote_host"] == "fixture" and record["remote_root"] == str(remote)
    assert len(record["remote_manifest_sha256"]) == 64
    assert pending_files(root) == []
    from tests.conftest import run_hook
    notice = run_hook(REPO_ROOT / "hooks/rtl-verify-stop-gate.sh", {"cwd": str(root)})["systemMessage"]
    assert notice.endswith(" on fixture.") and "regress.sh" in notice
    pending_files(root)  # track again for the checks below
    (remote / "rtl/top.sv").write_text("module stale; endmodule\n")
    stale = verify_run(root, *flags, env=env)
    assert stale.returncode == 3
    assert "differs on fixture: rtl/top.sv" in last_record(root)["unbound_reason"]
    (remote / "rtl/top.sv").unlink()
    missing = verify_run(root, *flags, env=env)
    assert missing.returncode == 3
    assert "missing on fixture: rtl/top.sv" in last_record(root)["unbound_reason"]


def test_failed_runner_skips_the_remote_step(remote_project):
    root, remote, _, env = remote_project
    add_rtl(root)
    result = verify_run(root, "-f", "rtl/files.f", "--remote-host", "fixture", "--remote-root", str(remote / "absent"),
                        "--", str(project_runner(root, "exit 4\n")), env=env)
    assert result.returncode == 4
    record = last_record(root)
    assert record["verdict"] == "FAIL"
    assert "remote_manifest_sha256" not in record and "unbound_reason" not in record


def test_live_run_lets_the_gate_wait(runner_project):
    root = runner_project
    release = root / "release"
    regress = project_runner(root, f'while [ ! -f "{release}" ]; do sleep 0.05; done\necho "TESTS=1 PASS=1 FAIL=0"\n')
    process = subprocess.Popen([sys.executable, str(RUNNER), "verify-run", "--root", str(root), "-f", "rtl/files.f",
                                "--", str(regress)], cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        track = root / ".rat/state/rtl-modified-files.txt"
        track.write_text("rtl/top.sv\n")
        deadline = time.time() + 10
        while not list((root / ".rat/state").glob("verify-runs/*.json")) and time.time() < deadline:
            time.sleep(0.05)
        waiting = subprocess.run([sys.executable, str(EVIDENCE), "pending", "--root", str(root), "--track", str(track)],
                                 timeout=15)
        assert waiting.returncode == 0
    finally:
        release.touch()
        assert process.wait(timeout=20) == 0


@pytest.mark.parametrize("flags", [
    ["--", "RUNNER"],
    ["-f", "rtl/files.f"],
    ["-f", "rtl/files.f", "--remote-host", "fixture", "--", "RUNNER"],
    ["-f", "rtl/files.f", "--remote-host", "fixture", "--remote-root", "relative/dir", "--", "RUNNER"],
    ["-f", "rtl/files.f", "--remote-host", "bad host", "--remote-root", "/remote/ws", "--", "RUNNER"],
    ["-f", "rtl/files.f", "--", "no-such-runner-anywhere"],
    ["-f", "rtl/files.f", "--", "echo", "RAT_SIM_PASS"],
    ["-f", "rtl/files.f", "--", "printf", "RAT_SIM_PASS"],
])
def test_invalid_requests_run_nothing_and_leave_no_record(runner_project, flags):
    regress = project_runner(runner_project, 'touch ran\necho RAT_SIM_PASS\n')
    result = verify_run(runner_project, *[str(regress) if value == "RUNNER" else value for value in flags])
    assert result.returncode == 2, result.stdout + result.stderr
    assert "EDA execution error" in result.stderr or "usage" in result.stderr
    assert not (runner_project / "ran").exists()
    assert not (runner_project / ".rat/state/verify-runs").exists()


def test_a_command_that_only_prints_the_token_is_refused(runner_project):
    result = verify_run(runner_project, "-f", "rtl/files.f", "--", "echo", "RAT_SIM_PASS")
    assert result.returncode == 2 and "runs no simulation" in result.stderr


def test_remote_hashing_covers_project_files_only(runner_project, tmp_path):
    outside = tmp_path / "outside.sv"
    outside.write_text("module outside; endmodule\n")
    result = verify_run(runner_project, "--source", str(outside), "--remote-host", "fixture",
                        "--remote-root", "/remote/ws", "--", str(project_runner(runner_project, "true\n")))
    assert result.returncode == 2 and "outside the project" in result.stderr
    assert not (runner_project / ".rat/state/verify-runs").exists()


def test_remote_filelists_must_stay_project_relative(runner_project):
    (runner_project / "rtl/files.f").write_text(str(runner_project / "rtl/top.sv") + "\n")
    result = verify_run(runner_project, "-f", "rtl/files.f", "--remote-host", "fixture", "--remote-root", "/remote/ws",
                        "--", str(project_runner(runner_project, "true\n")))
    assert result.returncode == 2 and "project-relative" in result.stderr


def test_only_documented_completion_lines_pass(runner_project):
    result = verify_run(runner_project, "-f", "rtl/files.f", "--",
                        str(project_runner(runner_project, 'echo "PASS: lint clean"\necho "TEST PASSED"\n')))
    assert result.returncode == 3
    assert last_record(runner_project)["verdict"] == "INCONCLUSIVE"


def test_editing_the_runner_afterwards_voids_its_evidence(runner_project):
    regress = project_runner(runner_project, "echo RAT_SIM_PASS\n")
    assert verify_run(runner_project, "-f", "rtl/files.f", "--", str(regress)).returncode == 0
    assert pending_files(runner_project) == []
    regress.write_text("#!/bin/sh\necho RAT_SIM_PASS  # never simulates\n")
    assert pending_files(runner_project) == ["rtl/top.sv"]


def test_a_summary_copied_back_from_an_earlier_run_is_inconclusive(runner_project):
    root = runner_project
    (root / "results").mkdir()
    old = root / "results/previous.txt"
    old.write_text("TESTS=23 PASS=23 FAIL=0\n")
    os.utime(old, (1577836800, 1577836800))  # 2020-01-01, as rsync -a keeps the host's time
    body = "rm -f results/regress.txt\ncp -p results/previous.txt results/regress.txt\n"
    result = verify_run(root, "-f", "rtl/files.f", "--log", "results/regress.txt", "--", str(project_runner(root, body)))
    assert result.returncode == 3
    assert "older time" in last_record(root)["unbound_reason"]


def test_runner_runs_from_the_project_root(runner_project, tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    regress = project_runner(runner_project, 'printf "TESTS=1 PASS=1 FAIL=0\\n" > results.txt\n')
    result = subprocess.run([sys.executable, str(RUNNER), "verify-run", "--root", str(runner_project), "-f",
                             "rtl/files.f", "--log", "results.txt", "--", "./regress.sh"],
                            cwd=elsewhere, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert (runner_project / "results.txt").is_file() and not (elsewhere / "results.txt").exists()
    assert regress.is_file()


@pytest.mark.parametrize("case", ["no-ssh-client", "remote-root-missing"])
def test_a_failed_remote_step_finishes_the_record_as_inconclusive(remote_project, case):
    root, remote, _, env = remote_project
    add_rtl(root)
    if case == "no-ssh-client":  # keep only ps, which process identity needs where /proc is absent
        tools = root / "tools-without-ssh"
        tools.mkdir()
        (tools / "ps").symlink_to(shutil.which("ps"))
        env = {**env, "PATH": str(tools)}
    target = remote / "absent" if case == "remote-root-missing" else remote
    result = verify_run(root, "-f", "rtl/files.f", "--remote-host", "fixture", "--remote-root", str(target), "--",
                        str(project_runner(root, "echo RAT_SIM_PASS\n")), env=env)
    assert result.returncode == 3, result.stdout + result.stderr
    record = last_record(root)
    assert record["verdict"] == "INCONCLUSIVE" and "hashing the inputs on fixture failed" in record["unbound_reason"]
    runs = [json.loads(path.read_text()) for path in (root / ".rat/state/verify-runs").glob("*.json")]
    assert runs and all(run["verdict"] != "RUNNING" for run in runs)


def test_uvm_library_headers_stay_local_in_the_remote_check(remote_project, tmp_path):
    root, remote, _, env = remote_project
    add_rtl(root)
    uvm = tmp_path / "uvm"
    (uvm / "src").mkdir(parents=True)
    (uvm / "src/uvm_macros.svh").write_text("`define UVM_FIXTURE\n")
    (root / "rtl/top.sv").write_text('`include "uvm_macros.svh"\nmodule top; endmodule\n')
    shutil.copytree(root / "rtl", remote / "rtl")
    result = verify_run(root, "-f", "rtl/files.f", "--remote-host", "fixture", "--remote-root", str(remote), "--",
                        str(project_runner(root, "echo RAT_SIM_PASS\n")), env={**env, "UVM_HOME": str(uvm)})
    assert result.returncode == 0, result.stdout + result.stderr
    record = last_record(root)
    assert str((uvm / "src/uvm_macros.svh").resolve()) in record["sources"]  # still bound locally
    assert "uvm_macros" not in (Path(record["outdir"]) / "remote-manifest.txt").read_text()


def test_machine_verification_settings_apply_without_project_config(tmp_path):
    (Path(os.environ["RAT_DATA_DIR"]) / "env-config.json").write_text(
        json.dumps({"verification": {"stop_gate": "notify"}}))
    assert invoke(tmp_path, "get", "--key", "verification.stop_gate").stdout.strip() == "notify"
    (tmp_path / "rat_config.json").write_text("{}")  # a project configuration owns its settings
    assert invoke(tmp_path, "get", "--key", "verification.stop_gate").stdout.strip() == ""


def test_machine_verification_settings_apply_with_a_default_site(tmp_path):
    data = Path(os.environ["RAT_DATA_DIR"])
    (data / "sites").mkdir(exist_ok=True)
    (data / "sites/lab.json").write_text(json.dumps({"measured_at": 1, "home": "/home/fixture", "tools": {},
                                                     "execution": {"backend": "ssh", "host": "example.invalid"}}))
    (data / "env-config.json").write_text(json.dumps({"default_site": "lab", "verification": {"stop_gate": "off"}}))
    result = invoke(tmp_path, "get", "--key", "verification.stop_gate")
    assert result.stdout.strip() == "off", result.stderr


# Remote output paths and the rsync variants (GNU rsync 3, GNU 2.6.9, macOS openrsync).
import eda_runner  # noqa: E402


@pytest.mark.parametrize("value,expected", [("sim/out/", "sim/out"), ("./sim/out", "sim/out"),
                                            ("sim//out", "sim/out"), ("out", "out")])
def test_outputs_are_kept_in_normal_form(value, expected):
    assert eda_runner.relative_output(value) == expected


@pytest.mark.parametrize("value", ["", ".", "./", "./.", ".//", "/abs/out", "../up", "sim/../..",
                                   ".git", ".git/hooks", ".rat/state", ".claude", ".rtl-agent-team"])
def test_root_absolute_and_reserved_outputs_are_refused(value):
    with pytest.raises(ValueError):
        eda_runner.relative_output(value)


@pytest.mark.parametrize("features", [(True, True), (False, True), (False, False)], ids=["gnu3", "gnu2.6.9", "openrsync"])
def test_relative_fetch_targets_the_output_path_for_every_rsync(features, monkeypatch, tmp_path):
    import shlex
    monkeypatch.setattr(eda_runner, "rsync_features", lambda rsync: features)
    value = eda_runner.relative_output("sim/out/")
    options, source, target, prefix = eda_runner.rsync_relative("/remote ws", value, tmp_path)
    if features[1]:
        assert (options, source, target, prefix) == (["--relative"], "/remote ws/./sim/out", tmp_path, "")
    else:  # rsync copies sim/out itself into target/, so it lands in tmp_path/sim/out
        assert (options, source, target, prefix) == ([], "/remote ws/sim/out", tmp_path / "sim", "sim/")
    argv, operand = eda_runner.rsync_transport([], *options)
    assert ("--protect-args" in argv) == features[0]
    assert operand("host", source) == "host:" + (source if features[0] else shlex.quote(source))


@pytest.mark.skipif(shutil.which("rsync") is None, reason="needs a real rsync")
def test_fetch_with_the_hosts_real_rsync_lands_results_at_their_path(tmp_path):
    # The real rsync on PATH (GNU on Linux, openrsync on macOS) over an ssh that runs the
    # "remote" command locally, as a login shell would: the path below has a space and a quote.
    tools = tmp_path / "bin"
    executable(tools / "ssh", '#!/bin/sh\nshift\nexec /bin/sh -c "$*"\n')
    remote = tmp_path / "remote ws'1"
    (remote / "sim/out").mkdir(parents=True)
    (remote / "sim/out/report.log").write_text("TESTS=1 PASS=1 FAIL=0\n")
    root = tmp_path / "project"
    run = root / ".rat/remote-runs/run-1"
    run.mkdir(parents=True)
    (run / "result.json").write_text(json.dumps({"experiment": "exp-1", "host": "fixture",
                                                 "remote_outputs": str(remote)}))
    result = subprocess.run([sys.executable, str(RUNNER), "fetch", "--root", str(root), "--experiment", "exp-1",
                             "sim/out/"], cwd=root, capture_output=True, text=True, timeout=60,
                            env={**os.environ, "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}"})
    assert result.returncode == 0, result.stdout + result.stderr
    assert (root / "experiment/exp-1/sim/out/report.log").read_text() == "TESTS=1 PASS=1 FAIL=0\n"
    assert not (root / "experiment/exp-1/sim/report.log").exists()


@pytest.mark.skipif(shutil.which("rsync") is None, reason="needs a real rsync")
def test_a_failed_fetch_leaves_no_empty_folders(tmp_path):
    tools = tmp_path / "bin"
    executable(tools / "ssh", '#!/bin/sh\nshift\nexec /bin/sh -c "$*"\n')
    root = tmp_path / "project"
    run = root / ".rat/remote-runs/run-1"
    run.mkdir(parents=True)
    (run / "result.json").write_text(json.dumps({"experiment": "exp-2", "host": "fixture",
                                                 "remote_outputs": str(tmp_path / "remote")}))
    result = subprocess.run([sys.executable, str(RUNNER), "fetch", "--root", str(root), "--experiment", "exp-2",
                             "deep/missing/out"], cwd=root, capture_output=True, text=True, timeout=60,
                            env={**os.environ, "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}"})
    assert result.returncode == 3 and "could not fetch deep/missing/out" in result.stderr
    assert sorted(path.name for path in (root / "experiment/exp-2").iterdir()) == [".gitignore"]


def test_a_failed_fetch_through_openrsync_removes_the_folders_it_made(tmp_path):
    # Linux CI has GNU rsync; this fake answers like macOS openrsync, so the branch that creates
    # the output's parent folders runs everywhere.
    tools = tmp_path / "bin"
    calls = tmp_path / "rsync-calls"
    executable(tools / "rsync", '#!/bin/sh\n'
               'case "$*" in *--protect-args*--version*) exit 1 ;; *--version*) echo "openrsync: protocol version 29"; exit 0 ;; esac\n'
               f'printf "%s\\n" "$*" >> "{calls}"\nexit 23\n')
    executable(tools / "ssh", '#!/bin/sh\nexit 255\n')
    root = tmp_path / "project"
    run = root / ".rat/remote-runs/run-1"
    run.mkdir(parents=True)
    (run / "result.json").write_text(json.dumps({"experiment": "exp-3", "host": "fixture",
                                                 "remote_outputs": "/remote/ws"}))
    result = subprocess.run([sys.executable, str(RUNNER), "fetch", "--root", str(root), "--experiment", "exp-3",
                             "deep/missing/out"], cwd=root, capture_output=True, text=True, timeout=60,
                            env={**os.environ, "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}"})
    assert result.returncode == 3, result.stdout + result.stderr
    # The openrsync branch ran: it fetched into the output's parent, which it had to create.
    assert calls.read_text().rstrip().endswith("experiment/exp-3/deep/missing/")
    assert sorted(path.name for path in (root / "experiment/exp-3").iterdir()) == [".gitignore"]

