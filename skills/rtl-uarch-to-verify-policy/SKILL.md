---
name: rtl-uarch-to-verify-policy
description: "Policy rules, prerequisite definitions, phase gate criteria, feedback loop classification, and checklists for the Phase 4→5 pipeline. Pure reference — no orchestration."
user-invocable: false
---

# μArch-to-Verify Policy

## Core Principles

### Hierarchical Spec Compliance
Lower phases MUST NOT violate upper phase specifications:
  Spec → Architecture → μArch → RTL → Verification
RTL must faithfully implement the μArch design. Verification must validate against the original Spec.

### Design Priority Order
1. Functional Correctness (highest) — Every required feature works exactly
2. Interface Compliance — Ports, protocols, timing match Architecture
3. Timing/Performance — Throughput, latency targets met
4. Area/Power (lowest)

### Document-as-Memory
Phase 4 reads Phase 1-3 documents as input context. Phase 5 reads Phase 4 artifacts.
No agent needs to "remember" another agent's output — it reads the document.
State is persisted at `.rtl-agent-team/state/rtl-uarch-to-verify-state.json` for resumability.

## Execution Rules

### Dual-Layer Phase Gates
Phase 4→5 transition requires BOTH:
1. **Artifact Gate**: Required files exist (fast check)
2. **Quality Gate**: Reviewer agent(s) verify quality AND hierarchical spec compliance

Quality Gate verdicts: `PASS` or `FAIL + findings[]`

### Gate Retry Policy
- Artifact Gate failure: retry phase once, then escalate to user
- Quality Gate failure: pass findings to worker agent, re-run gate. Max 2 retries
- Upper-spec violation: IMMEDIATE STOP (see Escalation)

### Context Manifests
Each phase has a manifest (`skills/rtl-autopilot/templates/context-manifest-phase-{N}.json`) declaring:
- `required_full_read`: files that MUST be fully read before starting the phase
- `required_summary_only`: files where only the phase summary is sufficient
- `optional_on_demand`: files read only when a specific question arises

### Termination
After Phase 5 Final Compliance Gate PASS, generate summary, then STOP.
Do NOT proceed to Phase 6.

## Prerequisite Requirements

| Artifact | Required Check |
|----------|---------------|
| `docs/phase-3-uarch/*.md` | At least one μArch module spec exists |
| `reviews/phase-3-uarch/uarch-review.md` | File exists AND contains `Verdict: PASS` |
| `docs/phase-1-research/requirements.json` | File exists (needed for traceability) |
| `docs/phase-1-research/io_definition.json` | File exists (needed for port verification) |
| `refc/*/*.c` | At least one C reference model source exists |
| `docs/phase-3-uarch/phase-3-summary.md` | File exists (Phase 3 summary for context) |

### Intake Checklist (from rtl-spec-to-uarch)
- [ ] Phase 3 summary exists: `docs/phase-3-uarch/phase-3-summary.md`
- [ ] All μArch specs exist: `docs/phase-3-uarch/{module}.md` for each module
- [ ] Phase 3 review passed: `reviews/phase-3-uarch/uarch-review.md` verdict=PASS
- [ ] Feature preservation verified: `reviews/phase-3-uarch/feature-preservation.md`
- [ ] State file updated: `.rtl-agent-team/state/{module}-phase-3-complete.json`
- [ ] Context manifest ready: `skills/rtl-autopilot/skills/rtl-autopilot/templates/context-manifest-phase-4.json` references valid files

## Phase Gate Definitions

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
- rtl-critic: functional coverage matrix (every requirement traced to RTL). Any MISSING → FAIL
  - Code quality: proper FSM, no latches, clean reset
  - Synthesizability: no non-synth constructs
  - Convention: i_/o_, {domain}_clk, logic only
  - Save: `reviews/phase-4-rtl/functional-completeness.md`, `reviews/phase-4-rtl/design-review.md`
- lint-checker: zero errors, warnings reviewed
  - Save: `reviews/phase-4-rtl/lint-report.md`
- **Verdict**: PASS if 100% functional coverage AND lint-clean AND design quality passes

**Summary Validation**: `docs/phase-4-rtl/phase-4-summary.md` must exist

### Phase 5 Completion
**Artifact Gate**: all verification sub-phases (5a-5e) pass
**Quality Gate**:
- func-verifier: Requirement Traceability Matrix
  - Save: `reviews/phase-5-verify/requirement-traceability.md`
- rtl-architect: end-to-end final compliance review + E2E Traceability Matrix
  - Save: `reviews/phase-5-verify/final-compliance.md`, `reviews/phase-5-verify/e2e-traceability.md`
- **Verdict**: PASS if every requirement is implemented, verified, and passing

**Summary Validation**: `docs/phase-5-verify/phase-5-summary.md` must exist

## Stream B Rules (Phase 4)

Stream B artifacts generated concurrently with Stream A (RTL implementation):
- B1. SVA property skeletons → `docs/phase-4-rtl/stream-b-sva-skeletons.md`
- B2. Preliminary CDC topology → `docs/phase-4-rtl/stream-b-cdc-preliminary.md`
- B3. cocotb TB skeletons → `docs/phase-4-rtl/stream-b-tb-skeletons.md`

**Traceability Convention**:
- SVA: `// Source: docs/phase-3-uarch/{module}.md, Section: {section}`
- CDC: each CDC path references architecture clock domain definition
- TB: `# REQ-{NNN}: {description}`

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
- Append entry to `docs/lessons-learned.md` using `skills/rtl-autopilot/templates/lessons-learned-entry.md` format
- Record: symptom, root cause, fix applied, prevention strategy, related REQ/module/ADR

## Escalation & Stop Conditions

- Prerequisites not met → report missing artifacts, suggest rtl-spec-to-uarch
- Phase 4 Quality Gate fails after 2 retries → ask user for RTL implementation direction
- Phase 5 sub-phase fails after 2 feedback loops → escalate to user
- DESIGN_FIX detected → STOP immediately, report upper-spec violation to user
- Coverage below target after additional test generation → ask user for acceptable threshold

## Coding Convention Summary

All phases must enforce:
- Port prefix: `i_`, `o_`, `io_` (NOT suffix). Clock/reset exempt
- Clock: `clk` (single) or `{domain}_clk` (multiple). Reset: `rst_n` or `{domain}_rst_n`
- `logic` only (no `reg`/`wire`), `always_ff`/`always_comb`, ANSI port style
- Instance prefix: `u_`, generate prefix: `gen_`
- SV RTL: IEEE 1800-2009. SV Verification: IEEE 1800-2012. C ref model: C11

## Final Checklist

- [ ] Prerequisites: all Phase 1-3 artifacts verified present
- [ ] Phase 4 Stream A: rtl/*/*.sv exist, all lint-clean
- [ ] Phase 4 Stream A: sim/*/tb_*.sv exist for all modules, unit tests all PASS
- [ ] Phase 4 Stream B: SVA skeletons, CDC preliminary, TB skeletons exist
- [ ] Phase 4: functional-completeness.md 100%, design-review.md PASS, lint-report.md zero errors
- [ ] Phase 4: phase-4-summary.md generated
- [ ] Phase 5a: formal-review.md exists
- [ ] Phase 5b: cdc-report.md exists
- [ ] Phase 5c: requirement-traceability.md exists
- [ ] Phase 5d: coverage-report.md exists
- [ ] Phase 5e: e2e-traceability.md + final-compliance.md verdict=PASS
- [ ] Phase 5: phase-5-summary.md generated
- [ ] State file updated with all phases completed
- [ ] Pipeline did NOT proceed to Phase 6
