import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

VERIBLE_AVAILABLE = shutil.which("verible-verilog-syntax") is not None
needs_verible = pytest.mark.skipif(not VERIBLE_AVAILABLE, reason="verible not installed")

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "rtl-document" / "scripts" / "extract_module_doc.py"
FIXTURES = ROOT / "tests" / "fixtures" / "rtl-document"


def _run(args, env=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=env
    )


def test_cli_help_exits_zero():
    r = _run(["--help"])
    assert r.returncode == 0
    assert "--rtl" in r.stdout
    assert "--out" in r.stdout


def test_missing_verible_returns_exit_code_2(tmp_path, monkeypatch):
    # Simulate verible-not-on-PATH: clear PATH.
    env = os.environ.copy()
    env["PATH"] = ""
    out = tmp_path / "x.json"
    r = _run(["--rtl", str(FIXTURES / "simple_fifo.sv"), "--out", str(out)], env=env)
    assert r.returncode == 2
    assert "verible" in r.stderr.lower()


@needs_verible
def test_simple_fifo_ports(tmp_path):
    out = tmp_path / "simple_fifo.json"
    r = _run(["--rtl", str(FIXTURES / "simple_fifo.sv"), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text())
    assert data["module_name"] == "simple_fifo"
    names = [p["name"] for p in data["ports"]]
    assert names == [
        "sys_clk", "sys_rst_n", "i_push", "i_data", "i_pop", "o_data", "o_full", "o_empty"
    ]
    by_name = {p["name"]: p for p in data["ports"]}
    assert by_name["sys_clk"]["kind"] == "clock"
    assert by_name["sys_clk"]["domain"] == "sys"
    assert by_name["sys_rst_n"]["kind"] == "reset"
    assert by_name["i_push"]["kind"] == "data"
    assert by_name["i_data"]["dir"] == "input"
    assert by_name["o_full"]["dir"] == "output"
    assert isinstance(by_name["i_data"]["width"], str)
    assert by_name["i_data"]["width"] in {"DATA_WIDTH", "1"}  # accept either form


@needs_verible
def test_simple_fifo_parameters(tmp_path):
    out = tmp_path / "x.json"
    _run(["--rtl", str(FIXTURES / "simple_fifo.sv"), "--out", str(out)])
    data = json.loads(out.read_text())
    pnames = {p["name"]: p for p in data["parameters"]}
    assert pnames["DATA_WIDTH"]["default"] == "32"
    assert pnames["DEPTH"]["default"] == "16"


@needs_verible
def test_axi_bridge_instances(tmp_path):
    out = tmp_path / "x.json"
    _run(["--rtl", str(FIXTURES / "axi_stream_bridge.sv"), "--out", str(out)])
    data = json.loads(out.read_text())
    inst_names = sorted(i["name"] for i in data["instances"])
    assert inst_names == ["u_egress_fifo", "u_ingress_fifo"]
    assert sorted(data["clock_domains"]) == ["pixel", "sys"]


@needs_verible
def test_cabac_fsm_candidates(tmp_path):
    out = tmp_path / "x.json"
    _run(["--rtl", str(FIXTURES / "cabac_encoder_excerpt.sv"), "--out", str(out)])
    data = json.loads(out.read_text())
    assert len(data["fsm_candidates"]) >= 1
    fsm = data["fsm_candidates"][0]
    assert fsm["state_register"] == "state"
    assert sorted(fsm["states"]) == ["ST_ENCODE", "ST_FLUSH", "ST_IDLE"]


@needs_verible
def test_parse_error_returns_exit_3(tmp_path):
    bad = tmp_path / "bad.sv"
    bad.write_text("module bad ( oops\n")  # unterminated
    out = tmp_path / "x.json"
    r = _run(["--rtl", str(bad), "--out", str(out)])
    assert r.returncode == 3
    assert "parse" in r.stderr.lower() or "syntax" in r.stderr.lower()


@needs_verible
def test_convention_violation_suffix_port(tmp_path):
    bad = tmp_path / "bad_naming.sv"
    # Ports split across lines — PORT_RE is line-anchored and cannot match
    # single-line multi-port declarations. Fixture written one port per line.
    bad.write_text(
        "module bad_naming (\n"
        "  input logic sys_clk,\n"
        "  input logic sys_rst_n,\n"
        "  input logic data_i,\n"
        "  output logic data_o\n"
        ");\nendmodule\n"
    )
    out = tmp_path / "x.json"
    _run(["--rtl", str(bad), "--out", str(out)])
    data = json.loads(out.read_text())
    sigs = {v["signal"] for v in data["convention_violations"]}
    assert sigs == {"data_i", "data_o"}


@needs_verible
def test_synth_summary(tmp_path):
    out = tmp_path / "x.json"
    _run([
        "--rtl", str(FIXTURES / "simple_fifo.sv"),
        "--syn-report", str(FIXTURES / "synth_report.txt"),
        "--out", str(out),
    ])
    data = json.loads(out.read_text())
    assert data["synth_summary"]["area_um2"] == 12450.30
    assert data["synth_summary"]["wns_ns"] == 0.21
    assert data["synth_summary"]["tns_ns"] == -3.40


@needs_verible
def test_literal_width_parsed(tmp_path):
    """Literal bus widths like [31:0] should yield the bit count, not '1'."""
    sv = tmp_path / "literal_width.sv"
    sv.write_text(
        "module literal_width (\n"
        "  input  logic        sys_clk,\n"
        "  input  logic        sys_rst_n,\n"
        "  input  logic [31:0] i_addr,\n"
        "  input  logic [7:0]  i_data,\n"
        "  output logic [15:0] o_count\n"
        ");\nendmodule\n"
    )
    out = tmp_path / "x.json"
    _run(["--rtl", str(sv), "--out", str(out)])
    data = json.loads(out.read_text())
    by_name = {p["name"]: p for p in data["ports"]}
    assert by_name["i_addr"]["width"] == "32"
    assert by_name["i_data"]["width"] == "8"
    assert by_name["o_count"]["width"] == "16"


@needs_verible
def test_multi_port_per_line(tmp_path):
    """Comma-separated identifiers on one declaration line must all be captured,
    inheriting the leading port's direction + width."""
    sv = tmp_path / "multi_port.sv"
    sv.write_text(
        "module multi_port (\n"
        "  input  logic       sys_clk,\n"
        "  input  logic       sys_rst_n,\n"
        "  input  logic [3:0] i_a, i_b, i_c,\n"
        "  output logic       o_x, o_y\n"
        ");\nendmodule\n"
    )
    out = tmp_path / "x.json"
    _run(["--rtl", str(sv), "--out", str(out)])
    data = json.loads(out.read_text())
    names = {p["name"] for p in data["ports"]}
    assert {"i_a", "i_b", "i_c", "o_x", "o_y"}.issubset(names)
    by_name = {p["name"]: p for p in data["ports"]}
    # i_a, i_b, i_c all inherit direction=input + width="4"
    for n in ("i_a", "i_b", "i_c"):
        assert by_name[n]["dir"] == "input"
        assert by_name[n]["width"] == "4"
    # o_x, o_y inherit direction=output + width="1"
    for n in ("o_x", "o_y"):
        assert by_name[n]["dir"] == "output"
        assert by_name[n]["width"] == "1"


@needs_verible
def test_non_u_prefix_instance_captured(tmp_path):
    """INSTANCE_RE captures instances regardless of naming convention.

    Pre-fix, only u_* names were captured, silently dropping fifo0/inst_a/etc.
    Post-fix, all identifier-named instances are emitted; convention violations
    are surfaced separately (not silently dropped).
    """
    sv = tmp_path / "non_u.sv"
    sv.write_text(
        "module non_u (\n"
        "  input  logic sys_clk,\n"
        "  input  logic sys_rst_n,\n"
        "  output logic o_x\n"
        ");\n"
        "  some_module fifo0  (.*);\n"
        "  other_mod   inst_a (.*);\n"
        "  yet_another u_legit (.*);\n"
        "endmodule\n"
    )
    out = tmp_path / "x.json"
    _run(["--rtl", str(sv), "--out", str(out)])
    data = json.loads(out.read_text())
    inst_names = {i["name"] for i in data["instances"]}
    assert {"fifo0", "inst_a", "u_legit"}.issubset(inst_names)


@needs_verible
def test_reserved_keywords_not_instances(tmp_path):
    """Expanded _RESERVED set must filter SV control-flow constructs out
    of the instance list now that INSTANCE_RE accepts any identifier."""
    sv = tmp_path / "reserved.sv"
    sv.write_text(
        "module reserved (\n"
        "  input  logic sys_clk,\n"
        "  input  logic sys_rst_n,\n"
        "  output logic o_x\n"
        ");\n"
        "  some_module u_real (.*);\n"
        "  always_ff @(posedge sys_clk) begin\n"
        "    if (sys_rst_n) o_x <= 1'b0;\n"
        "  end\n"
        "  assign o_x = 1'b1;\n"
        "endmodule\n"
    )
    out = tmp_path / "x.json"
    _run(["--rtl", str(sv), "--out", str(out)])
    data = json.loads(out.read_text())
    inst_modules = {i["module"] for i in data["instances"]}
    # Only the real instance survives; SV keywords are filtered.
    assert "some_module" in inst_modules
    for kw in ("always_ff", "if", "assign", "module", "endmodule"):
        assert kw not in inst_modules, f"{kw} should be filtered as reserved"


@needs_verible
def test_lowercase_parameter_captured(tmp_path):
    """PARAM_RE accepts any identifier casing, not just ALL_CAPS."""
    sv = tmp_path / "lowercase_param.sv"
    sv.write_text(
        "module lowercase_param #(\n"
        "  parameter int dataWidth = 32,\n"
        "  parameter int depth = 16,\n"
        "  parameter LATENCY = 4\n"
        ") (\n"
        "  input  logic sys_clk,\n"
        "  input  logic sys_rst_n\n"
        ");\nendmodule\n"
    )
    out = tmp_path / "x.json"
    _run(["--rtl", str(sv), "--out", str(out)])
    data = json.loads(out.read_text())
    param_names = {p["name"] for p in data["parameters"]}
    assert {"dataWidth", "depth", "LATENCY"}.issubset(param_names)


@needs_verible
def test_wrapped_port_declaration(tmp_path):
    """Port declarations wrapped across multiple lines are still captured.

    Multi-line port wrapping is a common SV formatting style for wide port
    lists. Pre-fix, the line-anchored PORT_RE silently dropped the port
    because direction/width/name landed on separate lines.
    """
    sv = tmp_path / "wrapped.sv"
    sv.write_text(
        "module wrapped (\n"
        "  input  logic\n"
        "                  sys_clk,\n"
        "  input  logic\n"
        "                  sys_rst_n,\n"
        "  input  logic\n"
        "         [31:0]\n"
        "                  i_addr,\n"
        "  output logic\n"
        "         [15:0]\n"
        "                  o_data\n"
        ");\nendmodule\n"
    )
    out = tmp_path / "x.json"
    _run(["--rtl", str(sv), "--out", str(out)])
    data = json.loads(out.read_text())
    names = [p["name"] for p in data["ports"]]
    assert names == ["sys_clk", "sys_rst_n", "i_addr", "o_data"]
    by_name = {p["name"]: p for p in data["ports"]}
    assert by_name["i_addr"]["width"] == "32"
    assert by_name["o_data"]["width"] == "16"
    assert by_name["i_addr"]["dir"] == "input"
    assert by_name["o_data"]["dir"] == "output"


@needs_verible
def test_comments_between_ports_do_not_fuse_declarations(tmp_path):
    """Line and block comments between port declarations must not bridge
    adjacent declarations after flattening (regression for // APB notes)."""
    sv = tmp_path / "with_comments.sv"
    sv.write_text(
        "module with_comments (\n"
        "  input  logic sys_clk,\n"
        "  // line comment between declarations\n"
        "  input  logic sys_rst_n,\n"
        "  /* block comment\n"
        "     spanning lines */\n"
        "  input  logic [3:0] i_data,\n"
        "  output logic       o_valid\n"
        ");\nendmodule\n"
    )
    out = tmp_path / "x.json"
    _run(["--rtl", str(sv), "--out", str(out)])
    data = json.loads(out.read_text())
    names = [p["name"] for p in data["ports"]]
    assert names == ["sys_clk", "sys_rst_n", "i_data", "o_valid"]
