---
name: rtl-spec-to-uarch-policy
description: "Policy rules, phase gate definitions, cascading quality protocol, handoff checklist, and ADR requirements for the Phase 1→3 pipeline. Pure reference — no orchestration."
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
Graduated iteration:
  Phase 1 (Research): 3 mandatory rounds (chief-coordinated)
  Phase 2 (Architecture): 3 mandatory rounds — memory, performance, ref model consistency
  Phase 3 (μArch): 3 mandatory rounds — performance, interface, memory optimization

Iteration count can be increased beyond 3 if convergence is not achieved.
Principle: **refine thoroughly at the top, execute efficiently at the bottom.**

### Document-as-Memory
Design artifacts serve as persistent memory. Each phase reads upstream documents and writes
downstream documents. State at `.rtl-agent-team/state/rtl-spec-to-uarch-state.json`.

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
  `.rtl-agent-team/scratch/phase-{N}/round-{R}-{agent}.md`
Coordinator reads all round files to aggregate feedback.
On phase gate PASS: consolidated review saved to reviews/, scratch cleaned.

### Termination
After Phase 3 Quality Gate PASS, generate summary + ADR, then STOP.
Do NOT proceed to Phase 4.

## Phase Gate Definitions

### Phase 1→2 (Research → Architecture)
**Artifact Gate**: requirements.json + io_definition.json + domain-analysis.md exist
**Quality Gate**:
- 3-round chief review converged (or gaps escalated and user-approved)
- spec-analyst self-reviews requirements.json (completeness, consistency)
  - Save: `reviews/phase-1-research/research-review.md`
- arch-designer evaluates implementation feasibility
- Per-round review artifacts: `reviews/phase-1-research/research-review-r1.md`, `r2.md`, `r3.md` (mandatory)
- **Verdict**: PASS if 3-round review converged AND all requirements clear, consistent, and implementable

**Summary Validation**: `docs/phase-1-research/phase-1-summary.md`

### Phase 2→3 (Architecture → μArch)
**Artifact Gate**: architecture.md (with D2 block diagram) + refc/*/*.c exist
**Quality Gate**:
- 3-round iterative review converged (or user-approved)
- Feature Coverage: 100% REQ-NNN mapped to architecture blocks
  - Save: `reviews/phase-2-architecture/feature-coverage.md`
- Memory access review PASS
- Architecture ↔ ref model consistency PASS
- Architecture Diagram saved
- Per-round review artifacts: `reviews/phase-2-architecture/architecture-review-r1.md`, `r2.md`, `r3.md` (mandatory)
- Save: `reviews/phase-2-architecture/architecture-review.md`
- **Verdict**: PASS if 100% feature coverage AND no structural defects AND 3-round review converged

**Phase 2 Iterative Review** (3-round, coordinated by rtl-architect):
- Parallel reviewers: rtl-architect + vcodec-architecture-expert + ref-model-dev
- Round 1-2: review → rebuttal (designer accepts/rejects each finding with rationale) → targeted revision (only accepted findings applied; rejections recorded in per-round artifact)
- Round 3 mandatory: cross-block interface audit + memory conflict analysis
- After 3 rounds not converged → escalate to user

**Summary + ADR**: phase-2-summary.md + 3-5 ADRs in docs/decisions/

### Phase 3 Completion (μArch → Human Review)
**Artifact Gate**: docs/phase-3-uarch/*.md + bfm/ directory exist
**Quality Gate**:
- 3-round iterative review converged
- Feature Preservation: 100% of architecture features preserved in μArch
  - Save: `reviews/phase-3-uarch/feature-preservation.md`
- Block boundary alignment: 1:1 with architecture.md
- μArch ↔ ref model consistency PASS
- Pipeline Diagram saved
- Per-round review artifacts: `reviews/phase-3-uarch/uarch-review-r1.md`, `r2.md`, `r3.md` (mandatory)
- Save: `reviews/phase-3-uarch/uarch-review.md`
- **Verdict**: PASS if 100% preservation AND timing reasonable AND 3-round review converged

**Phase 3 Iterative Review** (3-round, coordinated by rtl-architect):
- Parallel reviewers: rtl-architect + timing-advisor + vcodec-architecture-expert + ref-model-dev
- Round 1-2: review → rebuttal (designer accepts/rejects each finding with rationale) → targeted revision (only accepted findings applied; rejections recorded in per-round artifact)
- Round 3 mandatory: model consistency matrix + cross-module interface audit
- After 3 rounds not converged → escalate to user

**Summary + ADR**: phase-3-summary.md + 3-5 ADRs in docs/decisions/

## Handoff Checklist (to rtl-uarch-to-verify)
- [ ] Phase 3 summary exists: `docs/phase-3-uarch/phase-3-summary.md`
- [ ] All μArch specs exist: `docs/phase-3-uarch/{module}.md` for each module
- [ ] Phase 3 review passed: `reviews/phase-3-uarch/uarch-review.md` verdict=PASS
- [ ] Feature preservation verified: `reviews/phase-3-uarch/feature-preservation.md`
- [ ] State file updated: `.rtl-agent-team/state/{module}-phase-3-complete.json`
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

- [ ] Phase 1: requirements.json, io_definition.json, domain-analysis.md exist
- [ ] Phase 1: research-review.md verdict=PASS, per-round reviews (r1-r3) saved, phase-1-summary.md generated
- [ ] Phase 2: architecture.md with proper naming, refc/*/*.c exist
- [ ] Phase 2: architecture-review.md PASS, per-round reviews (r1-r3) saved, feature-coverage.md 100%
- [ ] Phase 2: phase-2-summary.md generated, ADRs recorded
- [ ] Phase 3: docs/phase-3-uarch/*.md exist, bfm/ directory exists
- [ ] Phase 3: uarch-review.md PASS, per-round reviews (r1-r3) saved, feature-preservation.md 100%
- [ ] Phase 3: phase-3-summary.md generated, ADRs recorded
- [ ] Scratch directories cleaned
- [ ] State file updated with all phases completed
- [ ] Pipeline did NOT proceed to Phase 4
