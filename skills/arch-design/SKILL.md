---
name: arch-design
description: "This skill should be used when designing system architecture from requirements in Phase 2. Produces architecture.md with block diagrams and Feature Coverage Checklist."
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
- Parallel: codec sub-domain experts (vcodec-syntax-entropy, vcodec-prediction, vcodec-transform-quant, vcodec-filter-recon) + video-processing-expert provide domain constraints, coordinated by vcodec-chief-standard-expert
- arch-designer produces the architecture document
- ref-model-dev produces the C++ reference model concurrently with arch-designer
- **Cascading Quality: 3-round mandatory iterative review (user-adjustable)**
  - rtl-architect coordinates review rounds as aggregator
  - 3 parallel reviewers each round: rtl-architect (spec compliance + structure), vcodec-architecture-expert (memory access + performance), ref-model-dev (architecture ↔ C model consistency)
  - Each round: parallel review → coordinator aggregates → targeted feedback → revision by specific experts only
  - Round 3 is mandatory even if earlier rounds converged (final quality pass)
  - After 3 rounds: escalate remaining issues to user via AskUserQuestion if not converged
  - User may request additional rounds beyond 3 ("set iterations to N")
</Execution_Policy>

<Steps>
1. Read requirements.json and io_definition.json
2. `mkdir -p reviews/phase-2-architecture`
3. Parallel: vcodec-chief-standard-expert (cross-block interface compliance and domain constraints from sub-domain experts), video-processing-expert (pipeline and memory constraints)
4. arch-designer produces architecture.md draft and block_diagram
   - All interface signal names MUST follow naming conventions:
     - Inputs: `i_` prefix, Outputs: `o_` prefix, Bidirectional: `io_` prefix (NOT suffix `_i`/`_o`)
     - Clocks: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
     - Resets: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
     - Instances: `u_` prefix (e.g., `u_input_buffer`), generates: `gen_` prefix
   - Block names: `snake_case` (these become RTL module names)
   - architecture.md MUST include a Mermaid block diagram section showing top-level block decomposition
5. **Parallel initial review** (3 reviewers in parallel, after arch-designer draft + ref-model ready):
   - a. `rtl-architect`: Spec compliance (Feature Coverage Checklist — every REQ-NNN mapped?) + structural review (block decomposition, interface adequacy)
   - b. `vcodec-architecture-expert`: Memory access pattern analysis for large blocks (SRAM/register file sizing, bandwidth requirements, access conflicts, DMA burst patterns, line buffer organization, shared memory arbitration)
   - c. `ref-model-dev`: Architecture-to-model consistency check (block ↔ ref_model module mapping, data flow order, interface widths/formats)
6. **Review Round 1** — rtl-architect as coordinator aggregates findings from all 3 reviewers:
   - Functional completeness (all REQ-NNN covered?)
   - Memory access (SRAM sizes adequate? bandwidth bottlenecks?)
   - Performance (pipeline depth, throughput, latency vs spec targets)
   - Ref model consistency (architecture ↔ C model alignment)
   - Interface correctness (port names, widths, protocols)
   - **Save to `reviews/phase-2-architecture/architecture-review-r1.md`** in standard review Markdown format
7. **Targeted revision Round 1→2** — re-delegate ONLY to experts whose review found issues:
   - arch-designer revises architecture.md for spec/structure issues
   - ref-model-dev revises ref_model for consistency issues
   - Experts without findings are NOT re-invoked
8. **Review Round 2** — same 3 reviewers in parallel, coordinator assesses convergence:
   - Focus on: were Round 1 issues resolved? Any new issues introduced by revisions?
   - **Save to `reviews/phase-2-architecture/architecture-review-r2.md`** in standard review Markdown format
9. **Targeted revision Round 2→3** — re-delegate ONLY to experts with remaining findings (skip if Round 2 fully converged)
10. **Review Round 3** (mandatory even if converged) — final quality pass:
    - Cross-block interface completeness (all data paths connected, no orphan ports)
    - Memory access conflict analysis (concurrent read/write patterns across blocks)
    - Ref model code review: code quality, bitexact correctness, test coverage
    - Architecture-to-model complete consistency matrix (every arch block ↔ ref model module)
    - **Save to `reviews/phase-2-architecture/architecture-review-r3.md`** in standard review Markdown format
    - If still not converged → escalate to user via AskUserQuestion with specific unresolved items
