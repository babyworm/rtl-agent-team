---
name: rtl-p5-verify
description: "Phase 5 verification orchestrator: two-level (module→top) parallel verification pipeline covering lint, SVA/formal, CDC, protocol, functional regression, coverage, performance, synthesizability estimation, and code review."
---

<Purpose>
Orchestrate comprehensive Phase 5 verification across all RTL modules and the top-level design.
Verification is structured in two levels:
  **Level 1 (Module)**: Each module independently verified in parallel across 9 verification categories
  **Level 2 (Top)**: System-level verification after all modules graduate
  **Level 3 (Final)**: Compliance review + summary generation

**Core principle: module-level verification first, top-level only after module graduation.**
A module "graduates" when ALL its verification checks PASS. Only graduated modules
participate in top-level integration. This prevents wasting top-level sim time on
modules with known bugs.

**Verification Categories (applied at both levels):**
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

Output:
- `docs/phase-5-verify/` — verification data and reports
- `reviews/phase-5-verify/` — verdicts (PASS/FAIL per category)
- `reviews/phase-5-verify/final-compliance.md` — final compliance verdict
</Purpose>

<Use_When>
- Phase 4 is complete (all modules lint-clean, code-reviewed, unit-tested, CDC/protocol checked)
- Stream B artifacts ready (SVA skeletons, preliminary CDC report, TB skeletons)
- Full Phase 5 verification pipeline execution
- Systematic verification closure across all modules
</Use_When>

<Do_Not_Use_When>
- Phase 4 not complete (run rtl-p4-implement first)
- Only a single verification type needed (use the specific rtl-p5s-* sub-skill directly)
- Only bug fix needed (use rtl-p4s-bugfix)
- Only regression re-run needed (use rtl-p5s-func-verify directly)
</Do_Not_Use_When>

<Why_This_Exists>
Phase 5 previously had no dedicated orchestrator — rtl-autopilot handled it inline with
5 sub-phases (5a-5e). This caused several problems:
- No systematic module graduation gate before top-level integration
- No parallel module-level verification across all categories simultaneously
- Functional verification bottlenecked (no scenario splitting)
- Synthesizability estimation deferred to ad-hoc checks
- Code quality degradation during verification not addressed

This skill provides:
- **Maximum parallelism**: M modules × N categories = up to M×N concurrent agents
- **Module graduation**: per-module quality gate before top-level integration
- **Scenario-split functional verification**: long simulations split by scenario, run in parallel
- **ASIC 28nm PPA estimation**: SDC-first synthesis estimation with NanGate45 (NAND2-FO2 gate count)
- **Quality maintenance**: code review + refactoring integrated into verification
- **Two-level architecture**: module bugs caught before expensive top-level sim
</Why_This_Exists>

<Execution_Policy>
- **Stage-based execution** with parallel agent spawning:
  - Stage 0 (Prepare): Enumerate modules, load Stream B artifacts, create tracker
  - Stage 1 (Module-Level): 9 verification categories per module, all modules in parallel
  - Stage 2 (Top-Level): System-level verification after all modules graduate
  - Stage 3 (Final): Compliance review + summary generation

- **Parallelism model** (Stage 1 per module):
  ```
  Parallel Group A: V1(Lint) + V2(SVA/Formal) + V3(CDC) + V4(Protocol) + V8(Synth Est.)
  Sequential: V5(Functional) starts after V1 pass (lint-clean required for sim)
  Incremental: V6(Coverage) starts as V5 data arrives
  Sequential: V7(Performance) after V5 pass (functional correctness required)
  Final: V9(Code Review) after V1-V8 results inform review scope
  ```

- **Functional verification scenario splitting** (V5):
  - Long test suites split by scenario category (e.g., basic, corner, stress, error)
  - Each scenario category runs as independent parallel agent
  - Multi-seed regression per scenario (5 seeds default)
  - Total: M modules × S scenarios × 5 seeds = massive parallelism

- **Module graduation gate**:
  All 9 categories PASS → module graduates to top-level pool
  Any FAIL → feedback to Phase 4 (rtl-p4s-bugfix), max 2 loops per module

- **Synthesis estimation policy** (ASIC TSMC 28nm):
  - SDC constraints MUST be generated BEFORE synthesis estimation
  - Module-level (Stage 1): Yosys synthesis estimation with NanGate45 liberty, area in NAND2-FO2 gate equivalents
  - Top-level (Stage 2): full synthesis estimation with NanGate45 + SDC; netlist export only on user request

