"""Behavioral contracts for the commercial UVM regression runner."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT, run_script


RUNNER = (
    REPO_ROOT
    / "skills"
    / "rtl-p5s-uvm-verify"
    / "scripts"
    / "run_regression_uvm.sh"
)


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


def _project(tmp_path: Path, *, filelist_text: str = "rtl/dut.sv\n") -> tuple[Path, Path]:
    project = tmp_path / "project"
    (project / "bin").mkdir(parents=True)
    (project / "rtl").mkdir()
    (project / "sim" / "uvm").mkdir(parents=True)
    (project / "rtl" / "dut.sv").write_text("module dut; endmodule\n")
    (project / "rtl" / "filelist_top.f").write_text(filelist_text)
    return project, project / "bin"


def _fake_vcs(bin_dir: Path) -> None:
    _write_executable(
        bin_dir / "vcs",
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with open(os.environ["VCS_ARGV_LOG"], "a") as handle:
    handle.write(json.dumps(args) + "\\n")
output = Path(args[args.index("-o") + 1])
output.write_text(r'''#!/usr/bin/env bash
if [[ "${FAKE_KILL_PARENT:-0}" == "1" ]]; then
  kill -TERM "$PPID"
  exit 1
fi
coverage_dir=""
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "-cm_dir" ]]; then coverage_dir="$2"; shift 2; else shift; fi
done
if [[ "${FAKE_NO_COVERAGE:-0}" != "1" && -n "$coverage_dir" ]]; then
  mkdir -p "$coverage_dir"
  : > "$coverage_dir/raw.vdb"
fi
uvm_errors=0
if [[ "${FAKE_UVM_ERROR:-0}" == "1" ]]; then
  echo 'UVM_ERROR @ 100: reporter [FAKE] injected error'
  uvm_errors=1
fi
printf 'UVM_WARNING :    0\nUVM_ERROR :    %s\nUVM_FATAL :    0\n' "$uvm_errors"
exit 0
''')
output.chmod(0o755)
""",
    )
    _write_executable(
        bin_dir / "urg",
        """#!/usr/bin/env python3
from pathlib import Path
import sys

args = sys.argv[1:]
if __import__("os").environ.get("FAKE_MERGE_FAIL") == "1":
    raise SystemExit(7)
report = Path(args[args.index("-report") + 1])
report.mkdir(parents=True, exist_ok=True)
(report / "dashboard.txt").write_text("fake coverage\\n")
(report / "dashboard.xml").write_text("<coverage/>\\n")
""",
    )


def _fake_xrun(bin_dir: Path) -> None:
    _write_executable(
        bin_dir / "xrun",
        """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with open(os.environ["XRUN_ARGV_LOG"], "a") as handle:
    handle.write(json.dumps(args) + "\\n")
if "-R" in args and "-covworkdir" in args:
    coverage_dir = Path(args[args.index("-covworkdir") + 1])
    coverage_dir.mkdir(parents=True, exist_ok=True)
    (coverage_dir / "raw.ucd").write_text("fake coverage\\n")
""",
    )
    _write_executable(bin_dir / "imc", "#!/usr/bin/env bash\nexit 0\n")


def _env(project: Path, **overrides: str) -> dict[str, str]:
    env = {
        "PATH": f"{project / 'bin'}:{os.environ.get('PATH', '')}",
        "RAT_PROJECT_ROOT": str(project),
        "VCS_ARGV_LOG": str(project / "vcs.argv.jsonl"),
        "XRUN_ARGV_LOG": str(project / "xrun.argv.jsonl"),
    }
    env.update(overrides)
    return env


def _run(project: Path, *args: str, **env_overrides: str):
    return run_script(
        RUNNER,
        *args,
        cwd=project,
        env=_env(project, **env_overrides),
        timeout=30,
    )


def _report(project: Path) -> dict:
    reports = sorted((project / "sim" / "uvm" / "regression").glob("regression_*.json"))
    assert reports
    return json.loads(reports[-1].read_text())


def test_clean_run_writes_valid_json_and_uses_module_base_test(tmp_path: Path) -> None:
    project, bin_dir = _project(tmp_path)
    _fake_vcs(bin_dir)

    result = _run(project, "--sim", "vcs", "--module", "dut", "--seeds", "42", "--parallel", "1")

    assert result.returncode == 0, result.stderr
    report = _report(project)
    assert report["test"] == "dut_base_test"
    assert report["seeds_total"] == 1
    assert report["coverage_status"] == "MERGED"
    seed_reports = list((project / "sim" / "uvm" / "regression").glob("run_*/seed_42_results.json"))
    assert len(seed_reports) == 1
    assert json.loads(seed_reports[0].read_text())["uvm_errors"] == 0


@pytest.mark.parametrize("option", ["--parallel", "--max-fail-rate"])
def test_arithmetic_options_reject_command_substitution(tmp_path: Path, option: str) -> None:
    project, bin_dir = _project(tmp_path)
    _fake_vcs(bin_dir)
    marker = tmp_path / "executed"
    payload = f"SRC_FILES[$(touch {marker})]"

    result = _run(
        project,
        "--sim",
        "vcs",
        "--module",
        "dut",
        "--seeds",
        "42",
        option,
        payload,
    )

    assert result.returncode != 0
    assert not marker.exists()


