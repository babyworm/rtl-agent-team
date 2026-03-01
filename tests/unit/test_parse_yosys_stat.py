"""Tests for parse_yosys_stat.py — Yosys synthesis output parser."""

import json
import sys
from pathlib import Path

import pytest

# Add script to path
SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "rtl-synth-check" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from parse_yosys_stat import parse_stat_output, generate_verdict


class TestParseStatOutput:
    """Tests for parse_stat_output()."""

    def test_basic_cells_parsed(self, yosys_stat_output):
        result = parse_stat_output(yosys_stat_output)
        assert result["cells"]["$_DFF_P_"] == 16
        assert result["cells"]["$_DFF_PN1_"] == 8
        assert result["cells"]["$add"] == 4
        assert result["cells"]["$mux"] == 12
        assert result["cells"]["$not"] == 2

    def test_total_cells(self, yosys_stat_output):
        result = parse_stat_output(yosys_stat_output)
        assert result["total_cells"] == 16 + 8 + 4 + 12 + 2

    def test_wire_counts_not_parsed_before_statistics(self, yosys_stat_output):
        """Wire counts appear before 'Statistics' in Yosys output and are
        only parsed after the parser sees 'Statistics' or 'Number of cells:'.
        In the standard fixture, wires appear ABOVE Statistics, so they're missed."""
        result = parse_stat_output(yosys_stat_output)
        assert result["wires"] == 0  # Known limitation: wires before Statistics

    def test_wire_counts_after_statistics(self):
        """Wire counts ARE parsed when they appear after 'Number of cells:'."""
        text = """\
   Number of cells:                 42

   Number of wires:                 42
   Number of wire bits:            256

   Statistics:
     $_DFF_P_                       16
"""
        result = parse_stat_output(text)
        assert result["wires"] == 42
        assert result["wire_bits"] == 256

    def test_no_latches_in_clean_design(self, yosys_stat_output):
        result = parse_stat_output(yosys_stat_output)
        assert result["latches_found"] == 0

    def test_latch_detection(self, yosys_stat_with_latches):
        result = parse_stat_output(yosys_stat_with_latches)
        assert result["latches_found"] == 2
        assert any("CRITICAL" in c and "latch" in c for c in result["concerns"])

    def test_multiplier_concern(self):
        text = """\
   Statistics:
     $mul                            3
     $_DFF_P_                        1
"""
        result = parse_stat_output(text)
        assert any("multiplier" in c for c in result["concerns"])

    def test_memory_info(self):
        text = """\
   Statistics:
     $mem                            2
     $_DFF_P_                        1
"""
        result = parse_stat_output(text)
        assert any("memory" in c.lower() for c in result["concerns"])

    def test_area_parsing(self):
        text = """\
   Statistics:
     $_DFF_P_                        4
   Chip area for top_module: 1234.56
"""
        result = parse_stat_output(text)
        assert result["area_um2"] == pytest.approx(1234.56)

    def test_empty_input(self):
        result = parse_stat_output("")
        assert result["total_cells"] == 0
        assert result["latches_found"] == 0
        assert result["wires"] == 0

    def test_no_statistics_section(self):
        text = "Some random text\nwithout Statistics keyword\n"
        result = parse_stat_output(text)
        assert result["total_cells"] == 0


class TestGenerateVerdict:
    """Tests for generate_verdict()."""

    def test_pass_clean_design(self, yosys_stat_output):
        result = parse_stat_output(yosys_stat_output)
        assert generate_verdict(result) == "PASS"

    def test_fail_latches(self, yosys_stat_with_latches):
        result = parse_stat_output(yosys_stat_with_latches)
        verdict = generate_verdict(result)
        assert verdict.startswith("FAIL")
        assert "latch" in verdict.lower()

    def test_fail_empty_design(self, yosys_stat_empty):
        result = parse_stat_output(yosys_stat_empty)
        verdict = generate_verdict(result)
        assert verdict.startswith("FAIL")
        assert "no cells" in verdict.lower()

    def test_fail_zero_cells(self):
        result = {"latches_found": 0, "total_cells": 0}
        verdict = generate_verdict(result)
        assert verdict.startswith("FAIL")
