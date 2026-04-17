"""Unit tests for validate_patch_scope.py — ensure patch stays within allowed scope."""
import pathlib
import sys

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "skills" / "rtl-ppa-optimize-dc" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import validate_patch_scope as vps  # noqa: E402


def _diff(paths):
    """Build a synthetic unified diff touching each path."""
    hunks = []
    for p in paths:
        hunks.append(
            f"diff --git a/{p} b/{p}\n"
            f"--- a/{p}\n"
            f"+++ b/{p}\n"
            f"@@ -1,2 +1,2 @@\n"
            f"-old line\n"
            f"+new line\n"
        )
    return "".join(hunks)


class TestExtractChangedFiles:
    def test_single_file(self):
        diff = _diff(["rtl/core/datapath.sv"])
        files = vps.extract_changed_files(diff)
        assert files == ["rtl/core/datapath.sv"]

    def test_multiple_files(self):
        diff = _diff(["rtl/core/a.sv", "rtl/core/b.sv"])
        files = vps.extract_changed_files(diff)
        assert set(files) == {"rtl/core/a.sv", "rtl/core/b.sv"}

    def test_empty_diff(self):
        assert vps.extract_changed_files("") == []


class TestCheckScope:
    def test_allowed_file_passes(self):
        allowed = ["rtl/core/**/*.sv"]
        frozen = ["rtl/common/**", "rtl/pkg/**"]
        ok, violations = vps.check_scope(["rtl/core/datapath.sv"], allowed, frozen)
        assert ok
        assert violations == []

    def test_frozen_violation(self):
        allowed = ["rtl/core/**/*.sv"]
        frozen = ["rtl/common/**", "rtl/pkg/**"]
        ok, violations = vps.check_scope(
            ["rtl/common/sram_sp.sv", "rtl/core/datapath.sv"], allowed, frozen
        )
        assert not ok
        assert "rtl/common/sram_sp.sv" in violations

    def test_outside_allowed(self):
        allowed = ["rtl/core/**/*.sv"]
        frozen = ["rtl/common/**"]
        ok, violations = vps.check_scope(
            ["rtl/unrelated/foo.sv"], allowed, frozen
        )
        assert not ok
        assert "rtl/unrelated/foo.sv" in violations

    def test_non_sv_file_outside_allowed(self):
        allowed = ["rtl/core/**/*.sv"]
        frozen = ["rtl/common/**"]
        ok, violations = vps.check_scope(
            ["docs/notes.md"], allowed, frozen
        )
        assert not ok
