---
name: uarch-design
description: Phase 3a skill. Produces microarchitecture documents including FSM, pipeline, and register maps.
---

<Purpose>
Translate the system architecture into implementable microarchitecture specifications.
Outputs: uarch/*.md files covering FSM diagrams, pipeline stages, register maps, memory organization.
Runs in parallel with bfm-develop during Phase 3.
</Purpose>

<Use_When>
- Phase 2 artifacts (architecture.md, block_diagram) are complete
- Microarchitecture needs to be specified before RTL coding
- Timing or pipeline details need expert review
</Use_When>

<Do_Not_Use_When>
- Phase 2 artifacts are missing (run arch-design first)
- Only RTL-level fixes needed (use rtl-refactor instead)
</Do_Not_Use_When>

<Why_This_Exists>
Architecture describes what blocks exist; microarchitecture describes how each block works internally.
Without explicit FSM and pipeline specs, RTL coders make inconsistent implementation choices.
timing-advisor ensures designs are achievable at the target frequency.
</Why_This_Exists>

<Execution_Policy>
- uarch-designer drives the document set
- codec-architecture-expert provides algorithm-specific micro-decisions
- timing-advisor reviews for frequency feasibility
- One review round from timing-advisor required before gate passes
</Execution_Policy>

<Steps>
1. Read architecture.md and block_diagram
2. uarch-designer produces per-block uarch/*.md: FSM, pipeline diagram, register map, memory map
   - **Signal naming conventions (MANDATORY — these flow directly to RTL):**
     - Inputs: `i_` prefix, Outputs: `o_` prefix, Bidirectional: `io_` prefix (NOT suffix `_i`/`_o`)
     - Clocks: `{domain}_clk` (e.g., `sys_clk`, `pixel_clk`) — NOT `clk_i`, `clk`, `clk_sys`
     - Resets: `{domain}_rst_n` (e.g., `sys_rst_n`) — NOT `rst_ni`, `rst_n`
     - Instances: `u_` prefix (e.g., `u_fifo`), generates: `gen_` prefix (e.g., `gen_stage`)
     - FSM states: `typedef enum logic [N:0]` with `UPPER_SNAKE_CASE` values
     - Types: `snake_case_t` suffix (e.g., `state_t`, `bus_req_t`)
     - Parameters: `UPPER_SNAKE_CASE` (e.g., `DATA_WIDTH`)
   - Use `logic` only in all signal declarations (no `reg`/`wire`)
3. codec-architecture-expert reviews algorithm alignment (no spec violations)
4. timing-advisor reviews critical paths and pipeline balance
5. Verify all signal names in uarch/*.md comply with naming conventions
6. Resolve review comments, finalize uarch/*.md
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:uarch-designer",
     prompt="Produce microarchitecture docs at uarch/ from architecture.md. Include FSM, pipeline, register map per block. All signal names MUST use: i_/o_/io_ prefix (NOT _i/_o suffix), {domain}_clk (e.g. sys_clk), {domain}_rst_n (e.g. sys_rst_n), u_ instance prefix, gen_ generate prefix, UPPER_SNAKE_CASE params, typedef enum for FSM states.")

Task(subagent_type="rtl-agent-team:timing-advisor",
     prompt="Review uarch/*.md for critical path issues at target frequency 500MHz. Flag pipeline imbalance. Also verify signal naming conventions: i_/o_ prefix, {domain}_clk/{domain}_rst_n.")
```
</Tool_Usage>

<Examples>
<Good>
uarch-designer produces 8 uarch/*.md files; timing-advisor flags 3-cycle combinational path in entropy coder;
uarch-designer adds pipeline register, updates FSM accordingly.
</Good>
<Bad>
Skipping timing-advisor review — RTL coder implements the design, synthesis fails timing by 40%, full RTL rework required.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Timing infeasibility at target frequency (expert says unachievable) → report to user, propose alternative frequency or architecture change
- FSM cannot represent required algorithm state → escalate to arch-design for block decomposition change
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] uarch/*.md exists for each block in architecture.md
- [ ] Each doc has FSM, pipeline diagram, register map
- [ ] timing-advisor review complete with no blockers
- [ ] codec-architecture-expert approved algorithm correctness
- [ ] All port names use `i_`/`o_`/`io_` prefix (NOT `_i`/`_o` suffix)
- [ ] All clocks named `{domain}_clk` (e.g., `sys_clk`) — no bare `clk`
- [ ] All resets named `{domain}_rst_n` (e.g., `sys_rst_n`) — no bare `rst_n`
- [ ] Instance names use `u_` prefix, generate blocks use `gen_` prefix
- [ ] FSM states defined as `typedef enum logic [N:0]` with `UPPER_SNAKE_CASE` values
</Final_Checklist>

<Advanced>
Register maps in uarch/*.md become the ground truth for ipxact-gen and rtl-document.
FSMs must be deterministic with explicit reset states and no deadlock conditions.

**Convention enforcement is critical here** — uarch/*.md signal names are directly copied by rtl-coder.
Wrong naming in uarch (e.g., bare `clk` instead of `sys_clk`, or suffix `data_i` instead of prefix `i_data`)
will propagate to RTL and require expensive refactoring across all modules.
</Advanced>
