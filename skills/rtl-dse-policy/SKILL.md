---
name: rtl-dse-policy
description: "Policy rules, DSE methodology, comparison matrix formats, C model transformation rules, and gate criteria for the Design Space Exploration pipeline (Phase 1→2). Pure reference — no orchestration."
user-invocable: false
---

# DSE Policy

## What Makes DSE Different from Standard Phase 1→2

| Aspect | Standard (p1-spec-research + p2-arch-design) | rtl-dse |
|--------|------------------------------------------|---------|
| Algorithm study | Select best, justify | Explore N candidates, quantitative comparison |
| Architecture | Single architecture from requirements | Multiple candidates, trade-off matrix, user selects |
| Ref C model | Build from scratch | Accept functional model as input, transform to architectural model |
| Fixed-point | Identify precision requirements | Simulate effects, precision vs area trade-off curves |
| Output | Ready for Phase 3 | Ready for Phase 3, with DSE rationale documented |

## Design Priority Order
1. Functional Correctness (highest) — Every required feature works exactly
2. Interface Compliance — Ports, protocols, timing match Architecture
3. Timing/Performance — Throughput, latency targets met
4. Area/Power (lowest)

## Document-as-Memory
All exploration results captured in design artifacts (docs/, reviews/) so downstream
phases can reference DSE rationale without repeating exploration.

## DSE Methodology

### Algorithm Comparison Matrix (per functional block)

For each major functional block, enumerate 2-4 algorithmic approaches:

| Metric | Candidate A | Candidate B | Candidate C |
|--------|-------------|-------------|-------------|
| Computational complexity (ops/input) | | | |
| Memory access pattern (seq/random, R/W ratio) | | | |
| Memory bandwidth estimate | | | |
| HW gate count estimate (order of magnitude) | | | |
| Quality/accuracy impact (PSNR/SSIM if applicable) | | | |
| Parallelization potential (data/pipeline) | | | |

### Fixed-Point Feasibility Analysis
- Minimum bit-width for acceptable precision
- Rounding mode impact (truncate vs round-half-up vs convergent)
- Precision vs area trade-off (e.g., 12-bit vs 16-bit internal paths)

### HW-Friendly Algorithm Modifications
- Simplifications that reduce gate count with minimal quality loss
- Regularization of memory access patterns for SRAM efficiency
- Opportunities for resource sharing between blocks

### Architecture Candidate Format

For each candidate (2-3 required):
- Block diagram (D2)
- Estimated area breakdown (LUT/FF for FPGA, gate count for ASIC)
- Throughput/latency estimate
- Memory bandwidth requirement
- Critical path identification

Output: `docs/phase-2-architecture/architecture-candidates.md`

## User Decision Points

Two mandatory AskUserQuestion interactions:
1. **Algorithm selection**: After algorithm exploration, present candidates with quantitative matrix
2. **Architecture selection**: After architecture candidate exploration, present trade-off matrix

Decisions recorded as ADRs:
- `docs/decisions/ADR-001-algorithm-selection.md`
- `docs/decisions/ADR-002-architecture-selection.md`

## Functional → Architectural C Model Transformation

When `input_mode == "transform"` (user-provided functional C model):

1. **Analyze**: Identify function boundaries, data flow, global state
2. **Map**: Map functions to architecture.md block boundaries
3. **Restructure**:
   - Split monolithic functions into per-block functions matching architecture blocks
   - Replace global memory access with `ext_mem_read()`/`ext_mem_write()` abstraction
   - Convert global state into per-block context structs (`context_t`)
   - Add block-level I/O interfaces matching architecture port definitions
4. **Verify**: Run same test vectors through original and transformed models
   - Bitexact match required — any mismatch is a transformation bug

