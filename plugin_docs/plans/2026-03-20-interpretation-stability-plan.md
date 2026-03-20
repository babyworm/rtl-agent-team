# Interpretation Stability Framework — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an adversarial reinterpretation quality gate to Phase 1 spec analysis (Steps 7.6-7.9 in p1-research-orchestrator).

**Architecture:** Adversarial agent challenges initial spec-analyst output. User resolves genuine ambiguities. Gate passes when all HIGH challenges are resolved and resolution_ratio ≥ 0.8. stability_check.py produces an informational audit report (not the gate).

**Tech Stack:** Python 3.10+ (stdlib only), SKILL.md prompts, agent .md prompts.

**Spec:** `plugin_docs/specs/2026-03-20-convergence-quality-framework.md`

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Create | `scripts/stability_check.py` | Deterministic content-based alignment + stability report |
| Create | `skills/p1-spec-research/templates/stability-report.md` | Report template |
| Create | `skills/p1-spec-research/templates/challenge-report-schema.json` | Challenge report JSON schema |
| Modify | `agents/p1-research-orchestrator.md` | Insert Steps 7.6-7.9 |
| Modify | `skills/p1-spec-research-policy/SKILL.md` | Add adversarial gate policy |
| Create | `tests/unit/test_stability_check.py` | Unit tests for stability_check.py |

---

### Task 1: stability_check.py — Core Algorithm

**Files:**
- Create: `scripts/stability_check.py`
- Create: `tests/unit/test_stability_check.py`

- [ ] **Step 1: Write test fixtures**

Create test data files for the test:

```python
# tests/unit/test_stability_check.py
"""Unit tests for stability_check.py — content-based requirement alignment."""
import json
import pytest
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from stability_check import tokenize, jaccard, align_requirements, compute_pair_similarity


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
        r1 = {"source": {"section": "3.2"}, "description": "data width 8 bit",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": ["width == 8"]}
        r2 = {"source": {"section": "5.1"}, "description": "data width 8 bit",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": ["width == 8"]}
        sim = compute_pair_similarity(r1, r2)
        assert sim < 0.9  # section mismatch reduces score

    def test_empty_fields(self):
        r1 = {"description": "test", "source": {}}
        r2 = {"description": "test", "source": {}}
        sim = compute_pair_similarity(r1, r2)
        assert 0.0 <= sim <= 1.0


class TestAlignRequirements:
    def test_identical_lists(self):
        reqs = [
            {"id": "REQ-F-001", "source": {"section": "3.1", "line": 5},
             "description": "FIFO depth 16", "type": "functional",
             "priority": "must", "complexity": "low",
             "acceptance_criteria": ["depth == 16"]},
            {"id": "REQ-F-002", "source": {"section": "3.2", "line": 20},
             "description": "Output latency 4 cycles", "type": "performance",
             "priority": "must", "complexity": "medium",
             "acceptance_criteria": ["latency <= 4"]},
        ]
        aligned, v1_only, v2_only = align_requirements(reqs, reqs)
        assert len(aligned) == 2
        assert len(v1_only) == 0
        assert len(v2_only) == 0

    def test_empty_v1(self):
        aligned, v1_only, v2_only = align_requirements([], [{"id": "R1", "source": {"section": "1"}, "description": "x"}])
        assert len(aligned) == 0
        assert len(v2_only) == 1

    def test_empty_both(self):
        aligned, v1_only, v2_only = align_requirements([], [])
        assert len(aligned) == 0

    def test_no_section_falls_to_pass2(self):
        v1 = [{"id": "R1", "source": {}, "description": "FIFO depth 16 entries",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": ["depth == 16"]}]
        v2 = [{"id": "R2", "source": {}, "description": "FIFO depth sixteen entries",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": ["depth == 16"]}]
        aligned, v1_only, v2_only = align_requirements(v1, v2)
        assert len(aligned) == 1  # matched by description similarity

    def test_v1_expansion_after_clarification(self):
        """v1 has 3 reqs, v2 has 5 (clarification split some)."""
        v1 = [{"id": f"R{i}", "source": {"section": f"{i}.0"}, "description": f"feature {i}",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": [f"test {i}"]} for i in range(3)]
        v2 = [{"id": f"R{i}", "source": {"section": f"{i}.0"}, "description": f"feature {i}",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": [f"test {i}"]} for i in range(3)]
        # Add 2 new reqs in v2 from new sections
        v2.append({"id": "R3", "source": {"section": "3.1"}, "description": "new feature A",
                    "type": "functional", "priority": "should", "complexity": "medium",
                    "acceptance_criteria": ["test A"]})
        v2.append({"id": "R4", "source": {"section": "3.2"}, "description": "new feature B",
                    "type": "functional", "priority": "should", "complexity": "medium",
                    "acceptance_criteria": ["test B"]})
        aligned, v1_only, v2_only = align_requirements(v1, v2)
        assert len(aligned) == 3
        assert len(v1_only) == 0
        assert len(v2_only) == 2

    def test_pass2_does_not_leave_stale_v1_unmatched(self):
        """Regression: v1_still_unmatched must exclude Pass 2 matches."""
        v1 = [{"id": "R1", "source": {}, "description": "alpha beta gamma",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": []}]
        v2 = [{"id": "R2", "source": {}, "description": "alpha beta gamma delta",
               "type": "functional", "priority": "must", "complexity": "low",
               "acceptance_criteria": []}]
        aligned, v1_only, v2_only = align_requirements(v1, v2)
        assert len(aligned) == 1
        assert len(v1_only) == 0  # must NOT contain R1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/unit/test_stability_check.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'stability_check'`

