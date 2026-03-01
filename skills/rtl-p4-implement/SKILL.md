---
name: rtl-p4-implement
description: "This skill should be used when implementing SystemVerilog RTL modules from uarch specs in Phase 4. Produces lint-clean, code-reviewed, unit-tested, CDC/protocol-checked rtl/*/*.sv through a 10-Wave pipeline."
---

<Purpose>
Generate synthesizable SystemVerilog RTL for every block defined in docs/phase-3-uarch/*.md.
Each module goes through a comprehensive 10-Wave pipeline:
  Write → Lint → Fix → Code Review → Bugfix → Unit Test → CDC → Protocol → Refactor → Integration Gate

**Core principle: lint is necessary but NOT sufficient.**
Phase 4 completion requires functional correctness (unit test), design quality (code review),
clock domain safety (CDC), protocol compliance, and code consistency (refactoring).

Output: rtl/*/*.sv (lint-clean, reviewed, tested) + sim/{module}/ (unit TBs) + reviews/phase-4-rtl/ (verdicts).
</Purpose>

<Use_When>
- Phase 3 artifacts (docs/phase-3-uarch/*.md, bfm/) are complete
- RTL implementation is needed for a new or revised module
- Lint errors need systematic resolution across the module set
- Full Phase 4 pipeline execution (coding through module-level verification)
</Use_When>

<Do_Not_Use_When>
- docs/phase-3-uarch/*.md does not exist for the target module (run rtl-p3-uarch-design first)
- Only structural refactoring needed without new implementation (use rtl-p4s-refactor instead)
- Only lint check needed (use rtl-lint-check instead)
- Only bug fix in existing RTL (use rtl-p4s-bugfix instead)
- Only unit test creation (use rtl-p4s-unit-test instead)
</Do_Not_Use_When>

<Why_This_Exists>
RTL coding requires both domain knowledge and SystemVerilog expertise.
Previous iterations showed that lint-only validation leaves design bugs, CDC hazards,
and protocol violations undetected until Phase 5 — causing expensive feedback loops.

This skill consolidates ALL module-level verification into Phase 4:
- **Code review** catches design-level bugs before simulation
- **Unit testing** proves functional correctness per module
- **CDC checking** identifies clock domain hazards early
- **Protocol checking** verifies handshake compliance
- **Refactoring** ensures code quality and consistency across modules

The 10-Wave pipeline maximizes parallelism: each wave launches N tasks simultaneously
(one per module), and modules that pass early waves can start later waves while others
are still fixing.
</Why_This_Exists>

<Execution_Policy>
- **10-Wave execution pattern** for maximum parallelism:
  - Wave 0 (Prepare): Enumerate modules, create per-module TODO list
  - Wave 1 (Write All): One rtl-coder Task per module, all launched in parallel
  - Wave 2 (Lint All): lint-checker runs on ALL files simultaneously
  - Wave 3 (Fix Lint): rtl-coder fixes ONLY modules that failed lint (max 3 rounds)
  - Wave 4 (Code Review): rtl-critic intensive review per module (parallel)
  - Wave 5 (Bugfix from Review): rtl-p4s-bugfix for modules with findings (parallel, max 3 rounds)
  - Wave 6 (Unit TB + Sim): testbench-dev + eda-runner per module (parallel)
  - Wave 7 (Module CDC): cdc-checker per module (parallel)
  - Wave 8 (Module Protocol): protocol-checker per module (parallel)
  - Wave 9 (Refactoring): rtl-p4s-refactor for modules needing cleanup (parallel)
  - Wave 10 (Integration + Gate): integration smoke test + spec compliance review + Stream B

- Key principles:
  - "Lint all at once, fix only failures, re-lint only fixes"
  - "Code review before testing — catch design bugs early"
  - "Module-level CDC/protocol before Phase 5 — catch hazards early"
  - Modules that pass early can start later waves while others are still in earlier waves

- **Overlap rules**: Waves 6-9 can overlap for different modules:
  - Module A passes code review → starts Wave 6 (unit test)
  - Module B still in Wave 5 (bugfix) → continues fixing
  - Module A passes unit test → starts Wave 7 (CDC) while Module B starts Wave 6

- Gate: ALL modules must pass ALL waves (lint-clean + code-review-clean + unit-test-PASS
  + CDC-clean + protocol-clean + refactored) AND basic integration PASS
  AND Stream B artifacts ready before Phase 5 begins
</Execution_Policy>

<Steps>
1. **Wave 0 — Preparation**
   - Read docs/phase-3-uarch/*.md to enumerate all modules
   - Read io_definition.json and CLAUDE.md to confirm naming conventions
   - Read docs/phase-3-uarch/clock-domain-map.md for clock domain info
   - Read docs/phase-3-uarch/protocol-assignments.md for protocol assignments
   - `mkdir -p reviews/phase-4-rtl`
   - Create per-module TODO list (TaskCreate per module with dependencies):
     ```
     Module {name}: Write → Lint → Review → Fix → TB → CDC → Protocol → Refactor
     ```
   - Identify module dependency order (leaf modules first, then composite modules)

2. **Wave 1 — Write All (parallel)**
   - Launch N rtl-coder tasks simultaneously, one per module
   - **Mandatory coding conventions per module:**
     - Port prefix: inputs `i_`, outputs `o_`, bidirectional `io_` (NOT suffix `_i`/`_o`)
     - Clock: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
     - Reset: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
     - Use `logic` only — `reg` and `wire` keywords forbidden
     - `always_ff` for sequential, `always_comb` for combinational
     - `typedef enum logic [N:0]` for FSM states, `typedef struct packed` for grouped signals
     - Instance prefix: `u_`, generate prefix: `gen_`
     - Parameters: `UPPER_SNAKE_CASE`, internal localparam: `L_` prefix, types: `snake_case_t`
     - ANSI port style, one module per file
   - Each rtl-coder produces rtl/{module}/{module}.sv
   - Also create rtl/filelist_{module}.f per module

3. **Wave 2 — Lint All (parallel)**
   - After ALL modules from Wave 1 are written, launch N lint-checker tasks simultaneously
   - Each lint-checker runs: `verilator --lint-only -Wall rtl/{module}/{module}.sv`
   - Collect results: classify each module as PASS or FAIL
   - Do NOT fix yet — collect ALL lint results first for pattern analysis
   - If common lint pattern across multiple modules, note it for Wave 3 broadcast

4. **Wave 3 — Fix Lint Failures (parallel, max 3 rounds)**
   - Launch rtl-coder tasks ONLY for FAIL modules
   - Re-lint ONLY fixed modules (not all modules)
   - If common lint pattern detected, broadcast the fix pattern to all affected rtl-coders
   - Max 3 fix rounds per module
   - Modules that passed in Wave 2 are untouched — they proceed to Wave 4 immediately

5. **Wave 4 — Code Review (parallel)**
   - Launch rtl-critic per lint-clean module (parallel)
   - **Review focus areas (per module):**
     - uarch compliance: does RTL match docs/phase-3-uarch/{module}.md?
     - Interface compliance: do ports match io_definition.json?
     - FSM completeness: all states from uarch spec present?
     - Pipeline correctness: stage count, latency, throughput match uarch?
     - Coding style: naming conventions, parameterization, comments
     - Logical correctness: potential bugs, off-by-one, sign extension, width mismatches
     - Power: unnecessary toggling, missing clock gating opportunities
   - Output: per-module review report at `.rtl-agent-team/scratch/phase-4/{module}_review.md`
   - Classify each module: REVIEW_PASS (0 critical/major findings) or REVIEW_FAIL

6. **Wave 5 — Bugfix from Review (parallel, max 3 rounds)**
   - For each REVIEW_FAIL module: invoke rtl-p4s-bugfix with review findings
   - rtl-p4s-bugfix follows: analyze → fix → lint → TB → sim cycle
   - After fix: re-submit to rtl-critic for re-review (same review focus)
   - Max 3 review→fix iterations per module
   - REVIEW_PASS modules proceed to Wave 6 immediately
   - **This is the most critical quality gate — thoroughness here prevents Phase 5 failures**

7. **Wave 6 — Unit TB + Sim (parallel, overlapping with Wave 5)**
   - Lint-clean + review-clean modules start TB generation
   - testbench-dev generates `sim/{module}/tb_{module}.sv` for each module
   - Smoke test level: reset sequence, basic I/O, FSM state coverage
   - Signal naming: follows `sys_clk`, `sys_rst_n`, `i_*/o_*` conventions
   - If TB already exists, update it (add new test cases)
   - eda-runner runs each unit test via run_sim.sh:
     ```bash
     scripts/run_sim.sh --sim verilator --top tb_{module} --outdir sim/{module} --trace \
       rtl/{module}/{module}.sv sim/{module}/tb_{module}.sv
     # Fallback: --sim iverilog (for 4-state X/Z simulation or verilator-unsupported SV constructs)
     ```
   - On failure: waveform-analyzer debug → rtl-coder fix → re-lint → re-sim (max 3 rounds)
   - Save results: `sim/{module}/{module}_results.txt`

8. **Wave 7 — Module-level CDC (parallel)**
   - Launch cdc-checker per module with multiple clock domains (parallel)
   - Read clock-domain-map.md to identify which modules have CDC crossings
   - Single-domain modules: skip CDC (mark as CDC_PASS automatically)
   - Multi-domain modules:
     - Identify all clock domain crossings within the module
     - Verify synchronizer presence (2FF, FIFO, handshake)
     - Flag missing synchronizers, incorrect synchronizer types
     - Check reset synchronization across domains
   - Output: per-module CDC report at `.rtl-agent-team/scratch/phase-4/{module}_cdc.md`
   - On FAIL: rtl-coder adds missing synchronizers → re-check (max 2 rounds)
   - Contribute findings to docs/phase-4-rtl/stream-b-cdc-preliminary.md

9. **Wave 8 — Module-level Protocol (parallel)**
   - Launch protocol-checker per module with bus interfaces (parallel)
   - Read protocol-assignments.md to identify which modules have protocol interfaces
   - Modules without bus interfaces: skip (mark as PROTOCOL_PASS automatically)
   - Modules with bus interfaces:
     - Verify handshake protocol compliance (valid/ready, req/ack)
     - Check AXI/APB/AHB interface compliance if applicable
     - Verify no combinational loops in handshake paths
     - Check back-pressure handling
   - Output: per-module protocol report at `.rtl-agent-team/scratch/phase-4/{module}_protocol.md`
   - On FAIL: rtl-coder fixes protocol violations → re-check (max 2 rounds)

10. **Wave 9 — Refactoring (parallel, selective)**
    - Not all modules need refactoring — select based on code review findings
    - Launch rtl-p4s-refactor for modules flagged by rtl-critic for:
      - Naming inconsistency
      - Excessive module size (>500 lines suggests splitting)
      - Code duplication across modules
      - Missing parameterization
    - Refactoring must maintain functional equivalence (lint + re-sim after refactoring)
    - rtl-p4s-refactor verifies equivalence via smoke sim or formal check

11. **Wave 10 — Integration + Gate**
    - **Basic Integration Check:**
      - testbench-dev generates `sim/top/tb_{top_module}_smoke.sv`
      - eda-runner runs top-level smoke test (reset propagation, clock connectivity)
    - **Hierarchical Spec Compliance Check (rtl-critic):**
      - Read requirements.json, docs/phase-3-uarch/*.md, all rtl/*/*.sv
      - Verify every REQ-NNN implemented in at least one RTL module
      - Verify every uarch behavioral spec reflected in corresponding module
      - Save Functional Completeness Report to `reviews/phase-4-rtl/functional-completeness.md`
      - Save design review to `reviews/phase-4-rtl/design-review.md`
      - Save lint report to `reviews/phase-4-rtl/lint-report.md`
      - Verdict: PASS or FAIL — [N] functional gaps found
      - On FAIL: rtl-coder implements missing functionality → re-lint → re-test
    - **Stream B Artifacts (parallel with Wave 10):**
      - sva-extractor generates SVA skeletons: docs/phase-4-rtl/stream-b-sva-skeletons.md
      - cdc-checker consolidates CDC topology: docs/phase-4-rtl/stream-b-cdc-preliminary.md
      - testbench-dev generates TB skeletons: docs/phase-4-rtl/stream-b-tb-skeletons.md
    - **Phase 4 Gate Check:**
      - All modules lint-clean
      - All modules code-review-clean (0 critical/major findings)
      - All unit tests PASS
      - All module CDC checks PASS (or single-domain skip)
      - All protocol checks PASS (or no-interface skip)
      - Refactoring complete for flagged modules
      - Integration smoke test PASS
      - Functional coverage verdict PASS
      - Stream B artifacts ready
      - `phase-4-summary.md` generated
</Steps>

<Tool_Usage>
```
# ============================================================
# Wave 0: Preparation
# ============================================================
# Read uarch specs to enumerate modules
Glob("docs/phase-3-uarch/*.md")
# Read each spec, then create per-module TODO list
# TaskCreate per module with wave dependencies

# ============================================================
# Wave 1: Write All Modules (parallel)
# ============================================================
# Launch one rtl-coder task per module — ALL modules simultaneously
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Implement rtl/cabac_encoder/cabac_encoder.sv from docs/phase-3-uarch/cabac_encoder.md. Read clock-domain-map.md for clock domains. Conventions: i_/o_/io_ port prefix (NOT _i/_o suffix), sys_clk/sys_rst_n (NOT clk_i/rst_ni), logic only (no reg/wire), always_ff/always_comb, u_ instance prefix, gen_ generate prefix, UPPER_SNAKE_CASE params, L_ prefix for localparam. Also create rtl/filelist_cabac_encoder.f.")
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Implement rtl/transform/transform.sv from docs/phase-3-uarch/transform.md. [same conventions]")
# ... one Task per module, all launched in parallel

# ============================================================
# Wave 2: Lint All (parallel, after ALL Wave 1 tasks complete)
# ============================================================
Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Run lint on rtl/cabac_encoder/cabac_encoder.sv via Bash CLI: 'verilator --lint-only -Wall rtl/cabac_encoder/cabac_encoder.sv'. Report all violations with line numbers. Classify result as PASS or FAIL. Also check naming conventions: i_/o_ prefix, {domain}_clk/{domain}_rst_n, no reg/wire.")
# ... one lint Task per module, all launched in parallel

# ============================================================
# Wave 3: Fix Failed Only (parallel, only FAIL modules)
# ============================================================
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Fix lint violations in rtl/cabac_encoder/cabac_encoder.sv per lint report: [paste report]. Maintain all naming conventions. After fix, re-run lint on THIS file only.")
# Max 3 fix rounds per module

# ============================================================
# Wave 4: Code Review (parallel, all lint-clean modules)
# ============================================================
Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="READ-ONLY intensive review of rtl/cabac_encoder/cabac_encoder.sv against docs/phase-3-uarch/cabac_encoder.md. Review focus: (1) uarch compliance — all FSM states, pipeline stages, data paths present? (2) Interface compliance — ports match io_definition.json? (3) Logical correctness — sign extension, width mismatch, off-by-one? (4) Coding style — naming conventions, parameterization? (5) Power — unnecessary toggling? Save review to .rtl-agent-team/scratch/phase-4/cabac_encoder_review.md. Classify: REVIEW_PASS or REVIEW_FAIL with finding list.")
# ... one review Task per module, all launched in parallel

