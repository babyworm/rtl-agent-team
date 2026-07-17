"""Tests for skills/rtl-ip-instantiate/scripts/gen_instantiation.py.

Validates the deterministic wrapper-skeleton contract: vendor module header
parsing, convention-compliant name mapping (i_/o_/io_ prefixes, clk/rst_n),
parameter pass-through with UPPER_SNAKE_CASE rename, --tie tie-off handling,
and regeneration sync of the committed vendor_sram_2p example.

All script invocations go through subprocess so the argparse CLI surface is
exercised exactly as the skill documents it (same pattern as gen_ipxact.py's
pixel_fifo example in test_asset_bundle_deepfill.py).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = ROOT / "skills" / "rtl-ip-instantiate"
SCRIPT = SKILL_DIR / "scripts" / "gen_instantiation.py"
EXAMPLE_DIR = SKILL_DIR / "examples" / "vendor_sram_2p"

EXAMPLE_TIES = [
    "--tie", "EMA=3'b010:vendor-recommended margin setting",
    "--tie", "RET1N=1'b1:retention mode not used",
    "--tie", "STOV=1'b0:self-time override disabled",
]


def run_script(*args, cwd=None):
    """Run gen_instantiation.py via subprocess; return CompletedProcess."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *[str(a) for a in args]],
        capture_output=True, text=True, cwd=cwd, check=False)


def gen_example(tmp_path):
    out = tmp_path / "sram_2p_wrapper.sv"
    result = run_script(EXAMPLE_DIR / "vendor_sram_2p.v", "-o", out,
                        *EXAMPLE_TIES)
    return result, out


class TestVendorSram2pExample:
    def test_example_generates_successfully(self, tmp_path):
        result, out = gen_example(tmp_path)
        assert result.returncode == 0, result.stderr
        assert out.is_file()
        assert "ip=vendor_sram_2p wrapper=sram_2p_wrapper" in result.stdout
        assert "(mapped=8, tied=3)" in result.stdout

    def test_committed_example_wrapper_matches_regeneration(self, tmp_path):
        """examples/vendor_sram_2p/sram_2p_wrapper.sv must stay in sync."""
        out = tmp_path / "regen.sv"
        result = run_script("vendor_sram_2p.v", "-o", out, *EXAMPLE_TIES,
                            cwd=EXAMPLE_DIR)
        assert result.returncode == 0, result.stderr
        committed = (EXAMPLE_DIR / "sram_2p_wrapper.sv").read_text()
        assert out.read_text() == committed

    def test_wrapper_and_instance_naming(self, tmp_path):
        _, out = gen_example(tmp_path)
        text = out.read_text()
        assert "module sram_2p_wrapper #(" in text  # vendor_ prefix stripped
        assert ") u_sram_2p (" in text              # u_ instance prefix

    def test_convention_port_mapping(self, tmp_path):
        _, out = gen_example(tmp_path)
        text = out.read_text()
        # Clocks: CLKA/CLKB → {domain}_clk form
        assert "input  logic" in text and " a_clk," in text
        assert " b_clk," in text
        # Data ports: i_/o_ prefixes, snake_case, widths as expressions
        assert "input  logic [$clog2(D)-1:0] i_aa," in text
        assert "input  logic [W-1:0]         i_da," in text
        assert "output logic [W-1:0]         o_qb" in text
        # Instance mapping keeps vendor names verbatim
        assert ".CLKA   (a_clk)," in text
        assert ".QB     (o_qb)," in text

    def test_parameter_pass_through(self, tmp_path):
        _, out = gen_example(tmp_path)
        text = out.read_text()
        assert "parameter int W = 32," in text
        assert "parameter int D = 256" in text
        assert ".W (W)," in text
        assert ".D (D)" in text
        assert "// PARAM:" in text

    def test_tie_offs_excluded_from_wrapper_ports(self, tmp_path):
        _, out = gen_example(tmp_path)
        text = out.read_text()
        header = text.split(");")[0]  # wrapper port list only
        for tied in ("i_ema", "i_ret1n", "i_stov", "EMA", "RET1N", "STOV"):
            assert tied not in header
        assert ".EMA    (3'b010),  // TIED: vendor-recommended margin setting" in text
        assert ".RET1N  (1'b1),    // TIED: retention mode not used" in text
        assert ".STOV   (1'b0)     // TIED: self-time override disabled" in text
        # Tie-off documentation table present
        assert "| Vendor Port | Tied To | Reason" in text

    def test_generated_wrapper_has_no_reg_wire_declarations(self, tmp_path):
        _, out = gen_example(tmp_path)
        for line in out.read_text().splitlines():
            stripped = line.strip()
            assert not stripped.startswith(("reg ", "wire ")), line


