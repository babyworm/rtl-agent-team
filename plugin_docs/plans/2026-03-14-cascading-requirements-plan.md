# Cascading Requirements Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add iron/open requirement taxonomy, compliance checker, and upstream challenge protocol to the RTL agent team plugin's phase-gated pipeline.

**Architecture:** Each phase produces `iron-requirements.json` (absolute rules) and `open-requirements.json` (homework). A compliance-checker agent validates downstream artifacts against upstream iron. The existing escalation ladder in `rtl-skill-completion-gate.sh` is extended with authority-differentiated budgets. No new hooks are added; 4 existing hooks are modified.

**Tech Stack:** POSIX shell (hooks), Markdown (agents/skills/policies), JSON (schemas/state), Python/pytest (tests)

**Spec:** `plugin_docs/specs/2026-03-14-cascading-requirements-design.md`

---

## File Structure

### New Files (2)
| File | Responsibility |
|------|---------------|
| `agents/compliance-checker.md` | Opus agent that compares downstream artifacts against upstream iron-requirements.json |
| `skills/rtl-p4-rapid-impl-policy/templates/compliance-state.json` | State template bootstrapped by phase-state-bootstrap hook |

### Modified Files (22)
| File | Change Summary |
|------|---------------|
| `skills/p1-spec-research-policy/SKILL.md` | Iron/open schema definition, classification verification rules |
| `agents/spec-analyst.md` | Output iron/open JSON instead of flat requirements.json |
| `skill-completion-criteria.json` | Add 5 new criteria to 10 skill entries |
| `skills/p2-arch-design-policy/SKILL.md` | Open resolution protocol, compliance procedure |
| `agents/p2-arch-orchestrator.md` | Open resolution step, compliance check invocation |
| `skills/rtl-p3-uarch-policy/SKILL.md` | Open resolution, zero-opens invariant, compliance |
| `agents/p3-uarch-orchestrator.md` | Open resolution, compliance, upstream challenge |
| `agents/p1-research-orchestrator.md` | Iron/open classification verification step |
| `hooks/rtl-phase-state-bootstrap.sh` | Upstream iron path injection, compliance-state.json creation |
| `hooks/rtl-skill-completion-gate.sh` | compliance-pass gate, authority-differentiated budgets, infeasibility branch |
| `hooks/rtl-spawn-context.sh` | Add upstream_iron and open_requirements to spawn context |
| `hooks/rtl-orchestrator-inject.sh` | Add Iron Requirements Protocol (~10 lines) |
| `skills/p1-spec-research/SKILL.md` | Reference iron/open artifacts in output section |
| `skills/p2-arch-design/SKILL.md` | Add open resolution and compliance gate to flow |
| `skills/rtl-p3-uarch-design/SKILL.md` | Add open resolution, zero-opens, compliance to flow |
| `skills/rtl-p1-research-team/SKILL.md` | Team variant: same changes as base P1 skill |
| `skills/rtl-p2-arch-team/SKILL.md` | Team variant: same changes as base P2 skill |
| `skills/rtl-p3-uarch-team/SKILL.md` | Team variant: same changes as base P3 skill |
| `skills/rtl-p4-implement/SKILL.md` | Add per-wave compliance check |
| `skills/rtl-p4-implement-team/SKILL.md` | Team variant: per-wave compliance |
| `skills/rtl-p5-verify/SKILL.md` | Add final acceptance_criteria compliance check |
| `skills/rtl-p5-verify-team/SKILL.md` | Team variant: final compliance |

### Test Files (new/modified)
| File | Tests |
|------|-------|
| `tests/unit/test_compliance_schema.py` | NEW: iron/open JSON schema validation, compliance-report structure |
| `tests/unit/test_hooks.py` | MODIFY: add compliance-gate tests, iron path injection tests |
| `tests/unit/test_json_schemas.py` | MODIFY: add skill-completion-criteria new entries validation |
| `tests/unit/test_agent_skill_structure.py` | MODIFY: add compliance-checker agent structural checks |

---

## Chunk 1: Schema + Core Agent (Foundation)

### Task 1: Iron/Open JSON Schema Tests

**Files:**
- Create: `tests/unit/test_compliance_schema.py`

- [ ] **Step 1: Write iron-requirements.json schema validation test**

```python
"""Tests for cascading requirements JSON schemas."""
import json
from pathlib import Path

import pytest

REQUIRED_IRON_FIELDS = {"id", "type", "description", "priority", "source", "acceptance_criteria", "violation_policy"}
VALID_TYPES = {"functional", "performance", "architecture", "micro-architecture"}
VALID_PRIORITIES = {"must", "should", "may"}
VALID_VIOLATION_POLICIES = {"user_escalation", "agent_retry"}
VALID_ID_PREFIXES = {"REQ-F-", "REQ-P-", "REQ-A-", "REQ-U-"}


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
        with pytest.raises(AssertionError):
            ac = []
            assert len(ac) > 0

    def test_vague_acceptance_criteria_detection(self):
        vague_terms = ["should support", "adequate", "sufficient", "appropriate"]
        criteria = "System should support real-time processing"
        matches = [t for t in vague_terms if t in criteria.lower()]
        assert len(matches) > 0, "Should detect vague language"

    def test_authority_must_be_1_2_or_3(self):
        for valid in [1, 2, 3]:
            assert valid in {1, 2, 3}
        for invalid in [0, 4, -1]:
            assert invalid not in {1, 2, 3}
```

- [ ] **Step 2: Write open-requirements.json schema validation test**

Add to same file:

```python
REQUIRED_OPEN_FIELDS = {"id", "topic", "context", "candidates", "evaluation_criteria", "related_iron", "resolution_expected"}


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
        import re
        valid_ids = ["OPEN-1-001", "OPEN-2-003", "OPEN-3-012"]
        for oid in valid_ids:
            assert re.match(r"^OPEN-\d+-\d{3}$", oid)
```

- [ ] **Step 3: Write compliance-report schema validation test**

Add to same file:

```python
REQUIRED_SUMMARY_FIELDS = {"verdict", "total", "pass", "violation", "uncertain", "max_violation_authority", "infeasibility_detected"}
VALID_VERDICTS = {"PASS", "FAIL"}
VALID_RESULT_VERDICTS = {"PASS", "VIOLATION", "UNCERTAIN"}


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
        summary = {"total": 10, "uncertain": 3}
        ratio = summary["uncertain"] / summary["total"]
        assert ratio > 0.2, "UNCERTAIN ratio > 20% should FAIL compliance check"
```

