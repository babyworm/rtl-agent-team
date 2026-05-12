---
name: rtl-bug-repro
description: This skill should be used when the user asks to "reproduce this RTL bug", "create a minimal repro testbench", "isolate root cause for this failure", "waveform analysis for bug BUG-XXX", "write a repro TB for this simulation failure", or when a regression failure needs isolation to a specific RTL module.
user-invocable: true
argument-hint: "[bug-id | --failing-test <path>]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Reproduce a reported RTL bug with the minimal stimulus, isolate the root cause via waveform analysis, and produce a confirmed reproduction testbench. Outputs: `sim/bugs/{bug_id}/repro_tb.sv` (minimal TB that reproduces the failure) and `sim/bugs/{bug_id}/root_cause.md` (signal trace, first failure cycle, suspected RTL location).
</Purpose>

<Use_When>
- A bug has been reported with a failure log or a failing test case.
- A simulation failure needs root cause analysis before an RTL fix is attempted.
- A regression failure needs isolation to a specific module.
</Use_When>

<Do_Not_Use_When>
- The bug is in the testbench, not in RTL — fix the testbench directly.
- The root cause is already known — proceed to RTL fix.
- The bug is a synthesis issue — use `rtl-synth-check` instead.
</Do_Not_Use_When>

<Why_This_Exists>
Debugging without a minimal reproduction wastes time. Waveform analysis on the full regression is slow; a targeted minimal TB isolates the failure in minutes. `root_cause.md` documents the finding for the RTL engineer making the fix, and the repro TB can be added directly to the regression suite.
</Why_This_Exists>

## Prerequisites

- A failure log or failing `.vcd`/`.fst` waveform from a previous simulation run.
- RTL source for the suspected module under `rtl/**/*.sv`.

If prerequisites are missing: WARNING — recommend running the failing regression test first to obtain a waveform. Proceed with available artifacts; the orchestrator adapts scope.

<Assets>
| Path | Role |
|------|------|
| `templates/repro-tb-template.sv` | Minimal TB scaffold: clock/reset gen, DUT instantiation, stimulus, pass/fail assertion. |
| `scripts/vcd_diff.py` | Cycle-by-cycle VCD comparison — identifies first divergence between two waveform files. |
| `references/bug-repro-conventions.md` | Naming rules, output schema (repro_tb.sv / root_cause.md), length guidance, anti-patterns. |
| `examples/` | (placeholder — deep-fill in follow-up PR) |
</Assets>

<Responsibility_Boundary>
- **Scripts** handle deterministic waveform work: `vcd_diff.py` identifies the exact divergence cycle and signal path between two VCD files.
- **LLM** handles interpretive content: root cause hypothesis, signal trace narrative, suspected RTL location, and minimal stimulus design.
- Contract surface: `root_cause.md` structure documented in `references/bug-repro-conventions.md`.
</Responsibility_Boundary>

<Execution>
1. Read the bug report or failing test log to understand the symptoms.
2. Run `python3 skills/rtl-bug-repro/scripts/vcd_diff.py --actual sim/regression/{test}.vcd --expected sim/regression/{test}_golden.vcd` to identify the first divergence cycle and originating signal. If no golden VCD exists, spawn `waveform-analyzer` (see Tool_Usage) to analyze the failing VCD directly.
3. Read `skills/rtl-bug-repro/references/bug-repro-conventions.md` for naming, TB structure, and `root_cause.md` schema.
4. Spawn `func-verifier` (see Tool_Usage) to write `sim/bugs/{bug_id}/repro_tb.sv` using `templates/repro-tb-template.sv` as scaffold. The TB must: use `i_`/`o_` port prefixes, `{domain}_clk`/`{domain}_rst_n` names, `logic` types only, and `u_dut` for the DUT instance.
5. Run the repro TB: `scripts/run_sim.sh --sim iverilog --top repro_tb --outdir sim/bugs/{bug_id} --trace rtl/{module}/{module}.sv sim/bugs/{bug_id}/repro_tb.sv`. Confirm the failure reproduces.
6. Write `sim/bugs/{bug_id}/root_cause.md` with: symptom, first failure cycle, signal trace table, suspected RTL file and line, clock/reset context.

