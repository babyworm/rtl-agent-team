---
name: synth-check
description: "This skill should be used when running Yosys synthesis for area/timing estimation, synthesizability checking, or generating SDC timing constraints. Detects inferred latches, unmapped cells, and produces Design Compiler/Genus-ready SDC."
---

<Purpose>
Run Yosys synthesis on RTL and generate area, cell count, and critical path reports.
Optionally generate SDC timing constraints for commercial synthesis (Design Compiler, Genus).
Outputs: synth/reports/{module}_synth.txt, synth/summary.json, and constraints/design.sdc.

Supports both generic synthesis (no technology) and technology-mapped synthesis
(sky130, nangate45) for more accurate area/timing estimates.
See `references/yosys-commands.md` for command reference and latch detection guide.
See `references/sdc-best-practices.md` for SDC writing rules and tool-specific commands.
</Purpose>

<Use_When>
- RTL is lint-clean and pre-synthesis area/timing estimates are needed
- Checking whether RTL is synthesizable (no latches, no unresolved references)
- Comparing area impact of an RTL change
- SDC timing constraints needed for Design Compiler, Genus, or OpenSTA
- Pre-tapeout constraint review gate
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
- constraint-writer generates SDC from RTL analysis + uarch spec (when SDC requested)
- Gate: no synthesis errors (warnings acceptable with documentation)
</Execution_Policy>

<Steps>
1. Verify RTL uses `logic` (no `reg`/`wire`) before synthesis — flag violations early
2. eda-runner runs Yosys via Bash CLI (see `templates/yosys-synth-script.ys` for script template) — choose synthesis mode:
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
7. Write synth/summary.json (see `templates/synth-summary.json` for format).
   Use `skills/synth-check/scripts/parse_yosys_stat.py` to automate parsing: `python skills/synth-check/scripts/parse_yosys_stat.py synth/reports/{module}_synth.txt`
8. Flag any inferred latches as hard errors
9. **SDC Generation** (when timing constraints are needed):
   - constraint-writer reads requirements.json (clock frequencies), uarch/*.md (multicycle paths), RTL top-level (port list)
   - Use `templates/design-constraints.sdc` as the SDC scaffold
   - See `references/sdc-best-practices.md` for writing rules and common mistakes
   - Generates constraints/design.sdc with: clock definitions, IO delays, false paths, multicycle paths, design rules
   - Validates Tcl syntax: `tclsh constraints/design.sdc`
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run Yosys synthesis via Bash CLI on rtl/src/ with top module cabac_top. Command: yosys -p 'read_verilog -sv rtl/src/*.sv; synth -top cabac_top -flatten; stat' | tee synth/reports/cabac_top_synth.txt. Check output for inferred latches and reg/wire usage warnings.")

Task(subagent_type="rtl-agent-team:synthesis-reporter",
     prompt="Parse synth/reports/ Yosys output. Extract cell count, area estimate, logic depth. Flag any inferred latches as hard errors. Write synth/summary.json.")

# SDC Generation (optional — when timing constraints needed)
Task(subagent_type="rtl-agent-team:constraint-writer",
     prompt="Generate comprehensive SDC for design top module. Read requirements.json for clock frequencies, uarch/*.md for multicycle paths, RTL top-level for port list. Use templates/design-constraints.sdc as scaffold. Write constraints/design.sdc with: create_clock for all clocks using {domain}_clk naming, set_input_delay/set_output_delay for all i_*/o_* ports, set_false_path for async resets with justification, set_multicycle_path (both -setup and -hold) from uarch pipeline specs, design rules (set_max_fanout, set_max_transition). Validate with tclsh. See references/sdc-best-practices.md for rules.")
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
- [ ] constraints/design.sdc written (if SDC requested):
  - [ ] Every clock has create_clock or create_generated_clock
  - [ ] All I/O ports have set_input_delay / set_output_delay
  - [ ] Every set_false_path has justification comment
  - [ ] Every set_multicycle_path has both -setup and -hold
  - [ ] SDC passes Tcl syntax check
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
