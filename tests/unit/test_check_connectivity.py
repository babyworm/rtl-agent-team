"""Tests for skills/rtl-p5s-integration-test/scripts/check_connectivity.py.

Covers the committed worked-example regeneration sync (dut_top + 2 submodules
with one intentional width mismatch and one dangling port), every violation
category, parameter-resolved width checking, honest skip behavior for
unresolvable constructs, and CLI error handling.

All script invocations go through subprocess so the argparse CLI surface is
exercised exactly as the skill documents it.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "rtl-p5s-integration-test"
SCRIPT = SKILL_DIR / "scripts" / "check_connectivity.py"
EXAMPLES = SKILL_DIR / "examples"


def run_script(*args, cwd=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(a) for a in args]],
        capture_output=True, text=True, cwd=cwd, check=False)


def run_on(tmp_path, top_src, subs=(), extra_args=()):
    """Write sources to tmp_path, run the checker, return (result, doc)."""
    top = tmp_path / "top.sv"
    top.write_text(top_src)
    files = [top]
    for i, src in enumerate(subs):
        p = tmp_path / f"sub{i}.sv"
        p.write_text(src)
        files.append(p)
    out = tmp_path / "report.json"
    result = run_script(*files, "-o", out, *extra_args)
    doc = json.loads(out.read_text()) if out.exists() else None
    return result, doc


SUB_LEAF = """
module leaf #(
  parameter int W = 8
) (
  input  logic         clk,
  input  logic         rst_n,
  input  logic [W-1:0] i_d,
  output logic [W-1:0] o_q
);
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) o_q <= '0;
    else        o_q <= i_d;
  end
endmodule
"""

TOP_CLEAN = """
module top_clean (
  input  logic       clk,
  input  logic       rst_n,
  input  logic [7:0] i_d,
  output logic [7:0] o_q
);
  leaf u_leaf (
    .clk   (clk),
    .rst_n (rst_n),
    .i_d   (i_d),
    .o_q   (o_q)
  );
endmodule
"""


# ---------------------------------------------------------------------------
# Committed example regeneration sync (mandatory pattern)
# ---------------------------------------------------------------------------

class TestExampleRegenerationSync:
    def test_example_json_matches_regeneration(self, tmp_path):
        out = tmp_path / "regen.json"
        result = run_script("dut_top.sv", "pixel_gen.sv", "pixel_pack.sv",
                            "-o", out, cwd=EXAMPLES)
        assert result.returncode == 1, result.stderr  # FAIL by design
        committed = (EXAMPLES / "dut_top_connectivity.json").read_text()
        assert out.read_text() == committed

    def test_example_reports_exactly_the_two_intentional_bugs(self):
        doc = json.loads((EXAMPLES / "dut_top_connectivity.json").read_text())
        assert doc["verdict"] == "FAIL"
        assert doc["summary"] == {
            "errors": 1, "warnings": 1, "instances": 2,
            "connections_checked": 11,
            "width_checks": {"checked": 10, "skipped": 0},
        }
        checks = [(v["check"], v["severity"], v["line"], v["port"])
                  for v in doc["violations"]]
        assert checks == [
            ("width_mismatch", "error", 29, "i_data"),
            ("dangling_port", "warning", 32, "o_word_valid"),
        ]

    def test_no_timestamps_in_output(self):
        text = (EXAMPLES / "dut_top_connectivity.json").read_text()
        assert "timestamp" not in text


# ---------------------------------------------------------------------------
# Clean designs pass
# ---------------------------------------------------------------------------

class TestPass:
    def test_clean_top_passes_exit_0(self, tmp_path):
        result, doc = run_on(tmp_path, TOP_CLEAN, [SUB_LEAF])
        assert result.returncode == 0, result.stderr
        assert doc["verdict"] == "PASS"
        assert doc["violations"] == []
        assert doc["summary"]["width_checks"]["checked"] == 4

    def test_parameter_override_resolves_width(self, tmp_path):
        top = TOP_CLEAN.replace("[7:0]", "[15:0]").replace(
            "leaf u_leaf (", "leaf #(.W(16)) u_leaf (")
        result, doc = run_on(tmp_path, top, [SUB_LEAF])
        assert result.returncode == 0, result.stderr
        assert doc["violations"] == []

    def test_clog2_and_arithmetic_in_widths(self, tmp_path):
        sub = """
