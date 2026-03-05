---
name: rtl-p4-implement-policy
description: "Policy rules, 10-Wave pipeline definitions, coding conventions, wave overlap strategy, escalation conditions, and checklists for the Phase 4 RTL implementation pipeline. Pure reference — no orchestration."
user-invocable: false
---

# Phase 4 Implementation Policy

## 10-Wave Pipeline Definition

```
Wave 0:  Prepare      — Enumerate modules, create per-module TODO, identify dependency order
Wave 1:  Write All    — One rtl-coder per module, all parallel
Wave 2:  Lint All     — One lint-checker per module, all parallel, collect results
Wave 3:  Fix Lint     — ONLY FAIL modules, max 3 rounds, re-lint only fixes
Wave 4:  Code Review  — rtl-critic per lint-clean module, parallel
Wave 5:  Bugfix       — ONLY REVIEW_FAIL modules, max 3 review→fix iterations
Wave 6:  Unit TB+Sim  — testbench-dev + eda-runner per module, parallel
Wave 7:  Module CDC   — cdc-checker per multi-domain module, parallel
Wave 8:  Module Proto — protocol-checker per bus-interface module, parallel
Wave 9:  Refactoring  — rtl-p4s-refactor for flagged modules, selective
Wave 10: Integration  — smoke test + spec compliance + Stream B + Phase 4 gate
```

Key principles:
- "Lint all at once, fix only failures, re-lint only fixes"
- "Code review before testing — catch design bugs early"
- "Module-level CDC/protocol before Phase 5 — catch hazards early"
- Modules that pass early waves start later waves immediately

## Wave Overlap Rules

- Waves 1-3 (Write/Lint/Fix): batch, then progress together
- Waves 4-5 (Review/Bugfix): REVIEW_PASS modules proceed to Wave 6 immediately
- Waves 6-9 (Test/CDC/Protocol/Refactor): can overlap for different modules
- Wave 10 (Integration + Gate): requires ALL modules complete Waves 1-9

## Per-Module State Tracker Schema

```json
{
  "module": "{module}",
  "wave_1_write": "DONE",
  "wave_2_lint": "PASS|FAIL",
  "wave_3_fix": "PASS|SKIP",
  "wave_4_review": "REVIEW_PASS|REVIEW_FAIL",
  "wave_5_bugfix": "PASS|SKIP",
  "wave_6_unit_test": "PASS|FAIL",
  "wave_7_cdc": "CDC_PASS|CDC_FAIL|SKIP",
  "wave_8_protocol": "PROTOCOL_PASS|PROTOCOL_FAIL|SKIP",
  "wave_9_refactor": "DONE|SKIP",
  "wave_10_gate": "PASS|FAIL"
}
```

## Coding Convention Summary (Core Overrides)

All RTL produced in Phase 4 MUST follow:
- Port prefix: inputs `i_`, outputs `o_`, bidirectional `io_` (NOT suffix `_i`/`_o`)
- Clock: `clk` (single domain) or `{domain}_clk` (e.g., `sys_clk`) — NOT `clk_i`, `clk_sys`
- Reset: `rst_n` (single domain) or `{domain}_rst_n` (e.g., `sys_rst_n`) — NOT `rst_ni`
- Clock/reset ports do NOT need `i_` prefix
- `logic` only — `reg` and `wire` keywords FORBIDDEN
- `always_ff` for sequential, `always_comb` for combinational — no bare `always`
- `typedef enum logic [N:0]` for FSM states, `typedef struct packed` for grouped signals
- Instance prefix: `u_`, generate prefix: `gen_`
- Parameters: `UPPER_SNAKE_CASE`, localparam: `L_` prefix, types: `snake_case_t`
- ANSI port style, one module per file

## Code Review Focus Areas (Wave 4)

Per-module review by rtl-critic:
1. **uarch compliance**: does RTL match docs/phase-3-uarch/{module}.md?
2. **Interface compliance**: do ports match io_definition.json?
3. **FSM completeness**: all states from uarch spec present?
4. **Pipeline correctness**: stage count, latency, throughput match uarch?
5. **Coding style**: naming conventions, parameterization, comments
6. **Logical correctness**: off-by-one, sign extension, width mismatches
7. **Power**: unnecessary toggling, missing clock gating opportunities

Classification: REVIEW_PASS (0 critical/major findings) or REVIEW_FAIL.

## Code Review Iteration Protocol (Wave 5)

- Round 1: Full review (all focus areas)
- Round 2: Targeted re-review (only previously failed focus areas)
- Round 3: Final check (must pass or escalate)

## CDC Check Scope (Phase 4 vs Phase 5)

- Phase 4 (Wave 7): Module-level CDC — within each module boundary
- Phase 5 (rtl-p5s-cdc-verify): System-level CDC — across module boundaries, top-level analysis
- Phase 4 catches module-internal hazards early; Phase 5 catches inter-module hazards

## Protocol Check Scope (Phase 4 vs Phase 5)

