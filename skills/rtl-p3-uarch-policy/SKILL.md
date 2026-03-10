---
name: rtl-p3-uarch-policy
description: "μArch design criteria, clock domain rules, protocol assignment rules, BFM validation requirements, signal naming conventions, and checklists for the Phase 3 μArch design pipeline. Pure reference — no orchestration."
user-invocable: false
---

# Phase 3 μArch Design Policy

## Document Requirements (per-module docs/phase-3-uarch/*.md)

Each module document MUST contain:
1. **Module decomposition**: sub-modules with rationale (or single-module rationale)
2. **Clock domain assignment**: per sub-block, with synchronizer specs for cross-domain
3. **Protocol assignment**: per interface with justification (data rate, latency, backpressure)
4. **Design partitioning**: pipeline stages, resource sharing, parallelism degree
5. **Register/SRAM/FSM allocation**: pipeline regs, config regs, SRAM capacity+banking, FSM state count
6. **Inter/intra-module pipeline**: data flow, handshake, backpressure, hazard analysis
7. **Signal naming**: compliant with conventions below

## REQ→uArch Reverse Traceability

Every P3 run MUST produce `docs/phase-3-uarch/req-uarch-traceability.md` mapping each REQ-NNN
from `docs/phase-1-research/requirements.json` to the uArch module(s) and section(s) implementing it.

Format:
```
| REQ ID   | uArch Module(s)         | Section(s)                  | Status   |
|----------|-------------------------|-----------------------------|----------|
| REQ-001  | intra_pred              | 3.2 Mode Decision FSM       | MAPPED   |
| REQ-002  | deblock_filter, sao     | 2.1 Pipeline, 4.3 SAO Ctrl  | MAPPED   |
| REQ-003  | —                       | —                           | UNMAPPED |
```

- **100% coverage required**: every REQ-NNN must appear. UNMAPPED REQs block the Phase 3 gate.
- **Staleness detection**: when P1 `requirements.json` changes after P3 completion, this table identifies which uArch sections need re-design. The P3 orchestrator uses mtime comparison to detect staleness.

## Clock Domain Assignment Rules

- Every sub-block MUST have an assigned clock domain
- Single-domain: `clk` / `rst_n`
- Multi-domain: `{domain}_clk` / `{domain}_rst_n` (e.g., `sys_clk`, `pixel_clk`)
- Cross-domain interfaces: explicit synchronizer type (2FF, handshake, async FIFO)
- Clock domain map: documented per module (which blocks share clocks, which cross)

## Protocol Assignment Rules

- Every inter-block interface MUST have an assigned protocol
- Supported protocols: valid/ready, AXI-Stream, FIFO, credit-based
- Protocol choice MUST be justified by data rate, latency, and backpressure requirements
- domain-consult invoked when protocol selection is non-obvious

## BFM Validation Requirements (MANDATORY)

- **Default**: blocking transport (LT — Loosely Timed) for fast simulation
- **On request**: non-blocking transport (AT — Approximately Timed) for timing accuracy
- **Per-block I/O logging MANDATORY**: every block input/output transaction logged
  - Format: timestamped records (cycle, address, data, control signals)
  - Logs serve as golden reference for Phase 4-5 RTL unit verification
- BFM must compile and simulate before review begins
- BFM outputs compared against C reference model (refc/)
- If BFM fails: iterate uarch-designer ↔ bfm-dev (max 2 iterations before escalation)

## Conditional Expert Delegation (Phase 3)

- **Invoke rtl-planner** when execution risk is the blocker rather than local RTL details:
  - Module/interface dependency chain is unclear for 5+ blocks
  - BFM and μArch revisions bounce for 2+ cycles with no convergence
  - Critical path or parallelization order is uncertain before Round 2 review
- **Expected rtl-planner output**: explicit task dependency graph, critical path, and
  parallel work groups that the orchestrator can apply to Step 3/5 sequencing.

- **Invoke clock-architect** when clocking strategy is non-trivial:
  - Multiple independent clock roots, generated clocks, PLL/MMCM, or clock muxing
  - Hierarchical clock gating strategy is proposed (ICG depth/placement decisions)
  - timing-advisor or cdc-checker repeatedly flags clock relationship feasibility risks
- **Expected clock-architect output**: review report at
  `reviews/phase-3-uarch/clock-architecture-review.md` and concrete fixes to
  `docs/phase-3-uarch/clock-domain-map.md`.

## Signal Naming Conventions (MANDATORY — flow to RTL)

- Inputs: `i_` prefix (NOT `_i` suffix)
- Outputs: `o_` prefix (NOT `_o` suffix)
- Bidirectional: `io_` prefix
- Clocks: `clk` (single) or `{domain}_clk` — NOT `clk_i`
- Resets: `rst_n` (single) or `{domain}_rst_n` — NOT `rst_ni`
- Instances: `u_` prefix (e.g., `u_fifo`)
- Generates: `gen_` prefix
- FSM states: `typedef enum logic [N:0]` with `UPPER_SNAKE_CASE` values
- Types: `snake_case_t` suffix (e.g., `state_t`, `bus_req_t`)
- Parameters: `UPPER_SNAKE_CASE` (e.g., `DATA_WIDTH`)
- Use `logic` only (no `reg`/`wire`)

## 3-Round Review Protocol (5 parallel reviewers)

