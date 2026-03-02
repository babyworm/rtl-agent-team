---
name: rtl-p5s-cdc-verify
description: "This skill should be used when analyzing clock domain crossings for synchronizer coverage and metastability risks."
user-invocable: true
---

<Purpose>
Perform static CDC analysis on RTL to identify missing synchronizers, metastability risks,
and CDC constraint gaps. Outputs: sim/cdc/cdc_report.md + syn/constraints/cdc_constraints.sdc.

See `references/cdc-patterns.md` for synchronizer types, common violations, and SDC constraint templates.
</Purpose>

<Use_When>
- RTL design has multiple clock domains
- Pre-synthesis CDC sign-off required
- New clock domain or crossing signal added to existing design
- CDCcheck in pre-tapeout checklist
</Use_When>

<Do_Not_Use_When>
- Design is single-clock (CDC analysis not applicable)
- Only functional simulation needed
- Synthesis timing analysis needed (use rtl-synth-check instead)
</Do_Not_Use_When>

<Why_This_Exists>
CDC bugs are among the hardest to find in simulation because metastability is
non-deterministic. Static analysis catches structural CDC violations reliably
before they become intermittent silicon failures.
</Why_This_Exists>

<Coding_Convention_Requirements>
CDC analysis MUST recognize the project clock/reset naming conventions (CLAUDE.md):
- Clocks: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`, `axi_clk`, `pixel_clk`)
  - NOT `clk_i`, `clk_sys` — these are non-conformant
- Resets: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`, `axi_rst_n`)
  - NOT `rst_ni` — this is non-conformant
- Clock/reset ports: `i_` prefix not required (exception). All other ports require `i_`/`o_`/`io_`
- Synchronizer instances: `u_` prefix (e.g., `u_sync_axi_to_sys`)
- Gray code modules: `u_` prefix (e.g., `u_gray_encoder`)

If RTL uses non-conformant clock/reset names, flag as a CONVENTION VIOLATION in the report
in addition to any CDC violations.
</Coding_Convention_Requirements>

<Execution_Policy>
- cdc-checker runs static analysis on RTL (structural, not simulation-based)
- constraint-writer generates SDC constraints to properly define clock domains
- Report categorizes findings: VIOLATION (missing sync), CAUTION (complex path), INFO, CONVENTION
- No auto-fix of RTL — report violations only
</Execution_Policy>

<Steps>
1. cdc-checker reads rtl/*/*.sv and identifies all clock domain signals
   - Expects `{domain}_clk` naming; flag any non-conformant clock names as CONVENTION violation
2. cdc-checker analyzes all cross-domain paths:
   - Missing synchronizers (flip-flop to flip-flop, different clocks)
   - Multi-bit bus crossings without gray code or handshake
   - Fanout from synchronized signal
   - Reset domain crossings (e.g., `sys_rst_n` used in `axi_clk` domain)
3. constraint-writer writes syn/constraints/cdc_constraints.sdc defining clock groups
   - Use `templates/cdc-constraints.sdc` as the SDC template
   - Uses `{domain}_clk` names consistent with RTL
4. cdc-checker writes sim/cdc/cdc_report.md (use `templates/cdc-report.md` as format template):
   - VIOLATION: unsynced crossing (file:line, source clock, dest clock)
   - CAUTION: complex multi-bit crossing needing review
   - CONVENTION: non-conformant clock/reset naming (file:line, found name, expected format)
   - INFO: safe crossings (gray code, handshake, quasi-static)
5. Report violation count to user
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:cdc-checker",
     prompt="Analyze rtl/*/*.sv for CDC violations. Identify all clock domains (expect {domain}_clk naming per CLAUDE.md). List all cross-domain signal paths, flag missing synchronizers. Also flag any non-conformant clock/reset names (clk_i, rst_ni, etc.). Write sim/cdc/cdc_report.md.")

Task(subagent_type="rtl-agent-team:constraint-writer",
     prompt="Read sim/cdc/cdc_report.md and rtl/*/*.sv. Write syn/constraints/cdc_constraints.sdc defining clock groups for all identified clock domains. Use {domain}_clk names matching RTL (e.g., sys_clk, axi_clk, codec_clk).")
```
</Tool_Usage>

<Examples>
<Good>
cdc-checker finds 3 clock domains (`sys_clk`, `axi_clk`, `codec_clk`); identifies 2 unsynced
crossings (VIOLATION) and 1 multi-bit bus without gray code (CAUTION);
all clock names follow `{domain}_clk` convention; synchronizers use `u_sync_` prefix;
constraint-writer generates correct `set_clock_groups` SDC; report written.
</Good>
<Bad>
Relying on simulation with UVM to catch CDC bugs — simulation may never trigger
the specific timing that causes metastability.
Not flagging `clk_i` or `rst_ni` in RTL — allows convention violations to persist into production.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- VIOLATION found → surface immediately, do NOT auto-insert synchronizers
- CONVENTION violation found → report alongside CDC violations, recommend fix before sign-off
- Clock domains cannot be determined from RTL alone → ask user for clocking architecture doc
- Tool (vc_cdc, Meridian, or spyglass) not available → use structural RTL analysis only
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All clock domains identified in RTL (expect `{domain}_clk` format)
- [ ] All cross-domain paths analyzed
- [ ] Non-conformant clock/reset names flagged as CONVENTION violations
- [ ] sim/cdc/cdc_report.md written with VIOLATION/CAUTION/CONVENTION/INFO classification
- [ ] syn/constraints/cdc_constraints.sdc written with correct clock domain names
- [ ] RTL not modified
- [ ] Violation count reported to user
</Final_Checklist>

<Advanced>
Synchronizer type selection guide:
| Crossing Type | Recommended Synchronizer |
|---------------|-------------------------|
| Single-bit control | 2-FF synchronizer (3-FF for high-freq) |
| Multi-bit counter | Gray code FIFO |
| Multi-bit data bus | Handshake (REQ/ACK) or MUX synchronizer |
| Single-cycle pulse | Pulse synchronizer (toggle-based) |
| Reset signal | Async assert, sync deassert reset synchronizer |

For comprehensive CDC analysis, commercial tools (SpyGlass CDC, Conformal CDC, Questa CDC)
provide formal proof of synchronizer correctness beyond structural analysis.

See `references/cdc-patterns.md` for SDC constraint templates, violation checklist,
and detailed synchronizer implementation guidance.
</Advanced>
