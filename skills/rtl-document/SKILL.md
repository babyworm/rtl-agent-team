---
name: rtl-document
description: "This skill should be used when generating RTL documentation from source and synthesis reports. Produces port tables and design summaries."
---

<Purpose>
Generate module-level documentation for RTL source files, including port tables,
parameter descriptions, functional descriptions, and synthesis summary.
Outputs: docs/rtl/{module_name}.md per module.
</Purpose>

<Use_When>
- New RTL module needs documentation
- Existing module documentation is stale after RTL changes
- Pre-release documentation pass required
</Use_When>

<Do_Not_Use_When>
- Architecture specification writing needed (use arch-design skill instead)
- IP-XACT generation needed (use rtl-ipxact-gen instead)
- Only synthesis reporting needed (use rtl-synth-check instead)
</Do_Not_Use_When>

<Why_This_Exists>
RTL documentation written manually drifts from implementation. Generating it from
the actual source files and synthesis reports ensures accuracy. Structured docs
with port tables and functional descriptions accelerate integration and review.
</Why_This_Exists>

<Execution_Policy>
- rtl-explorer reads source files to extract module structure
- synthesis-reporter provides area and timing data if synth report exists
- Output is Markdown per module, following docs/ structure
- Do NOT modify RTL source during documentation
</Execution_Policy>

<Steps>
1. rtl-explorer reads rtl/{module}/{module}.sv: extracts ports, parameters, internal signals, FSM states
2. rtl-explorer reads module header comments for existing functional description
3. If syn/synth_report.txt exists, read for area/timing data
4. rtl-explorer writes docs/rtl/{module}.md:
   - Module overview (functional description)
   - Port table (name, direction, width, description)
     - Port names reflect project convention: `i_` prefix = input, `o_` prefix = output, `io_` = bidir
     - Clock ports: `{domain}_clk` (e.g., `sys_clk`, `pixel_clk`)
     - Reset ports: `{domain}_rst_n` (e.g., `sys_rst_n`)
   - Parameter table (name, default, description) — `UPPER_SNAKE_CASE`
   - Timing/clocking notes (clock domain names, reset strategy)
   - Instance table (sub-module instantiations with `u_` prefix)
   - Synthesis summary (if available)
   - **Convention compliance notes**: flag any naming violations found in the RTL source
5. Report generated files to user
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:rtl-explorer",
     prompt="Read rtl/cabac_encoder/cabac_encoder.sv. Extract all ports, parameters, and functional behavior. Write docs/rtl/cabac_encoder.md with: port table (noting i_/o_/io_ prefix convention, {domain}_clk/{domain}_rst_n), parameter table (UPPER_SNAKE_CASE), instance table (u_ prefix), FSM state list, and functional description. Flag any naming convention violations found.")

Task(subagent_type="rtl-agent-team:synthesis-reporter",
     prompt="Read syn/synth_report.txt and syn/timing_report.txt. Provide area and timing summary section for docs/rtl/cabac_encoder.md.")
```

Port table format in generated docs:
```markdown
| Port Name    | Direction | Width | Clock Domain | Description          |
|--------------|-----------|-------|--------------|----------------------|
| sys_clk      | input     | 1     | sys          | System clock         |
| sys_rst_n    | input     | 1     | sys          | Active-low reset     |
| i_data       | input     | 32    | sys          | Input data bus       |
| o_valid      | output    | 1     | sys          | Output valid signal  |
```
</Tool_Usage>

<Examples>
<Good>
rtl-explorer reads cabac_encoder.sv with 18 ports (i_data, i_valid, o_encoded, o_ready, sys_clk, sys_rst_n, etc.);
generates docs/rtl/cabac_encoder.md with accurate port table using i_/o_ prefix convention,
3 parameter descriptions (DATA_WIDTH, DEPTH, MODE), FSM state list (ST_IDLE, ST_ENCODE, ST_FLUSH),
instance table (u_range_coder, u_context_mem), and synthesis summary from existing synth report.
</Good>
<Bad>
Generating documentation without reading the actual RTL — produces generic placeholder docs
that don't match the implementation. Or documenting ports with wrong naming convention
(e.g., writing `data_i` in port table when RTL says `i_data`).
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Module has no header comments → generate structural docs from code, note missing description
- Synthesis report not available → omit synthesis section, note it in document
- Port widths use complex expressions → document the expression, do not evaluate
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] docs/rtl/{module}.md created for each target module
- [ ] Port table complete with all ports listed (using `i_`/`o_`/`io_` prefix notation)
- [ ] Clock/reset ports documented with `{domain}_clk`/`{domain}_rst_n` naming
- [ ] Parameter table complete with defaults (`UPPER_SNAKE_CASE`)
- [ ] Instance table lists all sub-modules with `u_` prefix
- [ ] RTL source not modified
- [ ] Synthesis summary included if synth report available
- [ ] Naming convention violations flagged (if any found in source)
</Final_Checklist>
