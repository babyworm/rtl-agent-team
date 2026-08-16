---
name: rtl-ipxact-gen
description: "Generate IEEE 1685-2014 IP-XACT XML descriptor from RTL source — 'generate IP-XACT', IP handoff, or SoC/EDA integration needing component XML."
user-invocable: true
argument-hint: "[module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Generate a standards-compliant IP-XACT (IEEE 1685-2014) XML descriptor for an RTL module. Extracts ports, parameters, and bus interfaces directly from the SystemVerilog source to ensure the descriptor stays accurate as RTL evolves. Output: `ipxact/{module_name}.xml`, validated against the IEEE 1685-2014 schema.
</Purpose>

<Use_When>
- An RTL module needs an IP-XACT descriptor for EDA tool integration (Vivado, Quartus, Genus).
- IP handoff to a customer or partner requires IP-XACT.
- A SoC integration flow requires IP-XACT for automated port connection.
</Use_When>

<Do_Not_Use_When>
- Only Markdown documentation is needed — use `rtl-document` instead.
- An IP-XACT descriptor already exists and is current.
- The module is internal-only with no EDA tool integration requirement.
</Do_Not_Use_When>

<Why_This_Exists>
IP-XACT is the industry standard for IP description and enables automated integration in EDA tools. Manual XML authoring is error-prone; generating from RTL source ensures port widths and parameter values match implementation. The skill splits deterministic extraction (port/parameter lists) from interpretive mapping (bus interface classification), making the contract surface explicit.
</Why_This_Exists>

## Prerequisites

- RTL source at `rtl/{module}/{module}.sv` must exist.
- Optional: `sv_to_ipxact` CLI installed for schema-validated generation.

If the prerequisite is missing: WARNING — recommend running `/rtl-agent-team:rtl-p4-implement` first. Proceed with available artifacts; the orchestrator adapts scope.

<Assets>
| Path | Role |
|------|------|
| `templates/component-template.xml` | IP-XACT 2014 XML skeleton: vendor/library/name/version, busInterfaces, model/ports, parameters, memoryMaps stubs. |
| `scripts/gen_ipxact.py` | Deterministic IEEE 1685-2014 XML generator: parses SV module header (ANSI ports/parameters), emits VLNV + model/ports (widths kept as expressions) + parameters + fileSets. Stdlib-only fallback when `sv_to_ipxact` is unavailable. |
| `references/ipxact-conventions.md` | Port direction mapping, required XML sections, bus interface identification rules, anti-patterns. |
| `examples/` | Worked example: `pixel_fifo.sv` input + generated `pixel_fifo.xml` + README with the exact command and output checks. |
</Assets>

<Responsibility_Boundary>
- **Scripts** handle deterministic extraction: `sv_to_ipxact` (when installed) parses SV source and emits schema-validated XML; `rtl-explorer` extracts port/parameter lists as structured data when the CLI is unavailable.
- **LLM** handles interpretive mapping: bus interface type classification (AXI3/AXI4/APB/AHB), memory map register inference, and vendor/library/version field population.
- Contract surface: output XML must pass IEEE 1685-2014 schema validation; conventions in `references/ipxact-conventions.md`.
</Responsibility_Boundary>

<Execution>
1. Read `references/ipxact-conventions.md` for port direction mapping, required XML section order, and bus interface identification rules.
2. Attempt `sv_to_ipxact -i rtl/{module}/{module}.sv -o ipxact/{module}.xml --ipxact-2014 --validate`. If exit code 0, proceed to step 5. If `sv_to_ipxact` is not installed, run `python3 {plugin_root}/skills/rtl-ipxact-gen/scripts/gen_ipxact.py rtl/{module}/{module}.sv -o ipxact/{module}.xml` (`{plugin_root}` = plugin root resolved from `.rat/state/spawn-context.json`) for deterministic port/parameter extraction, then proceed to step 3.
3. Spawn `rtl-explorer` (see Tool_Usage) to extract all ports (name/direction/width), parameters, and identify AXI/APB/AHB bus interface groups by port name prefix.
4. Spawn `ipxact-generator` (see Tool_Usage) to write `ipxact/{module}.xml` — enriching the gen_ipxact.py output (or `templates/component-template.xml` scaffold) with bus interface and memory map sections. Preserve `i_`/`o_`/`io_` prefixes verbatim in `spirit:name`. Map `{domain}_clk` ports to clock roles and `{domain}_rst_n` to reset roles.
5. Validate: `xmllint --schema <ieee1685-2014.xsd> ipxact/{module}.xml --noout` (if xmllint available). Report PASS or FAIL with error summary.
6. Report the generated file path and validation result to the user.

