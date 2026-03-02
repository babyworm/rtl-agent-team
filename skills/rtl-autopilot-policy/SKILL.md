---
name: rtl-autopilot-policy
description: "Policy rules, phase gate definitions, quality criteria, feedback loop classification, and checklists for the RTL autopilot 6-phase pipeline. Pure reference — no orchestration."
user-invocable: false
---

# RTL Autopilot Policy

## Core Principles

### Hierarchical Spec Compliance
Lower phases MUST NOT violate upper phase specifications:
  Spec → Architecture → μArch → RTL → Verification
Each phase strictly adheres to decisions made in all preceding phases.
Deletion, reduction, or modification of features for convenience is FORBIDDEN.
If a change is needed, control returns to the upper phase for approval.

### Design Priority Order
1. Functional Correctness (highest) — Every required feature works exactly
2. Interface Compliance — Ports, protocols, timing match Architecture
3. Timing/Performance — Throughput, latency targets met
4. Area/Power (lowest)

### Cascading Quality
Higher abstraction levels demand MORE iterative refinement because their quality
cascades to ALL downstream phases. A defect at the architecture level costs orders
of magnitude more to fix at RTL than if caught during architecture review.

Graduated iteration by abstraction level:
  Phase 1 (Research): 3 mandatory rounds (chief-coordinated)
  Phase 2 (Architecture): 3 mandatory rounds — memory, performance, ref model consistency
  Phase 3 (μArch): 3 mandatory rounds — performance, interface, memory optimization
  Phase 4 (RTL): Wave-based lint+sim (implementation-level)
  Phase 5 (Verify): Sub-phase parallel (terminal verification)

Iteration count can be increased beyond 3 if convergence is not achieved.
Principle: **refine thoroughly at the top, execute efficiently at the bottom.**

### Document-as-Memory
Design artifacts (docs/, reviews/) serve as persistent memory across phases and agents.
Each phase reads upstream documents as input context and writes downstream documents as output.
No agent needs to "remember" another agent's output — it reads the document.

