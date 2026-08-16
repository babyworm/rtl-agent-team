r"""Tests for check_conventions.sh -- RTL naming convention checker.

Bug History:
- BUG-001: FIXED. ``set -euo pipefail`` + ``((VIOLATIONS++))`` previously caused
  silent exit when VIOLATIONS was 0 (post-increment returns 0, treated as failure
  by set -e). Fixed by replacing ``((VIOLATIONS++))`` with
  ``VIOLATIONS=$((VIOLATIONS + 1))``.
- BUG-002: FIXED. Rule 5 (INSTANCE_PREFIX) ``grep -n`` produced line-number prefixed
  output (``N:module``), but the ``-vE`` exclude filter expected ``^\s*(module|...)``.
  Fixed by updating the exclude pattern to ``^[0-9]+:\s*(module|...)``.
"""

import subprocess
from pathlib import Path

import pytest

from tests.conftest import SKILLS_DIR, run_script

CHECK_CONVENTIONS = SKILLS_DIR / "rtl-lint-check" / "scripts" / "check_conventions.sh"


class TestCheckConventions:
    """Tests for check_conventions.sh."""

    def test_clean_file_passes(self, sample_sv_clean):
        """Clean SV file with proper conventions should pass all checks."""
        result = run_script(CHECK_CONVENTIONS, str(sample_sv_clean))
        assert result.returncode == 0

    def test_nonexistent_target(self):
        result = run_script(CHECK_CONVENTIONS, "/nonexistent/path")
        assert result.returncode == 2

    def test_directory_scan_runs(self, tmp_path):
        """Verify directory mode doesn't crash."""
        sv = tmp_path / "a.sv"
        sv.write_text("module a;\n  logic l;\nendmodule\n")
        result = run_script(CHECK_CONVENTIONS, str(tmp_path))
        assert result.returncode == 0

    def test_no_reg_wire_rule_exists(self, tmp_path):
        """Verify that wire/reg IS detected (even if script exits early via BUG-001)."""
        sv = tmp_path / "test.sv"
        sv.write_text("module m;\n  wire [7:0] w_data;\nendmodule\n")
        result = run_script(CHECK_CONVENTIONS, str(sv))
        assert result.returncode == 1

    def test_port_suffix_detected(self, tmp_path):
        """Port suffix _i/_o should trigger violation."""
        sv = tmp_path / "test.sv"
        sv.write_text("module m (\n  input logic data_i,\n  output logic result_o\n);\nendmodule\n")
        result = run_script(CHECK_CONVENTIONS, str(sv))
        assert result.returncode == 1

    def test_clock_naming_detected(self, tmp_path):
        sv = tmp_path / "test.sv"
        sv.write_text("module m (\n  input logic clk_i,\n  input logic i_data\n);\nendmodule\n")
        result = run_script(CHECK_CONVENTIONS, str(sv))
        assert result.returncode == 1

    def test_reset_naming_detected(self, tmp_path):
        sv = tmp_path / "test.sv"
        sv.write_text("module m (\n  input logic rst_ni,\n  input logic i_data\n);\nendmodule\n")
        result = run_script(CHECK_CONVENTIONS, str(sv))
        assert result.returncode == 1

    def test_valid_instance_prefix_passes(self, tmp_path):
        """Module with properly u_ prefixed instances should pass Rule 5."""
        sv = tmp_path / "test.sv"
        sv.write_text("""\
module m (
  input logic clk,
  input logic rst_n
);
  sub_mod u_sub (
    .clk(clk)
  );
endmodule
""")
        result = run_script(CHECK_CONVENTIONS, str(sv))
        assert result.returncode == 0

    def test_file_without_module_decl(self, tmp_path):
        """A file with only preprocessor directives and no violations should pass."""
        sv = tmp_path / "assigns.sv"
        sv.write_text("""\
// Just some assignments, no module declaration
`ifndef GUARD
`define GUARD
`endif
""")
        result = run_script(CHECK_CONVENTIONS, str(sv))
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_report_format_on_pass(self, tmp_path):
        """When no violations occur, report format should be correct."""
        sv = tmp_path / "empty.sv"
        sv.write_text("// empty file\n")
        result = run_script(CHECK_CONVENTIONS, str(sv))
        assert result.returncode == 0
        assert "Convention Check Report" in result.stdout
        assert "VERDICT: PASS" in result.stdout

    def test_decl_order_forward_ref_detected(self, tmp_path):
        """Rule 7: Declaration after logic block should trigger DECL_ORDER violation.
        IEEE 1800 §12.5 requires identifiers to be declared before first use."""
        sv = tmp_path / "fwd_ref.sv"
        sv.write_text("""\
  logic [7:0] data_q;

  assign o_result = data_q;

  logic [7:0] late_decl;
""")
        result = run_script(CHECK_CONVENTIONS, str(sv))
        assert result.returncode == 1
        assert "DECL_ORDER" in result.stdout

    def test_decl_order_clean_no_violation(self, tmp_path):
        """Rule 7: Declarations before logic blocks should not trigger DECL_ORDER."""
        sv = tmp_path / "no_fwd_ref.sv"
        sv.write_text("""\
  logic [7:0] data_q;
  logic [7:0] intermediate;

  assign intermediate = data_q;
  assign o_result = intermediate;

  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) data_q <= '0;
    else        data_q <= i_data;
  end
""")
        result = run_script(CHECK_CONVENTIONS, str(sv))
        # No DECL_ORDER violation expected
        assert "DECL_ORDER" not in result.stdout


