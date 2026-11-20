"""Exercise template lifecycle without overwriting user edits or dry-run targets."""

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT


@pytest.fixture
def installation(tmp_path):
    plugin = tmp_path / "plugin"
    shutil.copytree(REPO_ROOT / "skills/rat-init-project", plugin / "skills/rat-init-project")
    for relative in ["scripts/run_sim.sh", "scripts/verify_evidence.py", "scripts/eda_runner.py", "scripts/eda_setup.py", "scripts/regression_evidence.py", "scripts/merge_coverpoint_logs.py", "hooks/lib/python-util.sh", "skills/rtl-p5s-uvm-verify/scripts/run_regression_uvm.sh"]:
        target = plugin / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / relative, target)
    workspace = tmp_path / "project with spaces"
    workspace.mkdir()
    installer = plugin / "skills/rat-init-project/scripts/install_project_templates.sh"
    env = {**os.environ, "HOME": str(tmp_path / "home")}

    def install(*flags):
        return subprocess.run(["bash", str(installer), *flags, str(workspace)],
                              capture_output=True, text=True, env=env, check=True)

    return plugin, workspace, install


def snapshot(root):
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in root.rglob("*") if p.is_file()}


def test_dry_run_leaves_empty_workspace_untouched(installation):
    _, workspace, install = installation
    result = install("--dry-run")
    assert "CREATE scripts/run_sim.sh" in result.stdout
    assert list(workspace.iterdir()) == []


def test_managed_script_and_guide_update_together(installation):
    plugin, workspace, install = installation
    install()
    for relative in ["run_syn.sh", "guides/docs-guide.md"]:
        source = plugin / "skills/rat-init-project/templates" / relative
        source.write_text(re.sub(r"rat-version: (\d+)\.(\d+)\.(\d+)", lambda m: "rat-version: "+m[1]+"."+m[2]+"."+str(int(m[3])+1), source.read_text()) + "\nupdated template\n")
    before = snapshot(workspace)
    install("--update", "--dry-run")
    assert snapshot(workspace) == before
    install("--update")
    assert "updated template" in (workspace / "syn/scripts/run_syn.sh").read_text()
    assert "updated template" in (workspace / "docs/CLAUDE.md").read_text()


def test_user_edit_survives_repeated_updates(installation):
    plugin, workspace, install = installation
    install()
    target = workspace / ".claude/rules/rtl-verification-gate.md"
    target.write_text(target.read_text() + "\nproject-specific verification\n")
    source = plugin / "skills/rat-init-project/templates/rules/rtl-verification-gate.md"
    source.write_text(re.sub(r"rat-version: (\d+)\.(\d+)\.(\d+)", lambda m: "rat-version: "+m[1]+"."+m[2]+"."+str(int(m[3])+1), source.read_text()))
    original = target.read_bytes()
    for _ in range(2):
        result = install("--update")
        assert "REVIEW .claude/rules/rtl-verification-gate.md" in result.stdout
        assert target.read_bytes() == original
    candidate = workspace / ".rat/template-updates/.claude/rules/rtl-verification-gate.md"
    assert candidate.read_bytes() == source.read_bytes()


def test_unrecognized_legacy_copy_is_preserved(installation):
    _, workspace, install = installation
    target = workspace / "scripts/run_sim.sh"
    target.parent.mkdir()
    target.write_text("#!/bin/bash\n# rat-version: 0.1.0\necho user script\n")
    original = target.read_bytes()
    install("--update")
    assert target.read_bytes() == original
    assert (workspace / ".rat/template-updates/scripts/run_sim.sh").exists()


def test_installer_does_not_follow_workspace_escape(installation, tmp_path):
    _, workspace, install = installation
    outside = tmp_path / "outside"
    outside.mkdir()
    (workspace / "scripts").symlink_to(outside, target_is_directory=True)
    with pytest.raises(subprocess.CalledProcessError):
        install()
    assert list(outside.iterdir()) == []
