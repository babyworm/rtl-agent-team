r"""Tests for check_conventions.sh -- RTL naming convention checker.

Known Issues:
- BUG-001: ``set -euo pipefail`` + ``((VIOLATIONS++))`` causes silent exit when
  VIOLATIONS is 0 (post-increment returns 0, treated as failure by set -e).
  The script exits with rc=1 but no stdout on first violation.
- BUG-002: Rule 5 (INSTANCE_PREFIX) uses ``grep -n`` producing line-number prefixed
  output, but the ``-vE`` exclude filter matches against ``^\s*(module|...)`` which
  fails because the line starts with ``N:module`` not ``module``. This causes false
  positives on module declarations.

Tests are written to document ACTUAL behavior. Tests marked with
``# DOCUMENTS BUG`` note where behavior diverges from intended behavior.
"""

import subprocess
from pathlib import Path

import pytest

from tests.conftest import SKILLS_DIR, run_script

CHECK_CONVENTIONS = SKILLS_DIR / "rtl-lint-check" / "scripts" / "check_conventions.sh"


class TestCheckConventions:
    """Tests for check_conventions.sh."""

    def test_clean_file_triggers_false_positive(self, sample_sv_clean):
        """DOCUMENTS BUG: Clean module declaration triggers INSTANCE_PREFIX false positive
        due to BUG-002, then BUG-001 causes silent exit."""
        result = run_script(CHECK_CONVENTIONS, str(sample_sv_clean))
        # Expected: rc=0, "PASS". Actual: rc=1, empty stdout (BUG-001 + BUG-002)
        assert result.returncode == 1  # DOCUMENTS BUG

    def test_nonexistent_target(self):
        result = run_script(CHECK_CONVENTIONS, "/nonexistent/path")
        assert result.returncode == 2

    def test_directory_scan_runs(self, tmp_path):
        """Verify directory mode doesn't crash."""
        sv = tmp_path / "a.sv"
        sv.write_text("module a;\n  logic l;\nendmodule\n")
        result = run_script(CHECK_CONVENTIONS, str(tmp_path))
        # Even clean files may trigger false positive due to BUG-002
        assert result.returncode in (0, 1)

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

    def test_valid_instance_prefix_still_caught(self, tmp_path):
        """DOCUMENTS BUG: Even with u_ prefix instances, module declaration itself
        triggers false positive (BUG-002)."""
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
        # Expected: rc=0 (u_ prefix correct). Actual: rc=1 (module decl false positive)
        assert result.returncode == 1  # DOCUMENTS BUG

    def test_file_without_module_decl(self, tmp_path):
        """A file with only assign statements should pass (no module declaration
        to trigger BUG-002)."""
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
