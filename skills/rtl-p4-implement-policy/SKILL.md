---
name: rtl-p4-implement-policy
description: "Policy rules, 10-Wave pipeline definitions, coding conventions, wave overlap strategy, escalation conditions, and checklists for the Phase 4 RTL implementation pipeline. Pure reference — no orchestration."
user-invocable: false
---

# Phase 4 Implementation Policy

## 10-Wave Pipeline Definition

```
Wave 0:  Prepare      — **Wave 0: Preparation + Test Plan**
         - Step 0a: Module enumeration, directory creation, TODO list (existing)
         - Step 0b: Test plan generation per module via test-plan-writer agent
           - Gate: sim/{module}/{module}_test_plan.md exists for every module
           - Failure: retry once, then proceed with WARNING (Wave 6a must generate missing plans)
Wave 1:  Write All    — One rtl-coder per module, all parallel
Wave 2:  Lint All     — One lint-checker per module, all parallel, collect results
Wave 3:  Fix Lint     — ONLY FAIL modules, max 3 rounds, re-lint only fixes
Wave 4:  Code Review  — rtl-critic per lint-clean module, parallel
Wave 5:  Bugfix       — ONLY REVIEW_FAIL modules, max 3 review→fix iterations
Wave 6a: Tier 1 Smoke — testbench-dev + eda-runner per module, parallel
Wave 6b: Tier 2 Unit  — Ref model comparison, REQ-U-* tracing, FSM >= 50%, line >= 60%, covergroups >= 1, codec conformance PASS/N/A
Wave 7:  Module CDC   — cdc-checker per multi-domain module, parallel
Wave 8:  Module Proto — protocol-checker per bus-interface module, parallel
Wave 9:  Refactoring  — rtl-p4s-refactor for flagged modules, selective
Wave 10: Integration  — smoke test + spec compliance + Stream B + Phase 4 gate
```

Key principles:
- "Lint all at once, fix only failures, re-lint only fixes"
- "Code review before testing — catch design bugs early"
- "Module-level CDC/protocol before Phase 5 — catch hazards early"
- "Stream B synthesis smoke test — catch latch inference and unmappable constructs before Phase 5"
- Modules that pass early waves start later waves immediately

## Wave Overlap Rules

- Waves 1-3 (Write/Lint/Fix): batch, then progress together
- Waves 4-5 (Review/Bugfix): REVIEW_PASS modules proceed to Wave 6a immediately
- Wave 6a (Smoke): per-module, can overlap; Wave 6b (Tier 2): global, starts after ALL modules pass Wave 6a
- Waves 7-8 (CDC/Protocol): can overlap for different modules, parallel with Wave 6b
- Wave 9 (Refactor): requires Wave 6b complete (avoids invalidating unit_results)
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
  "wave_6a_tier1_smoke": "PASS|FAIL",
  "wave_6b_tier2_unit": "PASS|FAIL",
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

## Memory Wrapper Rules

Storage elements specified as "SRAM wrapper" in Phase 3 μArch docs MUST use standardized wrappers:

**Wrapper placement**: `rtl/common/` (shared across modules)

**Standard wrappers** (parameterized behavioral models for simulation, replaced by foundry macros for synthesis):

| Wrapper | File | Use |
|---------|------|-----|
| `sram_sp` | `rtl/common/sram_sp.sv` | Single-port: 1 R/W port, single clock |
| `sram_tp` | `rtl/common/sram_tp.sv` | Two-port: 1W + 1R, single clock (`clk`) |
| `sram_dp` | `rtl/common/sram_dp.sv` | Dual-port: 1W + 1R, dual clock (`wclk`/`rclk`) |

**Parameter contract**:
- `DEPTH`: number of entries (power-of-2 recommended for efficient address decode)
- `WIDTH`: bits per entry
- Derived: `ADDR_W = $clog2(DEPTH)` (localparam inside wrapper)

