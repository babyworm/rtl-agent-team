---
name: rtl-p5-verify-policy
description: "Verification criteria, module graduation gates, coverage targets, synthesis estimation policy, and checklists for the Phase 5 three-stage verification pipeline. Pure reference — no orchestration."
user-invocable: false
---

# Phase 5 Verification Policy

## Three-Stage Architecture

Stage 1 (Module): Each module independently verified in parallel across 9 categories.
Stage 2 (Top): System-level verification after ALL modules graduate.
Stage 3 (Final): Compliance review + summary generation.

**Core principle**: Module-level verification first, top-level only after module graduation.
A module "graduates" when ALL its verification checks PASS. Only graduated modules
participate in top-level integration. This prevents wasting top-level sim time on
modules with known bugs.

## Verification Categories

Applied at both module-level (Stage 1) and top-level (Stage 2):
```
V1: Lint (final comprehensive)         → lint-checker
V2: SVA Completion + Formal            → sva-extractor + eda-runner
V3: CDC/RDC Analysis                   → cdc-checker + constraint-writer
V4: Protocol Compliance                → protocol-checker (if bus interfaces)
V5: Functional Regression (Tier 3/4)   → testbench-dev + eda-runner + func-verifier
V6: Coverage Analysis                  → coverage-analyst + testbench-dev
V7: Performance Verification           → perf-verifier + eda-runner
V8: Synthesizability + PPA Estimation  → eda-runner + synthesis-reporter
V9: Code Review + Refactoring          → rtl-critic + rtl-p4s-refactor
```

## Parallelism Model (Stage 1 per module)

```
Parallel Group A: V1(Lint) + V2(SVA/Formal) + V3(CDC) + V4(Protocol) + V8(Synth Est.)
Sequential: V5(Functional) starts after V1 pass (lint-clean required for sim)
Incremental: V6(Coverage) starts as V5 data arrives
Sequential: V7(Performance) after V5 pass (functional correctness required)
Final: V9(Code Review) after V1-V8 results inform review scope
```

### Overlap Rules
- Stage 1 modules are fully independent → all modules run simultaneously
- Within a module, Groups A/B/C progress as dependencies are met
- Stage 2 starts as soon as ALL modules graduate (not before)
- Stage 3 starts after Stage 2 completes

## Module Graduation Gate

A module graduates when ALL of:
- [x] V1: lint PASS (verilator + slang)
- [x] V2: formal — all properties proved or justified timeout
- [x] V3: CDC — zero VIOLATION (CAUTION acceptable with justification)
- [x] V4: protocol — PASS or n/a
- [x] V5: functional — all scenarios × all seeds PASS
- [x] V6: coverage — targets met (line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%)
- [x] V7: performance — all metrics within 10% of BFM baseline
- [x] V8: synthesizable — no latches, PPA estimate in NAND2-FO2 gate count
- [x] V9: code review — no critical findings

**On FAIL**: invoke rtl-p4s-bugfix (feedback loop, max 2 per module).
After fix, re-verify ONLY the failed categories (not all 9).

## AC-Level Module Graduation (when applicable)
When structured acceptance_criteria (with ac_id) exist in iron-requirements:
  **Module graduation (Stage 1):**
  - VERIFIED or FORMAL ac_ids: PASS
  - PARTIAL Critical/High ac_ids: WARNING — module graduates but flagged for Stage 3 closure
  - UNTESTED Critical/High ac_ids: FAIL — module does not graduate
  - NOT_VERIFIABLE ac_ids (verifiable: false): excluded from gate

  **Stage 3 audit (final, pre-P6):**
  - All Critical/High ac_ids must be VERIFIED or FORMAL (PARTIAL no longer accepted)
  - UNTESTED or PARTIAL Critical/High ac_ids at Stage 3 → FAIL (blocks P6 entry)
When no structured AC: existing REQ-level graduation applies.

## Top-Level Gate

All top-level checks PASS → proceed to Stage 3.
On FAIL → classify and fix:
- UNIT_FIX: single module issue → rtl-p4s-bugfix → re-verify module → re-graduate → re-verify top
- INTEGRATION_FIX: cross-module issue → fix → re-verify affected checks
- DESIGN_FIX: architecture issue → STOP, escalate to user

