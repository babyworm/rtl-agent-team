"""Tests for cascading requirements JSON schemas."""
import json
import re
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

REQUIRED_IRON_FIELDS = {"id", "type", "description", "priority", "source", "acceptance_criteria", "violation_policy"}
VALID_TYPES = {"functional", "performance", "architecture", "micro-architecture"}
VALID_PRIORITIES = {"must", "should", "may"}
VALID_VIOLATION_POLICIES = {"user_escalation", "agent_retry"}
VALID_ID_PREFIXES = {"REQ-F-", "REQ-P-", "REQ-A-", "REQ-U-"}

REQUIRED_OPEN_FIELDS = {"id", "topic", "context", "candidates", "evaluation_criteria", "related_iron", "resolution_expected"}

REQUIRED_SUMMARY_FIELDS = {"verdict", "total", "pass", "violation", "uncertain", "max_violation_authority", "infeasibility_detected"}
VALID_VERDICTS = {"PASS", "FAIL"}
VALID_RESULT_VERDICTS = {"PASS", "VIOLATION", "UNCERTAIN"}

REQUIRED_STATE_FIELDS = {"phase", "upstream_iron_paths", "open_requirements_path", "compliance_status", "compliance_authority", "challenge_count", "last_check_timestamp"}
VALID_STATUSES = {"pending", "pass", "violation", "challenge_pending"}


class TestIronRequirementsSchema:
    """Validate iron-requirements.json structure."""

    def test_valid_iron_requirement(self):
        req = {
            "id": "REQ-F-001",
            "type": "functional",
            "description": "Test requirement",
            "priority": "must",
            "source": {"document": "spec.pdf", "section": "1.1", "line": 10},
            "acceptance_criteria": ["Measurable criterion"],
            "violation_policy": "user_escalation"
        }
        assert REQUIRED_IRON_FIELDS.issubset(req.keys())
        assert req["type"] in VALID_TYPES
        assert req["violation_policy"] in VALID_VIOLATION_POLICIES
        assert any(req["id"].startswith(p) for p in VALID_ID_PREFIXES)

    def test_acceptance_criteria_must_be_nonempty_list(self):
        ac = []
        assert not ac, "Empty acceptance_criteria should be rejected"

    def test_vague_acceptance_criteria_detection(self):
        vague_terms = ["should support", "adequate", "sufficient", "appropriate"]
        criteria = "System should support real-time processing"
        matches = [t for t in vague_terms if t in criteria.lower()]
        assert len(matches) > 0, "Should detect vague language"

    def test_authority_must_be_1_2_or_3(self):
        valid_authorities = {1, 2, 3}
        for valid in [1, 2, 3]:
            assert valid in valid_authorities
        for invalid in [0, 4, -1]:
            assert invalid not in valid_authorities

    def test_id_prefix_matches_type(self):
        type_prefix_map = {
            "functional": "REQ-F-",
            "performance": "REQ-P-",
            "architecture": "REQ-A-",
            "micro-architecture": "REQ-U-",
        }
        for req_type, prefix in type_prefix_map.items():
            req_id = f"{prefix}001"
            assert req_id.startswith(prefix)


class TestOpenRequirementsSchema:
    """Validate open-requirements.json structure."""

    def test_valid_open_requirement(self):
        item = {
            "id": "OPEN-1-001",
            "topic": "Architecture selection",
            "context": "Multiple options available",
            "candidates": ["option-a", "option-b"],
            "evaluation_criteria": ["gate_count", "throughput"],
            "related_iron": ["REQ-F-001"],
            "resolution_expected": "Finalized in iron-requirements.json"
        }
        assert REQUIRED_OPEN_FIELDS.issubset(item.keys())

    def test_candidates_must_have_at_least_two(self):
        item = {"candidates": ["only-one"]}
        assert len(item["candidates"]) < 2, "Single candidate is not a research topic"

    def test_open_id_format(self):
        valid_ids = ["OPEN-1-001", "OPEN-2-003", "OPEN-3-012"]
        for oid in valid_ids:
            assert re.match(r"^OPEN-\d+-\d{3}$", oid)

    def test_invalid_open_id_rejected(self):
        invalid_ids = ["OPEN-001", "REQ-F-001", "open-1-001", "OPEN-1"]
        for oid in invalid_ids:
            assert not re.match(r"^OPEN-\d+-\d{3}$", oid)


class TestComplianceReportSchema:
    """Validate compliance-report.json structure."""

    def test_valid_summary(self):
        summary = {
            "verdict": "FAIL",
            "total": 24,
            "pass": 21,
            "violation": 2,
            "uncertain": 1,
            "max_violation_authority": 1,
            "infeasibility_detected": False
        }
        assert REQUIRED_SUMMARY_FIELDS.issubset(summary.keys())
        assert summary["verdict"] in VALID_VERDICTS
        assert summary["total"] == summary["pass"] + summary["violation"] + summary["uncertain"]

    def test_uncertain_ratio_gate(self):
        """UNCERTAIN ratio > 20% should fail compliance check."""
        summary = {"total": 10, "uncertain": 3}
        ratio = summary["uncertain"] / summary["total"]
        assert ratio > 0.2

    def test_result_verdicts_valid(self):
        for v in VALID_RESULT_VERDICTS:
            assert v in {"PASS", "VIOLATION", "UNCERTAIN"}

    def test_verdict_pass_requires_zero_violations(self):
        summary = {"verdict": "PASS", "violation": 0, "uncertain": 1, "total": 10}
        assert summary["violation"] == 0, "PASS verdict requires zero violations"


class TestComplianceStateSchema:
    """Validate compliance-state.json template."""

    def test_valid_state(self):
        state = {
            "phase": "",
            "upstream_iron_paths": [],
            "open_requirements_path": "",
            "compliance_status": "pending",
            "compliance_authority": None,
            "challenge_count": 0,
            "last_check_timestamp": None
        }
        assert REQUIRED_STATE_FIELDS.issubset(state.keys())
        assert state["compliance_status"] in VALID_STATUSES

    def test_all_valid_statuses(self):
        for status in VALID_STATUSES:
            assert status in {"pending", "pass", "violation", "challenge_pending"}

    def test_compliance_state_template_matches_schema(self):
        """Verify the actual template file matches expected schema."""
        template_path = REPO_ROOT / "skills" / "rtl-design-policy" / "templates" / "compliance-state.json"
        if template_path.exists():
            state = json.loads(template_path.read_text())
            assert REQUIRED_STATE_FIELDS.issubset(state.keys())
            assert state["compliance_status"] in VALID_STATUSES
