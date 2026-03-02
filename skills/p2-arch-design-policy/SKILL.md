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

## Architecture Review Criteria (3-Round Protocol)

3-round mandatory, coordinated by rtl-architect:
- **3 parallel reviewers each round**:
  (a) rtl-architect: spec compliance (Feature Coverage Checklist) + structural review
  (b) vcodec-architecture-expert: memory access patterns, performance analysis
  (c) ref-model-dev: architecture ↔ C model consistency (block mapping, data flow, interfaces)
- Round 1-2: review → tree exploration for issues → targeted revision
- Round 3 mandatory even if converged: cross-block interface audit + memory conflict analysis
- After 3 rounds if not converged → escalate to user via AskUserQuestion

## Architecture Naming Conventions

- Block names: `snake_case` (become RTL module names in Phase 4)
- Interface descriptions: data width, protocol type, direction — NOT RTL port naming
- RTL naming conventions (i_/o_ prefix, clock/reset naming) applied in Phase 4, not here

## Bandwidth Analysis Workflow

- ref-model produces bandwidth_report.json during Step 3
- arch-designer consumes bandwidth_report.json during Step 4 (after synchronization)
- If bandwidth exceeds limits → adjust block partitioning or PARALLEL_LANES before review

## Escalation & Stop Conditions

- 3-round review completed but issues remain → escalate to user via AskUserQuestion
- Domain constraint conflict → document conflict, ask user for priority
- Memory access infeasible (bandwidth exceeds technology) → escalate, propose alternative
- Architecture ↔ ref model fundamental mismatch → escalate, may require ref model rewrite

## Final Checklist

- [ ] docs/phase-2-architecture/hw-candidate-review.md exists with per-block selection + HW rationale
- [ ] P1 algorithm candidates reviewed from HW perspective
- [ ] architecture.md exists with all blocks and data paths
- [ ] block_diagram exists (D2)
- [ ] Every REQ-NNN mapped to at least one architecture block
- [ ] 3-round iterative review completed (or gaps escalated and approved)
- [ ] Memory access patterns reviewed for all large blocks
- [ ] Architecture ↔ ref model consistency verified
- [ ] Ref model code reviewed for quality and bitexact correctness
- [ ] bandwidth_report.json reviewed, external memory bandwidth validated
- [ ] Internal vs external memory classified per block
- [ ] C model executed and verified — architecture produces correct results
- [ ] Tree exploration used for issue resolution in each review round
- [ ] Per-round review artifacts saved (r1.md, r2.md, r3.md)
- [ ] reviews/phase-2-architecture/feature-coverage.md saved
- [ ] reviews/phase-2-architecture/architecture-review.md saved (consolidated)
- [ ] reviews/phase-2-architecture/architecture-diagram.md saved (D2)