11. **Finalize**:
    - Save final `reviews/phase-2-architecture/architecture-review.md` (consolidated from r1-r3)
    - Save `reviews/phase-2-architecture/feature-coverage.md` (final Feature Coverage Checklist)
    - **Save Mermaid block diagram to `reviews/phase-2-architecture/architecture-diagram.md`:**
      - Extract or generate a `graph TD` Mermaid diagram from architecture.md block decomposition
      - Example format:
        ```mermaid
        graph TD
            A[Top Module] --> B[Datapath]
            A --> C[Controller FSM]
            B --> D[ALU]
            B --> E[Register File]
            C --> F[AXI Slave Interface]
        ```
</Steps>

<Tool_Usage>
```
Bash("mkdir -p reviews/phase-2-architecture")

# --- Step 3-4: Domain experts + arch-designer draft + ref-model (parallel) ---
Task(subagent_type="rtl-agent-team:arch-designer",
     prompt="Design system architecture from requirements.json and io_definition.json. Produce architecture.md and block_diagram. All interface signals must use i_/o_/io_ prefix (NOT _i/_o suffix), clocks as {domain}_clk (e.g. sys_clk), resets as {domain}_rst_n. Instance names use u_ prefix. Include a Mermaid block diagram (graph TD) in architecture.md showing top-level block decomposition and connectivity.")

# --- Step 5: Parallel initial review (3 reviewers) ---
# After arch-designer draft + ref-model are ready, launch 3 reviewers in parallel:
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Review Round 1: Read requirements.json and architecture.md. Verify every REQ-NNN is mapped to at least one architecture block. Review for RTL implementability, timing feasibility, interface consistency, and naming convention compliance (i_/o_ prefix, {domain}_clk/{domain}_rst_n). Output Feature Coverage Checklist with per-REQ status.")

Task(subagent_type="rtl-agent-team:vcodec-architecture-expert",
     prompt="Review Round 1: Read architecture.md. Analyze memory access patterns for all large blocks: SRAM/register file sizing, bandwidth requirements, access conflicts, DMA burst patterns, line buffer organization, shared memory arbitration. Identify performance bottlenecks (pipeline depth, throughput, latency vs spec targets).")

Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Review Round 1: Read architecture.md and ref_model/src/. Check architecture-to-model consistency: block ↔ ref_model module mapping, data flow order, interface widths/formats. Identify any misalignment between architecture blocks and C++ model structure.")

# --- Step 6: Coordinator aggregates Round 1 findings ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Aggregate Round 1 findings from all 3 reviewers (rtl-architect, vcodec-architecture-expert, ref-model-dev). Consolidate: functional completeness, memory access, performance, ref model consistency, interface correctness. Save consolidated review to reviews/phase-2-architecture/architecture-review-r1.md in standard review Markdown format. Output targeted feedback for each expert that needs to revise.")

# --- Step 7: Targeted revision Round 1→2 (only experts with findings) ---
Task(subagent_type="rtl-agent-team:arch-designer",
     prompt="Revise architecture.md to address Round 1 findings: [paste targeted feedback]. Only address specific issues flagged by reviewers.")

# --- Step 8: Review Round 2 (3 reviewers in parallel) ---
# Same pattern as Round 1 — re-run all 3 reviewers
# Save to reviews/phase-2-architecture/architecture-review-r2.md

# --- Step 9: Targeted revision Round 2→3 (skip if converged) ---

# --- Step 10: Review Round 3 (mandatory final quality pass) ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Review Round 3 (mandatory final pass): Cross-block interface completeness, memory access conflict analysis (concurrent read/write patterns). Save to reviews/phase-2-architecture/architecture-review-r3.md.")

Task(subagent_type="rtl-agent-team:vcodec-architecture-expert",
     prompt="Review Round 3 (mandatory final pass): Verify all memory access patterns are conflict-free, shared memory arbitration is sound, bandwidth budgets are met across all blocks.")

Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Review Round 3 (mandatory final pass): Ref model code review for quality and bitexact correctness. Architecture-to-model complete consistency matrix. Verify test coverage of ref model.")

# --- Step 11: Finalize ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Finalize: Consolidate r1, r2, r3 reviews into reviews/phase-2-architecture/architecture-review.md. Save Feature Coverage Checklist to reviews/phase-2-architecture/feature-coverage.md. Save Mermaid block diagram to reviews/phase-2-architecture/architecture-diagram.md (graph TD). Output final verdict: VERDICT: PASS or VERDICT: FAIL.")

# On escalation (Round 3 not converged): use AskUserQuestion with unresolved items
```
</Tool_Usage>

