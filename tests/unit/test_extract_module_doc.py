import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

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