module fifo #(
  parameter int DEPTH = 16,
  parameter int W = 2 * 4
) (
  input  logic                   clk,
  input  logic [W-1:0]           i_d,
  output logic [$clog2(DEPTH):0] o_level
);
endmodule
"""
        top = """
module top_m (
  input  logic       clk,
  input  logic [7:0] i_d,
  output logic [4:0] o_level
);
  fifo u_fifo (
    .clk     (clk),
    .i_d     (i_d),
    .o_level (o_level)
  );
endmodule
"""
        result, doc = run_on(tmp_path, top, [sub])
        assert result.returncode == 0, result.stderr
        assert doc["summary"]["width_checks"] == {"checked": 3, "skipped": 0}

    def test_slice_literal_and_concat_widths(self, tmp_path):
        top = """
module top_m (
  input  logic        clk,
  input  logic        rst_n,
  input  logic [15:0] i_d,
  output logic [7:0]  o_q
);
  logic [3:0] nib_q;
  leaf u_leaf (
    .clk   (clk),
    .rst_n (rst_n),
    .i_d   ({i_d[11:8], nib_q}),
    .o_q   (o_q)
  );
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) nib_q <= '0;
    else        nib_q <= i_d[3:0];
  end
endmodule
"""
        result, doc = run_on(tmp_path, top, [SUB_LEAF])
        assert result.returncode == 0, result.stderr
        assert doc["violations"] == []

    def test_warnings_alone_still_pass(self, tmp_path):
        top = TOP_CLEAN.replace(".o_q   (o_q)", ".o_q   ()") + ""
        top = top.replace("endmodule", "  assign o_q = i_d;\nendmodule")
        result, doc = run_on(tmp_path, top, [SUB_LEAF])
        assert result.returncode == 0, result.stderr
        assert doc["verdict"] == "PASS"
        assert [v["check"] for v in doc["violations"]] == ["dangling_port"]
        assert doc["violations"][0]["severity"] == "warning"


# ---------------------------------------------------------------------------
# Violation categories
# ---------------------------------------------------------------------------

class TestViolations:
    def test_unknown_port_is_error(self, tmp_path):
        top = TOP_CLEAN.replace(".i_d   (i_d)", ".i_data (i_d)")
        result, doc = run_on(tmp_path, top, [SUB_LEAF])
        assert result.returncode == 1
        v = [x for x in doc["violations"] if x["check"] == "unknown_port"]
        assert len(v) == 1
        assert v[0]["severity"] == "error"
        assert v[0]["port"] == "i_data"
        assert v[0]["instance"] == "u_leaf"
        # The real i_d port is now also unconnected.
        assert any(x["check"] == "unconnected_port" and x["port"] == "i_d"
                   for x in doc["violations"])

    def test_undeclared_signal_is_error(self, tmp_path):
        top = TOP_CLEAN.replace(".i_d   (i_d)", ".i_d   (ghost_sig)")
        result, doc = run_on(tmp_path, top, [SUB_LEAF])
        assert result.returncode == 1
        v = [x for x in doc["violations"] if x["check"] == "undeclared_signal"]
        assert len(v) == 1
        assert "ghost_sig" in v[0]["detail"]

    def test_dangling_input_is_error_output_is_warning(self, tmp_path):
        top = TOP_CLEAN.replace(".i_d   (i_d)", ".i_d   ()")
        top = top.replace(".o_q   (o_q)", ".o_q   ()")
        top = top.replace("endmodule", "  assign o_q = i_d;\nendmodule")
        result, doc = run_on(tmp_path, top, [SUB_LEAF])
        assert result.returncode == 1
        sev = {v["port"]: v["severity"] for v in doc["violations"]
               if v["check"] == "dangling_port"}
        assert sev == {"i_d": "error", "o_q": "warning"}

    def test_omitted_port_is_unconnected_warning(self, tmp_path):
        top = TOP_CLEAN.replace(".rst_n (rst_n),\n", "")
        result, doc = run_on(tmp_path, top, [SUB_LEAF])
        assert result.returncode == 0, result.stderr  # warning-only
        v = [x for x in doc["violations"] if x["check"] == "unconnected_port"]
        assert len(v) == 1
        assert v[0]["port"] == "rst_n"
        assert v[0]["severity"] == "warning"

    def test_undriven_top_output_is_error(self, tmp_path):
        top = """
module top_m (
  input  logic       clk,
  input  logic       rst_n,
  input  logic [7:0] i_d,
  output logic [7:0] o_q,
  output logic       o_extra
);
  leaf u_leaf (
    .clk   (clk),
    .rst_n (rst_n),
    .i_d   (i_d),
    .o_q   (o_q)
  );
