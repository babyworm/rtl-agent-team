# Interpretation Stability Framework for Phase 1-3

> Design Spec — 2026-03-20 (Rev.3 — post-review rewrite)
> Status: DRAFT
> Scope: Supplements existing ambiguity scoring with adversarial reinterpretation
> Naming: "Interpretation stability" (NOT "convergence" — reserved for review finding convergence)
> MVP: Phase 1 only

## 1. Problem & Approach

### Problem
Phase 1 ambiguity scoring (0.0-1.0, 3-axis) is subjective and non-reproducible.

### Approach
**Supplement** (not replace) the ambiguity score with **adversarial reinterpretation**:
an agent actively challenges the initial output to surface genuine ambiguities.

### Core Principle
> If a document is unambiguous, an adversarial attempt to reinterpret it
> will fail to produce meaningful alternatives.

### Why Not Independent Re-runs
Same model + same input → correlated outputs. "Convergence" of correlated
samples measures LLM consistency, not document clarity.

## 2. Protocol Overview

```
Phase N:
  Step 1a: Initial interpretation → output_v1
  Step 1b: Adversarial reinterpretation → challenge_report
  Step 1c: User resolves HIGH/MEDIUM challenges
  Step 1d: Re-run with clarifications → output_v2 (canonical)
  Gate:    All HIGH challenges resolved, resolution_ratio ≥ threshold

  Step 2:  Model construction (refC@P2, BFM@P3; skipped @P1)
  Step 3:  Behavioral feedback → targeted adversarial re-check
  Step 4:  Model-document consistency check
```

### Gate Metric (replaces stability score from Rev.2)

The gate uses the **adversarial challenge report directly** — no separate stability score.

```
genuine = (HIGH + MEDIUM challenges) - NOT_GENUINE
resolved = RESOLVED + DOCUMENTED
resolution_ratio = resolved / genuine   (if genuine == 0: pass)
gate_pass = (all HIGH resolved) AND (resolution_ratio ≥ 0.8)
```

**Rationale** (Rev.2 lesson): A "stability score" comparing v1 vs v2 on unresolved items
is tautological — unresolved items were unresolved because no alternative was found,
so they trivially match. The adversarial report itself IS the quality signal.

## 3. Step 1b: Adversarial Reinterpretation (Detail)

### Adversarial Prompt

```
You are reviewing the following specification output. Your task is NOT to validate it,
but to find ALTERNATIVE VALID interpretations of the source spec that would produce
DIFFERENT requirements/architecture/design.

For each item, ask:
- Could this spec text be interpreted differently?
- Are there unstated assumptions?
- Could the acceptance criteria be measured differently?
- Is the data format/protocol/encoding ambiguous?

Reference items by source.section (NOT by requirement ID).

Output format:
{
  "challenges": [
    {
      "target_source": {"document": "spec.pdf", "section": "3.2"},
      "original_interpretation": "8-bit unsigned data",
      "alternative_interpretation": "8-bit signed data",
      "spec_evidence": "Section 3.2 says 'byte data' without specifying signedness",
      "impact": "Overflow behavior changes, affects transform output range",
      "severity": "HIGH"
    }
  ],
  "unchallenged_count": 20,
  "challenged_count": 5
}
```

**Key change from Rev.2**: References use `target_source.section` (stable across runs),
not requirement IDs (which differ between v1 and v2).

### Severity Classification (with boundary examples)

| Severity | Criterion | Example |
|----------|-----------|---------|
| **HIGH** | Different RTL behavior — different logic, different waveform | "Signed vs unsigned arithmetic" — overflow wraps vs saturates |
| **HIGH** | Different interface — port count, width, protocol changes | "32-bit AXI vs 64-bit AXI" — different datapath width |
| **MEDIUM** | Different parameterization — same logic, different constants | "FIFO depth 16 (fixed) vs configurable (default 16)" — parameterizable vs hardcoded |
| **MEDIUM** | Different timing — same function, different latency | "3-stage vs 4-stage pipeline" — area/timing tradeoff |
| **LOW** | Cosmetic — naming, formatting, documentation only | "Block named 'transform' vs 'tq_engine'" — no behavioral difference |