# ============================================================
# Wave 5: Bugfix from Review (parallel, only REVIEW_FAIL modules)
# ============================================================
# Invoke rtl-p4s-bugfix for each module with critical/major findings
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Fix code review findings in rtl/cabac_encoder/cabac_encoder.sv per review report: [paste findings]. Focus on: [critical/major items]. Maintain naming conventions. After fix, re-run lint.")
# After fix → re-review by rtl-critic (max 3 review→fix iterations)
Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="Re-review rtl/cabac_encoder/cabac_encoder.sv after bugfix. Focus on previously reported findings. Classify: REVIEW_PASS or REVIEW_FAIL.")

# ============================================================
# Wave 6: Unit TB + Sim (parallel, lint-clean + review-clean modules)
# ============================================================
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Create SV unit test for rtl/{module}/{module}.sv at sim/{module}/tb_{module}.sv. Include: (1) clock/reset generation (sys_clk, sys_rst_n), (2) basic I/O stimulus, (3) FSM state coverage, (4) self-checking assertions. Use i_*/o_* signal naming. DUT instance: u_dut.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run unit test via Bash CLI: 'scripts/run_sim.sh --sim verilator --top tb_{module} --outdir sim/{module} --trace rtl/{module}/{module}.sv sim/{module}/tb_{module}.sv | tee sim/{module}/{module}_results.txt'. Report pass/fail.")

