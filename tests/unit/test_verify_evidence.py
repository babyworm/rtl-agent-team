"""Simulation claims must follow measured verdicts and unchanged source inputs."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.conftest import HOOKS_DIR, REPO_ROOT, run_hook

SPEC = importlib.util.spec_from_file_location("verify_evidence", REPO_ROOT / "scripts/verify_evidence.py")
evidence = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evidence)


@pytest.mark.parametrize("code,text,expected", [
    (0, "RAT_SIM_PASS", "PASS"), (0, "PASS\nFATAL: mismatch", "FAIL"),
    (0, "simulation ended", "INCONCLUSIVE"), (23, "RAT_SIM_PASS", "FAIL"),
    (124, "RAT_SIM_PASS", "TIMEOUT"), (0, "RAT_STALL", "STALL"),
    (0, "TESTS=3 PASS=3 FAIL=0 SKIP=0", "PASS"),
    (0, "TESTS=3 PASS=2 FAIL=0 SKIP=1", "INCONCLUSIVE"),
    (0, "TESTS=3 PASS=2 FAIL=1 SKIP=0", "FAIL"),
])
def test_verdict_precedence(code, text, expected):
    assert evidence.classify(code, text) == expected


@pytest.fixture
def simulation(tmp_project):
    root = tmp_project
    source = root / "rtl/dut.sv"
    source.parent.mkdir()
    source.write_text("module dut; endmodule\n")
    tools = root / "fake-bin"
    tools.mkdir()
    compiler = tools / "iverilog"
    compiler.write_text("#!/bin/sh\nwhile [ $# -gt 0 ]; do if [ \"$1\" = -o ]; then : > \"$2\"; shift 2; else shift; fi; done\nexit 0\n")
    runtime = tools / "vvp"
    runtime.write_text("#!/bin/sh\nprintf '%s\\n' \"${SIM_OUTPUT:-RAT_SIM_PASS}\"\nexit \"${SIM_EXIT:-0}\"\n")
    for executable in (compiler, runtime):
        executable.chmod(0o755)
    env = {**os.environ, "PATH": str(tools) + os.pathsep + os.environ["PATH"], "RAT_PROJECT_ROOT": str(root)}

    def run(*flags, **overrides):
        return subprocess.run(["bash", str(REPO_ROOT / "scripts/run_sim.sh"), "--sim", "iverilog",
                               "--top", "tb", *flags, str(source)], cwd=root, env={**env, **overrides},
                              capture_output=True, text=True)

    return root, source, run


def test_passing_runner_evidence_satisfies_gate_and_new_edit_invalidates_it(simulation):
    root, source, run = simulation
    result = run()
    assert result.returncode == 0, result.stdout + result.stderr
    state = root / ".rat/state"
    records = json.loads((state / "verify-evidence.json").read_text())["runs"]
    assert records[-1]["verdict"] == "PASS"
    track = state / "rtl-modified-files.txt"
    track.write_text(str(source) + "\n")
    assert run_hook(HOOKS_DIR / "rtl-verify-stop-gate.sh", {"cwd": str(root)}) == {"continue": True}
    source.write_text("module dut; wire changed; endmodule\n")
    track.write_text(str(source) + "\n")
    (state / "rtl-verify-done").touch()
    blocked = run_hook(HOOKS_DIR / "rtl-verify-stop-gate.sh", {"cwd": str(root)})
    assert blocked["decision"] == "block"
    assert "touched marker is insufficient" in blocked["reason"]


@pytest.mark.parametrize("flags,overrides,expected", [
    (["--compile-only"], {}, "COMPILED"),
    ([], {"SIM_OUTPUT": "testbench ended"}, "INCONCLUSIVE"),
    ([], {"SIM_OUTPUT": "FAIL: expected 7 got 8"}, "FAIL"),
    ([], {"SIM_EXIT": "13"}, "FAIL"),
])
def test_compile_exit_and_logs_cannot_fabricate_functional_pass(simulation, flags, overrides, expected):
    root, _, run = simulation
    result = run(*flags, **overrides)
    record = json.loads((root / ".rat/state/verify-evidence.json").read_text())["runs"][-1]
    assert record["verdict"] == expected, result.stdout + result.stderr
    assert result.returncode == (0 if expected == "COMPILED" else (13 if overrides.get("SIM_EXIT") else 3))


def test_run_only_rejects_stale_compile(simulation):
    _, source, run = simulation
    assert run("--compile-only").returncode == 0
    source.write_text("module dut; wire new_logic; endmodule\n")
    result = run("--run-only")
    assert result.returncode != 0
    assert "compiled sources changed" in result.stderr


def test_log_tampering_invalidates_evidence(simulation):
    root, source, run = simulation
    assert run().returncode == 0
    state = root / ".rat/state"
    record = json.loads((state / "verify-evidence.json").read_text())["runs"][-1]
    Path(record["log"]).write_text("RAT_SIM_PASS\nmodified log\n")
    track = state / "rtl-modified-files.txt"
    track.write_text(str(source) + "\n")
    result = subprocess.run([sys.executable, str(REPO_ROOT / "scripts/verify_evidence.py"),
                             "unverified", "--root", str(root), "--track", str(track)], capture_output=True, text=True)
    assert result.returncode == 1
    assert "rtl/dut.sv" in result.stdout


def test_run_only_rejects_changed_build_bytes(simulation):
    root, _, run = simulation
    assert run('--compile-only').returncode == 0
    (root/'sim/build/tb').write_text('different executable bytes')
    result=run('--run-only')
    assert result.returncode != 0
    assert 'compiled artifacts changed' in result.stderr


def test_run_only_rejects_changed_compile_options(simulation):
    _, _, run = simulation
    assert run('--compile-only').returncode == 0
    result=run('--run-only','--define','CHANGED=1')
    assert result.returncode != 0
    assert 'compile again' in result.stderr


def test_compile_zero_exit_with_error_log_is_not_compiled(simulation):
    root, _, run = simulation
    compiler=root/'fake-bin/iverilog'
    compiler.write_text(compiler.read_text().replace('exit 0','echo "ERROR: compile failed"\nexit 0'))
    assert run('--compile-only').returncode != 0
    runs=json.loads((root/'.rat/state/verify-evidence.json').read_text())['runs']
    assert runs[-1]['verdict']=='FAIL'


@pytest.mark.parametrize('text', ['UVM_ERROR @ 1: checker bad\nRAT_SIM_PASS', '# UVM_FATAL @ 0: bad\nRAT_SIM_PASS'])
def test_uvm_error_without_summary_beats_positive_completion(text):
    assert evidence.classify(0,text)=='FAIL'


def test_compiler_pass_text_cannot_replace_a_missing_runtime_result(simulation):
    root, _, run=simulation
    compiler=root/'fake-bin/iverilog'
    compiler.write_text(compiler.read_text().replace('exit 0','echo RAT_SIM_PASS\nexit 0'))
    result=run(SIM_OUTPUT='simulation ended without test result')
    assert result.returncode!=0
    assert json.loads((root/'.rat/state/verify-evidence.json').read_text())['runs'][-1]['verdict']=='INCONCLUSIVE'


def test_compile_timeout_keeps_timeout_verdict_without_a_build_artifact(simulation):
    root, _, run=simulation
    (root/'fake-bin/iverilog').write_text('#!/bin/sh\necho RAT_TIMEOUT\nexit 124\n')
    result=run()
    assert result.returncode==124
    assert json.loads((root/'.rat/state/verify-evidence.json').read_text())['runs'][-1]['verdict']=='TIMEOUT'


def test_snapshot_consumes_the_configured_tool_environment(simulation):
    root, source, run=simulation
    includes=root/'vendor-headers';includes.mkdir()
    header=includes/'constants.svh';header.write_text('`define VALUE 1\n')
    source.write_text('`include "constants.svh"\nmodule dut; endmodule\n')
    (root/'rat_config.json').write_text(json.dumps({
        'execution':{'backend':'local'},
        'tools':{'simulators':{'iverilog':{'env_source':'export RAT_VENDOR_HEADERS='+str(includes)}}},
        'verification':{'include_dirs':['$RAT_VENDOR_HEADERS']}}))
    result=run()
    assert result.returncode==0,result.stdout+result.stderr
    record=json.loads((root/'.rat/state/verify-evidence.json').read_text())['runs'][-1]
    assert str(header) in record['sources']


def test_bundled_wrapper_does_not_mix_in_older_project_helpers(simulation):
    root, _, run=simulation
    library=root/'lib';library.mkdir()
    for name in ('verify_evidence.py','eda_runner.py'):
        (library/name).write_text('raise SystemExit("stale project helper")\n')
    result=run()
    assert result.returncode==0,result.stdout+result.stderr
    assert 'stale project helper' not in result.stdout+result.stderr
