"""Integration tests for lint tools with real EDA tools."""

import subprocess
from pathlib import Path

import pytest

from tests.conftest import SKILLS_DIR, run_script
from tests.integration.conftest import (
    requires_verilator,
    requires_verible,
    requires_slang,
)

# Template lint script (may not be installed as executable yet)
LINT_SCRIPT = SKILLS_DIR / "rtl-setup" / "templates" / "run_lint.sh"


@requires_verilator
class TestVerilatorLintLive:
    """Integration tests for verilator lint."""

    def test_clean_module_passes(self, tmp_path):
        sv = tmp_path / "clean.sv"
        sv.write_text("""\
module clean (
  input  logic        clk,
  input  logic        rst_n,
  input  logic [7:0]  i_data,
  output logic [7:0]  o_data
);
  always_ff @(posedge clk or negedge rst_n)
    if (!rst_n) o_data <= '0;
    else        o_data <= i_data;
endmodule
""")
        result = subprocess.run(
            ["verilator", "--lint-only", "-Wall", str(sv)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0

    def test_warning_on_unused_signal(self, tmp_path):
        sv = tmp_path / "unused.sv"
        sv.write_text("""\
module unused (
  input  logic        clk,
  input  logic        rst_n,
  input  logic [7:0]  i_data,
  output logic [7:0]  o_data
);
  logic [7:0] unused_sig;
  assign o_data = i_data;
endmodule
""")
        result = subprocess.run(
            ["verilator", "--lint-only", "-Wall", str(sv)],
            capture_output=True, text=True, timeout=30,
        )
        # verilator -Wall should warn about unused signal
        assert "UNUSED" in result.stderr or "unused" in result.stderr.lower()


@requires_verilator
class TestLintScriptLive:
    """Integration tests for the run_lint.sh template with verilator."""

    @pytest.fixture
    def lint_script_path(self):
        if not LINT_SCRIPT.exists():
            pytest.skip("run_lint.sh template not found")
        return LINT_SCRIPT

    def test_verilator_lint_clean(self, tmp_path, lint_script_path):
        sv = tmp_path / "clean.sv"
        sv.write_text("""\
module clean (
  input  logic clk,
  input  logic rst_n,
  input  logic [7:0] i_data,
  output logic [7:0] o_data
);
  always_ff @(posedge clk or negedge rst_n)
    if (!rst_n) o_data <= '0;
    else        o_data <= i_data;
endmodule
""")
        flist = tmp_path / "filelist.f"
        flist.write_text(str(sv) + "\n")

        result = run_script(
            lint_script_path,
            "--tool", "verilator",
            "--top", "clean",
            "-f", str(flist),
            "--outdir", str(tmp_path / "lint_out"),
            timeout=60,
        )
        assert result.returncode == 0
