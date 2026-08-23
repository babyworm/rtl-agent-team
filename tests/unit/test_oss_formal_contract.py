"""Contracts for the OSS SymbiYosys formal flow.

These tests protect against the old false contract where full concurrent SVA
was treated as usable OSS SBY input and sv2v/SBY conversion was described as
implicit. CI may not have SBY installed, but Yosys is enough to verify that the
OSS harness elaborates into real formal check cells.
"""

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT, SKILLS_DIR

SVA_SKILL = SKILLS_DIR / "rtl-p5s-sva-check"
HARNESS_TEMPLATE = SVA_SKILL / "templates" / "yosys-formal-harness-template.sv"
SVA_TEMPLATE = SVA_SKILL / "templates" / "sva-property-template.sv"
SBY_TEMPLATE = SVA_SKILL / "templates" / "sby-config.sby"
SVA_POLICY = SKILLS_DIR / "rtl-p5s-sva-policy" / "SKILL.md"
VERIFY_POLICY = SKILLS_DIR / "rtl-p5-verify-policy" / "SKILL.md"
ORCHESTRATOR = REPO_ROOT / "agents" / "p5s-sva-orchestrator.md"
EXTRACTOR = REPO_ROOT / "agents" / "sva-extractor.md"


def _render(text: str) -> str:
    return (
        text.replace("{{MODULE}}", "demo_dut")
        .replace("{{DOMAIN}}", "sys")
        .replace("{{RTL_SRC_DIR}}", "rtl/demo_dut")
        .replace("{{TOP_NAME}}", "demo_dut_formal_harness")
    )


def _read_all(paths: list[Path]) -> str:
    return "\n".join(path.read_text() for path in paths)


def test_yosys_harness_elaborates_with_real_check_cells(tmp_path):
    yosys = shutil.which("yosys")
    if yosys is None:
        pytest.skip("Yosys is not installed in this environment")

    (tmp_path / "demo_dut_v2v.v").write_text(
        """
module demo_dut #(parameter DATA_WIDTH = 8) (
  input sys_clk,
  input sys_rst_n,
  input i_valid,
  output o_ready,
  input [DATA_WIDTH-1:0] i_data,
  output [DATA_WIDTH-1:0] o_data
);
  assign o_ready = sys_rst_n;
  assign o_data = i_data;
endmodule
"""
    )
    (tmp_path / "demo_dut_formal_harness.sv").write_text(_render(HARNESS_TEMPLATE.read_text()))

    result = subprocess.run(
        [
            yosys,
            "-Q",
            "-p",
            (
                "read_verilog -formal demo_dut_v2v.v; "
                "read_verilog -formal -sv demo_dut_formal_harness.sv; "
                "prep -top demo_dut_formal_harness"
            ),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_concurrent_sva_is_commercial_only_and_not_sv2v_input():
    commercial_template = SVA_TEMPLATE.read_text()
    harness_template = HARNESS_TEMPLATE.read_text()
    flow_text = _read_all([SVA_SKILL / "SKILL.md", SVA_POLICY, ORCHESTRATOR, EXTRACTOR])

    assert "assert property" in commercial_template
    assert "commercial" in commercial_template.lower()
    assert "assert property" not in harness_template
    assert re.search(r"sv2v\s+--write=.*_v2v\.v", flow_text)
    assert not re.search(r"sv2v\s+--write[^\n]*(?:_props|\.sva)", flow_text)
    assert "Do NOT pass full concurrent SVA" in flow_text or "Do NOT run sv2v on full concurrent SVA" in flow_text


def test_sby_template_uses_copied_basenames_explicit_tasks_and_property_gate():
    sby = _render(SBY_TEMPLATE.read_text())

    assert "sby -f formal/demo_dut.sby bmc" in sby
    assert "sby -f formal/demo_dut.sby prove" in sby
    assert "sby -f formal/demo_dut.sby cover" in sby
    assert "read -formal rtl/demo_dut/demo_dut_v2v.v" in sby
    assert "read -formal -sv formal/demo_dut_formal_harness.sv" in sby
    assert "prep -top demo_dut_formal_harness" in sby
    assert re.search(r"rtl/demo_dut/demo_dut_v2v\.v", sby)
    assert re.search(r"formal/demo_dut_formal_harness\.sv", sby)
    assert "{{RTL_SRC_DIR}}/demo_dut_v2v.v" not in sby
    assert "formal/demo_dut_props.sv" not in sby


def test_old_false_formal_claims_are_absent():
    text = _read_all([SVA_SKILL / "SKILL.md", SVA_POLICY, VERIFY_POLICY, ORCHESTRATOR, EXTRACTOR])

    forbidden = [
        "handles sv2v internally",
        "Do NOT instruct manual sv2v execution",
        "per-property prove/fail",
        "sby -f formal/{module}_prove.sby",
        "_oss_formal_top",
        "formal_verify.json produced with status per property",
        "non-blocking for module graduation",
    ]
    for phrase in forbidden:
        assert phrase not in text

    assert "formal/formal_verify_{module}.json" in text
    assert "synthesis signoff and module graduation remain blocked" in text
