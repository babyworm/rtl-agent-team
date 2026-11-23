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
    (0, "# RAT_CHECK_POINT clip.cmp 3 1\nRAT_SIM_PASS", "FAIL"),
    (0, "RAT_CHECK_POINT clip.cmp 3 0\nRAT_SIM_PASS", "PASS"),
    (0, "RAT_CHECK_POINT clip.cmp 3\nRAT_SIM_PASS", "FAIL"),
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


@pytest.mark.parametrize("marker", [None, ".rtl-agent-team"])
def test_experiment_in_fresh_git_project_hides_outputs_and_preserves_evidence(simulation, marker):
    root, source, run = simulation
    if marker:
        (root / ".rat").rename(root / marker)
    else:  # before rat-init-project
        (root / ".rat/state").rmdir()
        (root / ".rat").rmdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "add", "rtl", "fake-bin"], cwd=root, check=True)

    proc = run(RAT_EXPERIMENT_ID="smoke")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    state = evidence.runtime_state_root(root) / "state"
    record = json.loads((state / "verify-evidence.json").read_text())["runs"][-1]
    assert record["experiment_id"] == "smoke"
    assert record["verdict"] == "PASS" and Path(record["log"]).is_relative_to(root / "experiment/smoke")
    assert str(source) in record["sources"]
    untracked = subprocess.check_output(["git", "-c", f"core.excludesFile={os.devnull}", "ls-files",
                                         "--others", "--exclude-standard"], cwd=root, text=True)
    if marker is None:
        # Run records stay in the plugin data folder, so a run does not initialize the folder.
        assert not (root / ".rat").exists() and not state.is_relative_to(root)
        assert untracked.splitlines() == []
        return
    # The Git rule is scoped to generated results; unrelated project metadata remains visible.
    run_hook(HOOKS_DIR / "rtl-audit-init.sh", {"cwd": str(root)})
    (state / "readme.md").write_text("User-authored state notes\n")
    untracked = subprocess.check_output(["git", "-c", f"core.excludesFile={os.devnull}", "ls-files",
                                         "--others", "--exclude-standard"], cwd=root, text=True)
    assert untracked.splitlines() == [f"{marker}/state/readme.md"]
    assert (root / ".rat").exists() == (marker == ".rat")


@pytest.mark.parametrize("before,after,same", [
    ("module m;\n  assign a = b; // drive\nendmodule\n", "module m;\n    assign a = b;   // reworded\n\nendmodule", True),
    ("module m; /* old */ wire w; endmodule", "module m; wire w; endmodule", True),
    ("module m; wire w; endmodule", "module m; wire w2; endmodule", False),
    ("module m; // synopsys translate_off\nendmodule", "module m;\nendmodule", False),
    ('initial $display("a // b");', 'initial $display("a  // b");', False),
    ("`define A 1\nwire w;", "`define A 1 wire w;", False),
])
def test_source_identity_ignores_ordinary_comments_and_indentation(tmp_path, before, after, same):
    first, second = tmp_path / "a.sv", tmp_path / "b.sv"
    first.write_text(before)
    second.write_text(after)
    assert (evidence.source_digest(first) == evidence.source_digest(second)) is same


def test_comment_edit_keeps_evidence_and_missing_paths_need_none(simulation):
    root, source, run = simulation
    assert run().returncode == 0
    state = root / ".rat/state"
    source.write_text("// header comment\nmodule dut;   endmodule\n")
    (state / "rtl-modified-files.txt").write_text(f"{source}\nrtl/renamed_away.sv\n*.sv\n")
    assert run_hook(HOOKS_DIR / "rtl-verify-stop-gate.sh", {"cwd": str(root)}) == {"continue": True}


