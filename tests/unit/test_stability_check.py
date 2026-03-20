"""Unit tests for stability_check.py — content-based requirement alignment."""
import json
import pytest
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from stability_check import tokenize, jaccard, align_requirements, compute_pair_similarity, compute_gate, generate_report


class TestTokenize:
    def test_basic(self):
        assert tokenize("FIFO output latency") == {"fifo", "output", "latency"}

    def test_removes_stopwords(self):
        result = tokenize("the data is valid and ready")
        assert "the" not in result
        assert "data" in result
        assert "valid" in result

    def test_empty(self):
        assert tokenize("") == set()

    def test_short_tokens_removed(self):
        assert tokenize("a b cd") == {"cd"}

    def test_underscore_preserved(self):
        result = tokenize("i_data o_valid sys_clk")
        assert "i_data" in result
        assert "o_valid" in result


class TestJaccard:
    def test_identical(self):
        assert jaccard({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint(self):
        assert jaccard({"a"}, {"b"}) == 0.0

    def test_partial(self):
        assert jaccard({"a", "b", "c"}, {"b", "c", "d"}) == pytest.approx(0.5)

    def test_both_empty(self):
        assert jaccard(set(), set()) == 1.0

    def test_one_empty(self):
        assert jaccard({"a"}, set()) == 0.0


class TestComputePairSimilarity:
    def test_identical_reqs(self):
        r = {"source": {"section": "3.2", "line": 10}, "type": "functional",
             "priority": "must", "complexity": "medium",
             "description": "FIFO output latency 4 cycles",
             "acceptance_criteria": ["latency <= 4 cycles"]}
        assert compute_pair_similarity(r, r) > 0.9

    def test_different_section(self):
        r1 = {"source": {"section": "3.2", "line": 10}, "description": "data width 8 bit",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": ["width == 8"]}
        r2 = {"source": {"section": "5.1", "line": 50}, "description": "data width 8 bit",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": ["width == 8"]}
        sim = compute_pair_similarity(r1, r2)
        assert sim < 0.9  # section mismatch reduces score

    def test_line_proximity(self):
        r1 = {"source": {"section": "3.2", "line": 10}, "description": "test",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": []}
        r2 = {"source": {"section": "3.2", "line": 12}, "description": "test",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": []}
        r3 = {"source": {"section": "3.2", "line": 100}, "description": "test",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": []}
        sim_close = compute_pair_similarity(r1, r2)
        sim_far = compute_pair_similarity(r1, r3)
        assert sim_close > sim_far  # closer lines = higher similarity

    def test_empty_fields(self):
        r1 = {"description": "test", "source": {}}
        r2 = {"description": "test", "source": {}}
        sim = compute_pair_similarity(r1, r2)
        assert 0.0 <= sim <= 1.0


class TestAlignRequirements:
    def _make_req(self, id, section, line, desc, **kwargs):
        r = {"id": id, "source": {"section": section, "line": line},
             "description": desc, "type": "functional", "priority": "must",
             "complexity": "low", "acceptance_criteria": [f"test {id}"]}
        r.update(kwargs)
        return r

    def test_identical_lists(self):
        reqs = [self._make_req("R1", "3.1", 5, "FIFO depth 16"),
                self._make_req("R2", "3.2", 20, "Output latency 4 cycles")]
        aligned, v1_only, v2_only, *_ = align_requirements(reqs, reqs)
        assert len(aligned) == 2
        assert len(v1_only) == 0
        assert len(v2_only) == 0

    def test_empty_v1(self):
        aligned, v1_only, v2_only, *_ = align_requirements(
            [], [self._make_req("R1", "1", 1, "x")])
        assert len(aligned) == 0
        assert len(v2_only) == 1

    def test_empty_both(self):
        aligned, v1_only, v2_only, *_ = align_requirements([], [])
        assert len(aligned) == 0

    def test_no_section_falls_to_pass2(self):
        v1 = [{"id": "R1", "source": {}, "description": "FIFO depth 16 entries",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": ["depth == 16"]}]
        v2 = [{"id": "R2", "source": {}, "description": "FIFO depth sixteen entries",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": ["depth == 16"]}]
        aligned, v1_only, v2_only, *_ = align_requirements(v1, v2)
        assert len(aligned) == 1

    def test_v2_expansion(self):
        v1 = [self._make_req(f"R{i}", f"{i}.0", i*10, f"feature {i}") for i in range(3)]
        v2 = list(v1) + [
            self._make_req("R3", "3.1", 30, "new feature A"),
            self._make_req("R4", "3.2", 40, "new feature B"),
        ]
        aligned, v1_only, v2_only, *_ = align_requirements(v1, v2)
        assert len(aligned) == 3
        assert len(v1_only) == 0
        assert len(v2_only) == 2

    def test_pass2_no_stale_v1_unmatched(self):
        v1 = [{"id": "R1", "source": {}, "description": "alpha beta gamma",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": []}]
        v2 = [{"id": "R2", "source": {}, "description": "alpha beta gamma delta",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": []}]
        aligned, v1_only, v2_only, *_ = align_requirements(v1, v2)
        assert len(aligned) == 1
        assert len(v1_only) == 0

    def test_best_match_within_section(self):
        """Two reqs in same section: should match by best similarity, not first."""
        v1 = [self._make_req("R1", "3.1", 5, "signed 8-bit data input"),
              self._make_req("R2", "3.1", 10, "unsigned 8-bit data output")]
        v2 = [self._make_req("R3", "3.1", 6, "unsigned 8-bit data output"),
              self._make_req("R4", "3.1", 11, "signed 8-bit data input")]
        aligned, v1_only, v2_only, *_ = align_requirements(v1, v2)
        assert len(aligned) == 2
        assert len(v1_only) == 0
        assert len(v2_only) == 0


class TestComputeGate:
    def test_all_resolved(self):
        challenges = [
            {"severity": "HIGH", "resolution": "RESOLVED"},
            {"severity": "MEDIUM", "resolution": "DOCUMENTED"},
            {"severity": "LOW", "resolution": None},
        ]
        result = compute_gate(challenges)
        assert result["gate_pass"] is True
        assert result["resolution_ratio"] == 1.0

    def test_high_unresolved_fails(self):
        challenges = [
            {"severity": "HIGH", "resolution": None},
            {"severity": "MEDIUM", "resolution": "RESOLVED"},
        ]
        result = compute_gate(challenges)
        assert result["gate_pass"] is False

    def test_not_genuine_excluded(self):
        challenges = [
            {"severity": "HIGH", "resolution": "RESOLVED"},
            {"severity": "MEDIUM", "resolution": "NOT_GENUINE"},
        ]
        result = compute_gate(challenges)
        assert result["gate_pass"] is True
        assert result["genuine"] == 1  # only HIGH counted

    def test_all_low_passes(self):
        challenges = [
            {"severity": "LOW", "resolution": None},
            {"severity": "LOW", "resolution": None},
        ]
        result = compute_gate(challenges)
        assert result["gate_pass"] is True  # genuine == 0 → pass

    def test_empty_challenges(self):
        result = compute_gate([])
        assert result["gate_pass"] is True

    def test_below_ratio_threshold(self):
        challenges = [
            {"severity": "HIGH", "resolution": "RESOLVED"},
            {"severity": "MEDIUM", "resolution": None},
            {"severity": "MEDIUM", "resolution": None},
            {"severity": "MEDIUM", "resolution": None},
            {"severity": "MEDIUM", "resolution": None},
        ]
        result = compute_gate(challenges)
        assert result["gate_pass"] is False  # 1/5 = 0.2 < 0.8

    def test_high_not_genuine_bypassed(self):
        challenges = [
            {"severity": "HIGH", "resolution": "NOT_GENUINE"},
            {"severity": "MEDIUM", "resolution": "RESOLVED"},
        ]
        result = compute_gate(challenges)
        assert result["gate_pass"] is True  # NOT_GENUINE HIGH excluded

    def test_high_documented_passes(self):
        challenges = [
            {"severity": "HIGH", "resolution": "DOCUMENTED"},
        ]
        result = compute_gate(challenges)
        assert result["gate_pass"] is True

    def test_custom_threshold(self):
        challenges = [
            {"severity": "HIGH", "resolution": "RESOLVED"},
            {"severity": "MEDIUM", "resolution": None},
        ]
        assert compute_gate(challenges, threshold=0.4)["gate_pass"] is True
        assert compute_gate(challenges, threshold=0.8)["gate_pass"] is False

    def test_all_medium_unresolved_no_high(self):
        challenges = [
            {"severity": "MEDIUM", "resolution": None},
            {"severity": "MEDIUM", "resolution": None},
        ]
        result = compute_gate(challenges)
        assert result["all_high_resolved"] is True  # vacuously true
        assert result["gate_pass"] is False  # 0/2 = 0.0 < 0.8


class TestAlignReturnCounts:
    """Verify pass1_count and pass2_count are returned correctly."""

    def test_all_pass1(self):
        reqs = [{"id": "R1", "source": {"section": "3.1", "line": 5},
                 "description": "test", "type": "functional", "priority": "must",
                 "complexity": "low", "acceptance_criteria": []}]
        aligned, v1_only, v2_only, p1, p2 = align_requirements(reqs, reqs)
        assert p1 == 1
        assert p2 == 0

    def test_all_pass2(self):
        v1 = [{"id": "R1", "source": {}, "description": "alpha beta gamma",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": []}]
        v2 = [{"id": "R2", "source": {}, "description": "alpha beta gamma",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": []}]
        aligned, _, _, p1, p2 = align_requirements(v1, v2)
        assert p1 == 0
        assert p2 == 1


class TestAlignPairingCorrectness:
    """Verify correct items are paired, not just counts."""

    def test_best_match_pairing(self):
        v1 = [{"id": "R1", "source": {"section": "3.1", "line": 5},
               "description": "signed 8-bit data input",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": ["signed input"]},
              {"id": "R2", "source": {"section": "3.1", "line": 10},
               "description": "unsigned 8-bit data output",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": ["unsigned output"]}]
        v2 = [{"id": "R3", "source": {"section": "3.1", "line": 6},
               "description": "unsigned 8-bit data output",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": ["unsigned output"]},
              {"id": "R4", "source": {"section": "3.1", "line": 11},
               "description": "signed 8-bit data input",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": ["signed input"]}]
        aligned, _, _, _, _ = align_requirements(v1, v2)
        pairs = {(a[0]["id"], a[1]["id"]) for a in aligned}
        assert ("R1", "R4") in pairs  # signed ↔ signed
        assert ("R2", "R3") in pairs  # unsigned ↔ unsigned


class TestSourceNull:
    """Verify source: null doesn't crash."""

    def test_null_source_similarity(self):
        r1 = {"source": None, "description": "test", "type": "functional",
               "priority": "must", "complexity": "low", "acceptance_criteria": []}
        r2 = {"source": None, "description": "test", "type": "functional",
               "priority": "must", "complexity": "low", "acceptance_criteria": []}
        sim = compute_pair_similarity(r1, r2)
        assert 0.0 <= sim <= 1.0

    def test_null_source_alignment(self):
        reqs = [{"id": "R1", "source": None, "description": "alpha beta",
                 "type": "functional", "priority": "must", "complexity": "low",
                 "acceptance_criteria": []}]
        aligned, v1_only, v2_only, _, _ = align_requirements(reqs, reqs)
        assert len(aligned) == 1


class TestGenerateReport:
    def test_basic_report_structure(self):
        aligned = [
            ({"source": {"section": "3.1"}, "description": "A"},
             {"source": {"section": "3.1"}, "description": "A"}, 0.95),
        ]
        report = generate_report(aligned, [], [], "v1.json", "v2.json", 1, 0)
        assert "# Interpretation Stability Report" in report
        assert "## Alignment Summary" in report
        assert "v1.json" in report
        assert "avg similarity: 0.95" in report

    def test_report_with_changes(self):
        v1_only = [{"source": {"section": "2.0"}, "description": "removed item"}]
        v2_only = [{"source": {"section": "4.0"}, "description": "new item"}]
        report = generate_report([], v1_only, v2_only, "a.json", "b.json")
        assert "## Changes From Clarification" in report
        assert "REMOVED" in report
        assert "ADDED" in report

    def test_pass2_warning(self):
        aligned = [
            ({"source": {}, "description": "x"},
             {"source": {}, "description": "x"}, 0.5),
        ]
        report = generate_report(aligned, [], [], "a.json", "b.json", 0, 1)
        assert "WARNING" in report

    def test_no_warning_when_pass1_dominant(self):
        aligned = [
            ({"source": {"section": "1"}, "description": "x"},
             {"source": {"section": "1"}, "description": "x"}, 0.9),
        ]
        report = generate_report(aligned, [], [], "a.json", "b.json", 1, 0)
        assert "WARNING" not in report

    def test_empty_aligned(self):
        report = generate_report([], [], [], "a.json", "b.json")
        assert "avg similarity: 0.00" in report
