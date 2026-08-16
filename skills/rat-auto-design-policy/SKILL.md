---
name: rat-auto-design-policy
description: "Internal reference: rat auto design policy (agent-loaded; do not invoke)."
user-invocable: false
---

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

### Cascading Quality
Higher abstraction levels demand MORE iterative refinement because their quality
cascades to ALL downstream phases. A defect at the architecture level costs orders
of magnitude more to fix at RTL than if caught during architecture review.

Graduated iteration by abstraction level:
  Phase 1 (Research): 3 mandatory rounds (chief-coordinated)
  Phase 2 (Architecture): dynamic convergence review (min 2, max 5 rounds per p2-arch-design-policy) — memory, performance, ref model consistency
  Phase 3 (μArch): dynamic convergence review (min 2, max 5 rounds per rtl-p3-uarch-policy) — performance, interface, memory optimization
  Phase 4 (RTL): Wave-based lint+sim (implementation-level)
  Phase 5 (Verify): Sub-phase parallel (terminal verification)

Iteration count can be increased beyond 3 if convergence is not achieved.
Principle: **refine thoroughly at the top, execute efficiently at the bottom.**

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
- On Quality Gate failure: pass findings back to the phase's worker agent for correction,
  then re-run Quality Gate. Maximum 2 retry cycles per gate
- On upper-spec violation: IMMEDIATE STOP (see Escalation)

### Escalation Ladder (Per-Gate 2x)
Every active gate uses a per-gate retry budget `N` (`retry_limit` in state):
- **Primary range**: attempts `1..N` with normal strategy
- **Fallback range**: attempts `N+1..2N` with immediate strategy switch
  - split by module/requirement
  - swap reviewer+solver agent pairing
  - re-run only impacted checks
- **Last chance**: one automatic alternative attempt after `2N`
- **Post 2x+1 fail**: set `needs_user_decision=true` and stop for user direction

State contract for hook enforcement lives in:
- `orchestration_control.active_gate_*` (fast path for hooks)
- `orchestration_control.gates.{gate_id}` (per-gate detailed counters)

### Dynamic Prompt Injection
When entering fallback or last-chance stages, orchestrator writes:
- `orchestration_control.dynamic_prompt_text` (plain text, single-shot guidance)
- `orchestration_control.dynamic_prompt` metadata (`source`, `strategy_tag`, `used`)

Fallback templates are available in:
- `${CLAUDE_PLUGIN_ROOT}/skills/rat-auto-design/templates/escalation-prompts.json` (plugin runtime)
- `skills/rat-auto-design/templates/escalation-prompts.json` (development repo context)

Use templates only when LLM-generated prompt text is unavailable.
If both paths are unreadable, orchestrator MUST use the built-in defaults below and still
write the chosen text into `orchestration_control.dynamic_prompt_text` with
`orchestration_control.dynamic_prompt.source = "builtin"`:
- `primary`: Continue current gate workflow, focus on pending criteria with existing agent assignment.
- `fallback`: Split failing scope by module/requirement, switch reviewer+solver pairing, rerun impacted checks only.
- `last_chance`: Apply one non-overlapping alternative strategy, record deltas, prepare escalation context.
- `user_escalation`: Retries exhausted; ask user with failure summary, attempted strategies, and recommended options.

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
| 1→2 | `docs/phase-1-research/`: iron-requirements.json + io_definition.json + timing_constraints.json + domain-analysis.md (open-requirements.json optional — absent if P1 had no open items) | `reviews/phase-1-research/research-review.md` + per-round `research-review-r1..r3.md` (mandatory) | verdict=PASS (3-round chief review converged, or gaps escalated and user-approved; all requirements clear, consistent, implementable) | quality gates per p1-spec-research-policy |
| 2→3 | `docs/phase-2-architecture/architecture.md` (with D2 block diagram) + iron-requirements.json (P2, REQ-A-*) + `refc/*/*.c` | `reviews/phase-2-architecture/architecture-review.md` + `feature-coverage.md` + per-round `architecture-review-r{N}.md` (min 2) | verdict=PASS AND 100% REQ coverage AND review converged | quality gates per p2-arch-design-policy |
| 3→4 | `docs/phase-3-uarch/*.md` + iron-requirements.json (P3, REQ-U-*) + `bfm/` directory | `reviews/phase-3-uarch/uarch-review.md` + `feature-preservation.md` + per-round `uarch-review-r{N}.md` (min 2) | verdict=PASS AND 100% feature preservation AND review converged | quality gates per rtl-p3-uarch-policy |
| 4→5 | `rtl/*/*.sv` (all lint-clean) + `sim/*/tb_*.sv` + `sim/*/*_results.txt` (all PASS) + basic integration smoke PASS + Stream B artifacts (see Stream B Rules) | `reviews/phase-4-rtl/functional-completeness.md` + `design-review.md` + `lint-report.md` | verdict=PASS on all three (100% functional coverage, lint 0 errors) | quality gates per rtl-p4-implement-policy |
| 5 completion | all verification sub-phases (5a-5e) PASS | `reviews/phase-5-verify/requirement-traceability.md` + `e2e-traceability.md` + `final-compliance.md` | verdict=PASS (every requirement implemented, verified, passing) | quality gates per rtl-p5-verify-policy |
| 5→6 | — (artifact-only gate) | `reviews/phase-5-verify/final-compliance.md` | verdict=PASS | — |
| 6 completion | `reviews/phase-6-review/design-note.md` (complete document) + `improvements.md` (recommendations produced) | `reviews/phase-6-review/code-review.md` + `design-review.md` | verdict=PASS on both; on FAIL iterate review → fix cycle (max 2 rounds) | quality gates per rtl-p6-design-review-policy |

**Phase 1 gate additions** (owned by this policy): compliance-checker verifies iron
requirements have no internal contradictions; arch-designer confirms implementation
feasibility (every requirement realizable in RTL within reasonable area/timing).

**Summary Validation** (every P1-P5 gate): `docs/phase-1-research/phase-1-summary.md`,
`docs/phase-2-architecture/phase-2-summary.md`, `docs/phase-3-uarch/phase-3-summary.md`,
`docs/phase-4-rtl/phase-4-summary.md`, `docs/phase-5-verify/phase-5-summary.md` must exist
(format: max 1 page with tables for Key Decisions, Module Inventory, Interface Summary,
Quality Gate Results, Open Items, Document References)

**ADR Recording** (Phase 2→3 and 3→4 gates): 3-5 key decisions → `docs/decisions/ADR-{NNN}.md`

**Phase 2 Iterative Review**: reviewer roster, round semantics, rebuttal protocol, and
convergence criteria are owned by p2-arch-design-policy (dynamic convergence: min 2, max 5
rounds; domain experts conditional on domain-package presence).

**Phase 3 Iterative Review**: reviewer roster (incl. BFM reviewer), round semantics,
rebuttal protocol, and convergence criteria are owned by rtl-p3-uarch-policy (dynamic
convergence: min 2, max 5 rounds; domain experts conditional on domain-package presence).

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
- **Gate ladder exhausted** (per Escalation Ladder: `N → 2N → last-chance`) → set `needs_user_decision=true`, stop and ask user before any further retry
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
