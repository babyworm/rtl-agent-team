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
- [ ] Every iron requirement has measurable acceptance_criteria (no vague terms)
- [ ] Every iron requirement has `"violation_policy": "user_escalation"`
- [ ] Every open item has ≥ 2 candidates and evaluation_criteria
- [ ] Every open item has target_phase specified
- [ ] Iron/open classification verification passed (no FAIL conditions)
