---
name: rtl-synth-check
description: "Yosys synthesis estimation on lint-clean RTL — 'synth check', 'area/timing estimate', 'generate SDC'; detects latches, emits DC/Genus-ready SDC."
user-invocable: true
---

<Purpose>
Run Yosys synthesis estimation on RTL targeting **ASIC TSMC 28nm** (approximated via NanGate45 liberty).
Area is reported in **NAND2 gate equivalents** (NAND2X1 fanout-of-2, ≈ 0.798 μm² in NanGate45).

**SDC-first flow**: SDC constraints are generated BEFORE synthesis to ensure timing-aware optimization.
Flow: 1. SDC generation → 2. sv2v conversion → 3. Yosys synthesis with NanGate45 liberty → 4. PPA report

Outputs: syn/log/ (logs), syn/rpt/ (reports), syn/vnet/ (netlist), syn/summary.json, and syn/constraints/design.sdc.

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
- RTL has lint errors (fix with rtl-lint-check first)
- Commercial synthesis tool required for signoff (Yosys is for estimation only)
- Only simulation results needed
</Do_Not_Use_When>

<Why_This_Exists>
Synthesis reveals RTL constructs that simulate correctly but are unsynthesizable or produce
unexpected hardware (latches, priority encoders). Early synthesis feedback prevents late-stage surprises.
</Why_This_Exists>

<Execution_Policy>
- **SDC-first**: constraint-writer generates SDC BEFORE synthesis (mandatory, not optional)
- eda-runner executes Yosys synthesis estimation with NanGate45 liberty
- For replayable execution, use `syn/scripts/run_syn.sh` (creates `syn/scr/replay/run_syn_*_latest.sh`)
- synthesis-reporter parses output, computes NAND2-FO2 gate count, and produces structured summary
- Target: ASIC TSMC 28nm estimation (NanGate45 as proxy)
- Area metric: NAND2 gate equivalents (total_area_um2 / 0.798)
- Gate: no synthesis errors, no inferred latches (warnings acceptable with documentation)
</Execution_Policy>

<Steps>
1. Verify RTL uses `logic` (no `reg`/`wire`) before synthesis — flag violations early

