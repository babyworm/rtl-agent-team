---
name: rtl-bug-repro
description: "This skill should be used when creating minimal reproduction testbenches for RTL bugs. Isolates root cause with waveform analysis."
---

<Purpose>
Reproduce a reported RTL bug with the minimal stimulus, isolate the root cause,
and produce a minimal reproduction test case.
Outputs: sim/bugs/{bug_id}/repro_tb.sv + sim/bugs/{bug_id}/root_cause.md.
</Purpose>

<Use_When>
- A bug has been reported with a failure log or failing test case
- A simulation failure needs root cause before RTL fix
- A regression failure needs isolation to a specific module
</Use_When>

<Do_Not_Use_When>
- Bug is in the testbench, not RTL (fix testbench directly)
- Root cause is already known (proceed to RTL fix)
- Bug is a synthesis issue (use rtl-synth-check instead)
</Do_Not_Use_When>

<Why_This_Exists>
Debugging without a minimal reproduction wastes time. Waveform analysis on the full
regression test is slow; a targeted minimal TB isolates the failure in minutes.
root_cause.md documents the finding for the RTL engineer making the fix.
</Why_This_Exists>

<Execution_Policy>
- waveform-analyzer reads existing failing simulation waveforms first
- func-verifier creates and runs a minimal reproduction TB
- Root cause documented in sim/bugs/{bug_id}/root_cause.md
- Do NOT fix RTL — reproduce and document only
</Execution_Policy>

<Steps>
1. Read the bug report / failing test log to understand symptoms
2. waveform-analyzer reads existing .vcd from the failing test:
   - Identifies first divergence cycle
   - Traces signal path to originating module (signals use i_/o_ prefixes)
   - Notes clock domain ({domain}_clk) and reset ({domain}_rst_n) context
3. func-verifier creates sim/bugs/{bug_id}/repro_tb.sv:
   - Minimal stimulus that reproduces failure
   - Targeted to the identified module only
   - Uses project conventions: i_/o_ port prefixes, {domain}_clk, {domain}_rst_n
   - `logic` types only, instance prefix `u_` for DUT
4. func-verifier runs repro_tb.sv via run_sim.sh and confirms reproduction:
   ```bash
   scripts/run_sim.sh --sim iverilog --top repro_tb --outdir sim/bugs/{bug_id} --trace \
     rtl/{module}/{module}.sv sim/bugs/{bug_id}/repro_tb.sv
   ```
5. waveform-analyzer performs deep analysis on repro waveform
6. Write sim/bugs/{bug_id}/root_cause.md:
   - Symptom, first failure cycle, signal trace (with full hierarchical names)
   - Suspected root cause, RTL file and line location
   - Clock domain and reset context if relevant
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:waveform-analyzer",
     prompt="Analyze sim/regression/test_cabac_fail.vcd. Find first divergence between actual and expected output. Identify originating module and signal. Note: port signals use i_/o_ prefixes, clocks are {domain}_clk, resets are {domain}_rst_n.")

Task(subagent_type="rtl-agent-team:func-verifier",
     prompt="Write sim/bugs/BUG-042/repro_tb.sv that reproduces the CABAC bypass mode failure at cycle ~250. Minimize stimulus to the essential sequence. Use project conventions: i_/o_ port prefixes, sys_clk for clock, sys_rst_n for reset, u_dut for DUT instance, logic types only. Run via: scripts/run_sim.sh --sim iverilog --top repro_tb --outdir sim/bugs/BUG-042 --trace rtl/cabac_encoder/cabac_encoder.sv sim/bugs/BUG-042/repro_tb.sv. Confirm reproduction.")
```
</Tool_Usage>

<Examples>
<Good>
waveform-analyzer finds RTL output diverges at cycle 247 in cabac_encoder bypass path;
func-verifier writes 40-line repro_tb that reproduces in 300 cycles;
root_cause.md identifies missing state reset in bypass_ctx register.
</Good>
<Bad>
Attempting to fix RTL before writing a repro — fix may mask the bug without resolving
the underlying issue, and no test case documents the failure.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Cannot reproduce with minimal TB → use full failing test, expand scope of waveform analysis
- Root cause requires architecture knowledge → include rtl-architect in analysis
- Bug affects multiple modules → document all affected paths, flag as systemic
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Existing waveform analyzed for first divergence point
- [ ] Minimal repro TB written and confirmed to reproduce
- [ ] sim/bugs/{bug_id}/root_cause.md written with signal trace
- [ ] RTL not modified
- [ ] Repro test case can be added to regression suite
</Final_Checklist>
