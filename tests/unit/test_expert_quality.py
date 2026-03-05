"""Tests for domain expert prompt quality and routing consistency.

These tests enforce Quality Contract compliance, required token presence,
knowledge base reference integrity, manifest-agent consistency, and
routing keyword coverage to prevent quality regression in expert prompts.
"""

import json
import re
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

AGENTS_DIR = REPO_ROOT / "agents"
DOMAIN_PKG_DIR = REPO_ROOT / "domain-packages" / "video-codec"
MANIFEST_PATH = DOMAIN_PKG_DIR / "manifest.json"
KNOWLEDGE_DIR = DOMAIN_PKG_DIR / "knowledge"
VPROC_PKG_DIR = REPO_ROOT / "domain-packages" / "video-processing"
VPROC_MANIFEST_PATH = VPROC_PKG_DIR / "manifest.json"
DOMAIN_CONSULT_SKILL = REPO_ROOT / "skills" / "domain-consult" / "SKILL.md"


@pytest.fixture
def manifest():
    if not MANIFEST_PATH.exists():
        pytest.skip("Video codec domain package not present")
    return json.loads(MANIFEST_PATH.read_text())


@pytest.fixture
def vproc_manifest():
    if not VPROC_MANIFEST_PATH.exists():
        pytest.skip("Video processing domain package not present")
    return json.loads(VPROC_MANIFEST_PATH.read_text())


# ── Quality Contract Presence ────────────────────────────────────────────────


VCODEC_EXPERTS = [
    "vcodec-syntax-entropy-expert",
    "vcodec-prediction-expert",
    "vcodec-transform-quant-expert",
    "vcodec-filter-recon-expert",
    "vcodec-chief-standard-expert",
    "vcodec-architecture-expert",
    "video-processing-expert",
]

VPROC_EXPERTS = [
    "vproc-color-format-expert",
    "vproc-denoise-expert",
    "vproc-image-processing-expert",
]

ALL_DOMAIN_EXPERTS = VCODEC_EXPERTS + VPROC_EXPERTS


class TestExpertQualityContract:
    """Validate that all domain experts have a <Quality_Contract> section."""

    @pytest.mark.parametrize("agent_name", VCODEC_EXPERTS)
    def test_has_quality_contract(self, agent_name):
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        assert agent_file.exists(), f"Agent file missing: {agent_name}.md"
        content = agent_file.read_text()
        assert "<Quality_Contract>" in content, (
            f"{agent_name} is missing <Quality_Contract> section"
        )
        assert "</Quality_Contract>" in content, (
            f"{agent_name} has unclosed <Quality_Contract> tag"
        )

    def test_tq_expert_has_extended_contract(self):
        """TQ expert must have 4 additional TQ-specific contract items."""
        agent_file = AGENTS_DIR / "vcodec-transform-quant-expert.md"
        content = agent_file.read_text()
        tq_items = [
            "lambda_definition",
            "cabac_rate_linkage",
            "qp_boundary",
            "ref_sw_comparison",
        ]
        for item in tq_items:
            assert item in content, (
                f"vcodec-transform-quant-expert missing TQ-specific contract item: {item}"
            )

    def test_chief_has_contract_compliance_check(self):
        """Chief expert must verify sub-domain Quality Contract compliance."""
        agent_file = AGENTS_DIR / "vcodec-chief-standard-expert.md"
        content = agent_file.read_text()
        assert "contract_compliance_check" in content, (
            "Chief expert missing contract_compliance_check in Quality_Contract"
        )


# ── Required Token Presence ──────────────────────────────────────────────────

# Sub-domain experts (excluding chief, architecture, video-processing)
SUBDOMAIN_EXPERTS = [
    "vcodec-syntax-entropy-expert",
    "vcodec-prediction-expert",
    "vcodec-transform-quant-expert",
    "vcodec-filter-recon-expert",
]


