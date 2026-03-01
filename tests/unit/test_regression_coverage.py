"""Tests for run_regression.sh and merge_coverage.sh — regression and coverage scripts."""

from pathlib import Path

import pytest

from tests.conftest import SKILLS_DIR, run_script

RUN_REGRESSION = SKILLS_DIR / "rtl-regression-run" / "scripts" / "run_regression.sh"
MERGE_COVERAGE = SKILLS_DIR / "rtl-regression-run" / "scripts" / "merge_coverage.sh"


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
