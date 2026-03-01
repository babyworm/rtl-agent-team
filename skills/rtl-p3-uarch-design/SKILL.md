---
name: rtl-p3-uarch-design
description: "Phase 3 μArch design skill. Concretizes P2 modules into sub-blocks with clock domains, design partitioning, protocol assignment, register/SRAM/FSM allocation. Validates via TLM-based BFM (blocking LT default, AT on request) with per-block I/O logging for future RTL unit verification. Produces docs/phase-3-uarch/*.md with pipeline diagrams."
---

<Purpose>
Phase 3: Concretize P2's architecture into implementable microarchitecture specifications.
This phase takes each P2 module and designs the detailed HW implementation.

Phase 3 has six key responsibilities:

1. **Module decomposition into sub-blocks**: Break architecture-level blocks into smaller hardware
   sub-modules (e.g., `prediction` → `intra_pred`, `inter_pred`, `mv_predictor`)
2. **Clock domain assignment**: Define clock domains per sub-block, identify clock crossings,
   determine which blocks share clocks vs require separate domains
3. **Design partitioning strategy**: How to split the design for efficient implementation —
   pipeline stages, area/throughput trade-offs, resource sharing strategies
4. **Protocol assignment**: Apply efficient HW protocols to inter-block interfaces —
   valid/ready handshake, AXI-Stream, FIFO interfaces, credit-based flow control.
   Choose the most efficient protocol for each interface based on data rate and latency requirements.
5. **Register/SRAM/FSM allocation**: Properly distribute storage resources per sub-block —
   pipeline registers, configuration registers, SRAM for data buffers, FSM for control logic.
   Each resource must be justified by the data flow requirements.
6. **Signal interface concretization**: Define concrete signal names (`i_`/`o_` prefix), exact bit widths,
   FSM state encodings, register maps — these flow directly to RTL in Phase 4

**BFM-based validation (MANDATORY)**:
The μArch design must be validated through a TLM-based BFM (Bus Functional Model):
- **Default mode: blocking transport (LT — Loosely Timed)** for fast simulation
- **On request: non-blocking transport (AT — Approximately Timed)** for timing accuracy
- **Per-block I/O logging**: Every block's input and output transactions must be logged.
  These logs serve as golden reference data for RTL unit verification in Phase 4-5.
  When RTL is implemented, the logged I/O can be replayed to verify block-level correctness.