class TestExpertRequiredTokens:
    """Validate that expert prompts contain required structural tokens."""

    @pytest.mark.parametrize("agent_name", SUBDOMAIN_EXPERTS)
    def test_has_domain_uncertainty_tag(self, agent_name):
        content = (AGENTS_DIR / f"{agent_name}.md").read_text()
        assert "DOMAIN_UNCERTAINTY" in content, (
            f"{agent_name} missing DOMAIN_UNCERTAINTY tag reference"
        )

    @pytest.mark.parametrize("agent_name", SUBDOMAIN_EXPERTS)
    def test_has_clause_citation_instruction(self, agent_name):
        content = (AGENTS_DIR / f"{agent_name}.md").read_text()
        assert re.search(r"clause|§[A-Z0-9]", content), (
            f"{agent_name} missing clause citation instruction"
        )

    @pytest.mark.parametrize("agent_name", SUBDOMAIN_EXPERTS)
    def test_has_encoder_decoder_distinction(self, agent_name):
        content = (AGENTS_DIR / f"{agent_name}.md").read_text()
        assert re.search(r"encoder.*decoder|enc_dec_scope|forward.*inverse", content), (
            f"{agent_name} missing encoder/decoder distinction"
        )

    @pytest.mark.parametrize("agent_name", SUBDOMAIN_EXPERTS)
    def test_has_conformance_reference(self, agent_name):
        content = (AGENTS_DIR / f"{agent_name}.md").read_text()
        assert re.search(r"JM|HM|conformance|reference.*(software|SW)", content), (
            f"{agent_name} missing conformance/reference SW mention"
        )

    @pytest.mark.parametrize("agent_name", VCODEC_EXPERTS)
    def test_has_final_checklist(self, agent_name):
        content = (AGENTS_DIR / f"{agent_name}.md").read_text()
        assert "<Final_Checklist>" in content, (
            f"{agent_name} missing <Final_Checklist> section"
        )

    @pytest.mark.parametrize("agent_name", VCODEC_EXPERTS)
    def test_final_checklist_references_quality_contract(self, agent_name):
        """Final checklist should reference Quality Contract compliance."""
        content = (AGENTS_DIR / f"{agent_name}.md").read_text()
        assert re.search(r"Quality Contract", content), (
            f"{agent_name} Final_Checklist does not reference Quality Contract"
        )


# ── Knowledge Base Reference Integrity ───────────────────────────────────────


class TestExpertKnowledgeBaseRef:
    """Validate that knowledge files referenced by experts actually exist."""

    def _extract_knowledge_refs(self, content):
        """Extract knowledge file paths from agent prompt content."""
        refs = re.findall(
            r"domain-packages/video-codec/knowledge/([^\s)`\"]+\.md)", content
        )
        return refs

    @pytest.mark.parametrize("agent_name", VCODEC_EXPERTS)
    def test_referenced_knowledge_files_exist(self, agent_name):
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        content = agent_file.read_text()
        refs = self._extract_knowledge_refs(content)
        for ref in refs:
            knowledge_file = KNOWLEDGE_DIR / ref
            assert knowledge_file.exists(), (
                f"{agent_name} references non-existent knowledge file: {ref}"
            )

    def test_manifest_knowledge_files_exist(self, manifest):
        """All knowledge files listed in manifest.json must exist on disk."""
        for entry in manifest.get("knowledge_base", {}).get("contents", []):
            knowledge_file = KNOWLEDGE_DIR / entry["file"]
            assert knowledge_file.exists(), (
                f"Manifest lists non-existent knowledge file: {entry['file']}"
            )


# ── Manifest-Agent File Consistency ──────────────────────────────────────────


class TestManifestAgentFileExists:
    """Validate that every agent declared in manifest.json has a corresponding file."""

    def test_all_manifest_agents_have_files(self, manifest):
        agents = manifest.get("agents", [])
        assert len(agents) > 0, "No agents in manifest"
        missing = []
        for agent in agents:
            agent_file = REPO_ROOT / agent["file"]
            if not agent_file.exists():
                missing.append(agent["id"])
        assert missing == [], f"Manifest agents with missing files: {missing}"

    def test_manifest_agent_ids_match_filenames(self, manifest):
        """Agent id should match the filename (without .md extension)."""
        mismatches = []
        for agent in manifest.get("agents", []):
            expected_filename = f"agents/{agent['id']}.md"
            if agent["file"] != expected_filename:
                mismatches.append(
                    f"{agent['id']}: expected '{expected_filename}', got '{agent['file']}'"
                )
        assert mismatches == [], f"Agent ID/filename mismatches: {mismatches}"


# ── Knowledge Version Consistency ────────────────────────────────────────────