Apply steps 1-6 to every requested module — do not stop after the first.
</Execution>

<Tool_Usage>
RTL extraction (sv_to_ipxact unavailable):
```
Task(subagent_type="rtl-agent-team:rtl-explorer",
     prompt="Read rtl/dma_controller/dma_controller.sv. Extract all ports (name/direction/width), parameters, and identify AXI/APB/AHB bus interfaces by port name grouping. Port direction: i_ = input, o_ = output, io_ = inout. Clocks match {domain}_clk, resets match {domain}_rst_n. Provide structured summary for IP-XACT generation.")
```

XML authoring (after extraction):
```
Task(subagent_type="rtl-agent-team:ipxact-generator",
     prompt="Generate IEEE 1685-2014 IP-XACT XML for dma_controller. Ports: {port_list}. Parameters: {param_list}. Bus interfaces: AXI4-Lite slave. Scaffold: {plugin_root}/skills/rtl-ipxact-gen/templates/component-template.xml. Preserve i_/o_/io_ prefixes in spirit:name. Map {domain}_clk to clock roles, {domain}_rst_n to reset roles. Write ipxact/dma_controller.xml.")
```
</Tool_Usage>

<Examples>
<example index="1">
<scenario>DMA controller with AXI4-Lite slave interface and 5 parameters.</scenario>
<reference>skills/rtl-ipxact-gen/examples/</reference>
<expected_output>`rtl-explorer` extracts 24 ports and 5 parameters; `ipxact-generator` produces valid IEEE 1685-2014 XML with one AXI4-Lite bus interface mapped; `xmllint` validation passes.</expected_output>
</example>

<example index="2">
<scenario>Module with parameterized port widths (e.g., `input logic [DATA_WIDTH-1:0] i_data`).</scenario>
<reference>skills/rtl-ipxact-gen/examples/</reference>
<expected_output>Port width recorded as expression `DATA_WIDTH` in IP-XACT rather than a hardcoded number; parameter `DATA_WIDTH` appears in the parameters section with its default value.</expected_output>
</example>

<example index="3">
<scenario>Bus interface type is ambiguous — ports match both AXI3 and AXI4 naming.</scenario>
<reference>skills/rtl-ipxact-gen/examples/</reference>
<expected_output>Generation pauses; user is asked to confirm AXI3 vs AXI4. XML is not delivered until the bus type is confirmed. No bus interface type is assumed or invented.</expected_output>
</example>
</Examples>

<Escalation_And_Stop_Conditions>
- XML schema validation fails → report the exact validation errors; do not deliver invalid XML.
- Bus interface type is ambiguous → ask the user to confirm before generating the busInterfaces section.
- Complex parameterized widths → document as expressions in `spirit:vector` elements; do not resolve to literals.
- RTL source has syntax errors → report file and line; do not attempt generation on unparseable source.
</Escalation_And_Stop_Conditions>

## Output

- `ipxact/{module_name}.xml` — IEEE 1685-2014 IP-XACT XML: component description, port maps, bus interfaces, parameters, and register maps (when a register interface is present).
- Schema validation result: `PASS` or `FAIL: {error summary}`.

<Final_Checklist>
- [ ] All RTL ports present in the IP-XACT ports section with verbatim names.
- [ ] All RTL parameters present in the parameters section.
- [ ] Bus interfaces correctly mapped (type confirmed by user if ambiguous).
- [ ] XML validates against IEEE 1685-2014 schema.
- [ ] RTL source not modified.
- [ ] `ipxact/{module}.xml` path and validation result reported to the user.
</Final_Checklist>
