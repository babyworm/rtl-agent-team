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
