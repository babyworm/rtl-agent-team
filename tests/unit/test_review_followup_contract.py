from __future__ import annotations

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
    assert (
        "Step 0 sync complete: consumer files scanned: 33, changed: 0, "
        "unchanged: 33, skipped: 0."
    ) in clean.stdout

    fixture_root = tmp_path / "sync-fixture"
    (fixture_root / "scripts").mkdir(parents=True)
    (fixture_root / "agents" / "lib").mkdir(parents=True)
    shutil.copy2(sync_script, fixture_root / "scripts" / "sync_step0.sh")
    shutil.copy2(
        REPO_ROOT / "agents" / "lib" / "step0-template.md",
        fixture_root / "agents" / "lib" / "step0-template.md",
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
    ).read_text()
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

    assert "SLANG_VERSION=v11.0" in readme and "SVLENS_VERSION=v0.3.6" in readme
    assert "SLANG_VERSION=v11.0" in readme_kr and "SVLENS_VERSION=v0.3.6" in readme_kr
    assert "genus, vivado" not in readme.lower()
    assert "genus, vivado" not in readme_kr.lower()
    assert "managed exceptions" in readme and "config.mk" in readme
    assert "관리 대상 예외" in readme_kr and "config.mk" in readme_kr
    assert "{syn_root}/scr/replay/" in readme
    assert "{syn_root}/scr/replay/" in readme_kr
    assert "Regression helpers generate reports rather than replay scripts" in readme
    assert "회귀 테스트 helper는 replay 대신 보고서를 생성" in readme_kr
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
