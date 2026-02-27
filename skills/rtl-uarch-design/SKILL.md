---
name: rtl-uarch-design
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
- vcodec-architecture-expert provides algorithm-specific micro-decisions
- timing-advisor reviews for frequency feasibility
- **Cascading Quality: 3-round mandatory iterative review per module (user-adjustable)**
  - rtl-architect coordinates review rounds as aggregator
  - 4 parallel reviewers each round: rtl-architect (feature preservation + block boundary + interface), timing-advisor (critical paths at target frequency), vcodec-architecture-expert (algorithm/memory/interface optimization), ref-model-dev (model consistency — behavior, data widths, fixed-point)
  - Each round focuses on: performance, interface, memory access optimization per module
  - Round 3 is mandatory even if earlier rounds converged (final quality pass)
  - After 3 rounds: escalate remaining issues to user via AskUserQuestion if not converged
  - User may request additional rounds beyond 3
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
4. **Parallel initial review** (4 reviewers in parallel, after uarch-designer draft ready):
   - a. `rtl-architect`: Feature Preservation Checklist (every architecture block has uarch doc, block boundaries preserved, all functional responsibilities present) + interface correctness
   - b. `timing-advisor`: Critical path analysis at target frequency, pipeline balance, register placement feasibility
   - c. `vcodec-architecture-expert`: Algorithm ↔ μArch consistency, memory access optimization (SRAM banking, port conflicts, access scheduling), interface optimization (handshake, backpressure)
   - d. `ref-model-dev`: Model consistency check (behavioral match, data widths, fixed-point formats, rounding modes)
5. **Review Round 1** — rtl-architect as coordinator aggregates findings from all 4 reviewers:
   - Feature preservation (all architecture features present in uarch?)
   - Performance (pipeline depth, critical paths, throughput at target frequency)
   - Memory optimization (SRAM banking adequate? port conflicts? access scheduling?)
   - Interface optimization (handshake protocols, backpressure mechanisms)
   - Model consistency (uarch behavior matches ref model?)
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
   - **Save to `reviews/phase-3-uarch/uarch-review-r1.md`** in standard review Markdown format
   - On FAIL with boundary change: **escalate — may require Phase 2 (arch-design) revision**