- **Overlap rules**:
  - Stage 1 modules are fully independent → all modules run simultaneously
  - Within a module, Groups A/B/C progress as dependencies are met
  - Stage 2 starts as soon as ALL modules graduate (not before)
  - Stage 3 starts after Stage 2 completes
</Execution_Policy>

<Steps>
## Stage 0: Preparation

0.1. Read Phase 4 completion artifacts:
   - `docs/phase-4-rtl/module-descriptions.md` → list of all modules
   - `docs/phase-4-rtl/phase-4-summary.md` → Phase 4 compressed summary
   - `reviews/phase-4-rtl/design-review.md` → Phase 4 review verdict

0.2. Load Stream B artifacts from Phase 4:
   - `docs/phase-4-rtl/stream-b-sva-skeletons.md` → SVA property skeletons (input for V2)
   - `docs/phase-4-rtl/stream-b-cdc-preliminary.md` → preliminary CDC topology (input for V3)
   - `docs/phase-4-rtl/stream-b-tb-skeletons.md` → cocotb TB skeletons (input for V5)

0.3. Create per-module verification tracker:
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

0.4. Create output directories:
   ```bash
   mkdir -p docs/phase-5-verify reviews/phase-5-verify sim/coverage sim/formal sim/cdc
   ```

0.5. Determine functional verification scenarios per module:
   - Read `docs/phase-3-uarch/{module}.md` for feature list
   - Split into scenario categories: basic, corner_case, stress, error_handling
   - Each category becomes an independent parallel task

---

## Stage 1: Module-Level Verification (Parallel per Module)

For EACH module, launch the following verification groups. All modules run simultaneously.

### Group A (fully parallel, no dependencies): V1 + V2 + V3 + V4 + V8

