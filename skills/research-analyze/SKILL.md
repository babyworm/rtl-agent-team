---
name: research-analyze
description: Phase 1 skill. Extracts requirements, I/O definitions, and domain analysis from specification documents.
---

<Purpose>
Transform raw specification documents into structured artifacts that downstream phases can consume.
Produces three mandatory outputs: requirements.json, io_definition.json, domain-analysis.md.
</Purpose>

<Use_When>
- Starting Phase 1 of the RTL pipeline
- Specification has changed and artifacts need regeneration
- Domain knowledge gap exists before architecture decisions
</Use_When>

<Do_Not_Use_When>
- Artifacts already exist and spec has not changed
- Only a quick domain question needs answering (use domain-consult instead)
</Do_Not_Use_When>

<Why_This_Exists>
Codec specifications are dense and cross-referenced. Multiple domain experts must reconcile
their interpretations before a unified requirements set can drive architecture.
Separating this from arch-design prevents spec ambiguity from corrupting structural decisions.
</Why_This_Exists>

<Execution_Policy>
- Run codec-standards-expert, video-processing-expert, spec-analyst in parallel
- Merge outputs into unified artifacts
- Validate JSON schemas before declaring gate passed
</Execution_Policy>

<Steps>
1. Parallel: delegate to codec-standards-expert (standard compliance requirements), video-processing-expert (signal processing requirements), spec-analyst (formal requirement extraction)
2. Merge results into requirements.json (all functional + non-functional requirements)
3. Produce io_definition.json (all input/output ports with widths, rates, protocols)
   - **Port naming convention (MANDATORY):**
     - Inputs: `i_` prefix (e.g., `i_data`, `i_valid`) — NOT suffix `_i`
     - Outputs: `o_` prefix (e.g., `o_result`, `o_ready`) — NOT suffix `_o`
     - Bidirectional: `io_` prefix (e.g., `io_sda`)
     - Clocks: `{domain}_clk` (e.g., `sys_clk`, `pixel_clk`) — NOT `clk_i`, `clk`, `clk_sys`
     - Resets: `{domain}_rst_n` (e.g., `sys_rst_n`, `pixel_rst_n`) — NOT `rst_ni`, `rst_n`
   - Single clock domain defaults to `sys_clk` / `sys_rst_n`
4. Produce domain-analysis.md (algorithm overview, known implementation challenges, references)
5. Validate all three files exist and JSON is well-formed
6. Validate io_definition.json port names comply with naming conventions above
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:codec-standards-expert",
     prompt="Extract compliance requirements from spec at specs/. Output structured list.")

Task(subagent_type="rtl-agent-team:video-processing-expert",
     prompt="Extract signal processing and datapath requirements from specs/.")

Task(subagent_type="rtl-agent-team:spec-analyst",
     prompt="Parse specs/ and produce requirements.json and io_definition.json. Port names in io_definition.json MUST use: i_/o_/io_ prefix (NOT suffix _i/_o), clocks as {domain}_clk (e.g. sys_clk), resets as {domain}_rst_n (e.g. sys_rst_n).")
```
</Tool_Usage>

<Examples>
<Good>
Input: H.264 spec PDF + system constraints doc
Output: requirements.json with 47 functional requirements, io_definition.json with all AXI ports (using i_/o_ prefix, sys_clk/sys_rst_n naming), domain-analysis.md with CABAC algorithm notes.
Example io_definition.json port: `{"name": "i_axi_awaddr", "direction": "input", "width": 32, "protocol": "AXI4-Lite"}`
</Good>
<Bad>
Skipping spec-analyst and writing requirements.json manually — misses formal traceability.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Spec document not found → report to user, halt
- Conflicting requirements between experts → flag conflict in domain-analysis.md, ask user to resolve
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] requirements.json exists and is valid JSON
- [ ] io_definition.json exists and is valid JSON
- [ ] io_definition.json port names use `i_`/`o_`/`io_` prefix (NOT suffix `_i`/`_o`)
- [ ] io_definition.json clocks use `{domain}_clk` (e.g., `sys_clk`) — no bare `clk`
- [ ] io_definition.json resets use `{domain}_rst_n` (e.g., `sys_rst_n`) — no bare `rst_n`
- [ ] domain-analysis.md exists
- [ ] No unresolved requirement conflicts
</Final_Checklist>

<Advanced>
If spec is in multiple formats (PDF + XML + prose), run separate extraction per format then merge.
Traceability: each requirement in requirements.json must have a spec section reference.
</Advanced>
