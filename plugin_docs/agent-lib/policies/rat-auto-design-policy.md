# RTL Auto-Design Policy

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

### Light review
One review against the evidence. Name the open items and stop. A further round runs only when the user asks.

  Phase 1 (Research): one chief review
  Phase 2 (Architecture): one review — memory, performance, ref model
  Phase 3 (μArch): one review — performance, interface, memory
  Phase 4 (RTL): implement, lint, and one functional check
  Phase 5 (Verify): check the requirements once

Do not schedule a second pass to chase convergence. With no measurement, the model's confidence is the gate: the spec has one reading, or one architecture choice fits. Record it. Do not iterate to raise it. Low confidence is named and asked once. Lint, simulation, formal, coverage, synthesis, CDC, and model comparison are judged from the measured result. Confidence does not override a measurement. Prompts state the goal, the constraints, the evidence, and the done condition. Leave effort at the session default.

### Document-as-Memory
Design artifacts (docs/, reviews/) serve as persistent memory across phases and agents.
Each phase reads upstream documents as input context and writes downstream documents as output.
No agent needs to "remember" another agent's output — it reads the document.

Document flow:
  iron-requirements.json + open-requirements.json → arch-designer reads → architecture.md → uarch-designer reads →
  docs/phase-3-uarch/*.md → rtl-coder reads
  reviews/phase-N/ → Quality Gate reads → next phase proceeds or fails

State is persisted at `.rat/state/rat-auto-design-state.json` for resumability.

## Execution Rules

### Dual-Layer Phase Gates
Every phase transition requires BOTH:
1. **Artifact Gate**: Required files/directories exist (fast check)
2. **Quality Gate**: Reviewer agent(s) verify quality AND hierarchical spec compliance

Quality Gate verdicts: `PASS` or `FAIL + findings[]`

### Gate Retry Policy
- On Artifact Gate failure: retry the failed phase once, then escalate to user
- On Quality Gate failure: if the gate is a judgment with no measurement, high confidence passes and low confidence asks the user once. Do not re-run that gate to become more sure. If the gate is a measurement — lint, simulation, formal, coverage, synthesis, CDC, or a model comparison — the measured result stands. Confidence does not pass a failing measurement. The measured repair budget below applies to that failure.
- On upper-spec violation: IMMEDIATE STOP (see Escalation)

### Measured repair budget

A failed measurement authorizes repair of that defect and rerunning affected checks.
At most two failed repair cycles may run automatically; then record
`orchestration_control.needs_user_decision=true` and report the failure and evidence.
Missing artifacts authorize producing those artifacts, not repeating a settled
review. Unresolved material ambiguity requires one focused user decision.
Do not switch reviewers, spawn alternatives, or add an automatic last chance merely
because a counter advanced. Keep `active_gate_primary_attempts` as the repair count;
legacy fallback/last-chance fields are read only for migration, not new work.

### Context Preload
Before each phase, verify required upstream files exist:
- **required (full read)**: files that MUST be fully read before starting the phase
- **summary only**: files where only the phase summary is sufficient
- **optional (on demand)**: files read only when a specific question arises

Agents entering a phase MUST load required files first, then summaries.
Specific file lists are defined inline in each orchestrator's phase steps.

### Scratchpad Convention
During iterative review rounds, reviewers write findings to:
  `.rat/scratch/phase-{N}/round-{R}-{agent}.md`

Coordinator reads all round files to aggregate:
  `.rat/scratch/phase-{N}/round-{R}-feedback.md`

On phase gate PASS: consolidated review saved to `reviews/phase-{N}-*/`, scratch cleaned.
On phase gate FAIL + retry: scratch files preserved for next round.

## Phase Gate Definitions

Every transition = Artifact Gate + Quality Gate (see Dual-Layer Phase Gates).
Quality-gate semantics — reviewer rosters, review rounds, rebuttal protocol, convergence,
and detailed pass/fail criteria — are OWNED by the per-phase policies in the table below.
This policy defines only the artifact/verdict contract the orchestrator checks.

| Gate | Artifact Gate (must exist) | Verdict File(s) | Verdict | Quality Gate |
|------|---------------------------|-----------------|---------|--------------|
| 1→2 | `docs/phase-1-research/`: iron-requirements.json + io_definition.json + timing_constraints.json + domain-analysis.md (open-requirements.json optional — absent if P1 had no open items) | `reviews/phase-1-research/research-review.md` | verdict=PASS (one chief review, open items named; requirements clear, consistent, implementable) | quality gates per p1-spec-research-policy |
| 2→3 | `docs/phase-2-architecture/architecture.md` (with D2 block diagram) + iron-requirements.json (P2, REQ-A-*) + `refc/*/*.c` | `reviews/phase-2-architecture/architecture-review.md` + `feature-coverage.md` | verdict=PASS AND 100% REQ coverage | quality gates per p2-arch-design-policy |
| 3→4 | `docs/phase-3-uarch/*.md` + iron-requirements.json (P3, REQ-U-*) + `bfm/` directory | `reviews/phase-3-uarch/uarch-review.md` + `feature-preservation.md` | verdict=PASS AND 100% feature preservation | quality gates per rtl-p3-uarch-policy |
| 4→5 | `rtl/*/*.sv` (all lint-clean) + `sim/*/tb_*.sv` + `sim/*/*_results.txt` (all PASS) + basic integration smoke PASS + Stream B artifacts (see Stream B Rules) | `reviews/phase-4-rtl/functional-completeness.md` + `design-review.md` + `lint-report.md` | verdict=PASS on all three (100% functional coverage, lint 0 errors) | quality gates per rtl-p4-implement-policy |
| 5 completion | all verification sub-phases (5a-5e) PASS | `reviews/phase-5-verify/requirement-traceability.md` + `e2e-traceability.md` + `final-compliance.md` | verdict=PASS (every requirement implemented, verified, passing) | quality gates per rtl-p5-verify-policy |
| 5→6 | — (artifact-only gate) | `reviews/phase-5-verify/final-compliance.md` | verdict=PASS | — |
| 6 completion | `reviews/phase-6-review/design-note.md` (complete document) + `improvements.md` (recommendations produced) | `reviews/phase-6-review/code-review.md` + `design-review.md` | verdict=PASS on both; on FAIL name the inconsistencies once and report what remains | quality gates per rtl-p6-design-review-policy |

**Phase 1 gate additions** (owned by this policy): compliance-checker verifies iron
requirements have no internal contradictions; arch-designer confirms implementation
feasibility (every requirement realizable in RTL within reasonable area/timing).

**Summary Validation** (every P1-P5 gate): `docs/phase-1-research/phase-1-summary.md`,
`docs/phase-2-architecture/phase-2-summary.md`, `docs/phase-3-uarch/phase-3-summary.md`,
`docs/phase-4-rtl/phase-4-summary.md`, `docs/phase-5-verify/phase-5-summary.md` must exist
(format: max 1 page with tables for Key Decisions, Module Inventory, Interface Summary,
Quality Gate Results, Open Items, Document References)

**ADR Recording** (Phase 2→3 and 3→4 gates): 3-5 key decisions → `docs/decisions/ADR-{NNN}.md`

**Phase 2 review**: one pass. Roster and rebuttal rules are owned by p2-arch-design-policy.

**Phase 3 review**: one pass. Roster and rebuttal rules are owned by rtl-p3-uarch-policy.

## Stream B Rules (Phase 4)

Stream B artifacts are generated concurrently with Stream A (RTL implementation):
- B1. SVA property skeletons from μArch specs → `docs/phase-4-rtl/stream-b-sva-skeletons.md`
- B2. Preliminary CDC topology from μArch specs → `docs/phase-4-rtl/stream-b-cdc-preliminary.md`
- B3. cocotb TB skeletons from μArch specs → `docs/phase-4-rtl/stream-b-tb-skeletons.md`

**Traceability Convention**:
- SVA skeletons: each property references μArch source: `// Source: docs/phase-3-uarch/{module}.md, Section: {section}`
- CDC preliminary: each CDC path references architecture clock domain definition
- TB skeletons: each test scenario references requirement: `# REQ-{NNN}: {description}`