Output: refc/*.c (restructured), refc/include/*.h. C11, no clock/reset, DPI-C compatible.

## Optional Evaluations

> **Quantitative RD evaluation**: If ref C model encoder is buildable and test sequences
> are available, invoke `/rtl-agent-team:codec-rd-eval` for BD-PSNR measurements.
>
> **Decoder conformance**: If ref C model decoder exists and conformance bitstreams
> are available, invoke `/rtl-agent-team:codec-conformance-eval`.

## Execution Rules

### Dual-Layer Phase Gates
Phase 1→2 and Phase 2 completion require BOTH Artifact Gate + Quality Gate.
Quality Gate verdicts: `PASS` or `FAIL + findings[]`. Max 2 retries.

### Scratchpad Convention
`.rtl-agent-team/scratch/phase-{N}/round-{R}-{agent}.md`
On gate PASS: consolidate to reviews/, clean scratch.

### Termination
After Phase 2 Quality Gate PASS, generate summary + ADR, then STOP.
Do NOT proceed to Phase 3.

## Phase Gate Definitions

### Phase 1→2 (Research → Architecture DSE)
**Artifact Gate**: requirements.json + io_definition.json + timing_constraints.json + domain-analysis.md exist
**Quality Gate**:
- Requirements complete and consistent
- Algorithm comparison matrices complete with quantitative data
- Algorithm selection ADR recorded with user's decision
- Save: `reviews/phase-1-research/research-review.md`
- **Verdict**: PASS if requirements clear, algorithms selected with rationale

**Summary Validation**: `docs/phase-1-research/phase-1-summary.md`

### Phase 2 Completion (Architecture DSE → Human Review)
**Artifact Gate**: architecture.md + architecture-candidates.md + refc/*.c exist
**Quality Gate**:
- 3-round iterative review converged (or user-approved)
- Feature Coverage: 100% REQ-NNN mapped to architecture blocks
  - Save: `reviews/phase-2-architecture/feature-coverage.md`
- Architecture candidates document with quantitative comparison
- Architecture selection ADR with user's decision and rationale
- Ref C model architecturally structured (block boundaries match architecture.md)
- If transformed: bitexact equivalence verified
- Architecture Diagram saved
- Save: `reviews/phase-2-architecture/architecture-review.md`
- **Verdict**: PASS if 100% coverage AND architecture selected AND ref model consistent

**Summary + ADR**: phase-2-summary.md + ADRs (including algorithm + architecture selection)

## Escalation & Stop Conditions

- Algorithm candidates cannot be differentiated → ask user for priority (area vs throughput vs quality)
- Architecture candidates too similar → ask user for dominant constraint
- Functional C model too complex to transform → report, suggest manual restructuring guidance
- Phase 1 Quality Gate fails after 2 retries → ask user to clarify spec
- Phase 2 Quality Gate fails after 2 retries → ask user for architecture direction
- Ref model transformation breaks bitexact equivalence → report divergence, ask user to verify original

## Coding Convention Summary

- Port prefix: `i_`, `o_`, `io_`. Clock: `{domain}_clk`. Reset: `{domain}_rst_n`
- C ref model: C11, no clock/reset, ext_mem abstraction, DPI-C compatible

## Final Checklist

- [ ] Phase 1: requirements.json, io_definition.json, timing_constraints.json exist
- [ ] Phase 1: domain-analysis.md contains algorithm comparison matrices (not just selection)
- [ ] Phase 1: Algorithm selection ADR recorded with user's decision
- [ ] Phase 1: research-review.md PASS, phase-1-summary.md generated
- [ ] Phase 2: architecture-candidates.md contains 2+ candidates with quantitative comparison
- [ ] Phase 2: Architecture selection ADR recorded with user's decision
- [ ] Phase 2: architecture.md exists (refined from selected candidate)
- [ ] Phase 2: refc/*.c exists
- [ ] Phase 2: If transform mode — bitexact equivalence verified
- [ ] Phase 2: architecture-review.md PASS, feature-coverage.md 100%
- [ ] Phase 2: phase-2-summary.md generated, ADRs recorded
- [ ] Scratch directories cleaned
- [ ] State file updated with all phases completed
- [ ] Pipeline did NOT proceed to Phase 3