<Examples>
<Good>
3-round iterative convergence:
→ Round 1: rtl-architect flags 2 unmapped REQ items, vcodec-architecture-expert identifies SRAM
  bandwidth bottleneck in transform block, ref-model-dev finds data flow mismatch in entropy path.
→ Targeted revision: arch-designer adds missing blocks + resizes SRAM; ref-model-dev fixes data flow.
→ Round 2: SRAM issue resolved; rtl-architect finds new interface width inconsistency from revision.
→ Targeted revision: arch-designer fixes interface width.
→ Round 3 (mandatory): Cross-block interface audit PASS; memory conflict analysis PASS;
  ref model code review identifies minor quality issue (documented, non-blocking).
→ Final verdict: PASS. All 3 round artifacts saved (r1, r2, r3).
</Good>
<Good>
arch-designer proposes 4-stage pipeline; rtl-architect flags critical path in stage 3;
arch-designer revises to 5-stage with register between stages 3-4.
</Good>
<Bad>
Skipping rtl-architect review and passing architecture directly to uarch-design — misses
timing-critical issues that are expensive to fix at RTL stage.
</Bad>
<Bad>
Running only 1 review round for architecture — memory access bottleneck not caught until
Phase 4 RTL coding, requiring full architecture rework. Cascading Quality Principle violated.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- 3-round iterative review completed but issues remain unresolved → escalate to user via AskUserQuestion with specific items
- Domain constraint conflict between experts → document conflict, ask user for priority
- Memory access pattern infeasible (bandwidth exceeds technology limits) → escalate to user, propose alternative architecture
- Architecture ↔ ref model fundamental mismatch (block structure incompatible) → escalate, may require ref model rewrite
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] architecture.md exists with all blocks described
- [ ] block_diagram exists
- [ ] **Every REQ-NNN in requirements.json is mapped to at least one architecture block**
- [ ] **3-round iterative review completed** (or remaining gaps escalated to user and approved)
- [ ] **Memory access patterns reviewed** for all large blocks (SRAM sizing, bandwidth, conflicts)
- [ ] **Architecture ↔ ref model consistency verified** (block mapping, data flow, interface alignment)
- [ ] **Ref model code reviewed** for quality and bitexact correctness
- [ ] rtl-architect spec compliance verdict is PASS
- [ ] rtl-architect review completed with no blockers
- [ ] All interfaces consistent with io_definition.json
- [ ] All signal names use `i_`/`o_`/`io_` prefix (NOT `_i`/`_o` suffix)
- [ ] All clocks named `{domain}_clk` (e.g., `sys_clk`) — bare `clk` OK for single domain, `{domain}_clk` for multiple domains. NOT `clk_i`
- [ ] All resets named `{domain}_rst_n` (e.g., `sys_rst_n`) — bare `rst_n` OK for single domain, `{domain}_rst_n` for multiple domains. NOT `rst_ni`
- [ ] Instance names use `u_` prefix, generate blocks use `gen_` prefix
- [ ] **Per-round review artifacts saved:**
  - [ ] reviews/phase-2-architecture/architecture-review-r1.md
  - [ ] reviews/phase-2-architecture/architecture-review-r2.md
  - [ ] reviews/phase-2-architecture/architecture-review-r3.md
- [ ] **reviews/phase-2-architecture/feature-coverage.md saved with Feature Coverage Checklist**
- [ ] **reviews/phase-2-architecture/architecture-review.md saved with consolidated final review**
- [ ] **reviews/phase-2-architecture/architecture-diagram.md saved with Mermaid block diagram**
</Final_Checklist>

<Advanced>
architecture.md should include: block list, per-block responsibility, inter-block interfaces (protocol, width, handshake), clock domains, reset strategy.

Naming convention enforcement in architecture.md:
- Interface table signal names: `i_blockname_signal`, `o_blockname_signal` (prefix, not suffix)
- Clock columns: `clk`, `sys_clk`, `pixel_clk`, etc. (NOT `clk_i`, `clk_sys`)
- Reset columns: `rst_n`, `sys_rst_n`, `pixel_rst_n` (NOT `rst_ni`)
- Block instance names when referenced: `u_block_name` prefix
- These names flow directly to uarch-design and rtl-code — errors here cascade downstream
</Advanced>