**Boundary rule**: If the alternative interpretation would cause a **different RTL module
to be written** (different ports, different FSM states, different datapath width) → HIGH.
If same module but different parameter values → MEDIUM. If same module, same parameters → LOW.

**Challenge budget**: Max 30 challenges per adversarial pass. If the adversarial agent
identifies >30, it must rank and return only the top 30 by severity.

### Independence

Step 1b runs as a **separate Task() subagent** with clean context.
It receives: (1) original spec documents, (2) output_v1 as a file to challenge.
It does NOT see the orchestrator's conversation history.

## 4. Step 1c: User Resolution

For each HIGH challenge:
- Present both interpretations to the user (AskUserQuestion)
- User selects the correct interpretation
- Resolution recorded as clarification input for Step 1d

For each MEDIUM challenge:
- Present to user if ≤10 total MEDIUM challenges
- If >10 MEDIUM, batch as a summary and ask "review these assumptions?"

For LOW challenges:
- Log as documented assumptions
- No user interaction

### Pathological Patterns

| Pattern | Detection | Action |
|---------|-----------|--------|
| **Zero challenges** on spec with >15 requirements | challenged_count = 0 AND total_reqs > 15 | Re-run with explicit prompt: "The initial pass found zero issues. Look harder." |
| **Challenge saturation** | >50% items at HIGH severity | Spec fundamentally under-specified. Escalate: "Spec needs major revision before proceeding." |
| **Forced disagreements** | Challenges with weak spec_evidence | During user resolution, user can mark as "NOT_GENUINE" → excluded from ratio |

## 5. Step 1d: Re-run and Gate

Re-run spec-analyst with enriched input (original spec + user clarifications from Step 1c).
The re-run produces ALL FOUR canonical artifacts (not just iron-requirements.json):
- `docs/phase-1-research/iron-requirements.json`
- `docs/phase-1-research/open-requirements.json`
- `docs/phase-1-research/io_definition.json`
- `docs/phase-1-research/timing_constraints.json`