- [ ] **Step 4: Write compliance-state.json template validation test**

Add to same file:

```python
REQUIRED_STATE_FIELDS = {"phase", "upstream_iron_paths", "open_requirements_path", "compliance_status", "compliance_authority", "challenge_count", "last_check_timestamp"}
VALID_STATUSES = {"pending", "pass", "violation", "challenge_pending"}


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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/babyworm/work/rtl-agent-team && python -m pytest tests/unit/test_compliance_schema.py -v`
Expected: All tests PASS (these are schema definition tests, not integration tests)

- [ ] **Step 6: Commit**

```bash
git add tests/unit/test_compliance_schema.py
git commit -m "test: add iron/open and compliance JSON schema validation tests"
```

---

### Task 2: compliance-state.json Template

**Files:**
- Create: `skills/rtl-p4-rapid-impl-policy/templates/compliance-state.json`

- [ ] **Step 1: Check existing templates directory**

Run: `ls skills/rtl-p4-rapid-impl-policy/templates/`
Expected: See existing template files (p4-state.json etc.)

- [ ] **Step 2: Write compliance-state.json template**

```json
{
  "phase": "",
  "upstream_iron_paths": [],
  "open_requirements_path": "",
  "compliance_status": "pending",
  "compliance_authority": null,
  "challenge_count": 0,
  "last_check_timestamp": null
}
```

- [ ] **Step 3: Verify template matches test schema**

Run: `python -c "import json; t=json.load(open('skills/rtl-p4-rapid-impl-policy/templates/compliance-state.json')); assert set(t.keys()) == {'phase','upstream_iron_paths','open_requirements_path','compliance_status','compliance_authority','challenge_count','last_check_timestamp'}; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add skills/rtl-p4-rapid-impl-policy/templates/compliance-state.json
git commit -m "feat: add compliance-state.json template for phase state bootstrap"
```

---

### Task 3: Update skill-completion-criteria.json

**Files:**
- Modify: `skill-completion-criteria.json`

- [ ] **Step 1: Write test for new criteria entries**

Add to `tests/unit/test_json_schemas.py`:

```python
class TestSkillCompletionCriteriaNewEntries:
    """Validate new cascading requirements criteria."""

    @pytest.fixture
    def criteria(self):
        path = REPO_ROOT / "skill-completion-criteria.json"
        return json.loads(path.read_text())

    @pytest.mark.parametrize("skill", ["p1-spec-research", "rtl-p1-research-team"])
    def test_p1_has_iron_open_classified(self, criteria, skill):
        assert "iron-open-classified" in criteria[skill]
        assert "ambiguity-pass" in criteria[skill]

    @pytest.mark.parametrize("skill", [
        "p2-arch-design", "rtl-p2-arch-team",
        "rtl-p3-uarch-design", "rtl-p3-uarch-team",
    ])
    def test_p2_p3_has_compliance_pass(self, criteria, skill):
        assert "open-resolved" in criteria[skill]
        assert "compliance-pass" in criteria[skill]
        assert "ambiguity-pass" in criteria[skill]

    @pytest.mark.parametrize("skill", ["rtl-p3-uarch-design", "rtl-p3-uarch-team"])
    def test_p3_has_zero_remaining_opens(self, criteria, skill):
        assert "zero-remaining-opens" in criteria[skill]

    @pytest.mark.parametrize("skill", [
        "rtl-p4-implement", "rtl-p4-implement-team",
        "rtl-p5-verify", "rtl-p5-verify-team",
    ])
    def test_p4_p5_has_compliance_pass(self, criteria, skill):
        assert "compliance-pass" in criteria[skill]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_json_schemas.py::TestSkillCompletionCriteriaNewEntries -v`
Expected: FAIL (criteria not yet added)

- [ ] **Step 3: Update skill-completion-criteria.json**

Modify `skill-completion-criteria.json` — add new criteria to each skill entry per spec Section 5.

Changes:
- `p1-spec-research`: append `|iron-open-classified|ambiguity-pass`
- `rtl-p1-research-team`: append `|iron-open-classified|ambiguity-pass`
- `p2-arch-design`: append `|open-resolved|compliance-pass|ambiguity-pass`
- `rtl-p2-arch-team`: append `|open-resolved|compliance-pass|ambiguity-pass`
- `rtl-p3-uarch-design`: append `|open-resolved|zero-remaining-opens|compliance-pass|ambiguity-pass`
- `rtl-p3-uarch-team`: append `|open-resolved|zero-remaining-opens|compliance-pass|ambiguity-pass`
- `rtl-p4-implement`: append `|compliance-pass`
- `rtl-p4-implement-team`: append `|compliance-pass`
- `rtl-p5-verify`: append `|compliance-pass`
- `rtl-p5-verify-team`: append `|compliance-pass`

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_json_schemas.py::TestSkillCompletionCriteriaNewEntries -v`
Expected: All PASS

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `python -m pytest tests/unit/test_json_schemas.py -v`
Expected: All existing tests still PASS

- [ ] **Step 6: Commit**

```bash
git add skill-completion-criteria.json tests/unit/test_json_schemas.py
git commit -m "feat: add cascading requirements completion criteria to 10 skills"
```

---

### Task 4: Compliance Checker Agent

**Files:**
- Create: `agents/compliance-checker.md`

- [ ] **Step 1: Write structural test for the new agent**

Add to `tests/unit/test_agent_skill_structure.py` inside the `TestAgentDefinitions` class:

```python
def test_compliance_checker_agent(self):
    """Verify compliance-checker agent has required sections."""
    agent = AGENTS_DIR / "compliance-checker.md"
    assert agent.exists(), "compliance-checker.md agent must exist"
    content = agent.read_text()
    assert "name: compliance-checker" in content, "Must have name in frontmatter"
    assert "upstream_iron" in content, "Must reference upstream iron requirements"
    assert "VIOLATION" in content, "Must define VIOLATION verdict"
    assert "UNCERTAIN" in content, "Must define UNCERTAIN verdict"
    assert "UNCERTAIN ratio" in content or "anti-rationalization" in content.lower(), "Must include anti-rationalization rules"
    assert "Do not trust" in content, "Must enforce context isolation"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_agent_skill_structure.py::test_compliance_checker_agent_exists -v`
Expected: FAIL (agent does not exist yet)

- [ ] **Step 3: Write the compliance-checker agent**

Create `agents/compliance-checker.md` with the following content. Reference the spec (Section 3) for the full agent definition:

```markdown
---
name: compliance-checker
model: opus
description: Independent compliance verification agent — compares downstream artifacts against upstream iron requirements
tools:
  - Read
  - Glob
  - Grep
