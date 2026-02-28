---
name: rtl-code
description: "This skill should be used when implementing SystemVerilog RTL modules from uarch specs in Phase 4. Produces lint-clean rtl/*/*.sv with write-lint-fix cycles."
---

<Purpose>
Generate synthesizable SystemVerilog RTL for every block defined in docs/phase-3-uarch/*.md.
Each module goes through a write → lint → fix cycle before the phase gate passes.
Output: rtl/*/*.sv, all lint-clean under Verible and slang.
</Purpose>

<Use_When>
- Phase 3 artifacts (docs/phase-3-uarch/*.md, bfm/) are complete
- RTL implementation is needed for a new or revised module
- Lint errors need systematic resolution across the module set
</Use_When>

<Do_Not_Use_When>
- docs/phase-3-uarch/*.md does not exist for the target module (run rtl-uarch-design first)
- Only structural refactoring needed (use rtl-refactor instead)
- Only lint check needed (use rtl-lint-check instead)
</Do_Not_Use_When>

<Why_This_Exists>
RTL coding requires both codec domain knowledge and SystemVerilog expertise.
The write→lint→fix cycle prevents lint debt from accumulating.
Parallelizing per-module coding maximizes throughput.
</Why_This_Exists>

<Execution_Policy>
- **Wave-based execution pattern** for maximum parallelism:
  - Wave 1 (Write All): One rtl-coder Task per module, all launched in parallel
  - Wave 2 (Lint All): After all modules written, lint-checker runs on ALL files simultaneously
  - Wave 3 (Fix Failed Only): rtl-coder fixes ONLY modules that failed lint (parallel), then re-lint ONLY fixed modules (max 3 fix rounds)
  - Wave 4 (Unit TB + Sim): All lint-clean modules proceed to TB generation simultaneously
- Key principle: "Lint all at once, fix only failures, re-lint only fixes"
- Modules that pass lint early in Wave 3 can start Wave 4 while others are still fixing
- Gate: all modules lint-clean AND unit test PASS AND basic integration PASS AND Stream B artifacts ready (SVA skeletons, CDC topology, TB skeletons) before Phase 5 begins
</Execution_Policy>

<Steps>
1. Read docs/phase-3-uarch/*.md to enumerate all modules
2. Read io_definition.json and CLAUDE.md to confirm naming conventions
3. `mkdir -p reviews/phase-4-rtl`
4. **Wave 1 — Write All (parallel)**: Launch N rtl-coder tasks simultaneously, one per module
   - **Mandatory coding conventions per module:**
     - Port prefix: inputs `i_`, outputs `o_`, bidirectional `io_` (NOT suffix `_i`/`_o`)
     - Clock: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
     - Reset: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
     - Use `logic` only — `reg` and `wire` keywords forbidden
     - `always_ff` for sequential, `always_comb` for combinational
     - `typedef enum logic [N:0]` for FSM states, `typedef struct packed` for grouped signals
     - Instance prefix: `u_`, generate prefix: `gen_`
     - Parameters: `UPPER_SNAKE_CASE`, types: `snake_case_t`
     - ANSI port style, one module per file
   - Each rtl-coder produces rtl/{module}/{module}.sv

5. **Wave 2 — Lint All (parallel)**: After ALL modules from Wave 1 are written, launch N lint-checker tasks simultaneously
   - Each lint-checker runs: `verilator --lint-only -Wall rtl/{module}/{module}.sv`
   - Collect results: classify each module as PASS or FAIL
   - Do NOT fix yet — collect ALL lint results first for pattern analysis

5.5. **Wave 3 — Fix Failed Only (parallel)**: Launch rtl-coder tasks ONLY for FAIL modules
   - Re-lint ONLY fixed modules (not all modules)
   - If common lint pattern detected across multiple modules, broadcast the fix pattern to all affected rtl-coders
   - Max 3 fix rounds per module (same as current)
   - Modules that passed in Wave 2 are untouched — they proceed to Wave 4 immediately

6. **Wave 4 — Unit TB + Sim (parallel, overlapping with Wave 3)**:
   - Lint-clean modules can start TB generation while other modules are still in Wave 3 fix rounds
   - testbench-dev generates `sim/{module}/tb_{module}.sv` for each lint-clean module
   - Smoke test level: reset sequence, basic I/O, FSM state coverage
   - Signal naming: follows `sys_clk`, `sys_rst_n`, `i_*/o_*` conventions
   - If TB already exists, update it (add new test cases)
7. **Per-Module Unit Simulation (parallel)**
   - eda-runner runs each unit test via run_sim.sh:
     ```bash
     scripts/run_sim.sh --sim iverilog --top tb_{module} --outdir sim/{module} --trace \
       rtl/{module}/{module}.sv sim/{module}/tb_{module}.sv
     ```
   - On failure: waveform-analyzer debug → rtl-coder fix → re-run (max 3 rounds)
   - Save results: `sim/{module}/{module}_results.txt`
8. **Basic Integration Check**
   - Run smoke test on the top-level module
   - Basic verification of inter-module connections (reset propagation, clock connectivity)
   - testbench-dev generates `sim/top/tb_{top_module}_smoke.sv`
   - eda-runner executes: compile all modules + top-level sim
9. **Hierarchical Spec Compliance Check — functional coverage review:**
   - rtl-critic reads requirements.json, docs/phase-3-uarch/*.md, and all rtl/*/*.sv files
   - Verify every functional requirement (REQ-NNN) from requirements.json is implemented in RTL
   - Verify every docs/phase-3-uarch/*.md behavioral specification is reflected in the corresponding module
   - Output a Functional Completeness Report:
     ```
     REQ-001: implemented in cabac_encoder.sv (OK)
     REQ-003: implemented in input_buffer.sv (OK)
     REQ-007: NOT FOUND in any RTL module — missing implementation
     docs/phase-3-uarch/transform.md FSM state FLUSH: NOT FOUND in transform.sv — missing state
     ```
   - **Save Functional Completeness Report to `reviews/phase-4-rtl/functional-completeness.md`** in standard review Markdown format
   - **Save full design review to `reviews/phase-4-rtl/design-review.md`** in standard review Markdown format
   - **Save lint report to `reviews/phase-4-rtl/lint-report.md`** in standard review Markdown format
   - Verdict: `VERDICT: PASS` or `VERDICT: FAIL — [N] functional gaps found`
   - On FAIL: rtl-coder receives the gap list and implements missing functionality
   - Re-run lint after any functional additions
10. Collect lint status per module; gate passes when all are lint-clean AND functional coverage is PASS AND unit tests PASS AND basic integration PASS AND Stream B artifacts ready (docs/phase-4-rtl/stream-b-sva-skeletons.md, stream-b-cdc-preliminary.md, stream-b-tb-skeletons.md)
</Steps>

<Tool_Usage>
```
# ============================================================
# Wave 1: Write All Modules (parallel)
# ============================================================
# Launch one rtl-coder task per module — ALL modules simultaneously
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Implement rtl/cabac_encoder/cabac_encoder.sv from docs/phase-3-uarch/cabac_encoder.md. Conventions: i_/o_/io_ port prefix (NOT _i/_o suffix), sys_clk/sys_rst_n (NOT clk_i/rst_ni), logic only (no reg/wire), always_ff/always_comb, u_ instance prefix, gen_ generate prefix, UPPER_SNAKE_CASE params.")
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Implement rtl/transform/transform.sv from docs/phase-3-uarch/transform.md. [same conventions]")
# ... one Task per module, all launched in parallel

# ============================================================
# Wave 2: Lint All (parallel, after ALL Wave 1 tasks complete)
# ============================================================
# Launch lint on ALL modules simultaneously — do NOT fix yet
Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Run lint on rtl/cabac_encoder/cabac_encoder.sv via Bash CLI: 'verilator --lint-only -Wall rtl/cabac_encoder/cabac_encoder.sv' and 'slang --lint-only rtl/cabac_encoder/cabac_encoder.sv'. Report all violations with line numbers. Classify result as PASS or FAIL. Also check naming conventions: i_/o_ prefix, {domain}_clk/{domain}_rst_n.")
Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Run lint on rtl/transform/transform.sv via Bash CLI. [same pattern]")
# ... one lint Task per module, all launched in parallel
# Collect all results: PASS modules → proceed to Wave 4, FAIL modules → Wave 3

# ============================================================
# Wave 3: Fix Failed Only (parallel, only FAIL modules)
# ============================================================
# Launch rtl-coder ONLY for modules that FAILED lint in Wave 2
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Fix lint violations in rtl/cabac_encoder/cabac_encoder.sv per lint report: [paste report]. Maintain all naming conventions (i_/o_ prefix, sys_clk/sys_rst_n). After fix, re-run lint on THIS file only.")
# Re-lint ONLY the fixed modules (not all)
Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Re-lint ONLY rtl/cabac_encoder/cabac_encoder.sv (fixed in Wave 3). Report PASS/FAIL.")
# Max 3 fix rounds per module

# ============================================================
# Wave 4: Unit TB + Sim (parallel, starts as soon as modules pass lint)
# ============================================================
# Lint-clean modules start TB generation immediately (overlap with Wave 3)
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Create SV unit test for rtl/{module}/{module}.sv at sim/{module}/tb_{module}.sv. Include: (1) clock/reset generation (sys_clk, sys_rst_n), (2) basic I/O stimulus, (3) FSM state coverage, (4) self-checking assertions. Use i_*/o_* signal naming.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run unit test via Bash CLI: 'scripts/run_sim.sh --sim iverilog --top tb_{module} --outdir sim/{module} --trace rtl/{module}/{module}.sv sim/{module}/tb_{module}.sv | tee sim/{module}/{module}_results.txt'. Report pass/fail.")

# ============================================================
# Integration Smoke Test (after all modules lint-clean and unit tested)
# ============================================================
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Create top-level integration smoke test at sim/top/tb_{top_module}_smoke.sv. Include: (1) reset propagation check, (2) clock connectivity, (3) basic data flow through all modules.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run integration smoke test via Bash CLI: scripts/run_sim.sh --sim iverilog --top tb_{top_module}_smoke --filelist rtl/filelist_top.f --outdir sim/{module} --trace sim/top/tb_{top_module}_smoke.sv. Execute and report pass/fail.")

# ============================================================
# Functional Coverage Review (after all modules lint-clean + unit tested)
# ============================================================
Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="READ-ONLY review. Read requirements.json, all docs/phase-3-uarch/*.md, and all rtl/*/*.sv. For each REQ-NNN in requirements.json, verify it is implemented in at least one RTL module. For each docs/phase-3-uarch/*.md behavioral spec (FSM states, pipeline stages, data paths), verify the corresponding RTL module implements it. Output a Functional Completeness Report with per-REQ and per-uarch-feature status. Save the Functional Completeness Report to reviews/phase-4-rtl/functional-completeness.md in standard review Markdown format. Save the full design review to reviews/phase-4-rtl/design-review.md. verdict: PASS or FAIL — [N] functional gaps found.")

Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Run lint on all rtl/*/*.sv. Save the lint report to reviews/phase-4-rtl/lint-report.md in standard review Markdown format. verdict: PASS or FAIL + error list[]")

# On FAIL: fix missing functionality
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Implement the following missing functionality in rtl/ per rtl-critic report: [paste gaps]. Then re-run lint.")
```
</Tool_Usage>

<Examples>
<Good>
Wave-based execution: 6 modules coded in Wave 1 (parallel). Wave 2 lint: 4 PASS, 2 FAIL.
Wave 3: 2 FAIL modules fixed in parallel (1 fix round each). Re-lint only those 2 → both PASS.
Meanwhile, Wave 4 started for the 4 early-PASS modules. All 6 modules lint-clean + unit tested in under 10 minutes.
</Good>
<Bad>
Sequential per-module: write module A → lint A → fix A → write module B → lint B → fix B → ...
This serializes the entire coding phase. Wave-based batching is 3-5x faster for N modules.

Another anti-pattern: linting all modules after each single fix round (re-linting PASS modules wastes time).
Only re-lint the modules that were actually fixed in Wave 3.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Module still has lint errors after 3 fix rounds → escalate to rtl-architect for design review
- uarch spec is ambiguous for a module → pause that module, flag to user, continue others
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] rtl/*/*.sv exists for every block in architecture.md
- [ ] All files pass Verible lint with zero errors (via Bash CLI)
- [ ] All files pass slang lint with zero errors (via Bash CLI)
- [ ] No module blocked after 3 fix rounds
- [ ] sim/{module}/tb_{module}.sv exists for every module
- [ ] All unit tests PASS (sim/{module}/{module}_results.txt)
- [ ] Basic integration smoke test PASS (sim/top/tb_{top_module}_smoke.sv)
- [ ] **rtl-critic functional coverage verdict is PASS**
- [ ] **Every REQ-NNN from requirements.json implemented in at least one RTL module**
- [ ] **Every docs/phase-3-uarch/*.md behavioral spec reflected in corresponding RTL module**
- [ ] All port names use `i_`/`o_`/`io_` prefix (NOT suffix `_i`/`_o`)
- [ ] All clocks: `{domain}_clk` (e.g., `sys_clk`) — NOT `clk_i`, `clk_sys` (bare `clk` is allowed for single-domain)
- [ ] All resets: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni` (bare `rst_n` is allowed for single-domain)
- [ ] All instances: `u_` prefix, generates: `gen_` prefix
- [ ] `logic` only — no `reg`/`wire` keywords
- [ ] `always_ff` for sequential, `always_comb` for combinational — no bare `always`
- [ ] **reviews/phase-4-rtl/functional-completeness.md saved with Functional Completeness Report**
- [ ] **reviews/phase-4-rtl/design-review.md saved with full design review**
- [ ] **reviews/phase-4-rtl/lint-report.md saved with lint report**
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
</Advanced>