- [ ] **Step 3: Implement stability_check.py**

Copy the fully specified algorithm from spec §6 into `scripts/stability_check.py`.
Add CLI entry point:

```python
#!/usr/bin/env python3
"""stability_check.py — Content-based requirement alignment and stability report.

Compares two iron-requirements.json files (v1 vs v2) and produces a
stability report documenting what changed after adversarial clarification.

Usage:
    python3 scripts/stability_check.py v1.json v2.json [-o report.md]

This is an INFORMATIONAL audit tool, not a gate.
The adversarial gate uses the challenge report directly.
"""
# ... [full algorithm from spec §6] ...

def generate_report(aligned, v1_only, v2_only, v1_path, v2_path):
    """Generate stability-report.md content."""
    # ... [template from spec §6 output format] ...

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Requirement alignment and stability report")
    parser.add_argument("v1", help="Initial iron-requirements.json (v1)")
    parser.add_argument("v2", help="Post-clarification iron-requirements.json (v2)")
    parser.add_argument("-o", "--output", default=None, help="Output report path (.md)")
    args = parser.parse_args()
    # ... load, align, report ...

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/unit/test_stability_check.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full CI test suite**

Run: `python3 -m pytest tests/unit/ -x -q`
Expected: ALL PASS (no regression)

- [ ] **Step 6: Commit**

```bash
git add scripts/stability_check.py tests/unit/test_stability_check.py
git commit -m "feat: add stability_check.py — content-based requirement alignment

Deterministic Python script (stdlib only) for comparing two
iron-requirements.json files. Uses source.section + line proximity
alignment with Jaccard fallback. Produces stability-report.md.
Part of Interpretation Stability Framework (MVP Phase 1)."
```

---

### Task 2: Stability Report Template + Challenge Report Schema

**Files:**
- Create: `skills/p1-spec-research/templates/stability-report.md`
- Create: `skills/p1-spec-research/templates/challenge-report-schema.json`

- [ ] **Step 1: Create templates directory if needed**

Run: `mkdir -p skills/p1-spec-research/templates`

- [ ] **Step 2: Write stability-report.md template**

Copy template from spec §6 output format section.

- [ ] **Step 3: Write challenge-report-schema.json**

Define the JSON schema matching spec §3 adversarial prompt output format:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "required": ["challenges", "unchallenged_count", "challenged_count"],
  "properties": {
    "challenges": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["target_source", "original_interpretation", "alternative_interpretation", "spec_evidence", "impact", "severity"],
        "properties": {
          "target_source": {"type": "object", "properties": {"document": {"type": "string"}, "section": {"type": "string"}}},
          "severity": {"enum": ["HIGH", "MEDIUM", "LOW"]},
          "resolution": {"enum": ["RESOLVED", "DOCUMENTED", "NOT_GENUINE", null]}
        }
      }
    },
    "unchallenged_count": {"type": "integer", "minimum": 0},
    "challenged_count": {"type": "integer", "minimum": 0}
  }
}
```