Apply steps 1-6 to every bug ID requested — do not stop after the first.
</Execution>

<Tool_Usage>
Waveform analysis (when no golden VCD for diff):
```
Task(subagent_type="rtl-agent-team:waveform-analyzer",
     prompt="Analyze sim/regression/test_cabac_fail.vcd. Find first divergence between actual and expected output. Identify originating module and signal path. Port signals use i_/o_ prefixes, clocks are {domain}_clk, resets are {domain}_rst_n.")
```

Minimal TB authoring and confirmation:
```
Task(subagent_type="rtl-agent-team:func-verifier",
     prompt="Write sim/bugs/BUG-042/repro_tb.sv that reproduces the CABAC bypass mode failure at cycle ~250. Minimize stimulus to the essential sequence. Use: i_/o_ port prefixes, sys_clk, sys_rst_n, u_dut instance, logic types only. Scaffold: skills/rtl-bug-repro/templates/repro-tb-template.sv. Run: scripts/run_sim.sh --sim iverilog --top repro_tb --outdir sim/bugs/BUG-042 --trace rtl/cabac_encoder/cabac_encoder.sv sim/bugs/BUG-042/repro_tb.sv. Confirm reproduction.")
```
</Tool_Usage>

<Examples>
<example index="1">
<scenario>Regression test `test_cabac_bypass` fails at cycle 247; waveform shows output divergence in the bypass path.</scenario>
<reference>skills/rtl-bug-repro/examples/</reference>
<expected_output>`vcd_diff.py` reports first divergence at cycle 247 on `u_cabac_encoder.o_bin_val`; `func-verifier` writes a 40-line `repro_tb.sv` that reproduces in 300 cycles; `root_cause.md` identifies missing state reset in `bypass_ctx` register at `rtl/cabac_encoder/cabac_encoder.sv:183`.</expected_output>
</example>

<example index="2">
<scenario>No golden VCD available; only the failing test log and the module source exist.</scenario>
<reference>skills/rtl-bug-repro/examples/</reference>
<expected_output>`waveform-analyzer` reads the failing VCD and identifies the signal path without a golden reference; `func-verifier` writes minimal stimulus based on the identified divergence point; `root_cause.md` labels the hypothesis as "suspected" pending confirmation by the repro run.</expected_output>
</example>

<example index="3">
<scenario>Bug affects three modules; regression isolates failure to the AXI-Stream bridge boundary.</scenario>
<reference>skills/rtl-bug-repro/examples/</reference>
<expected_output>Repro TB instantiates only the two modules at the failing boundary; `root_cause.md` documents all affected signal paths and flags the issue as systemic per escalation rules.</expected_output>
</example>
</Examples>

<Escalation_And_Stop_Conditions>
- Cannot reproduce with minimal TB → expand stimulus scope to the full failing test; note in `root_cause.md` that a minimal repro could not be isolated.
- Root cause requires architecture knowledge → include `rtl-architect` in the analysis task.
- Bug affects multiple modules → document all affected signal paths in `root_cause.md` and flag as systemic.
- VCD file is unreadable or corrupt → report the parse failure; do not fabricate waveform values.
</Escalation_And_Stop_Conditions>

## Output

- `sim/bugs/{bug_id}/repro_tb.sv` — minimal reproduction testbench, confirmed to reproduce the failure.
- `sim/bugs/{bug_id}/root_cause.md` — root cause analysis: symptom, first failure cycle, signal trace, suspected RTL location.
- `sim/bugs/{bug_id}/repro_tb.vcd` (or `.fst`) — waveform from the reproduction run.

<Final_Checklist>
- [ ] Existing waveform analyzed for first divergence point before writing the TB.
- [ ] Minimal repro TB written using `templates/repro-tb-template.sv` scaffold.
- [ ] TB confirmed to reproduce the failure (`run_sim.sh` exit code 0 + failure assertion fires).
- [ ] `sim/bugs/{bug_id}/root_cause.md` written with signal trace and suspected RTL location.
- [ ] RTL source not modified.
- [ ] Repro TB is small enough to add to the regression suite.
</Final_Checklist>
