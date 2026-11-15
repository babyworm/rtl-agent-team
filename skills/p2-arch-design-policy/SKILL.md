---
name: p2-arch-design-policy
description: "Internal reference: p2 arch design policy (agent-loaded; do not invoke)."
user-invocable: false
---

# Phase 2 Architecture Design Policy

## P1 Algorithm Candidate HW Review Criteria

For each functional area's candidates from P1's domain-analysis.md, evaluate:
- Gate count estimate (from literature or analytical estimation)
- Critical path depth (combinational logic levels)
- SRAM requirements (capacity, banking, port count)
- External memory bandwidth (bytes/pixel, access patterns)
- Achievable throughput at target frequency (pixels/cycle, blocks/cycle)
- Implementation risk (tool support, verification complexity, proven vs novel)

## Architecture Review

One review, coordinated by rtl-architect. A further pass runs only when the user asks.
- **3 reviewers, in parallel, once**:
  (a) rtl-architect: spec compliance (Feature Coverage Checklist) + structural review
  (b) vcodec-architecture-expert: memory access patterns, performance analysis
  (c) ref-model-dev: architecture ↔ C model consistency (block mapping, data flow, interfaces)
- **+1 conditional reviewer**:
  (d) ref-model-reviewer: C model quality (algorithm fidelity, numerical precision,
      undefined behavior/build warning risk) when the ref model is new or more than 30% of its lines changed.
      Skip it when the ref model is unchanged.
- Record accept or reject, with a reason, for each finding in `architecture-review.md`.
- Name open items, including a cross-block interface or memory conflict. Do not open another review.

## Architecture Naming Conventions

- Block names: `snake_case` (become RTL module names in Phase 4)
- Interface descriptions: data width, protocol type, direction — NOT RTL port naming
- RTL naming conventions (i_/o_ prefix, clock/reset naming) applied in Phase 4, not here

## HW Candidate Review Format

`docs/phase-2-architecture/hw-candidate-review.md` must contain:
1. Per functional area: candidate list with algorithm description
2. Comparison matrix columns: gate count, critical path depth, SRAM requirements,
   external memory BW, throughput at target freq, memory latency impact, implementation risk
3. Selected candidate per area with REQ-NNN justification
4. User decision record when more than one candidate still fits (AskUserQuestion response). A single fitting choice is recorded without a question.

## Bandwidth Analysis Workflow

- ref-model produces bandwidth_report.json during Step 3
- arch-designer consumes bandwidth_report.json during Step 4 (after synchronization)
- If bandwidth exceeds limits → adjust block partitioning or PARALLEL_LANES before review

## Memory Architecture Classification

Each block's storage elements must be classified at architecture level:
- **Local storage**: SRAM or register file (Phase 3 specifies exact type: SP/TP/DP wrapper)
- **Cross-domain storage**: flag for dual-clock SRAM (DP) when read and write are in different clock domains
- **External memory**: DDR/HBM accessed via bus interface

Architecture does NOT select wrapper types (that is Phase 3 μArch responsibility), but MUST identify:
- Estimated capacity per block (bits = depth × width)
- Port count requirement (1 R/W, simultaneous R+W, multi-port)
- Clock domain: same domain (→ SP or TP in Phase 3) vs cross-domain (→ DP in Phase 3)

## Memory Access Latency Awareness

Architecture review must verify:
- Per-block latency budget distinguishes compute cycles vs memory access cycles
- Default assumptions: internal memory = 1 cycle, external memory = 500 cycles
- MEM_LATENCY_EXTERNAL is parameterizable (design-specific, technology-dependent)
- Blocks with heavy external memory access have documented latency hiding strategy
  (prefetch, double buffering, pipelining, or accepted latency penalty with justification)
- bandwidth_report.json estimated cycle counts validated against timing_constraints.json budgets
- Comparison of estimated latency WITH and WITHOUT latency hiding, to quantify strategy benefit

## Assumptions

The review records unvalidated assumptions in `docs/phase-2-architecture/wonder-log.md` (assumption, domain, risk). Name high-risk items. Do not open another review to clear them.

## Escalation & Stop Conditions

- Open items after the one review → ask the user
- Domain constraint conflict → document conflict, ask user for priority
- Memory access infeasible (bandwidth exceeds technology) → escalate, propose alternative
- Architecture ↔ ref model fundamental mismatch → escalate, may require ref model rewrite

## Architecture Feature Completeness Gate

Phase 2 architecture review MUST verify that ALL spec features flow through to the design:

1. **Spec-to-architecture mapping**: Every REQ-F-* from P1 must map to an architecture block
   - Missing mapping → CRITICAL finding (spec feature not architected)

2. **Ref model-to-architecture alignment**: When C reference model exists:
   - Compare ref model function coverage against spec feature list
   - "Enum declared but not called in any function" → COVERAGE_GAP
   - Escalate gaps to user: "Spec feature X exists in enum but ref model doesn't implement it"

3. **Omission justification**: Spec features omitted from architecture require:
   - User-approved ADR from Phase 1 (with documented impact)
   - ADR-less omissions → Phase 2 gate FAIL