**Port naming** (SP example):
- `clk` — clock
- `i_ce` — chip enable (active-high)
- `i_we` — write enable (active-high)
- `i_addr [ADDR_W-1:0]` — address
- `i_wdata [WIDTH-1:0]` — write data
- `o_rdata [WIDTH-1:0]` — read data (1-cycle latency, registered output)

**TP port naming** (two-port: 1W + 1R, single clock):
- `clk` — clock
- `i_wen` — write enable
- `i_waddr [ADDR_W-1:0]` — write address
- `i_wdata [WIDTH-1:0]` — write data
- `i_ren` — read enable
- `i_raddr [ADDR_W-1:0]` — read address
- `o_rdata [WIDTH-1:0]` — read data (1-cycle latency)

**DP port naming** (dual-port: 1W + 1R, dual clock):
- `wclk` — write clock
- `i_wen` — write enable
- `i_waddr [ADDR_W-1:0]` — write address
- `i_wdata [WIDTH-1:0]` — write data
- `rclk` — read clock
- `i_ren` — read enable
- `i_raddr [ADDR_W-1:0]` — read address
- `o_rdata [WIDTH-1:0]` — read data (1-cycle latency, rclk domain)

**Instance naming**: `u_mem_{purpose}` (e.g., `u_mem_coeff`, `u_mem_line_buf`)