@pytest.mark.parametrize("relative,after,tracked", [
    ("rtl/a.sv", "module a; // reworded\nendmodule\n", False),
    ("rtl/a.sv", "module a; wire w; endmodule\n", True),
    ("formal/a_props.sv", "module a_props; wire w; endmodule\n", False),
])
def test_tracker_records_behavioral_hdl_edits_only(tmp_project, relative, after, tracked):
    path = tmp_project / relative
    path.parent.mkdir()
    path.write_text("module a; // note\nendmodule\n")
    for event in ("PreToolUse", "PostToolUse"):
        if event == "PostToolUse":
            path.write_text(after)
        run_hook(HOOKS_DIR / "rtl-edit-tracker.sh", {
            "hook_event_name": event, "tool_name": "Edit", "tool_use_id": "t1", "session_id": "s",
            "cwd": str(tmp_project), "tool_input": {"file_path": str(path)}})
    track = tmp_project / ".rat/state/rtl-modified-files.txt"
    assert (track.is_file() and relative in track.read_text()) is tracked


def test_bash_comment_edit_uses_known_identity_and_unknown_counts_as_change(tmp_project):
    seen, unseen = tmp_project / "rtl/seen.sv", tmp_project / "rtl/unseen.sv"
    seen.parent.mkdir()
    seen.write_text("module seen; // a\nendmodule\n")
    unseen.write_text("module unseen; // a\nendmodule\n")
    track = tmp_project / ".rat/state/rtl-modified-files.txt"

    def tool(name, tool_id, edit, **tool_input):
        for event in ("PreToolUse", "PostToolUse"):
            if event == "PostToolUse":
                edit()
            run_hook(HOOKS_DIR / "rtl-edit-tracker.sh", {
                "hook_event_name": event, "tool_name": name, "tool_use_id": tool_id, "session_id": "s",
                "cwd": str(tmp_project), "tool_input": tool_input})

    tool("Edit", "e1", lambda: seen.write_text("module seen; wire w; // a\nendmodule\n"), file_path=str(seen))
    track.unlink()
    tool("Bash", "b1", lambda: (seen.write_text("module seen; wire w; // b\nendmodule\n"),
                                unseen.write_text("module unseen; // b\nendmodule\n")), command="sed -i")
    assert track.read_text().split() == ["rtl/unseen.sv"]


def test_unrunnable_verification_is_a_notice_not_a_block(tmp_project):
    (tmp_project / "rtl").mkdir()
    (tmp_project / "rtl/a.sv").write_text("module a; endmodule\n")
    (tmp_project / ".rat/state/rtl-modified-files.txt").write_text("rtl/a.sv\n")
    names = ("iverilog", "verilator", "vcs", "xrun", "vsim")
    bare = os.pathsep.join(d for d in os.environ["PATH"].split(os.pathsep)
                           if not any(os.access(os.path.join(d, n), os.X_OK) for n in names))
    env = {name: value for name, value in os.environ.items() if name != "SIM"}
    result = subprocess.run(["sh", str(HOOKS_DIR / "rtl-verify-stop-gate.sh")], input=json.dumps({"cwd": str(tmp_project)}),
                            env={**env, "PATH": bare}, capture_output=True, text=True)
    output = json.loads(result.stdout)
    assert "decision" not in output
    assert "rat-setup" in output["systemMessage"]
    run_sim = subprocess.run(["bash", str(REPO_ROOT / "scripts/run_sim.sh"), "--top", "a", "rtl/a.sv"], cwd=tmp_project,
                             env={**env, "PATH": bare}, capture_output=True, text=True)
    assert run_sim.returncode == 2 and "no simulator" in run_sim.stderr


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


@pytest.mark.parametrize("legacy", [False, True])
def test_failed_named_comparison_never_verifies_an_rtl_edit(simulation, legacy):
    root, source, run = simulation
    result = run(SIM_OUTPUT="RAT_CHECK_POINT clip.scoreboard 3 1\nRAT_SIM_PASS")
    assert result.returncode != 0, result.stdout
    state = root / ".rat/state"
    index = state / "verify-evidence.json"
    data = json.loads(index.read_text())
    record = data["runs"][-1]
    assert record["verdict"] == "FAIL"
    if legacy:
        record["verdict"] = "PASS"
        record.pop("check_points_classified")
        index.write_text(json.dumps(data))
    (state / "rtl-modified-files.txt").write_text(str(source) + "\n")
    assert run_hook(HOOKS_DIR / "rtl-verify-stop-gate.sh", {"cwd": str(root)})["decision"] == "block"


