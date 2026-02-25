---
name: synth-check
description: "This skill should be used when running Yosys synthesis for area/timing estimation or synthesizability checking. Detects inferred latches and unmapped cells."
---

<Purpose>
Run Yosys synthesis on RTL and generate area, cell count, and critical path reports.
Outputs: synth/reports/{module}_synth.txt and synth/summary.json.

Supports both generic synthesis (no technology) and technology-mapped synthesis
(sky130, nangate45) for more accurate area/timing estimates.
See `references/yosys-commands.md` for command reference and latch detection guide.
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
2. eda-runner runs Yosys via Bash CLI — choose synthesis mode:
   **Generic synthesis** (no technology mapping, quick check):
   ```bash
   yosys -p "read_verilog -sv rtl/src/*.sv; synth -top {top} -flatten; stat" \
     | tee synth/reports/{module}_synth.txt
   ```
   **Technology-mapped synthesis** (accurate area/timing with liberty file):
   ```bash
   yosys -p "read_verilog -sv rtl/src/*.sv; synth -top {top}; \
     dfflibmap -liberty {lib}.lib; abc -liberty {lib}.lib; \
     stat -liberty {lib}.lib" | tee synth/reports/{module}_synth.txt
   ```
   Supported libraries: sky130_fd_sc_hd (open-source), NangateOpenCellLibrary (academic)
3. Capture synth/reports/{module}_synth.txt (raw Yosys output)
4. synthesis-reporter parses: cell count, estimated area, critical path depth
5. **Latch detection** — check `stat` output for `$_DLATCH_` cells:
   - Any `$_DLATCH_*` count > 0 is a **HARD FAIL**
   - Common causes: missing `default:` in case, unassigned signal in if-else branches
   - See `references/yosys-commands.md` for latch detection details
6. Check for other concerning cells: `$mem` (unintended RAM), `$mul` (area-heavy multipliers)
7. Write synth/summary.json: {module, cells, area_um2_est, max_logic_depth, latches_found, library}
8. Flag any inferred latches as hard errors
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
Technology mapping with liberty files for accurate area estimates:
```bash
# Sky130 (open-source PDK)
dfflibmap -liberty sky130_fd_sc_hd__tt_025C_1v80.lib
abc -liberty sky130_fd_sc_hd__tt_025C_1v80.lib
stat -liberty sky130_fd_sc_hd__tt_025C_1v80.lib

# NanGate45 (academic PDK)
dfflibmap -liberty NangateOpenCellLibrary_typical.lib
abc -liberty NangateOpenCellLibrary_typical.lib
stat -liberty NangateOpenCellLibrary_typical.lib
```

Key `stat` output fields to monitor:
| Cell | Concern |
|------|---------|
| `$_DFF_*` | Normal flip-flops (count should match intent) |
| `$_DLATCH_*` | **CRITICAL — must be zero** |
| `$_MUX_` | High count may indicate priority encoding |
| `$add`, `$mul` | Check if area-efficient implementation needed |
| `$mem` | Check if SRAM inference was intended |

Additional useful commands: `scc -max_depth 10` (combinational loop check),
`write_verilog synth/netlist.v` (export netlist), `show -format dot` (schematic).
See `references/yosys-commands.md` for complete command reference.
</Advanced>