## Per-Module Verification Tracker Schema

```json
{
  "module": "{module}",
  "status": "pending",
  "checks": {
    "v1_lint": "pending",
    "v2_sva_formal": "pending",
    "v3_cdc": "pending",
    "v4_protocol": "pending|n/a",
    "v5_functional": "pending",
    "v6_coverage": "pending",
    "v7_performance": "pending",
    "v8_synth_est": "pending",
    "v9_code_review": "pending"
  },
  "feedback_loops": 0,
  "graduated": false
}
```

## Functional Verification Scenario Splitting (V5)

Long test suites split by scenario category:
| Category | Description | Typical Vector Count |
|----------|-------------|---------------------|
| basic | Normal operation, happy path | 50-100 |
| corner_case | Boundary conditions, edge cases | 100-200 |
| stress | Maximum throughput, back-to-back, full FIFO | 200-500 |
| error_handling | Invalid inputs, error injection, recovery | 50-100 |

Each scenario category runs as independent parallel agent.
Multi-seed regression per scenario (5 seeds default: 1, 42, 123, 1337, 65536).
Total: M modules × S scenarios × 5 seeds = massive parallelism.
Early termination: >5% failure rate → halt and report.

For very large modules, further split by feature within each category.

## SVA Iterative Refinement

Minimum 3 rounds: Draft → Strengthen → Harden.
- sv2v conversion REQUIRED before SymbiYosys: `sv2v rtl/{module}/*.sv -o rtl/{module}/{module}_v2v.v`
- .sby config MUST reference `_v2v.v` (NOT `.sv`)
- On counterexample: waveform-analyzer diagnoses

## Coverage Targets

| Metric | Target |
|--------|--------|
| Line coverage | ≥ 90% |
| Toggle coverage | ≥ 80% |
| FSM coverage | ≥ 70% |

Iterative coverpoint refinement (minimum 3 rounds).
Generate additional tests for HIGH priority gaps. Re-run regression for new tests.

## Synthesis Estimation Policy (ASIC TSMC 28nm)

Both Module-level (V8) and Top-level (T8):
1. constraint-writer generates SDC (MANDATORY — before synthesis)
2. sv2v conversion: `.sv` → `_v2v.v`
3. Yosys synthesis with NanGate45 liberty (TSMC 28nm proxy)
4. Area reported in NAND2-FO2 gate equivalents (area_um2 / 0.798)

Module-level (Stage 1 V8):
  → Always: synthesis estimation with NanGate45 + NAND2 gate count
  → SDC: per-module clock/IO constraints

Top-level (Stage 2 T8):
  → Always: full synthesis estimation with NanGate45 + SDC
  → User requested full synthesis? → additionally export netlist + JSON report
  → Area metric: ALWAYS NAND2-FO2 gate equivalents (NOT LUTs, NOT raw cell count)

## Parallelism Budget

Theoretical maximum concurrent agents for M modules, S scenarios:
```
Stage 1 Group A: M × 5 checks
Stage 1 Group B: M × S scenarios × 5 seeds
Stage 1 Group C: M × 2 checks
Stage 1 Group D: M × 1

Example: 6 modules, 4 scenarios
  Group A: 30, Group B: 120, Group C: 12, Group D: 6
  Peak: ~168 (practical limit: ~20-30 via run_in_background)
```

## Module Graduation Fast Path

Modules that pass all Group A checks can start Group B immediately without
waiting for other modules' Group A. Each module progresses independently.

## Feedback Loop Classification

| Failure Type | Scope | Fix Approach | Re-verify |
|---|---|---|---|
| UNIT_FIX (lint) | Single module V1 | rtl-coder fix | V1 only |
| UNIT_FIX (SVA) | Single module V2 | rtl-p4s-bugfix | V2 only |
| UNIT_FIX (CDC) | Single module V3 | rtl-coder add sync | V3 only |
| UNIT_FIX (sim) | Single module V5 | rtl-p4s-bugfix | V5 + V6 |
| INTEGRATION_FIX | Cross-module | rtl-p4s-bugfix | Affected Vx + Stage 2 |
| DESIGN_FIX | Architecture | STOP → user | All (after upper phase fix) |