# ============================================================
# Wave 7: Module-level CDC (parallel, multi-domain modules only)
# ============================================================
Task(subagent_type="rtl-agent-team:cdc-checker",
     prompt="Analyze CDC crossings in rtl/cabac_encoder/cabac_encoder.sv. Read docs/phase-3-uarch/clock-domain-map.md for domain assignments. Identify all clock domain crossings, verify synchronizer presence (2FF/FIFO/handshake), flag missing synchronizers. Save report to .rtl-agent-team/scratch/phase-4/cabac_encoder_cdc.md. Classify: CDC_PASS or CDC_FAIL.")
# Single-domain modules: skip

# ============================================================
# Wave 8: Module-level Protocol (parallel, bus-interface modules only)
# ============================================================
Task(subagent_type="rtl-agent-team:protocol-checker",
     prompt="Verify protocol compliance in rtl/cabac_encoder/cabac_encoder.sv. Read docs/phase-3-uarch/protocol-assignments.md for assigned protocols. Check: (1) valid/ready handshake correctness, (2) no combinational loops in handshake, (3) back-pressure handling, (4) AXI/APB compliance if applicable. Save report to .rtl-agent-team/scratch/phase-4/cabac_encoder_protocol.md. Classify: PROTOCOL_PASS or PROTOCOL_FAIL.")