2. **SDC Generation (MANDATORY — before synthesis)**:
   - constraint-writer reads requirements.json (clock frequencies), docs/phase-3-uarch/*.md (multicycle paths), RTL top-level (port list)
   - Use `templates/design-constraints.sdc` as the SDC scaffold
   - See `references/sdc-best-practices.md` for writing rules and common mistakes
   - Generates syn/constraints/design.sdc with: clock definitions, IO delays, false paths, multicycle paths, design rules
   - Validates Tcl syntax: `tclsh syn/constraints/design.sdc`
   - **SDC must exist before synthesis estimation proceeds**

3. **Synthesis execution** (via replayable wrapper):
   `run_syn.sh` handles tool selection, sv2v conversion (Yosys path), and output normalization
   internally. Do NOT run sv2v manually — the script manages it as a Layer 2 concern.
   ```bash
   # Preferred: replayable wrapper (auto-includes rtl/common/, handles sv2v internally)
   syn/scripts/run_syn.sh --tool yosys --top {module} -f rtl/filelist_{module}.f --liberty NangateOpenCellLibrary_typical.lib

   # With commercial tool (no sv2v needed):
   syn/scripts/run_syn.sh --tool dc_shell --top {module} -f rtl/filelist_{module}.f

   # Optional: skip if tool unavailable (for non-blocking estimation)
   syn/scripts/run_syn.sh --tool yosys --top {module} -f rtl/filelist_{module}.f --skip-if-unavailable
   ```

4. **ASIC synthesis estimation** (NanGate45 liberty — TSMC 28nm proxy):
   Use the replayable wrapper or `templates/yosys-synth-script.ys` for script template:
   ```bash
   syn/scripts/run_syn.sh --tool yosys --top {module} -f rtl/filelist_{module}.f --liberty NangateOpenCellLibrary_typical.lib
   ```
   For manual debugging:
   ```bash
   yosys -p "read_verilog rtl/{module}/{module}_v2v.v; \
     hierarchy -check -top {module}; proc; opt; fsm; opt; \
     memory; opt; techmap; opt; \
     dfflibmap -liberty NangateOpenCellLibrary_typical.lib; \
     abc -liberty NangateOpenCellLibrary_typical.lib; clean; \
     stat -liberty NangateOpenCellLibrary_typical.lib" \
     | tee syn/log/{module}_synth.log
   ```
   **Note**: Always use NanGate45 (ASIC target). Do NOT use generic synthesis (no liberty) or FPGA synthesis.

4.5. **SRAM wrapper handling during synthesis**:
   - SRAM wrappers (`sram_sp`, `sram_tp`, `sram_dp` from `rtl/common/`) contain behavioral memory arrays
   - Yosys `memory` pass infers these as memory blocks (BRAM on FPGA, mapped cells on ASIC)
   - For ASIC with foundry macros: wrapper body replaced via `` `ifdef SYNTHESIS `` guard
   - Check `synth-summary.json` `memory_inference` field to verify correct inference
   - If SRAM incorrectly inferred as FFs → check `memory -nomap; stat` to debug

5. Capture syn/log/{module}_synth.log (raw Yosys output)

6. synthesis-reporter parses: cell count, area (μm²), NAND2-FO2 gate count, critical path depth
   - **Gate count formula**: `gate_count = total_area_um2 / 0.798` (NAND2X1 area in NanGate45)

7. **Latch detection** — check `stat` output for `$_DLATCH_` cells:
   - Any `$_DLATCH_*` count > 0 is a **HARD FAIL**
   - Common causes: missing `default:` in case, unassigned signal in if-else branches
   - See `references/yosys-commands.md` for latch detection details

8. Check for other concerning cells: `$mem` (unintended RAM), `$mul` (area-heavy multipliers)

9. Write syn/summary.json (see `templates/synth-summary.json` for format).
   Use `skills/rtl-synth-check/scripts/parse_yosys_stat.py` to automate parsing:
   ```bash
   python skills/rtl-synth-check/scripts/parse_yosys_stat.py syn/log/{module}_synth.log
   ```
   Output includes: area_um2, gate_count_nand2, technology target

9.5. **Commercial synthesis** (when available):
   Use the replayable wrapper which auto-generates tool scripts with SDC loading,
   SRAM don't-touch handling, and full PPA reporting (area/timing/power/QoR):
   ```bash
   # Synopsys Design Compiler
   syn/scripts/run_syn.sh --tool dc_shell --top {top} -f rtl/filelist_top.f --liberty <tech.lib>

   # Cadence Genus
   syn/scripts/run_syn.sh --tool genus --top {top} -f rtl/filelist_top.f --liberty <tech.lib>
   ```
   - Auto-generated scripts include: SDC source (`syn/constraints/design.sdc`),
     `rtl/common/` auto-inclusion, SRAM wrapper `dont_touch` placeholders,
     `report_area`, `report_timing`, `report_power`, `report_qor`
   - Provide `--script <tcl>` to use a custom Tcl script instead of auto-generation
   - SRAM wrappers: uncomment `dont_touch` lines in generated script when using foundry macros

10. Flag any inferred latches as hard errors
</Steps>

<Tool_Usage>
```
# ============================================================
# Step 2: SDC Generation (MANDATORY — before synthesis)
# ============================================================
Task(subagent_type="rtl-agent-team:constraint-writer",
     prompt="Generate comprehensive SDC for design top module. Read requirements.json for clock frequencies, docs/phase-3-uarch/*.md for multicycle paths, RTL top-level for port list. Use templates/design-constraints.sdc as scaffold. Write syn/constraints/design.sdc with: create_clock for all clocks using {domain}_clk naming, set_input_delay/set_output_delay for all i_*/o_* ports, set_false_path for async resets with justification, set_multicycle_path (both -setup and -hold) from uarch pipeline specs, design rules (set_max_fanout, set_max_transition). Validate with tclsh. See references/sdc-best-practices.md for rules.")