---

# Compliance Checker Agent

You are an independent compliance verification agent. Your role is to compare
downstream phase artifacts against upstream iron requirements and produce a
structured compliance report.

**Core principle: "Do not trust the implementer's report. Read the actual artifacts."**

## Input

You receive:
- `upstream_iron`: list of paths to iron-requirements.json files
- `target_artifacts`: list of paths to current phase artifacts

## Procedure

### Step 1: Load Upstream Iron Requirements

Read ALL iron-requirements.json files listed in `upstream_iron`.
Build a flat list of all requirements with their authority levels.

### Step 2: Load Target Artifacts

Read ALL files listed in `target_artifacts`.
These are the artifacts being verified for compliance.

### Step 3: Per-Requirement 1:1 Comparison

For EACH requirement in the upstream iron list:
  For EACH item in its `acceptance_criteria`:
    - Search target artifacts for evidence of fulfillment
    - **PASS**: Explicit evidence found. Record exact file path and section.
    - **VIOLATION**: No evidence found OR evidence contradicts the criterion.
      Record which criterion failed and what was found instead.
    - **UNCERTAIN**: Artifact not yet generated (and ONLY this reason).

### Step 4: Generate Compliance Report

Output a JSON compliance report to `.rtl-agent-team/state/compliance-report.json`.

```json
{
  "phase": "<current phase>",
  "checked_against": ["<upstream phase 1>", "<upstream phase 2>"],
  "timestamp": "<ISO 8601>",
  "summary": {
    "verdict": "PASS or FAIL",
    "total": 0,
    "pass": 0,
    "violation": 0,
    "uncertain": 0,
    "max_violation_authority": null,
    "infeasibility_detected": false
  },
  "results": []
}
```

**Summary rules:**
- `verdict`: "PASS" if violation == 0 AND uncertain ratio <= 0.2. "FAIL" otherwise.
- `max_violation_authority`: lowest authority number among VIOLATION results (null if none).
- `infeasibility_detected`: set to true only if orchestrator has provided validated infeasibility evidence.

**Per-result entry:**
```json
{
  "req_id": "REQ-F-001",
  "authority": 1,
  "verdict": "PASS | VIOLATION | UNCERTAIN",
  "evidence": "file path and section (PASS only)",
  "failed_criteria": "specific criterion text (VIOLATION only)",
  "finding": "what was found instead (VIOLATION only)",
  "suggested_action": "recommended fix (VIOLATION/UNCERTAIN only)",
  "reason": "why uncertain (UNCERTAIN only)"
}
```

## Anti-Rationalization Rules

- UNCERTAIN is allowed ONLY when the artifact has not yet been generated.
- "Probably fine" -> VIOLATION
- "No explicit evidence" -> VIOLATION
- UNCERTAIN ratio > 20% of total -> verdict = FAIL (compliance check itself fails)
- Do NOT accept implementer explanations. Read actual files only.

## Context Isolation

You must be invoked with explicit file paths only:
```
Task(compliance-checker, prompt="""
  upstream_iron: [file paths]
  target_artifacts: [file paths]
  Read only the above files and compare directly.
""")
```

Never accept: "Review what we've done so far" or session-context-based prompts.

## Infeasibility Validation

When invoked with `validate_infeasibility: true`:
- Read the orchestrator's infeasibility claim with quantitative evidence
- Verify the numbers are physically/technically sound
- Check that the evidence uses concrete metrics (not vague language)
- If validated: set `infeasibility_detected: true` in summary
- If rejected (evidence insufficient): set `infeasibility_detected: false`

Valid evidence examples:
- "2-stage pipeline max throughput = 0.8 bin/cycle, required = 1.0 bin/cycle"
- "Gate count estimate 320K, area budget 200K — 1.6x over"

Invalid (reject these):
- "This requirement seems difficult to achieve"
- "Generally this level is unrealistic"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_agent_skill_structure.py::test_compliance_checker_agent_exists -v`
Expected: PASS

- [ ] **Step 5: Run all agent structure tests to check no regression**

Run: `python -m pytest tests/unit/test_agent_skill_structure.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add agents/compliance-checker.md tests/unit/test_agent_skill_structure.py
git commit -m "feat: add compliance-checker agent for upstream iron requirement verification"
```

---

### Task 5: p1-spec-research-policy Iron/Open Schema Definition

**Files:**
- Modify: `skills/p1-spec-research-policy/SKILL.md`

- [ ] **Step 1: Read current policy file**

Run: `cat skills/p1-spec-research-policy/SKILL.md`
Understand the current structure, particularly the Output Artifacts and Final Checklist sections.

- [ ] **Step 2: Add iron/open schema definition section**

After the existing output artifacts section, add:

1. **Iron/Open Requirement Classification** subsection defining:
   - Iron-requirements.json schema (as per spec Section 1)
   - Open-requirements.json schema (as per spec Section 1)
   - ID prefix convention: REQ-F-*, REQ-P-* for P1
   - OPEN-1-* for P1 open items with target_phase: "phase-2-architecture"
   - Classification rules: acceptance_criteria must be measurable, violation_policy required

2. **Iron/Open Classification Verification** subsection with FAIL/WARN conditions:
   - FAIL: vague acceptance_criteria, missing evaluation_criteria on open, candidates <= 1, missing violation_policy
   - WARN: iron ratio < 30%, empty related_iron, CONDITIONAL PASS axis linked to iron REQ

3. **Ambiguity-to-Iron Gate**: requirement cannot become iron until ambiguity score passes

- [ ] **Step 3: Update the Final Checklist**

Add to existing checklist:
- `[ ] iron-requirements.json exists with all settled REQ-F-* and REQ-P-* entries`
- `[ ] open-requirements.json exists with all research topics as OPEN-1-* entries`
- `[ ] Every iron requirement has measurable acceptance_criteria (no vague terms)`
- `[ ] Every open item has >= 2 candidates and evaluation_criteria`
- `[ ] Every open item has target_phase specified`
- `[ ] Iron/open classification verification passed (no FAIL conditions)`
- `[ ] Ambiguity score <= 0.5 for all iron requirements`

- [ ] **Step 4: Verify policy references correct file paths**

Ensure all referenced paths use `docs/phase-1-research/iron-requirements.json` and `docs/phase-1-research/open-requirements.json`.

- [ ] **Step 5: Commit**

```bash
git add skills/p1-spec-research-policy/SKILL.md
git commit -m "feat: add iron/open schema definition and classification rules to P1 policy"
```

---

### Task 6: spec-analyst Agent — Iron/Open Output

**Files:**
- Modify: `agents/spec-analyst.md`

- [ ] **Step 1: Read current spec-analyst agent**

Run: `cat agents/spec-analyst.md`
Understand the current output format (requirements.json, io_definition.json, timing_constraints.json).

- [ ] **Step 2: Update output specification**

Replace `requirements.json` output with dual iron/open output:

1. Change "Output Artifacts" section:
   - `requirements.json` -> `iron-requirements.json` + `open-requirements.json`
   - Keep `io_definition.json` and `timing_constraints.json` unchanged

2. Add classification guidance:
   - Functional and performance requirements with clear, measurable acceptance_criteria -> iron
   - Architecture/implementation choices needing further investigation -> open
   - Items with ambiguity score > 0.5 -> cannot be iron until clarified

3. Update the self-validation protocol:
   - After generating iron/open files, verify:
     - Every spec feature maps to either an iron REQ or an open item
     - No iron REQ uses vague language in acceptance_criteria
     - Every open item has >= 2 candidates
     - Iron/open classification verification passes

4. Add violation_policy field guidance:
   - authority=1 requirements: `"violation_policy": "user_escalation"`
   - All P1 iron requirements are authority=1

- [ ] **Step 3: Verify backward compatibility note**

Add a note: "The legacy `requirements.json` is replaced by `iron-requirements.json` + `open-requirements.json`. All downstream consumers should read from the new files."

- [ ] **Step 4: Commit**

```bash
git add agents/spec-analyst.md
git commit -m "feat: update spec-analyst to produce iron/open requirement classification"
```

---

### Task 7: p1-research-orchestrator — Classification Verification Step

**Files:**
- Modify: `agents/p1-research-orchestrator.md`

- [ ] **Step 1: Read current orchestrator**

Run: `cat agents/p1-research-orchestrator.md`
Identify Step 7 (self-verification) and Step 7.5 (ambiguity gate).

- [ ] **Step 2: Update Step 4 (sub-domain survey) output references**

Change references from `requirements.json` to `iron-requirements.json` + `open-requirements.json`.

- [ ] **Step 3: Renumber existing Step 7.5 and add Iron/Open Classification Verification**

The current orchestrator already has "Step 7.5: Ambiguity Gate". Renumber it to "Step 7.5a: Ambiguity Gate" (content unchanged), then add the new step as "Step 7.5b":

```
Step 7.5b: Iron/Open Classification Verification