**V1: Final Comprehensive Lint**
```
Skill: /rtl-agent-team:rtl-lint-check
Agent: lint-checker
```
- Run `verilator --lint-only -Wall` AND `slang --lint-only` on rtl/{module}/*.sv
- Verify naming conventions (i_/o_ prefix, {domain}_clk, {domain}_rst_n, logic only)
- Gate: V5 (functional) cannot start until V1 passes

**V2: SVA Completion + Formal Verification**
```
Skill: /rtl-agent-team:rtl-p5s-sva-check
Agents: sva-extractor, eda-runner, waveform-analyzer
```
- Complete SVA skeletons from Stream B (docs/phase-4-rtl/stream-b-sva-skeletons.md)
- Iterative SVA refinement (minimum 3 rounds): Draft → Strengthen → Harden
- **sv2v conversion required before SymbiYosys**: `sv2v rtl/{module}/*.sv -o rtl/{module}/{module}_v2v.v`
- Run SymbiYosys BMC + induction per module (.sby references `_v2v.v`, not `.sv`)
- On counterexample: waveform-analyzer diagnoses

**V3: CDC/RDC Analysis**
```
Skill: /rtl-agent-team:rtl-p5s-cdc-verify
Agents: cdc-checker, constraint-writer
```
- Extend preliminary CDC report from Stream B
- Full static CDC analysis per module
- Generate SDC clock domain constraints
- Flag VIOLATION (missing sync), CAUTION (complex path), CONVENTION (naming)

**V4: Protocol Compliance** (if module has bus interface)
```
Skill: /rtl-agent-team:rtl-p5s-protocol-verify
Agents: sva-extractor, protocol-checker, eda-runner
```
- Skip if module has no AXI/AHB/APB interface (mark as n/a)
- Write protocol-specific SVA assertions
- Bind and run with simulation
- Report violations with cycle numbers

**V8: Synthesizability + PPA Estimation** (module-level: ASIC 28nm estimation)
```
Skill: /rtl-agent-team:rtl-synth-check
Agents: constraint-writer, eda-runner, synthesis-reporter
```
- **SDC-first flow**: constraint-writer generates SDC BEFORE synthesis estimation
- **sv2v conversion**: `sv2v rtl/{module}/*.sv -o rtl/{module}/{module}_v2v.v`
- Run Yosys synthesis estimation with **NanGate45 liberty** (TSMC 28nm proxy)
- Area reported in **NAND2-FO2 gate equivalents** (area_um2 / 0.798)
- Flag inferred latches (hard fail) and non-synthesizable constructs
- Save: docs/phase-5-verify/synthesis-estimate.md (per-module section)

### Group B (depends on V1 pass): V5

**V5: Functional Regression (Tier 3, scenario-split)**
```
Skill: /rtl-agent-team:rtl-p5s-func-verify
Agents: testbench-dev, eda-runner, func-verifier, waveform-analyzer
```
- Prerequisite: V1 (lint) PASS
- Complete cocotb TB skeletons from Stream B
- **Scenario splitting** — each category runs as independent parallel agent:
  ```
  Module A:
    Task(eda-runner, scenario="basic",       seeds=[1,42,123,1337,65536], run_in_background=true)
    Task(eda-runner, scenario="corner_case", seeds=[1,42,123,1337,65536], run_in_background=true)
    Task(eda-runner, scenario="stress",      seeds=[1,42,123,1337,65536], run_in_background=true)
    Task(eda-runner, scenario="error",       seeds=[1,42,123,1337,65536], run_in_background=true)
  → 4 scenarios × 5 seeds = 20 parallel sim tasks per module
  ```
- RTL vs C reference model comparison per vector
- Early termination: >5% failure rate → halt and report
- Generate Requirement Traceability Matrix

### Group C (depends on V5): V6 + V7

**V6: Coverage Analysis (incremental)**
```
Skill: /rtl-agent-team:rtl-p5s-coverage-analyze
Agents: coverage-analyst, testbench-dev
```
- Starts as V5 scenario data becomes available (don't wait for all scenarios)
- Merge multi-seed coverage data
- Check targets: line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%
- Iterative coverpoint refinement (minimum 3 rounds)
- Generate additional tests for HIGH priority gaps
- Re-run regression for new tests

**V7: Performance Verification**
```
Skill: /rtl-agent-team:rtl-p5s-perf-verify
Agents: perf-verifier, eda-runner, waveform-analyzer
```
- Prerequisite: V5 (functional) PASS (functional correctness required)
- Measure throughput, latency, stall rate
- Compare against BFM baseline (bfm/perf_baseline.json)
- Flag deviations >10%

### Group D (after V1-V8 results available): V9

**V9: Code Review + Refactoring**
```
Agents: rtl-critic, rtl-p4s-refactor (via skill invocation)
```
- Review RTL quality after verification iterations
  (verification debug may have introduced code quality regressions)
- rtl-critic performs intensive code review per module
- rtl-p4s-refactor applies fixes for any findings:
  - Naming convention violations
  - Structural improvements
  - Dead code from debug iterations
- After refactoring: re-run V1 (lint) to confirm lint-clean
- **No behavioral change** — equivalence must be maintained

### Module Graduation Gate

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

---

## Stage 2: Top-Level Verification (After ALL Modules Graduate)

All modules must graduate before Stage 2 begins. Stage 2 applies the same verification
categories at the system (top) level with cross-module scope.

### Stage 2 Parallel Groups

**Group 2A (fully parallel):**

**T1: Top-Level Lint**
- Run lint on full design via `rtl/filelist_top.f`
- Verify inter-module signal consistency

**T2: System-Level SVA + Formal**
- Cross-module properties (e.g., end-to-end data integrity)
- Interface compliance between modules
- **sv2v conversion required**: `sv2v rtl/*/*.sv -o rtl/top/design_v2v.v` before SymbiYosys
- Run SymbiYosys on top-level properties (.sby references `_v2v.v`, not `.sv`)

**T3: System-Level CDC**
- Full design CDC analysis (all clock domain crossings)
- Cross-module synchronizer verification
- Update SDC constraints for full design

**T4: System-Level Protocol**
- Protocol compliance at top-level interfaces
- Inter-module handshake verification

**T8: Top-Level Synthesis / PPA Estimation** (ASIC 28nm, SDC-first)
- **SDC-first**: constraint-writer generates/updates syn/constraints/design.sdc for top-level
- **sv2v conversion**: `sv2v rtl/*/*.sv -o rtl/top/design_v2v.v`
- **Default (always)**: Run Yosys synthesis estimation with NanGate45 liberty (TSMC 28nm proxy)
  ```bash
  sv2v rtl/*/*.sv -o rtl/top/design_v2v.v
  yosys -p "read_verilog rtl/top/design_v2v.v; synth -top {top}; \
    dfflibmap -liberty NangateOpenCellLibrary_typical.lib; \
    abc -liberty NangateOpenCellLibrary_typical.lib; \
    stat -liberty NangateOpenCellLibrary_typical.lib" | tee syn/reports/{top}_synth.txt
  ```
- Area metric: NAND2-FO2 gate equivalents (area_um2 / 0.798)
- **If user explicitly requested full synthesis**: additionally export netlist + JSON report
- Generate: docs/phase-5-verify/synthesis-estimate.md (top-level section)

**Group 2B (depends on T1 pass):**

**T5: Integration Test (Tier 4)**
```
Skill: /rtl-agent-team:rtl-p5s-integration-test
Agents: integration-verifier, testbench-dev, eda-runner, func-verifier, waveform-analyzer
```
- Connectivity verification (static): reset, clock, port width
- End-to-end data flow tests
- Handshake/backpressure propagation across modules
- End-to-end reference comparison (full system)

**Group 2C (depends on T5):**

**T6: System-Level Coverage**
- Merge module-level coverage + integration coverage
- Cross-module coverage analysis
- Final coverage targets verification

**T7: System-Level Performance**
- End-to-end throughput/latency measurement
- Full pipeline performance vs architecture spec

**Group 2D (after T1-T8):**

**T9: Top-Level Code Review**
- Top-level module code review
- Inter-module interface consistency review

### Top-Level Gate

All top-level checks PASS → proceed to Stage 3.
Any FAIL → classify and fix:
- UNIT_FIX: single module issue → rtl-p4s-bugfix → re-verify module → re-graduate → re-verify top
- INTEGRATION_FIX: cross-module issue → fix → re-verify affected checks
- DESIGN_FIX: architecture issue → STOP, escalate to user

---

## Stage 3: Final Compliance + Summary

3.1. **Requirement Traceability Matrix**
   - Map every REQ-NNN to test(s) that verify it
   - Save: `reviews/phase-5-verify/requirement-traceability.md`

3.2. **E2E Traceability Matrix**
   - Unified: REQ → Arch → μArch → RTL → Test → Result
   - Save: `reviews/phase-5-verify/e2e-traceability.md`

3.3. **Final Compliance Review**
   - rtl-architect reviews ALL Phase 5 results
   - Verifies RTL implements original spec requirements
   - Save: `reviews/phase-5-verify/final-compliance.md` (verdict: PASS/FAIL)

3.4. **Phase 5 Summary Generation**
   - Generate `docs/phase-5-verify/phase-5-summary.md`
   - Compressed context for Phase 6

3.5. **Collect all verification reports** into `docs/phase-5-verify/`:
   - `unit-test-report.md` — module regression results
   - `integration-report.md` — Tier 4 integration results
   - `ref-rtl-model-consistency.md` — RTL vs C golden comparison
   - `lint-report.md` — final lint results
   - `synthesis-estimate.md` — PPA estimates (+ synthesis results if requested)
</Steps>

<Tool_Usage>
```
# ============================================================
# Stage 0: Preparation
# ============================================================
Bash("mkdir -p docs/phase-5-verify reviews/phase-5-verify sim/coverage sim/formal sim/cdc")

