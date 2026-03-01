r"""Tests for run_regression.sh and merge_coverage.sh -- argument validation and logic.

Known Issues:
- BUG-003: run_regression.sh has ``set -euo pipefail`` + ``((TOTAL++))``
  which causes silent exit when TOTAL is 0 (same as check_conventions BUG-001).
  The script exits before running any seeds.
  Seed execution tests document this with ``# DOCUMENTS BUG``.
"""

from pathlib import Path

import pytest

from tests.conftest import SKILLS_DIR, run_script

RUN_REGRESSION = SKILLS_DIR / "rtl-regression-run" / "scripts" / "run_regression.sh"
MERGE_COVERAGE = SKILLS_DIR / "rtl-regression-run" / "scripts" / "merge_coverage.sh"


class TestRunRegressionArgs:
    """Tests for run_regression.sh argument parsing."""

    def test_unknown_option(self):
        result = run_script(RUN_REGRESSION, "--bad-flag")
        assert result.returncode != 0

    def test_header_printed(self, tmp_path):
        """Script should print header before crashing on BUG-003."""
        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1",
            env={"TB_DIR": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert "Regression Run" in result.stdout

    def test_creates_results_dir(self, tmp_path):
        run_script(
            RUN_REGRESSION,
            "--seeds", "1",
            env={"TB_DIR": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert (tmp_path / "regression").exists()

    def test_creates_coverage_dir(self, tmp_path):
        run_script(
            RUN_REGRESSION,
            "--seeds", "1",
            env={"TB_DIR": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert (tmp_path / "coverage").exists()

    def test_seeds_displayed(self, tmp_path):
        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1 42 99",
            env={"TB_DIR": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert "1 42 99" in result.stdout

    def test_sim_arg_displayed(self, tmp_path):
        result = run_script(
            RUN_REGRESSION,
            "--seeds", "1",
            "--sim", "verilator",
            env={"TB_DIR": str(tmp_path)},
            cwd=str(tmp_path),
        )
        assert "verilator" in result.stdout


class TestRunRegressionSeedLogic:
    """Tests for seed execution logic.

    NOTE: Due to BUG-003, ``((TOTAL++))`` with ``set -e`` causes the script
    to exit at the first seed iteration before running make. These tests
    document the current (broken) behavior.
    """

    def test_script_exits_on_first_seed(self, tmp_path):
        """DOCUMENTS BUG-003: Script exits at ((TOTAL++)) before running seeds."""
        (tmp_path / "Makefile").write_text('all:\n\t@echo "PASS"\n')
        result = run_script(
            RUN_REGRESSION,
            "--seeds", "42",
            "--sim", "icarus",
            env={"TB_DIR": str(tmp_path)},
            cwd=str(tmp_path),
        )
        # Expected: rc=0, seed runs, result file created
        # Actual: rc=1, no seed runs (BUG-003)
        assert result.returncode == 1  # DOCUMENTS BUG
        result_file = tmp_path / "regression" / "seed_42_results.json"
        assert not result_file.exists()  # DOCUMENTS BUG: seed never runs


class TestMergeCoverageArgs:
    """Tests for merge_coverage.sh argument validation."""

    def test_unknown_format(self, tmp_path):
        result = run_script(
            MERGE_COVERAGE,
            env={"FORMAT": "unknown_format"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 2
        assert "Unknown format" in result.stdout

    def test_no_dat_files_verilator(self, tmp_path):
        """Verilator mode with no .dat files should exit 1."""
        reg_dir = tmp_path / "sim" / "regression"
        reg_dir.mkdir(parents=True)
        result = run_script(
            MERGE_COVERAGE,
            env={"FORMAT": "verilator"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 1
        assert "No coverage.dat" in result.stdout

    def test_no_info_files_lcov(self, tmp_path):
        """lcov mode with no .info files should exit 1."""
        reg_dir = tmp_path / "sim" / "regression"
        reg_dir.mkdir(parents=True)
        result = run_script(
            MERGE_COVERAGE,
            env={"FORMAT": "lcov"},
            cwd=str(tmp_path),
        )
        assert result.returncode == 1
        assert "No .info files" in result.stdout

    def test_default_format_is_verilator(self, tmp_path):
        """Default format should be verilator when FORMAT env var not set."""
        reg_dir = tmp_path / "sim" / "regression"
        reg_dir.mkdir(parents=True)
        result = run_script(
            MERGE_COVERAGE,
            cwd=str(tmp_path),
        )
        # Should show "Merging Verilator coverage data"
        assert "Verilator" in result.stdout or "verilator" in result.stdout.lower()

    def test_creates_output_dirs(self, tmp_path):
        """Coverage and HTML directories should be created."""
        run_script(
            MERGE_COVERAGE,
            env={"FORMAT": "verilator"},
            cwd=str(tmp_path),
        )
        assert (tmp_path / "sim" / "coverage").exists()
        assert (tmp_path / "sim" / "coverage" / "html").exists()
