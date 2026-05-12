import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "rtl-document" / "scripts" / "render_doc.py"
TEMPLATE_DIR = ROOT / "skills" / "rtl-document" / "templates"


def _run(args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)


def test_help_exits_zero():
    r = _run(["--help"])
    assert r.returncode == 0
    assert "--template-dir" in r.stdout


def test_minimal_render_no_optional_sections(tmp_path):
    payload = {
        "module_name": "simple_fifo",
        "file": "rtl/simple_fifo/simple_fifo.sv",
        "parameters": [{"name": "DATA_WIDTH", "type": "int", "default": "32"}],
        "ports": [
            {"name": "sys_clk",   "dir": "input",  "width": 1,  "domain": "sys", "kind": "clock"},
            {"name": "sys_rst_n", "dir": "input",  "width": 1,  "domain": "sys", "kind": "reset"},
            {"name": "i_data",    "dir": "input",  "width": 32, "domain": "sys", "kind": "data"},
        ],
        "instances": [],
        "fsm_candidates": [],
        "clock_domains": ["sys"],
        "convention_violations": [],
    }
    jpath = tmp_path / "x.json"
    jpath.write_text(json.dumps(payload))
    out = tmp_path / "doc.md"
    r = _run(["--json", str(jpath), "--template-dir", str(TEMPLATE_DIR), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    body = out.read_text()
    assert "FSM States" not in body
    assert "```d2" not in body
    assert "i_data" in body
    assert "LLM_FILL: functional description" in body


def test_fsm_and_diagram_when_present(tmp_path):
    payload = {
        "module_name": "cabac_encoder",
        "file": "rtl/cabac/cabac.sv",
        "parameters": [],
        "ports": [
            {"name": "sys_clk", "dir": "input", "width": 1, "domain": "sys", "kind": "clock"},
        ],
        "instances": [
            {"name": "u_a", "module": "ma"},
            {"name": "u_b", "module": "mb"},
        ],
        "fsm_candidates": [
            {"state_register": "state", "type_name": "state_e",
             "states": ["ST_IDLE", "ST_ENCODE"]}
        ],
        "clock_domains": ["sys"],
        "convention_violations": [],
    }
    jpath = tmp_path / "x.json"
    jpath.write_text(json.dumps(payload))
    out = tmp_path / "doc.md"
    r = _run(["--json", str(jpath), "--template-dir", str(TEMPLATE_DIR), "--out", str(out)])
    assert r.returncode == 0
    body = out.read_text()
    assert "FSM States" in body
    assert "stateDiagram-v2" in body
    assert "```d2" in body
    assert "u_a" in body and "u_b" in body
    assert "LLM_FILL: FSM state semantics" in body


def test_violation_banner(tmp_path):
    payload = {
        "module_name": "bad",
        "file": "rtl/bad.sv",
        "parameters": [], "ports": [], "instances": [],
        "fsm_candidates": [], "clock_domains": [],
        "convention_violations": [
            {"signal": "data_i", "rule": "Use i_/o_/io_ prefix (not suffix)"}
        ],
    }
    jpath = tmp_path / "x.json"
    jpath.write_text(json.dumps(payload))
    out = tmp_path / "doc.md"
    _run(["--json", str(jpath), "--template-dir", str(TEMPLATE_DIR), "--out", str(out)])
    body = out.read_text()
    assert "Convention Violations" in body
    assert "data_i" in body
