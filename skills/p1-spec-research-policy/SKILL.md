---
name: p1-spec-research-policy
description: "Internal reference: p1 spec research policy (agent-loaded; do not invoke)."
user-invocable: false
---

# Phase 1 Research Policy

## Core Principles

- **AskUserQuestion-First**: Resolve every ambiguity, design choice, or scope decision via
  AskUserQuestion BEFORE proceeding. Never assume — a wrong assumption cascades to all later phases.
- **Structured Interview (before spec parsing)**: Interview the user first — one question per
  message covering goal, scope, constraints, priority trade-offs, verification strategy, and
  dependencies (full interview protocol owned by the goal-clarifier agent). Record answers in
  `docs/phase-1-research/design-intent.md`; resolve ambiguous spec language with the user's
  stated intent, never agent assumptions.
- **Approach Comparison for Open Items**: When the spec allows multiple implementation paths,
  present a per-OPEN comparison table (Approach | Pros | Cons | Area Est. | Latency Est. |
  Recommendation) and let the user select via AskUserQuestion. Record choice + rationale in
  open-requirements.json `resolution_rationale`.
- **Incremental Requirement Approval**: Seek approval in stages — interface/IO → functional
  (per block) → performance → open items — so users correct misinterpretations before they
  propagate. Finalize iron-requirements.json only after all stages are approved.
- **Domain-Consult-First**: Invoke domain-consult for algorithms, standards, coding tools, and
  HW trade-offs — never research in isolation. Experts provide knowledge; spec-analyst captures
  it as structured artifacts.
- **Propose, Do Not Decide**: Present algorithm/tool candidates with trade-offs; the user makes
  final selections. Architecture-level decisions (pipeline, partitioning, memory hierarchy)
  belong to Phase 2 — Phase 1 surveys and recommends.
- **Exhaustive Tree Exploration**: Spawn maximum parallel agents to explore every feasible
  solution path before committing. Skip ONLY if the user specifies exact algorithm +
  architecture (even then, explore at least 2 variants for validation).

## Spec Refinement Criteria

AskUserQuestion MUST cover these areas (skip items already provided by user):
- Target codec, profile, level (e.g., H.264 High Profile Level 4.1)
- Target resolution and framerate (e.g., 1080p@60fps, 4K@30fps)
- Encoder, decoder, or both
- Interface protocol (AXI4, AXI4-Lite, APB, custom)
- Clock frequency target and process node (ASIC vs FPGA)
- Feature scope restrictions (e.g., "TQ only", "intra-only")
- Priority trade-off preference (throughput vs area vs power vs quality)

## 3-Round Chief Review Protocol

Mandatory 3 rounds, coordinated by rtl-architect (domain-agnostic default).
If a domain chief exists (e.g., vcodec-chief-standard-expert for video-codec domain),
invoke both rtl-architect AND domain chief for domain-specific validation:
- **Round 1**: Cross-block data flow completeness, dependencies, performance constraints,
  fixed-point constraints, cross-block issues, [AMBIGUITY]/[CONFLICT] status
  Save: `reviews/phase-1-research/research-review-r1.md`
- **Round 2**: Convergence assessment. Rebuttal: spec-analyst accepts/rejects each Round 1 finding with rationale. Even if converged, proceed to Round 3
  Save: `reviews/phase-1-research/research-review-r2.md`
- **Round 3**: Mandatory final quality pass. Remaining gaps → escalate via AskUserQuestion
  Save: `reviews/phase-1-research/research-review-r3.md`

Review criteria per round:
1. Data flow: inputs/outputs defined at every block boundary
2. Dependencies: which block produces/consumes what data
3. Performance: throughput, latency, bandwidth as specific numbers
4. Fixed-point: bit widths, rounding modes per block
5. Cross-block issues: RDOQ↔Entropy dependency, ME↔MC pipeline, etc.
6. Ambiguities: all resolved or promoted to [ARCHITECTURE_DECISION]

User may override round count: "set iterations to N" → N rounds (minimum 1).

## Iron/Open Requirement Taxonomy

Phase 1 produces TWO requirement files instead of a single requirements.json:
- `docs/phase-1-research/iron-requirements.json` — settled functional (REQ-F-NNN) and
  performance (REQ-P-NNN) requirements, authority = 1, binding for ALL downstream phases.
- `docs/phase-1-research/open-requirements.json` — research topics (OPEN-1-NNN) that
  Phase 2 must investigate and resolve into architecture decisions.

