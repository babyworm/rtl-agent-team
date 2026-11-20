"""rat-doctor marks settings ✓/?/✗ from the same lookups the runner uses."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest

from tests.conftest import REPO_ROOT

DOCTOR = REPO_ROOT / "scripts/rat_doctor.py"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from eda_setup import tool_fingerprint  # noqa: E402


def doctor(root, env=None):
    result = subprocess.run([sys.executable, str(DOCTOR), "--root", str(root), "--json"],
                            env={**os.environ, **(env or {})}, capture_output=True, text=True, timeout=60)
    rows = {(row["level"], row["item"]): row for row in json.loads(result.stdout)}
    return result.returncode, rows


def site(data, probe_status, workload):
    entry = {"path": "/opt/fixture/xrun", "detected": True, "env_source": "", "env_shell": "bash"}
    entry["probe"] = {"status": probe_status, "evidence_level": "workload_passed" if workload else "command_passed",
                      "license_checked": workload, "failure": "license_failed" if probe_status == "failed" else "",
                      "configuration_sha256": tool_fingerprint(entry)}
    (data / "sites").mkdir(parents=True, exist_ok=True)
    (data / "env-config.json").write_text(json.dumps({"default_site": "fixture"}))
    (data / "sites/fixture.json").write_text(json.dumps({
        "schema_version": 1, "measured_at": time.time(), "home": "/home/fixture",
        "execution": {"backend": "ssh", "host": "eda.example.invalid", "python": "/usr/bin/python3"},
        "tools": {"simulators": {"xrun": entry}}, "preferences": {"simulator": "xrun"},
        "technology": {"db": "/opt/fixture/cells.db"}}))


def test_missing_settings_folder_is_a_failure(tmp_path):
    code, rows = doctor(tmp_path, {"RAT_DATA_DIR": "", "CLAUDE_PLUGIN_DATA": ""})
    assert code == 1 and rows[("plugin", "settings folder")]["status"] == "✗"
    assert "restart Claude Code" in rows[("plugin", "settings folder")]["fix"]


@pytest.mark.parametrize("probe_status,workload,expected", [
    ("completed", True, "✓"), ("completed", False, "?"), ("failed", False, "✗")])
def test_simulator_mark_follows_the_measured_probe(tmp_path, probe_status, workload, expected):
    site(Path(os.environ["RAT_DATA_DIR"]), probe_status, workload)
    project = tmp_path / "project"
    project.mkdir()
    code, rows = doctor(project)
    assert rows[("plugin", "default site")]["status"] == "✓"
    assert rows[("project", "initialized")]["status"] == "–"
    assert rows[("project", "execution")]["status"] == "✓"
    assert rows[("project", "simulator")]["status"] == expected
    assert rows[("project", "technology.db")]["status"] == "?"  # remote path is checked only with --live
    assert code == (1 if expected == "✗" else 0)
    assert not any(project.iterdir())  # diagnosis writes nothing into the project


def test_unreadable_project_config_is_reported(tmp_path):
    (tmp_path / "rat_config.json").write_text("{broken")
    code, rows = doctor(tmp_path)
    assert code == 1 and rows[("project", "rat_config.json")]["status"] == "✗"


def test_live_checks_never_pass_injected_host_or_paths_to_a_shell(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "ssh-calls"
    (bin_dir / "ssh").write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" >> "{calls}"\nexit 1\n')
    (bin_dir / "ssh").chmod(0o755)
    project = tmp_path / "project"
    project.mkdir()
    (project / "rat_config.json").write_text(json.dumps({
        "execution": {"backend": "ssh", "host": "-oProxyCommand=touch PWNED", "workspace": "/remote/ws",
                      "ssh_options": ["-oProxyCommand=touch PWNED"]},
        "technology": {"db": "/lib/$(touch PWNED).db"}}))
    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    result = subprocess.run([sys.executable, str(DOCTOR), "--root", str(project), "--json", "--live"],
                            env={**os.environ, **env}, capture_output=True, text=True, timeout=60, cwd=tmp_path)
    rows = {(row["level"], row["item"]): row for row in json.loads(result.stdout)}
    assert rows[("project", "technology.db")]["status"] == "✗"
    assert "plain SSH alias" in rows[("project", "technology.db")]["detail"]
    assert not calls.exists() and not list(tmp_path.rglob("PWNED"))


def test_live_library_check_quotes_the_path_for_the_remote_shell(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "ssh-calls"
    (bin_dir / "ssh").write_text(f'#!/bin/sh\nprintf "%s\\n" "$@" >> "{calls}"\nexit 1\n')
    (bin_dir / "ssh").chmod(0o755)
    project = tmp_path / "project"
    project.mkdir()
    (project / "rat_config.json").write_text(json.dumps({
        "execution": {"backend": "ssh", "host": "eda.example.invalid", "workspace": "/remote/ws"},
        "technology": {"db": "/lib/$(touch PWNED).db"}}))
    env = {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}
    subprocess.run([sys.executable, str(DOCTOR), "--root", str(project), "--json", "--live"],
                   env={**os.environ, **env}, capture_output=True, text=True, timeout=60)
    argv = calls.read_text().splitlines()
    assert argv[argv.index("--") + 1] == "eda.example.invalid"
    script = argv[-1]
    assert script.startswith("sh -c ") and "touch PWNED" not in script  # base64-encoded, run by sh, not the login shell


@pytest.mark.parametrize("mode,expected", [("experiment", "✓"), ("merge", "✗"), ("bogus", "✗")])
def test_remote_result_mode_is_checked(tmp_path, mode, expected):
    # tmp_path is not a Git work tree, so merge cannot protect sources.
    (tmp_path / "rat_config.json").write_text(json.dumps({"execution": {
        "backend": "ssh", "host": "eda.example.invalid", "workspace": "/remote/ws", "results": mode}}))
    _, rows = doctor(tmp_path)
    assert rows[("project", "remote results")]["status"] == expected
