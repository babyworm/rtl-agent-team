"""Structural invariants for the asset-bundle migration of 10 candidate skills.

This test locks in the v0.11.0 reference pattern (established by `rtl-document`)
across the 10 utility skills migrated in the asset-bundle-clone-pack PR. Each
migrated skill must:

  1. Have all four canonical asset directories: templates, scripts, references,
     examples.
  2. Have at least one `references/*-conventions.md` file under 150 lines.

A subset of skills (currently 4: ref-model, bfm-develop, rtl-ip-instantiate, and
rtl-document itself) carries the full lean SKILL.md form (`<Assets>` +
`<Responsibility_Boundary>` sections). The remaining 6 skills inherit the
*structural* migration (4 directories + references doc) in this PR; their lean
SKILL.md rewrite is tracked as a follow-up.

Deep script/example fills are explicitly NOT validated here — those are deferred
to per-skill follow-up PRs. This test verifies *structural uniformity* so the
follow-ups can proceed independently without coupling.
"""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / "skills"

# The 10 skills migrated in the asset-bundle-clone-pack PR (Task list in
# plugin_docs/plans/2026-05-13-asset-bundle-clone-pack-plan.md).
MIGRATED_SKILLS = [
    "rtl-bug-repro",
    "rtl-ipxact-gen",
    "rtl-p5s-perf-verify",
    "rtl-p5s-coverage-analyze",
    "rtl-p5s-integration-test",
    "ref-model",
    "bfm-develop",
    "rtl-ip-instantiate",
    "rtl-model-consistency",
    "rtl-conformance-test",
]

REQUIRED_DIRS = ("templates", "scripts", "references", "examples")

# Skills that have completed the FULL lean SKILL.md rewrite (`<Assets>` +
# `<Responsibility_Boundary>` sections present). The remaining MIGRATED_SKILLS
# entries that are NOT in this tuple have only the structural migration
# (4 directories + references/*-conventions.md); their lean SKILL.md rewrite
# is tracked as a follow-up.
FULL_LEAN_SKILLS = (
    "rtl-bug-repro",
    "rtl-ipxact-gen",
    "rtl-p5s-perf-verify",
    "rtl-p5s-coverage-analyze",
    "rtl-p5s-integration-test",
    "ref-model",
    "bfm-develop",
    "rtl-ip-instantiate",
    "rtl-model-consistency",
)

# XML sections required for the FULL lean SKILL.md form.
ASSET_BUNDLE_SECTIONS = (
    "<Assets>",
    "<Responsibility_Boundary>",
)


@pytest.mark.parametrize("skill_name", MIGRATED_SKILLS)
def test_skill_has_four_asset_dirs(skill_name):
    """Every migrated skill must have all four asset directories."""
    skill_root = SKILLS_DIR / skill_name
    assert skill_root.is_dir(), f"skill directory missing: {skill_root}"
    for d in REQUIRED_DIRS:
        sub = skill_root / d
        assert sub.is_dir(), f"{skill_name} missing required dir: {d}/"


@pytest.mark.parametrize("skill_name", MIGRATED_SKILLS)
def test_skill_has_references_conventions_doc(skill_name):
    """Every migrated skill must have a references/*-conventions.md (<=150 lines)."""
    refs_dir = SKILLS_DIR / skill_name / "references"
    convention_files = list(refs_dir.glob("*-conventions.md"))
    assert convention_files, (
        f"{skill_name} has no references/*-conventions.md "
        f"(checked {refs_dir})"
    )
    for conv in convention_files:
        line_count = sum(1 for _ in conv.read_text().splitlines())
        assert line_count <= 150, (
            f"{skill_name}/{conv.name} is {line_count} lines "
            f"(max 150 — keep references lean per the v0.11.0 pattern)"
        )


@pytest.mark.parametrize("skill_name", FULL_LEAN_SKILLS)
def test_full_lean_skill_has_asset_bundle_sections(skill_name):
    """Skills marked FULL_LEAN must contain the full asset-bundle XML sections."""
    skill_md = SKILLS_DIR / skill_name / "SKILL.md"
    assert skill_md.is_file(), f"{skill_name}/SKILL.md missing"
    body = skill_md.read_text()
    for section in ASSET_BUNDLE_SECTIONS:
        assert section in body, (
            f"{skill_name}/SKILL.md missing canonical section: {section}"
        )


def test_all_ten_skills_present():
    """Sanity guard: every name in MIGRATED_SKILLS resolves to a real directory.

    Prevents a typo in MIGRATED_SKILLS from silently passing the per-skill
    parameterized tests on the wrong target.
    """
    missing = [s for s in MIGRATED_SKILLS if not (SKILLS_DIR / s).is_dir()]
    assert not missing, f"MIGRATED_SKILLS references unknown skills: {missing}"


def test_full_lean_skills_are_subset_of_migrated():
    """FULL_LEAN_SKILLS must be a subset of MIGRATED_SKILLS."""
    extras = set(FULL_LEAN_SKILLS) - set(MIGRATED_SKILLS)
    assert not extras, f"FULL_LEAN_SKILLS references non-migrated skills: {extras}"