Document flow:
  requirements.json → arch-designer reads → architecture.md → uarch-designer reads →
  docs/phase-3-uarch/*.md → rtl-coder reads
  reviews/phase-N/ → Quality Gate reads → next phase proceeds or fails

State is persisted at `.rtl-agent-team/state/rtl-autopilot-state.json` for resumability.

## Execution Rules

### Dual-Layer Phase Gates
Every phase transition requires BOTH:
1. **Artifact Gate**: Required files/directories exist (fast check)
2. **Quality Gate**: Reviewer agent(s) verify quality AND hierarchical spec compliance

Quality Gate verdicts: `PASS` or `FAIL + findings[]`

### Gate Retry Policy
- On Artifact Gate failure: retry the failed phase once, then escalate to user
- On Quality Gate failure: pass findings back to the phase's worker agent for correction,
  then re-run Quality Gate. Maximum 2 retry cycles per gate
- On upper-spec violation: IMMEDIATE STOP (see Escalation)

### Context Manifests
Each phase has a manifest (`templates/context-manifest-phase-{N}.json`) declaring:
- `required_full_read`: files that MUST be fully read before starting the phase
- `required_summary_only`: files where only the phase summary is sufficient
- `optional_on_demand`: files read only when a specific question arises

Agents entering a phase MUST load `required_full_read` first, then summaries.

### Scratchpad Convention
During iterative review rounds, reviewers write findings to:
  `.rtl-agent-team/scratch/phase-{N}/round-{R}-{agent}.md`

Coordinator reads all round files to aggregate:
  `.rtl-agent-team/scratch/phase-{N}/round-{R}-feedback.md`

On phase gate PASS: consolidated review saved to `reviews/phase-{N}-*/`, scratch cleaned.
On phase gate FAIL + retry: scratch files preserved for next round.

## Phase Gate Definitions

### Phase 1→2 (Research → Architecture)
**Artifact Gate**: requirements.json + io_definition.json + domain-analysis.md exist
**Quality Gate**:
- spec-analyst self-reviews requirements.json for completeness and internal consistency
  - All functional requirements traceable to spec sections
  - No contradictions or ambiguities
  - Save: `reviews/phase-1-research/research-review.md`
- arch-designer evaluates requirements for implementation feasibility
  - Every requirement realizable in RTL within reasonable area/timing
  - No missing constraints
- **Verdict**: PASS if all requirements clear, consistent, and implementable

**Summary Validation**: `docs/phase-1-research/phase-1-summary.md` must exist (format: `templates/phase-summary.md`)

### Phase 2→3 (Architecture → μArch)
**Artifact Gate**: architecture.md + block_diagram + refc/*/*.c exist
**Quality Gate**:
- 3-round iterative review converged (or gaps escalated and user-approved)
- Feature Coverage Checklist: 100% of REQ-NNN mapped to architecture blocks
  - Save: `reviews/phase-2-architecture/feature-coverage.md`
- Memory access review PASS: all large blocks have viable memory strategy
- Architecture ↔ ref model consistency PASS: block mapping + data flow + interface alignment
- Ref model code review: quality, bitexact correctness verified
- Architecture Diagram: D2 block diagram saved
- Per-round review artifacts: architecture-review-r1.md, r2.md, r3.md
- Save: `reviews/phase-2-architecture/architecture-review.md`
- **Verdict**: PASS if 100% feature coverage AND no structural defects AND iterative review converged

**Phase 2 Iterative Review** (3-round mandatory, coordinated by rtl-architect):
- Parallel reviewers each round:
  (a) rtl-architect: spec compliance (Feature Coverage Checklist) + structural review
  (b) vcodec-architecture-expert: memory access patterns, performance analysis
  (c) ref-model-dev: architecture ↔ C model consistency
- Round 1-2: review → targeted feedback → revision (only experts with findings re-run)
- Round 3 mandatory even if converged: cross-block interface audit + memory conflict analysis
- After 3 rounds if not converged → escalate to user via AskUserQuestion

**Summary Validation**: `docs/phase-2-architecture/phase-2-summary.md`
**ADR Recording**: 3-5 key decisions → `docs/decisions/ADR-{NNN}.md`

### Phase 3→4 (μArch → RTL)
**Artifact Gate**: docs/phase-3-uarch/*.md + bfm/ directory exist
**Quality Gate**:
- 3-round iterative review converged
- Feature Preservation Checklist: 100% of architecture features preserved in μArch
  - Save: `reviews/phase-3-uarch/feature-preservation.md`
- Block boundary alignment: 1:1 correspondence with architecture.md
- Memory access optimization PASS: SRAM banking, port conflicts, access scheduling reviewed
- μArch ↔ ref model consistency PASS: behavior, data widths, fixed-point formats aligned
- Pipeline Diagram: Mermaid pipeline diagram saved
- Per-round review artifacts: uarch-review-r1.md, r2.md, r3.md
- Save: `reviews/phase-3-uarch/uarch-review.md`
- **Verdict**: PASS if 100% feature preservation AND timing paths reasonable AND converged

**Phase 3 Iterative Review** (3-round mandatory, coordinated by rtl-architect):
- Parallel reviewers each round:
  (a) rtl-architect: feature preservation + block boundary + interface correctness
  (b) timing-advisor: critical paths at target frequency, pipeline balance
  (c) vcodec-architecture-expert: algorithm/memory/interface optimization
  (d) ref-model-dev: model consistency (behavioral match, data widths, fixed-point)
- Round 3 mandatory: model consistency matrix + cross-module interface audit
- After 3 rounds if not converged → escalate to user

**Summary Validation**: `docs/phase-3-uarch/phase-3-summary.md`
**ADR Recording**: 3-5 key decisions → `docs/decisions/ADR-{NNN}.md`

### Phase 4→5 (RTL → Verification)
**Artifact Gate**:
- rtl/*/*.sv exist and all lint-clean
- sim/*/tb_*.sv exist for all modules
- sim/*/*_results.txt exist and all PASS
- Basic integration smoke test PASS
- Stream B artifacts exist:
  - docs/phase-4-rtl/stream-b-sva-skeletons.md
  - docs/phase-4-rtl/stream-b-cdc-preliminary.md
  - docs/phase-4-rtl/stream-b-tb-skeletons.md

**Quality Gate**:
- rtl-critic reviews RTL against μArch specs AND requirements.json
  - Functional Coverage Matrix: every requirement traced to RTL. Any MISSING → FAIL
  - Code quality: proper FSM, no latches, clean reset
  - Synthesizability: no non-synth constructs
  - Convention compliance: i_/o_, {domain}_clk, logic only
  - Hierarchical compliance: no unauthorized deviation from μArch
  - Save: `reviews/phase-4-rtl/functional-completeness.md`, `reviews/phase-4-rtl/design-review.md`
- lint-checker: zero errors, warnings reviewed
  - Save: `reviews/phase-4-rtl/lint-report.md`
- **Verdict**: PASS if 100% functional coverage AND lint-clean AND design quality passes

**Summary Validation**: `docs/phase-4-rtl/phase-4-summary.md`

### Phase 5 Completion
**Artifact Gate**: All verification sub-phases (5a-5e) pass
**Quality Gate**:
- func-verifier: Requirement Traceability Matrix
  - Save: `reviews/phase-5-verify/requirement-traceability.md`
- rtl-architect: end-to-end final compliance review
  - Save: `reviews/phase-5-verify/final-compliance.md`
- End-to-End Traceability Matrix unifying 4 upstream traceability artifacts
  - Save: `reviews/phase-5-verify/e2e-traceability.md`
- **Verdict**: PASS if every requirement is implemented, verified, and passing

**Summary Validation**: `docs/phase-5-verify/phase-5-summary.md`

### Phase 5→6 (Verification → Design Review)
**Artifact Gate**: `reviews/phase-5-verify/final-compliance.md` exists AND verdict=PASS

### Phase 6 Completion
All 4 deliverables exist AND pass quality checks:
- `reviews/phase-6-review/code-review.md` — verdict PASS
- `reviews/phase-6-review/design-review.md` — verdict PASS
- `reviews/phase-6-review/design-note.md` — complete document
- `reviews/phase-6-review/improvements.md` — recommendations produced
On FAIL: iterate review → fix cycle (max 2 rounds)

## Stream B Rules (Phase 4)

Stream B artifacts are generated concurrently with Stream A (RTL implementation):
- B1. SVA property skeletons from μArch specs → `docs/phase-4-rtl/stream-b-sva-skeletons.md`
- B2. Preliminary CDC topology from μArch specs → `docs/phase-4-rtl/stream-b-cdc-preliminary.md`
- B3. cocotb TB skeletons from μArch specs → `docs/phase-4-rtl/stream-b-tb-skeletons.md`

**Traceability Convention**:
- SVA skeletons: each property references μArch source: `// Source: docs/phase-3-uarch/{module}.md, Section: {section}`
- CDC preliminary: each CDC path references architecture clock domain definition
- TB skeletons: each test scenario references requirement: `# REQ-{NNN}: {description}`

