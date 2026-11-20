from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from tests.conftest import REPO_ROOT


def test_review_followup_contract(tmp_path: Path) -> None:
    sync_script = REPO_ROOT / "scripts" / "sync_step0.sh"
    clean = subprocess.run(
        ["bash", str(sync_script), "--dry-run"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert clean.returncode == 0, clean.stdout + clean.stderr
    consumers = sum(
        bool(re.search(r"^#{2,3} Step 0: Context Bootstrap", p.read_text(), re.MULTILINE))
        for p in (REPO_ROOT / "agents").glob("*.md")
    )
    assert consumers > 0
    assert (
        f"consumer files scanned: {consumers}, changed: 0, "
        f"unchanged: {consumers}, skipped: 0."
    ) in clean.stdout

    fixture_root = tmp_path / "sync-fixture"
    (fixture_root / "scripts").mkdir(parents=True)
    (fixture_root / "agents").mkdir(parents=True)
    (fixture_root / "plugin_docs" / "agent-lib").mkdir(parents=True)
    shutil.copy2(sync_script, fixture_root / "scripts" / "sync_step0.sh")
    shutil.copy2(
        REPO_ROOT / "plugin_docs" / "agent-lib" / "step0-template.md",
        fixture_root / "plugin_docs" / "agent-lib" / "step0-template.md",
    )
    (fixture_root / "agents" / "broken.md").write_text(
        "## Step 0: Context Bootstrap\n\nmissing canonical sentinel\n"
    )
    skipped = subprocess.run(
        ["bash", str(fixture_root / "scripts" / "sync_step0.sh"), "--dry-run"],
        cwd=fixture_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert skipped.returncode != 0
    assert (
        "consumer files scanned: 1, changed: 0, unchanged: 0, skipped: 1"
        in skipped.stdout
    )

    readme = (REPO_ROOT / "README.md").read_text()
    readme_kr = (REPO_ROOT / "README_kr.md").read_text()
    init_skill = (REPO_ROOT / "skills" / "rat-init-project" / "SKILL.md").read_text()
    eda_guide = (REPO_ROOT / "plugin_docs" / "eda-setup-guide.md").read_text()
    sva_agent = (REPO_ROOT / "agents" / "p5s-sva-orchestrator.md").read_text()
    sva_policy = (
        REPO_ROOT / "skills" / "rtl-p5s-sva-policy" / "SKILL.md"
    )
    sva_policy = (REPO_ROOT / "plugin_docs/agent-lib/policies/rtl-p5s-sva-policy.md").read_text()
    workflow = (
        REPO_ROOT / "plugin_docs" / "specs" / "workflow-ultracode-compat.md"
    ).read_text()
    block_spec = (
        REPO_ROOT
        / "plugin_docs"
        / "specs"
        / "2026-03-15-block-parallel-domain-expert-design.md"
    ).read_text()
    block_plan = (
        REPO_ROOT
        / "plugin_docs"
        / "plans"
        / "2026-03-15-block-parallel-domain-expert-plan.md"
    ).read_text()
    cascading_spec = (
        REPO_ROOT
        / "plugin_docs"
        / "specs"
        / "2026-03-14-cascading-requirements-design.md"
    ).read_text()
    cascading_plan = (
        REPO_ROOT
        / "plugin_docs"
        / "plans"
        / "2026-03-14-cascading-requirements-plan.md"
    ).read_text()
    lifecycle = (REPO_ROOT / "plugin_docs" / "README.md").read_text()
    test_readme = (REPO_ROOT / "tests" / "README.md").read_text()
    memory_spec = (
        REPO_ROOT
        / "plugin_docs"
        / "specs"
        / "2026-05-26-synth-memory-blackbox-design.md"
    ).read_text()
    hook_output_plan = (
        REPO_ROOT / "plugin_docs" / "plans" / "p3-11-hook-output-standardization.md"
    ).read_text()

    dockerfile = (REPO_ROOT / "docker" / "Dockerfile").read_text()
    for tool in ("SLANG", "SVLENS"):
        version_arg = next(line.split(" ", 1)[1] for line in dockerfile.splitlines()
                           if line.startswith(f"ARG {tool}_VERSION="))
        assert f"--build-arg {version_arg}" in eda_guide
    for overview in (readme, readme_kr):
        assert "plugin_docs/eda-setup-guide.md" in overview
        assert "genus, vivado" not in overview.lower()
    assert "config.mk" in eda_guide
    assert "{syn_root}/scr/replay/" in eda_guide
    assert "Regression helpers generate per-seed and aggregate" in eda_guide
    assert "trusted project input" in init_skill
    assert "stale or unusable" in init_skill
    assert "trusted project input" in eda_guide
    assert "stale or unusable" in eda_guide
    assert "pip install sbyosys" not in sva_agent
    assert "pip install sbyosys" not in sva_policy
    assert "**Status**: Implemented" in block_spec
    assert "archival shipped record" in block_spec
    assert "archival shipped record" in block_plan
    assert "**Status**: Implemented" in cascading_spec
    assert "Historical boundary" in cascading_spec
    assert "archival shipped record" in cascading_plan
    for status in ("Draft", "Approved", "Implemented", "Historical", "Superseded"):
        assert f"`{status}`" in lifecycle
    assert "retained `make -C sim/{module}`" in workflow
    assert "explicit `sim` target" in workflow
    assert "10-30" in test_readme
    assert "- Status: Implemented" in memory_spec
    assert "Historical boundary" in memory_spec
    assert "- Status: Historical" in hook_output_plan
    assert "Historical boundary" in hook_output_plan