@pytest.mark.parametrize("inputs", [[], ["golden.txt"]])
def test_changed_refc_invalidates_passing_run_even_with_unchanged_vectors(simulation, inputs):
    root, _, run = simulation
    model = root / "refc/clip.c"
    model.parent.mkdir()
    model.write_text("int clip(int x) { return x > 255 ? 255 : x; }\n")
    (root / "golden.txt").write_text("256 255\n")
    point = {"id": "clip.cmp", "kind": "scoreboard", "requirement": "REQ-F-002",
             "source": "spec §2 and refc/clip.c#clip", "trigger": "x exceeds 255",
             "expected_result": "255", "confidence": "high", "basis": "spec §2"}
    if inputs:
        point["inputs"] = inputs
    plan = root / evidence.POINT_PLAN
    plan.parent.mkdir(exist_ok=True)
    plan.write_text(json.dumps({"points": [point]}))
    assert run(SIM_OUTPUT="RAT_CHECK_POINT clip.cmp 4 0\nRAT_SIM_PASS").returncode == 0
    runs = json.loads((root / ".rat/state/verify-evidence.json").read_text())["runs"]
    judgment = root / "docs/phase-5-verify/judgment.json"
    judgment.parent.mkdir(parents=True)
    judgment.write_text(json.dumps({"simulation_runs": [runs[-1]["run_id"]]}))
    command = [sys.executable, str(REPO_ROOT / "scripts/gates/simulation_points.py"), "--root", str(root)]
    (model.parent / "unrelated.c").write_text("int unrelated;\n")
    assert subprocess.run(command, capture_output=True).returncode == 0
    model.write_text(model.read_text().replace("? 255", "? 254"))
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode != 0 and "clip.cmp" in result.stdout


def test_external_model_is_pinned_independently_of_generated_vectors(tmp_path):
    (tmp_path / "golden.txt").write_text("256 255\n")
    point = {"id": "clip.cmp", "kind": "scoreboard", "requirement": "REQ-F-002",
             "source": "external refC", "trigger": "overflow", "expected_result": "255",
             "inputs": ["golden.txt"]}
    with pytest.raises(ValueError, match="oracle_revision"):
        evidence.point_fingerprint(tmp_path, point)
    with pytest.raises(ValueError, match="oracle_revision"):
        evidence.point_fingerprint(tmp_path, {**point, "oracle_revision": "main"})
    with pytest.raises(ValueError, match="oracle_revision"):
        evidence.point_fingerprint(tmp_path, {**point, "source": "external refC and vector SHA-256 " + "e"*64})
    before = evidence.point_fingerprint(tmp_path, {**point, "oracle_revision": "a"*40})
    after = evidence.point_fingerprint(tmp_path, {**point, "oracle_revision": "b"*40})
    assert before != after
    evidence.point_fingerprint(tmp_path, {**point, "source": "external refC at " + "e"*64})
    evidence.point_fingerprint(tmp_path, {**point, "source": "spec §2"})


@pytest.mark.parametrize("source,inputs", [
    ("Specification §5.C", []), ("ISO Table A.1.c", []),
    ("Python reference model", ["model.py"]),
])
def test_non_c_citations_remain_valid(tmp_path, source, inputs):
    point = {"id": "x", "kind": "scoreboard", "requirement": "REQ-F-001",
             "trigger": "accepted", "expected_result": "x", "source": source, "inputs": inputs}
    for name in inputs:
        (tmp_path / name).write_text("def expected(x): return x\n")
    before = evidence.point_fingerprint(tmp_path, point)
    if inputs:
        (tmp_path / inputs[0]).write_text("def expected(x): return x + 1\n")
        assert evidence.point_fingerprint(tmp_path, point) != before


@pytest.mark.parametrize("citation", ["refc/clip.c", "clip.c#clip", "`clip.c`", "refC clip.c"])
def test_clear_reference_to_missing_local_oracle_fails(tmp_path, citation):
    point = {"id": "x", "kind": "scoreboard", "requirement": "REQ-F-001",
             "trigger": "accepted", "expected_result": "x", "source": citation}
    with pytest.raises((FileNotFoundError, ValueError)):
        evidence.point_fingerprint(tmp_path, point)