endmodule
"""
        result, doc = run_on(tmp_path, top, [SUB_LEAF])
        assert result.returncode == 1
        v = [x for x in doc["violations"] if x["check"] == "undriven_output"]
        assert len(v) == 1
        assert v[0]["port"] == "o_extra"
        assert v[0]["severity"] == "error"

    def test_missing_module_def_is_warning(self, tmp_path):
        top = TOP_CLEAN.replace(
            "endmodule",
            "  phantom u_ph (\n    .i_x (i_d)\n  );\nendmodule")
        result, doc = run_on(tmp_path, top, [SUB_LEAF])
        assert result.returncode == 0, result.stderr
        v = [x for x in doc["violations"] if x["check"] == "missing_module_def"]
        assert len(v) == 1
        assert v[0]["module"] == "phantom"
        assert v[0]["instance"] == "u_ph"

    def test_positional_and_wildcard_flagged_not_analyzed(self, tmp_path):
        top = """
module top_m (
  input  logic       clk,
  input  logic       rst_n,
  input  logic [7:0] i_d,
  output logic [7:0] o_q
);
  leaf u_a (clk, rst_n, i_d, o_q);
  leaf u_b (.*);
endmodule
"""
        result, doc = run_on(tmp_path, top, [SUB_LEAF])
        assert result.returncode == 0, result.stderr
        checks = sorted(v["check"] for v in doc["violations"])
        assert checks == ["positional_connection", "wildcard_connection"]
        # No unconnected_port noise for unanalyzed connection styles.
        assert doc["summary"]["connections_checked"] == 0


# ---------------------------------------------------------------------------
# Honest-skip behavior for unresolvable widths
# ---------------------------------------------------------------------------

class TestWidthSkips:
    def test_unresolvable_port_width_is_skipped_not_guessed(self, tmp_path):
        sub = """
module leaf #(
  parameter type T = logic,
  parameter int W = mystery_fn(4)
) (
  input  logic         clk,
  input  logic [W-1:0] i_d
);
endmodule
"""
        top = """
module top_m (
  input  logic       clk,
  input  logic [7:0] i_d
);
  leaf u_leaf (
    .clk (clk),
    .i_d (i_d)
  );