Mandatory 3 rounds, coordinated by rtl-architect:
- **4 mandatory + 1 conditional parallel reviewers each round**:
  1. rtl-architect: feature preservation, block boundary, interface, protocol consistency
  2. timing-advisor: critical paths at target frequency, pipeline balance, clock domain feasibility
  3. (conditional) domain architecture expert: algorithm/memory/interface optimization
     — invoke when `domain-packages/{domain}/` exists (e.g., vcodec-architecture-expert for video codec).
     When no domain expert available, rtl-architect covers algorithm consistency in its scope.
  4. ref-model-dev: model consistency (behavior, data widths, fixed-point, I/O log alignment)
  5. bfm-dev: BFM simulation results, I/O logging correctness, protocol behavior

- Round 1-2: review → rebuttal (designer accepts/rejects each finding with rationale) → tree exploration for accepted issues → targeted revision (rejections recorded in per-round artifact)
- Round 3 mandatory: cross-module interface audit, clock domain map consistency,
  memory conflict analysis, model consistency matrix, BFM final pass, μArch code review
- After 3 rounds if not converged → escalate to user via AskUserQuestion
- Conditional reviewers:
  - clock-architect: multi-clock/generated-clock/gating risk present
  - rtl-planner: schedule/dependency risk dominates convergence delays

### Feature Preservation Checklist Format

Save to `reviews/phase-3-uarch/feature-preservation.md`:
```
# Phase 3 Review: Feature Preservation
- Date: YYYY-MM-DD
- Reviewer: rtl-architect
- Upper Spec: architecture.md
- Verdict: PASS | FAIL

## Feature Coverage Checklist
| Feature | Architecture Block | μArch Doc | Status |

## Findings
### [severity] Finding-N: ...

## Verdict
PASS | FAIL: [reason]
```

## Escalation & Stop Conditions

- Timing infeasibility → report to user, propose alternative frequency or architecture change
- FSM cannot represent algorithm state → escalate to p2-arch-design
- Block boundary violation (merge/split not in architecture.md) → escalate to Phase 2
- Functional responsibility missing → uarch-designer adds or escalate if architecture change needed
- Clock domain crossing infeasible → escalate to p2-arch-design
- Protocol deadlock in BFM → iterate; if architectural cause, escalate to Phase 2
- BFM simulation fails after 2 iterations → escalate to user with root cause
- Per-block I/O logging incomplete → block Phase 3 completion

## Final Checklist

**Module decomposition & structure:**
- [ ] docs/phase-3-uarch/*.md exists for each block in architecture.md
- [ ] Module decomposition documented for every block
- [ ] Inter/intra-module pipelines defined
- [ ] **Throughput invariant verified**: every pipeline depth decision documents `rate_per_cycle × clock_freq ≥ target_throughput`. Pipeline changes that reduce net throughput below target are rejected.
- [ ] All block boundaries preserved (no unauthorized merges/splits)
- [ ] All functional responsibilities present

**Clock domain assignment:**
- [ ] Every sub-block has assigned clock domain
- [ ] Cross-domain interfaces specify synchronizer type
- [ ] docs/phase-3-uarch/clock-domain-map.md saved

**Protocol assignment:**
- [ ] Every inter-block interface has assigned protocol with justification
- [ ] docs/phase-3-uarch/protocol-assignments.md saved
- [ ] domain-consult invoked for protocol guidance

**Register/SRAM/FSM allocation:**
- [ ] Pipeline registers: placement justified
- [ ] Config registers: fields, widths, reset values defined
- [ ] SRAM: capacity, banking, port count per block
- [ ] FSM: state count, encoding, transitions per control path

**BFM validation:**
- [ ] TLM-based BFM built and compiled (blocking LT)
- [ ] BFM simulation passes against C ref model
- [ ] Per-block I/O logging for ALL blocks
- [ ] I/O logs archived for Phase 4-5 use
- [ ] No deadlocks or protocol violations

**Review & compliance:**
- [ ] 3-round review completed (or gaps escalated and approved)
- [ ] Cross-module interfaces reviewed
- [ ] μArch ↔ ref model consistency verified
- [ ] Naming conventions enforced (i_/o_, {domain}_clk, u_, logic only)
- [ ] rtl-architect verdict PASS
- [ ] timing-advisor no blockers
- [ ] Domain architecture expert approved (when applicable)

**Rebuttal & per-round artifacts:**
- [ ] reviews/phase-3-uarch/uarch-review-r1.md with rebuttal section (accept/reject + rationale)
- [ ] reviews/phase-3-uarch/uarch-review-r2.md with rebuttal section (accept/reject + rationale)
- [ ] reviews/phase-3-uarch/uarch-review-r3.md (mandatory final pass)

**Artifacts saved:**
- [ ] reviews/phase-3-uarch/feature-preservation.md
- [ ] reviews/phase-3-uarch/uarch-review.md (consolidated)
- [ ] reviews/phase-3-uarch/pipeline-diagram.md (Mermaid — see format below)
- [ ] docs/phase-3-uarch/clock-domain-map.md
- [ ] docs/phase-3-uarch/protocol-assignments.md
- [ ] docs/phase-3-uarch/phase-3-summary.md
- [ ] docs/phase-3-uarch/req-uarch-traceability.md (100% REQ coverage)
- [ ] docs/decisions/ADR-*.md generated (3-5 key μArch decisions)

## Mermaid Pipeline Diagram Format

Per diagram-rules.md: use Mermaid for pipeline/flow diagrams (ASCII art prohibited).

```mermaid
flowchart LR
  S0[S0: Fetch] -->|"data[31:0]"| S1[S1: Decode]
  S1 -->|"op[7:0], operands"| S2[S2: Execute]
  S2 -->|"result[47:0]"| S3[S3: Writeback]

  S0 -.->|stall| S0
  S2 -.->|forward| S1
```

Each stage node: `SN[SN: stage_name]`. Edges: data width annotation.
Stall/forward paths: dashed arrows (`-.->`).
