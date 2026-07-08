---
name: rat-p1p3-spec-uarch-policy
description: "Internal reference: rat p1p3 spec uarch policy (agent-loaded; do not invoke)."
user-invocable: false
---

# Spec-to-μArch Policy

## Core Principles

### Hierarchical Spec Compliance
Lower phases MUST NOT violate upper phase specifications:
  Spec → Architecture → μArch
Each phase strictly adheres to decisions made in all preceding phases.
Deletion, reduction, or modification of features for convenience is FORBIDDEN.
If a change is needed, control returns to the upper phase for approval.

### Design Priority Order
1. Functional Correctness (highest) — Every required feature works exactly
2. Interface Compliance — Ports, protocols, timing match Architecture
3. Timing/Performance — Throughput, latency targets met
4. Area/Power (lowest)

### Cascading Quality
Higher abstraction levels demand MORE iterative refinement.
Dynamic convergence with graduated minimums:
  Phase 1 (Research): min 3 rounds (chief-coordinated, fixed — P1 is the quality foundation)
  Phase 2 (Architecture): min 2, max 5 rounds — memory, performance, ref model consistency
  Phase 3 (μArch): min 2, max 5 rounds — performance, interface, memory optimization

P2/P3 use convergence criteria (finding_delta < 0.1, critical resolved, wonder stable).
Principle: **refine thoroughly at the top, execute efficiently at the bottom.**

### Document-as-Memory
Design artifacts serve as persistent memory. Each phase reads upstream documents and writes
downstream documents. State at `.rat/state/rat-p1p3-spec-uarch-state.json`.

## Execution Rules

### Dual-Layer Phase Gates
Every phase transition requires BOTH:
1. **Artifact Gate**: Required files exist
2. **Quality Gate**: Reviewer(s) verify quality AND hierarchical spec compliance

### Gate Retry Policy
- Artifact Gate failure: retry phase once, then escalate to user
- Quality Gate failure: pass findings to worker, re-run gate. Max 2 retries
- Upper-spec violation: IMMEDIATE STOP, return to violated upper phase

### Context Preload
Before each phase, verify required upstream files exist (specific file lists defined inline in orchestrator steps).

### Scratchpad Convention
During iterative review rounds:
  `.rat/scratch/phase-{N}/round-{R}-{agent}.md`
Coordinator reads all round files to aggregate feedback.
On phase gate PASS: consolidated review saved to reviews/, scratch cleaned.

### Termination
After Phase 3 Quality Gate PASS, generate summary + ADR, then STOP.
Do NOT proceed to Phase 4.

## Phase Gate Definitions

### Phase 1→2 (Research → Architecture)
**Artifact Gate**: requirements.json + io_definition.json + timing_constraints.json + domain-analysis.md exist
**Quality Gate**:
- 3-round chief review converged (or gaps escalated and user-approved)
- Ambiguity Gate passed: ambiguity_score ≤ 0.5 (BLOCK if > 0.5)
- spec-analyst self-reviews requirements.json (completeness, consistency)
  - Save: `reviews/phase-1-research/research-review.md`
- arch-designer evaluates implementation feasibility
- Per-round review artifacts: `reviews/phase-1-research/research-review-r1.md`, `r2.md`, `r3.md` (mandatory)
- `docs/phase-1-research/ambiguity-assessment.md` exists with per-axis scores
- **Verdict**: PASS if 3-round review converged AND ambiguity gate passed AND all requirements clear, consistent, and implementable

**Summary Validation**: `docs/phase-1-research/phase-1-summary.md`