class TestInstancePrefixRule:
    """Rule 5 (INSTANCE_PREFIX) -- see BUG-003."""

    def _run(self, tmp_path, body):
        sv = tmp_path / "dut.sv"
        sv.write_text(body)
        return run_script(CHECK_CONVENTIONS, str(sv))

    def test_unique_case_is_not_an_instance(self, tmp_path):
        """`unique case (x)` leads with a qualifier, not the `case` keyword."""
        result = self._run(tmp_path, (
            "module m;\n"
            "  always_comb begin\n"
            "    unique case (i_a)\n"
            "      default: o_b = 1'b0;\n"
            "    endcase\n"
            "  end\n"
            "endmodule\n"
        ))
        assert "INSTANCE_PREFIX" not in result.stdout, result.stdout
        assert result.returncode == 0

    def test_interface_and_modport_are_not_instances(self, tmp_path):
        result = self._run(tmp_path, (
            "interface my_if (input logic sys_clk);\n"
            "  modport DRV (input sys_clk);\n"
            "  modport MON (input sys_clk);\n"
            "endinterface\n"
        ))
        assert "INSTANCE_PREFIX" not in result.stdout, result.stdout
        assert result.returncode == 0

    def test_plain_instance_without_prefix_is_flagged(self, tmp_path):
        result = self._run(tmp_path, (
            "module m;\n"
            "  sub_block bad_inst (.sys_clk(sys_clk), .i_a(i_a));\n"
            "endmodule\n"
        ))
        assert "bad_inst" in result.stdout, result.stdout
        assert result.returncode == 1

    def test_parameterized_instance_without_prefix_is_flagged(self, tmp_path):
        """`#` is not a word character -- the pre-BUG-003 pattern skipped these."""
        result = self._run(tmp_path, (
            "module m;\n"
            "  sub_block #(.W(8), .D(16)) bad_param (.sys_clk(sys_clk));\n"
            "endmodule\n"
        ))
        assert "bad_param" in result.stdout, result.stdout
        assert result.returncode == 1

    def test_correctly_prefixed_instances_pass(self, tmp_path):
        result = self._run(tmp_path, (
            "module m;\n"
            "  sub_block u_good (.sys_clk(sys_clk));\n"
            "  sub_block #(.W(8)) u_good_param (.sys_clk(sys_clk));\n"
            "endmodule\n"
        ))
        assert "INSTANCE_PREFIX" not in result.stdout, result.stdout
        assert result.returncode == 0