**Foundry macro replacement strategy**:
- Behavioral wrapper is used for simulation and open-source synthesis (Yosys infers BRAM)
- For ASIC: replace `sram_sp` body with foundry-specific macro instantiation behind `` `ifdef SYNTHESIS `` guard
- Wrapper interface stays identical — no RTL changes outside the wrapper

**Wave 1 responsibility**: rtl-coder creates `rtl/common/sram_*.sv` wrappers if not already present, then instantiates them in modules per μArch spec.

## Combinational Chain Depth Heuristic

Sequential dependency loops in always_comb (e.g., error diffusion, SAD accumulation,
carry chains) create deep combinational paths that risk timing closure.

- **Threshold**: > 4 sequential-dependency iterations in a single always_comb block is a timing risk
- **If uArch budgets extra latency**: split into sub-stages with pipeline registers at N/2
- **If uArch requires single-cycle**: do NOT split — escalate to rtl-architect/timing-advisor for review
- **Exceptions**: FPGA carry chains, balanced adder trees, and low-frequency clock domains
  may tolerate deeper chains — document the justification

**Pattern**: `for (s = 0; s < N; s++)` where iteration s depends on iteration s-1
  → split at N/2 with registered intermediate results (when latency budget allows)

Examples where split was beneficial (ASIC):
- Error diffusion: 4-sample chain × 2 sub-blocks → split into 2+2
- SAD accumulation: 8 abs-diff + sum → register after 4
- Carry chain: 16-bit ripple → register at bit 8 (ASIC only — FPGA carry chains are an exception)

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

## Structural Verification in Code Review (Wave 4)

Wave 4 code review MUST include automated structural checks (performed by rtl-critic):
1. FSM state completeness: all uarch spec states present in RTL
2. Pipeline depth: RTL stages match uarch spec ±1
3. Port mapping: all uarch spec ports present with correct direction/width
4. Timing contract: pipeline supports specified latency (if documented)

Structural findings are classified:
- CRITICAL: missing FSM state, missing port → triggers Wave 5 bugfix
- MAJOR: pipeline depth mismatch, timing violation → triggers Wave 5 bugfix
- MINOR: naming inconsistency → advisory only

REVIEW_PASS requires zero CRITICAL structural findings.

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
  - Timing contract assertion checks for interfaces with timing specs in uarch
  - valid/ready backpressure exercise
  - Multi-beat transfer protocol verification
- Phase 5 (rtl-p5s-protocol-verify): System-level protocol — end-to-end transaction flow
- Phase 4 catches per-interface violations + timing contract mismatches; Phase 5 catches integration-level protocol issues

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

## Wave 6a/6b Unit Test Scope

- **Wave 6a** (Tier 1 Smoke): Basic I/O stimulus, FSM state coverage,
  self-checking assertions. Quick pass/fail per module.
  Produces: `sim/{module}/tb_{module}.sv`
- **Wave 6b** (Tier 2 Unit — MANDATORY): Reference model comparison
  (DPI-C or file-based), uarch feature-level coverage with REQ-U-* tracing,
  per-feature result JSON. Deeper per-module verification.
  Extends: `sim/{module}/tb_{module}.sv` (adds reference comparison logic to
  existing Wave 6a TBs, does NOT replace them).
  Gate: `sim/{module}/{module}_unit_results.json` with `ref_mismatches=0`,
  coverage meeting thresholds (FSM >= 50%, line >= 60%), `req_ids` populated,
  `func_coverage.covergroups_defined >= 1`, and `codec_conformance` PASS/N/A.
- **rtl-p4s-unit-test** (standalone skill): Can still be invoked independently
  for ad-hoc Tier 2 testing outside the pipeline

## AC Coverage at Wave 6b (Advisory)
When iron-requirements has structured acceptance_criteria (with ac_id) for a REQ-U-*:
  ac_ids should be populated for each unit test feature covering that requirement.
  This is advisory at P4 (not hard-block). Incomplete AC coverage is flagged as WARNING
  and deferred to P5 for closure.
When no structured AC: existing req_ids gate applies unchanged.

## Rapid-Impl to Full-Impl Transition

- `rtl-p4-rapid-impl` produces: lint-clean modules, module-level CDC pass,
  smoke functional pass, block sanity pass. State in `p4-state.json`.
- `rtl-p4-implement` adds: code review (Wave 4-5), Tier 1 smoke tests (Wave 6a),
  Tier 2 unit tests (Wave 6b), protocol checks (Wave 8), refactoring (Wave 9),
  integration gate (Wave 10), Stream B artifacts.
- Transition: Full-impl orchestrator should detect existing lint-clean modules
  from rapid-impl and skip Waves 1-3 for those modules. Detection via:
  `rtl/*/*.sv` exists + lint passes.

## Phase 4 Sub-Skills Integration

- `rtl-p4s-bugfix`: Used in Wave 5 for review-driven fixes, and Wave 6 for test-driven fixes
- `rtl-p4s-refactor`: Used in Wave 9 for code quality improvements
- `rtl-p4s-unit-test`: Tier 2 testing (used in Wave 6b for mandatory per-module verification; also available standalone)
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
- [ ] Per-module review reports at `.rat/scratch/phase-4/`
- [ ] No module blocked after 3 review→fix iterations

**Test Plan:**
- [ ] sim/{module}/{module}_test_plan.md exists for every module (Wave 0 Step 0b)

**Unit Test (Tier 1 + Tier 2):**
- [ ] sim/{module}/tb_{module}.sv exists for every module
- [ ] All Tier 1 smoke tests PASS (sim/{module}/{module}_results.txt)
- [ ] All Tier 2 unit tests PASS (sim/{module}/{module}_unit_results.json with ref_mismatches=0)
- [ ] Tier 2 coverage meets thresholds: FSM >= 50%, line >= 60%
- [ ] Every feature entry in unit_results.json has `req_ids` populated (REQ-U-* tracing)
- [ ] Functional coverage: `func_coverage.covergroups_defined >= 1` per module
- [ ] Codec conformance PASS (if H.264/H.265 decoder — Step 5a)

**AC Coverage (advisory):**
- [ ] ac_ids populated in unit_results.json when acceptance_criteria exist (advisory)

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

**Stream B (content quality verified):**
- [ ] docs/phase-4-rtl/stream-b-sva-skeletons.md saved — contains `property`/`assert` per module
- [ ] docs/phase-4-rtl/stream-b-cdc-preliminary.md saved — references clock domain names from `clock-domain-map.md`
- [ ] docs/phase-4-rtl/stream-b-tb-skeletons.md saved — references `REQ-` tag per module + contains test function/task
- [ ] docs/phase-4-rtl/stream-b-synth-estimate.md saved (synthesis smoke test — no inferred latches, no unmappable constructs)

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
