---
name: ip-instantiate
description: "This skill should be used when generating IP instantiation wrappers from IP-XACT descriptors or datasheets with convention-compliant port mapping."
---

<Purpose>
Generate an RTL wrapper module that instantiates a third-party IP with correct port connections,
parameter settings, and tie-offs. Outputs: rtl/src/ip_wrappers/{ip_name}_wrapper.sv.
</Purpose>

<Use_When>
- Integrating a new third-party IP (memory, PLL, PHY, DSP block)
- IP has an IP-XACT descriptor or datasheet with port list
- Wrapper with standard AXI/APB/custom interface adapter is needed
</Use_When>

<Do_Not_Use_When>
- IP is already instantiated and only parameter changes needed (edit directly)
- IP is first-party RTL developed in this project (no wrapper needed)
- Full IP integration with verification needed (use func-verify after this skill)
</Do_Not_Use_When>

<Why_This_Exists>
IP instantiation is error-prone: wrong port widths, missing tie-offs, and parameter mismatches
cause subtle bugs. Automated wrapper generation from the authoritative IP descriptor
eliminates transcription errors and documents all connections explicitly.
</Why_This_Exists>

<Execution_Policy>
- rtl-explorer reads existing project structure and interface conventions
- rtl-architect designs the wrapper interface and connection strategy
- rtl-coder writes the wrapper RTL
- Wrapper MUST follow project coding conventions:
  - Port prefixes: `i_` (input), `o_` (output), `io_` (bidirectional)
  - Clock: `clk` (단일) or `{domain}_clk` (다중, e.g., `sys_clk`) — NOT `clk_i`
  - Reset: `rst_n` (단일) or `{domain}_rst_n` (다중, e.g., `sys_rst_n`) — NOT `rst_ni`
  - `logic` only — no `reg`/`wire`
  - Instance: `u_` prefix (e.g., `u_sram`)
  - Generate: `gen_` prefix
</Execution_Policy>

<Steps>
1. rtl-explorer reads project structure: existing wrappers in rtl/src/ip_wrappers/, interface conventions, coding style
2. rtl-architect reads IP descriptor (IP-XACT or datasheet): lists all ports, parameters, tie-off requirements
3. rtl-architect designs wrapper interface — adapts IP vendor port names to project conventions:
   - Vendor `clk_i` → project `clk` or `{domain}_clk` (e.g., `sys_clk`)
   - Vendor `rst_ni` → project `rst_n` or `{domain}_rst_n` (e.g., `sys_rst_n`)
   - Vendor ports → project `i_`/`o_`/`io_` prefix convention
4. rtl-coder writes rtl/src/ip_wrappers/{ip_name}_wrapper.sv:
   - Module declaration with `i_`/`o_`/`io_` prefixed ports, `logic` types only
   - IP instantiation with `u_` prefix (e.g., `u_{ip_name}`)
   - All ports connected or explicitly tied off with `// TIED: reason` comments
   - Parameter mapping with `// PARAM: description` comments
   - No `reg`/`wire` — `logic` only
5. lint-checker runs Verible + slang on generated wrapper via Bash CLI
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:rtl-explorer",
     prompt="Read rtl/src/ip_wrappers/ and docs/ for existing wrapper patterns. Summarize: port naming convention (i_/o_/io_ prefixes), clock naming ({domain}_clk), reset naming ({domain}_rst_n), instance naming (u_ prefix).")

Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Read IP descriptor at docs/ip/{ip_name}.xml (or datasheet). List all ports, required tie-offs, and parameter settings. Design wrapper interface: map vendor port names to project convention (i_/o_/io_ prefixes, {domain}_clk, {domain}_rst_n).")

Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Write rtl/src/ip_wrappers/{ip_name}_wrapper.sv. Instantiate {ip_name} as u_{ip_name} with all ports connected per architect spec. Use logic only (no reg/wire). Port prefixes: i_ (input), o_ (output), io_ (bidirectional). Clock: sys_clk, reset: sys_rst_n. Follow CLAUDE.md coding conventions.")
```
</Tool_Usage>

<Examples>
<Good>
rtl-explorer finds project uses AXI4-Lite for register interfaces with i_/o_ port prefixes;
rtl-architect reads SRAM IP-XACT, maps 32 vendor ports to project convention
(vendor clk→sys_clk, vendor rst_n→sys_rst_n, vendor din→i_sram_din);
rtl-coder writes wrapper instantiating as u_sram with logic types only; lint-check passes.
</Good>
<Bad>
Writing wrapper without reading existing project conventions — creates inconsistent port naming
that breaks downstream integration.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- IP descriptor not found → halt, ask user for IP datasheet or IP-XACT file location
- Port width mismatch between IP and project interface → flag to user, do not auto-resolve
- Generated wrapper fails lint → fix lint errors before delivering
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] IP port list fully read from descriptor
- [ ] All IP ports connected or explicitly tied off with `// TIED: reason` comments
- [ ] Wrapper ports use `i_`/`o_`/`io_` prefixes (NOT `_i`/`_o` suffix)
- [ ] Clocks use `clk` or `{domain}_clk` naming (NOT `clk_i`)
- [ ] Resets use `rst_n` or `{domain}_rst_n` naming (NOT `rst_ni`)
- [ ] IP instance uses `u_` prefix (e.g., `u_{ip_name}`)
- [ ] `logic` types only — no `reg`/`wire`
- [ ] lint-check passes on generated wrapper (Verible + slang)
- [ ] Wrapper path reported: rtl/src/ip_wrappers/{ip_name}_wrapper.sv
</Final_Checklist>
