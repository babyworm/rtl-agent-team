import re
from pathlib import Path

from tests.conftest import REPO_ROOT


ACTIVE_SUFFIXES = {".json", ".md", ".py", ".sdc", ".sh"}
CANONICAL_IRON = "docs/phase-1-research/iron-requirements.json"
CANONICAL_OPEN = "docs/phase-1-research/open-requirements.json"
LEGACY_REQUIREMENTS = re.compile(r"(?<!iron-)(?<!open-)requirements\.json")
EXCLUDED_PATHS = {
    "agents/dc-report-parser.md",
    "agents/ppa-optimizer-dc-orchestrator.md",
    "agents/ppa-optimizer-dc.md",
}
MIGRATION_EXPLANATION_PATHS = {
    "agents/spec-analyst.md",
    "skills/p1-spec-research-policy/SKILL.md",
}
EXCLUDED_PREFIXES = (
    "skills/ppa-optimizer-dc-policy/",
    "skills/rat-ultraloop-ppa/",
    "skills/rtl-ppa-optimize-dc/",
)


def test_active_non_ppa_consumers_use_phase_one_requirement_artifacts() -> None:
    # Given: active agent and skill artifacts outside the separate PPA contract.
    candidates = (
        path
        for root in (REPO_ROOT / "agents", REPO_ROOT / "skills")
        for path in root.rglob("*")
        if path.is_file() and path.suffix in ACTIVE_SUFFIXES
    )

    # When: bare references to the retired flat requirement artifact are collected.
    violations: list[str] = []
    for path in candidates:
        relative_path = path.relative_to(REPO_ROOT).as_posix()
        if (
            relative_path in EXCLUDED_PATHS
            or relative_path.startswith(EXCLUDED_PREFIXES)
        ):
            continue

        lines = path.read_text().splitlines()
        for line_number, line in enumerate(lines, start=1):
            for match in LEGACY_REQUIREMENTS.finditer(line):
                canonical_fallback = (
                    CANONICAL_IRON in line[: match.start()]
                    and "legacy" in line.lower()
                    and "fallback" in line.lower()
                )
                migration_context = "\n".join(
                    lines[max(0, line_number - 2) : line_number + 3]
                )
                migration_explanation = (
                    relative_path in MIGRATION_EXPLANATION_PATHS
                    and CANONICAL_IRON in migration_context
                    and CANONICAL_OPEN in migration_context
                )
                if not canonical_fallback and not migration_explanation:
                    violations.append(f"{relative_path}:{line_number}")

    # Then: every remaining legacy path is either qualified fallback or migration prose.
    assert violations == []