- [ ] **Step 4: Commit**

```bash
git add skills/p1-spec-research/templates/
git commit -m "feat: add stability-report template and challenge-report schema

Part of Interpretation Stability Framework (MVP Phase 1)."
```

---

### Task 3: Adversarial Gate Policy

**Files:**
- Modify: `skills/p1-spec-research-policy/SKILL.md` (after line ~117, existing WARN conditions)

- [ ] **Step 1: Read current policy to find insertion point**

Run: `grep -n 'WARN conditions\|Ambiguity.*Gate\|Final Checklist' skills/p1-spec-research-policy/SKILL.md`

- [ ] **Step 2: Add adversarial gate section to policy**

Insert after the existing "Iron/Open Classification Verification" section:

```markdown
## Adversarial Interpretation Gate (Step 7.6-7.9)

After iron/open classification verification passes, run adversarial reinterpretation:

1. **Step 7.6**: Spawn adversarial spec-analyst (separate Task, clean context) to challenge
   iron-requirements.json. Output: challenge-report.json in scratch.
2. **Step 7.7**: Present HIGH challenges to user (AskUserQuestion). MEDIUM batched if >10.
   LOW auto-documented. User may mark challenges as NOT_GENUINE.
3. **Step 7.8**: Re-run spec-analyst with original spec + clarifications → all 4 canonical artifacts.
4. **Step 7.9**: Gate check:

```
genuine = (HIGH + MEDIUM) - NOT_GENUINE
resolved = RESOLVED + DOCUMENTED
resolution_ratio = resolved / genuine   (if genuine == 0: pass)
gate_pass = (all HIGH resolved) AND (resolution_ratio ≥ 0.8)
```

**Gate failure**: list unresolved HIGH challenges, loop back to Step 7.7 (max 1 re-loop).
After 2nd failure: escalate to user with full divergence report.

### Dual Gate Arbitration

| Ambiguity Score | Adversarial Gate | Decision |
|-----------------|-----------------|----------|
| PASS (≤0.3) | PASS | Proceed |
| PASS (≤0.3) | FAIL | BLOCK |
| CONDITIONAL (0.3-0.5) | PASS | Proceed with WARNING |
| BLOCK (>0.5) | PASS | BLOCK |
| BLOCK (>0.5) | FAIL | BLOCK |

Rule: Either gate can block; neither can unblock the other.

### Pathological Patterns
- Zero challenges on >15 requirements: re-run with stronger adversarial framing
- >50% items at HIGH severity: spec fundamentally under-specified, escalate
- Challenge budget: max 30 per adversarial pass

### Checklist Addition
- [ ] Adversarial reinterpretation completed (Step 7.6)?
- [ ] All HIGH challenges resolved or escalated?
- [ ] resolution_ratio ≥ 0.8?
- [ ] stability-report.md saved to reviews/phase-1-research/?
```

- [ ] **Step 3: Run tests to check no regression**

Run: `python3 -m pytest tests/unit/ -x -q`

- [ ] **Step 4: Commit**

```bash
git add skills/p1-spec-research-policy/SKILL.md
git commit -m "feat: add adversarial gate policy to p1-spec-research-policy

Dual gate: ambiguity score + adversarial challenge report.
Either can block, neither can unblock the other.
Part of Interpretation Stability Framework (MVP Phase 1)."
```

---

### Task 4: Orchestrator Integration (Steps 7.6-7.9)

**Files:**
- Modify: `agents/p1-research-orchestrator.md` (after Step 7.5b, before Step 8)

- [ ] **Step 1: Read orchestrator to find insertion point**

Run: `grep -n 'Step 7.5b\|Step 8:' agents/p1-research-orchestrator.md`

- [ ] **Step 2: Insert Steps 7.6-7.9**

After Step 7.5b block, before Step 8, insert:

```markdown
## Step 7.6: Adversarial Reinterpretation

Spawn a separate spec-analyst subagent with adversarial prompt to challenge
the iron-requirements.json produced in Step 7.

```
# Save v1 to scratch for stability report
Bash: mkdir -p .rtl-agent-team/scratch/stability/phase-1
Bash: cp docs/phase-1-research/iron-requirements.json .rtl-agent-team/scratch/stability/phase-1/output-v1.json