This ensures the full artifact set is consistent with user clarifications.
Self-validation (spec-analyst's built-in Step 15) re-runs automatically as part of the re-run.
Output_v1 remains in scratch (temporary).

### Gate Check

```
gate_pass = (all HIGH resolved) AND (resolution_ratio ≥ 0.8)

where:
  actionable = HIGH + MEDIUM challenges (LOW excluded — auto-documented)
  genuine = actionable - NOT_GENUINE (user-excluded forced disagreements)
  resolved = challenges marked RESOLVED or DOCUMENTED by user in Step 1c
  resolution_ratio = resolved / genuine   (if genuine == 0: gate_pass = true)
```

If gate fails:
- List unresolved HIGH challenges
- Escalate to user: "These ambiguities must be resolved before Phase 2."
- User provides additional clarification → loop back to Step 1c (max 1 re-loop)

### What This Gate Measures

| What it measures | How |
|-----------------|-----|
| Are there genuine ambiguities? | YES if adversarial agent found HIGH challenges with strong spec evidence |
| Were they resolved? | YES if user provided clarification for each |
| Is the resolution sufficient? | Verified by resolution_ratio ≥ 0.8 |

## 6. Comparison Script: stability_check.py

### Purpose

Content-based alignment between output_v1 and output_v2 for the **stability report**
(informational, NOT the gate — the gate is adversarial report based).

The stability report documents WHAT CHANGED between v1 and v2 after clarifications.
It is an audit artifact, not a quality gate.

### Algorithm (Fully Specified)

```python
import json
import re

# ═══ Tokenizer ═══
STOPWORDS = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
             "being", "have", "has", "had", "do", "does", "did", "will",
             "would", "shall", "should", "may", "might", "can", "could",
             "of", "in", "to", "for", "with", "on", "at", "from", "by",
             "and", "or", "not", "no", "but", "if", "then", "else",
             "this", "that", "these", "those", "it", "its"}

def tokenize(text):
    """Lowercase, split on non-alphanumeric, remove stopwords."""
    tokens = re.findall(r'[a-z0-9_]+', text.lower())
    return set(t for t in tokens if t not in STOPWORDS and len(t) > 1)

def jaccard(set_a, set_b):
    """Jaccard similarity: |intersection| / |union|."""
    if not set_a and not set_b:
        return 1.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0

# ═══ Requirement Alignment ═══
def align_requirements(v1_reqs, v2_reqs):
    """Align requirements using source.section as primary key.
    Fallback: greedy matching on description token similarity.

    Note: Multiple requirements may share the same source.section.
    Pass 1 performs greedy 1:1 matching within each section group;
    excess requirements fall through to Pass 2.
    If ALL items have blank source.section, everything goes through Pass 2
    (greedy Jaccard). The stability report should emit a WARNING when >50%
    of alignments came from Pass 2 rather than Pass 1."""

    aligned = []  # [(v1_req, v2_req, similarity)]
    v2_used = set()

    def _source_key(r):
        """Composite key: (document, section, line) — uses all available fields."""
        src = r.get("source", {})
        return (src.get("document", ""), src.get("section", ""), src.get("line", 0))

    # Pass 1: source-key grouping with best-match within each group
    v2_by_section = {}
    for j, r2 in enumerate(v2_reqs):
        sec = r2.get("source", {}).get("section", "")
        if sec:
            v2_by_section.setdefault(sec, []).append((j, r2))

    for r1 in v1_reqs:
        sec = r1.get("source", {}).get("section", "")
        if sec and sec in v2_by_section:
            # Best-match within section group (not first-match)
            best_sim, best_j, best_r2 = -1.0, -1, None
            for j, r2 in v2_by_section[sec]:
                if j not in v2_used:
                    sim = compute_pair_similarity(r1, r2)
                    if sim > best_sim:
                        best_sim, best_j, best_r2 = sim, j, r2
            if best_j >= 0:
                aligned.append((r1, best_r2, best_sim))
                v2_used.add(best_j)

    # Pass 2: greedy matching on remaining by description similarity
    v1_unmatched = [r for r in v1_reqs
                    if not any(a[0] is r for a in aligned)]
    v2_unmatched = [(j, r) for j, r in enumerate(v2_reqs)
                    if j not in v2_used]

    for r1 in v1_unmatched:
        best_sim, best_j, best_r2 = 0.0, -1, None
        t1 = tokenize(r1.get("description", ""))
        for j, r2 in v2_unmatched:
            t2 = tokenize(r2.get("description", ""))
            sim = jaccard(t1, t2)
            if sim > best_sim:
                best_sim, best_j, best_r2 = sim, j, r2
        if best_sim >= 0.4 and best_j >= 0:  # alignment threshold
            full_sim = compute_pair_similarity(r1, best_r2)
            aligned.append((r1, best_r2, full_sim))
            v2_unmatched = [(j, r) for j, r in v2_unmatched if j != best_j]

    # Rebuild v1_unmatched after Pass 2 consumed some items
    v1_still_unmatched = [r for r in v1_unmatched
                          if not any(a[0] is r for a in aligned)]
    return aligned, v1_still_unmatched, [r for _, r in v2_unmatched]

def compute_pair_similarity(r1, r2):
    """Per-pair similarity on structured fields."""
    score = 0.0

    # source match (25%) — composite key: section (15%) + line proximity (10%)
    src1 = r1.get("source", {})
    src2 = r2.get("source", {})
    sec_match = 1.0 if (src1.get("section") and src1.get("section") == src2.get("section")) else 0.0
    line1, line2 = src1.get("line", 0), src2.get("line", 0)
    line_proximity = 1.0 if (line1 and line2 and abs(line1 - line2) <= 5) else 0.0
    score += 0.15 * sec_match + 0.10 * line_proximity

    # type + priority match (15%)
    type_match = 1.0 if r1.get("type") == r2.get("type") else 0.0
    prio_match = 1.0 if r1.get("priority") == r2.get("priority") else 0.0
    score += 0.15 * (0.5 * type_match + 0.5 * prio_match)

    # acceptance_criteria overlap (30%) — tokenized Jaccard per AC item, averaged
    ac1 = r1.get("acceptance_criteria", [])
    ac2 = r2.get("acceptance_criteria", [])
    if ac1 and ac2:
        ac_sims = []
        for a1 in ac1:
            best = max((jaccard(tokenize(a1), tokenize(a2)) for a2 in ac2), default=0.0)
            ac_sims.append(best)
        score += 0.30 * (sum(ac_sims) / len(ac_sims))
    elif not ac1 and not ac2:
        score += 0.30

    # description keyword overlap (20%) — Jaccard on tokenized description
    score += 0.20 * jaccard(
        tokenize(r1.get("description", "")),
        tokenize(r2.get("description", ""))
    )

    # complexity match (10%)
    score += 0.10 * (1.0 if r1.get("complexity") == r2.get("complexity") else 0.0)

    return score
```

**Determinism**: This algorithm uses only string operations (tokenize, Jaccard, exact match).
No LLM, no embeddings, no external dependencies beyond Python stdlib.
Same inputs → same output, guaranteed.

### Output: stability-report.md

```markdown
# Interpretation Stability Report
- Phase: phase-1-research
- Date: YYYY-MM-DD
- v1 path: .rtl-agent-team/scratch/stability/phase-1/output-v1.json
- v2 path: docs/phase-1-research/ (iron-requirements.json + open-requirements.json + io_definition.json + timing_constraints.json)

## Alignment Summary
- v1 requirements: N
- v2 requirements: M
- Aligned pairs: K (avg similarity: X.XX)
- v1-only (removed after clarification): L
- v2-only (added after clarification): P

## Changes From Clarification
| v1 source.section | v2 source.section | Field Changed | Before | After |
|-------------------|-------------------|---------------|--------|-------|
| §3.2 | §3.2 | description | "byte data" | "unsigned 8-bit data" |

## Adversarial Challenge Resolution
| Challenge | Source Section | Severity | Resolution | Status |
|-----------|--------------|----------|------------|--------|
| Signedness | §3.2 | HIGH | User: unsigned | RESOLVED |
| FIFO depth | §4.1 | MEDIUM | Assumed: fixed 16 | DOCUMENTED |
```

## 7. Steps 2-4: Model Validation (Phase 2-3 only)

### Step 2: Model Construction

After adversarial gate passes:
- Phase 2: Build refC — validates block I/O, data flow, bandwidth
- Phase 3: Build BFM — validates module timing, clock domains, pipeline

Behavioral ambiguities logged as:
```json
{
  "type": "behavioral_ambiguity",
  "source": "refC_construction",
  "location": "block_name",
  "description": "...",
  "impact": "HIGH | MEDIUM | LOW",
  "related_source_section": "§3.2"
}
```
**Note**: References use `source.section`, not requirement IDs.

### Step 3: Behavioral Feedback

HIGH-impact behavioral ambiguities → user resolution (AskUserQuestion).
MEDIUM → document with assumption. LOW → log only.

After resolution, re-run adversarial check on **affected items only**:

**Affected items definition**: An item is affected if:
- (a) Its `source.section` matches the `related_source_section` of any behavioral ambiguity, OR
- (b) It has a `dependencies` entry in iron-requirements.json that references any item from (a)

Blast radius: **1-hop** (direct dependency only, not transitive).

**Budget**: Max 15 HIGH behavioral ambiguities before escalation.

### Step 4: Model-Document Consistency

refC/BFM output vs acceptance criteria. Same as existing G4a/G4b gates.

## 8. Orchestrator Integration

### Phase 1: Where Steps Insert

```
Existing p1-research-orchestrator flow:
  Step 0: Context Bootstrap
  Step 1: Spec source identification
  Step 2: Domain expert consultation
  Step 3: AskUserQuestion for spec gaps
  Step 4: spec-analyst run (parallel sub-domain survey)
  Step 5: 3-round chief review (finding_delta convergence)
  Step 6: Solution tree merge
  Step 7: Iron/open classification
  Step 7.5a: Ambiguity gate (existing, KEPT)
  Step 7.5b: Iron/open classification verification (existing, KEPT)

  ──── NEW: Interpretation Stability Steps (after 7.5b) ────
  Step 7.6: Adversarial reinterpretation (Step 1b)
    - Task(subagent_type="spec-analyst", prompt="adversarial reinterpretation of...")
    - Input: original spec + iron-requirements.json from Step 7
    - Output: challenge_report.json → .rtl-agent-team/scratch/stability/phase-1/
  Step 7.7: User resolution (Step 1c)
    - AskUserQuestion for each HIGH challenge
    - Accumulate clarifications
  Step 7.8: Re-run spec-analyst with clarifications (Step 1d)
    - Input: original spec + clarifications
    - Output: all 4 canonical artifacts (iron-requirements.json, open-requirements.json,
      io_definition.json, timing_constraints.json) + self-validation
  Step 7.9: Adversarial gate check
    - All HIGH resolved AND resolution_ratio ≥ 0.8
    - Run stability_check.py for audit report (informational)
    - If FAIL: loop back to Step 7.7 (max 1 re-loop)
  ──── END NEW ────

  Step 8: Codex cross-review (existing, optional)
  Step 9: Final artifacts + exit gate
```

**Rationale for placement after Step 7.5b**: The existing ambiguity score (7.5a)
and iron/open verification (7.5b) provide fast first-pass filters. Adversarial
reinterpretation is a deeper, more expensive check that runs only after the spec
passes both initial gates. This ensures the adversarial agent challenges FINAL
classified iron requirements, not pre-classification output.

### Phase 1 Team Mode

The team orchestrator (`p1-research-team-orchestrator.md`) uses T1-T12 numbering.
Insert adversarial reinterpretation as a new task after the final verification task:
- Create `TaskCreate(subject="Adversarial reinterpretation")` → assigned to any available worker
- Blocked by: T12 (final verification / iron-open classification)
- Blocks: codex cross-review task (if present) and the leader's exit gate monitoring
- Worker spawns `Task(subagent_type="spec-analyst", prompt="adversarial...")` internally

### Phase 2-3 (Future Extension)

Insert after the existing iron/open classification step in each phase's orchestrator,
before the existing review convergence rounds. Exact step numbers to be determined
when Phase 2-3 MVP is designed.

## 9. Dual Gate: Ambiguity Score + Adversarial Report

Both gates exist. Arbitration when they disagree:

| Ambiguity Score | Adversarial Gate | Decision |
|-----------------|-----------------|----------|
| PASS (≤0.3) | PASS | **Proceed** |
| PASS (≤0.3) | FAIL | **BLOCK** — adversarial found issues the score missed |
| CONDITIONAL (0.3-0.5) | PASS | **Proceed with WARNING** — score flagged concerns but adversarial found no alternatives |
| CONDITIONAL (0.3-0.5) | FAIL | **BLOCK** — adversarial confirms ambiguity concerns |
| BLOCK (>0.5) | PASS | **BLOCK** — ambiguity score is the conservative gate |
| BLOCK (>0.5) | FAIL | **BLOCK** |

**Rule**: Either gate can block; neither can unblock the other.
This is intentionally conservative — false negatives (missing ambiguity) are far more
expensive than false positives (unnecessary clarification) in silicon design.

## 10. Codex Cross-Review Integration (Optional)

When Codex CLI is available, use `codex-cross-review` as an **independent model check**
after Step 7.8 (before or alongside Step 8):
- Codex reviews iron-requirements.json independently
- Disagreements between Claude and Codex are treated as additional challenges
- Provides TRUE model independence (different model family)
- Captured in existing codex-cross-review workflow — no new infrastructure

## 11. Artifact Paths

| Artifact | Path | Lifecycle |
|----------|------|-----------|
| Initial output (v1) | `.rtl-agent-team/scratch/stability/phase-{N}/output-v1.json` | Temporary |
| Challenge report | `.rtl-agent-team/scratch/stability/phase-{N}/challenge-report.json` | Temporary |
| Canonical output (v2) | `docs/phase-{N}-*/iron-requirements.json` + `open-requirements.json` + `io_definition.json` + `timing_constraints.json` | Permanent |
| Stability report | `reviews/phase-{N}-*/stability-report.md` | Permanent |

No schema changes to iron-requirements.json. v1 is scratch-only.

## 12. Cost Analysis (Honest)

| Step | LLM Cost | Human Cost | Notes |
|------|---------|-----------|-------|
| 1a | 0 | 0 | Already part of current pipeline |
| 1b (adversarial) | +1 full spec-analyst invocation | 0 | Processes full output, significant token cost |
| 1c (resolution) | 0 | **Blocking** — N decisions | Dominant cost. Depends on challenge count |
| 1d (re-run) | +1 full spec-analyst invocation | 0 | Full re-run with clarifications |
| Gate check | Negligible (Python script) | 0 | Deterministic comparison |
| **Total added LLM** | **+2 spec-analyst runs** | | ~20-30% overhead on P1 LLM cost |
| **Total added human** | | **5-15 decisions** | Pipeline blocks until user responds |

**Note**: The human decision cost is the dominant factor. For a complex spec with 10+
HIGH challenges, the pipeline may block for hours. This is intentional — these decisions
MUST be made before silicon commitment. Currently they are made implicitly (LLM assumes);
now they are made explicitly (user decides).

## 13. MVP Scope: Phase 1 Only

### Deliverables

1. **Adversarial prompt template** — embedded in orchestrator Step 7.6
2. **`scripts/stability_check.py`** — fully specified algorithm (§6)
3. **Stability gate logic** — in `p1-spec-research-policy/SKILL.md`
4. **Orchestrator integration** — Steps 7.6-7.9 in `p1-research-orchestrator.md`
5. **`stability-report.md` template** — in `skills/p1-spec-research/templates/`

### NOT in MVP

- Phase 2-3 stability checking (deferred until P1 validated on 3+ designs)
- Multi-model consensus (Codex cross-review already exists, integration is optional)
- stability_check.py comparison for architecture/uarch prose documents

## 14. Success Criteria

| Metric | Target | How to Measure |
|--------|--------|---------------|
| Adversarial challenges that are genuine | >50% marked RESOLVED (not NOT_GENUINE) by user | Track over 5 designs |
| HIGH challenges found per design | 3-10 range (neither zero nor overwhelming) | Track |
| Pipeline latency increase | <2 hours of human decision time per Phase 1 | Track |
| Phase 5→4 feedback loops | Decrease vs designs without stability checking | Compare |
| False alarm rate | <20% challenges marked NOT_GENUINE | Track |

## 15. Open Questions (3 remaining)

1. **Adversarial prompt effectiveness**: Will the adversarial agent find genuine issues
   or produce forced disagreements? Needs empirical testing on 1-2 existing specs.
2. **Threshold calibration**: resolution_ratio ≥ 0.8 is a starting value.
   Calibrate after 5 designs based on observed distribution.
3. **Codex availability**: Multi-model validation via codex-cross-review is optional.
   Track whether designs that use it have fewer downstream issues.

## 16. Relationship to Existing Concepts

| Concept | What It Is | Relationship |
|---------|-----------|-------------|
| Ambiguity score (spec-analyst) | Subjective 0-1 readiness signal | **Kept, supplemented** by adversarial gate |
| Review convergence (finding_delta) | Measures review round stabilization | **Orthogonal** — different mechanism, different axis |
| Ouroboros ontology stability | Multi-generation schema convergence | **Inspired by** — we use adversarial instead of re-runs |
| Iron/open classification | Settled vs open requirements | **Used as substrate** — adversarial challenges iron items |