**Merge Point**: Stream A (lint-clean + unit PASS) + Stream B artifacts ready → Phase 4→5 Gate.

## Feedback Loop Classification (Phase 5→4)

| Type | Scope | Handling | Re-verify |
|------|-------|----------|-----------|
| UNIT_FIX | Single module (SVA fail, assertion error) | rtl-p4s-bugfix (parallel across modules) | Only failed sub-phases |
| INTEGRATION_FIX | Cross-module interface | rtl-p4s-bugfix (sequential) | 5b + 5c |
| DESIGN_FIX | Architecture-level | IMMEDIATE STOP → user approval | All (5a-5e) after upper phase fix |

**Batch UNIT_FIX across sub-phases:**
- Group by module. Different modules → parallel fix. Same module → sequential.
- Each rtl-p4s-bugfix follows: analyze → fix → lint → TB → sim
- After ALL fixes: re-run ONLY affected sub-phases in parallel

**Max 2 feedback loops per sub-phase**. After loop 2 fails → escalate to user.

### Sub-phase Re-entry Criteria

| Fix Type | Re-run Sub-phases | Condition |
|----------|------------------|-----------|
| UNIT_FIX (SVA fail) | 5a only (formal) | SVA property affected |
| UNIT_FIX (sim fail) | 5c only (integration) | Testbench affected |
| INTEGRATION_FIX | 5b + 5c (CDC + integration) | Interface modified |
| DESIGN_FIX | All (5a-5e) after upper phase approval | Architecture changed |