class TestKnowledgeVersionConsistency:
    """Validate version consistency between manifest, knowledge files, and ref SW."""

    def test_h264_spec_version_matches(self, manifest):
        """h264-spec-summary.md reference version must match manifest entry."""
        for entry in manifest["knowledge_base"]["contents"]:
            if entry["file"] == "h264-spec-summary.md":
                assert entry.get("standard_version"), (
                    "h264-spec-summary.md missing standard_version in manifest"
                )
                content = (KNOWLEDGE_DIR / entry["file"]).read_text()
                assert entry["standard_version"] in content, (
                    f"h264-spec-summary.md does not contain manifest version "
                    f"'{entry['standard_version']}'"
                )
                return
        pytest.fail("h264-spec-summary.md not found in manifest knowledge_base")

    def test_h265_spec_version_matches(self, manifest):
        """h265-spec-summary.md reference version must match manifest entry."""
        for entry in manifest["knowledge_base"]["contents"]:
            if entry["file"] == "h265-spec-summary.md":
                assert entry.get("standard_version"), (
                    "h265-spec-summary.md missing standard_version in manifest"
                )
                content = (KNOWLEDGE_DIR / entry["file"]).read_text()
                assert entry["standard_version"] in content, (
                    f"h265-spec-summary.md does not contain manifest version "
                    f"'{entry['standard_version']}'"
                )
                return
        pytest.fail("h265-spec-summary.md not found in manifest knowledge_base")

    def test_jm_version_matches_manifest_ref_sw(self, manifest):
        """JM function map version must match manifest reference_software entry."""
        jm_manifest_version = None
        for sw in manifest.get("reference_software", []):
            if sw["id"] == "JM":
                jm_manifest_version = sw["version"]
                break
        if jm_manifest_version is None:
            pytest.skip("JM not in manifest reference_software")

        for entry in manifest["knowledge_base"]["contents"]:
            if entry["file"] == "jm-function-map.md":
                content = (KNOWLEDGE_DIR / entry["file"]).read_text()
                assert jm_manifest_version in content, (
                    f"jm-function-map.md does not reference JM version "
                    f"'{jm_manifest_version}' declared in manifest"
                )
                return
        pytest.skip("jm-function-map.md not in manifest knowledge_base")

    def test_all_knowledge_entries_have_standard_id(self, manifest):
        """Every knowledge_base entry must declare which standard(s) it covers."""
        missing = []
        for entry in manifest["knowledge_base"]["contents"]:
            if "standard_id" not in entry:
                missing.append(entry["file"])
        assert missing == [], (
            f"Knowledge entries missing standard_id: {missing}"
        )

    def test_knowledge_standard_ids_match_manifest_standards(self, manifest):
        """standard_id values in knowledge entries must exist in manifest standards list."""
        valid_ids = {s["id"] for s in manifest.get("standards", [])}
        invalid = []
        for entry in manifest["knowledge_base"]["contents"]:
            std_ids = entry.get("standard_id", [])
            if isinstance(std_ids, str):
                std_ids = [std_ids]
            if std_ids is None:
                continue
            for sid in std_ids:
                if sid not in valid_ids:
                    invalid.append(f"{entry['file']}: unknown standard_id '{sid}'")
        assert invalid == [], f"Invalid standard_id references: {invalid}"


# ── Routing Keyword Coverage ─────────────────────────────────────────────────


class TestRoutingKeywordCoverage:
    """Validate that manifest agent triggers appear in domain-consult routing."""

    def _get_routing_table_content(self):
        if not DOMAIN_CONSULT_SKILL.exists():
            pytest.skip("domain-consult SKILL.md not found")
        return DOMAIN_CONSULT_SKILL.read_text()

    def test_all_manifest_agents_have_routing_entry(self, manifest):
        """Every agent in manifest should be referenced in domain-consult routing."""
        routing_content = self._get_routing_table_content()
        agents = manifest.get("agents", [])
        missing = []
        for agent in agents:
            agent_id = agent["id"]
            if agent_id not in routing_content:
                missing.append(agent_id)
        assert missing == [], (
            f"Manifest agents not referenced in domain-consult routing: {missing}"
        )

    def test_manifest_trigger_keywords_covered(self, manifest):
        """At least one trigger keyword per agent should appear in routing table."""
        routing_content = self._get_routing_table_content().lower()
        agents_with_missing_triggers = []
        for agent in manifest.get("agents", []):
            triggers = agent.get("triggers", [])
            if not triggers:
                continue
            found_any = any(t.lower() in routing_content for t in triggers)
            if not found_any:
                agents_with_missing_triggers.append(
                    f"{agent['id']}: none of {triggers[:3]}... found in routing"
                )
        assert agents_with_missing_triggers == [], (
            f"Agents with no trigger keywords in routing table: "
            f"{agents_with_missing_triggers}"
        )

    def test_vproc_manifest_agents_have_routing_entry(self, vproc_manifest):
        """Every agent in vproc manifest should be referenced in domain-consult routing."""
        routing_content = self._get_routing_table_content()
        agents = vproc_manifest.get("agents", [])
        missing = []
        for agent in agents:
            agent_id = agent["id"]
            if agent_id not in routing_content:
                missing.append(agent_id)
        assert missing == [], (
            f"Vproc manifest agents not referenced in domain-consult routing: {missing}"
        )

    def test_vproc_manifest_trigger_keywords_covered(self, vproc_manifest):
        """At least one trigger keyword per vproc agent should appear in routing table."""
        routing_content = self._get_routing_table_content().lower()
        agents_with_missing_triggers = []
        for agent in vproc_manifest.get("agents", []):
            triggers = agent.get("triggers", [])
            if not triggers:
                continue
            found_any = any(t.lower() in routing_content for t in triggers)
            if not found_any:
                agents_with_missing_triggers.append(
                    f"{agent['id']}: none of {triggers[:3]}... found in routing"
                )
        assert agents_with_missing_triggers == [], (
            f"Vproc agents with no trigger keywords in routing table: "
            f"{agents_with_missing_triggers}"
        )


