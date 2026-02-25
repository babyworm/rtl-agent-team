---
name: rtl-code
description: Phase 4 skill. Implements all RTL modules in SystemVerilog with lint-clean gate.
---

<Purpose>
Generate synthesizable SystemVerilog RTL for every block defined in uarch/*.md.
Each module goes through a write → lint → fix cycle before the phase gate passes.
Output: rtl/src/*.sv, all lint-clean under Verible and slang.
</Purpose>

<Use_When>
- Phase 3 artifacts (uarch/*.md, bfm/) are complete
- RTL implementation is needed for a new or revised module
- Lint errors need systematic resolution across the module set
</Use_When>

<Do_Not_Use_When>
- uarch/*.md does not exist for the target module (run uarch-design first)
- Only structural refactoring needed (use rtl-refactor instead)
- Only lint check needed (use lint-check instead)
</Do_Not_Use_When>

<Why_This_Exists>
RTL coding requires both codec domain knowledge and SystemVerilog expertise.
The write→lint→fix cycle prevents lint debt from accumulating.
Parallelizing per-module coding maximizes throughput.
</Why_This_Exists>

<Execution_Policy>
- One rtl-coder Task per module, all launched in parallel
- After each module is written, lint-checker runs on that file immediately
- rtl-coder fixes lint errors (max 3 rounds per module)
- Gate: all modules lint-clean before Phase 5 begins
</Execution_Policy>

<Steps>
1. Read uarch/*.md to enumerate all modules
2. Read io_definition.json and CLAUDE.md to confirm naming conventions
3. Launch parallel rtl-coder tasks: one per module
   - **Mandatory coding conventions per module:**
     - Port prefix: inputs `i_`, outputs `o_`, bidirectional `io_` (NOT suffix `_i`/`_o`)
     - Clock: `{domain}_clk` (e.g., `sys_clk`, `pixel_clk`) — NOT `clk_i`, `clk`, `clk_sys`
     - Reset: `{domain}_rst_n` (e.g., `sys_rst_n`) — NOT `rst_ni`, `rst_n`
     - Use `logic` only — `reg` and `wire` keywords forbidden
     - `always_ff` for sequential, `always_comb` for combinational
     - `typedef enum logic [N:0]` for FSM states, `typedef struct packed` for grouped signals
     - Instance prefix: `u_`, generate prefix: `gen_`
     - Parameters: `UPPER_SNAKE_CASE`, types: `snake_case_t`
     - ANSI port style, one module per file
4. Each rtl-coder produces rtl/src/{module}.sv
5. lint-checker runs on each produced file via Bash CLI: `verilator --lint-only -Wall rtl/src/{module}.sv`
6. rtl-coder fixes reported lint violations (up to 3 rounds)
7. **Hierarchical Spec Compliance Check — functional coverage review:**
   - rtl-critic reads requirements.json, uarch/*.md, and all rtl/src/*.sv files
   - Verify every functional requirement (REQ-NNN) from requirements.json is implemented in RTL
   - Verify every uarch/*.md behavioral specification is reflected in the corresponding module
   - Output a Functional Completeness Report:
     ```
     REQ-001: implemented in cabac_encoder.sv (OK)
     REQ-003: implemented in input_buffer.sv (OK)
     REQ-007: NOT FOUND in any RTL module — missing implementation
     uarch/transform.md FSM state FLUSH: NOT FOUND in transform.sv — missing state
     ```
   - Verdict: `VERDICT: PASS` or `VERDICT: FAIL — [N] functional gaps found`
   - On FAIL: rtl-coder receives the gap list and implements missing functionality
   - Re-run lint after any functional additions
8. Collect lint status per module; gate passes when all are lint-clean AND functional coverage is PASS
</Steps>

<Tool_Usage>
```
# Launch one task per module (parallel)
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Implement rtl/src/cabac_encoder.sv from uarch/cabac_encoder.md. Conventions: i_/o_/io_ port prefix (NOT _i/_o suffix), sys_clk/sys_rst_n (NOT clk_i/rst_ni), logic only (no reg/wire), always_ff/always_comb, u_ instance prefix, gen_ generate prefix, UPPER_SNAKE_CASE params. Run lint after writing.")

# Lint via Bash CLI (NOT MCP)
Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Run lint on rtl/src/cabac_encoder.sv via Bash CLI: 'verilator --lint-only -Wall rtl/src/cabac_encoder.sv' and 'slang --lint-only rtl/src/cabac_encoder.sv'. Report all violations with line numbers. Also check naming conventions: i_/o_ prefix, {domain}_clk/{domain}_rst_n.")

# Fix round
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Fix lint violations in rtl/src/cabac_encoder.sv per lint report: [paste report]. Maintain all naming conventions (i_/o_ prefix, sys_clk/sys_rst_n).")

# Functional coverage review (after all modules lint-clean)
Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="READ-ONLY review. Read requirements.json, all uarch/*.md, and all rtl/src/*.sv. For each REQ-NNN in requirements.json, verify it is implemented in at least one RTL module. For each uarch/*.md behavioral spec (FSM states, pipeline stages, data paths), verify the corresponding RTL module implements it. Output a Functional Completeness Report with per-REQ and per-uarch-feature status. Verdict: VERDICT: PASS or VERDICT: FAIL — [N] functional gaps found.")

# On FAIL: fix missing functionality
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Implement the following missing functionality in rtl/src/ per rtl-critic report: [paste gaps]. Then re-run lint.")
```
</Tool_Usage>

<Examples>
<Good>
6 modules coded in parallel; 4 pass lint on first attempt; 2 need one fix round; all clean in under 10 minutes.
</Good>
<Bad>
Writing all modules then running lint at the end — lint errors in module A may indicate systemic issues
that should be caught before coding modules B-F.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Module still has lint errors after 3 fix rounds → escalate to rtl-architect for design review
- uarch spec is ambiguous for a module → pause that module, flag to user, continue others
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] rtl/src/*.sv exists for every block in architecture.md
- [ ] All files pass Verible lint with zero errors (via Bash CLI)
- [ ] All files pass slang lint with zero errors (via Bash CLI)
- [ ] No module blocked after 3 fix rounds
- [ ] **rtl-critic functional coverage verdict is PASS**
- [ ] **Every REQ-NNN from requirements.json implemented in at least one RTL module**
- [ ] **Every uarch/*.md behavioral spec reflected in corresponding RTL module**
- [ ] All port names use `i_`/`o_`/`io_` prefix (NOT suffix `_i`/`_o`)
- [ ] All clocks: `{domain}_clk` (e.g., `sys_clk`) — no bare `clk`, `clk_i`, `clk_sys`
- [ ] All resets: `{domain}_rst_n` (e.g., `sys_rst_n`) — no bare `rst_n`, `rst_ni`
- [ ] All instances: `u_` prefix, generates: `gen_` prefix
- [ ] `logic` only — no `reg`/`wire` keywords
- [ ] `always_ff` for sequential, `always_comb` for combinational — no bare `always`
</Final_Checklist>

<Advanced>
rtl-coder should use parameters for all configurable constants (widths, depths).

**Clock and reset naming (project-specific override of lowRISC guide):**
- Clock: `{domain}_clk` — e.g., `sys_clk`, `pixel_clk`, `axi_clk`
  - WRONG: `clk`, `clk_i`, `clk_sys`, `clock`
- Reset: `{domain}_rst_n` — e.g., `sys_rst_n`, `pixel_rst_n`
  - WRONG: `rst_n`, `rst_ni`, `reset_n`, `rstn`
- Single clock domain defaults to `sys_clk` / `sys_rst_n`

**Port naming:**
- Inputs: `i_data`, `i_valid`, `i_addr` (NOT `data_i`, `valid_i`)
- Outputs: `o_result`, `o_ready`, `o_ack` (NOT `result_o`, `ready_o`)

**EDA tools run via Bash CLI directly** (not through MCP):
```bash
verilator --lint-only -Wall rtl/src/{module}.sv
slang --lint-only rtl/src/{module}.sv
```
</Advanced>