# ============================================================
# Step 3-4: ASIC Synthesis Estimation via wrapper (NanGate45 / TSMC 28nm proxy)
# ============================================================
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run ASIC synthesis estimation using wrapper: syn/scripts/run_syn.sh --tool yosys --top {top} -f rtl/filelist_top.f --liberty NangateOpenCellLibrary_typical.lib --skip-if-unavailable. Script handles sv2v conversion internally. Outputs: syn/rpt/ (reports), syn/vnet/ (netlist), syn/log/ (logs). Check output for inferred latches. If SKIPPED, record status.")

# ============================================================
# Step 6-9: Parse results → gate count (NAND2-FO2 equivalent)
# ============================================================
Task(subagent_type="rtl-agent-team:synthesis-reporter",
     prompt="Parse syn/log/ and syn/rpt/ Yosys output. Extract cell count, area (um2), compute NAND2-FO2 gate count (area / 0.798). Flag any inferred latches as hard errors. Write syn/summary.json with gate_count_nand2 field. Technology: ASIC TSMC 28nm (NanGate45 proxy).")
```
</Tool_Usage>

<Examples>
<Good>
ASIC 28nm estimation (NanGate45): 12,450 cells; area 9,935 μm²; 12,450 NAND2-FO2 gate equivalents;
max logic depth 18; no latches; SDC with 200MHz sys_clk constraint applied before synthesis.
</Good>
<Bad>
Running generic synthesis (no liberty file) — area/timing estimates are meaningless without technology mapping.
Skipping SDC creation — timing-unaware optimization produces unreliable PPA estimates.
Ignoring Yosys latch warnings — inferred latches cause hold-time violations in silicon.
Using FPGA synthesis (synth_xilinx) for ASIC estimation — wrong target technology.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Synthesis errors (not warnings) → report to rtl-coder for RTL fix
- Inferred latches found → hard FAIL, report to rtl-coder with latch location
- Area estimate >2x target → report to rtl-architect for redesign consideration
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] SDC generated BEFORE synthesis (syn/constraints/design.sdc)
  - [ ] Every clock has create_clock or create_generated_clock
  - [ ] All I/O ports have set_input_delay / set_output_delay
  - [ ] Every set_false_path has justification comment
  - [ ] Every set_multicycle_path has both -setup and -hold
  - [ ] SDC passes Tcl syntax check
- [ ] sv2v conversion done before Yosys
- [ ] Yosys synthesis estimation completed with NanGate45 liberty (ASIC target)
- [ ] No inferred latches
- [ ] syn/summary.json written with gate_count_nand2 field
- [ ] Area reported in NAND2-FO2 gate equivalents (area_um2 / 0.798)
- [ ] Technology recorded as "ASIC TSMC 28nm (NanGate45 proxy)"
</Final_Checklist>

<Advanced>
**Default ASIC synthesis flow (NanGate45 — TSMC 28nm proxy):**
```bash
# NanGate45 is the DEFAULT and ONLY target for ASIC estimation
dfflibmap -liberty NangateOpenCellLibrary_typical.lib
abc -liberty NangateOpenCellLibrary_typical.lib
stat -liberty NangateOpenCellLibrary_typical.lib
```

**NAND2-FO2 gate count conversion:**
- NanGate45 NAND2X1 area = 0.798 μm²
- Gate count = Chip area (from `stat -liberty`) / 0.798
- This is the standard area metric for all PPA reports
- Example: 9,935 μm² → 12,450 NAND2 gate equivalents

**Why NanGate45 for TSMC 28nm:**
- NanGate45 (FreePDK45) is the closest open-source liberty to real 28nm
- Gate count ratios (relative proportions) are representative
- Absolute area: apply scaling factor (45nm→28nm) ≈ (28/45)² ≈ 0.39 for physical area
- For estimation purposes, gate count is technology-independent

Key `stat` output fields to monitor:
| Cell | Concern |
|------|---------|
| `$_DFF_*` | Normal flip-flops (count should match intent) |
| `$_DLATCH_*` | **CRITICAL — must be zero** |
| `$_MUX_` | High count may indicate priority encoding |
| `$add`, `$mul` | Check if area-efficient implementation needed |
| `$mem` | Check if SRAM inference was intended |

Additional useful commands: `scc -max_depth 10` (combinational loop check),
`write_verilog syn/netlist.v` (export netlist), `show -format dot` (schematic).
See `references/yosys-commands.md` for complete command reference.
</Advanced>
