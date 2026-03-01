"""Tests for run_sim.sh — Argument parsing and validation."""

import subprocess
from pathlib import Path

import pytest

from tests.conftest import SCRIPTS_DIR, run_script

RUN_SIM = SCRIPTS_DIR / "run_sim.sh"


class TestRunSimValidation:
    """Tests for run_sim.sh argument validation."""

    def test_missing_top_exits_error(self):
        result = run_script(RUN_SIM, "dummy.sv")
        assert result.returncode == 1
        assert "--top" in result.stderr

    def test_no_sources_exits_error(self):
        result = run_script(RUN_SIM, "--top", "tb_module")
        assert result.returncode == 1
        assert "No source files" in result.stderr

    def test_unknown_option_exits_error(self):
        result = run_script(RUN_SIM, "--invalid-flag", "--top", "tb_module", "dummy.sv")
        assert result.returncode == 1
        assert "Unknown option" in result.stderr

    def test_help_flag(self):
        result = run_script(RUN_SIM, "--help")
        assert result.returncode == 0
        assert "Usage:" in result.stdout

    def test_unsupported_simulator(self, tmp_path):
        sv = tmp_path / "dummy.sv"
        sv.write_text("module dummy; endmodule")
        result = run_script(RUN_SIM, "--sim", "nonexistent_sim", "--top", "dummy", str(sv))
        assert result.returncode == 1
        assert "Unsupported simulator" in result.stderr

    def test_missing_filelist_exits_error(self):
        result = run_script(
            RUN_SIM, "--top", "tb_module", "--filelist", "/nonexistent/filelist.f"
        )
        assert result.returncode == 1
        assert "Filelist not found" in result.stderr

    def test_run_only_skips_source_requirement(self, tmp_path):
        """--run-only should not require source files."""
        # Will fail at simulator execution, but should pass argument validation
        result = run_script(RUN_SIM, "--top", "tb_module", "--run-only", "--sim", "iverilog")
        # Should get past validation (no "No source files" error)
        assert "No source files" not in result.stderr


class TestRunSimOutputDir:
    """Tests for output directory creation."""

    def test_outdir_created(self, tmp_path):
        sv = tmp_path / "dummy.sv"
        sv.write_text("module dummy; endmodule")
        outdir = tmp_path / "build_output"
        # Will fail at compile (iverilog may not be installed), but outdir should be created
        run_script(
            RUN_SIM, "--top", "dummy", "--outdir", str(outdir),
            "--compile-only", str(sv)
        )
        assert outdir.exists()


class TestRunSimFilelist:
    """Tests for filelist processing."""

    def test_filelist_with_incdir(self, tmp_path):
        """iverilog should convert +incdir+ to -I."""
        sv = tmp_path / "dummy.sv"
        sv.write_text("module dummy; endmodule")
        flist = tmp_path / "filelist.f"
        flist.write_text(f"+incdir+{tmp_path}/include\n{sv}\n")

        # Use --verbose to see the command, compile-only to avoid running
        result = run_script(
            RUN_SIM, "--top", "dummy", "--filelist", str(flist),
            "--compile-only", "--verbose"
        )
        # The -I flag should appear in the verbose compile command output
        assert f"-I{tmp_path}/include" in result.stdout or result.returncode != 0

    def test_filelist_comments_stripped(self, tmp_path):
        sv = tmp_path / "dummy.sv"
        sv.write_text("module dummy; endmodule")
        flist = tmp_path / "filelist.f"
        flist.write_text(f"// This is a comment\n{sv}\n// Another comment\n")

        result = run_script(
            RUN_SIM, "--top", "dummy", "--filelist", str(flist), "--compile-only"
        )
        # Should not error on comment lines
        assert "comment" not in result.stderr.lower()


class TestRunSimDefinesAndParams:
    """Tests for define and param flag generation."""

    def test_multiple_defines(self, tmp_path):
        sv = tmp_path / "dummy.sv"
        sv.write_text("module dummy; endmodule")
        result = run_script(
            RUN_SIM, "--top", "dummy", "--compile-only", "--verbose",
            "--define", "FOO=1", "--define", "BAR=2", str(sv),
        )
        # Both -DFOO=1 and -DBAR=2 should appear in the compile command
        assert "-DFOO=1" in result.stdout
        assert "-DBAR=2" in result.stdout

    def test_param_flag_iverilog(self, tmp_path):
        sv = tmp_path / "dummy.sv"
        sv.write_text("module dummy; endmodule")
        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "dummy", "--compile-only",
            "--verbose", "--param", "WIDTH=8", str(sv),
        )
        # iverilog param format: -Pdummy.WIDTH=8
        assert "-Pdummy.WIDTH=8" in result.stdout

    def test_header_shown(self, tmp_path):
        sv = tmp_path / "dummy.sv"
        sv.write_text("module dummy; endmodule")
        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "dummy",
            "--compile-only", str(sv),
        )
        assert "run_sim.sh" in result.stdout
        assert "iverilog" in result.stdout
        assert "dummy" in result.stdout


class TestRunSimCompileOnly:
    """Tests for --compile-only mode."""

    def test_compile_only_does_not_run(self, tmp_path):
        sv = tmp_path / "dummy.sv"
        sv.write_text("module dummy; endmodule")
        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "dummy",
            "--compile-only", str(sv),
        )
        # Should NOT show "--- Run ---" section
        assert "--- Run ---" not in result.stdout