Per-item field schemas for both files are owned by the spec-analyst agent prompt.
This policy owns only the classification and verification rules below.

### Classification Rules

- Functional/performance requirements with clear, measurable acceptance_criteria → **iron**
- Architecture/implementation choices needing further investigation → **open**
- Items with ambiguity score > 0.5 → CANNOT become iron until clarified
- A requirement cannot become iron until its ambiguity score passes (reproducibility check)

## Iron/Open Classification Verification

After iron/open files are produced, verify:

**FAIL conditions** (must fix before exit):
- acceptance_criteria contains vague terms ("should support", "adequate", "sufficient")
- open item missing evaluation_criteria
- open item has candidates.length ≤ 1
- iron item missing violation_policy

**WARN conditions** (log and proceed):
- iron ratio < 30% (most items pushed to open — weakens Phase 1 value)
- open item related_iron is empty
- CONDITIONAL PASS ambiguity axis linked to an iron-classified REQ

## Port Naming Conventions (io_definition.json)

- Inputs: `i_` prefix (e.g., `i_data`, `i_valid`) — NOT suffix `_i`
- Outputs: `o_` prefix (e.g., `o_result`, `o_ready`) — NOT suffix `_o`
- Bidirectional: `io_` prefix (e.g., `io_sda`)
- Clocks: `clk` (single domain) or `{domain}_clk` (e.g., `sys_clk`) — NOT `clk_i`
- Resets: `rst_n` (single domain) or `{domain}_rst_n` (e.g., `sys_rst_n`) — NOT `rst_ni`
- Single clock domain defaults to `sys_clk` / `sys_rst_n`

## Self-Verification Format

Save to `reviews/phase-1-research/research-review.md`:
```
# Phase 1 Review: Research Completeness
- Date: YYYY-MM-DD
- Reviewer: spec-analyst
- Upper Spec: specs/
- Verdict: PASS | FAIL

## Feature Coverage Checklist
| Spec Section | Requirement ID | Status |

## Findings
### [severity] Finding-N: ...

## Verdict
PASS | FAIL: [reason]
```

## Spec Feature Completeness Audit (MANDATORY — Step 7.5c / team T12b-T12c)

The extractor MUST NOT grade its own completeness: an extraction blind spot also biases
the self-counted denominator (5-of-10 modes self-reports 5/5). The completeness verdict
comes from an independent census + mechanical diff:

1. **Independent feature census** (clean context): spawn spec-analyst in FEATURE CENSUS
   MODE. It reads ONLY original spec sources (`specs/**`, `docs/phase-1-research/goal.md`,
   domain knowledge files) and MUST NOT read iron-requirements.json, open-requirements.json,
   or any prior Phase 1 analysis. Enumerate EVERY spec-defined item — expand mode/format
   tables item-by-item (e.g., each intra prediction mode, encoding mode, color format,
   block size is one entry). Write `docs/phase-1-research/spec-feature-inventory.json`:
   ```json
   { "features": [ { "feature_id": "FEAT-001", "name": "...", "kind": "mode|format|algorithm|capability|constraint",
                     "source": { "document": "...", "section": "..." } } ] }
   ```

2. **Mechanical diff** (different agent): spawn rtl-architect to map every FEAT-* to
   REQ/OPEN IDs in iron ∪ open requirements. Per-feature status:
   - `EXTRACTED` — mapped to at least one REQ/OPEN id
   - `EXCLUDED_BY_SCOPE` — user-approved exclusion, ADR reference recorded
   - `MISSING` — no mapping and no approval

3. **Gap escalation**: any MISSING feature → MUST ask user via AskUserQuestion:
   - "Spec defines N features; requirements cover M. Omitting K features may reduce
     [quality metric]. Approve omission?"
   - Approved → status `EXCLUDED_BY_SCOPE` + ADR with rationale and impact estimate
   - Not approved → add REQ-F-* to iron-requirements.json as MUST_IMPLEMENT, re-run diff

4. **Documentation**: save `docs/phase-1-research/feature-coverage.md`:
   ```
   | Feature | Spec Source | REQ/OPEN IDs | Status |
   |---------|-------------|--------------|--------|
   | Intra mode DC | §8.3.1 | REQ-F-012 | EXTRACTED |
   | Intra mode planar | §8.3.2 | — (ADR-007) | EXCLUDED_BY_SCOPE |
   ```
   plus totals: features / extracted / excluded_by_scope / missing.