# Modules without bus interfaces: skip

# ============================================================
# Wave 9: Refactoring (parallel, selective — only flagged modules)
# ============================================================
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Analyze rtl/cabac_encoder/cabac_encoder.sv and produce refactoring plan. Include: (1) naming convention fixes, (2) module size reduction if >500 lines, (3) code duplication elimination, (4) parameterization opportunities. READ-ONLY analysis.")

Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Apply refactoring plan to rtl/cabac_encoder/cabac_encoder.sv: [paste plan]. Do not change behavior. After refactoring, re-run lint and smoke sim to verify equivalence.")

# ============================================================
# Wave 10: Integration + Gate
# ============================================================
# Integration Smoke Test
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Create top-level integration smoke test at sim/top/tb_{top_module}_smoke.sv. Include: (1) reset propagation check, (2) clock connectivity, (3) basic data flow through all modules.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run integration smoke test via Bash CLI: scripts/run_sim.sh --sim verilator --top tb_{top_module}_smoke --filelist rtl/filelist_top.f --outdir sim/top --trace sim/top/tb_{top_module}_smoke.sv. Report pass/fail.")

# Functional Coverage Review
Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="READ-ONLY review. Read requirements.json, all docs/phase-3-uarch/*.md, and all rtl/*/*.sv. For each REQ-NNN, verify implementation. For each uarch behavioral spec, verify RTL reflects it. Save Functional Completeness Report to reviews/phase-4-rtl/functional-completeness.md. Save design review to reviews/phase-4-rtl/design-review.md. Verdict: PASS or FAIL — [N] functional gaps found.")

Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Run lint on all rtl/*/*.sv. Save lint report to reviews/phase-4-rtl/lint-report.md. Verdict: PASS or FAIL + error list[]")

# Stream B Artifacts (parallel with Integration)
Task(subagent_type="rtl-agent-team:sva-extractor",
     prompt="Generate SVA property skeletons from docs/phase-3-uarch/*.md. Output to docs/phase-4-rtl/stream-b-sva-skeletons.md.")

Task(subagent_type="rtl-agent-team:cdc-checker",
     prompt="Consolidate per-module CDC reports into docs/phase-4-rtl/stream-b-cdc-preliminary.md. Include full clock domain topology and crossing summary.")

Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Generate cocotb TB skeletons from docs/phase-3-uarch/*.md. Output to docs/phase-4-rtl/stream-b-tb-skeletons.md.")

# On functional coverage FAIL: fix missing functionality
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Implement the following missing functionality in rtl/ per rtl-critic report: [paste gaps]. Then re-run lint.")
```
</Tool_Usage>

<Examples>
<Good>
10-Wave execution for 6 modules:
  Wave 0: Enumerated 6 modules from uarch specs, created TODO list per module
  Wave 1: 6 rtl-coder tasks launched in parallel — all 6 modules written
  Wave 2: 6 lint-checker tasks — 4 PASS, 2 FAIL
  Wave 3: 2 FAIL modules fixed (1 round each), re-lint → both PASS
  Wave 4: 6 rtl-critic reviews — 5 REVIEW_PASS, 1 REVIEW_FAIL (missing FSM state)
  Wave 5: 1 module fixed via rtl-p4s-bugfix, re-reviewed → REVIEW_PASS
  Wave 6: 6 TB generated + simulated — 5 PASS, 1 FAIL (off-by-one in counter)
    → waveform debug → rtl-coder fix → re-sim → PASS
  Wave 7: 2 multi-domain modules CDC-checked — both CDC_PASS
  Wave 8: 3 modules with AXI interfaces protocol-checked — all PROTOCOL_PASS
  Wave 9: 1 module refactored (800 lines split into 3 sub-modules), equivalence verified
  Wave 10: Integration smoke PASS, functional coverage PASS, Stream B ready
  Total: all 6 modules fully verified at module level before Phase 5
</Good>
<Good>
Overlap execution for faster throughput:
  Modules A,B pass code review early → start Wave 6 (unit test) immediately
  Module C still in Wave 5 (bugfix round 2)
  Module A passes unit test → starts Wave 7 (CDC) while B is still in Wave 6
  All modules eventually converge at Wave 10 gate
  Result: ~30% faster than strict sequential wave execution
</Good>
<Bad>
Sequential per-module: write module A → lint A → fix A → review A → fix A → test A → ...
then write module B → lint B → ...
This serializes the entire coding phase. Wave-based batching is 3-5x faster for N modules.

Another anti-pattern: linting all modules after each single fix round (re-linting PASS modules wastes time).
Only re-lint the modules that were actually fixed in Wave 3.
</Bad>
<Bad>
Skipping Wave 4 (code review): "lint passed, so code is correct"
→ Unit test in Wave 6 finds 5 design bugs that code review would have caught
→ 5 additional fix→lint→re-test cycles wasted. Review catches design bugs earlier than simulation.
</Bad>
<Bad>
Skipping Wave 7 (CDC): "CDC is Phase 5's job"
→ Phase 5 CDC analysis finds 12 missing synchronizers across 4 modules
→ Expensive Phase 5→4 feedback loop. Module-level CDC catches these early.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Module still has lint errors after 3 fix rounds → escalate to rtl-architect for design review
- Module fails code review after 3 review→fix iterations → escalate to rtl-architect for structural redesign
- uarch spec is ambiguous for a module → pause that module, flag to user, continue others
- Unit test fails after 3 debug→fix→re-sim iterations → escalate to waveform-analyzer + rtl-architect
- CDC FAIL after 2 fix rounds → escalate to cdc-reviewer (expert review agent) for synchronization strategy
- Protocol FAIL after 2 fix rounds → escalate to protocol-reviewer (expert review agent) for interface redesign
- Functional coverage review FAIL with >3 missing REQs → pause, flag to user (potential uarch spec gap)
</Escalation_And_Stop_Conditions>

<Final_Checklist>
**--- RTL Files ---**
- [ ] rtl/*/*.sv exists for every block in docs/phase-3-uarch/
- [ ] rtl/filelist_{module}.f exists for every module
- [ ] rtl/filelist_top.f exists and includes all module filelists

