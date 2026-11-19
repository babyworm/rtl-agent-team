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

### Light review
One review against the evidence, then stop and name the open items. A further pass runs only when the user asks. Phase 1 has no measurement: the model's confidence is the gate. A ref-model run or a BFM comparison is judged from that result. Confidence does not override a mismatch.
  Phase 1 (Research): one chief review
  Phase 2 (Architecture): one review — memory, performance, ref model
  Phase 3 (μArch): one review — performance, interface, memory

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
- Quality Gate failure: report the findings. Another attempt runs only when the user asks.
- Upper-spec violation: IMMEDIATE STOP, return to violated upper phase

### Context Preload
Before each phase, verify required upstream files exist (specific file lists defined inline in orchestrator steps).

### Scratchpad Convention
During a phase:
  `.rat/scratch/phase-{N}/{agent}.md`
The coordinator reads those notes once and writes the review.
On phase gate PASS: consolidated review saved to reviews/, scratch cleaned.

### Termination
After Phase 3 Quality Gate PASS, generate summary + ADR, then STOP.
Do NOT proceed to Phase 4.

## Phase Gate Definitions

### Phase 1→2 (Research → Architecture)
**Artifact Gate**: iron-requirements.json (required; open-requirements.json optional) + io_definition.json + timing_constraints.json + domain-analysis.md exist
**Quality Gate**:
- One chief review done, with open items named (or the user accepted the gaps)
- Confidence is high (the spec has one reading), or the user answered the one question about the remaining ambiguity. Do not block in order to re-score.
- spec-analyst self-reviews iron-requirements.json and open-requirements.json if present (completeness, consistency)
  - Save: `reviews/phase-1-research/research-review.md`
- arch-designer evaluates implementation feasibility
- `reviews/phase-1-research/research-review.md`
- `docs/phase-1-research/ambiguity-assessment.md` exists with per-axis scores
- **Verdict**: PASS if the one review is recorded AND confidence is high, or the user accepted the named ambiguity, AND requirements are clear, consistent, and implementable

**Summary Validation**: `docs/phase-1-research/phase-1-summary.md`

### Phase 2→3 (Architecture → μArch)
**Artifact Gate**: architecture.md (with D2 block diagram) + refc/*/*.c exist
**Quality Gate**:
- One review recorded, or the user accepted the open items
- Feature Coverage: 100% REQ-NNN mapped to architecture blocks
  - Save: `reviews/phase-2-architecture/feature-coverage.md`
- Memory access review PASS
- Architecture ↔ ref model consistency PASS
- Architecture Diagram saved
- Wonder log names high-risk assumptions (`docs/phase-2-architecture/wonder-log.md`)
- Save: `reviews/phase-2-architecture/architecture-review.md` (accept or reject, with a reason, for each finding)
- **Verdict**: PASS if feature coverage is complete and the one review is recorded. Open items are reported, not sent to another review.

**Phase 2 review** (once, coordinated by rtl-architect):
- Parallel reviewers: rtl-architect, vcodec-architecture-expert, ref-model-dev
- One review covers the cross-block interfaces and memory conflicts
- Report remaining critical findings to the user. Do not open another review.

**Summary + ADR**: phase-2-summary.md + 3-5 ADRs in docs/decisions/

### Phase 3 Completion (μArch → Human Review)
**Artifact Gate**: docs/phase-3-uarch/*.md + bfm/ directory exist
**Quality Gate**:
- One review recorded, or the user accepted the open items
- Feature Preservation: 100% of architecture features preserved in μArch
  - Save: `reviews/phase-3-uarch/feature-preservation.md`
- Block boundary alignment: 1:1 with architecture.md
- μArch ↔ ref model consistency PASS
- Pipeline Diagram saved
- Wonder log names high-risk assumptions (`docs/phase-3-uarch/wonder-log.md`)
- Upstream feedback report generated (`docs/phase-3-uarch/upstream-feedback-report.md`)
- Save: `reviews/phase-3-uarch/uarch-review.md` (accept or reject, with a reason, for each finding)
- **Verdict**: PASS if preservation is complete and the one review is recorded. Open items are reported.

**Phase 3 review** (once, coordinated by rtl-architect):
- Parallel reviewers: rtl-architect, timing-advisor, the domain expert when one exists, ref-model-dev
- One review covers model consistency and cross-module interfaces
- Report remaining critical findings to the user. Do not open another review.

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
3. Do not start that re-run unless the user asks
4. Record which generation the user accepted

### Requirement Similarity
After a user-asked re-run, report:
- requirement_similarity, how much P3 still changes P1
- architecture_similarity, how much P3 still changes P2
Name the difference. Do not start another pass.

## Review

P2 and P3 each get one review. Name the open items and stop.

## Handoff Checklist (to rat-p4p5-impl-verify)
- [ ] Phase 3 summary exists: `docs/phase-3-uarch/phase-3-summary.md`
- [ ] All μArch specs exist: `docs/phase-3-uarch/{module}.md` for each module
- [ ] Phase 3 review passed: `reviews/phase-3-uarch/uarch-review.md` verdict=PASS
- [ ] Feature preservation verified: `reviews/phase-3-uarch/feature-preservation.md`
- [ ] State file updated: `.rat/state/{module}-phase-3-complete.json`
- [ ] Context preload files verified: Phase 4 required upstream files exist

## Escalation & Stop Conditions

- Phase 1 quality gate fails → ask the user to clarify the spec
- Phase 2 quality gate fails → ask the user for the architecture direction
- Phase 3 quality gate fails → ask the user for the μArch decision
- Upper-spec violation detected → STOP and report to user immediately
- Missing information → use AskUserQuestion

## Coding Convention Summary

- Port prefix: `i_`, `o_`, `io_`. Clock: `{domain}_clk`. Reset: `{domain}_rst_n`
- `snake_case` or `ALL_CAPS` only. Parameters `ALL_CAPS`, localparam `L_` prefix
- Instance `u_`, generate `gen_`, `logic` only
- SV RTL: IEEE 1800-2009. C ref model: C11

## Final Checklist

- [ ] Phase 1: iron-requirements.json (open-requirements.json optional), io_definition.json, timing_constraints.json, domain-analysis.md exist
- [ ] Phase 1: research-review.md verdict=PASS, phase-1-summary.md generated
- [ ] Phase 1: ambiguity-assessment.md saved. High confidence passes, or the user answered the one question
- [ ] Phase 2: architecture.md with proper naming, refc/*/*.c exist
- [ ] Phase 2: architecture-review.md PASS, feature-coverage.md 100%
- [ ] Phase 2: phase-2-summary.md generated, ADRs recorded
- [ ] Phase 3: docs/phase-3-uarch/*.md exist, bfm/ directory exists
- [ ] Phase 3: uarch-review.md PASS, feature-preservation.md 100%
- [ ] Phase 3: phase-3-summary.md generated, ADRs recorded
- [ ] Phase 3: wonder-log.md exists, upstream-feedback-report.md generated
- [ ] Phase 3: requirement-delta.md generated (Phase Coherence Check Step 4.5)
- [ ] Phase Coherence Check passed (all REQs implementable or user-approved deltas)
- [ ] Scratch directories cleaned
- [ ] State file updated with all phases completed
- [ ] Pipeline did NOT proceed to Phase 4