5. **Gate**: PASS iff missing == 0 (every feature EXTRACTED or EXCLUDED_BY_SCOPE).
   FAIL blocks Phase 1 completion (`feature-coverage-audited` completion criterion).

6. **Downstream contract**: `spec-feature-inventory.json` is the authoritative spec-item
   denominator for later phases; `EXCLUDED_BY_SCOPE` records let downstream gates
   distinguish user-approved scope reduction from silent extraction loss.

7. **Reference model cross-check** (Phase 2+, when refC or an external golden exists):
   compare the inventory against model implementation — "enum declared but function not
   implemented" → COVERAGE_GAP warning.

## Escalation & Stop Conditions

- Spec document not found → report to user, halt
- Conflicting requirements between experts → flag conflict in domain-analysis.md, ask user
- Chief not converged after 3 rounds → escalate remaining gaps to user with specific questions
- Sub-domain expert returns [DOMAIN_UNCERTAINTY] → AskUserQuestion before proceeding

## Ambiguity Score Protocol

Every Phase 1 completion MUST include an ambiguity assessment:

1. spec-analyst produces `Ambiguity_Assessment` with per-axis scores
2. Ambiguity Gate enforced by both orchestrators:
   - p1-research-orchestrator: Step 7.5
   - p1-research-team-orchestrator: Step 3.5
3. Score is recorded in `docs/phase-1-research/ambiguity-assessment.md`
4. Phase 2 entry reads this score — if > 0.3, phase 2 reviewers prioritize clarifying those axes

This is inspired by Ouroboros's AmbiguityScorer pattern:
- Goal Ambiguity (40%): Is the design objective ambiguous? (0.0=clear, 1.0=ambiguous)
- Constraint Ambiguity (30%): Are timing/area/power/protocol constraints missing? (0.0=explicit, 1.0=missing)
- AC Ambiguity (30%): Are acceptance criteria untestable? (0.0=testable, 1.0=untestable)

Scoring: ambiguity_score = weighted_average(goal, constraint, ac) — higher = worse
- ≤ 0.3: PASS — proceed to Phase 2
- 0.3–0.5: CONDITIONAL PASS — log warnings, Phase 2 reviewers focus on flagged axes
- \> 0.5: BLOCK — resolve top ambiguities via AskUserQuestion before proceeding

## Adversarial Interpretation Gate (Steps 7.6-7.9)

After ambiguity gate (Step 7.5a) and iron/open verification (Step 7.5b) pass,
run adversarial reinterpretation to surface ambiguities the initial analysis missed.

### Protocol (summary — Task-level orchestration owned by p1-research-orchestrator Steps 7.6-7.9)

1. **7.6 Challenge**: adversarial spec-analyst (clean context) challenges iron-requirements.json
   by `source.section` (not REQ ID); types: `REINTERPRETATION` (alternative reading) and
   `OMISSION` (zero-REQ spec feature vs spec-feature-inventory.json →
   original_interpretation="NOT_EXTRACTED", severity HIGH). Output
   `.rat/scratch/stability/phase-1/challenge-report.json`
   (schema: `skills/p1-spec-research/templates/challenge-report-schema.json`; max 30 per pass).
2. **7.7 User resolution**: HIGH individually via AskUserQuestion; MEDIUM batched if >10;
   LOW auto-documented. User may mark challenges NOT_GENUINE.
3. **7.8 Re-run**: spec-analyst re-analyzes with accumulated clarifications → all 4 canonical
   artifacts (iron/open requirements, io_definition, timing_constraints) + self-validation.
4. **7.9 Gate check**: compute Gate Metric below + save `reviews/phase-1-research/stability-report.md`.

### Gate Metric

```
genuine = (HIGH + MEDIUM challenges) - NOT_GENUINE
resolved = RESOLVED + DOCUMENTED
resolution_ratio = resolved / genuine   (if genuine == 0: pass)
gate_pass = (all HIGH resolved) AND (resolution_ratio ≥ 0.8)
```

Gate failure: list unresolved HIGH challenges, loop back to Step 7.7 (max 1 re-loop).
After 2nd failure: escalate to user with full divergence report.

### Dual Gate Arbitration (Ambiguity Score + Adversarial Gate)