endmodule
"""
        result, doc = run_on(tmp_path, top, [sub])
        assert result.returncode == 0, result.stderr
        assert not any(v["check"] == "width_mismatch"
                       for v in doc["violations"])
        assert doc["summary"]["width_checks"]["skipped"] >= 1

    def test_unsized_literal_connection_not_width_checked(self, tmp_path):
        top = TOP_CLEAN.replace(".i_d   (i_d)", ".i_d   ('0)")
        result, doc = run_on(tmp_path, top, [SUB_LEAF])
        assert result.returncode == 0, result.stderr
        assert doc["violations"] == []

    def test_sized_literal_width_is_checked(self, tmp_path):
        top = TOP_CLEAN.replace(".i_d   (i_d)", ".i_d   (4'hF)")
        result, doc = run_on(tmp_path, top, [SUB_LEAF])
        assert result.returncode == 1
        v = [x for x in doc["violations"] if x["check"] == "width_mismatch"]
        assert len(v) == 1
        assert "width 8" in v[0]["detail"] and "width 4" in v[0]["detail"]


# ---------------------------------------------------------------------------
# CLI contract
# ---------------------------------------------------------------------------

class TestCliContract:
    def test_missing_input_file_is_error(self, tmp_path):
        result = run_script(tmp_path / "nope.sv")
        assert result.returncode == 2
        assert "not found" in result.stderr

    def test_no_module_in_files_is_error(self, tmp_path):
        f = tmp_path / "empty.sv"
        f.write_text("// nothing here\n")
        result = run_script(f)
        assert result.returncode == 2
        assert "no module declarations" in result.stderr

    def test_unknown_top_name_is_error(self, tmp_path):
        f = tmp_path / "a.sv"
        f.write_text(SUB_LEAF)
        result = run_script(f, "--top", "nonexistent")
        assert result.returncode == 2
        assert "top module 'nonexistent' not found" in result.stderr

    def test_top_flag_selects_module(self, tmp_path):
        f = tmp_path / "both.sv"
        f.write_text(SUB_LEAF + TOP_CLEAN)
        out = tmp_path / "report.json"
        result = run_script(f, "--top", "top_clean", "-o", out)
        assert result.returncode == 0, result.stderr
        doc = json.loads(out.read_text())
        assert doc["top_module"] == "top_clean"
        assert doc["summary"]["instances"] == 1

    def test_duplicate_module_definition_is_error(self, tmp_path):
        a = tmp_path / "a.sv"
        b = tmp_path / "b.sv"
        a.write_text(SUB_LEAF)
        b.write_text(SUB_LEAF)
        result = run_script(a, b)
        assert result.returncode == 2
        assert "defined in both" in result.stderr

    def test_non_ansi_header_is_error(self, tmp_path):
        f = tmp_path / "old.sv"
        f.write_text("module old_style(a, b);\ninput a;\noutput b;\nendmodule\n")
        result = run_script(f)
        assert result.returncode == 2
        assert "non-ANSI" in result.stderr

    def test_stdout_mode_emits_json(self):
        result = run_script(EXAMPLES / "dut_top.sv",
                            EXAMPLES / "pixel_gen.sv",
                            EXAMPLES / "pixel_pack.sv")
        assert result.returncode == 1
        doc = json.loads(result.stdout)
        assert doc["tool"] == "check_connectivity.py"
        assert doc["top_module"] == "dut_top"

    def test_comments_do_not_confuse_parser(self, tmp_path):
        top = TOP_CLEAN.replace(
            "  leaf u_leaf (",
            "  // leaf u_fake ( .i_d(bogus) );\n  /* leaf u_c (.x(y)); */\n"
            "  leaf u_leaf (")
        result, doc = run_on(tmp_path, top, [SUB_LEAF])
        assert result.returncode == 0, result.stderr
        assert doc["summary"]["instances"] == 1
        assert doc["violations"] == []


class TestSafeConstEval:
    """Codex round-3 regression: width/parameter expressions must be evaluated
    by a restricted AST walker, never eval() — the char whitelist admits '**'
    and eval('9**9**9') would grind on unbounded big-int exponentiation."""

    @staticmethod
    def _mod():
        import importlib.util

        spec = importlib.util.spec_from_file_location("check_connectivity", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_pow_rejected_fast(self):
        import time

        mod = self._mod()
        start = time.time()
        assert mod.eval_const("2**30", {}) is None
        assert mod.eval_const("9**9**9", {}) is None
        assert time.time() - start < 2.0, "Pow must be rejected, not computed"

    def test_normal_arithmetic_still_works(self):
        mod = self._mod()
        assert mod.eval_const("(8+8)*2/4%7", {}) == 1
        assert mod.eval_const("W-1", {"W": 8}) == 7
        assert mod.eval_const("$clog2(16)", {}) == 4

    def test_operand_magnitude_bounded(self):
        mod = self._mod()
        assert mod.eval_const("4294967296*4294967296", {}) is None
        assert mod.eval_const("1/0", {}) is None


GROUPED_TOP_OK = """
module top_grp (
  input  logic        clk,
  input  logic        rst_n,
  input  logic [15:0] i_a, i_b,
  output logic [15:0] o_y
);
  leaf #(.W(16)) u_leaf (
    .clk   (clk),
    .rst_n (rst_n),
    .i_d   (i_b),
    .o_q   (o_y)
  );
endmodule
"""

GROUPED_TOP_MISMATCH = GROUPED_TOP_OK.replace("#(.W(16))", "#(.W(8))").replace(
    "output logic [15:0] o_y", "output logic [7:0] o_y")


class TestGroupedAnsiPorts:
    """Codex round-7 regression: second-and-later ports in grouped ANSI
    declarations (input logic [15:0] a, b) must inherit the packed range —
    they were previously width-checked as scalars."""

    def test_second_grouped_port_inherits_packed_range(self, tmp_path):
        result, doc = run_on(tmp_path, GROUPED_TOP_OK, [SUB_LEAF])
        assert result.returncode == 0, result.stderr
        assert doc["violations"] == [], (
            "i_b must be 16-bit via group inheritance, not a scalar")

    def test_second_grouped_port_width_mismatch_detected(self, tmp_path):
        result, doc = run_on(tmp_path, GROUPED_TOP_MISMATCH, [SUB_LEAF])
        assert result.returncode == 1
        v = [x for x in doc["violations"] if x["check"] == "width_mismatch"]
        assert v, doc["violations"]
        assert "16" in v[0]["detail"], (
            "mismatch must be reported against the inherited 16-bit width")
