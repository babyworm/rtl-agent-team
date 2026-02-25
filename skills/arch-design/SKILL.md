---
name: arch-design
description: Phase 2a skill. Produces system architecture and block diagram from requirements.
---

<Purpose>
Translate requirements.json and io_definition.json into a concrete system architecture.
Outputs architecture.md (block descriptions, interfaces, data flow) and block_diagram (ASCII or Mermaid).
Runs in parallel with ref-model during Phase 2.
</Purpose>

<Use_When>
- Phase 1 artifacts (requirements.json, io_definition.json) are complete
- Architecture needs to be designed or revised
- Block-level decomposition is needed before uarch work begins
</Use_When>

<Do_Not_Use_When>
- Phase 1 artifacts do not exist (run research-analyze first)
- Only reviewing existing architecture (use arch-review instead)
</Do_Not_Use_When>

<Why_This_Exists>
Architecture decisions (block partitioning, interface protocols, pipeline depth) must be made
before RTL coding begins. Mistakes here cascade through all downstream phases.
Dedicated domain experts catch codec-specific pitfalls early.
</Why_This_Exists>

<Execution_Policy>
- Parallel: codec-standards-expert + video-processing-expert provide domain constraints
- arch-designer produces the architecture document
- rtl-architect performs review before gate passes
- Review comments must be addressed before gate clears
</Execution_Policy>

<Steps>
1. Read requirements.json and io_definition.json
2. Parallel: codec-standards-expert (interface standard compliance), video-processing-expert (pipeline and memory constraints)
3. arch-designer produces architecture.md draft and block_diagram
   - All interface signal names MUST follow naming conventions:
     - Inputs: `i_` prefix, Outputs: `o_` prefix, Bidirectional: `io_` prefix (NOT suffix `_i`/`_o`)
     - Clocks: `{domain}_clk` (e.g., `sys_clk`, `pixel_clk`) — NOT `clk_i`, `clk`, `clk_sys`
     - Resets: `{domain}_rst_n` (e.g., `sys_rst_n`) — NOT `rst_ni`, `rst_n`
     - Instances: `u_` prefix (e.g., `u_input_buffer`), generates: `gen_` prefix
   - Block names: `snake_case` (these become RTL module names)
4. rtl-architect reviews for RTL implementability, timing feasibility, interface consistency, and naming convention compliance
5. Iterate on review comments (max 2 rounds)
6. Finalize architecture.md and block_diagram
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:arch-designer",
     prompt="Design system architecture from requirements.json and io_definition.json. Produce architecture.md and block_diagram. All interface signals must use i_/o_/io_ prefix (NOT _i/_o suffix), clocks as {domain}_clk (e.g. sys_clk), resets as {domain}_rst_n. Instance names use u_ prefix.")

Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Review architecture.md for RTL implementability, timing, interface consistency, and naming convention compliance (i_/o_ prefix, {domain}_clk/{domain}_rst_n). List issues.")
```
</Tool_Usage>

<Examples>
<Good>
arch-designer proposes 4-stage pipeline; rtl-architect flags critical path in stage 3;
arch-designer revises to 5-stage with register between stages 3-4.
</Good>
<Bad>
Skipping rtl-architect review and passing architecture directly to uarch-design — misses
timing-critical issues that are expensive to fix at RTL stage.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Review round limit (2) exceeded with unresolved issues → escalate to user with issue list
- Domain constraint conflict between experts → document conflict, ask user for priority
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] architecture.md exists with all blocks described
- [ ] block_diagram exists
- [ ] rtl-architect review completed with no blockers
- [ ] All interfaces consistent with io_definition.json
- [ ] All signal names use `i_`/`o_`/`io_` prefix (NOT `_i`/`_o` suffix)
- [ ] All clocks named `{domain}_clk` (e.g., `sys_clk`) — no bare `clk`
- [ ] All resets named `{domain}_rst_n` (e.g., `sys_rst_n`) — no bare `rst_n`
- [ ] Instance names use `u_` prefix, generate blocks use `gen_` prefix
</Final_Checklist>

<Advanced>
architecture.md should include: block list, per-block responsibility, inter-block interfaces (protocol, width, handshake), clock domains, reset strategy.

Naming convention enforcement in architecture.md:
- Interface table signal names: `i_blockname_signal`, `o_blockname_signal` (prefix, not suffix)
- Clock columns: `sys_clk`, `pixel_clk`, etc. (NOT `clk`, `clk_i`, `clk_sys`)
- Reset columns: `sys_rst_n`, `pixel_rst_n` (NOT `rst_n`, `rst_ni`)
- Block instance names when referenced: `u_block_name` prefix
- These names flow directly to uarch-design and rtl-code — errors here cascade downstream
</Advanced>
