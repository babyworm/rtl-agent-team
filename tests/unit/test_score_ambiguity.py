import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "p1-spec-research" / "scripts" / "score_ambiguity.py"


def _run(args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)


def test_help_exits_zero():
    r = _run(["--help"])
    assert r.returncode == 0
    assert "--functionality" in r.stdout
    assert "--json" in r.stdout


def test_human_mode_basic():
    r = _run(["--functionality", "85", "--ppa", "70",
              "--scope", "90", "--verification", "60"])
    assert r.returncode == 0
    assert "Ambiguity:" in r.stdout
    assert "Functionality:  85/100" in r.stdout
    assert "Verification:   60/100" in r.stdout
    assert "Lowest:" in r.stdout
    assert "verification" in r.stdout.lower()


def test_json_mode_schema():
    r = _run(["--json",
              "--functionality", "85", "--ppa", "70",
              "--scope", "90", "--verification", "60"])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["ambiguity"] == 24
    assert data["lowest"] == "verification"
    assert data["lowest_score"] == 60
    assert data["exit"] is False


def test_json_exit_true_when_under_threshold():
    r = _run(["--json",
              "--functionality", "85", "--ppa", "85",
              "--scope", "85", "--verification", "85"])
    data = json.loads(r.stdout)
    assert data["ambiguity"] == 15
    assert data["exit"] is True


def test_invalid_score_rejected():
    r = _run(["--functionality", "150", "--ppa", "70",
              "--scope", "90", "--verification", "60"])
    assert r.returncode != 0
    assert "0" in r.stderr or "100" in r.stderr