6. **Targeted revision Round 1→2** — re-delegate ONLY to experts/modules with feedback:
   - uarch-designer revises specific uarch/*.md files for feature/structure issues
   - Experts without findings are NOT re-invoked
7. **Review Round 2** — same 4 reviewers in parallel, coordinator assesses convergence:
   - Focus on: were Round 1 issues resolved? Any new issues introduced by revisions?
   - **Save to `reviews/phase-3-uarch/uarch-review-r2.md`** in standard review Markdown format
8. **Targeted revision Round 2→3** — re-delegate ONLY to experts with remaining findings (skip if Round 2 fully converged)
9. **Review Round 3** (mandatory even if converged) — final quality pass:
   - Cross-module interface completeness and protocol consistency
   - Memory access conflict analysis across all modules (concurrent access patterns)
   - Complete model consistency matrix (every uarch behavior ↔ ref model function)
   - Code review of μArch specs: naming, FSM completeness, no dead states
   - **Save to `reviews/phase-3-uarch/uarch-review-r3.md`** in standard review Markdown format
   - If still not converged → escalate to user via AskUserQuestion with specific unresolved items
10. **Finalize**:
    - Save final `reviews/phase-3-uarch/uarch-review.md` (consolidated from r1-r3)
    - **Save Mermaid pipeline diagram to `reviews/phase-3-uarch/pipeline-diagram.md`:**
      - Generate a `graph LR` Mermaid diagram showing pipeline stages and data flow
      - Example format:
        ```mermaid
        graph LR
            IF[Fetch] --> ID[Decode] --> EX[Execute] --> WB[Writeback]
        ```
    - Verify all signal names in uarch/*.md comply with naming conventions
</Steps>

<Tool_Usage>
```
Bash("mkdir -p reviews/phase-3-uarch")

# --- Step 3: uarch-designer draft ---
Task(subagent_type="rtl-agent-team:uarch-designer",
     prompt="Produce microarchitecture docs at uarch/ from architecture.md. Include FSM, pipeline, register map per block. All signal names MUST use: i_/o_/io_ prefix (NOT _i/_o suffix), {domain}_clk (e.g. sys_clk), {domain}_rst_n (e.g. sys_rst_n), u_ instance prefix, gen_ generate prefix, UPPER_SNAKE_CASE params, typedef enum for FSM states.")

# --- Step 4: Parallel initial review (4 reviewers) ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Review Round 1: Read architecture.md and all uarch/*.md. Verify block boundary alignment (1:1 correspondence), feature preservation (all architecture features present), interface correctness. Save Feature Preservation Checklist to reviews/phase-3-uarch/feature-preservation.md in standard review Markdown format.")

Task(subagent_type="rtl-agent-team:timing-advisor",
     prompt="Review Round 1: Review uarch/*.md for critical path issues at target frequency. Flag pipeline imbalance, register placement feasibility, combinational paths that violate timing.")

Task(subagent_type="rtl-agent-team:vcodec-architecture-expert",
     prompt="Review Round 1: Read uarch/*.md. Verify algorithm ↔ μArch consistency. Analyze memory access optimization: SRAM banking, port conflicts, access scheduling. Review interface optimization: handshake protocols, backpressure mechanisms.")

Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Review Round 1: Read uarch/*.md and ref_model/src/. Check model consistency: behavioral match between uarch specs and C++ ref model, data widths, fixed-point formats, rounding modes.")

# --- Step 5: Coordinator aggregates Round 1 findings ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Aggregate Round 1 findings from all 4 reviewers. Consolidate: feature preservation, performance, memory optimization, interface optimization, model consistency. Save to reviews/phase-3-uarch/uarch-review-r1.md. Output targeted feedback for each expert/module that needs revision.")

# --- Step 6: Targeted revision Round 1→2 ---
Task(subagent_type="rtl-agent-team:uarch-designer",
     prompt="Revise specific uarch/*.md files to address Round 1 findings: [paste targeted feedback]. Only modify files with identified issues.")

# --- Step 7: Review Round 2 (4 reviewers in parallel) ---
# Same pattern as Round 1 — save to reviews/phase-3-uarch/uarch-review-r2.md

# --- Step 8: Targeted revision Round 2→3 (skip if converged) ---

# --- Step 9: Review Round 3 (mandatory final quality pass) ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Review Round 3 (mandatory final pass): Cross-module interface completeness and protocol consistency. Save to reviews/phase-3-uarch/uarch-review-r3.md.")

Task(subagent_type="rtl-agent-team:timing-advisor",
     prompt="Review Round 3 (mandatory final pass): Final critical path analysis across all modules. Verify pipeline balance is achievable at target frequency.")

Task(subagent_type="rtl-agent-team:vcodec-architecture-expert",
     prompt="Review Round 3 (mandatory final pass): Memory access conflict analysis across all modules. Verify concurrent access patterns are conflict-free.")

Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Review Round 3 (mandatory final pass): Complete model consistency matrix (every uarch behavior ↔ ref model function). Code review of μArch specs: naming, FSM completeness, no dead states.")

# --- Step 10: Finalize ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Finalize: Consolidate r1, r2, r3 reviews into reviews/phase-3-uarch/uarch-review.md. Save Mermaid pipeline diagram to reviews/phase-3-uarch/pipeline-diagram.md (graph LR). Output final verdict: VERDICT: PASS or VERDICT: FAIL.")

# On escalation (Round 3 not converged): use AskUserQuestion with unresolved items
# On boundary violation: escalate to Phase 2 (arch-design) for revision
```
</Tool_Usage>

<Examples>
<Good>
3-round iterative convergence:
→ Round 1: rtl-architect flags missing feature in transform block uarch, timing-advisor finds
  3-cycle combinational path in entropy coder, vcodec-architecture-expert identifies SRAM port
  conflict in prediction block, ref-model-dev finds fixed-point rounding mismatch.
→ Targeted revision: uarch-designer adds missing feature, inserts pipeline register, fixes SRAM
  banking; ref-model-dev aligns rounding modes.
→ Round 2: All Round 1 issues resolved; timing-advisor identifies new critical path from revision.
→ Targeted revision: uarch-designer rebalances pipeline stages.
→ Round 3 (mandatory): Cross-module interface audit PASS; memory conflict analysis PASS;
  model consistency matrix complete; μArch code review clean.
→ Final verdict: PASS. All 3 round artifacts saved (r1, r2, r3).
</Good>
<Good>
uarch-designer produces 8 uarch/*.md files; timing-advisor flags 3-cycle combinational path in entropy coder;
uarch-designer adds pipeline register, updates FSM accordingly.
</Good>
<Bad>
Skipping timing-advisor review — RTL coder implements the design, synthesis fails timing by 40%, full RTL rework required.
</Bad>
<Bad>
Running only 1 review round for μArch — SRAM port conflict not caught until Phase 5 verification,
requiring μArch redesign and full RTL rewrite. Cascading Quality Principle violated.
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
- [ ] **3-round iterative review completed** (or remaining gaps escalated to user and approved)
- [ ] **Memory access patterns optimized** for all modules (SRAM banking, port conflicts, access scheduling)
- [ ] **Cross-module interfaces reviewed** for protocol consistency and completeness
- [ ] **μArch ↔ ref model consistency verified** (behavior, data widths, fixed-point formats, rounding modes)
- [ ] **μArch code review passed** (naming, FSM completeness, no dead states)
- [ ] rtl-architect hierarchical spec compliance verdict is PASS
- [ ] Each doc has FSM, pipeline diagram, register map
- [ ] timing-advisor review complete with no blockers
- [ ] vcodec-architecture-expert approved algorithm correctness
- [ ] All port names use `i_`/`o_`/`io_` prefix (NOT `_i`/`_o` suffix)
- [ ] All clocks named `{domain}_clk` (e.g., `sys_clk`) — bare `clk` OK for single domain, `{domain}_clk` for multiple domains. NOT `clk_i`
- [ ] All resets named `{domain}_rst_n` (e.g., `sys_rst_n`) — bare `rst_n` OK for single domain, `{domain}_rst_n` for multiple domains. NOT `rst_ni`
- [ ] Instance names use `u_` prefix, generate blocks use `gen_` prefix
- [ ] FSM states defined as `typedef enum logic [N:0]` with `UPPER_SNAKE_CASE` values
- [ ] **Per-round review artifacts saved:**
  - [ ] reviews/phase-3-uarch/uarch-review-r1.md
  - [ ] reviews/phase-3-uarch/uarch-review-r2.md
  - [ ] reviews/phase-3-uarch/uarch-review-r3.md
- [ ] **reviews/phase-3-uarch/feature-preservation.md saved with Feature Preservation Checklist**
- [ ] **reviews/phase-3-uarch/uarch-review.md saved with consolidated final μArch review**
- [ ] **reviews/phase-3-uarch/pipeline-diagram.md saved with Mermaid pipeline diagram**
</Final_Checklist>

<Advanced>
Register maps in uarch/*.md become the ground truth for rtl-ipxact-gen and rtl-document.
FSMs must be deterministic with explicit reset states and no deadlock conditions.

**Convention enforcement is critical here** — uarch/*.md signal names are directly copied by rtl-coder.
Wrong naming in uarch (e.g., `clk_i` instead of `clk`/`sys_clk`, or suffix `data_i` instead of prefix `i_data`)
will propagate to RTL and require expensive refactoring across all modules.
</Advanced>