# ── Video Processing Domain Tests ────────────────────────────────────────────


class TestVprocExpertQuality:
    """Validate video-processing domain expert prompts."""

    @pytest.mark.parametrize("agent_name", VPROC_EXPERTS)
    def test_has_quality_contract(self, agent_name):
        agent_file = AGENTS_DIR / f"{agent_name}.md"
        assert agent_file.exists(), f"Agent file missing: {agent_name}.md"
        content = agent_file.read_text()
        assert "<Quality_Contract>" in content, (
            f"{agent_name} is missing <Quality_Contract> section"
        )
        assert "</Quality_Contract>" in content, (
            f"{agent_name} has unclosed <Quality_Contract> tag"
        )

    @pytest.mark.parametrize("agent_name", VPROC_EXPERTS)
    def test_has_final_checklist(self, agent_name):
        content = (AGENTS_DIR / f"{agent_name}.md").read_text()
        assert "<Final_Checklist>" in content, (
            f"{agent_name} missing <Final_Checklist> section"
        )

    @pytest.mark.parametrize("agent_name", VPROC_EXPERTS)
    def test_final_checklist_references_quality_contract(self, agent_name):
        content = (AGENTS_DIR / f"{agent_name}.md").read_text()
        assert "Quality Contract" in content, (
            f"{agent_name} Final_Checklist does not reference Quality Contract"
        )

    @pytest.mark.parametrize("agent_name", VPROC_EXPERTS)
    def test_has_domain_uncertainty_tag(self, agent_name):
        content = (AGENTS_DIR / f"{agent_name}.md").read_text()
        assert "DOMAIN_UNCERTAINTY" in content, (
            f"{agent_name} missing DOMAIN_UNCERTAINTY tag reference"
        )

    @pytest.mark.parametrize("agent_name", VPROC_EXPERTS)
    def test_has_fixed_point_spec(self, agent_name):
        """Vproc experts must include fixed-point implementation guidance."""
        content = (AGENTS_DIR / f"{agent_name}.md").read_text()
        assert re.search(r"[Ff]ixed.?[Pp]oint|Q\d+\.\d+", content), (
            f"{agent_name} missing fixed-point implementation reference"
        )

    @pytest.mark.parametrize("agent_name", VPROC_EXPERTS)
    def test_has_team_worker_protocol(self, agent_name):
        """Vproc experts must include Team Worker Protocol section."""
        content = (AGENTS_DIR / f"{agent_name}.md").read_text()
        assert "Team Worker Protocol" in content, (
            f"{agent_name} missing Team Worker Protocol section"
        )


class TestVprocManifestConsistency:
    """Validate video-processing manifest-agent consistency."""

    def test_all_manifest_agents_have_files(self, vproc_manifest):
        agents = vproc_manifest.get("agents", [])
        assert len(agents) > 0, "No agents in vproc manifest"
        missing = []
        for agent in agents:
            agent_file = REPO_ROOT / agent["file"]
            if not agent_file.exists():
                missing.append(agent["id"])
        assert missing == [], f"Vproc manifest agents with missing files: {missing}"

    def test_manifest_agent_ids_match_filenames(self, vproc_manifest):
        mismatches = []
        for agent in vproc_manifest.get("agents", []):
            expected_filename = f"agents/{agent['id']}.md"
            if agent["file"] != expected_filename:
                mismatches.append(
                    f"{agent['id']}: expected '{expected_filename}', got '{agent['file']}'"
                )
        assert mismatches == [], f"Vproc agent ID/filename mismatches: {mismatches}"

    def test_manifest_status_is_active(self, vproc_manifest):
        """Video-processing package should be active (not scaffold)."""
        assert vproc_manifest.get("status") == "active", (
            "video-processing manifest status should be 'active'"
        )

    def test_manifest_has_standards(self, vproc_manifest):
        standards = vproc_manifest.get("standards", [])
        assert len(standards) > 0, "Vproc manifest has no standards listed"

    def test_manifest_scope_definition_present(self, vproc_manifest):
        assert "scope_definition" in vproc_manifest, (
            "Vproc manifest missing scope_definition"
        )