# Read Phase 4 artifacts
Read("docs/phase-4-rtl/module-descriptions.md")      # Module list
Read("docs/phase-4-rtl/stream-b-sva-skeletons.md")   # SVA skeletons
Read("docs/phase-4-rtl/stream-b-cdc-preliminary.md")  # CDC preliminary
Read("docs/phase-4-rtl/stream-b-tb-skeletons.md")     # TB skeletons

# ============================================================
# Stage 1: Module-Level Verification (ALL modules in parallel)
# ============================================================
# --- Per Module: Group A (all parallel) ---

# V1: Lint (per module, parallel)
Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Final comprehensive lint on rtl/{module_a}/*.sv: verilator --lint-only -Wall AND slang --lint-only. Verify naming conventions (i_/o_ prefix, {domain}_clk, {domain}_rst_n). Report PASS/FAIL.",
     run_in_background=true)
Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Final comprehensive lint on rtl/{module_b}/*.sv: [same]. Report PASS/FAIL.",
     run_in_background=true)

# V2: SVA + Formal (per module, parallel)
Task(subagent_type="rtl-agent-team:sva-extractor",
     prompt="Complete SVA skeletons from docs/phase-4-rtl/stream-b-sva-skeletons.md for module {module_a}. Iterative refinement: Round 1 (Draft) → Round 2 (Strengthen) → Round 3 (Harden). Write sim/formal/{module_a}_props.sv. Then convert RTL for SymbiYosys: sv2v rtl/{module_a}/*.sv -o rtl/{module_a}/{module_a}_v2v.v. Generate .sby config referencing _v2v.v (not .sv) and run: sby -f sim/formal/{module_a}.sby. Report proved/failed/timeout per property.",
     run_in_background=true)

# V3: CDC (per module, parallel)
Task(subagent_type="rtl-agent-team:cdc-checker",
     prompt="Full CDC analysis for rtl/{module_a}/*.sv extending docs/phase-4-rtl/stream-b-cdc-preliminary.md. Identify all cross-domain paths, flag missing synchronizers. Write sim/cdc/{module_a}_cdc_report.md.",
     run_in_background=true)

# V4: Protocol (per module, parallel — skip if no bus interface)
Task(subagent_type="rtl-agent-team:protocol-checker",
     prompt="Verify AXI4 protocol compliance for rtl/{module_a}/{module_a}.sv. Write SVA assertions using i_/o_ signal names. Bind and run simulation. Save reviews/phase-5-verify/{module_a}_protocol.md.",
     run_in_background=true)

# V8: Synthesizability + PPA Estimation (per module, parallel — ASIC 28nm estimation)
# SDC must be generated before this step (constraint-writer in Group A pre-step)
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Convert RTL then run ASIC synthesis estimation with NanGate45 (TSMC 28nm proxy) for {module_a}: sv2v rtl/{module_a}/*.sv -o rtl/{module_a}/{module_a}_v2v.v && yosys -p 'read_verilog rtl/{module_a}/{module_a}_v2v.v; synth -top {module_a}; dfflibmap -liberty NangateOpenCellLibrary_typical.lib; abc -liberty NangateOpenCellLibrary_typical.lib; stat -liberty NangateOpenCellLibrary_typical.lib' | tee syn/reports/{module_a}_synth.txt. Extract area (um2), compute NAND2-FO2 gate count (area / 0.798). Flag inferred latches. Save to docs/phase-5-verify/{module_a}_ppa_estimate.md.",
     run_in_background=true)

# --- Per Module: Group B (after V1 pass) ---

# V5: Functional Regression — Scenario Split (per module, per scenario, parallel)
# Wait for V1 (lint) PASS, then launch all scenarios in parallel:
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Complete cocotb TB for {module_a} from Stream B skeleton. Split into scenario categories: basic, corner_case, stress, error_handling. Write sim/{module_a}/test_{module_a}_{scenario}.py per category. Signal naming: dut.sys_clk, dut.i_*/dut.o_*.")