Outputs: docs/phase-3-uarch/*.md files covering module decomposition, pipeline diagrams (inter/intra),
FSM specifications, register maps, memory organization, clock domain map, protocol assignments.
Runs in parallel with bfm-develop during Phase 3.
</Purpose>

<Use_When>
- Phase 2 artifacts (architecture.md, block_diagram) are complete
- Microarchitecture needs to be specified before RTL coding
- Timing or pipeline details need expert review
</Use_When>

<Do_Not_Use_When>
- Phase 2 artifacts are missing (run p2-arch-design first)
- Only RTL-level fixes needed (use rtl-p4s-refactor instead)
</Do_Not_Use_When>

<Why_This_Exists>
Architecture describes what blocks exist and how data flows between them.
Microarchitecture describes how each block decomposes into sub-modules and how they work internally:
- Which blocks need further decomposition into smaller hardware modules
- How sub-modules interact (inter-module pipeline, handshake, data dependencies)
- How each sub-module is structured internally (intra-module pipeline, FSM, datapath)

Without explicit module decomposition and pipeline specs, RTL coders make inconsistent implementation choices.
timing-advisor ensures designs are achievable at the target frequency.
</Why_This_Exists>

<Execution_Policy>
- uarch-designer drives the document set (docs/phase-3-uarch/*.md)
- vcodec-architecture-expert provides algorithm-specific micro-decisions
- timing-advisor reviews for frequency feasibility
- **bfm-dev runs in parallel** with uarch-designer to build TLM-based BFM for validation
- **domain-consult actively invoked** for protocol selection, memory architecture, and HW design pattern decisions

**Phase 3 core workflow:**
1. uarch-designer produces per-module specs (sub-block decomposition, clock domains, protocols, register/SRAM/FSM)
2. bfm-dev builds TLM-based BFM in parallel (blocking LT default, AT on request)
3. 3-round iterative review with BFM validation integrated
4. Per-block I/O logging verified — logs become golden reference for Phase 4-5 RTL unit verification

**Clock domain assignment rules:**
- Each sub-block must have an assigned clock domain
- Cross-domain interfaces require explicit synchronizer or CDC primitive specification
- Clock domain map must be documented per module (which blocks share clocks, which are separate)

**Protocol assignment rules:**
- Every inter-block interface must have an assigned protocol (valid/ready, AXI-Stream, FIFO, credit-based)
- Protocol choice must be justified by data rate, latency, and backpressure requirements
- domain-consult invoked when protocol selection is non-obvious

**BFM validation (MANDATORY before review Round 1):**
- BFM must compile and simulate before architectural review begins
- Per-block I/O logging must be enabled — all transactions recorded
- BFM simulation results compared against C reference model outputs
- I/O logs archived for Phase 4-5 RTL unit verification (golden reference)

**Cascading Quality: 3-round mandatory iterative review per module (user-adjustable)**
  - rtl-architect coordinates review rounds as aggregator
  - 5 parallel reviewers each round:
    1. rtl-architect: feature preservation + block boundary + interface + protocol consistency
    2. timing-advisor: critical paths at target frequency + clock domain feasibility
    3. vcodec-architecture-expert: algorithm/memory/interface optimization
    4. ref-model-dev: model consistency (behavior, data widths, fixed-point, I/O log alignment)
    5. bfm-dev: BFM simulation results + I/O logging correctness
  - Each round focuses on: performance, interface, memory access, clock domains, protocol correctness
  - Round 3 is mandatory even if earlier rounds converged (final quality pass)
  - After 3 rounds: escalate remaining issues to user via AskUserQuestion if not converged
  - User may request additional rounds beyond 3
</Execution_Policy>

<Steps>
1. Read architecture.md, block_diagram, and P2 memory classification (internal SRAM vs external DRAM/cache)
2. `mkdir -p reviews/phase-3-uarch docs/phase-3-uarch`
3. **Invoke domain-consult** for domain-specific design patterns:
   - Protocol selection guidance (which protocols suit which data flow patterns)
   - Memory architecture patterns (SRAM banking strategies, line buffer designs)
   - Pipeline design patterns (systolic arrays, wavefront processing, etc.)
4. **uarch-designer produces per-block docs/phase-3-uarch/*.md** (IN PARALLEL with Step 5 BFM development):
   Each module document must contain:
   - **Module decomposition**: Identify which architecture blocks need sub-module decomposition
     - e.g., `prediction` → `intra_pred` + `inter_pred` + `mv_predictor`
     - Blocks that are small enough remain as single modules
   - **Clock domain assignment**: Assign each sub-block to a clock domain
     - Single-domain blocks: `clk` / `rst_n`
     - Multi-domain blocks: `{domain}_clk` / `{domain}_rst_n` (e.g., `sys_clk`, `pixel_clk`)
     - Cross-domain interfaces: specify synchronizer type (2FF, handshake, async FIFO)
     - Clock domain map diagram (which blocks share clocks, which cross domains)
   - **Design partitioning strategy**: How each module is split for efficient implementation
     - Pipeline stages vs combinational logic, area/throughput trade-offs
     - Resource sharing opportunities (ALU reuse, time-multiplexing)
     - Parallelism strategy (spatial vs temporal, degree of unrolling)
   - **Protocol assignment**: Every inter-block interface has an assigned protocol
     - valid/ready handshake (simple point-to-point)
     - AXI-Stream (streaming data with TLAST/TKEEP)
     - FIFO interface (decoupled producer/consumer)
     - Credit-based flow control (high-throughput, predictable latency)
     - Justification: why this protocol for this interface (data rate, latency, backpressure)
   - **Inter-module pipeline**: Data flow between sub-modules within the same architecture block
     - Protocol per connection, backpressure mechanism, data dependencies
   - **Intra-module pipeline**: Pipeline stages within each sub-module
     - Stage names, register cut points, operations per stage, hazard analysis
   - **FSM specification**: State encoding, transitions, outputs, reset state
   - **Register/SRAM/FSM allocation**:
     - Pipeline registers: where and why (timing closure, data alignment)
     - Configuration registers: programmable parameters, field widths, reset values
     - SRAM allocation: capacity, banking, port count, access scheduling
     - FSM allocation: which control paths use FSM, complexity estimate (state count)
   - **Memory map**: SRAM banking, access scheduling, port allocation
     - Internal memory (SRAM): capacity per block, banking strategy, read/write port allocation
     - External memory interface: burst size, outstanding transactions, bandwidth requirements
   - **Signal naming conventions (MANDATORY — these flow directly to RTL):**
     - Inputs: `i_` prefix, Outputs: `o_` prefix, Bidirectional: `io_` prefix (NOT suffix `_i`/`_o`)
     - Clocks: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
     - Resets: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
     - Instances: `u_` prefix (e.g., `u_fifo`), generates: `gen_` prefix (e.g., `gen_stage`)
     - FSM states: `typedef enum logic [N:0]` with `UPPER_SNAKE_CASE` values
     - Types: `snake_case_t` suffix (e.g., `state_t`, `bus_req_t`)
     - Parameters: `UPPER_SNAKE_CASE` (e.g., `DATA_WIDTH`)
   - Use `logic` only in all signal declarations (no `reg`/`wire`)
5. **BFM development (PARALLEL with Step 4)** — bfm-dev builds TLM-based BFM:
   - **Default: blocking transport (LT — Loosely Timed)** for fast functional simulation
   - **On request: non-blocking transport (AT — Approximately Timed)** for timing accuracy
   - **Per-block I/O logging (MANDATORY)**:
     - Every block's input and output transactions must be logged to files
     - Log format: timestamped transaction records (address, data, control signals)
     - Logs serve as golden reference for Phase 4-5 RTL unit verification
     - When RTL is implemented, logged I/O can be replayed to verify block-level correctness
   - BFM must compile and simulate against C reference model outputs before review begins
6. **BFM validation gate** — before proceeding to review rounds:
   - BFM simulation must produce correct outputs (compared against C reference model)
   - Per-block I/O logs must be generated and archived
   - If BFM fails: iterate between uarch-designer and bfm-dev to resolve inconsistencies
7. **Parallel initial review** (5 reviewers in parallel, after uarch-designer draft + BFM validation):
   - a. `rtl-architect`: Feature Preservation Checklist (every architecture block has uarch doc, block boundaries preserved, all functional responsibilities present) + interface + protocol consistency
   - b. `timing-advisor`: Critical path analysis at target frequency, pipeline balance, register placement feasibility, clock domain feasibility
   - c. `vcodec-architecture-expert`: Algorithm ↔ μArch consistency, memory access optimization (SRAM banking, port conflicts, access scheduling), interface optimization
   - d. `ref-model-dev`: Model consistency check (behavioral match, data widths, fixed-point formats, rounding modes)
   - e. `bfm-dev`: BFM simulation results, I/O logging correctness, protocol behavior validation
8. **Review Round 1** — rtl-architect as coordinator aggregates findings from all 5 reviewers:
   - Feature preservation (all architecture features present in uarch?)
   - Performance (pipeline depth, critical paths, throughput at target frequency)
   - Clock domain correctness (proper synchronizers at all crossings?)
   - Protocol adequacy (right protocol for each interface? backpressure handled?)
   - Register/SRAM/FSM allocation (sufficient capacity? no port conflicts?)
   - Memory optimization (SRAM banking adequate? access scheduling?)
   - BFM validation (simulation passes? I/O logs match expected behavior?)
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
   - On FAIL with boundary change: **escalate — may require Phase 2 (p2-arch-design) revision**
9. **Targeted revision Round 1→2** — re-delegate ONLY to experts/modules with feedback:
   - uarch-designer revises specific docs/phase-3-uarch/*.md files for feature/structure issues
   - bfm-dev updates BFM if protocol or interface changes were made
   - Experts without findings are NOT re-invoked
10. **Review Round 2** — same 5 reviewers in parallel, coordinator assesses convergence:
    - Focus on: were Round 1 issues resolved? Any new issues introduced by revisions?
    - BFM re-validated if uarch changes affected interfaces
    - **Save to `reviews/phase-3-uarch/uarch-review-r2.md`** in standard review Markdown format
11. **Targeted revision Round 2→3** — re-delegate ONLY to experts with remaining findings (skip if Round 2 fully converged)
12. **Review Round 3** (mandatory even if converged) — final quality pass:
    - Cross-module interface completeness and protocol consistency
    - Clock domain map consistency (no unhandled crossings)
    - Memory access conflict analysis across all modules (concurrent access patterns)
    - Complete model consistency matrix (every uarch behavior ↔ ref model function)
    - BFM final simulation pass with all I/O logs verified
    - Code review of μArch specs: naming, FSM completeness, no dead states
    - **Save to `reviews/phase-3-uarch/uarch-review-r3.md`** in standard review Markdown format
    - If still not converged → escalate to user via AskUserQuestion with specific unresolved items
13. **Finalize**:
    - Save final `reviews/phase-3-uarch/uarch-review.md` (consolidated from r1-r3)
    - **Save clock domain map to docs/phase-3-uarch/clock-domain-map.md**
    - **Save protocol assignment table to docs/phase-3-uarch/protocol-assignments.md**
    - **Archive per-block I/O logs** for Phase 4-5 RTL unit verification use
    - **Save Mermaid pipeline diagram to `reviews/phase-3-uarch/pipeline-diagram.md`:**
      - Generate a `graph LR` Mermaid diagram showing pipeline stages and data flow
      - Include clock domain boundaries and protocol annotations
      - Example format:
        ```mermaid
        graph LR
            subgraph sys_clk domain
                IF[Fetch] -->|valid/ready| ID[Decode] -->|AXI-Stream| EX[Execute]
            end
            subgraph pixel_clk domain
                EX -->|async FIFO| WB[Writeback]
            end
        ```
    - Verify all signal names in docs/phase-3-uarch/*.md comply with naming conventions
    - Generate phase-3-summary.md for downstream Phase 4 context consumption
</Steps>

<Tool_Usage>
```
Bash("mkdir -p reviews/phase-3-uarch docs/phase-3-uarch")

# --- Step 3: Domain consultation for design pattern guidance ---
Skill("rtl-agent-team:domain-consult",
      args="Protocol selection guidance for inter-block interfaces (valid/ready vs AXI-Stream vs FIFO vs credit-based). Memory architecture patterns (SRAM banking, line buffer). Pipeline design patterns for target domain.")

# --- Step 4+5: uarch-designer draft + BFM development (IN PARALLEL) ---
Task(subagent_type="rtl-agent-team:uarch-designer",
     prompt="Produce microarchitecture docs at docs/phase-3-uarch/ from architecture.md.
     Each module doc MUST include:
     1. Sub-block decomposition with rationale
     2. Clock domain assignment per sub-block (clk/rst_n for single, {domain}_clk/{domain}_rst_n for multi)
     3. Protocol assignment per interface (valid/ready, AXI-Stream, FIFO, credit-based) with justification
     4. Design partitioning strategy (pipeline stages, resource sharing, parallelism degree)
     5. Register/SRAM/FSM allocation (pipeline regs, config regs, SRAM capacity+banking, FSM state count)
     6. Inter/intra-module pipeline, FSM spec, register map, memory map
     7. Signal naming: i_/o_/io_ prefix (NOT _i/_o suffix), {domain}_clk, {domain}_rst_n, u_ instance, UPPER_SNAKE_CASE params
     Also produce: docs/phase-3-uarch/clock-domain-map.md and docs/phase-3-uarch/protocol-assignments.md")

Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="Build TLM-based BFM from architecture.md and docs/phase-3-uarch/ (read as drafts become available).
     Requirements:
     1. Default: blocking transport (LT — Loosely Timed) for fast simulation
     2. AT (non-blocking) mode available on request for timing accuracy
     3. Per-block I/O logging MANDATORY: every block input/output transaction logged to file
        - Format: timestamped records (cycle, address, data, control signals)
        - Logs serve as golden reference for Phase 4-5 RTL unit verification
     4. Compare simulation outputs against C reference model (refc/)
     5. Archive I/O logs for downstream RTL verification use")

# --- Step 6: BFM validation gate ---
# Verify BFM compiles, simulates correctly, and I/O logs are generated
# If BFM fails: iterate uarch-designer ↔ bfm-dev until consistent

# --- Step 7: Parallel initial review (5 reviewers) ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Review Round 1: Read architecture.md and all docs/phase-3-uarch/*.md.
     Verify: block boundary alignment (1:1), feature preservation, interface correctness,
     protocol consistency (every interface has assigned protocol with justification).
     Save Feature Preservation Checklist to reviews/phase-3-uarch/feature-preservation.md.")

Task(subagent_type="rtl-agent-team:timing-advisor",
     prompt="Review Round 1: Review docs/phase-3-uarch/*.md.
     Check: critical path issues at target frequency, pipeline imbalance, register placement feasibility,
     clock domain feasibility (proper synchronizers at all crossings), clock domain map completeness.")

Task(subagent_type="rtl-agent-team:vcodec-architecture-expert",
     prompt="Review Round 1: Read docs/phase-3-uarch/*.md.
     Verify: algorithm ↔ μArch consistency, memory access optimization (SRAM banking, port conflicts),
     protocol adequacy (right protocol per interface?), resource sharing efficiency.")

Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Review Round 1: Read docs/phase-3-uarch/*.md and refc/.
     Check: behavioral match between uarch specs and C ref model, data widths, fixed-point formats,
     rounding modes, I/O log alignment with ref model outputs.")

Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="Review Round 1: Report BFM simulation results.
     Verify: all blocks produce correct outputs, per-block I/O logs generated and valid,
     protocol behavior matches uarch spec (handshake timing, backpressure), no deadlocks.")

# --- Step 8: Coordinator aggregates Round 1 findings ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Aggregate Round 1 findings from all 5 reviewers.
     Consolidate: feature preservation, performance, clock domains, protocols,
     register/SRAM/FSM allocation, memory optimization, BFM validation, model consistency.
     Save to reviews/phase-3-uarch/uarch-review-r1.md.
     Output targeted feedback for each expert/module that needs revision.")

# --- Step 9: Targeted revision Round 1→2 ---
Task(subagent_type="rtl-agent-team:uarch-designer",
     prompt="Revise specific docs/phase-3-uarch/*.md files to address Round 1 findings: [paste targeted feedback]. Only modify files with identified issues.")

Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="Update BFM to reflect Round 1 revisions: [paste interface/protocol changes]. Re-run simulation and verify I/O logs.")
# ^ Only invoke bfm-dev if protocol or interface changes were made

# --- Step 10: Review Round 2 (5 reviewers in parallel) ---
# Same pattern as Round 1 — save to reviews/phase-3-uarch/uarch-review-r2.md
# Include BFM re-validation if uarch changes affected interfaces

# --- Step 11: Targeted revision Round 2→3 (skip if converged) ---

# --- Step 12: Review Round 3 (mandatory final quality pass) ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Review Round 3 (mandatory final pass): Cross-module interface completeness, protocol consistency across all modules, clock domain map consistency. Save to reviews/phase-3-uarch/uarch-review-r3.md.")

Task(subagent_type="rtl-agent-team:timing-advisor",
     prompt="Review Round 3 (mandatory final pass): Final critical path analysis across all modules. Verify pipeline balance at target frequency. Clock domain crossing timing verification.")

Task(subagent_type="rtl-agent-team:vcodec-architecture-expert",
     prompt="Review Round 3 (mandatory final pass): Memory access conflict analysis across all modules. Verify concurrent access patterns are conflict-free. Protocol efficiency final check.")

Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Review Round 3 (mandatory final pass): Complete model consistency matrix (every uarch behavior ↔ ref model function). Code review of μArch specs: naming, FSM completeness, no dead states.")

Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="Review Round 3 (mandatory final pass): Final BFM simulation pass. Verify all per-block I/O logs are complete and archived for Phase 4-5 use. Report any remaining discrepancies.")

# --- Step 13: Finalize ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Finalize: Consolidate r1, r2, r3 reviews into reviews/phase-3-uarch/uarch-review.md.
     Save Mermaid pipeline diagram to reviews/phase-3-uarch/pipeline-diagram.md (graph LR with clock domain boundaries and protocol annotations).
     Verify clock-domain-map.md and protocol-assignments.md are complete.
     Generate phase-3-summary.md for Phase 4 context consumption.
     Output final verdict: VERDICT: PASS or VERDICT: FAIL.")

# On escalation (Round 3 not converged): use AskUserQuestion with unresolved items
# On boundary violation: escalate to Phase 2 (p2-arch-design) for revision
```
</Tool_Usage>

<Examples>
<Good>
3-round iterative convergence with BFM validation:
→ Step 4+5 (parallel): uarch-designer produces 8 module docs with clock domains + protocols;
  bfm-dev builds TLM LT BFM with per-block I/O logging; BFM simulation passes against C ref model.
→ Round 1: rtl-architect flags missing feature in transform block, timing-advisor finds 3-cycle
  combinational path in entropy coder, vcodec-architecture-expert identifies SRAM port conflict,
  ref-model-dev finds fixed-point rounding mismatch, bfm-dev reports deadlock on credit-based interface.
→ Targeted revision: uarch-designer adds feature, inserts pipeline register, fixes SRAM banking,
  changes credit-based → FIFO interface; bfm-dev updates BFM protocol; ref-model-dev aligns rounding.
→ Round 2: All Round 1 issues resolved; timing-advisor identifies new critical path from revision.
  BFM re-validated with updated interfaces — I/O logs regenerated.
→ Targeted revision: uarch-designer rebalances pipeline stages.
→ Round 3 (mandatory): Cross-module interface audit PASS; clock domain map consistent;
  protocol assignments justified; memory conflict analysis PASS; BFM final simulation PASS;
  I/O logs archived; model consistency matrix complete; μArch code review clean.
→ Final verdict: PASS. All 3 round artifacts + I/O logs saved.
</Good>
<Good>
Clock domain + protocol assignment:
→ uarch-designer assigns `sys_clk` (200MHz) to control path, `pixel_clk` (150MHz) to data path.
  Inter-domain interface uses async FIFO with depth justified by throughput calculation.
  Intra-domain interfaces use valid/ready handshake. External DRAM interface uses AXI-Stream.
→ BFM validates the clock domain crossing with I/O logging on both sides of async FIFO.
</Good>
<Bad>
Skipping BFM validation — RTL coder implements the design, but protocol mismatch between blocks
causes deadlock discovered only in Phase 5 cocotb regression, requiring μArch redesign.
</Bad>
<Bad>
No per-block I/O logging — RTL unit tests have no golden reference, Phase 4 unit verification
must derive expected values manually, increasing verification time 3x and introducing errors.
</Bad>
<Bad>
Running only 1 review round for μArch — SRAM port conflict not caught until Phase 5 verification,
requiring μArch redesign and full RTL rewrite. Cascading Quality Principle violated.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Timing infeasibility at target frequency (expert says unachievable) → report to user, propose alternative frequency or architecture change
- FSM cannot represent required algorithm state → escalate to p2-arch-design for block decomposition change
- **Block boundary violation detected** (merge/split not in architecture.md) → escalate to Phase 2 (p2-arch-design) for architecture revision before continuing
- **Functional responsibility missing** from uarch that exists in architecture.md → uarch-designer must add it, or escalate if architecture change is needed
- **Clock domain crossing infeasible** (required data rate exceeds synchronizer throughput) → escalate to p2-arch-design for clock domain restructuring
- **Protocol deadlock detected in BFM** → iterate uarch-designer ↔ bfm-dev; if architectural cause, escalate to p2-arch-design
- **BFM simulation fails after 2 iterations** of uarch-bfm fix loop → escalate to user with root cause analysis
- **Per-block I/O logging incomplete** (blocks without logging) → block Phase 3 completion until all blocks have I/O logs
</Escalation_And_Stop_Conditions>

<Final_Checklist>
**Module decomposition & structure:**
- [ ] docs/phase-3-uarch/*.md exists for each block in architecture.md
- [ ] Module decomposition documented for every block (sub-modules defined or single-module rationale)
- [ ] Inter-module pipelines defined (data flow, handshake, backpressure between sub-modules)
- [ ] Intra-module pipelines defined (stages, register cuts, hazard analysis per sub-module)
- [ ] All block boundaries from architecture.md preserved (no unauthorized merges/splits)
- [ ] All functional responsibilities from architecture.md present in uarch specs

**Clock domain assignment:**
- [ ] Every sub-block has an assigned clock domain
- [ ] Cross-domain interfaces specify synchronizer type (2FF, handshake, async FIFO)
- [ ] docs/phase-3-uarch/clock-domain-map.md saved with complete clock domain map

**Protocol assignment:**
- [ ] Every inter-block interface has an assigned protocol (valid/ready, AXI-Stream, FIFO, credit-based)
- [ ] Each protocol choice justified by data rate, latency, and backpressure requirements
- [ ] docs/phase-3-uarch/protocol-assignments.md saved with protocol assignment table
- [ ] domain-consult invoked for protocol selection guidance

**Register/SRAM/FSM allocation:**
- [ ] Pipeline registers: placement and justification documented per sub-block
- [ ] Configuration registers: fields, widths, reset values defined
- [ ] SRAM allocation: capacity, banking, port count, access scheduling per block
- [ ] FSM allocation: state count, encoding, transitions per control path
- [ ] Memory access patterns optimized (no port conflicts, proper access scheduling)

**BFM validation:**
- [ ] TLM-based BFM built and compiled (blocking LT default)
- [ ] BFM simulation passes against C reference model outputs
- [ ] Per-block I/O logging enabled for ALL blocks (no exceptions)
- [ ] I/O logs archived for Phase 4-5 RTL unit verification use
- [ ] No deadlocks or protocol violations detected in BFM simulation

**Review & compliance:**
- [ ] 3-round iterative review completed (or remaining gaps escalated to user and approved)
- [ ] Cross-module interfaces reviewed for protocol consistency and completeness
- [ ] μArch ↔ ref model consistency verified (behavior, data widths, fixed-point formats, rounding modes)
- [ ] μArch code review passed (naming, FSM completeness, no dead states)
- [ ] rtl-architect hierarchical spec compliance verdict is PASS
- [ ] timing-advisor review complete with no blockers
- [ ] vcodec-architecture-expert approved algorithm correctness

**Naming conventions:**
- [ ] All port names use `i_`/`o_`/`io_` prefix (NOT `_i`/`_o` suffix)
- [ ] All clocks named `{domain}_clk` (e.g., `sys_clk`) — bare `clk` OK for single domain. NOT `clk_i`
- [ ] All resets named `{domain}_rst_n` (e.g., `sys_rst_n`) — bare `rst_n` OK for single domain. NOT `rst_ni`
- [ ] Instance names use `u_` prefix, generate blocks use `gen_` prefix
- [ ] FSM states defined as `typedef enum logic [N:0]` with `UPPER_SNAKE_CASE` values

**Artifacts saved:**
- [ ] reviews/phase-3-uarch/uarch-review-r1.md
- [ ] reviews/phase-3-uarch/uarch-review-r2.md
- [ ] reviews/phase-3-uarch/uarch-review-r3.md
- [ ] reviews/phase-3-uarch/feature-preservation.md (Feature Preservation Checklist)
- [ ] reviews/phase-3-uarch/uarch-review.md (consolidated final review)
- [ ] reviews/phase-3-uarch/pipeline-diagram.md (Mermaid diagram with clock domains + protocols)
- [ ] docs/phase-3-uarch/clock-domain-map.md
- [ ] docs/phase-3-uarch/protocol-assignments.md
- [ ] docs/phase-3-uarch/phase-3-summary.md (compressed summary for Phase 4)
</Final_Checklist>

<Advanced>
Register maps in docs/phase-3-uarch/*.md become the ground truth for rtl-ipxact-gen and rtl-document.
FSMs must be deterministic with explicit reset states and no deadlock conditions.

**Convention enforcement is critical here** — docs/phase-3-uarch/*.md signal names are directly copied by rtl-coder.
Wrong naming in uarch (e.g., `clk_i` instead of `clk`/`sys_clk`, or suffix `data_i` instead of prefix `i_data`)
will propagate to RTL and require expensive refactoring across all modules.

**Per-block I/O logs as golden reference:**
The I/O logs generated by BFM during Phase 3 validation become the primary golden reference for
Phase 4-5 RTL unit verification. Each block's logged transactions (input stimuli + expected outputs)
can be directly replayed against RTL to verify functional correctness without re-deriving test vectors.
This significantly reduces Phase 4-5 verification effort and eliminates manual test vector errors.

**Protocol assignment persistence:**
Protocol assignments in docs/phase-3-uarch/protocol-assignments.md are binding for Phase 4 RTL coding.
rtl-coder must implement the exact protocol specified (e.g., if valid/ready is assigned, do not substitute
with AXI-Stream). Protocol changes require Phase 3 re-review.

**Clock domain map persistence:**
Clock domain assignments in docs/phase-3-uarch/clock-domain-map.md flow to Phase 4 RTL and Phase 5
CDC verification. Any deviation in RTL from the assigned clock domains requires Phase 3 re-review
and CDC analysis update.
</Advanced>
