"""Tests for run_regression.sh and merge_coverage.sh — regression and coverage scripts."""

import json
import subprocess

import pytest

from tests.conftest import SKILLS_DIR, run_script

RUN_REGRESSION = SKILLS_DIR / "rtl-regression-run" / "scripts" / "run_regression.sh"
MERGE_COVERAGE = SKILLS_DIR / "rtl-regression-run" / "scripts" / "merge_coverage.sh"


def _expected_default_parallel() -> int:
    """Mirror run_regression.sh default: max(1, nproc-2)."""
    probe = subprocess.run(
        [
            "bash",
            "-lc",
            "if command -v nproc >/dev/null 2>&1; then nproc; "
            "elif command -v getconf >/dev/null 2>&1; then getconf _NPROCESSORS_ONLN 2>/dev/null || true; "
            "else echo 4; fi",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    cores_text = probe.stdout.strip()
    cores = int(cores_text) if cores_text.isdigit() else 4
    return max(1, cores - 2)


class TestRunRegression:
    """Tests for run_regression.sh argument validation."""

    def test_unknown_option_exits_2(self):
        result = run_script(RUN_REGRESSION, "--bogus", timeout=10)
        assert result.returncode == 2
        assert "Unknown option" in result.stdout or "Unknown" in result.stderr

    def test_header_printed(self, tmp_path):
        """Script should print header even when TB_DIR is missing."""
        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1",
            "--sim", "icarus",
            env={"TB_DIR": str(tmp_path / "nonexistent")},
            timeout=10,
        )
        assert "Regression Run" in result.stdout

    def test_default_seeds(self, tmp_path):
        """Default seeds should be '1 42 123 1337 65536'."""
        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1",
            env={"TB_DIR": str(tmp_path / "nonexistent")},
            timeout=10,
        )
        # With --seeds override, should see Seed: 1
        assert "Seeds: 1" in result.stdout

    def test_parallel_flag_accepted(self, tmp_path):
        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1",
            "--parallel", "2",
            env={"TB_DIR": str(tmp_path / "nonexistent")},
            timeout=10,
        )
        assert "Parallel: 2" in result.stdout

    def test_default_parallel_uses_nproc_minus_2(self, tmp_path):
        expected = _expected_default_parallel()
        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1",
            env={"TB_DIR": str(tmp_path / "nonexistent")},
            timeout=10,
        )
        assert f"Parallel: {expected} (auto: nproc-2)" in result.stdout

    def test_default_mode_is_local(self, tmp_path):
        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1",
            env={"TB_DIR": str(tmp_path / "nonexistent")},
            timeout=10,
        )
        assert "Mode: local" in result.stdout

    def test_invalid_mode_exits_2(self, tmp_path):
        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1",
            "--mode", "bogus",
            env={"TB_DIR": str(tmp_path / "nonexistent")},
            timeout=10,
        )
        assert result.returncode == 2
        assert "Unsupported mode" in result.stdout

    def test_aws_batch_mode_is_blocked_without_explicit_orchestration(self, tmp_path):
        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1",
            "--mode", "aws-batch",
            env={"TB_DIR": str(tmp_path / "nonexistent")},
            timeout=10,
        )
        assert result.returncode == 2
        assert "RTL_ALLOW_AWS=1" in result.stdout

    def test_aws_batch_mode_requires_runner_path(self, tmp_path):
        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1",
            "--mode", "aws-batch",
            env={
                "TB_DIR": str(tmp_path / "nonexistent"),
                "RTL_ALLOW_AWS": "1",
            },
            timeout=10,
        )
        assert result.returncode == 2
        assert "no AWS runner configured" in result.stdout

    def test_aws_batch_mode_delegates_to_runner_when_opted_in(self, tmp_path):
        runner = tmp_path / "aws-runner.sh"
        runner.write_text(
            "#!/usr/bin/env bash\n"
            "echo \"AWS_RUNNER $*\"\n"
            "exit 0\n"
        )
        runner.chmod(0o755)

        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1 2",
            "--sim", "verilator",
            "--parallel", "3",
            "--mode", "aws-batch",
            env={
                "RTL_ALLOW_AWS": "1",
                "RTL_AWS_BATCH_RUNNER": str(runner),
            },
            timeout=10,
        )
        assert result.returncode == 0
        assert "AWS_RUNNER" in result.stdout
        assert "--seeds 1 2" in result.stdout
        assert "--sim verilator" in result.stdout
        assert "--parallel 3" in result.stdout
        assert "--results-dir sim/regression" in result.stdout

    def test_parallel_must_be_positive_integer(self, tmp_path):
        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1",
            "--parallel", "0",
            env={"TB_DIR": str(tmp_path / "nonexistent")},
            timeout=10,
        )
        assert result.returncode == 2
        assert "--parallel must be >= 1" in result.stdout

    def test_local_runner_writes_mode_module_and_random_seed(self, tmp_path):
        sim_dir = tmp_path / "sim"
        sim_dir.mkdir(parents=True)
        (sim_dir / "Makefile").write_text(
            "all:\n"
            "\t@echo \"RANDOM_SEED=$(RANDOM_SEED)\"\n"
            "\t@echo \"SIM_BUILD=$(SIM_BUILD)\"\n"
            "\t@test -n \"$(SIM_BUILD)\"\n"
            "\t@mkdir -p \"$(SIM_BUILD)\"\n"
        )

        result = run_script(
            RUN_REGRESSION,
            "--seeds", "7",
            "--tb-dir", "sim",
            "--module", "adder",
            "--parallel", "1",
            cwd=str(tmp_path),
            timeout=20,
        )
        assert result.returncode == 0

        regression_dir = sim_dir / "regression"
        seed_log = (regression_dir / "seed_7.log").read_text()
        assert "RANDOM_SEED=7" in seed_log
        assert "SIM_BUILD=" in seed_log
        assert "seed_7" in seed_log

        seed_result = json.loads((regression_dir / "seed_7_results.json").read_text())
        assert seed_result["status"] == "PASS"
        assert seed_result["mode"] == "local"
        assert seed_result["runner"] == "local"
        assert seed_result["module"] == "adder"

        summaries = sorted(regression_dir.glob("results_*.json"))
        assert summaries
        summary = json.loads(summaries[-1].read_text())
        assert summary["mode"] == "local"
        assert summary["module"] == "adder"

    def test_parallel_early_halt_terminates_active_jobs(self, tmp_path):
        sim_dir = tmp_path / "sim"
        sim_dir.mkdir(parents=True)
        (sim_dir / "Makefile").write_text(
            "all:\n"
            "\t@if [ \"$(RANDOM_SEED)\" = \"1\" ]; then echo \"forced fail\"; exit 1; fi\n"
            "\t@sleep 5\n"
            "\t@echo \"pass $(RANDOM_SEED)\"\n"
        )

        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1 2 3 4",
            "--tb-dir", "sim",
            "--parallel", "3",
            "--max-fail-rate", "0",
            cwd=str(tmp_path),
            timeout=15,
        )
        assert result.returncode == 1
        assert "HALT: Failure rate" in result.stdout
        assert "Stopping active jobs due to early termination threshold..." in result.stdout

    def test_local_parallel_completion_counts_all_passes(self, tmp_path):
        sim_dir = tmp_path / "sim"
        sim_dir.mkdir(parents=True)
        (sim_dir / "Makefile").write_text(
            "all:\n"
            "\t@sleep 0.1\n"
            "\t@echo \"seed $(RANDOM_SEED) pass\"\n"
        )

        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1 2 3",
            "--tb-dir", "sim",
            "--parallel", "2",
            cwd=str(tmp_path),
            timeout=20,
        )
        assert result.returncode == 0
        assert "Seeds: 3 | Passed: 3 | Failed: 0" in result.stdout