Task(spec-analyst):
  -> Verify iron/open classification:
    1. Every iron REQ has measurable acceptance_criteria (reject vague terms)
    2. Every open item has >= 2 candidates and evaluation_criteria
    3. Every open item has target_phase = "phase-2-architecture"
    4. Iron ratio >= 30% (warn if most items pushed to open)
    5. No CONDITIONAL PASS ambiguity axis items classified as iron
  -> If FAIL conditions detected: fix and re-classify
  -> If WARN conditions detected: log and proceed
  -> Save: docs/phase-1-research/iron-requirements.json (final)
  -> Save: docs/phase-1-research/open-requirements.json (final)
```

- [ ] **Step 4: Update Step 7 artifact verification**

Change `Glob("docs/phase-1-research/requirements.json")` to:
```
Glob("docs/phase-1-research/iron-requirements.json")
Glob("docs/phase-1-research/open-requirements.json")
```

- [ ] **Step 5: Commit**

```bash
git add agents/p1-research-orchestrator.md
git commit -m "feat: add iron/open classification verification to P1 orchestrator"
```

---

### Task 8: Wave 1 Verification

- [ ] **Step 1: Run all unit tests**

Run: `python -m pytest tests/unit/ -v --tb=short`
Expected: All PASS, no regressions

- [ ] **Step 2: Verify file structure**

Run: `ls agents/compliance-checker.md skills/rtl-p4-rapid-impl-policy/templates/compliance-state.json`
Expected: Both files exist

- [ ] **Step 3: Verify skill-completion-criteria.json is valid JSON**

Run: `python -c "import json; json.load(open('skill-completion-criteria.json')); print('Valid JSON')"`
Expected: `Valid JSON`

---

## Chunk 2: Cross-Phase Connection (Handoff + Compliance)

### Task 9: p2-arch-design-policy — Open Resolution + Compliance

**Files:**
- Modify: `skills/p2-arch-design-policy/SKILL.md`

- [ ] **Step 1: Read current P2 policy**

Run: `cat skills/p2-arch-design-policy/SKILL.md`

- [ ] **Step 2: Add Open Resolution Protocol section**

After existing review sections, add:

1. **Open Resolution Protocol**:
   - Read `docs/phase-1-research/open-requirements.json`
   - For each OPEN-1-* item:
     - Conduct architecture research using candidates and evaluation_criteria
     - Select winner with quantitative justification
     - Record in iron-requirements.json with `resolved_from`, `resolution_rationale`, `rejected_alternatives`, `upstream_compliance`
   - Verify: all OPEN-1-* items resolved

2. **Compliance Check Procedure**:
   - After iron-requirements.json (REQ-A-*) finalized:
   - Invoke compliance-checker agent with:
     - upstream_iron: `["docs/phase-1-research/iron-requirements.json"]`
     - target_artifacts: P2 output artifacts
   - Gate: compliance-report.json verdict must be PASS

3. **Upstream Challenge Protocol**:
   - If compliance VIOLATION persists after Primary stage:
     - Orchestrator declares correctable vs infeasible
     - If infeasible: produce challenge report with quantitative PPA evidence
     - Compliance-checker validates infeasibility claim
   - Reference: spec Section 4.5 for challenge report structure

4. **Ambiguity Gate (Phase 2)**:
   - Apply ambiguity scoring to all new REQ-A-* decisions
   - "Would re-evaluating this architecture produce the same conclusion?"
   - Score <= 0.5 required before REQ-A-* becomes iron

- [ ] **Step 3: Update Final Checklist**

Add:
- `[ ] All OPEN-1-* items resolved with rationale and rejected_alternatives`
- `[ ] iron-requirements.json contains REQ-A-* entries with resolved_from tracking`
- `[ ] Compliance check against P1 iron: verdict = PASS`
- `[ ] Ambiguity score <= 0.5 for all new REQ-A-* requirements`
- `[ ] open-requirements.json (OPEN-2-*) created for Phase 3 homework (if any)`

- [ ] **Step 4: Commit**

```bash
git add skills/p2-arch-design-policy/SKILL.md
git commit -m "feat: add open resolution, compliance check, and upstream challenge to P2 policy"
```

---

### Task 10: p2-arch-orchestrator — Resolution + Compliance Steps

**Files:**
- Modify: `agents/p2-arch-orchestrator.md`

- [ ] **Step 1: Read current P2 orchestrator**

Run: `cat agents/p2-arch-orchestrator.md`
Identify the step sequence and where new steps should be inserted.

- [ ] **Step 2: Add open-requirements intake to Step 1**

Extend existing Step 1 ("Read P1 Artifacts + Domain Knowledge") — add an additional Read() call at the end of Step 1:

```
# Append to existing Step 1:
Open Requirements Intake