**--- Lint ---**
- [ ] All files pass `verilator --lint-only -Wall` with zero errors
- [ ] No module blocked after 3 lint fix rounds

**--- Code Review ---**
- [ ] All modules reviewed by rtl-critic (Wave 4)
- [ ] All modules REVIEW_PASS (0 critical/major findings)
- [ ] Per-module review reports saved at `.rtl-agent-team/scratch/phase-4/`
- [ ] No module blocked after 3 review→fix iterations

**--- Unit Test ---**
- [ ] sim/{module}/tb_{module}.sv exists for every module
- [ ] All unit tests PASS (sim/{module}/{module}_results.txt)

**--- CDC ---**
- [ ] All multi-domain modules CDC-checked (Wave 7)
- [ ] All multi-domain modules CDC_PASS
- [ ] Single-domain modules explicitly marked as skip

**--- Protocol ---**
- [ ] All bus-interface modules protocol-checked (Wave 8)
- [ ] All bus-interface modules PROTOCOL_PASS
- [ ] No-interface modules explicitly marked as skip

**--- Refactoring ---**
- [ ] Flagged modules refactored (Wave 9)
- [ ] Equivalence verified for all refactored modules (lint + smoke sim)

**--- Integration + Gate ---**
- [ ] Basic integration smoke test PASS (sim/top/tb_{top_module}_smoke.sv)
- [ ] rtl-critic functional coverage verdict is PASS
- [ ] Every REQ-NNN from requirements.json implemented in at least one RTL module
- [ ] Every docs/phase-3-uarch/*.md behavioral spec reflected in corresponding RTL module
- [ ] reviews/phase-4-rtl/functional-completeness.md saved
- [ ] reviews/phase-4-rtl/design-review.md saved
- [ ] reviews/phase-4-rtl/lint-report.md saved

**--- Stream B ---**
- [ ] docs/phase-4-rtl/stream-b-sva-skeletons.md saved
- [ ] docs/phase-4-rtl/stream-b-cdc-preliminary.md saved
- [ ] docs/phase-4-rtl/stream-b-tb-skeletons.md saved

**--- Naming Conventions ---**
- [ ] All port names use `i_`/`o_`/`io_` prefix (NOT suffix `_i`/`_o`)
- [ ] All clocks: `clk` or `{domain}_clk` (e.g., `sys_clk`) — NOT `clk_i`, `clk_sys`
- [ ] All resets: `rst_n` or `{domain}_rst_n` (e.g., `sys_rst_n`) — NOT `rst_ni`
- [ ] All instances: `u_` prefix, generates: `gen_` prefix
- [ ] `logic` only — no `reg`/`wire` keywords
- [ ] `always_ff` for sequential, `always_comb` for combinational — no bare `always`
- [ ] Parameters: `UPPER_SNAKE_CASE`, localparam: `L_` prefix, types: `snake_case_t`

**--- Phase 4 Summary ---**
- [ ] docs/phase-4-rtl/phase-4-summary.md generated
</Final_Checklist>

<Advanced>
rtl-coder should use parameters for all configurable constants (widths, depths).

**Clock and reset naming (project-specific override of lowRISC guide):**
- Clock: `clk` (single domain) or `{domain}_clk` (multiple domains) — e.g., `sys_clk`, `pixel_clk`
  - WRONG: `clk_i`, `clk_sys`, `clock`
- Reset: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains) — e.g., `sys_rst_n`, `pixel_rst_n`
  - WRONG: `rst_ni`, `reset_n`, `rstn`
- Clock/reset ports do NOT need `i_` prefix

**Port naming:**
- Inputs: `i_data`, `i_valid`, `i_addr` (NOT `data_i`, `valid_i`)
- Outputs: `o_result`, `o_ready`, `o_ack` (NOT `result_o`, `ready_o`)

**EDA tools run via Bash CLI directly** (not through MCP):
```bash
verilator --lint-only -Wall rtl/{module}/{module}.sv
slang --lint-only rtl/{module}/{module}.sv
```

**Wave overlap strategy:**
Modules progress through waves independently. A per-module state tracker records:
```json
{
  "module": "cabac_encoder",
  "wave_1_write": "DONE",
  "wave_2_lint": "PASS",
  "wave_3_fix": "SKIP",
  "wave_4_review": "PASS",
  "wave_5_bugfix": "SKIP",
  "wave_6_unit_test": "PASS",
  "wave_7_cdc": "PASS",
  "wave_8_protocol": "SKIP",
  "wave_9_refactor": "SKIP",
  "wave_10_gate": "PASS"
}
```

**Code review iteration protocol:**
- Round 1: Full review (all focus areas)
- Round 2: Targeted re-review (only previously failed focus areas)
- Round 3: Final check (must pass or escalate)

**CDC check scope in Phase 4 vs Phase 5:**
- Phase 4 (Wave 7): Module-level CDC — within each module boundary
- Phase 5 (rtl-p5s-cdc-verify): System-level CDC — across module boundaries, top-level analysis
- Phase 4 catches module-internal hazards early; Phase 5 catches inter-module hazards

**Protocol check scope in Phase 4 vs Phase 5:**
- Phase 4 (Wave 8): Module-level protocol — each module's bus interfaces in isolation
- Phase 5 (rtl-p5s-protocol-verify): System-level protocol — end-to-end transaction flow across modules
- Phase 4 catches per-interface violations; Phase 5 catches integration-level protocol issues

**Refactoring decision criteria (Wave 9):**
- Module >500 lines: consider splitting
- 3+ modules share similar code: extract common module
- Naming inconsistency flagged by rtl-critic: rename pass
- Missing parameterization: add parameters for magic numbers
- Refactoring is selective — not all modules need it

**Phase 4 sub-skills integration:**
- `rtl-p4s-bugfix`: Used in Wave 5 for review-driven fixes, and Wave 6 for test-driven fixes
- `rtl-p4s-refactor`: Used in Wave 9 for code quality improvements
- `rtl-p4s-unit-test`: Tier 2 testing (used after Phase 4 for deeper per-module verification)
- `rtl-lint-check`: Used in Waves 2-3 and after any code modification
</Advanced>