| Ambiguity Score | Adversarial Gate | Decision |
|-----------------|-----------------|----------|
| PASS (≤0.3) | PASS | Proceed |
| PASS (≤0.3) | FAIL | **BLOCK** |
| CONDITIONAL (0.3-0.5) | PASS | Proceed with WARNING |
| CONDITIONAL (0.3-0.5) | FAIL | **BLOCK** |
| BLOCK (>0.5) | PASS | **BLOCK** |
| BLOCK (>0.5) | FAIL | **BLOCK** |

Rule: Either gate can block; neither can unblock the other.

### Severity Classification

| Severity | Criterion | Example |
|----------|-----------|---------|
| HIGH | Missing item (OMISSION) | Spec defines 10 encoding modes, only 5 extracted |
| HIGH | Different RTL behavior | Signed vs unsigned arithmetic |
| HIGH | Different interface | 32-bit vs 64-bit datapath |
| MEDIUM | Different parameterization | Fixed depth vs configurable |
| MEDIUM | Different timing | 3-stage vs 4-stage pipeline |
| LOW | Cosmetic only | Block naming differences |

Boundary rule: alternative interpretation would cause different RTL module → HIGH.
Same module but different parameters → MEDIUM. Same module, same parameters → LOW.

### Pathological Patterns

- Zero challenges on >15 requirements → re-run with stronger adversarial framing
- >50% items at HIGH severity → spec fundamentally under-specified, escalate
- Challenge budget exceeded (>30) → rank by severity, return top 30

## Final Checklist

- [ ] `docs/phase-1-research/iron-requirements.json` exists and is valid JSON
- [ ] `docs/phase-1-research/open-requirements.json` exists and is valid JSON
- [ ] Every requirement has unique `"id": "REQ-NNN"` field
- [ ] `docs/phase-1-research/io_definition.json` exists and is valid JSON
- [ ] io_definition.json port names use `i_`/`o_`/`io_` prefix (NOT suffix)
- [ ] io_definition.json clocks use `{domain}_clk`, resets use `{domain}_rst_n`
- [ ] `docs/phase-1-research/timing_constraints.json` exists with per-block timing targets (rough estimates)
- [ ] `docs/phase-1-research/domain-analysis.md` exists with cross-block dependency matrix and per-block timing targets
- [ ] No unresolved requirement conflicts
- [ ] Review coordinator (rtl-architect, or domain chief if available) declared Architecture-Ready (or gaps escalated)
- [ ] Self-verification verdict produced (PASS or REVIEW_NEEDED)
- [ ] Spec feature count vs iron-requirements.json + open-requirements.json count documented
- [ ] `docs/phase-1-research/spec-feature-inventory.json` produced by independent census (clean context, no requirements.json access)
- [ ] `docs/phase-1-research/feature-coverage.md` saved with zero MISSING features (all EXTRACTED or EXCLUDED_BY_SCOPE with ADR)
- [ ] `reviews/phase-1-research/research-review.md` saved (consolidated)
- [ ] Per-round review artifacts saved: research-review-r1.md, r2.md, r3.md
- [ ] `docs/phase-1-research/solution-tree.json` exists (structured JSON)
- [ ] `docs/phase-1-research/candidate-comparison.md` exists
- [ ] `docs/phase-1-research/selected-approach.md` exists
- [ ] `docs/phase-1-research/literature-survey.md` exists
- [ ] Tree exploration used maximum parallel agents (8-20 leaf + cross-cutting)
- [ ] domain-consult invoked at least once
- [ ] Algorithm/tool candidates presented with trade-offs (NOT pre-selected)
- [ ] AskUserQuestion used at every ambiguity point (no unresolved assumptions)
- [ ] `docs/phase-1-research/ambiguity-assessment.md` saved with per-axis scores and overall ambiguity_score
- [ ] Ambiguity Gate passed (score ≤ 0.3 for PASS, 0.3–0.5 for CONDITIONAL PASS)
- [ ] Adversarial reinterpretation completed (Step 7.6)
- [ ] All HIGH challenges resolved or escalated
- [ ] resolution_ratio ≥ 0.8 (adversarial gate PASS)
- [ ] `reviews/phase-1-research/stability-report.md` saved
- [ ] Every iron requirement has measurable acceptance_criteria (no vague terms)
- [ ] Every iron requirement has `"violation_policy": "user_escalation"`
- [ ] Every open item has ≥ 2 candidates and evaluation_criteria
- [ ] File-level target_phase specified in open-requirements.json
- [ ] Iron/open classification verification passed (no FAIL conditions)
