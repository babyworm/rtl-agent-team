---
name: uarch-design
description: "This skill should be used when creating microarchitecture specs (FSM, pipeline, register maps) in Phase 3. Produces uarch/*.md with pipeline diagrams."
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
2. `mkdir -p reviews/phase-3-uarch`
3. uarch-designer produces per-block uarch/*.md: FSM, pipeline diagram, register map, memory map
   - **Signal naming conventions (MANDATORY — these flow directly to RTL):**
     - Inputs: `i_` prefix, Outputs: `o_` prefix, Bidirectional: `io_` prefix (NOT suffix `_i`/`_o`)
     - Clocks: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
     - Resets: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
     - Instances: `u_` prefix (e.g., `u_fifo`), generates: `gen_` prefix (e.g., `gen_stage`)
     - FSM states: `typedef enum logic [N:0]` with `UPPER_SNAKE_CASE` values
     - Types: `snake_case_t` suffix (e.g., `state_t`, `bus_req_t`)
     - Parameters: `UPPER_SNAKE_CASE` (e.g., `DATA_WIDTH`)
   - Use `logic` only in all signal declarations (no `reg`/`wire`)
4. **Hierarchical Spec Compliance Check — architecture.md preservation verification:**
   - rtl-architect reads architecture.md and all uarch/*.md files
   - Verify that every block defined in architecture.md has a corresponding uarch/*.md
   - Verify that block boundaries from architecture.md are preserved (no unauthorized merges or splits)
   - Verify that all functional responsibilities assigned in architecture.md are present in the uarch specs
   - **Save Feature Preservation Checklist to `reviews/phase-3-uarch/feature-preservation.md`** in standard review Markdown format:
     ```markdown
     # Phase 3 Review: Feature Preservation
     - Date: YYYY-MM-DD
     - Reviewer: rtl-architect
     - Upper Spec: architecture.md
     - Verdict: PASS | FAIL

     ## Feature Coverage Checklist
     | Feature | Architecture Block | μArch Doc | Status |
     |---------|-------------------|-----------|--------|

     ## Findings
     ### [severity] Finding-N: ...

     ## Verdict
     PASS | FAIL: [reason]
     ```
   - Output verdict:
     ```
     VERDICT: PASS — all architecture blocks and functions preserved in μArch
     ```
     or:
     ```
     VERDICT: FAIL — [N] violations found
       - block_X: missing uarch spec
       - block_Y: function "Z" from architecture.md not found in uarch
       - block_A merged into block_B: unauthorized boundary change
     ```
   - On FAIL with missing function: uarch-designer revises to include the missing functionality
   - On FAIL with boundary change: **escalate — may require Phase 2 (arch-design) revision**
   - **Save full μArch review to `reviews/phase-3-uarch/uarch-review.md`** in standard review Markdown format
5. **Save Mermaid pipeline diagram to `reviews/phase-3-uarch/pipeline-diagram.md`:**
   - Generate a `graph LR` Mermaid diagram showing pipeline stages and data flow
   - Example format:
     ```mermaid
     graph LR
         IF[Fetch] --> ID[Decode] --> EX[Execute] --> WB[Writeback]
     ```
6. codec-architecture-expert reviews algorithm alignment (no spec violations)
7. timing-advisor reviews critical paths and pipeline balance
8. Verify all signal names in uarch/*.md comply with naming conventions
9. Resolve review comments, finalize uarch/*.md
</Steps>

<Tool_Usage>
```
Bash("mkdir -p reviews/phase-3-uarch")

Task(subagent_type="rtl-agent-team:uarch-designer",
     prompt="Produce microarchitecture docs at uarch/ from architecture.md. Include FSM, pipeline, register map per block. All signal names MUST use: i_/o_/io_ prefix (NOT _i/_o suffix), {domain}_clk (e.g. sys_clk), {domain}_rst_n (e.g. sys_rst_n), u_ instance prefix, gen_ generate prefix, UPPER_SNAKE_CASE params, typedef enum for FSM states.")

Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Read architecture.md and all uarch/*.md files. Verify: (1) every block in architecture.md has a corresponding uarch/*.md, (2) block boundaries are preserved — no unauthorized merges or splits, (3) all functional responsibilities from architecture.md are present in uarch specs. Save the Feature Preservation Checklist to reviews/phase-3-uarch/feature-preservation.md in standard review Markdown format with Date, Reviewer (rtl-architect), Upper Spec (architecture.md), Verdict, checklist table, Findings, and Verdict sections. Save the full μArch review to reviews/phase-3-uarch/uarch-review.md in standard review Markdown format. Also save a Mermaid pipeline diagram to reviews/phase-3-uarch/pipeline-diagram.md showing pipeline stages and data flow (graph LR with stage names and connections). Output VERDICT: PASS or VERDICT: FAIL with specific violations. If boundary changes are found, flag as 'requires Phase 2 revision'.")

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
- **Block boundary violation detected** (merge/split not in architecture.md) → escalate to Phase 2 (arch-design) for architecture revision before continuing
- **Functional responsibility missing** from uarch that exists in architecture.md → uarch-designer must add it, or escalate if architecture change is needed
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] uarch/*.md exists for each block in architecture.md
- [ ] **All block boundaries from architecture.md preserved (no unauthorized merges/splits)**
- [ ] **All functional responsibilities from architecture.md present in uarch specs**
- [ ] rtl-architect hierarchical spec compliance verdict is PASS
- [ ] Each doc has FSM, pipeline diagram, register map
- [ ] timing-advisor review complete with no blockers
- [ ] codec-architecture-expert approved algorithm correctness
- [ ] All port names use `i_`/`o_`/`io_` prefix (NOT `_i`/`_o` suffix)
- [ ] All clocks named `{domain}_clk` (e.g., `sys_clk`) — bare `clk` OK for single domain, `{domain}_clk` for multiple domains. NOT `clk_i`
- [ ] All resets named `{domain}_rst_n` (e.g., `sys_rst_n`) — bare `rst_n` OK for single domain, `{domain}_rst_n` for multiple domains. NOT `rst_ni`
- [ ] Instance names use `u_` prefix, generate blocks use `gen_` prefix
- [ ] FSM states defined as `typedef enum logic [N:0]` with `UPPER_SNAKE_CASE` values
- [ ] **reviews/phase-3-uarch/feature-preservation.md saved with Feature Preservation Checklist**
- [ ] **reviews/phase-3-uarch/uarch-review.md saved with full μArch review**
- [ ] **reviews/phase-3-uarch/pipeline-diagram.md saved with Mermaid pipeline diagram**
</Final_Checklist>

<Advanced>
Register maps in uarch/*.md become the ground truth for ipxact-gen and rtl-document.
FSMs must be deterministic with explicit reset states and no deadlock conditions.

**Convention enforcement is critical here** — uarch/*.md signal names are directly copied by rtl-coder.
Wrong naming in uarch (e.g., `clk_i` instead of `clk`/`sys_clk`, or suffix `data_i` instead of prefix `i_data`)
will propagate to RTL and require expensive refactoring across all modules.
</Advanced>