4. **Impact quantification** (domain-specific):
   - Codec: BD-rate impact of omitted modes/tools
   - Processor: missing instruction coverage
   - Generic: functional coverage percentage vs spec

## Open Resolution Protocol

Phase 2 receives `docs/phase-1-research/open-requirements.json` containing OPEN-1-* research topics.
For each OPEN-1-* item, the architecture team must:

1. Conduct architecture research using the item's `candidates` and `evaluation_criteria`
2. Select a winner with quantitative justification (gate count, throughput, area, etc.)
3. Record the decision in `docs/phase-2-architecture/iron-requirements.json` (REQ-A-*) with:
   - `resolved_from`: the OPEN-1-* ID that was resolved
   - `resolution_rationale`: why this candidate was selected
   - `rejected_alternatives`: all non-selected candidates with rejection reasons
   - `upstream_compliance`: verification that new REQ-A-* does not violate P1 iron
   - `violation_policy`: `"agent_retry"` (authority=2)
   - `acceptance_criteria`: measurable criteria for the architectural decision
4. A high-confidence choice is recorded and the item is resolved. A low-confidence item is asked once. Do not research again to manufacture a winner.

Phase 2 may also produce `docs/phase-2-architecture/open-requirements.json` (OPEN-2-*) for
research topics to be resolved by Phase 3 (e.g., micro-architecture choices).

## Compliance Check Procedure

After `docs/phase-2-architecture/iron-requirements.json` (REQ-A-*) is finalized:

1. Invoke compliance-checker agent with:
   - `upstream_iron`: `["docs/phase-1-research/iron-requirements.json"]`
   - `target_artifacts`: Phase 2 output artifacts
2. Gate: compliance-report.json verdict must be PASS
3. On VIOLATION: enter authority-differentiated escalation ladder
   - Authority 1 (P1 functional): Custom budget: Primary 3 + Fallback 2 + Last-chance 1
   - Authority 2 (P2 architecture): Custom budget: Primary 4 + Fallback 3 + Last-chance 1

## Upstream Challenge Protocol

If compliance VIOLATION persists after Primary stage and is technically infeasible:
1. Orchestrator produces infeasibility assessment with quantitative evidence
2. Compliance-checker validates the infeasibility claim
3. If validated: produce upstream challenge report with PPA estimates
   - Required fields: frequency_mhz, area_gate_count, pixel_rate_mpps, achievable_fps
4. Present challenge to user via AskUserQuestion with comparison table

## Confidence (Phase 2)

A REQ-A-* is iron when confidence is high: one architecture choice fits the evidence and the others do not. Record that confidence. Do not score again to become more sure. A choice where more than one candidate still fits stays open: name them and ask once. The user's answer is the decision. This check satisfies `ambiguity-pass`. The choice itself has no measurement. A ref-model run, a bitexact comparison, and `bandwidth_report.json` are measurements: the measured result is the judgment, and confidence does not override a mismatch.

## Final Checklist

- [ ] docs/phase-2-architecture/hw-candidate-review.md exists with per-block selection + HW rationale
- [ ] P1 algorithm candidates reviewed from HW perspective
- [ ] architecture.md exists with all blocks and data paths
- [ ] architecture.md includes D2 block diagram
- [ ] Every REQ (REQ-F-*, REQ-P-*, REQ-A-*) mapped to at least one architecture block
- [ ] One architecture review completed, or the open items were reported to the user
- [ ] Memory access patterns reviewed for all large blocks
- [ ] Architecture ↔ ref model consistency verified
- [ ] Ref model code reviewed for quality and bitexact correctness
- [ ] reviews/phase-2-architecture/ref-model-review.md saved when ref model changed
- [ ] bandwidth_report.json reviewed, external memory bandwidth validated
- [ ] Internal vs external memory classified per block
- [ ] C model executed and verified — architecture produces correct results
- [ ] reviews/phase-2-architecture/feature-coverage.md saved
- [ ] reviews/phase-2-architecture/architecture-review.md saved (consolidated)
- [ ] reviews/phase-2-architecture/architecture-diagram.md saved (D2)
- [ ] docs/decisions/ADR-*.md generated (3-5 key architectural decisions)
- [ ] `docs/phase-2-architecture/wonder-log.md` names the unvalidated assumptions
- [ ] All High-risk assumptions in wonder-log resolved or explicitly accepted
- [ ] `reviews/phase-2-architecture/architecture-review.md` saved
- [ ] All OPEN-1-* items from P1 resolved with rationale and rejected_alternatives
- [ ] `docs/phase-2-architecture/iron-requirements.json` exists with REQ-A-* entries and resolved_from tracking
- [ ] Compliance check against P1 iron: verdict = PASS
- [ ] Each REQ-A-* is high confidence, or the user chose among the named alternatives (`ambiguity-pass`)
- [ ] `docs/phase-2-architecture/open-requirements.json` (OPEN-2-*) created for Phase 3 homework (if any)