# Launch all scenarios in parallel with multi-seed:
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb scenario 'basic' for {module_a}: make -C sim/{module_a} SIM=verilator TOPLEVEL={module_a} MODULE=test_{module_a}_basic RANDOM_SEED=42. Then run seeds [1, 123, 1337, 65536].",
     run_in_background=true)
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb scenario 'corner_case' for {module_a}: [same pattern, all 5 seeds].",
     run_in_background=true)
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb scenario 'stress' for {module_a}: [same pattern, all 5 seeds].",
     run_in_background=true)
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb scenario 'error_handling' for {module_a}: [same pattern, all 5 seeds].",
     run_in_background=true)

# --- Per Module: Group C (after V5) ---

# V6: Coverage Analysis (incremental — starts as V5 data arrives)
Task(subagent_type="rtl-agent-team:coverage-analyst",
     prompt="Analyze coverage for {module_a} from completed scenario sims. Merge multi-seed data. Check targets: line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%. Iterative refinement (3 rounds). Write sim/coverage/{module_a}_coverage_gaps.md.",
     run_in_background=true)

# V7: Performance (after V5 PASS)
Task(subagent_type="rtl-agent-team:perf-verifier",
     prompt="Measure throughput/latency/stall for {module_a}. Compare vs BFM baseline. Flag >10% deviation. Write sim/{module_a}/{module_a}_perf.json.",
     run_in_background=true)

# --- Per Module: Group D (after V1-V8) ---

# V9: Code Review + Refactoring
Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="Intensive code review of rtl/{module_a}/*.sv. Check for quality regressions from verification debug. Report findings by severity (CRITICAL/HIGH/MEDIUM/LOW). READ-ONLY.")

# If findings exist:
Skill("rtl-agent-team:rtl-p4s-refactor",
      args="rtl/{module_a}/*.sv — apply fixes from code review findings. No behavioral change.")