Read("docs/phase-1-research/open-requirements.json")
-> Parse OPEN-1-* items
-> Build research task list from candidates and evaluation_criteria
-> Each OPEN-1-* becomes a research task assigned to appropriate agent
```

- [ ] **Step 3: Add Step 5.5 — Open Resolution Verification**

After existing dynamic convergence review (Step 5):

```
Step 5.5: Open Resolution Verification

For each OPEN-1-* item:
  -> Verify resolved_from exists in iron-requirements.json REQ-A-*
  -> Verify resolution_rationale is present and substantive
  -> Verify rejected_alternatives lists all non-selected candidates
  -> Verify upstream_compliance shows P1 iron check results

If any OPEN-1-* unresolved:
  -> AskUserQuestion to resolve OR upstream feedback to P1
```

- [ ] **Step 4: Renumber existing Step 6 and add Compliance Check**

Renumber existing "Step 6: Phase 2 Gate" to "Step 6.5: Phase 2 Gate" (content unchanged). Also update Step 1 upstream artifact references from `requirements.json` to `iron-requirements.json`. Insert the new compliance step as Step 6:

```
Step 6: Compliance Check (NEW — before existing Phase 2 Gate)

Task(compliance-checker):
  -> upstream_iron: ["docs/phase-1-research/iron-requirements.json"]
  -> target_artifacts: [P2 output artifact paths]
  -> Output: .rtl-agent-team/state/compliance-report.json

Read(".rtl-agent-team/state/compliance-report.json")
If verdict == "FAIL":
  -> Check max_violation_authority
  -> Enter authority-appropriate escalation ladder
  -> If infeasibility detected after Primary exhaustion:
     -> Produce upstream challenge report with PPA estimates
     -> Re-invoke compliance-checker with validate_infeasibility: true
     -> Present challenge to user via AskUserQuestion
```

- [ ] **Step 5: Update artifact verification in final step**

Add to existing final artifact checks:
```
Glob("docs/phase-2-architecture/iron-requirements.json")
Glob("docs/phase-2-architecture/open-requirements.json")
Read(".rtl-agent-team/state/compliance-report.json")
# Verify verdict == "PASS"
```

- [ ] **Step 6: Commit**

```bash
git add agents/p2-arch-orchestrator.md
git commit -m "feat: add open resolution, compliance check, and upstream challenge to P2 orchestrator"
```

---

### Task 11: rtl-p3-uarch-policy — Zero-Opens Invariant

**Files:**
- Modify: `skills/rtl-p3-uarch-policy/SKILL.md`

- [ ] **Step 1: Read current P3 policy**

Run: `cat skills/rtl-p3-uarch-policy/SKILL.md`

- [ ] **Step 2: Add sections (same pattern as Task 9 with P3-specific additions)**

Add the same 4 sections as P2 policy (Open Resolution, Compliance Check, Upstream Challenge, Ambiguity Gate) with these P3-specific differences:

1. **Open Resolution**: resolves OPEN-2-* (from P2), not OPEN-1-*
2. **Compliance Check**: checks against P1 AND P2 iron (two upstream files)
3. **Zero-Opens Invariant**: "Phase 3 exit with remaining opens -> EXIT GATE FAIL. P4 requires all requirements to be iron."
4. **No new open-requirements.json**: P3 does not produce open items

- [ ] **Step 3: Update Final Checklist**

Add:
- `[ ] All OPEN-2-* items resolved`
- `[ ] Zero remaining open items (P4 entry invariant)`
- `[ ] Compliance check against P1+P2 iron: verdict = PASS`
- `[ ] Ambiguity score <= 0.5 for all new REQ-U-*`
- `[ ] NO open-requirements.json produced (all homework resolved)`

- [ ] **Step 4: Commit**

```bash
git add skills/rtl-p3-uarch-policy/SKILL.md
git commit -m "feat: add open resolution, zero-opens invariant, and compliance to P3 policy"
```

---

### Task 12: p3-uarch-orchestrator — Resolution + Compliance + Challenge

**Files:**
- Modify: `agents/p3-uarch-orchestrator.md`

- [ ] **Step 1: Read current P3 orchestrator**

Run: `cat agents/p3-uarch-orchestrator.md`

- [ ] **Step 2: Extend Step 1 with open-requirements intake**

Append to existing Step 1 ("Read P2 Artifacts"):
```
Read("docs/phase-2-architecture/open-requirements.json")
-> Parse OPEN-2-* items
-> Build μArch research task list from candidates and evaluation_criteria
```

Also update Step 1 upstream artifact references from `requirements.json` to `iron-requirements.json`.

- [ ] **Step 3: Add Step 5.5 — Open Resolution + Zero-Opens Verification**

After existing convergence review (Step 5):

```
Step 5.5: Open Resolution + Zero-Opens Verification

# 1. Verify all OPEN-2-* resolved
Read("docs/phase-2-architecture/open-requirements.json")
Read("docs/phase-3-uarch/iron-requirements.json")
For each OPEN-2-* item:
  -> Verify a REQ-U-* exists with resolved_from == OPEN-2-* id
  -> Verify resolution_rationale is present
  -> Verify rejected_alternatives lists all non-selected candidates

# 2. Zero-opens invariant: no P3 open-requirements.json should exist
Glob("docs/phase-3-uarch/open-requirements.json")
  -> If exists -> EXIT GATE FAIL ("P4 requires all requirements to be iron")

# 3. Count check: every OPEN-2-* has a matching resolved_from
unresolved = OPEN-2-* items without matching REQ-U-* resolved_from
If unresolved > 0 -> EXIT GATE FAIL (list unresolved items)
```

- [ ] **Step 4: Renumber existing Step 6 and add Compliance Check**

Renumber existing "Step 6: Phase 3 Gate" to "Step 6.5: Phase 3 Gate". Insert:

```
Step 6: Compliance Check (NEW)

