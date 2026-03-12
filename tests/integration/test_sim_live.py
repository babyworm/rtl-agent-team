"""Integration tests for run_sim.sh with real simulators."""

from pathlib import Path

import pytest

from tests.conftest import SCRIPTS_DIR, run_script
from tests.integration.conftest import requires_iverilog, requires_verilator

RUN_SIM = SCRIPTS_DIR / "run_sim.sh"

# Minimal SV testbench that passes
PASSING_TB = """\
module tb_pass;
  initial begin
    $display("TEST PASSED");
    $finish;
  end
endmodule
"""

# SV testbench that fails ($fatal)
FAILING_TB = """\
module tb_fail;
  initial begin
    $display("TEST FAILED");
    $fatal(1, "Intentional failure");
  end
endmodule
"""


@requires_iverilog
class TestIverilogLive:
    """Integration tests with real iverilog."""

    def test_compile_and_run_pass(self, tmp_path):
        sv = tmp_path / "tb_pass.sv"
        sv.write_text(PASSING_TB)
        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "tb_pass",
            "--outdir", str(tmp_path / "build"), str(sv),
            timeout=60,
        )
        assert result.returncode == 0
        assert "TEST PASSED" in result.stdout
        assert "Compile OK" in result.stdout

    def test_compile_only(self, tmp_path):
        sv = tmp_path / "tb_pass.sv"
        sv.write_text(PASSING_TB)
        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "tb_pass",
            "--outdir", str(tmp_path / "build"), "--compile-only", str(sv),
            timeout=60,
        )
        assert result.returncode == 0
        assert "Compile OK" in result.stdout
        # Should not have run
        assert "TEST PASSED" not in result.stdout

    def test_compile_error_exits_nonzero(self, tmp_path):
        sv = tmp_path / "bad.sv"
        sv.write_text("module bad; syntax error here; endmodule")
        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "bad",
            "--outdir", str(tmp_path / "build"), str(sv),
            timeout=60,
        )
        assert result.returncode != 0

    def test_define_flag(self, tmp_path):
        sv = tmp_path / "tb_define.sv"
        sv.write_text("""\
module tb_define;
  initial begin
`ifdef MY_DEFINE
    $display("DEFINE FOUND");
`else
    $display("DEFINE MISSING");
`endif
    $finish;
  end
endmodule
""")
        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "tb_define",
            "--outdir", str(tmp_path / "build"),
            "--define", "MY_DEFINE", str(sv),
            timeout=60,
        )
        assert result.returncode == 0
        assert "DEFINE FOUND" in result.stdout

    def test_filelist_integration(self, tmp_path):
        mod = tmp_path / "adder.sv"
        mod.write_text("""\
module adder (
  input  logic [7:0] i_a, i_b,
  output logic [8:0] o_sum
);
  assign o_sum = i_a + i_b;
endmodule
""")
        tb = tmp_path / "tb_adder.sv"
        tb.write_text("""\
module tb_adder;
  logic [7:0] a, b;
  logic [8:0] sum;
  adder u_dut (.i_a(a), .i_b(b), .o_sum(sum));
  initial begin
    a = 8'd10; b = 8'd20;
    #1;
    if (sum == 9'd30) $display("TEST PASSED");
    else $display("TEST FAILED: sum=%0d", sum);
    $finish;
  end
endmodule
""")
        flist = tmp_path / "filelist.f"
        flist.write_text(f"{mod}\n")

        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "tb_adder",
            "--outdir", str(tmp_path / "build"),
            "--filelist", str(flist), str(tb),
            timeout=60,
        )
        assert result.returncode == 0
        assert "TEST PASSED" in result.stdout


@requires_verilator
class TestVerilatorLive:
    """Integration tests with real verilator (lint-only for speed)."""

    def test_lint_clean_module(self, tmp_path):
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
        import subprocess
        result = subprocess.run(
            ["verilator", "--lint-only", "-Wall", str(sv)],
            capture_output=True, text=True, timeout=30,
        )
        assert result.returncode == 0
