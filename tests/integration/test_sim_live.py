"""Integration tests for run_sim.sh with real simulators."""

import json

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

    def test_only_the_requested_top_can_finish_the_simulation(self, tmp_project):
        benches = tmp_project / "benches.sv"
        benches.write_text("""\
module early_smoke;
  initial begin
    #1;
    $display("RAT_SIM_PASS");
    $finish;
  end
endmodule
module requested;
  initial #2 $fatal(1, "requested bench mismatch");
endmodule
""")
        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "requested", str(benches),
            cwd=tmp_project,
        )
        assert result.returncode != 0
        assert "requested bench mismatch" in result.stdout
        assert "verdict=FAIL" in result.stdout

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

    def test_run_only_requires_recompile_for_legacy_implicit_roots(self, tmp_project):
        sv = tmp_project / "tb_pass.sv"
        sv.write_text(PASSING_TB)
        args = ("--sim", "iverilog", "--top", "tb_pass")
        compiled = run_script(RUN_SIM, *args, "--compile-only", str(sv), cwd=tmp_project)
        assert compiled.returncode == 0, compiled.stderr

        receipt = tmp_project / "sim/build/.rat-build.json"
        build = json.loads(receipt.read_text())
        build["context"] = "iverilog|tb_pass|||0||"  # pre20 compiled every root
        receipt.write_text(json.dumps(build))

        result = run_script(RUN_SIM, *args, "--run-only", cwd=tmp_project)
        assert result.returncode != 0
        assert "compile again" in result.stdout + result.stderr

    def test_compile_error_exits_nonzero(self, tmp_path):
        sv = tmp_path / "bad.sv"
        sv.write_text("module bad; syntax error here; endmodule")
        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "bad",
            "--outdir", str(tmp_path / "build"), str(sv),
            timeout=60,
        )
        assert result.returncode != 0

    @pytest.mark.parametrize("flags,failures", [(["--define", "MY_DEFINE"], 0), ([], 1)])
    def test_define_flag(self, tmp_path, flags, failures):
        sv = tmp_path / "tb_define.sv"
        sv.write_text("""\
module tb_define;
  initial begin
`ifdef MY_DEFINE
    $display("RAT_CHECK_POINT define.present 1 0");
`else
    $display("RAT_CHECK_POINT define.present 1 1");
`endif
    $display("RAT_SIM_PASS");
    $finish;
  end
endmodule
""")
        result = run_script(
            RUN_SIM, "--sim", "iverilog", "--top", "tb_define",
            "--outdir", str(tmp_path / "build"),
            *flags, str(sv),
            timeout=60,
        )
        assert f"RAT_CHECK_POINT define.present 1 {failures}" in result.stdout
        assert (result.returncode == 0) == (failures == 0)
        assert ("verdict=FAIL" if failures else "verdict=PASS") in result.stdout

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