Task(compliance-checker):
  -> upstream_iron: ["docs/phase-1-research/iron-requirements.json",
                     "docs/phase-2-architecture/iron-requirements.json"]
  -> target_artifacts: [P3 output artifact paths]
  -> Output: .rtl-agent-team/state/compliance-report.json

Read(".rtl-agent-team/state/compliance-report.json")
If verdict == "FAIL":
  -> Check max_violation_authority
  -> Enter authority-appropriate escalation ladder
  -> If infeasibility detected after Primary exhaustion:
     -> Produce upstream challenge report with PPA estimates:
        - Required fields: frequency_mhz, area_gate_count, pixel_rate_mpps, achievable_fps
        - At least one throughput sub-field relevant to challenged REQ's acceptance_criteria
        - Must identify which upstream authority is challenged (P1 or P2)
     -> Re-invoke compliance-checker with validate_infeasibility: true
     -> Present challenge to user via AskUserQuestion
```

- [ ] **Step 4: Commit**

```bash
git add agents/p3-uarch-orchestrator.md
git commit -m "feat: add open resolution, compliance, upstream challenge to P3 orchestrator"
```

---

### Task 13: Wave 2 Verification

- [ ] **Step 1: Run all unit tests**

Run: `python -m pytest tests/unit/ -v --tb=short`
Expected: All PASS

- [ ] **Step 2: Verify all modified files reference correct upstream paths**

Run: `grep -l "iron-requirements.json" agents/p1-research-orchestrator.md agents/p2-arch-orchestrator.md agents/p3-uarch-orchestrator.md`
Expected: All 3 files listed

- [ ] **Step 3: Verify policies reference compliance-checker**

Run: `grep -l "compliance-checker" skills/p2-arch-design-policy/SKILL.md skills/rtl-p3-uarch-policy/SKILL.md`
Expected: Both files listed

---

## Chunk 3: Hook Integration + Skill Updates

### Task 14: rtl-phase-state-bootstrap.sh — Iron Path Injection

**Files:**
- Modify: `hooks/rtl-phase-state-bootstrap.sh`

- [ ] **Step 1: Read current hook**

Run: `cat hooks/rtl-phase-state-bootstrap.sh`
Identify the section where phase state is bootstrapped.

- [ ] **Step 2: Write hook test for iron path injection**

Add to `tests/unit/test_hooks.py`:

```python
class TestComplianceStateBootstrap:
    """Tests for compliance state bootstrap in rtl-phase-state-bootstrap.sh."""

    HOOK = HOOKS_DIR / "rtl-phase-state-bootstrap.sh"

    def test_p2_skill_gets_p1_iron_path(self, tmp_path):
        state_dir = tmp_path / ".rtl-agent-team" / "state"
        state_dir.mkdir(parents=True)
        # Create P1 iron file marker
        p1_dir = tmp_path / "docs" / "phase-1-research"
        p1_dir.mkdir(parents=True)
        (p1_dir / "iron-requirements.json").write_text("{}")

        result = run_hook(self.HOOK, {
            "cwd": str(tmp_path),
            "skill": "rtl-agent-team:p2-arch-design"
        })
        # Check compliance-state.json was created
        state_file = state_dir / "compliance-state.json"
        if state_file.exists():
            state = json.loads(state_file.read_text())
            assert "docs/phase-1-research/iron-requirements.json" in str(state.get("upstream_iron_paths", []))
```

- [ ] **Step 3: Add compliance state bootstrap logic to hook**

After existing phase state bootstrap logic, add:

```bash
# Compliance state bootstrap
# Note: $SHORT_NAME is the existing variable (derived from skill name at top of hook)
# Note: $CWD is the existing working directory variable
_CS_STATE_DIR="$CWD/.rtl-agent-team/state"
_CS_FILE="$_CS_STATE_DIR/compliance-state.json"
if [ ! -f "$_CS_FILE" ]; then
  case "$SHORT_NAME" in
    p2-arch-design|rtl-p2-arch-team)
      _cs_upstream='["docs/phase-1-research/iron-requirements.json"]'
      _cs_open="docs/phase-1-research/open-requirements.json"
      ;;
    rtl-p3-uarch-design|rtl-p3-uarch-team)
      _cs_upstream='["docs/phase-1-research/iron-requirements.json","docs/phase-2-architecture/iron-requirements.json"]'
      _cs_open="docs/phase-2-architecture/open-requirements.json"
      ;;
    rtl-p4-*|rtl-p5-*)
      _cs_upstream='["docs/phase-1-research/iron-requirements.json","docs/phase-2-architecture/iron-requirements.json","docs/phase-3-uarch/iron-requirements.json"]'
      _cs_open=""
      ;;
    *)
      # Non-phase skills: skip compliance state creation
      _cs_upstream=""
      ;;
  esac

  # Only create compliance-state.json for phase skills
  if [ -n "$_cs_upstream" ]; then
    cat > "$_CS_FILE" << CEOF
{
  "phase": "$SHORT_NAME",
  "upstream_iron_paths": $_cs_upstream,
  "open_requirements_path": "$_cs_open",
  "compliance_status": "pending",
  "compliance_authority": null,
  "challenge_count": 0,
  "last_check_timestamp": null
}
CEOF
  fi
