# IP-XACT Generation Conventions

A quick reference for `rtl-ipxact-gen`. Stays under 150 lines so it can be consulted in one read.

## 1. Naming & output structure

| Element | Convention | Example |
|---------|-----------|---------|
| Output XML path | `ipxact/{module_name}.xml` | `ipxact/dma_controller.xml` |
| IP-XACT standard | IEEE 1685-2014 (default) | namespace `spirit:` or `ipxact:` |
| spirit:name | Preserve RTL port name verbatim (including `i_`/`o_`/`io_` prefix) | `<spirit:name>i_data</spirit:name>` |
| vendor field | Use project/org identifier; do not invent | `<spirit:vendor>acme.com</spirit:vendor>` |
| library field | RTL library name, snake_case | `<spirit:library>video_codec</spirit:library>` |
| version field | Match RTL parameter `VERSION` if present, else `1.0` | `<spirit:version>1.0</spirit:version>` |
| Clock/reset abstraction | Map `{domain}_clk` → clock role; `{domain}_rst_n` → reset role | |

Port direction mapping from RTL prefix:
- `i_` prefix → `<spirit:direction>in</spirit:direction>`
- `o_` prefix → `<spirit:direction>out</spirit:direction>`
- `io_` prefix → `<spirit:direction>inout</spirit:direction>`

## 2. Output schema — required XML sections

A well-formed IP-XACT component XML must contain these top-level elements in order:

```xml
<spirit:component>
  <spirit:vendor>...</spirit:vendor>
  <spirit:library>...</spirit:library>
  <spirit:name>{module_name}</spirit:name>
  <spirit:version>...</spirit:version>

  <spirit:busInterfaces>        <!-- one per identified bus (AXI/APB/AHB) -->
    <spirit:busInterface>...</spirit:busInterface>
  </spirit:busInterfaces>

  <spirit:model>
    <spirit:ports>              <!-- all RTL ports, verbatim names -->
      <spirit:port>...</spirit:port>
    </spirit:ports>
  </spirit:model>

  <spirit:parameters>           <!-- all RTL parameters -->
    <spirit:parameter>...</spirit:parameter>
  </spirit:parameters>

  <spirit:memoryMaps>           <!-- include only if register interface present -->
    <spirit:memoryMap>...</spirit:memoryMap>
  </spirit:memoryMaps>
</spirit:component>
```

Bus interface identification rules:
- AXI4 / AXI4-Lite: ports with `axi_` or `s_axi_` / `m_axi_` prefix groups
- APB: ports with `apb_` prefix group
- AHB: ports with `ahb_` prefix group
- When ambiguous (AXI3 vs AXI4), ask the user before generating

## 3. Length guidance

- XML file size: proportional to port count. A 20-port module with one bus interface
  typically produces 80–150 lines of XML. Do not pad with empty optional sections.
- memoryMaps: include only when a CSR/register interface is clearly present (APB/AXI-Lite
  slave with `addr` and `wen` signals). Omit rather than fabricate register details.
- Validation output: one line — `PASS: schema validation against IEEE 1685-2014` or
  `FAIL: {error summary}`. Do not include the full xmllint error log in the report.

## 4. Anti-patterns

- Do not hardcode port widths as literal numbers — extract from RTL and use expressions
  where parameterized (e.g., `{DATA_WIDTH}` as an IP-XACT expression).
- Do not rename ports in `spirit:name` — the XML port name must match the RTL port name
  exactly, including the `i_`/`o_`/`io_` prefix.
- Do not deliver XML that fails schema validation — report errors and stop.
- Do not fabricate bus interface types — if the interface type cannot be determined from
  port naming, mark the interface as `spirit:busType` unknown and flag for user review.
- Do not modify RTL source as part of IP-XACT generation.
- Do not include internal signals (nets that are not RTL module ports) in the ports section.