class TestVendorNameMapping:
    def write_camel(self, tmp_path):
        src = tmp_path / "acme_phy.v"
        src.write_text(
            "module acme_phy #(parameter AddrWidth = 8) (\n"
            "    input Clk,\n"
            "    input RstN,\n"
            "    input [AddrWidth-1:0] WrAddr,\n"
            "    input DataValid,\n"
            "    output TxReady\n"
            ");\nendmodule\n")
        return src

    def test_camelcase_ports_become_snake_case(self, tmp_path):
        src = self.write_camel(tmp_path)
        out = tmp_path / "acme_phy_wrapper.sv"
        result = run_script(src, "-o", out)
        assert result.returncode == 0, result.stderr
        text = out.read_text()
        assert "module acme_phy_wrapper #(" in text
        assert " clk," in text            # single clock → bare clk
        assert " rst_n," in text          # RstN → rst_n (active-low marker kept)
        assert "i_wr_addr," in text
        assert "i_data_valid," in text
        assert "o_tx_ready" in text
        assert ".Clk" in text and "(clk)" in text

    def test_parameter_renamed_to_upper_snake_case(self, tmp_path):
        src = self.write_camel(tmp_path)
        out = tmp_path / "w.sv"
        result = run_script(src, "-o", out)
        text = out.read_text()
        assert "parameter int ADDR_WIDTH = 8" in text
        assert ".AddrWidth (ADDR_WIDTH)" in text   # vendor name in instance
        # width expression rewritten to the renamed parameter
        assert "[ADDR_WIDTH-1:0] i_wr_addr" in text
        assert "renamed to 'ADDR_WIDTH'" in result.stderr

    def test_domain_flag_prefixes_single_clock_reset(self, tmp_path):
        src = self.write_camel(tmp_path)
        out = tmp_path / "w.sv"
        run_script(src, "-o", out, "--domain", "sys")
        text = out.read_text()
        assert " sys_clk," in text
        assert " sys_rst_n," in text

    def test_direction_suffix_stripped_before_prefixing(self, tmp_path):
        src = tmp_path / "ip.v"
        src.write_text(
            "module ip (input clk_i, input rst_ni, input [7:0] data_i,\n"
            "           output [7:0] data_o);\nendmodule\n")
        out = tmp_path / "w.sv"
        result = run_script(src, "-o", out)
        assert result.returncode == 0, result.stderr
        text = out.read_text()
        assert " clk," in text
        assert " rst_n," in text
        assert "i_data," in text
        assert "o_data" in text

    def test_active_high_reset_gets_polarity_todo(self, tmp_path):
        src = tmp_path / "ip.v"
        src.write_text("module ip (input clk, input RST, input i_d,\n"
                       "           output o_q);\nendmodule\n")
        out = tmp_path / "w.sv"
        result = run_script(src, "-o", out)
        assert result.returncode == 0, result.stderr
        text = out.read_text()
        line = [ln for ln in text.splitlines() if " rst_n," in ln]
        assert line and "TODO: verify polarity" in line[0]

    def test_wrapper_name_override(self, tmp_path):
        src = self.write_camel(tmp_path)
        out = tmp_path / "w.sv"
        run_script(src, "-o", out, "--wrapper-name", "phy_wrap")
        assert "module phy_wrap #(" in out.read_text()

    def test_output_tie_nc_leaves_port_unconnected(self, tmp_path):
        src = tmp_path / "ip.v"
        src.write_text("module ip (input clk, input i_d, output o_q,\n"
                       "           output Dbg);\nendmodule\n")
        out = tmp_path / "w.sv"
        result = run_script(src, "-o", out, "--tie", "Dbg=NC")
        assert result.returncode == 0, result.stderr
        text = out.read_text()
        assert ".Dbg" in text and "(/* NC */)" in text
        assert "// TIED: TODO — document reason" in text


class TestErrorHandling:
    def test_missing_input_file_is_error(self, tmp_path):
        result = run_script(tmp_path / "nope.v")
        assert result.returncode == 2
        assert "not found" in result.stderr

    def test_no_module_is_error(self, tmp_path):
        src = tmp_path / "empty.v"
        src.write_text("// nothing here\n")
        result = run_script(src, "-o", tmp_path / "w.sv")
        assert result.returncode == 2
        assert "no module declaration" in result.stderr

    def test_non_ansi_header_is_error(self, tmp_path):
        src = tmp_path / "old.v"
        src.write_text("module old_style(a, b);\ninput a;\noutput b;\nendmodule\n")
        result = run_script(src, "-o", tmp_path / "w.sv")
        assert result.returncode == 2
        assert "non-ANSI" in result.stderr

    def test_unknown_tie_port_is_error(self, tmp_path):
        result = run_script(EXAMPLE_DIR / "vendor_sram_2p.v",
                            "-o", tmp_path / "w.sv", "--tie", "NOPE=1'b0")
        assert result.returncode == 2
        assert "'NOPE' not found" in result.stderr

    def test_malformed_tie_is_error(self, tmp_path):
        result = run_script(EXAMPLE_DIR / "vendor_sram_2p.v",
                            "-o", tmp_path / "w.sv", "--tie", "EMA")
        assert result.returncode == 2
        assert "expected PORT=VALUE" in result.stderr

    def test_wrapper_name_collision_is_error(self, tmp_path):
        src = tmp_path / "ip.v"
        src.write_text("module ip (input clk, input data_i, input i_data,\n"
                       "           output o_q);\nendmodule\n")
        result = run_script(src, "-o", tmp_path / "w.sv")
        assert result.returncode == 2
        assert "collision" in result.stderr

    def test_all_ports_tied_is_error(self, tmp_path):
        src = tmp_path / "ip.v"
        src.write_text("module ip (input TM);\nendmodule\n")
        result = run_script(src, "-o", tmp_path / "w.sv", "--tie", "TM=1'b0")
        assert result.returncode == 2
        assert "nothing to wrap" in result.stderr


def test_skill_md_no_longer_marks_script_as_stub():
    """SKILL.md Assets row must describe the real script, not a stub."""
    assert "NotImplementedError" not in SCRIPT.read_text()
    skill_md = (SKILL_DIR / "SKILL.md").read_text()
    row = [ln for ln in skill_md.splitlines()
           if "`scripts/gen_instantiation.py`" in ln]
    assert row and "deep-fill" not in row[0] and "Stub" not in row[0]
