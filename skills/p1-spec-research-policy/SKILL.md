---
name: p1-spec-research-policy
description: "Quality criteria, review protocols, naming conventions, artifact format specifications, and checklists for the Phase 1 research pipeline. Pure reference — no orchestration."
user-invocable: false
---

# Phase 1 Research Policy

## Core Principles

### AskUserQuestion-First
Every ambiguity, design choice, or scope decision MUST be resolved via AskUserQuestion
BEFORE proceeding. Do not assume — ask. The cost of asking is low; the cost of a wrong
assumption cascades to all later phases.

### Structured Interview Protocol (before spec parsing)

Before analyzing spec documents, conduct a structured user interview to understand
intent, priorities, and constraints. Ask **one question per message** — do not batch.

Interview sequence (adapt to context, skip if already clear from spec):
1. **Goal**: "What is the primary purpose of this design? What problem does it solve?"
2. **Scope**: "Which features from the spec are in-scope for this implementation?
   Any intentional omissions?"
3. **Constraints**: "Target frequency? Area budget? Power envelope? Technology node?"
4. **Priority**: "If trade-offs arise (area vs performance vs power), which takes precedence?"
5. **Verification**: "What is the verification strategy? cocotb/UVM? Formal? Target coverage?"
6. **Dependencies**: "Any existing IP/modules to integrate? Reference models to match?"

Record answers in `docs/phase-1-research/design-intent.md`. These answers become
the interpretive context for all spec parsing — ambiguous spec language is resolved
using the user's stated intent, not agent assumptions.

### Approach Comparison for Open Items

When the spec allows multiple implementation paths (algorithm choices, architecture options,
protocol selections), present structured comparisons to the user:

```markdown
## OPEN-1-NNN: {topic}

| Approach | Pros | Cons | Area Est. | Latency Est. | Recommendation |
|----------|------|------|-----------|-------------|----------------|
| A: {name} | ... | ... | ... | ... | |
| B: {name} | ... | ... | ... | ... | ★ Recommended |
| C: {name} | ... | ... | ... | ... | |

Trade-off summary: {1-2 sentences}
```

Ask user to select via AskUserQuestion. Record choice + rationale in open-requirements.json
`resolution_rationale` field.

### Incremental Requirement Approval

Do NOT present all requirements at once. Group by functional area and seek approval
in stages:

1. Present **interface/IO requirements** first (ports, protocols, clocks) → user approves
2. Present **functional requirements** by block → user approves per block
3. Present **performance requirements** (timing, throughput, area) → user approves
4. Present **open items** with approach comparisons → user selects

At each stage, the user can correct misinterpretations before they propagate.
Only after all stages are approved, finalize iron-requirements.json.

### Domain-Consult-First
Actively invoke domain-consult to acquire domain expert knowledge on algorithms, standards,
coding tools, filter characteristics, and HW implementation trade-offs. Do not research
in isolation. Domain experts provide knowledge; spec-analyst captures results as structured artifacts.

### Propose, Do Not Decide
Present algorithm/tool candidates with trade-offs. Let the user make final selections.
Architecture-level decisions (pipeline, block partitioning, memory hierarchy) are Phase 2's
responsibility. Phase 1 surveys and recommends; Phase 2 designs.

### Exhaustive Tree Exploration
Spawn maximum agents in parallel to explore all solution paths. Every feasible approach
must be investigated and compared before committing. Skip ONLY if user specifies exact
algorithm + architecture (even then, explore at least 2 variants for validation).

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

### iron-requirements.json — Settled Rules (Authority = 1)

Located at `docs/phase-1-research/iron-requirements.json`. Contains functional and
performance requirements that are absolute rules for ALL downstream phases.

Each iron requirement MUST have:
- `"id"`: `"REQ-F-NNN"` (functional) or `"REQ-P-NNN"` (performance) — unique, sequential
- `"type"`: `"functional"` or `"performance"`
- `"description"`: what the requirement is
- `"priority"`: `"must"` | `"should"` | `"may"`
- `"source"`: `{"document": "...", "section": "...", "line": N}` for traceability
- `"acceptance_criteria"`: array of **measurable** criteria (reject vague terms like "should support", "adequate", "sufficient")
- `"violation_policy"`: `"user_escalation"` (all P1 iron requirements use this)

### open-requirements.json — Research Homework for Phase 2

Located at `docs/phase-1-research/open-requirements.json`. Contains research topics
that Phase 2 must investigate and resolve into architecture decisions.

Each open item MUST have:
- `"id"`: `"OPEN-1-NNN"` — sequential
- `"topic"`: what needs to be investigated
- `"context"`: why this is an open question
- `"candidates"`: array of ≥ 2 candidates (single candidate = not a research topic)
- `"evaluation_criteria"`: metrics Phase 2 should use for comparison
- `"related_iron"`: array of REQ-F/REQ-P IDs that constrain this research
- `"resolution_expected"`: how this should be resolved in Phase 2

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

## Spec Feature Completeness Audit

Phase 1 spec analysis MUST enumerate ALL features defined in the specification and track
their implementation status throughout the pipeline:

1. **Feature enumeration**: Extract every algorithm, mode, format, or capability from the spec
   - Example: intra prediction modes, encoding modes, color formats, block sizes
   - Assign each feature a REQ-F-* ID in iron-requirements.json

2. **Reference model coverage check** (if ref model exists at P1 or provided externally):
   - Compare spec feature list against ref model implementation
   - enum/define declarations vs actual function implementations
   - "Enum declared but function not implemented" → COVERAGE_GAP warning

3. **Gap escalation**: When feature coverage < 100%, MUST ask user via AskUserQuestion:
   - "Spec defines N features but model implements M. Omitting K features may reduce
     [quality metric]. Approve omission?"
   - User-approved omissions → record in ADR with rationale and impact estimate
   - Unapproved omissions → feature stays in iron-requirements as MUST_IMPLEMENT

4. **Documentation**: Save `docs/phase-1-research/feature-coverage.md`:
   ```
   | Feature | Spec Count | Model Count | Coverage | Status |
   |---------|-----------|-------------|----------|--------|
   | Intra modes | 8 | 4 | 50% | USER_APPROVED / MUST_IMPLEMENT |
   ```

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

### Protocol

1. **Step 7.6**: Spawn adversarial spec-analyst (separate Task, clean context) to challenge
   iron-requirements.json. References items by `source.section`, not REQ ID.
   Output: `challenge-report.json` in `.rat/scratch/stability/phase-1/`.
   Schema: `skills/p1-spec-research/templates/challenge-report-schema.json`.
   Budget: max 30 challenges per pass.
2. **Step 7.7**: Present HIGH challenges to user (AskUserQuestion). MEDIUM batched if >10.
   LOW auto-documented. User may mark challenges as NOT_GENUINE (forced disagreements).
3. **Step 7.8**: Re-run spec-analyst with original spec + clarifications → all 4 canonical artifacts
   (iron-requirements.json, open-requirements.json, io_definition.json, timing_constraints.json)
   + self-validation.
4. **Step 7.9**: Gate check + stability report.

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
