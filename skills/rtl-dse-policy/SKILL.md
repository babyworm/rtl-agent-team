---
name: rtl-dse-policy
description: "Policy rules, DSE methodology, comparison matrix formats, C model transformation rules, self-critique protocol, trial comparison, and gate criteria for the iterative Design Space Exploration pipeline (Phase 1→3). Pure reference — no orchestration."
user-invocable: false
---

# DSE Policy

## What Makes DSE Different from Standard Phase 1→3

| Aspect | Standard (p1 + p2 + p3 sequential) | rtl-dse |
|--------|------------------------------------------|---------|
| Algorithm study | Select best, justify | Explore N candidates, quantitative comparison |
| Architecture | Single architecture from requirements | Multiple candidates, trade-off matrix, user selects |
| μArch + BFM | Single-pass μArch design | Iterative μArch with self-critique and re-exploration |
| Ref C model | Build from scratch | Accept functional model as input, transform to architectural model |
| Fixed-point | Identify precision requirements | Simulate effects, precision vs area trade-off curves |
| Iteration | One-shot per phase | Self-critique → re-run → user review → trial comparison |
| Output | Ready for Phase 4 | Pre-implementation package with DSE rationale, ready for Phase 4 |

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
Phase 1→2, Phase 2→3, and Phase 3 completion require BOTH Artifact Gate + Quality Gate.
Quality Gate verdicts: `PASS` or `FAIL + findings[]`. Max 2 retries per gate.

### Scratchpad Convention
`.rtl-agent-team/scratch/phase-{N}/round-{R}-{agent}.md`
On gate PASS: consolidate to reviews/, clean scratch.

### Termination
After Phase 3 Quality Gate PASS + self-critique re-run, present results to user.
Do NOT proceed to Phase 4. DSE produces a pre-implementation package for user review.

## Phase Gate Definitions

### Phase 1→2 (Research → Architecture DSE)
**Artifact Gate**: iron-requirements.json + open-requirements.json + io_definition.json + timing_constraints.json + domain-analysis.md exist
**Quality Gate**:
- Iron/open requirements complete and consistent
- Ambiguity score ≤ 0.5 for all iron requirements
- Algorithm comparison matrices complete with quantitative data
- Algorithm selection ADR recorded with user's decision
- Save: `reviews/phase-1-research/research-review.md`
- **Verdict**: PASS if requirements clear, algorithms selected with rationale

**Summary Validation**: `docs/phase-1-research/phase-1-summary.md`

