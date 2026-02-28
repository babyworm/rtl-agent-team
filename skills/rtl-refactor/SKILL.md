---
name: rtl-refactor
description: "This skill should be used when restructuring RTL code without behavioral change. Applies naming conventions and verifies equivalence."
---

<Purpose>
Refactor existing RTL for improved readability, maintainability, or lint compliance
without changing functional behavior. Verifies equivalence after refactoring.
</Purpose>

<Use_When>
- RTL exists but has structural problems (naming, style, lint violations)
- Module needs to be split or merged without behavioral change
- Preparing RTL for review or handoff
</Use_When>

<Do_Not_Use_When>
- Behavioral change is needed (use rtl-code for new implementation)
- Only lint checking needed without fixing (use rtl-lint-check instead)
</Do_Not_Use_When>

<Why_This_Exists>
Refactoring RTL is risky without equivalence verification — a "cosmetic" rename can break
a signal connection. Combining rtl-architect analysis with lint-checker verification provides safety.
</Why_This_Exists>

<Execution_Policy>
- rtl-architect analyzes structure and produces refactoring plan
- rtl-coder implements the refactoring per plan
- lint-checker verifies lint-clean after refactoring
- Formal equivalence check if tool available; otherwise simulation smoke test
</Execution_Policy>

<Steps>
1. rtl-architect reads target file(s), produces refactoring plan (what changes, what must stay identical)
   - Plan must include naming convention audit:
     - Ports: `i_`/`o_`/`io_` prefix (NOT suffix `_i`/`_o`) — flag violations for correction
     - Clocks: `clk` (single domain) or `{domain}_clk` (multiple domains) — flag `clk_i`, `clk_sys`
     - Resets: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains) — flag `rst_ni`
     - Instances: `u_` prefix — flag missing prefix
     - Generates: `gen_` prefix — flag missing prefix
     - `logic` only — flag any `reg`/`wire` usage
2. rtl-coder implements changes per plan, maintaining naming conventions
3. lint-checker validates lint-clean via Bash CLI: `verilator --lint-only -Wall` and `slang --lint-only`
4. Run smoke simulation or formal equivalence check to confirm no behavioral change
   - Bash CLI: `verilator --cc rtl/{module}/{module}.sv --exe sim/{module}/tb_{module}.cpp && make -C obj_dir`
   - Or: `cd formal/ && sby -f {module}.sby`
5. Report: what changed, naming convention fixes applied, equivalence evidence
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Analyze rtl/entropy_coder/entropy_coder.sv and produce a refactoring plan. Include: (1) naming convention fixes (i_/o_ prefix NOT _i/_o suffix, clk or {domain}_clk NOT clk_i, rst_n or {domain}_rst_n NOT rst_ni, u_ instance prefix, gen_ generate prefix), (2) module size reduction, (3) reg/wire to logic conversion. READ-ONLY analysis.")

Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Apply refactoring plan to rtl/entropy_coder/entropy_coder.sv: [paste plan]. Ensure all names use i_/o_ prefix, sys_clk/sys_rst_n convention. Do not change behavior.")

Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Run lint via Bash CLI: 'verilator --lint-only -Wall rtl/entropy_coder/entropy_coder.sv' and 'slang --lint-only rtl/entropy_coder/entropy_coder.sv'. Report any violations. Verify naming conventions (i_/o_ prefix, {domain}_clk/{domain}_rst_n).")
```
</Tool_Usage>

<Examples>
<Good>
Split 800-line module into 3 focused modules; lint-checker confirms clean; smoke sim passes same vectors as before.
</Good>
<Bad>
Refactoring signal names without checking all instantiation sites — breaks hierarchical connections silently.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Equivalence check fails → revert to original, report diff to user
- Refactoring plan conflicts with uarch spec → pause, flag to user
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All changed files pass lint (Verible + slang via Bash CLI)
- [ ] Equivalence verified (formal or smoke sim)
- [ ] No instantiation sites broken
- [ ] Refactoring plan followed exactly
- [ ] All port names use `i_`/`o_`/`io_` prefix (NOT suffix `_i`/`_o`)
- [ ] All clocks: `{domain}_clk` (e.g., `sys_clk`) — bare `clk` OK for single domain, `{domain}_clk` for multiple domains. NOT `clk_i`
- [ ] All resets: `{domain}_rst_n` (e.g., `sys_rst_n`) — bare `rst_n` OK for single domain, `{domain}_rst_n` for multiple domains. NOT `rst_ni`
- [ ] All instances: `u_` prefix, generates: `gen_` prefix
- [ ] No `reg`/`wire` keywords — `logic` only
</Final_Checklist>

<Advanced>
For large module splits, update all instantiation sites in the same task to maintain consistency.

**Common refactoring patterns for naming convention compliance:**
- `data_i` -> `i_data`, `valid_o` -> `o_valid` (suffix to prefix)
- `clk_i` -> `clk` or `sys_clk` (suffix clock to conformant name)
- `rst_ni` -> `rst_n` or `sys_rst_n` (suffix reset to conformant name)
- `fifo_inst` -> `u_fifo` (missing instance prefix)
- `reg [7:0] data` -> `logic [7:0] data` (reg to logic)

When renaming ports, use Grep to find ALL instantiation sites across the codebase and update them in the same task.
</Advanced>
