---
name: p2-arch-design-policy
description: "Architecture review criteria, HW candidate evaluation methodology, naming conventions, and checklists for the Phase 2 architecture design pipeline. Pure reference — no orchestration."
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

## Architecture Review Criteria (Dynamic Convergence Protocol)

Dynamic convergence review (min 2, max 5 rounds), coordinated by rtl-architect:
- **3 mandatory parallel reviewers each round**:
  (a) rtl-architect: spec compliance (Feature Coverage Checklist) + structural review
  (b) vcodec-architecture-expert: memory access patterns, performance analysis
  (c) ref-model-dev: architecture ↔ C model consistency (block mapping, data flow, interfaces)
- **+1 conditional reviewer**:
  (d) ref-model-reviewer: independent C model quality gate (algorithm fidelity, numerical precision,
      undefined behavior/build warning risk) when ref model is newly created or substantially revised
- **ref-model-reviewer activation threshold**: Invoke when ref model is newly created OR
  >30% of source lines changed from prior version. Both sequential and team orchestrators
  use this same threshold. Skip review tasks when ref model is unchanged.
- Each round: review → rebuttal (designer accepts/rejects each finding with rationale) → tree exploration for issues → targeted revision (rejections recorded in per-round artifact)
- Last round (converged or max reached): cross-block interface audit + memory conflict analysis
- Convergence check after round >= min_rounds: finding_delta < 0.1, all critical resolved, wonder stable
- After max_rounds if not converged → escalate to user via AskUserQuestion

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
4. User decision record (AskUserQuestion response summary)

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

## Wonder Log (Required)

Each review round MUST produce a wonder-log entry:
- File: `docs/phase-2-architecture/wonder-log.md`
- Format: Markdown table with columns: Round, Assumption, Domain, Risk(H/M/L), Resolution
- Purpose: Track unvalidated assumptions across rounds
- Exit gate: All High-risk assumptions must be resolved or explicitly accepted before phase completion

## Review Convergence Criteria

Review rounds use dynamic convergence instead of fixed 3 rounds:

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| min_rounds | 2 | Minimum for meaningful review |
| max_rounds | 5 | Prevent infinite loops |
| finding_delta_threshold | 0.1 | < 10% new findings = stable |
| critical_resolution | ALL | All Critical/High must be resolved |
| wonder_stability | true | No new High-risk assumptions |

**Early exit** (round 2): When findings converge quickly (simple designs)
**Extended review** (rounds 4-5): For complex designs with emergent issues

This is inspired by Ouroboros's ConvergenceCriteria:
- Stability signal: finding_delta < threshold
- Stagnation detection: same findings repeated across rounds
- Oscillation detection: finding toggling resolved↔reopened

## Escalation & Stop Conditions

- max_rounds reached but issues remain → escalate to user via AskUserQuestion
- Domain constraint conflict → document conflict, ask user for priority
- Memory access infeasible (bandwidth exceeds technology) → escalate, propose alternative
- Architecture ↔ ref model fundamental mismatch → escalate, may require ref model rewrite

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
4. Verify: ALL OPEN-1-* items must be resolved before Phase 2 exit

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

## Ambiguity Gate (Phase 2)

Apply ambiguity scoring to all new REQ-A-* decisions:
- "Would re-evaluating this architecture produce the same conclusion?"
- Score ≤ 0.5 required before REQ-A-* becomes iron
- Ambiguous decisions cannot be iron

## Final Checklist

- [ ] docs/phase-2-architecture/hw-candidate-review.md exists with per-block selection + HW rationale
- [ ] P1 algorithm candidates reviewed from HW perspective
- [ ] architecture.md exists with all blocks and data paths
- [ ] architecture.md includes D2 block diagram
- [ ] Every REQ (REQ-F-*, REQ-P-*, REQ-A-*) mapped to at least one architecture block
- [ ] Dynamic convergence review completed (min 2 rounds, or gaps escalated and approved)
- [ ] Memory access patterns reviewed for all large blocks
- [ ] Architecture ↔ ref model consistency verified
- [ ] Ref model code reviewed for quality and bitexact correctness
- [ ] reviews/phase-2-architecture/ref-model-review.md saved when ref model changed
- [ ] bandwidth_report.json reviewed, external memory bandwidth validated
- [ ] Internal vs external memory classified per block
- [ ] C model executed and verified — architecture produces correct results
- [ ] Tree exploration used for issue resolution in each review round
- [ ] Per-round review artifacts saved (r1.md, r2.md, and additional rounds if needed)
- [ ] reviews/phase-2-architecture/feature-coverage.md saved
- [ ] reviews/phase-2-architecture/architecture-review.md saved (consolidated)
- [ ] reviews/phase-2-architecture/architecture-diagram.md saved (D2)
- [ ] docs/decisions/ADR-*.md generated (3-5 key architectural decisions)
- [ ] `docs/phase-2-architecture/wonder-log.md` exists with per-round assumption tracking
- [ ] All High-risk assumptions in wonder-log resolved or explicitly accepted
- [ ] Per-round review artifacts saved (r1.md through rN.md, minimum 2 rounds)
- [ ] All OPEN-1-* items from P1 resolved with rationale and rejected_alternatives
- [ ] `docs/phase-2-architecture/iron-requirements.json` exists with REQ-A-* entries and resolved_from tracking
- [ ] Compliance check against P1 iron: verdict = PASS
- [ ] Ambiguity score ≤ 0.5 for all new REQ-A-* requirements
- [ ] `docs/phase-2-architecture/open-requirements.json` (OPEN-2-*) created for Phase 3 homework (if any)