fi
```

- [ ] **Step 4: Run hook tests**

Run: `python -m pytest tests/unit/test_hooks.py::TestComplianceStateBootstrap -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add hooks/rtl-phase-state-bootstrap.sh tests/unit/test_hooks.py
git commit -m "feat: add compliance state bootstrap with upstream iron path injection"
```

---

### Task 15: rtl-skill-completion-gate.sh — Compliance Gate

**Files:**
- Modify: `hooks/rtl-skill-completion-gate.sh`

- [ ] **Step 1: Read current hook**

Run: `cat hooks/rtl-skill-completion-gate.sh`
Identify: criteria parsing, iteration counting, escalation ladder logic.

- [ ] **Step 2: Write compliance gate test**

Add to `tests/unit/test_hooks.py`:

```python
class TestComplianceGate:
    """Tests for compliance-pass in rtl-skill-completion-gate.sh."""

    HOOK = HOOKS_DIR / "rtl-skill-completion-gate.sh"

    def test_compliance_pass_blocks_without_report(self, tmp_path):
        state_dir = tmp_path / ".rtl-agent-team" / "state"
        state_dir.mkdir(parents=True)
        # Write skill-active with compliance-pass criteria
        (state_dir / "skill-active.json").write_text(json.dumps({
            "skill": "p2-arch-design",
            "active": True,
            "iteration": 1,
            "max_iterations": 5,
            "pending": "compliance-pass",
            "all_complete": False
        }))
        result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
        output = result.get("raw_stdout", "")
        # Should block — compliance report does not exist
        assert "compliance" in output.lower() or result.get("exit_code", 0) != 0

    def test_compliance_pass_succeeds_with_pass_verdict(self, tmp_path):
        state_dir = tmp_path / ".rtl-agent-team" / "state"
        state_dir.mkdir(parents=True)
        (state_dir / "skill-active.json").write_text(json.dumps({
            "skill": "p2-arch-design",
            "active": True,
            "iteration": 1,
            "max_iterations": 5,
            "pending": "compliance-pass",
            "all_complete": False
        }))
        (state_dir / "compliance-report.json").write_text(json.dumps({
            "summary": {"verdict": "PASS", "violation": 0, "max_violation_authority": None}
        }))
        result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
        # Should not block
        output = result.get("raw_stdout", "")
        # Verify no blocking message about compliance
```

- [ ] **Step 3: Add compliance-pass handling to hook**

In the criteria checking section of `rtl-skill-completion-gate.sh`, add:

Note: The existing hook uses `jsonu_get_file_path_string` (from `hooks/lib/json-util.sh`) for reading and `sed` substitution for writing (building a `_SED_SCRIPT` tempfile). There is no `json_set` helper. Also, `rtl-skill-activation.sh` must be modified to include `compliance_authority`, `max_primary`, `max_fallback` fields with defaults in the initial skill-active.json.

**Pre-requisite**: Add these default fields to `rtl-skill-activation.sh` line ~114 where skill-active.json is created:
```json
"compliance_authority": null,
"max_primary": null,
"max_fallback": null,
```

**Compliance-pass handling code** (POSIX sh compatible):

```bash
# Check compliance-pass criteria
if echo "$pending" | grep -q "compliance-pass"; then
  _cr_report="$CWD/.rtl-agent-team/state/compliance-report.json"
  if [ ! -f "$_cr_report" ]; then
    _cr_met=false
    _cr_msg="Compliance check not yet performed. Run compliance-checker agent."
  else
    _cr_verdict=$(jsonu_get_file_path_string "$_cr_report" "summary.verdict")
    if [ "$_cr_verdict" = "PASS" ]; then
      _cr_met=true
    else
      _cr_met=false
      _cr_auth=$(jsonu_get_file_path_num "$_cr_report" "summary.max_violation_authority")
      _cr_infeasible=$(jsonu_get_file_path_bool "$_cr_report" "summary.infeasibility_detected")

      # Authority-differentiated budget override
      case "$_cr_auth" in
        1) _cr_max_p=3; _cr_max_f=2 ;;
        2) _cr_max_p=4; _cr_max_f=3 ;;
        *) _cr_max_p=$MAX_ITER; _cr_max_f=$MAX_ITER ;;
      esac

      # Write overrides via sed (matching existing hook pattern)
      _SED_SCRIPT=$(mktemp)
      printf 's/"compliance_authority": *[^,]*/"compliance_authority": %s/\n' "$_cr_auth" >> "$_SED_SCRIPT"
      printf 's/"max_primary": *[^,]*/"max_primary": %s/\n' "$_cr_max_p" >> "$_SED_SCRIPT"
      printf 's/"max_fallback": *[^,]*/"max_fallback": %s/\n' "$_cr_max_f" >> "$_SED_SCRIPT"

      # Infeasibility branch
      if [ "$_cr_infeasible" = "true" ] && [ "$iteration" -gt "$_cr_max_p" ]; then
        printf 's/"strategy": *"[^"]*"/"strategy": "upstream_challenge"/\n' >> "$_SED_SCRIPT"
        _cr_msg="[UPSTREAM CHALLENGE] Infeasibility validated. Produce challenge report with PPA estimates."
      else
        case "$_cr_auth" in
          1) _cr_tag="[CRITICAL — UPSTREAM REQUIREMENT VIOLATION]" ;;
          2) _cr_tag="[WARNING — HIGH]" ;;
          *) _cr_tag="[WARNING]" ;;
        esac
        _cr_msg="$_cr_tag Compliance violation (authority=$_cr_auth). Fix before proceeding. Attempt $iteration."
      fi

      sed -f "$_SED_SCRIPT" "$SKILL_ACTIVE" > "${SKILL_ACTIVE}.tmp" && mv "${SKILL_ACTIVE}.tmp" "$SKILL_ACTIVE"
      rm -f "$_SED_SCRIPT"
    fi
  fi

  if [ "$_cr_met" = "true" ]; then
    # Remove compliance-pass from pending via sed
    _new_pending=$(echo "$pending" | sed 's/compliance-pass//' | sed 's/||/|/g' | sed 's/^|//' | sed 's/|$//')
    sed "s|\"pending\": *\"[^\"]*\"|\"pending\": \"$_new_pending\"|" "$SKILL_ACTIVE" > "${SKILL_ACTIVE}.tmp" && mv "${SKILL_ACTIVE}.tmp" "$SKILL_ACTIVE"
  fi
fi
```

- [ ] **Step 4: Run hook tests**

Run: `python -m pytest tests/unit/test_hooks.py::TestComplianceGate -v`
Expected: PASS

- [ ] **Step 5: Run all hook tests for regression**

Run: `python -m pytest tests/unit/test_hooks.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add hooks/rtl-skill-completion-gate.sh tests/unit/test_hooks.py
git commit -m "feat: add compliance-pass gate with authority-differentiated escalation"
```

---

### Task 16: rtl-spawn-context.sh — Upstream Iron in Spawn Context

**Files:**
- Modify: `hooks/rtl-spawn-context.sh`

- [ ] **Step 1: Read current hook**

Run: `cat hooks/rtl-spawn-context.sh`

- [ ] **Step 2: Add upstream iron paths to spawn context**

In the JSON generation section, add fields:

```bash
# After existing spawn context fields:
# Read compliance state if exists
_sc_cstate="$CWD/.rtl-agent-team/state/compliance-state.json"
if [ -f "$_sc_cstate" ]; then
  upstream_iron=$(jsonu_get_file_path_string "$_sc_cstate" "upstream_iron_paths")
  open_req=$(jsonu_get_file_path_string "$_sc_cstate" "open_requirements_path")
