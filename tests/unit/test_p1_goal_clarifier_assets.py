"""Unit tests for the P1 goal-clarifier integration assets."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]

# ------------------------------------------------------------------
# Trigger heuristic — Python reference implementation.
# This MUST stay in sync with the prose in agents/p1-research-orchestrator.md.
# ------------------------------------------------------------------

def needs_clarifier(arguments: str, cwd: Path) -> bool:
    """Return True iff goal-clarifier should run before spec-analyst.

    Mirrors the heuristic documented in p1-research-orchestrator Step 0a.
    """
    a = arguments.strip()
    if not a:
        return True
    # If arguments is a path to an existing readable text spec file → skip.
    # Guard: real filenames are always short; skip the stat() call for long strings
    # to avoid OSError ENAMETOOLONG on Linux (255-byte filename limit).
    candidate = cwd / a
    if len(a) < 256 and candidate.is_file() and candidate.suffix in {".md", ".txt", ".rst"}:
        return False
    # Already-rich seed: require BOTH a clock signal AND a PPA/coverage signal.
    # Either one alone is insufficient — a 500-char paragraph mentioning only
    # "coverage" (no clock target) or only "200 MHz" (no PPA detail) is still
    # under-specified and should still trigger the goal-clarifier interview.
    text = a.lower()
    clock_signals = ["mhz", "ghz"]
    ppa_signals = ["coverage", "bitexact", "um^2", "mm^2", "gates", " mw", " ns "]
    has_clock = any(s in text for s in clock_signals)
    has_ppa = any(s in text for s in ppa_signals)
    if len(a) >= 500 and has_clock and has_ppa:
        return False
    return True


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_empty_seed_triggers_clarifier(tmp_path):
    assert needs_clarifier("", tmp_path) is True


def test_short_natural_idea_triggers_clarifier(tmp_path):
    assert needs_clarifier("Build an AXI bridge", tmp_path) is True


def test_path_to_markdown_skips_clarifier(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# spec\n")
    assert needs_clarifier("spec.md", tmp_path) is False


def test_path_to_txt_skips_clarifier(tmp_path):
    spec = tmp_path / "design.txt"
    spec.write_text("design notes\n")
    assert needs_clarifier("design.txt", tmp_path) is False


def test_path_to_nonexistent_file_treated_as_idea(tmp_path):
    # Non-existent paths fall through to the natural-language case.
    assert needs_clarifier("does-not-exist.md", tmp_path) is True


def test_long_rich_seed_skips_clarifier(tmp_path):
    rich = (
        "Build an AES-128-GCM core targeting 200 MHz on TSMC N28HPC. "
        "Area budget 50000 gates. Coverage target 95% line + functional. "
        "Bitexact match against OpenSSL reference required. "
        "AXI4-Stream IO, 64-bit data path. "
    ) * 3
    assert len(rich) >= 500
    assert needs_clarifier(rich, tmp_path) is False


def test_long_but_vague_seed_triggers_clarifier(tmp_path):
    vague = "Build some hardware that does encryption stuff. " * 20
    assert len(vague) >= 500
    assert needs_clarifier(vague, tmp_path) is True


def test_long_seed_with_only_coverage_triggers_clarifier(tmp_path):
    """Tightened heuristic: PPA-only signal (no clock target) → still vague."""
    seed = ("This IP must hit 95% line coverage with bitexact match against the "
            "vendor reference and exhaustive directed tests across all modes. ") * 10
    assert len(seed) >= 500
    assert needs_clarifier(seed, tmp_path) is True


def test_long_seed_with_only_clock_triggers_clarifier(tmp_path):
    """Tightened heuristic: clock-only signal (no PPA/coverage detail) → still vague."""
    seed = ("This block runs at 200 MHz on a modern process node and processes "
            "incoming data packets through a configurable pipeline. ") * 10
    assert len(seed) >= 500
    assert needs_clarifier(seed, tmp_path) is True


# ------------------------------------------------------------------
# Asset structural tests
# ------------------------------------------------------------------

TEMPLATE = ROOT / "skills" / "p1-spec-research" / "templates" / "goal.md"
REFERENCE = ROOT / "skills" / "p1-spec-research" / "references" / "goal-dimensions.md"


def test_template_has_all_four_dimensions():
    body = TEMPLATE.read_text()
    for section in ["## Functionality", "## PPA Target", "## Scope", "## Verification"]:
        assert section in body, f"template missing {section}"


def test_template_has_status_footer():
    body = TEMPLATE.read_text()
    assert "STATUS: ambiguity={{AMBIGUITY_PCT}}%" in body
    assert "ROUNDS: {{ROUNDS_COUNT}}" in body


def test_template_placeholders_renderable():
    """Every {{PLACEHOLDER}} must use UPPER_SNAKE_CASE."""
    import re
    body = TEMPLATE.read_text()
    placeholders = set(re.findall(r"\{\{([A-Z_]+)\}\}", body))
    assert placeholders, "template has no placeholders"
    for ph in placeholders:
        assert ph.isupper(), f"bad placeholder: {ph}"


def test_reference_doc_length_under_200_lines():
    n = sum(1 for _ in REFERENCE.read_text().splitlines())
    assert n <= 200, f"reference doc is {n} lines (must be ≤ 200)"


def test_reference_doc_covers_all_four_dimensions():
    body = REFERENCE.read_text().lower()
    for dim in ["functionality", "ppa", "scope", "verification"]:
        assert dim in body, f"reference doc missing {dim}"


def test_reference_doc_has_anti_patterns_section():
    body = REFERENCE.read_text()
    assert "Anti-patterns" in body or "anti-patterns" in body.lower()