### Feedback Loop State Schema
```json
{
  "loop_count": 1,
  "max_loops": 2,
  "failures": [{
    "sub_phase": "5a",
    "type": "UNIT_FIX",
    "module": "example_module",
    "description": "SVA counterexample at cycle 42",
    "fix_applied": "Added pipeline register",
    "re_run_phases": ["5a"]
  }],
  "status": "in_progress"
}
```

### Lesson Learned Recording
After each successful feedback fix:
- Append entry to `docs/lessons-learned.md` using `templates/lessons-learned-entry.md` format
- Record: symptom, root cause, fix applied, prevention strategy, related REQ/module/ADR

## Escalation & Stop Conditions

- **Artifact Gate fails twice** → pause and report missing artifacts to user
- **Quality Gate fails after 2 fix-and-retry cycles** → pause, present all accumulated findings, request guidance
- **Upper-Spec Violation detected at any Quality Gate** → IMMEDIATE STOP:
  1. Identify the violated upper phase and the specific violation
  2. Report to user with full context
  3. DO NOT proceed — wait for user to approve rollback or waiver
  4. If approved, return to the appropriate upper phase
- **Phase 5→4 Feedback Loop exhausted** (2 cycles per sub-phase) → escalate to user
- **Phase 5 DESIGN_FIX detected** → IMMEDIATE STOP, report upper-spec violation
- **Verification phase fails after 2 retries** → invoke rtl-bug-repro skill
- **User says "cancel"/"stop"** → delete state file, report progress summary

## Coding Convention Summary

All phases must enforce:
- Port prefix: `i_`, `o_`, `io_` (NOT suffix). Clock/reset exempt
- Clock: `clk` (single) or `{domain}_clk` (multiple). Reset: `rst_n` or `{domain}_rst_n`
- No CamelCase: `snake_case` or `ALL_CAPS` only
- Parameters `ALL_CAPS`, localparam `L_` prefix
- `logic` only (no `reg`/`wire`), `always_ff`/`always_comb`, ANSI port style
- Instance prefix: `u_`, generate prefix: `gen_`
- SV RTL: IEEE 1800-2009. SV Verification: IEEE 1800-2012. C ref model: C11

## Final Checklist

- [ ] State file written before starting
- [ ] Each phase passed BOTH Artifact Gate AND Quality Gate
- [ ] Hierarchical Spec Compliance verified at every gate:
  - Phase 1→2: requirements complete, consistent, implementable
  - Phase 2→3: 100% feature coverage + 3-round iterative review converged
  - Phase 3→4: 100% feature preservation + 3-round iterative review converged
  - Phase 4→5: 100% functional coverage + lint-clean + unit tests PASS + Stream B ready
  - Phase 5: multi-seed regression PASS + e2e-traceability.md exists
  - Phase 5 final: Final Compliance Matrix PASS
  - Phase 6: all 4 deliverables exist and pass
- [ ] No upper-spec violations left unresolved
- [ ] Naming conventions enforced at every phase gate
- [ ] All 6 phases completed
- [ ] State file removed on clean completion
- [ ] Summary report generated
- [ ] Review artifacts verified per references/review-checklist.md (26 mandatory files)
