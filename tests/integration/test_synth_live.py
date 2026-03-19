"""Integration tests for synthesis with real Yosys."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tests.conftest import SKILLS_DIR, run_script
from tests.integration.conftest import requires_yosys

SYNTH_SCRIPT = SKILLS_DIR / "rat-init-project" / "templates" / "run_syn.sh"
PARSE_SCRIPT = (
    Path(__file__).resolve().parent.parent.parent
    / "skills" / "rtl-synth-check" / "scripts" / "parse_yosys_stat.py"
)


@requires_yosys
class TestYosysSynthLive:
    """Integration tests with real Yosys."""

    def test_simple_module_synthesis(self, tmp_path):
        sv = tmp_path / "counter.sv"
        sv.write_text("""\
module counter (
  input  logic       clk,
  input  logic       rst_n,
  output logic [7:0] o_count
);
  always_ff @(posedge clk or negedge rst_n)
    if (!rst_n) o_count <= '0;
    else        o_count <= o_count + 1'b1;
endmodule
""")

        # Write a yosys script
        ys = tmp_path / "synth.ys"
        ys.write_text(f"""\
read_verilog -sv {sv}
hierarchy -check -top counter
proc; opt
synth
stat -top counter
""")

        result = subprocess.run(
            ["yosys", "-s", str(ys)],
            capture_output=True, text=True,
            cwd=str(tmp_path), timeout=60,
        )
        assert result.returncode == 0
        assert "Number of cells:" in result.stdout or "Number of wires:" in result.stdout

    def test_parse_yosys_stat_integration(self, tmp_path):
        """Full pipeline: yosys synthesis → parse_yosys_stat.py → summary.json."""
        sv = tmp_path / "adder.sv"
        sv.write_text("""\
module adder (
  input  logic [7:0] i_a,
  input  logic [7:0] i_b,
  output logic [8:0] o_sum
);
  assign o_sum = i_a + i_b;
endmodule
""")

        ys = tmp_path / "synth.ys"
        ys.write_text(f"""\
read_verilog -sv {sv}
hierarchy -check -top adder
proc; opt
synth
stat -top adder
""")

        # Run yosys
        synth_result = subprocess.run(
            ["yosys", "-s", str(ys)],
            capture_output=True, text=True,
            cwd=str(tmp_path), timeout=60,
        )
        assert synth_result.returncode == 0

        # Save output
        yosys_out = tmp_path / "yosys_output.txt"
        yosys_out.write_text(synth_result.stdout)

        # Run parser
        summary_path = tmp_path / "summary.json"
        parse_result = subprocess.run(
            [sys.executable, str(PARSE_SCRIPT), str(yosys_out), "--output", str(summary_path)],
            capture_output=True, text=True, timeout=30,
        )
        assert parse_result.returncode == 0
        assert summary_path.exists()

        summary = json.loads(summary_path.read_text())
        assert summary["verdict"] == "PASS"
        assert summary["total_cells"] > 0
        assert summary["latches_found"] == 0


@requires_yosys
class TestSynthScriptLive:
    """Integration tests for run_syn.sh template with Yosys."""

    @pytest.fixture
    def synth_script_path(self):
        if not SYNTH_SCRIPT.exists():
            pytest.skip("run_syn.sh template not found")
        return SYNTH_SCRIPT

    def test_yosys_synthesis(self, tmp_path, synth_script_path):
        sv = tmp_path / "mux.sv"
        sv.write_text("""\
module mux (
  input  logic       i_sel,
  input  logic [7:0] i_a,
  input  logic [7:0] i_b,
  output logic [7:0] o_y
);
  assign o_y = i_sel ? i_b : i_a;
endmodule
""")
        flist = tmp_path / "filelist.f"
        flist.write_text(str(sv) + "\n")

        result = run_script(
            synth_script_path,
            "--tool", "yosys",
            "--top", "mux",
            "-f", str(flist),
            "--outdir", str(tmp_path / "syn_out"),
            timeout=120,
        )
        assert result.returncode == 0