# ============================================================
# Stage 1 Feedback Loop (on FAIL)
# ============================================================
# Module {module_a} V2 (formal) FAIL: SVA counterexample
Skill("rtl-agent-team:rtl-p4s-bugfix",
      args="Fix SVA counterexample in {module_a}. feedback_origin=5-formal")
# After fix: re-verify V2 only (not all 9 checks)

# ============================================================
# Stage 2: Top-Level Verification (after ALL modules graduate)
# ============================================================

# T5: Integration Test (Tier 4)
Skill("rtl-agent-team:rtl-p5s-integration-test")

# T3: System-level CDC
Task(subagent_type="rtl-agent-team:cdc-checker",
     prompt="Full system-level CDC analysis. Read rtl/filelist_top.f. Identify ALL cross-module clock domain crossings. Generate system-level SDC constraints. Write sim/cdc/system_cdc_report.md.",
     run_in_background=true)

# T2: System-level SVA + Formal
Task(subagent_type="rtl-agent-team:sva-extractor",
     prompt="Write system-level SVA properties for top module. Focus on cross-module data integrity, end-to-end protocol compliance, and system-level safety properties. Convert RTL before SymbiYosys: sv2v rtl/*/*.sv -o rtl/top/design_v2v.v. Ensure .sby references _v2v.v (not .sv). Run SymbiYosys.",
     run_in_background=true)

# T8: Top-level Synthesis / PPA Estimation (ASIC 28nm, SDC-first)
# Step 1: Generate/update SDC for top-level
Task(subagent_type="rtl-agent-team:constraint-writer",
     prompt="Generate/update SDC for top-level design. Read requirements.json, docs/phase-3-uarch/*.md, RTL top port list. Write syn/constraints/design.sdc. Validate with tclsh.")

# Step 2: ASIC synthesis estimation with NanGate45 (default — always runs)
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Convert RTL then run ASIC synthesis estimation with NanGate45 (TSMC 28nm proxy) on top-level: sv2v rtl/*/*.sv -o rtl/top/design_v2v.v && yosys -p 'read_verilog rtl/top/design_v2v.v; synth -top {top}; dfflibmap -liberty NangateOpenCellLibrary_typical.lib; abc -liberty NangateOpenCellLibrary_typical.lib; stat -liberty NangateOpenCellLibrary_typical.lib' | tee syn/reports/{top}_synth.txt. Compute NAND2-FO2 gate count (area / 0.798). Report area, gate count, timing.")

# Step 3: Parse results
Task(subagent_type="rtl-agent-team:synthesis-reporter",
     prompt="Parse syn/reports/{top}_synth.txt. Extract area (um2), compute NAND2-FO2 gate count (area / 0.798). Technology: ASIC TSMC 28nm (NanGate45 proxy). Write syn/summary.json.")

# T6: System-level Coverage
Task(subagent_type="rtl-agent-team:coverage-analyst",
     prompt="Merge all module-level coverage + integration test coverage. Analyze system-level coverage targets. Generate final coverage report. Write reviews/phase-5-verify/coverage-report.md.")

# T7: System-level Performance
Task(subagent_type="rtl-agent-team:perf-verifier",
     prompt="End-to-end performance measurement on top-level design. Full pipeline throughput/latency vs architecture spec targets.")

# T9: Top-level Code Review
Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="Review top-level module and inter-module interfaces. Check: port naming consistency across modules, proper u_ instance prefixes, consistent clock/reset distribution. READ-ONLY.")

# ============================================================
# Stage 3: Final Compliance
# ============================================================

# 3.1 Requirement Traceability
Task(subagent_type="rtl-agent-team:requirement-tracer",
     prompt="Read requirements.json and ALL test results. Map each REQ-NNN to test(s) that verify it. Save reviews/phase-5-verify/requirement-traceability.md.")

# 3.2 E2E Traceability
Task(subagent_type="rtl-agent-team:requirement-tracer",
     prompt="Build unified end-to-end traceability: REQ → Arch → μArch → RTL → Test → Result. Save reviews/phase-5-verify/e2e-traceability.md.")

# 3.3 Final Compliance Review
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="READ-ONLY final spec compliance review. Read requirements.json, io_definition.json, architecture.md, rtl/*/*.sv, and ALL Phase 5 review results. Verify RTL implements ALL spec requirements. Write reviews/phase-5-verify/final-compliance.md with verdict PASS/FAIL.")

