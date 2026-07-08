---
name: rtl-ip-instantiate
description: "Generate convention-compliant SV wrapper for third-party IP (memory, PLL, PHY, DSP) — 'instantiate IP', 'IP wrapper', 'integrate third-party IP'."
user-invocable: true
argument-hint: "[ip-name | path/to/ip-descriptor.xml]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Generate a convention-compliant SystemVerilog wrapper module that instantiates a third-party IP with correct port connections, parameter settings, and explicit tie-offs. Output: `rtl/ip_wrappers/{ip_name}_wrapper.sv`.
</Purpose>

<Use_When>
- Integrating a new third-party IP (memory, PLL, PHY, DSP block) with an IP-XACT descriptor or datasheet.
- A wrapper with standard AXI/APB or custom interface adaptation is needed.
- Vendor port names must be translated to project naming conventions.
</Use_When>

<Do_Not_Use_When>
- IP is already instantiated and only parameter changes are needed — edit the file directly.
- IP is first-party RTL developed in this project — no wrapper needed.
- Full IP integration with verification is needed → run `rtl-p5s-func-verify` after this skill.
</Do_Not_Use_When>

<Why_This_Exists>
IP instantiation is error-prone: wrong port widths, missing tie-offs, and parameter mismatches cause subtle bugs that survive lint. Automated wrapper generation from the authoritative IP descriptor eliminates transcription errors and documents every connection explicitly, making the mapping auditable.
</Why_This_Exists>

## Prerequisites

- IP descriptor present at `docs/ip/{ip_name}.xml` (IP-XACT) or equivalent datasheet.
- Project coding conventions readable from `rtl/ip_wrappers/` (existing wrappers) or `.claude/rules/rtl-coding-conventions.md`.

If missing: WARNING — halt and ask user for IP descriptor location before generating.

<Assets>
| Path | Role |
|------|------|
| `templates/ip-wrapper-template.sv` | SV wrapper scaffold with `u_` instance, `logic`-only ports, `// TIED:` and `// PARAM:` comment patterns. |
| `scripts/.gitkeep` | (placeholder — deep-fill in follow-up PR) |
| `references/ip-instantiate-conventions.md` | Port-prefix rules, vendor-to-project mapping table, tie-off/param comment format, anti-patterns. |
| `examples/.gitkeep` | (placeholder — deep-fill in follow-up PR) |
</Assets>

<Responsibility_Boundary>
- **Scripts** handle lint validation (Verible + slang) via Bash CLI.
- **LLM** handles port mapping design, tie-off decisions, and parameter documentation.
- Contract surface: every IP port either connects to a wrapper port or carries a `// TIED: reason` comment; no silent unconnected ports.
</Responsibility_Boundary>

<Execution>
1. Spawn `rtl-explorer` to read existing `rtl/ip_wrappers/` and summarise current naming conventions (port prefixes, clock/reset style, instance prefix).
2. Spawn `rtl-architect` to read the IP descriptor — list all ports, tie-off requirements, and parameter settings; design wrapper interface mapping vendor names to project conventions (`i_`/`o_`/`io_` prefixes, `{domain}_clk`, `{domain}_rst_n`).
3. Spawn `rtl-coder` to write `rtl/ip_wrappers/{ip_name}_wrapper.sv` using `templates/ip-wrapper-template.sv` as scaffold — `logic` types only, `u_{ip_name}` instance, all ports connected or `// TIED:`, parameters documented with `// PARAM:`.
4. Run lint: `verible-verilog-lint rtl/ip_wrappers/{ip_name}_wrapper.sv && slang rtl/ip_wrappers/{ip_name}_wrapper.sv` — fix all errors before delivering.
5. Report wrapper path to the user.

Apply steps 1-5 to every requested IP — do not stop after the first.
</Execution>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:rtl-explorer",
     prompt="Read rtl/ip_wrappers/ and docs/ for existing wrapper patterns. Summarise: "
            "port naming convention (i_/o_/io_ prefixes), clock naming ({domain}_clk), "
            "reset naming ({domain}_rst_n), instance naming (u_ prefix).")

Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Read IP descriptor at docs/ip/{ip_name}.xml (or datasheet). List all ports, "
            "required tie-offs, and parameter settings. Design wrapper interface: map vendor "
            "port names to project convention (i_/o_/io_ prefixes, {domain}_clk, {domain}_rst_n).")

Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Write rtl/ip_wrappers/{ip_name}_wrapper.sv. Instantiate {ip_name} as u_{ip_name} "
            "with all ports connected per architect spec. Use logic only (no reg/wire). "
            "Port prefixes: i_ input, o_ output, io_ bidirectional. "
            "Clock: {domain}_clk, reset: {domain}_rst_n. "
            "Tied ports: // TIED: reason. Parameters: // PARAM: description.")
```
</Tool_Usage>

<Examples>
<example index="1">
<scenario>SRAM IP with 32 vendor ports; IP-XACT at docs/ip/sram.xml; project uses AXI4-Lite.</scenario>
<expected_output>rtl-explorer confirms i_/o_ prefix style; rtl-architect maps vendor clk→sys_clk, rst_n→sys_rst_n, din→i_sram_din; rtl-coder writes wrapper with u_sram instance and logic types; lint passes.</expected_output>
</example>

<example index="2">
<scenario>PLL IP with test-mode ports that must be tied off.</scenario>
<expected_output>All functional ports connected; test-mode ports tied to constants with `// TIED: unused test mode input` comments; parameter DATA_WIDTH documented with `// PARAM: AXI data bus width`.</expected_output>
</example>

<example index="3">
<scenario>IP has port width mismatch — vendor provides 36-bit data bus, project interface is 32-bit.</scenario>
<expected_output>rtl-architect flags mismatch to user; wrapper generation halted pending user resolution decision; no auto-truncation performed.</expected_output>
</example>
</Examples>

<Escalation_And_Stop_Conditions>
- IP descriptor not found → halt immediately; ask user for datasheet or IP-XACT file path.
- Port width mismatch between IP and project interface → flag to user; do not auto-resolve.
- Generated wrapper fails lint → fix all errors before delivering; do not suppress warnings without documented rationale.
</Escalation_And_Stop_Conditions>

## Output

- `rtl/ip_wrappers/{ip_name}_wrapper.sv` — convention-compliant wrapper module.

<Final_Checklist>
- [ ] IP port list fully read from descriptor before writing wrapper.
- [ ] All IP ports connected or explicitly tied off with `// TIED: reason` comments.
- [ ] Wrapper ports use `i_`/`o_`/`io_` prefixes (NOT `_i`/`_o` suffix).
- [ ] Clocks use `clk` or `{domain}_clk` naming (NOT `clk_i`).
- [ ] Resets use `rst_n` or `{domain}_rst_n` naming (NOT `rst_ni`).
- [ ] IP instance uses `u_` prefix (e.g., `u_{ip_name}`).
- [ ] `logic` types only — no `reg`/`wire`.
- [ ] Parameters documented with `// PARAM:` comments.
- [ ] Lint passes (Verible + slang) on generated wrapper.
- [ ] Wrapper path reported: `rtl/ip_wrappers/{ip_name}_wrapper.sv`.
</Final_Checklist>