### Phase 2→3 (Architecture → μArch)
**Artifact Gate**: architecture.md (with D2 block diagram) + refc/*/*.c exist
**Quality Gate**:
- Dynamic convergence review converged (min 2 rounds, or user-approved)
- Feature Coverage: 100% REQ-NNN mapped to architecture blocks
  - Save: `reviews/phase-2-architecture/feature-coverage.md`
- Memory access review PASS
- Architecture ↔ ref model consistency PASS
- Architecture Diagram saved
- Wonder log: all High-risk assumptions resolved (`docs/phase-2-architecture/wonder-log.md`)
- Per-round review artifacts: `reviews/phase-2-architecture/architecture-review-r1.md`, `r2.md` (minimum), additional rounds if needed
- Save: `reviews/phase-2-architecture/architecture-review.md`
- **Verdict**: PASS if 100% feature coverage AND no structural defects AND review converged AND wonder stable

**Phase 2 Iterative Review** (dynamic convergence, coordinated by rtl-architect):
- Parallel reviewers: rtl-architect + vcodec-architecture-expert + ref-model-dev
- Each round: review → wonder step → rebuttal (designer accepts/rejects each finding with rationale) → targeted revision (only accepted findings applied; rejections recorded in per-round artifact)
- Last round (converged or max): cross-block interface audit + memory conflict analysis
- Convergence: finding_delta < 0.1, all critical resolved, wonder stable (min 2, max 5 rounds)
- After max_rounds not converged → escalate to user

**Summary + ADR**: phase-2-summary.md + 3-5 ADRs in docs/decisions/

### Phase 3 Completion (μArch → Human Review)
**Artifact Gate**: docs/phase-3-uarch/*.md + bfm/ directory exist
**Quality Gate**:
- Dynamic convergence review converged (min 2 rounds, or user-approved)
- Feature Preservation: 100% of architecture features preserved in μArch
  - Save: `reviews/phase-3-uarch/feature-preservation.md`
- Block boundary alignment: 1:1 with architecture.md
- μArch ↔ ref model consistency PASS
- Pipeline Diagram saved
- Wonder log: all High-risk assumptions resolved (`docs/phase-3-uarch/wonder-log.md`)
- Upstream feedback report generated (`docs/phase-3-uarch/upstream-feedback-report.md`)
- Per-round review artifacts: `reviews/phase-3-uarch/uarch-review-r1.md`, `r2.md` (minimum), additional rounds if needed
- Save: `reviews/phase-3-uarch/uarch-review.md`
- **Verdict**: PASS if 100% preservation AND timing reasonable AND review converged AND wonder stable

**Phase 3 Iterative Review** (dynamic convergence, coordinated by rtl-architect):
- Parallel reviewers: rtl-architect + timing-advisor + vcodec-architecture-expert + ref-model-dev
- Each round: review → wonder step → rebuttal (designer accepts/rejects each finding with rationale) → targeted revision (only accepted findings applied; rejections recorded in per-round artifact)
- Last round (converged or max): model consistency matrix + cross-module interface audit
- Convergence: finding_delta < 0.1, all critical resolved, wonder stable (min 2, max 5 rounds)
- After max_rounds not converged → escalate to user

**Summary + ADR**: phase-3-summary.md + 3-5 ADRs in docs/decisions/

## Phase Feedback Loop Protocol

### Forward Flow (Normal)
P1 → P2 → P3: Each phase reads upstream artifacts, writes downstream.

### Backward Flow (Coherence Failure)
When P3 discovers P1 requirement gaps:

1. P3 generates `requirement-delta.md` (Step 4.5 of spec-to-uarch-orchestrator)
2. If delta contains MODIFY, ADD, or DROP actions:
   a. Orchestrator sets `upper_spec_blocking: true`
   b. User is consulted via AskUserQuestion
   c. If user approves revision: P1 re-runs with delta as input
   d. P2 re-runs reading updated P1 artifacts
   e. P3 re-runs reading updated P2 artifacts
3. Maximum feedback iterations: 2 (then escalate to user regardless)
4. Each iteration records generation number for traceability

### Requirement Similarity Convergence
After feedback loop iteration:
- requirement_similarity ≥ 0.95 (P3 barely changes P1) → converged
- architecture_similarity ≥ 0.95 (P3 barely changes P2) → converged
- Otherwise → another iteration (up to max 2)

## Review Convergence Criteria

Review rounds within P2 and P3 use dynamic convergence instead of fixed 3 rounds:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| min_rounds | 2 | Minimum for meaningful review |
| max_rounds | 5 | Prevent infinite loops |
| finding_delta_threshold | 0.1 | < 10% new findings = stable |
| critical_resolution | ALL | All Critical/High must be resolved |
| wonder_stability | true | No new High-risk assumptions |

## Handoff Checklist (to rat-p4p5-impl-verify)
- [ ] Phase 3 summary exists: `docs/phase-3-uarch/phase-3-summary.md`
- [ ] All μArch specs exist: `docs/phase-3-uarch/{module}.md` for each module
- [ ] Phase 3 review passed: `reviews/phase-3-uarch/uarch-review.md` verdict=PASS
- [ ] Feature preservation verified: `reviews/phase-3-uarch/feature-preservation.md`
- [ ] State file updated: `.rat/state/{module}-phase-3-complete.json`
- [ ] Context preload files verified: Phase 4 required upstream files exist

## Escalation & Stop Conditions

- Phase 1 Quality Gate fails after 2 retries → ask user to clarify/refine spec
- Phase 2 Quality Gate fails after 2 retries → ask user for architecture direction
- Phase 3 Quality Gate fails after 2 retries → ask user for μArch decisions
- Upper-spec violation detected → STOP and report to user immediately
- Missing information → use AskUserQuestion

## Coding Convention Summary

- Port prefix: `i_`, `o_`, `io_`. Clock: `{domain}_clk`. Reset: `{domain}_rst_n`
- `snake_case` or `ALL_CAPS` only. Parameters `ALL_CAPS`, localparam `L_` prefix
- Instance `u_`, generate `gen_`, `logic` only
- SV RTL: IEEE 1800-2009. C ref model: C11

## Final Checklist

- [ ] Phase 1: requirements.json, io_definition.json, timing_constraints.json, domain-analysis.md exist
- [ ] Phase 1: research-review.md verdict=PASS, per-round reviews (r1-r3) saved, phase-1-summary.md generated
- [ ] Phase 1: ambiguity-assessment.md saved with ambiguity_score ≤ 0.5
- [ ] Phase 2: architecture.md with proper naming, refc/*/*.c exist
- [ ] Phase 2: architecture-review.md PASS, per-round reviews (r1-r3) saved, feature-coverage.md 100%
- [ ] Phase 2: phase-2-summary.md generated, ADRs recorded
- [ ] Phase 3: docs/phase-3-uarch/*.md exist, bfm/ directory exists
- [ ] Phase 3: uarch-review.md PASS, per-round reviews (r1-r3) saved, feature-preservation.md 100%
- [ ] Phase 3: phase-3-summary.md generated, ADRs recorded
- [ ] Phase 3: wonder-log.md exists, upstream-feedback-report.md generated
- [ ] Phase 3: requirement-delta.md generated (Phase Coherence Check Step 4.5)
- [ ] Phase Coherence Check passed (all REQs implementable or user-approved deltas)
- [ ] Scratch directories cleaned
- [ ] State file updated with all phases completed
- [ ] Pipeline did NOT proceed to Phase 4