# 3.4 Phase 5 Summary
Task(subagent_type="rtl-agent-team:rtl-architect",
     model="sonnet",
     prompt="Generate compressed Phase 5 summary. Read all Phase 5 artifacts. Write docs/phase-5-verify/phase-5-summary.md (max 200 lines). Include: verification results per module, coverage metrics, performance vs spec, synthesis estimates, outstanding issues.")
```
</Tool_Usage>

<Examples>
<Good>
6-module design, Phase 5 orchestrated:
  Stage 0: 6 modules enumerated, Stream B artifacts loaded.
  Stage 1: 6 modules × 9 checks = 54 verification tasks launched.
    Group A (parallel): lint + SVA + CDC + protocol + synth est. (30 tasks, ~5 min)
    Group B: functional regression with scenario split
      6 modules × 4 scenarios × 5 seeds = 120 sim tasks (parallel, ~15 min)
    Group C: coverage analysis (incremental) + performance (6 tasks)
    Group D: code review (6 tasks) → 2 modules need minor refactoring → re-lint PASS
    Module graduation: 5/6 modules graduate immediately.
      1 module fails V2 (SVA counterexample) → rtl-p4s-bugfix → re-verify V2 → PASS → graduates.
  Stage 2: Top-level verification
    Integration test (Tier 4): end-to-end PASS
    System CDC: 1 CAUTION (justified), 0 VIOLATION
    Top-level synthesis estimation: ~85K NAND2-FO2 gates, fmax ~200 MHz (NanGate45/28nm proxy)
    System coverage: line 94%, toggle 85%, FSM 78%
  Stage 3: Final compliance
    REQ traceability: 100% requirements covered, all PASS
    Final verdict: PASS
    Phase 5 summary generated.
  Total wall time: ~25 min (vs ~2 hours sequential)
</Good>
<Good>
Parallel UNIT_FIX during Stage 1:
  Module A: V3 (CDC) FAIL — missing synchronizer on data_valid crossing
  Module B: V5 (functional) FAIL — corner case assertion on FIFO full condition
  Different modules → parallel rtl-p4s-bugfix:
    → Module A fix (cdc-checker guided) — background
    → Module B fix (waveform-analyzer guided) — background, parallel
    → Both re-verified (only failed checks) → PASS
    → Both graduate → proceed to Stage 2
</Good>
<Bad>
Running top-level integration (Stage 2) before all modules graduate — integration failures
mask per-module bugs, waste expensive simulation time debugging cross-module effects that
are actually caused by single-module issues.
</Bad>
<Bad>
Running all 9 checks sequentially per module, then moving to next module — wastes massive
parallelism opportunity. Should run all modules simultaneously with all independent checks
launched in parallel.
</Bad>
<Bad>
Running generic Yosys synthesis (no liberty file) — gate count and area estimates are meaningless
without technology mapping. Always use NanGate45 liberty (ASIC 28nm proxy) with SDC constraints.
Skipping SDC creation before synthesis — timing-unaware optimization produces unreliable PPA.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- **Module feedback loop exhausted** (2 cycles for same check) → escalate to user with findings
- **DESIGN_FIX detected** (architecture-level issue) → IMMEDIATE STOP, escalate to user
- **Coverage persistently below target after 3 rounds** → escalate to rtl-architect
- **Performance deficit >20%** → escalate to rtl-architect for pipeline review
- **Synthesis estimation shows infeasible design** → escalate to user with PPA report
- **Multiple modules fail same check type** → indicates systematic issue, escalate to rtl-architect
- **Stage 2 integration FAIL with >3 bugs** → escalate to rtl-architect for interface review
- **Tool not installed** → eda-runner provides installation instructions, halt affected check
</Escalation_And_Stop_Conditions>

<Final_Checklist>
## Stage 1 (Per Module)
- [ ] V1: lint PASS (verilator --lint-only -Wall + slang --lint-only)
- [ ] V2: SVA formal — all properties proved or justified (3+ refinement rounds)
- [ ] V3: CDC — zero VIOLATION, CAUTIONs justified
- [ ] V4: protocol PASS or n/a (no bus interface)
- [ ] V5: functional — all scenarios × all seeds PASS
- [ ] V6: coverage targets met (line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%)
- [ ] V7: performance — all metrics within 10% of BFM baseline
- [ ] V8: synthesizable — no latches, NAND2-FO2 gate count estimated (NanGate45/28nm)
- [ ] V9: code review — no critical findings, refactoring applied if needed
- [ ] All modules graduated

## Stage 2 (Top-Level)
- [ ] T1: top-level lint PASS
- [ ] T2: system SVA formal PASS
- [ ] T3: system CDC PASS (zero VIOLATION)
- [ ] T4: system protocol PASS
- [ ] T5: integration test (Tier 4) PASS
- [ ] T6: system coverage targets met
- [ ] T7: system performance within spec
- [ ] T8: ASIC 28nm synthesis estimation saved (NanGate45, NAND2-FO2 gate count, SDC applied)
- [ ] T9: top-level code review — no critical findings

## Stage 3 (Final)
- [ ] reviews/phase-5-verify/requirement-traceability.md saved
- [ ] reviews/phase-5-verify/e2e-traceability.md saved
- [ ] reviews/phase-5-verify/final-compliance.md saved with verdict PASS
- [ ] docs/phase-5-verify/phase-5-summary.md generated
- [ ] docs/phase-5-verify/ reports collected (unit-test, integration, lint, synthesis-estimate)
- [ ] All feedback loops resolved (max 2 per module per check)
</Final_Checklist>

<Advanced>
## Parallelism Budget

Theoretical maximum concurrent agents for M modules, S scenarios:
```
Stage 1 Group A: M × 5 checks (lint, SVA, CDC, protocol, synth est.)
Stage 1 Group B: M × S scenarios × 5 seeds
Stage 1 Group C: M × 2 checks (coverage, performance)
Stage 1 Group D: M × 1 (code review)

