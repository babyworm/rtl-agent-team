"""Parallel experiment outputs stay separate even without a project initialization."""
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os

from tests.conftest import REPO_ROOT, run_script
from tests.unit.test_uvm_regression_runner import _fake_xrun, _project, _run

SIM = REPO_ROOT / "scripts/run_sim.sh"
SYN = REPO_ROOT / "skills/rat-init-project/templates/run_syn.sh"
COCOTB = REPO_ROOT / "skills/rtl-p5s-func-verify/scripts/run_regression.sh"


def run_sim(project, name, *args):
    return run_script(
        SIM, "--sim", "xrun", "--top", "tb", "tb.sv", *args, cwd=project,
        env={"RAT_EXPERIMENT_ID": name, "RAT_PROJECT_ROOT": str(project),
             "RAT_EXECUTION_LOCAL": "1", "CLAUDE_PLUGIN_DATA": str(project / ".site"),
             "PATH": str(project / "bin") + os.pathsep + os.environ["PATH"]},
    )


def test_parallel_simulators_keep_their_build_and_log(tmp_path):
    (tmp_path / "bin").mkdir()
    (tmp_path / "tb.sv").write_text("module tb; endmodule\n")
    xrun = tmp_path / "bin/xrun"
    xrun.write_text("""#!/bin/sh
mkdir -p xlib
echo "$RAT_EXPERIMENT_ID" >xlib/snapshot
case "$1" in -R) echo RAT_SIM_PASS ;; esac
""")
    xrun.chmod(0o755)
    names = ("freq-a", "freq-b")
    with ThreadPoolExecutor(max_workers=2) as pool:
        runs = list(pool.map(lambda name: run_sim(tmp_path, name), names))
    for name, run in zip(names, runs):
        assert run.returncode == 0, run.stdout + run.stderr
        build = tmp_path / "experiment" / name / "sim/build"
        assert (build / "xlib/snapshot").read_text().strip() == name
        assert json.loads((build / ".rat-build.json").read_text())["experiment_id"] == name
    assert not (tmp_path / "sim/build").exists()

    namespace = tmp_path / "experiment" / names[0]
    fd = os.open(namespace, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        busy = run_sim(tmp_path, names[0])
        assert busy.returncode and "namespace is busy" in busy.stderr
    finally:
        os.close(fd)
    escaped = run_sim(tmp_path, names[0], "--outdir", str(tmp_path / "wrong"))
    assert escaped.returncode and not (tmp_path / "wrong").exists()


def test_uvm_compile_seed_and_coverage_paths(tmp_path):
    project, binaries = _project(tmp_path, filelist_text="-y rtl\n-f rtl/nested.f\n")
    (project / "rtl/nested.f").write_text("-v dut.sv\n")
    _fake_xrun(binaries)
    xrun = binaries / "xrun"
    xrun.write_text(xrun.read_text().replace("args = sys.argv[1:]", 'Path("xrun.log").touch()\nargs = sys.argv[1:]'))
    result = _run(project, "--sim", "xrun", "--seeds", "42 43", "--parallel", "2",
                  "--coverage-mode", "functional-log", FAKE_BIN_LOG="1", RAT_EXPERIMENT_ID="uvm",
                  CLAUDE_PLUGIN_DATA=str(tmp_path / ".site"), RAT_EXECUTION_LOCAL="1")
    assert result.returncode == 0, result.stdout + result.stderr
    sim = project / "experiment/uvm/sim/uvm"
    run_dir, = (sim / "regression").glob("run_*")
    assert (run_dir / "inputs.f").read_text().splitlines() == [
        "-y", str(project / "rtl"), "-v", str(project / "rtl/dut.sv"),
    ]
    assert (run_dir / "xrun.log").is_file()
    for seed in (42, 43):
        assert (run_dir / f"seed_{seed}/xrun.log").is_file()
    assert list((sim / "coverage").glob("functional_*.json"))
    assert not (project / "xrun.log").exists()


def test_cocotb_results_xml_is_per_seed(tmp_path):
    tb = tmp_path / "sim"
    tb.mkdir()
    (tb / "dut.sv").write_text("module dut; endmodule\n")
    (tb / "Makefile").write_text('VERILOG_SOURCES = dut.sv\nsim:\n\t@echo $(RANDOM_SEED) > "$(COCOTB_RESULTS_FILE)"\n\t@echo RAT_SIM_PASS\n')
    run = run_script(COCOTB, "--seeds", "4 7", "--parallel", "2", "--sim", "icarus",
                     cwd=tmp_path, env={"RAT_EXPERIMENT_ID": "coco", "RAT_EXECUTION_LOCAL": "1",
                                        "CLAUDE_PLUGIN_DATA": str(tmp_path / ".site")})
    assert run.returncode == 0, run.stdout + run.stderr
    assert sorted(f.read_text().strip() for f in (tmp_path / "experiment/coco").rglob("results.xml")) == ["4", "7"]
    assert not (tb / "regression").exists()


def test_synthesis_outdir_is_relative_to_experiment(tmp_path):
    (tmp_path / "cells.db").write_text("fixture")
    (tmp_path / "dut.sv").write_text("module dut; endmodule\n")
    (tmp_path / "rat_config.json").write_text(json.dumps({"technology": {"db": "cells.db"}}))
    tool = tmp_path / "dc_shell"
    tool.write_text("#!/bin/sh\necho fake DC\n")
    tool.chmod(0o755)
    run = run_script(SYN, "--tool", "dc_shell", "--top", "dut", "--outdir", "custom", "dut.sv",
                     cwd=tmp_path, env={"RAT_EXPERIMENT_ID": "area", "RAT_EXECUTION_LOCAL": "1",
                                        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"]})
    assert run.returncode == 0, run.stdout + run.stderr
    assert list((tmp_path / "experiment/area/custom/scr").glob("dc_syn_dut_*.tcl"))
    assert not (tmp_path / "custom").exists()


def test_coverage_merge_selects_only_named_experiment(tmp_path):
    merge = COCOTB.with_name("merge_coverage.sh")
    bindir = tmp_path / "bin"
    bindir.mkdir()
    lcov = bindir / "lcov"
    lcov.write_text("""#!/bin/sh
if [ "$1" = --summary ]; then echo 'lines 100'; exit 0; fi
cat "$2" > "$4"
""")
    lcov.chmod(0o755)
    genhtml = bindir / "genhtml"
    genhtml.write_text("#!/bin/sh\nexit 0\n")
    genhtml.chmod(0o755)
    for name in ("one", "two"):
        folder = tmp_path / "experiment" / name / "sim/regression"
        folder.mkdir(parents=True)
        (folder / "coverage.info").write_text(name)
    result = run_script(merge, cwd=tmp_path, env={"RAT_EXPERIMENT_ID": "one", "FORMAT": "lcov",
                                                  "PATH": str(bindir) + os.pathsep + os.environ["PATH"]})
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "experiment/one/sim/coverage/merged.info").read_text() == "one"
    assert not (tmp_path / "sim").exists()