Independent UNIT_FIX failures in different modules: fix in parallel.
Same-module failures: fix sequentially within a single task.
INTEGRATION_FIX: always sequential (cross-module dependencies).

## Integration with rat-auto-design

When invoked from rat-auto-design, state is tracked in `.rtl-agent-team/state/rat-auto-design-state.json`:
```json
{
  "current_phase": 5,
  "completed_sub_phases": ["stage-1-module-a", ...],
  "pending_sub_phases": ["stage-2-integration", "stage-3-compliance"],
  "fix_history": [
    {"sub_phase": "stage-1-v2", "module": "module_a", "fix_count": 1, "status": "resolved"}
  ]
}
```
This enables resume: re-read state and continue from next pending sub-phase.

## UVM Verification (Optional)

If commercial simulator available and UVM mandated, invoke `/rtl-agent-team:rtl-p5s-uvm-verify`
alongside V5. UVM is NOT a replacement for cocotb regression — both provide complementary coverage.

## Escalation & Stop Conditions

- Module feedback loop exhausted (2 cycles for same check) → escalate to user with findings
- DESIGN_FIX detected (architecture-level issue) → IMMEDIATE STOP, escalate to user
- Coverage persistently below target after 3 rounds → escalate to rtl-architect
- Performance deficit >20% → escalate to rtl-architect for pipeline review
- Synthesis estimation shows infeasible design → escalate to user with PPA report
- Multiple modules fail same check type → systematic issue, escalate to rtl-architect
- Stage 2 integration FAIL with >3 bugs → escalate to rtl-architect for interface review
- CDC failures where root cause is uncertain clock relationship/clock gating/muxing →
  escalate to clock-architect + cdc-reviewer before next fix loop
- Tool not installed → eda-runner provides instructions, halt affected check

## Final Checklist

### Stage 1 (Per Module)
- [ ] V1: lint PASS (verilator --lint-only -Wall + slang --lint-only)
- [ ] V2: SVA formal — all properties proved or justified (3+ refinement rounds)
- [ ] V3: CDC — zero VIOLATION, CAUTIONs justified
- [ ] V4: protocol PASS or n/a
- [ ] V5: functional — all scenarios × all seeds PASS
- [ ] V6: coverage targets met (line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%)
- [ ] V7: performance — within 10% of BFM baseline
- [ ] V8: synthesizable — no latches, NAND2-FO2 gate count (NanGate45/28nm)
- [ ] V9: code review — no critical findings, refactoring applied if needed
- [ ] All modules graduated

### Stage 2 (Top-Level)
- [ ] T1: top-level lint PASS
- [ ] T2: system SVA formal PASS
- [ ] T3: system CDC PASS (zero VIOLATION)
- [ ] T4: system protocol PASS
- [ ] T5: integration test (Tier 4) PASS
- [ ] T6: system coverage targets met
- [ ] T7: system performance within spec
- [ ] T8: ASIC 28nm synthesis estimation saved (NanGate45, NAND2-FO2, SDC applied)
- [ ] T9: top-level code review — no critical findings

### Stage 3 (Final)
- [ ] reviews/phase-5-verify/requirement-traceability.md saved
- [ ] reviews/phase-5-verify/e2e-traceability.md saved
- [ ] reviews/phase-5-verify/traceability-audit.md saved with verdict PASS
- [ ] Zero Critical/High priority UNTESTED requirements or ac_ids (when structured AC exists)
- [ ] AC-level traceability audit: no Critical/High ac_id UNTESTED
- [ ] reviews/phase-5-verify/final-compliance.md saved with verdict PASS
- [ ] docs/phase-5-verify/phase-5-summary.md generated
- [ ] docs/phase-5-verify/ reports collected
- [ ] All feedback loops resolved (max 2 per module per check)

## Requirement Traceability Gate (P6 Entry Blocker)

Stage 3 includes a **Formal Traceability Audit** that gates P6 entry:
- Every Critical/High priority requirement in requirements.json must have status
  VERIFIED (simulation test with assertion) or FORMAL (SVA proof)
- PARTIAL Critical/High requirements produce WARNING but do not block
- UNTESTED Critical/High requirements produce FAIL and block P6 entry
- The traceability-audit.md verdict must be PASS for final-compliance.md to pass

This ensures no Critical/High requirement ships without at least one verification artifact.