Example: 6 modules, 4 scenarios
  Group A: 6 × 5 = 30 agents
  Group B: 6 × 4 × 5 = 120 agents
  Group C: 6 × 2 = 12 agents
  Group D: 6 × 1 = 6 agents
  Peak: ~150 concurrent agents (practical limit: ~20-30 via run_in_background)
```

In practice, use `run_in_background: true` for all long-running tasks and limit
concurrent background agents to ~20 for resource management.

## Module Graduation Fast Path

Modules that pass all Group A checks can start Group B immediately without waiting
for other modules' Group A. This is the "overlap rule" — each module progresses
independently through the verification pipeline.

## Scenario Splitting Guidelines

Scenario categories for functional regression (V5):
| Category | Description | Typical Vector Count |
|----------|-------------|---------------------|
| basic | Normal operation, happy path | 50-100 |
| corner_case | Boundary conditions, edge cases | 100-200 |
| stress | Maximum throughput, back-to-back, full FIFO | 200-500 |
| error_handling | Invalid inputs, error injection, recovery | 50-100 |

For very large modules, further split by feature within each category.

## Synthesis Estimation Policy (ASIC TSMC 28nm)

```
Both Module-level (V8) and Top-level (T8):
  1. constraint-writer generates SDC (MANDATORY — before synthesis)
  2. sv2v conversion: .sv → _v2v.v
  3. Yosys synthesis with NanGate45 liberty (TSMC 28nm proxy)
  4. Area reported in NAND2-FO2 gate equivalents (area_um2 / 0.798)

Module-level (Stage 1 V8):
  → Always: synthesis estimation with NanGate45 + NAND2 gate count
  → SDC: per-module clock/IO constraints

Top-level (Stage 2 T8):
  → Always: full synthesis estimation with NanGate45 + SDC
  → User requested full synthesis? → additionally export netlist + JSON report
  → Area metric: always NAND2-FO2 gate equivalents (NOT LUTs, NOT raw cell count)
```

## UVM Verification (Optional)

If a commercial simulator is available and the project mandates UVM methodology,
invoke `/rtl-agent-team:rtl-p5s-uvm-verify` as an additional check alongside V5.
UVM verification is NOT a replacement for cocotb functional regression — both
provide complementary coverage.

## Integration with rtl-autopilot

When rtl-p5-verify is invoked from rtl-autopilot, the state is tracked in
`.rtl-agent-team/state/rtl-autopilot-state.json` with:
```json
{
  "current_phase": 5,
  "completed_sub_phases": ["stage-1-module-a", "stage-1-module-b", ...],
  "pending_sub_phases": ["stage-2-integration", "stage-3-compliance"],
  "fix_history": [
    {"sub_phase": "stage-1-v2", "module": "module_a", "fix_count": 1, "status": "resolved"}
  ]
}
```

This enables resume: if the session is interrupted, re-read the state file and
continue from the next pending sub-phase.

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
</Advanced>