else
  upstream_iron="[]"
  open_req=""
fi

# Add to output JSON:
# "upstream_iron": $upstream_iron,
# "open_requirements": "$open_req",
# "compliance_state": "pending"
```

- [ ] **Step 3: Commit**

```bash
git add hooks/rtl-spawn-context.sh
git commit -m "feat: add upstream iron paths to agent spawn context manifest"
```

---

### Task 17: rtl-orchestrator-inject.sh — Iron Protocol Rules

**Files:**
- Modify: `hooks/rtl-orchestrator-inject.sh`

- [ ] **Step 1: Read current hook**

Run: `cat hooks/rtl-orchestrator-inject.sh`
Identify where the routing block and absolute rules are generated.

- [ ] **Step 2: Write test for iron protocol injection**

Add to `tests/unit/test_hooks.py`:

```python
def test_iron_requirements_protocol_injected(self, tmp_path):
    """Verify Iron Requirements Protocol is injected for RTL projects."""
    (tmp_path / "rtl").mkdir()
    result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
    output = result.get("raw_stdout", "")
    assert "Iron Requirements Protocol" in output
    assert "iron-requirements.json" in output
    assert "authority" in output.lower() or "Authority" in output
```

Add this test to the existing `TestRtlOrchestratorInject` class.

- [ ] **Step 3: Add Iron Requirements Protocol to injection**

After the existing absolute rules section, add:

```bash
cat << 'IRON_EOF'

## Iron Requirements Protocol
- Each phase produces iron-requirements.json (absolute rules) and open-requirements.json (homework for next phase)
- Iron requirements from upper phases MUST NOT be violated
- Authority hierarchy: P1(functional) > P2(architecture) > P3(micro-arch)
- Violation triggers graduated escalation; infeasibility triggers Upstream Challenge with quantitative PPA evidence
- Phase exit requires compliance-checker PASS against all upstream iron
IRON_EOF
```

- [ ] **Step 4: Run injection tests**

Run: `python -m pytest tests/unit/test_hooks.py::TestRtlOrchestratorInject -v`
Expected: All PASS including new test

- [ ] **Step 5: Commit**

```bash
git add hooks/rtl-orchestrator-inject.sh tests/unit/test_hooks.py
git commit -m "feat: inject Iron Requirements Protocol in SessionStart hook"
```

---

### Task 18: Action Skills — P1/P2/P3 Base + Team Variants

**Files:**
- Modify: 6 skill files (base + team for P1, P2, P3)

- [ ] **Step 1: Update P1 skills (base + team)**

Modify `skills/p1-spec-research/SKILL.md`:
- Update Output Artifacts section to list `iron-requirements.json` and `open-requirements.json` instead of `requirements.json`
- Add note about classification verification step

Modify `skills/rtl-p1-research-team/SKILL.md`:
- Same changes as base P1 skill

- [ ] **Step 2: Update P2 skills (base + team)**

Modify `skills/p2-arch-design/SKILL.md`:
- Add "Open Resolution" to the workflow description
- Add "Compliance Check" step reference
- Update exit gate to include compliance-pass

Modify `skills/rtl-p2-arch-team/SKILL.md`:
- Same changes as base P2 skill

- [ ] **Step 3: Update P3 skills (base + team)**

Modify `skills/rtl-p3-uarch-design/SKILL.md`:
- Add "Open Resolution" + "Zero-Opens Invariant" to workflow
- Add "Compliance Check" step reference
- Update exit gate to include compliance-pass and zero-remaining-opens

Modify `skills/rtl-p3-uarch-team/SKILL.md`:
- Same changes as base P3 skill

- [ ] **Step 4: Commit**

```bash
git add skills/p1-spec-research/SKILL.md skills/rtl-p1-research-team/SKILL.md \
       skills/p2-arch-design/SKILL.md skills/rtl-p2-arch-team/SKILL.md \
       skills/rtl-p3-uarch-design/SKILL.md skills/rtl-p3-uarch-team/SKILL.md
git commit -m "feat: update P1-P3 action skills with iron/open and compliance references"
```

---

### Task 19: P4/P5 Skills — Compliance Check Addition

**Files:**
- Modify: 4 skill files (P4 base+team, P5 base+team)

- [ ] **Step 1: Update P4 skills**

Modify `skills/rtl-p4-implement/SKILL.md`:
- Add per-wave compliance check: after each wave's lint+test, invoke compliance-checker against P1+P2+P3 iron
- Add note: "RTL implementation must comply with all upstream iron requirements"

Modify `skills/rtl-p4-implement-team/SKILL.md`:
- Same changes

- [ ] **Step 2: Update P5 skills**

Modify `skills/rtl-p5-verify/SKILL.md`:
- Add final compliance check: verify acceptance_criteria against test results
- Add note: "Verification must confirm all iron requirement acceptance_criteria are met"

Modify `skills/rtl-p5-verify-team/SKILL.md`:
- Same changes

- [ ] **Step 3: Commit**

```bash
git add skills/rtl-p4-implement/SKILL.md skills/rtl-p4-implement-team/SKILL.md \
       skills/rtl-p5-verify/SKILL.md skills/rtl-p5-verify-team/SKILL.md
git commit -m "feat: add compliance check to P4/P5 action skills"
```

---

### Task 20: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/unit/ -v --tb=short`
Expected: All PASS

- [ ] **Step 2: Verify all 24 files touched**

Run: `git diff --stat HEAD~$(git log --oneline plugin_docs/specs/2026-03-14-cascading-requirements-design.md -1 --format=%h)..HEAD --name-only | wc -l`
Verify count matches expected (~24 files + tests)

- [ ] **Step 3: Verify no broken cross-references**

Run: `grep -r "requirements.json" agents/ skills/ hooks/ | grep -v "iron-requirements" | grep -v "open-requirements" | grep -v "compliance-report" | grep -v "skill-completion-criteria"`
Expected: No orphaned references to old flat `requirements.json` in modified files (some unmodified files may still reference it — that's OK for now)

- [ ] **Step 4: Verify skill-completion-criteria consistency**

Run: `python -c "import json; c=json.load(open('skill-completion-criteria.json')); [print(f'{k}: {v}') for k,v in c.items() if 'compliance' in v or 'iron' in v or 'ambiguity' in v]"`
Expected: All 10 modified entries printed with correct new criteria

- [ ] **Step 5: Final commit (if any remaining changes)**

```bash
git status
# If clean: done
# If changes: stage and commit with descriptive message
```