Task(subagent_type="rtl-agent-team:spec-analyst",
     prompt="ADVERSARIAL REINTERPRETATION MODE.
     You are NOT extracting requirements. You are CHALLENGING an existing extraction.
     Read the original spec and the iron-requirements.json below.
     For each requirement, find ALTERNATIVE VALID interpretations that differ.
     Reference items by source.section (NOT requirement ID).
     Severity: HIGH = different RTL behavior, MEDIUM = different parameters, LOW = cosmetic.
     Output JSON challenge report to .rtl-agent-team/scratch/stability/phase-1/challenge-report.json
     using the schema in skills/p1-spec-research/templates/challenge-report-schema.json.
     Max 30 challenges, ranked by severity.")
```

## Step 7.7: User Resolution

```
Read(".rtl-agent-team/scratch/stability/phase-1/challenge-report.json")
# For each HIGH challenge: AskUserQuestion with both interpretations
# For MEDIUM (if ≤10): AskUserQuestion batched
# For MEDIUM (if >10): present summary, ask "review these assumptions?"
# For LOW: auto-document as assumptions
# User may mark any challenge as NOT_GENUINE
# Accumulate clarifications for Step 7.8
```

## Step 7.8: Re-run with Clarifications

```
Task(subagent_type="rtl-agent-team:spec-analyst",
     prompt="Re-analyze the specification with the following clarifications from user review:
     {accumulated_clarifications}
     Produce all 4 canonical artifacts:
     - docs/phase-1-research/iron-requirements.json
     - docs/phase-1-research/open-requirements.json
     - docs/phase-1-research/io_definition.json
     - docs/phase-1-research/timing_constraints.json
     Include self-validation.")
```

## Step 7.9: Adversarial Gate Check

```
Read(".rtl-agent-team/scratch/stability/phase-1/challenge-report.json")
# Compute gate:
#   genuine = (HIGH + MEDIUM) - NOT_GENUINE
#   resolved = RESOLVED + DOCUMENTED
#   resolution_ratio = resolved / genuine (if genuine == 0: pass)
#   gate_pass = (all HIGH resolved) AND (resolution_ratio ≥ 0.8)
#
# If FAIL: loop back to Step 7.7 (max 1 re-loop)
# If PASS: run stability_check.py for audit report
Bash: python3 scripts/stability_check.py \
  .rtl-agent-team/scratch/stability/phase-1/output-v1.json \
  docs/phase-1-research/iron-requirements.json \
  -o reviews/phase-1-research/stability-report.md
# Proceed to Step 8
```
```

- [ ] **Step 3: Run tests to check no regression**

Run: `python3 -m pytest tests/unit/ -x -q`

- [ ] **Step 4: Commit**

```bash
git add agents/p1-research-orchestrator.md
git commit -m "feat: add Steps 7.6-7.9 adversarial reinterpretation to P1 orchestrator

Step 7.6: Adversarial spec-analyst challenges iron-requirements.json
Step 7.7: User resolves HIGH/MEDIUM challenges
Step 7.8: Re-run spec-analyst with clarifications (all 4 artifacts)
Step 7.9: Gate check + stability_check.py audit report
Part of Interpretation Stability Framework (MVP Phase 1)."
```

---

### Task 5: Final Integration + CI Verification

**Files:**
- Verify: all modified files
- Modify: `skill-completion-criteria.json` (add adversarial-pass if needed)

- [ ] **Step 1: Run full CI test suite**

Run: `python3 -m pytest tests/unit/ -x -q`

- [ ] **Step 2: Run shellcheck**

Run: `shellcheck -s sh hooks/*.sh hooks/lib/*.sh`

- [ ] **Step 3: Verify stability_check.py runs standalone**

Run: `python3 scripts/stability_check.py --help`

- [ ] **Step 4: Verify skill count unchanged (93)**

Run: `ls -d skills/*/SKILL.md | wc -l`
Expected: 93 (no new skills added, only templates)

- [ ] **Step 5: Run sync script**

Run: `bash scripts/sync_orchestrator_inject.sh`

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: final integration verification for Interpretation Stability Framework"
```

- [ ] **Step 7: Push**

```bash
git push origin main
```