class TestMergeCoverage:
    """Tests for merge_coverage.sh format validation."""

    def test_unknown_format_exits_2(self, tmp_path):
        result = run_script(
            MERGE_COVERAGE,
            env={"FORMAT": "bogus", "OUTPUT": str(tmp_path / "out.info")},
            cwd=str(tmp_path),
            timeout=10,
        )
        assert result.returncode == 2
        assert "Unknown format" in result.stdout

    def test_verilator_no_dat_exits_1(self, tmp_path):
        """Verilator mode with no .dat files should exit 1."""
        reg_dir = tmp_path / "sim" / "regression"
        reg_dir.mkdir(parents=True)
        result = run_script(
            MERGE_COVERAGE,
            env={"FORMAT": "verilator", "OUTPUT": str(tmp_path / "out.info")},
            cwd=str(tmp_path),
            timeout=10,
        )
        assert result.returncode == 1
        assert "No coverage.dat" in result.stdout

    def test_lcov_no_info_exits_1(self, tmp_path):
        """lcov mode with no .info files should exit 1."""
        reg_dir = tmp_path / "sim" / "regression"
        reg_dir.mkdir(parents=True)
        result = run_script(
            MERGE_COVERAGE,
            env={"FORMAT": "lcov", "OUTPUT": str(tmp_path / "out.info")},
            cwd=str(tmp_path),
            timeout=10,
        )
        assert result.returncode == 1
        assert "No .info files" in result.stdout

    def test_verilator_header_printed(self, tmp_path):
        reg_dir = tmp_path / "sim" / "regression"
        reg_dir.mkdir(parents=True)
        result = run_script(
            MERGE_COVERAGE,
            env={"FORMAT": "verilator", "OUTPUT": str(tmp_path / "out.info")},
            cwd=str(tmp_path),
            timeout=10,
        )
        assert "Merging Verilator" in result.stdout

    def test_lcov_header_printed(self, tmp_path):
        reg_dir = tmp_path / "sim" / "regression"
        reg_dir.mkdir(parents=True)
        result = run_script(
            MERGE_COVERAGE,
            env={"FORMAT": "lcov", "OUTPUT": str(tmp_path / "out.info")},
            cwd=str(tmp_path),
            timeout=10,
        )
        assert "Merging lcov" in result.stdout