@pytest.mark.parametrize("relative", [False, True])
def test_pinned_external_citation_does_not_read_external_files(tmp_path, relative):
    root = tmp_path / "project"
    root.mkdir()
    model = tmp_path / "external model/clip.c"
    path = "../external model/clip.c" if relative else str(model)
    point = {"id": "clip.cmp", "kind": "scoreboard", "requirement": "REQ-F-002",
             "source": f"refC `{path}#clip`", "trigger": "overflow", "expected_result": "255"}
    with pytest.raises(ValueError, match="oracle_revision"):
        evidence.point_fingerprint(root, point)
    pinned = {**point, "oracle_revision": "a"*40}
    before = evidence.point_fingerprint(root, pinned)
    model.parent.mkdir()
    model.write_text("external content is unavailable to the EDA host")
    assert evidence.point_fingerprint(root, pinned) == before
    with pytest.raises(ValueError, match="project-relative|invalid point input"):
        evidence.point_fingerprint(root, {**pinned, "inputs": [path]})


@pytest.mark.parametrize("seed_args,expected", [
    (["first.log", "second.log"], "PASS"),
    (["second.log", "first.log"], "INCONCLUSIVE"),
    (["first.log", "first.log"], "INCONCLUSIVE"),
])
def test_seed_boundaries_must_match_the_bound_runtime_log(tmp_path, seed_args, expected):
    helper = [sys.executable, str(REPO_ROOT / "scripts/verify_evidence.py")]
    (tmp_path / "dut.sv").write_text("module dut; endmodule\n")
    begin = subprocess.run([*helper, "begin", "--root", str(tmp_path), "--outdir", str(tmp_path),
                            "--tool", "test", "--top", "dut", "--source", "dut.sv"],
                           check=True, capture_output=True, text=True)
    logs = [b"RAT_CHECK_POINT p 1 0\nRAT_SIM_PASS\n", b"RAT_CHECK_POINT p 2 0\nRAT_SIM_PASS\n"]
    for name, data in zip(("first.log", "second.log"), logs):
        (tmp_path / name).write_bytes(data)
    (tmp_path / "runtime.log").write_bytes(b"".join(logs))
    (tmp_path / "combined.log").write_bytes(b"compile\n" + b"".join(logs))
    result = subprocess.run([*helper, "finish", "--snapshot", begin.stdout.strip(), "--exit-code", "0",
                             "--log", "combined.log", "--runtime-log", "runtime.log",
                             *(arg for name in seed_args for arg in ("--seed-log", name))],
                            cwd=tmp_path, capture_output=True, text=True)
    record = json.loads((evidence.runtime_state_root(tmp_path) / "state/verify-evidence.json").read_text())["runs"][-1]
    assert record["verdict"] == expected, result.stdout + result.stderr
    if expected == "PASS":
        assert result.returncode == 0 and record["seed_log_sizes"] == list(map(len, logs))
    else:
        assert result.returncode != 0 and record["seed_log_error"] in result.stderr


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


@pytest.mark.parametrize("before,after", [
    ("wire \\a//x ;", "wire \\a//y ;"),          # escaped identifiers may contain //
    ("wire \\a/*x ;", "wire \\a/*y ;"),          # ... or /*
    ("// rtl_synthesis_off\nwire a;", "// rtl_synthesis_on\nwire a;"),  # prefixed directive
])
def test_identity_keeps_escaped_identifiers_and_prefixed_directives(before, after):
    assert evidence.hdl_text(before) != evidence.hdl_text(after)


def test_experiment_results_are_not_rtl_sources(tmp_path):
    snapshot = importlib.util.spec_from_file_location("rtl_change_snapshot", REPO_ROOT / "scripts/rtl_change_snapshot.py")
    module = importlib.util.module_from_spec(snapshot)
    snapshot.loader.exec_module(module)
    assert not module.is_source(Path("experiment/run-1/syn/netlist.v"))
    assert module.is_source(Path("rtl/top.sv"))
    for path in ("experiment/run-1/syn/netlist.v", "rtl/top.sv"):
        (tmp_path / path).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / path).write_text("module m; endmodule\n")
    # Tracking files written before this rule may still name fetched results.
    assert evidence.tracked_paths(tmp_path, ["experiment/run-1/syn/netlist.v", "rtl/top.sv"]) == {
        str((tmp_path / "rtl/top.sv").resolve())}