- Phase 4 (Wave 8): Module-level protocol — each module's bus interfaces in isolation
- Phase 5 (rtl-p5s-protocol-verify): System-level protocol — end-to-end transaction flow
- Phase 4 catches per-interface violations; Phase 5 catches integration-level protocol issues

## Refactoring Decision Criteria (Wave 9)

- Module >500 lines: consider splitting
- 3+ modules share similar code: extract common module
- Naming inconsistency flagged by rtl-critic: rename pass
- Missing parameterization: add parameters for magic numbers
- Refactoring is selective — not all modules need it
- Refactor equivalence proof policy:
  - Cosmetic/style-only cleanup: lint + smoke simulation minimum
  - Any change touching combinational/sequential logic, reset, clock enable, or constraints intent:
    invoke equivalence-checker (RTL-vs-RTL) before Wave 10 gate

## Phase 4 Sub-Skills Integration

- `rtl-p4s-bugfix`: Used in Wave 5 for review-driven fixes, and Wave 6 for test-driven fixes
- `rtl-p4s-refactor`: Used in Wave 9 for code quality improvements
- `rtl-p4s-unit-test`: Tier 2 testing (used after Phase 4 for deeper per-module verification)
- `rtl-lint-check`: Used in Waves 2-3 and after any code modification

## Escalation & Stop Conditions

- Module still has lint errors after 3 fix rounds → escalate to rtl-architect for design review
- Module fails code review after 3 review→fix iterations → escalate to rtl-architect for structural redesign
- uarch spec is ambiguous for a module → pause that module, flag to user, continue others
- Unit test fails after 3 debug→fix→re-sim iterations → escalate to waveform-analyzer + rtl-architect
- CDC FAIL after 2 fix rounds → escalate to cdc-reviewer for synchronization strategy
- CDC FAIL where root cause is clock source/clock gating/clock mux relationship ambiguity →
  escalate to clock-architect (in addition to cdc-reviewer)
- Protocol FAIL after 2 fix rounds → escalate to protocol-reviewer for interface redesign
- Functional coverage review FAIL with >3 missing REQs → pause, flag to user (potential uarch spec gap)

## Phase 4 Gate Criteria

ALL of the following must be true before Phase 5:

**RTL Files:**
- [ ] rtl/*/*.sv exists for every block in docs/phase-3-uarch/
- [ ] rtl/filelist_{module}.f exists for every module
- [ ] rtl/filelist_top.f exists and includes all module filelists

**Lint:**
- [ ] All files pass `verilator --lint-only -Wall` with zero errors
- [ ] No module blocked after 3 lint fix rounds

**Code Review:**
- [ ] All modules reviewed by rtl-critic (Wave 4)
- [ ] All modules REVIEW_PASS (0 critical/major findings)
- [ ] Per-module review reports at `.rtl-agent-team/scratch/phase-4/`
- [ ] No module blocked after 3 review→fix iterations

**Unit Test:**
- [ ] sim/{module}/tb_{module}.sv exists for every module
- [ ] All unit tests PASS (sim/{module}/{module}_results.txt)

**CDC:**
- [ ] All multi-domain modules CDC-checked (Wave 7)
- [ ] All multi-domain modules CDC_PASS
- [ ] Single-domain modules explicitly marked as skip

**Protocol:**
- [ ] All bus-interface modules protocol-checked (Wave 8)
- [ ] All bus-interface modules PROTOCOL_PASS
- [ ] No-interface modules explicitly marked as skip

**Refactoring:**
- [ ] Flagged modules refactored (Wave 9)
- [ ] Equivalence verified for all refactored modules
- [ ] For logic/clock/reset-impact refactors: equivalence-checker report exists (RTL-vs-RTL)

**Integration + Gate:**
- [ ] Basic integration smoke test PASS
- [ ] rtl-critic functional coverage verdict is PASS
- [ ] Every REQ-NNN implemented in at least one RTL module
- [ ] reviews/phase-4-rtl/functional-completeness.md saved
- [ ] reviews/phase-4-rtl/design-review.md saved
- [ ] reviews/phase-4-rtl/lint-report.md saved

**Stream B:**
- [ ] docs/phase-4-rtl/stream-b-sva-skeletons.md saved
- [ ] docs/phase-4-rtl/stream-b-cdc-preliminary.md saved
- [ ] docs/phase-4-rtl/stream-b-tb-skeletons.md saved

**Naming Conventions:**
- [ ] All port names use `i_`/`o_`/`io_` prefix (NOT suffix `_i`/`_o`)
- [ ] All clocks: `clk` or `{domain}_clk` — NOT `clk_i`, `clk_sys`
- [ ] All resets: `rst_n` or `{domain}_rst_n` — NOT `rst_ni`
- [ ] All instances: `u_` prefix, generates: `gen_` prefix
- [ ] `logic` only — no `reg`/`wire` keywords
- [ ] `always_ff`/`always_comb` — no bare `always`
- [ ] Parameters: `UPPER_SNAKE_CASE`, localparam: `L_` prefix, types: `snake_case_t`

**Summary:**
- [ ] docs/phase-4-rtl/phase-4-summary.md generated