def test_stale_seed_result_is_not_harvested(tmp_path: Path) -> None:
    project, bin_dir = _project(tmp_path)
    _fake_vcs(bin_dir)
    results_dir = project / "sim" / "uvm" / "regression"
    results_dir.mkdir(parents=True)
    (results_dir / "seed_999_results.json").write_text(
        json.dumps({"seed": 999, "status": "FAIL"}) + "\n"
    )

    result = _run(project, "--sim", "vcs", "--module", "dut", "--seeds", "42", "--parallel", "1")

    assert result.returncode == 0, result.stderr
    report = _report(project)
    assert report["seeds_total"] == 1
    assert report["seeds_failed"] == 0


def test_empty_seed_list_is_an_error(tmp_path: Path) -> None:
    project, bin_dir = _project(tmp_path)
    _fake_vcs(bin_dir)

    result = _run(project, "--sim", "vcs", "--module", "dut", "--seeds", "", "--parallel", "1")

    assert result.returncode != 0
    assert "seed" in (result.stdout + result.stderr).lower()


def test_background_worker_failure_cannot_report_pass(tmp_path: Path) -> None:
    project, bin_dir = _project(tmp_path)
    _fake_vcs(bin_dir)

    result = _run(
        project,
        "--sim",
        "vcs",
        "--module",
        "dut",
        "--seeds",
        "42",
        "--parallel",
        "2",
        FAKE_KILL_PARENT="1",
    )

    assert result.returncode != 0
    reports = sorted((project / "sim" / "uvm" / "regression").glob("regression_*.json"))
    if reports:
        assert json.loads(reports[-1].read_text())["verdict"] != "PASS"


def test_missing_coverage_cannot_report_pass(tmp_path: Path) -> None:
    project, bin_dir = _project(tmp_path)
    _fake_vcs(bin_dir)

    result = _run(
        project,
        "--sim",
        "vcs",
        "--module",
        "dut",
        "--seeds",
        "42",
        "--parallel",
        "1",
        FAKE_NO_COVERAGE="1",
    )

    assert result.returncode != 0
    report = _report(project)
    assert report["coverage_status"] == "FAILED"
    assert report["verdict"] == "FAIL"


def test_zero_count_uvm_summary_is_not_treated_as_an_error(tmp_path: Path) -> None:
    project, bin_dir = _project(tmp_path)
    _fake_vcs(bin_dir)

    result = _run(project, "--sim", "vcs", "--module", "dut", "--seeds", "42", "--parallel", "1")

    assert result.returncode == 0, result.stderr
    seed_report = next((project / "sim" / "uvm" / "regression").glob("run_*/seed_42_results.json"))
    payload = json.loads(seed_report.read_text())
    assert payload["uvm_errors"] == 0
    assert payload["uvm_fatals"] == 0


def test_real_uvm_error_fails_the_seed(tmp_path: Path) -> None:
    project, bin_dir = _project(tmp_path)
    _fake_vcs(bin_dir)

    result = _run(
        project,
        "--sim",
        "vcs",
        "--module",
        "dut",
        "--seeds",
        "42",
        "--parallel",
        "1",
        FAKE_UVM_ERROR="1",
    )

    assert result.returncode != 0
    assert _report(project)["verdict"] == "FAIL"


def test_coverage_merge_failure_cannot_report_pass(tmp_path: Path) -> None:
    project, bin_dir = _project(tmp_path)
    _fake_vcs(bin_dir)

    result = _run(
        project,
        "--sim",
        "vcs",
        "--module",
        "dut",
        "--seeds",
        "42",
        "--parallel",
        "1",
        FAKE_MERGE_FAIL="1",
    )

    assert result.returncode != 0
    report = _report(project)
    assert report["coverage_status"] == "FAILED"
    assert report["verdict"] == "FAIL"


def test_filelist_is_passed_intact_to_simulator(tmp_path: Path) -> None:
    project, bin_dir = _project(
        tmp_path,
        filelist_text=(
            "+incdir+rtl/include\n"
            "+define+FEATURE=1\n"
            "rtl/dut.sv\n"
            "-f rtl/nested.f\n"
        ),
    )
    (project / "rtl" / "include").mkdir()
    (project / "rtl" / "nested.sv").write_text("module nested; endmodule\n")
    (project / "rtl" / "nested.f").write_text("rtl/nested.sv\n")
    _fake_vcs(bin_dir)

    result = _run(project, "--sim", "vcs", "--module", "dut", "--seeds", "42", "--parallel", "1")

    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in (project / "vcs.argv.jsonl").read_text().splitlines()]
    assert "-f" in calls[0]
    assert str(project / "rtl" / "filelist_top.f") in calls[0]
    assert not any("-f rtl/nested.f" in arg for arg in calls[0])


def test_xrun_elaborates_before_running(tmp_path: Path) -> None:
    project, bin_dir = _project(tmp_path)
    _fake_xrun(bin_dir)

    result = _run(project, "--sim", "xrun", "--module", "dut", "--seeds", "42", "--parallel", "1")

    assert result.returncode == 0, result.stderr
    calls = [json.loads(line) for line in (project / "xrun.argv.jsonl").read_text().splitlines()]
    phases = ["-compile" if "-compile" in call else "-elaborate" if "-elaborate" in call else "-R" for call in calls]
    assert phases[:3] == ["-compile", "-elaborate", "-R"]