**Content Quality Gate** (prevents empty-skeleton artifacts from passing):
- SVA skeletons: must contain at least one `property` or `assert` keyword per referenced module
- CDC preliminary: must reference actual clock domain names from `docs/phase-3-uarch/clock-domain-map.md`
- TB skeletons: must reference at least one `REQ-` tag per module and contain at least one test function/task

**Merge Point**: Stream A (lint-clean + unit PASS) + Stream B artifacts ready (content quality verified) → Phase 4→5 Gate.

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
- Append entry to `docs/lessons-learned.md` with format: LL-{NNN} with sections: Symptom, Root Cause, Fix Applied, Prevention, Related (REQ IDs, module, fix commit, ADR, Phase 5 Sub-phase)
- Record: symptom, root cause, fix applied, prevention strategy, related REQ/module/ADR

## Escalation & Stop Conditions

- **Artifact Gate fails twice** → pause and report missing artifacts to user
- **Quality Gate fails after 2 fix-and-retry cycles** → pause, present all accumulated findings, request guidance
- **Two failed repair cycles** → set `needs_user_decision=true` and request direction before any further repair
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
- [ ] Hierarchical Spec Compliance verified at every gate (verdict contract per the
  Artifact-Gate Table above; detailed criteria per each gate's owning policy)
- [ ] No upper-spec violations left unresolved
- [ ] Naming conventions enforced at every phase gate
- [ ] All 6 phases completed
- [ ] State file removed on clean completion
- [ ] Summary report generated
- [ ] Review artifacts verified per `{plugin_root}/skills/rat-auto-design/references/review-checklist.md` (26 mandatory files)