### Phase 2→3 (Architecture DSE → μArch + BFM)
**Artifact Gate**: architecture.md + architecture-candidates.md + refc/*.c + iron-requirements.json (P2, REQ-A-*) exist
**Quality Gate**:
- 3-round iterative review converged (or user-approved)
- Feature Coverage: 100% REQ (REQ-F-*, REQ-P-*, REQ-A-*) mapped to architecture blocks
  - Save: `reviews/phase-2-architecture/feature-coverage.md`
- All OPEN-1-* resolved with rationale in iron-requirements.json (REQ-A-*)
- Compliance check against P1 iron: PASS
- Architecture candidates document with quantitative comparison
- Architecture selection ADR with user's decision and rationale
- Ref C model architecturally structured (block boundaries match architecture.md)
- If transformed: bitexact equivalence verified
- Architecture Diagram saved
- Save: `reviews/phase-2-architecture/architecture-review.md`
- **Verdict**: PASS if 100% coverage AND architecture selected AND ref model consistent AND compliance PASS

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

## Phase 3 Gate Definition

### Phase 2→3 (Architecture DSE → μArch + BFM)
**Artifact Gate**: architecture.md + refc/*.c + iron-requirements.json (P1+P2) exist
**Quality Gate**:
- Architecture review converged (or user-approved)
- Ref C model verified (bitexact if transform mode)

### Phase 3 Completion (μArch + BFM → Self-Critique)
**Artifact Gate**: docs/phase-3-uarch/*.md + bfm/src/*.cpp (or bfm/src/*.c) + iron-requirements.json (P3) exist
**Quality Gate**:
- μArch review converged (min 2 rounds)
- BFM compiles and simulates, outputs match ref C model
- REQ→μArch traceability 100% coverage
- Clock domain map and protocol assignments complete
- **Verdict**: PASS if all above satisfied

**Note**: Phase 3 produces C/SystemC BFM, NOT SystemVerilog RTL.
BFM is the executable μArch model. DPI bridge template is prepared for
future RTL comparison in Phase 4, but no RTL is written in DSE.

## Self-Critique Protocol

After Phase 3 Quality Gate PASS, the orchestrator performs self-critique
BEFORE presenting results to the user:

1. **Critique agent** reviews the complete P1→P3 output:
   - Spec completeness: any requirements missed or vague?
   - Architecture soundness: any structural weakness, bottleneck, or over-engineering?
   - μArch feasibility: pipeline depths realistic? memory bandwidth achievable?
   - BFM correctness: any untested paths? ref model coverage gaps?
   - Iron/open quality: acceptance_criteria measurable? resolution rationale substantive?
   - Cross-phase consistency: do P3 decisions contradict P1/P2 iron requirements?

2. **Output**: `reviews/dse-self-critique.md` with findings rated HIGH/MEDIUM/LOW

3. **Re-run**: Run Phase 1→3 again incorporating all critique findings
   - HIGH findings: must be addressed (fix spec, revise architecture, redesign μArch)
   - MEDIUM findings: should be addressed
   - LOW findings: note for user, no action required

4. **Result**: Second pass produces refined pre-implementation package

## Trial Comparison Protocol

When the user requests another iteration (not satisfied with results),
a new trial is created in a git worktree:

### Trial Management
- **Trial 1**: runs on current branch, results committed
- **Trial N (N≥2)**: created via `Agent(isolation="worktree")` with user feedback
- Each trial produces a complete P1→P3 artifact set

### Comparison Method
After Trial N completes, compare against the current best trial:

1. **Independent compliance checks**: invoke compliance-checker separately on EACH trial's P1→P3 chain
   - Run compliance-checker on current best trial → compliance-report-current.json
   - Run compliance-checker on new trial → compliance-report-new.json
   - Compare: which trial covers more acceptance_criteria? fewer VIOLATION items? more measurable iron?

2. **Quantitative comparison table** (presented to user):

| Metric | Current Best (Trial K) | New Trial (Trial N) |
|--------|----------------------|---------------------|
| Iron requirements count | | |
| Open items remaining | | |
| Ambiguity score (P1) | | |
| Architecture candidates explored | | |
| μArch modules defined | | |
| BFM ↔ RefC match | | |
| Compliance verdict (P1+P2→P3) | | |
| Self-critique HIGH findings | | |

3. **Selection**: user chooses which trial to keep
   - If Trial N selected → merge worktree changes into main branch
   - If current best selected → discard Trial N worktree

### Iteration Loop
```
repeat:
  AskUserQuestion("결과가 만족스러운가? (yes/no)")
  if yes → done (pre-implementation package ready for Phase 4)
  if no  → collect user feedback
         → create new trial (worktree)
         → run P1→P3 with feedback
         → compare trials
         → user selects better trial
```

## Final Checklist

- [ ] Phase 1: iron-requirements.json, open-requirements.json, io_definition.json, timing_constraints.json exist
- [ ] Phase 1: domain-analysis.md contains algorithm comparison matrices (not just selection)
- [ ] Phase 1: Algorithm selection ADR recorded with user's decision
- [ ] Phase 1: research-review.md PASS, phase-1-summary.md generated
- [ ] Phase 1: Ambiguity score ≤ 0.5
- [ ] Phase 2: architecture-candidates.md contains 2+ candidates with quantitative comparison
- [ ] Phase 2: Architecture selection ADR recorded with user's decision
- [ ] Phase 2: architecture.md exists (refined from selected candidate)
- [ ] Phase 2: iron-requirements.json (REQ-A-*) with resolved_from tracking
- [ ] Phase 2: refc/*.c exists
- [ ] Phase 2: If transform mode — bitexact equivalence verified
- [ ] Phase 2: architecture-review.md PASS, feature-coverage.md 100%
- [ ] Phase 2: Compliance check against P1 iron: PASS
- [ ] Phase 3: docs/phase-3-uarch/*.md per-module specs exist
- [ ] Phase 3: iron-requirements.json (REQ-U-*) with resolved_from tracking
- [ ] Phase 3: BFM (bfm/src/*.cpp or bfm/src/*.c) compiles and matches ref C model
- [ ] Phase 3: clock-domain-map.md, protocol-assignments.md exist
- [ ] Phase 3: req-uarch-traceability.md with 100% REQ coverage
- [ ] Phase 3: Compliance check against P1+P2 iron: PASS
- [ ] Phase 3: Zero remaining open items
- [ ] Self-critique: reviews/dse-self-critique.md produced
- [ ] Self-critique: Phase 1→3 re-run with critique findings incorporated
- [ ] User satisfaction check performed
- [ ] If multiple trials: comparison table presented, better trial selected
- [ ] Scratch directories cleaned
- [ ] State file updated with all phases completed
- [ ] Pipeline did NOT proceed to Phase 4
