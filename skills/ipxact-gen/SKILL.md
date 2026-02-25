---
name: ipxact-gen
description: Generate IEEE 1685 IP-XACT XML descriptor from RTL source.
---

<Purpose>
Generate a standards-compliant IP-XACT (IEEE 1685) XML descriptor for an RTL module.
Outputs: ipxact/{module_name}.xml with component, bus interfaces, ports, and memory maps.
</Purpose>

<Use_When>
- RTL module needs IP-XACT descriptor for EDA tool integration
- IP handoff to customer or partner requires IP-XACT
- SoC integration flow requires IP-XACT for automated connection
</Use_When>

<Do_Not_Use_When>
- Only Markdown documentation needed (use rtl-document instead)
- IP-XACT already exists and is current
- Module is internal-only with no EDA tool integration requirement
</Do_Not_Use_When>

<Why_This_Exists>
IP-XACT is the industry standard for IP description and enables automated integration
in EDA tools (Vivado, Quartus, Genus). Manual XML authoring is error-prone;
generating from RTL source ensures port widths and parameter values are accurate.
</Why_This_Exists>

<Execution_Policy>
- rtl-explorer reads RTL to extract port and parameter information
- ipxact-generator writes standards-compliant XML
- Schema validation must pass (IEEE 1685-2014)
- Do NOT modify RTL source
</Execution_Policy>

<Steps>
1. rtl-explorer reads rtl/src/{module}.sv: extracts ports (name, direction, width), parameters, clock/reset ports
   - Port direction inferred from prefix: `i_` = input, `o_` = output, `io_` = inout
   - Clock ports identified by `{domain}_clk` pattern (e.g., `sys_clk`, `axi_clk`)
   - Reset ports identified by `{domain}_rst_n` pattern (e.g., `sys_rst_n`)
2. rtl-explorer identifies bus interfaces (AXI, APB, AHB) by port name grouping
3. ipxact-generator writes ipxact/{module}.xml:
   - component element with vendor/library/name/version
   - busInterfaces for each identified bus (map `i_`/`o_` prefixed ports to bus port names)
   - ports section with all RTL ports mapped (preserve `i_`/`o_`/`io_` prefixes in spirit:name)
   - parameters section with all RTL parameters
   - memoryMaps section if register interface present
   - Clock and reset ports mapped to their respective bus clock/reset roles
4. Validate XML against IP-XACT 2014 schema (use xmllint via Bash CLI if available)
5. Report validation result
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:rtl-explorer",
     prompt="Read rtl/src/dma_controller.sv. Extract all ports (name/direction/width), parameters, and identify any AXI/APB/AHB bus interfaces. Port direction follows project convention: i_ prefix = input, o_ prefix = output, io_ prefix = inout. Clocks match {domain}_clk, resets match {domain}_rst_n. Provide structured summary for IP-XACT generation.")

Task(subagent_type="rtl-agent-team:ipxact-generator",
     prompt="Generate IEEE 1685-2014 IP-XACT XML for dma_controller. Ports: {port_list}. Parameters: {param_list}. Bus interfaces: AXI4-Lite slave. Preserve i_/o_/io_ port name prefixes in spirit:name elements. Map {domain}_clk ports as clock roles and {domain}_rst_n as reset roles. Write ipxact/dma_controller.xml.")
```
</Tool_Usage>

<Examples>
<Good>
rtl-explorer extracts 24 ports and 5 parameters from dma_controller.sv;
ipxact-generator produces valid IEEE 1685-2014 XML with AXI4-Lite bus interface mapped;
schema validation passes.
</Good>
<Bad>
Hardcoding port widths as numbers rather than using RTL-extracted values — creates
IP-XACT that diverges from implementation when RTL is updated.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- XML schema validation fails → report exact validation errors, do not deliver invalid XML
- Bus interface type ambiguous → ask user to confirm (AXI3 vs AXI4, etc.)
- Complex parameterized widths → document as expressions in IP-XACT spirit element
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All RTL ports present in IP-XACT ports section
- [ ] All RTL parameters present in IP-XACT parameters section
- [ ] Bus interfaces correctly mapped
- [ ] XML validates against IEEE 1685-2014 schema
- [ ] ipxact/{module}.xml path reported to user
</Final_Checklist>
