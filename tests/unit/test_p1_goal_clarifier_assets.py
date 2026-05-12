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
    # Already-rich seed (≥ 500 chars AND mentions PPA or coverage signals) → skip.
    signals = ["mhz", "ghz", "ns ", "coverage", "bitexact", "um^2", "mm^2", "gates"]
    if len(a) >= 500 and any(s in a.lower() for s in signals):
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
