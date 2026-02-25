---
name: synth-check
description: Synthesis flow using Yosys. Produces area, timing, and resource reports.
---

<Purpose>
Run Yosys synthesis on RTL and generate area, cell count, and critical path reports.
Outputs: synth/reports/{module}_synth.txt and synth/summary.json.
</Purpose>

<Use_When>
- RTL is lint-clean and pre-synthesis area/timing estimates are needed
- Checking whether RTL is synthesizable (no latches, no unresolved references)
- Comparing area impact of an RTL change
</Use_When>

<Do_Not_Use_When>
- RTL has lint errors (fix with lint-check first)
- Commercial synthesis tool required for signoff (Yosys is for estimation only)
- Only simulation results needed
</Do_Not_Use_When>

<Why_This_Exists>
Synthesis reveals RTL constructs that simulate correctly but are unsynthesizable or produce
unexpected hardware (latches, priority encoders). Early synthesis feedback prevents late-stage surprises.
</Why_This_Exists>

<Execution_Policy>
- eda-runner executes Yosys synthesis script
- synthesis-reporter parses output and produces structured summary
- Gate: no synthesis errors (warnings acceptable with documentation)
</Execution_Policy>

<Steps>
1. Verify RTL uses `logic` (no `reg`/`wire`) before synthesis — flag violations early
2. eda-runner runs Yosys via Bash CLI:
   ```bash
   yosys -p "read_verilog -sv rtl/src/*.sv; synth -top {top} -flatten; stat" \
     | tee synth/reports/{module}_synth.txt
   ```
3. Capture synth/reports/{module}_synth.txt (raw Yosys output)
4. synthesis-reporter parses: cell count, estimated area, critical path depth
5. Check for latches (inferred latches = synthesis error)
6. Write synth/summary.json: {module, cells, area_um2_est, max_logic_depth, latches_found}
7. Flag any inferred latches as hard errors
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run Yosys synthesis via Bash CLI on rtl/src/ with top module cabac_top. Command: yosys -p 'read_verilog -sv rtl/src/*.sv; synth -top cabac_top -flatten; stat' | tee synth/reports/cabac_top_synth.txt. Check output for inferred latches and reg/wire usage warnings.")

Task(subagent_type="rtl-agent-team:synthesis-reporter",
     prompt="Parse synth/reports/ Yosys output. Extract cell count, area estimate, logic depth. Flag any inferred latches as hard errors. Write synth/summary.json.")
```
</Tool_Usage>

<Examples>
<Good>
Synthesis runs clean; 12,450 cells; max logic depth 18; no latches; area estimate 0.8mm2 at 28nm.
</Good>
<Bad>
Ignoring Yosys latch warnings — inferred latches cause hold-time violations in silicon.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Synthesis errors (not warnings) → report to rtl-coder for RTL fix
- Inferred latches found → hard FAIL, report to rtl-coder with latch location
- Area estimate >2x target → report to rtl-architect for redesign consideration
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Yosys synthesis completed without errors
- [ ] No inferred latches
- [ ] synth/summary.json written
- [ ] Area estimate within target range (or deviation documented)
</Final_Checklist>

<Advanced>
Use Yosys with technology mapping (synth -liberty {lib.lib}) for more accurate area estimates.
Synthesis target library: sky130 or nangate45 for open-source estimation.
</Advanced>
