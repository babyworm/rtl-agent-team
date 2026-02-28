---
name: rtl-autopilot
description: "This skill should be used when starting a full RTL design pipeline from spec to verification. Orchestrates 6-phase flow (Research → Architecture → μArch → RTL → Verify → Design Note) with dual-layer phase gates and hierarchical spec compliance."
---

<Purpose>
Drive the complete RTL design pipeline through six sequential phases with enforced dual-layer phase gates.
Each phase must pass both an Artifact Gate (verify deliverables exist) and a Quality Gate (verify quality + hierarchical spec compliance) before the next phase begins.

**Hierarchical Spec Compliance Principle:**
Lower phases MUST NOT violate upper phase specifications:
  Spec → Architecture → μArch → RTL → Verification
Each phase strictly adheres to decisions made in all preceding phases.
Deletion, reduction, or modification of features for convenience is FORBIDDEN.
If a change is needed, control returns to the upper phase for approval.

**Design Priority Order:**
1. Functional Correctness (highest) — Every required feature in Spec works exactly
2. Interface Compliance — Ports, protocols, timing interfaces match Architecture
3. Timing/Performance — Throughput, latency targets met
4. Area/Power (lowest)

**Cascading Quality Principle:**
Good research → good architecture → good μArch → good RTL.
Higher abstraction levels demand MORE iterative refinement because their quality cascades
to ALL downstream phases. A defect at the architecture level costs orders of magnitude more
to fix at RTL than if caught during architecture review. Time is NOT a constraint at upper
levels — it is better to spend extra review rounds perfecting architecture than to discover
fundamental issues during RTL.

Graduated iteration by abstraction level:
  Phase 1 (Research): 3 mandatory rounds (existing — chief-coordinated)
  Phase 2 (Architecture): 3 mandatory rounds — memory, performance, ref model consistency
  Phase 3 (μArch): 3 mandatory rounds — performance, interface, memory optimization
  Phase 4 (RTL): Wave-based lint+sim (implementation-level)
  Phase 5 (Verify): Sub-phase parallel (terminal verification)

Iteration count can be increased beyond 3 if convergence is not achieved.
The principle: **refine thoroughly at the top, execute efficiently at the bottom.**

**Document-as-Memory Principle:**
Design artifacts (docs/, reviews/) serve as persistent memory across phases and agents.
Each phase reads upstream documents as input context and writes downstream documents as output.
This eliminates direct agent-to-agent state coupling and enables resumability — any phase can
restart by re-reading its input documents.

Document flow:
  requirements.json → arch-designer reads → architecture.md → uarch-designer reads → docs/phase-3-uarch/*.md → rtl-coder reads
  reviews/phase-N/ → Quality Gate reads → next phase proceeds or fails

No agent needs to "remember" another agent's output — it reads the document.

State is persisted at .rtl-agent-team/state/rtl-autopilot-state.json for resumability.
</Purpose>

<Use_When>
- Starting a new RTL design project from specification
- Resuming an interrupted pipeline run
- Full end-to-end automation is required with no manual phase handoff
</Use_When>

<Do_Not_Use_When>
- Only a single phase needs to run (use the phase-specific skill instead)
- Design already has completed artifacts for early phases
- Quick prototype or exploratory work only
</Do_Not_Use_When>

<Why_This_Exists>
RTL design spans domains (algorithm, architecture, RTL, verification) that require different specialists.
Manual handoff between phases loses context and misses interface contracts.
This skill automates sequencing, gate checking, and recovery.
</Why_This_Exists>

<Execution_Policy>
- State file (.rtl-agent-team/state/rtl-autopilot-state.json) tracks progress for resumability
- Independent sub-tasks within a phase run in parallel via concurrent Task() calls
- **Dual-Layer Phase Gates** are hard stops between every phase:
  1. **Artifact Gate**: Required files/directories exist (fast check)
  2. **Quality Gate**: Reviewer agent(s) verify quality AND hierarchical spec compliance
- Quality Gate verdicts are structured: `PASS` or `FAIL + findings[]`
- On Artifact Gate failure: retry the failed phase once, then escalate to user
- On Quality Gate failure: pass findings back to the phase's worker agent for correction, then re-run Quality Gate
- **On upper-spec violation**: return to the violated upper phase (e.g., Architecture violates Spec → return to Phase 1). Report violation to user and DO NOT proceed without approval
- Maximum 2 Quality Gate retry cycles per phase before escalating to user
- **Phase 5→4 Feedback Loop**: On Phase 5 sub-phase FAIL, classify as UNIT_FIX/INTEGRATION_FIX/DESIGN_FIX and handle accordingly (max 2 feedback loops per sub-phase)
- On interruption: state file is preserved with detailed context for resumability:
  - Set `interrupted_reason` (e.g., "user_cancel", "gate_fail_escalated", "error")
  - Set `partial_work_summary` with human-readable progress description
  - Update per-phase `partial_work`: move completed items, record `current_action` and `last_agent`
  - For Phase 4: update `completed_modules`, `stream_a_status`, `stream_b_status`
  - For Phase 5: update `completed_sub_phases`, `fix_history`
  - For Phase 6: update `completed_waves`, `current_wave`
  - Re-invoking this skill triggers the Resume check (Step 1.5) which reads partial_work to skip completed work
- **Context Manifest**: Each phase has a manifest (`templates/context-manifest-phase-{N}.json`) that declares:
  - `required_full_read`: files that MUST be fully read before starting the phase
  - `required_summary_only`: files where only the phase summary (`phase-N-summary.md`) is sufficient
  - `optional_on_demand`: files read only when a specific question arises during the phase
  This prevents both context starvation (missing upstream docs) and context waste (loading unnecessary files).
  Agents entering a phase MUST load `required_full_read` first, then `required_summary_only` summaries.
- **Scratchpad for intra-phase communication**: During iterative reviews, agents write findings
  to `.rtl-agent-team/scratch/phase-{N}/` as temporary working files. The coordinator reads
  these to aggregate feedback. On phase completion, findings are consolidated into reviews/
  and scratch files are cleaned up.
</Execution_Policy>

<Steps>
1. **Initialize state**: write .rtl-agent-team/state/rtl-autopilot-state.json with phase=1, sub_phase=null, feedback_loops=0, max_feedback_loops=2

1.5. **Resume check** (if state file already exists):
   - Read `.rtl-agent-team/state/rtl-autopilot-state.json`
   - **Schema migration**: if `schema_version` is missing or `"1.0"`, migrate to v2.0:
     - Add `schema_version: "2.0"`, `current_phase`, `current_phase_name`, `interrupted_reason`, `partial_work_summary`
     - Add per-phase fields: `started_at`, `completed_at`, `gate_passed_at`, `review_rounds_completed`, `partial_work`
     - Add Phase 4 fields: `completed_modules`, `pending_modules`, `stream_a_status`, `stream_b_status`
     - Add Phase 5 fields: `completed_sub_phases`, `pending_sub_phases`, `fix_history`
     - Add Phase 6 fields: `completed_waves`, `current_wave`
   - **Skip completed phases**: for each phase where `status == "completed"` AND `gate_passed_at != null`, skip entirely
   - **Resume in-progress phase**: read `partial_work.completed_items` to determine what is already done
     - Skip completed items, continue from `partial_work.current_action`
     - Resume review rounds from `review_rounds_completed` (e.g., if 1 of 3 rounds done, start at round 2)
   - **Phase 4 resume**: check `completed_modules` vs `pending_modules`, resume `stream_a_status`/`stream_b_status`
   - **Phase 5 resume**: check `completed_sub_phases` vs `pending_sub_phases`, resume from next pending sub-phase
   - **Phase 6 resume**: check `completed_waves`, resume from `current_wave`
   - **Context reload**: read upstream documents for the resumed phase per Context Manifest (see #3)
   - Clear `interrupted_reason` and `partial_work_summary` after successful resume

---

2. **Phase 1 — Research**: invoke research-analyze skill
   - io_definition.json must use project naming conventions: `i_`/`o_`/`io_` port prefixes, `{domain}_clk`, `{domain}_rst_n`
   - **Review artifacts setup**: `mkdir -p reviews/phase-1-research`

   **Phase 1→2 Artifact Gate**: requirements.json + io_definition.json + domain-analysis.md exist

   **Phase 1→2 Quality Gate (Research Completeness Review)**:
   - `spec-analyst` self-reviews requirements.json for completeness and internal consistency
     - Are all functional requirements traceable to spec sections?
     - Are there contradictions or ambiguities?
     - **Save review result to `reviews/phase-1-research/research-review.md`** in standard review Markdown format
   - `arch-designer` evaluates requirements for implementation feasibility
     - Can every requirement be realized in RTL within reasonable area/timing?
     - Are there missing constraints (clock frequency, interface protocols)?
   - **Verdict**: PASS if all requirements are clear, consistent, and implementable; FAIL + findings otherwise

   **Phase 1 Summary Generation** (after Quality Gate PASS, before Phase 2 starts):
   - Delegate to `rtl-architect` (model=sonnet): read all Phase 1 artifacts and generate
     `docs/phase-1-research/phase-1-summary.md` using `templates/phase-summary.md` format.
   - This summary is used by Phase 3-4 as compressed context via `required_summary_only`.

   **Phase 1→2 Summary Validation:**
   - Verify `docs/phase-1-research/phase-1-summary.md` exists
   - If missing: delegate to `rtl-architect` (model=sonnet) to generate from Phase 1 artifacts
   - Summary must follow `templates/phase-summary.md` format

---

3. **Phase 2 — Architecture + Reference Model (parallel + 3-round iterative review)**:

   **Context Manifest Preload Validation** (Phase 2 start):
   - Load `templates/context-manifest-phase-2.json`
   - For each `required_full_read` entry: verify file exists, read into context
   - For each `required_summary_only` entry: verify referenced phase summaries exist
   - If ANY required file missing: STOP with clear error listing missing files
   - `optional_on_demand` files: skip validation, load lazily during execution

   invoke arch-design and ref-model skills concurrently
   - arch-designer + ref-model-dev produce initial artifacts concurrently
   - architecture.md interface tables must use `i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n` naming
   - **Review artifacts setup**: `mkdir -p reviews/phase-2-architecture .rtl-agent-team/scratch/phase-2`
   - **Cascading Quality: 3-round mandatory iterative review** coordinated by rtl-architect:
     - Parallel reviewers each round:
       (a) `rtl-architect`: spec compliance (Feature Coverage Checklist) + structural review
       (b) `vcodec-architecture-expert`: memory access patterns, performance analysis (SRAM sizing, bandwidth, access conflicts)
       (c) `ref-model-dev`: architecture ↔ C model consistency (block mapping, data flow, interface alignment)
     - Round 1-2: review → targeted feedback → revision (only experts with findings re-run)
     - Round 3 mandatory even if converged: cross-block interface audit + memory conflict analysis + ref model code review
     - After 3 rounds if not converged → escalate to user via AskUserQuestion
     - User may request additional rounds beyond 3 ("set iterations to N")
   - `rtl-critic` performs synthesizability pre-assessment (parallel with Round 1)

   **Phase 2→3 Artifact Gate**: architecture.md + block_diagram + refc/*/*.c exist

   **Phase 2→3 Quality Gate (Architecture Review)**:
   - 3-round iterative review converged (or gaps escalated and user-approved)
   - **Feature Coverage Checklist**: 100% of REQ-NNN mapped to architecture blocks
     - **Save checklist to `reviews/phase-2-architecture/feature-coverage.md`** in standard review Markdown format
   - Memory access review PASS: all large blocks have viable memory strategy
   - Architecture ↔ ref model consistency PASS: block mapping + data flow + interface alignment
   - Ref model code review: quality, bitexact correctness verified
   - **Architecture Diagram**: Save Mermaid block diagram to `reviews/phase-2-architecture/architecture-diagram.md`
   - Per-round review artifacts: architecture-review-r1.md, r2.md, r3.md
   - **Save consolidated review to `reviews/phase-2-architecture/architecture-review.md`** in standard review Markdown format
   - **Verdict**: PASS if Spec feature coverage is 100% AND no structural defects AND iterative review converged; FAIL + findings otherwise

   **Phase 2 Summary Generation** (after Quality Gate PASS, before Phase 3 starts):
   - Delegate to `rtl-architect` (model=sonnet): read all Phase 2 artifacts and generate
     `docs/phase-2-architecture/phase-2-summary.md` using `templates/phase-summary.md` format.
   - This summary is used by Phase 4+ as compressed context via `required_summary_only`.

   **Phase 2→3 Summary Validation:**
   - Verify `docs/phase-2-architecture/phase-2-summary.md` exists
   - If missing: delegate to `rtl-architect` (model=sonnet) to generate from Phase 2 artifacts
   - Summary must follow `templates/phase-summary.md` format

   **Phase 2 ADR Recording** (after summary, before Phase 3 starts):
   - Delegate to `arch-designer` (model=sonnet): identify 3-5 key architectural decisions made
     during Phase 2 (e.g., pipeline vs combinational, memory architecture, interface protocol choice).
   - For each decision, create `docs/decisions/ADR-{NNN}.md` using `templates/adr-template.md` format.
   - Link each ADR to relevant REQ IDs and architecture.md sections.

---

4. **Phase 3 — μArch + BFM (parallel + 3-round iterative review)**:

   **Context Manifest Preload Validation** (Phase 3 start):
   - Load `templates/context-manifest-phase-3.json`
   - For each `required_full_read` entry: verify file exists, read into context
   - For each `required_summary_only` entry: verify referenced phase summaries exist
   - If ANY required file missing: STOP with clear error listing missing files
   - `optional_on_demand` files: skip validation, load lazily during execution

   invoke rtl-uarch-design and bfm-develop skills concurrently
   - uarch-designer + bfm-dev produce initial artifacts concurrently
   - docs/phase-3-uarch/*.md register/signal names must follow: `i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n`, `u_` instances, `gen_` generates
   - **Review artifacts setup**: `mkdir -p reviews/phase-3-uarch .rtl-agent-team/scratch/phase-3`
   - **Cascading Quality: 3-round mandatory iterative review** coordinated by rtl-architect:
     - Parallel reviewers each round:
       (a) `rtl-architect`: feature preservation + block boundary alignment + interface correctness
       (b) `timing-advisor`: critical paths at target frequency, pipeline balance
       (c) `vcodec-architecture-expert`: algorithm/memory/interface optimization (SRAM banking, port conflicts, handshake, backpressure)
       (d) `ref-model-dev`: model consistency (behavioral match, data widths, fixed-point formats, rounding modes)
     - Each round focuses on: performance, interface, memory access optimization per module
     - Round 3 mandatory: model consistency matrix + cross-module interface audit + μArch code review
     - After 3 rounds if not converged → escalate to user via AskUserQuestion
     - User may request additional rounds beyond 3

   **Phase 3→4 Artifact Gate**: docs/phase-3-uarch/*.md + bfm/ directory exist

   **Phase 3→4 Quality Gate (μArch Review)**:
   - 3-round iterative review converged (or gaps escalated and user-approved)
   - **Feature Preservation Checklist**: 100% of architecture features preserved in μArch
     - **Save checklist to `reviews/phase-3-uarch/feature-preservation.md`** in standard review Markdown format
   - Block boundary alignment: 1:1 correspondence with architecture.md
   - Memory access optimization PASS: SRAM banking, port conflicts, access scheduling reviewed
   - μArch ↔ ref model consistency PASS: behavior, data widths, fixed-point formats aligned
   - **Pipeline Diagram**: Save Mermaid pipeline diagram to `reviews/phase-3-uarch/pipeline-diagram.md`
   - Per-round review artifacts: uarch-review-r1.md, r2.md, r3.md
   - **Save consolidated review to `reviews/phase-3-uarch/uarch-review.md`** in standard review Markdown format
   - **Verdict**: PASS if architecture is fully and faithfully decomposed into μArch with no feature loss AND timing paths are reasonable AND iterative review converged; FAIL + findings otherwise

   **Phase 3 Summary Generation** (after Quality Gate PASS, before Phase 4 starts):
   - Delegate to `rtl-architect` (model=sonnet): read all Phase 3 artifacts and generate
     `docs/phase-3-uarch/phase-3-summary.md` using `templates/phase-summary.md` format.
   - This summary is used by Phase 5+ as compressed context via `required_summary_only`.

   **Phase 3→4 Summary Validation:**
   - Verify `docs/phase-3-uarch/phase-3-summary.md` exists
   - If missing: delegate to `rtl-architect` (model=sonnet) to generate from Phase 3 artifacts
   - Summary must follow `templates/phase-summary.md` format

   **Phase 3 ADR Recording** (after summary, before Phase 4 starts):
   - Delegate to `uarch-designer` (model=sonnet): identify 3-5 key μArch decisions made
     during Phase 3 (e.g., pipeline depth, SRAM banking strategy, FSM decomposition, handshake protocol).
   - For each decision, create `docs/decisions/ADR-{NNN}.md` using `templates/adr-template.md` format.
   - Link each ADR to relevant architecture.md sections and upstream Phase 2 ADRs.

---

5. **Phase 4 — RTL Implementation + Early Verification (PARALLEL STREAMS)**

   **Context Manifest Preload Validation** (Phase 4 start):
   - Load `templates/context-manifest-phase-4.json`
   - For each `required_full_read` entry: verify file exists, read into context
   - For each `required_summary_only` entry: verify referenced phase summaries exist
   - If ANY required file missing: STOP with clear error listing missing files
   - `optional_on_demand` files: skip validation, load lazily during execution

   Two parallel streams run simultaneously after Phase 3→4 gate passes:
   - Enforce: `logic` only (no `reg`/`wire`), `always_ff`/`always_comb`, ANSI port style
   - **Review artifacts setup**: `mkdir -p reviews/phase-4-rtl`

   **Stream A — RTL Implementation (invoke rtl-code skill):**
   - rtl-coder writes modules (wave-based parallel per module)
   - lint-checker validates (Wave 2: lint all at once)
   - testbench-dev generates unit TBs (Wave 4)
   - eda-runner runs unit sim (Wave 4)

   **Stream B — Early Verification Framework (starts simultaneously with Stream A):**
   - B1. `sva-extractor`: Generate SVA property skeletons from docs/phase-3-uarch/*.md
     (signal names, FSM states, protocol handshakes are known from μArch specs)
   - B2. `cdc-checker`: Analyze clock domain topology from docs/phase-3-uarch/*.md
     (identify synchronizer requirements, crossing points, generate preliminary CDC report)
   - B3. `testbench-dev`: Generate cocotb TB skeletons from docs/phase-3-uarch/*.md
     (port connectivity, clock/reset structure, test vector scaffolds)
     Mark as "skeleton" — full execution deferred to Phase 5c

   **Stream B Traceability Convention:**
   Each Stream B artifact must include source traceability:
   - SVA skeletons (`docs/phase-4-rtl/stream-b-sva-skeletons.md`):
     Each property must reference μArch source: `// Source: docs/phase-3-uarch/{module}.md, Section: {section}`
   - CDC preliminary (`docs/phase-4-rtl/stream-b-cdc-preliminary.md`):
     Each CDC path must reference architecture clock domain definition
   - TB skeletons (`docs/phase-4-rtl/stream-b-tb-skeletons.md`):
     Each test scenario must reference requirement: `# REQ-{NNN}: {description}`

   **Merge Point (Phase 4→5 Gate):**
   - Stream A: all RTL lint-clean + unit tests PASS + basic integration PASS
   - Stream B artifacts (SVA skeletons, preliminary CDC report, TB skeletons) ready for Phase 5
   - Stream B CDC findings fed back to RTL coders if synchronizers are missing

   **Phase 4→5 Artifact Gate**: rtl/*/*.sv exist and all lint-clean + sim/*/tb_*.sv exist for all modules + sim/*/*_results.txt exist and all PASS + basic integration smoke test PASS + Stream B artifacts exist (sim/formal/ SVA skeletons, preliminary CDC report, sim/ TB skeletons)

   **Phase 4→5 Quality Gate (RTL Design Review)**:
   - `rtl-critic` reviews RTL code against μArch specs AND requirements.json:
     - **Functional Coverage Check**: for each requirement in requirements.json, trace it through uarch to RTL implementation. Produce a coverage matrix: requirement → uarch section → RTL module/line. Flag any requirement with no RTL implementation as FAIL
       - **Save functional completeness report to `reviews/phase-4-rtl/functional-completeness.md`** in standard review Markdown format
     - Code quality: proper FSM coding, no latches, clean reset logic
     - Synthesizability: no non-synthesizable constructs, appropriate clock gating
     - Coding convention compliance: `i_`/`o_` ports, `{domain}_clk`/`{domain}_rst_n`, `u_` instances, `gen_` generates, `logic` only
     - **Save full design review to `reviews/phase-4-rtl/design-review.md`** in standard review Markdown format
   - `lint-checker` runs full lint pass:
     - Zero errors required; warnings reviewed for false positives
     - **Save lint report to `reviews/phase-4-rtl/lint-report.md`** in standard review Markdown format
   - **Verdict**: PASS if functional coverage is 100% AND lint-clean AND design quality passes; FAIL + findings otherwise

   **Phase 4 Summary Generation** (after Quality Gate PASS, before Phase 5 starts):
   - Delegate to `rtl-architect` (model=sonnet): read all Phase 4 artifacts and generate
     `docs/phase-4-rtl/phase-4-summary.md` using `templates/phase-summary.md` format.
   - This summary is used by Phase 5-6 as compressed context via `required_summary_only`.

   **Phase 4→5 Summary Validation:**
   - Verify `docs/phase-4-rtl/phase-4-summary.md` exists
   - If missing: delegate to `rtl-architect` (model=sonnet) to generate from Phase 4 artifacts
   - Summary must follow `templates/phase-summary.md` format

---

6. **Phase 5 — Extensive Verification (Sub-Phases)**
   - **Review artifacts setup**: `mkdir -p reviews/phase-5-verify`

   **Context Manifest Preload Validation** (Phase 5 start):
   - Load `templates/context-manifest-phase-5.json`
   - For each `required_full_read` entry: verify file exists, read into context
   - For each `required_summary_only` entry: verify referenced phase summaries exist
   - If ANY required file missing: STOP with clear error listing missing files
   - `optional_on_demand` files: skip validation, load lazily during execution
   - Phase 5 is structured into 5 sub-phases (some can run in parallel)
   - State tracking: uses `completed_sub_phases`, `pending_sub_phases`, `fix_history` fields in `rtl-autopilot-state.json`

   **Phase 5a: SVA Completion + Formal Verification (parallel with 5b/5c)**
   - `sva-extractor`: Complete SVA properties using Stream B skeletons + actual RTL
     (Stream B provided structural skeletons; now add RTL-specific signal bindings)
   - `eda-runner`: run formal verification with SymbiYosys
   - Output: `reviews/phase-5-verify/formal-review.md`

   **Phase 5b: CDC Verification (parallel with 5a/5c)**
   - `cdc-checker`: Update preliminary CDC report (from Stream B) with final RTL
     Compare Stream B CDC predictions vs actual RTL implementation
     Verify synchronizers exist where Stream B identified crossing points
   - Output: `reviews/phase-5-verify/cdc-report.md`

   **Phase 5c: Integration TB + Ref Model Comparison (parallel with 5a/5b)**
   - `testbench-dev`: Complete cocotb TB skeletons from Stream B with actual test logic
   - `func-verifier`: extensive RTL vs ref_model comparison
   - `eda-runner`: run cocotb regression — **per-module parallel + multi-seed (5 seeds × N modules)**
   - Output: `reviews/phase-5-verify/requirement-traceability.md`

   **Phase 5d: Coverage Analysis (incremental, starts as modules complete 5a-5c)**
   - `coverage-analyst`: analyze line/toggle/FSM coverage incrementally
     Don't wait for ALL modules — analyze completed modules as they finish
   - If below target: `testbench-dev` generates additional tests
   - Output: `reviews/phase-5-verify/coverage-report.md`

   **Phase 5e: Extensive Design Review (after 5a-5d complete)**
   - `rtl-architect`: Final Compliance Matrix (end-to-end audit)
     - **Final Feature Completeness Audit**: re-read every requirement from requirements.json and confirm: (a) it is implemented in RTL, (b) it has at least one verification test covering it, (c) that test passed
     - Interface completeness: are all ports in io_definition.json present and connected in the top-level RTL?
     - Untested paths: identify any functionality that lacks verification coverage
   - `rtl-critic`: comprehensive design review
   - Output: `reviews/phase-5-verify/final-compliance.md`, `reviews/phase-5-verify/e2e-traceability.md`

   **Phase 5→4 Feedback Loop (with parallel UNIT_FIX):**
   - Collect ALL FAIL results from sub-phases 5a, 5b, 5c before starting fixes
   - Classify each FAIL:
     - **UNIT_FIX**: resolvable by fixing a single module (e.g., SVA counterexample, assertion failure)
     - **INTEGRATION_FIX**: requires inter-module interface modification
     - **DESIGN_FIX**: requires architecture-level design change (→ user approval mandatory)
   - **Batch UNIT_FIX across sub-phases:**
     - Group all UNIT_FIX failures by module
     - If failures are in DIFFERENT modules → launch parallel rtl-bugfix tasks (one per module)
     - If failures are in SAME module → sequential fix within single rtl-bugfix task
     - Each rtl-bugfix follows: analyze → fix → lint → TB → sim
     - All parallel fixes run concurrently with `run_in_background: true`
   - INTEGRATION_FIX: always sequential (cross-module dependencies)
   - After ALL fixes complete: re-run ONLY affected sub-phases in parallel
     (e.g., if 5a and 5c both failed, re-run 5a + 5c simultaneously after fixes)
   - Maximum 2 feedback loops per sub-phase (escalate to user if exceeded)
   - **Lesson Learned Recording** (after each successful feedback fix):
     - Delegate to `rtl-coder` (model=sonnet): append a lesson entry to `docs/lessons-learned.md`
       using `templates/lessons-learned-entry.md` format.
     - Record: symptom, root cause, fix applied, prevention strategy, related REQ/module/ADR.
     - This builds a cross-project knowledge base that Phase 4/5 agents can reference to avoid repeat bugs.
   - DESIGN_FIX handling:
     1. IMMEDIATE STOP — classified as upper-spec violation
     2. Report to user: violation details + impact scope + recommended action
     3. After user approval, return to Phase 3 (μArch) or Phase 2 (Architecture)

   **Sub-phase Re-entry Criteria:**
   | Fix Type | Re-run Sub-phases | Condition |
   |----------|------------------|-----------|
   | UNIT_FIX (SVA fail) | 5a only (formal) | SVA property affected |
   | UNIT_FIX (sim fail) | 5c only (integration) | Testbench affected |
   | INTEGRATION_FIX | 5b + 5c (CDC + integration) | Interface modified |
   | DESIGN_FIX | All (5a-5e) after upper phase approval | Architecture changed |

   **Timeout Policy:**
   - Per feedback loop: max 30 min wall-clock (estimated, not enforced)
   - Per rtl-bugfix task: inherits `execution.timeout_per_job` from config
   - If loop 2 fails: STOP, report to user with full failure context

   **Feedback Loop State Tracking:**
   State file: `.rtl-agent-team/state/feedback-loop-state.json`
   ```json
   {
     "loop_count": 1,
     "max_loops": 2,
     "failures": [
       {
         "sub_phase": "5a",
         "type": "UNIT_FIX",
         "module": "example_module",
         "description": "SVA counterexample at cycle 42",
         "fix_applied": "Added pipeline register",
         "re_run_phases": ["5a"]
       }
     ],
     "status": "in_progress"
   }
   ```

   **Phase 5 Completion Artifact Gate**: all verification sub-phases (5a-5e) pass

   **Phase 5 Completion Quality Gate (Final Spec Compliance Review)**:
   - `func-verifier` produces Requirement Traceability Matrix:
     - **Save to `reviews/phase-5-verify/requirement-traceability.md`** in standard review Markdown format
   - `rtl-architect` performs end-to-end review via Phase 5e results:
     - **Save final compliance review to `reviews/phase-5-verify/final-compliance.md`** in standard review Markdown format
   - **Verdict**: PASS if every original requirement is implemented, verified, and passing; FAIL + findings otherwise

   **Phase 5 Summary Generation** (after Quality Gate PASS, before Phase 6 starts):
   - Delegate to `rtl-architect` (model=sonnet): read all Phase 5 artifacts and generate
     `docs/phase-5-verify/phase-5-summary.md` using `templates/phase-summary.md` format.
   - This summary captures verification results for Phase 6 design review reference.

   **Phase 5→6 Summary Validation:**
   - Verify `docs/phase-5-verify/phase-5-summary.md` exists
   - If missing: delegate to `rtl-architect` (model=sonnet) to generate from Phase 5 artifacts
   - Summary must follow `templates/phase-summary.md` format

---

7. **Phase 6 — Design Review & Documentation**: invoke rtl-design-review-phase skill

   **Phase 5→6 Artifact Gate**: `reviews/phase-5-verify/final-compliance.md` exists AND verdict=PASS

   **Phase 6 Execution** (2-wave parallel):
   - **Wave 1 (parallel)**: `code-quality-reviewer` + `design-quality-reviewer` — code quality scoring + cross-phase design consistency
   - **Wave 2 (parallel, after Wave 1)**: `design-note-writer` + `improvement-analyst` — comprehensive design note + prioritized improvement recommendations

   **Phase 6 Completion Quality Gate**: All 4 deliverables exist AND pass quality checks:
   - `reviews/phase-6-review/code-review.md` — `code-quality-reviewer` verdict must be PASS
   - `reviews/phase-6-review/design-review.md` — `design-quality-reviewer` verdict must be PASS
   - `reviews/phase-6-review/design-note.md` — `design-note-writer` must produce complete document
   - `reviews/phase-6-review/improvements.md` — `improvement-analyst` must produce recommendations
   - On FAIL: iterate review → fix cycle (max 2 rounds, same as Phase 5)
   - On agent failure: retry once, then escalate to user

---

8. **On completion**: remove state file, report summary with final compliance matrix and Phase 6 deliverables

---

**Gate Failure Handling:**
- **Quality Gate FAIL (same-level fix)**: pass findings to the phase's worker agent for correction. Re-run Quality Gate after fix. Max 2 retry cycles per gate
- **Upper-Spec Violation detected**: STOP immediately. Identify which upper phase is violated (e.g., "μArch dropped Feature X that Architecture requires"). Return to the violated upper phase. Report violation details to user — DO NOT proceed without user approval
- **Artifact Gate FAIL**: retry the phase once, then escalate to user

**Scratchpad Convention (intra-phase agent communication):**
During iterative review rounds, reviewers write findings to scratch files:
  .rtl-agent-team/scratch/phase-{N}/round-{R}-{agent}.md

The coordinator (rtl-architect) reads all round files to aggregate and produce:
  .rtl-agent-team/scratch/phase-{N}/round-{R}-feedback.md  (targeted feedback for revision agents)

On phase gate PASS:
  - Consolidated review saved to reviews/phase-{N}-*/
  - Scratch directory cleaned: rm -rf .rtl-agent-team/scratch/phase-{N}/

On phase gate FAIL + retry:
  - Scratch files preserved for the next round

This pattern follows Document-as-Memory: agents communicate through files, not direct coupling.

**Coding Convention Enforcement (all phases):**
See CLAUDE.md "Coding Conventions" section for full rules (language standards + Core Overrides).
Summary: i_/o_/io_ port prefix, {domain}_clk/{domain}_rst_n, u_ instances, gen_ generates, logic only.
</Steps>

<Tool_Usage>
```
# ============================================================
# Context Manifest: Before starting each Phase N, load files per
#   templates/context-manifest-phase-{N}.json
#   1. Read all required_full_read files
#   2. Read phase-summary.md for required_summary_only files
#   3. Load optional_on_demand only when needed during the phase
# ============================================================

# ============================================================
# State Update Pattern (apply after each milestone):
#   Read state → update partial_work.completed_items → update current_action → write state
#   On phase completion: set status="completed", completed_at, gate_passed_at
#   On interruption: set interrupted_reason, partial_work_summary, per-phase partial_work
# ============================================================

# ============================================================
# Phase 1: Research
# ============================================================
Bash("mkdir -p reviews/phase-1-research")

Task(subagent_type="rtl-agent-team:spec-analyst",
     prompt="Analyze spec at specs/ and produce requirements.json, io_definition.json, domain-analysis.md. Port names in io_definition.json must use i_/o_/io_ prefix convention, clocks as {domain}_clk, resets as {domain}_rst_n.")

# --- Phase 1→2 Quality Gate ---
Task(subagent_type="rtl-agent-team:spec-analyst",
     prompt="READ-ONLY self-review. Read requirements.json you produced. Verify:
1. Every functional requirement is traceable to a specific section in specs/.
2. No contradictions or ambiguities exist between requirements.
3. All interface constraints (protocols, timing) are explicitly stated.
4. io_definition.json port naming follows i_/o_/io_ prefix, {domain}_clk/{domain}_rst_n.
Produce a Feature Coverage Checklist mapping each spec section to its requirement(s).
Save your review result to reviews/phase-1-research/research-review.md in this format:
  # Phase 1 Review: Research Completeness
  - Date: (today)
  - Reviewer: spec-analyst
  - Upper Spec: specs/
  - Verdict: PASS | FAIL
  ## Feature Coverage Checklist
  (per spec section to REQ mapping)
  ## Findings
  ### [severity] Finding-N: ...
  ## Verdict
  PASS | FAIL: [reason]
verdict: PASS or FAIL + findings[]")

Task(subagent_type="rtl-agent-team:arch-designer",
     prompt="READ-ONLY feasibility review. Read requirements.json and io_definition.json.
Evaluate each requirement for RTL implementation feasibility:
1. Can every functional requirement be realized in synthesizable RTL?
2. Are clock frequency, area, and power constraints realistic?
3. Are there missing constraints that would block architecture design?
4. Flag any requirement that is ambiguous or under-specified for implementation.
verdict: PASS or FAIL + findings[]")

# ============================================================
# Phase 2: Architecture + Reference Model (parallel + 3-round iterative review)
# ============================================================
Bash("mkdir -p reviews/phase-2-architecture .rtl-agent-team/scratch/phase-2")

# Parallel: architecture design + reference model development
Skill(skill="rtl-agent-team:arch-design")    # Handles 3-round iterative review internally
Skill(skill="rtl-agent-team:ref-model")      # C golden model (functional, no clock/reset)

# Synthesizability pre-assessment (parallel with arch-design Round 1)
Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="READ-ONLY synthesizability pre-assessment. Read architecture.md.
Evaluate: synthesis-difficult patterns, CDC strategy, memory sizing, combinational loop risks.
verdict: PASS or FAIL + findings[]")

# Phase 2→3 Quality Gate: verify arch-design produced PASS verdict
# Check: reviews/phase-2-architecture/architecture-review.md verdict=PASS
# Check: reviews/phase-2-architecture/feature-coverage.md 100% coverage
# Clean up scratch: rm -rf .rtl-agent-team/scratch/phase-2/

# ============================================================
# Phase 3: μArch + BFM (parallel + 3-round iterative review)
# ============================================================
Bash("mkdir -p reviews/phase-3-uarch .rtl-agent-team/scratch/phase-3")

# Parallel: μArch design + BFM development
Skill(skill="rtl-agent-team:rtl-uarch-design")   # Handles 3-round iterative review internally
Skill(skill="rtl-agent-team:bfm-develop")    # SystemC TLM BFMs

# Phase 3→4 Quality Gate: verify rtl-uarch-design produced PASS verdict
# Check: reviews/phase-3-uarch/uarch-review.md verdict=PASS
# Check: reviews/phase-3-uarch/feature-preservation.md 100% preserved
# Clean up scratch: rm -rf .rtl-agent-team/scratch/phase-3/

# ============================================================
# Phase 4: RTL Implementation (parallel per module)
# ============================================================
Bash("mkdir -p reviews/phase-4-rtl")

Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Implement rtl/{module}/{module}.sv from docs/phase-3-uarch/{module}.md. Use logic only (no reg/wire), i_/o_ port prefix, {domain}_clk/{domain}_rst_n, u_ instances, gen_ generates. Run lint after writing.")

# --- Stream B: Early Verification Framework (parallel with Stream A) ---
Task(subagent_type="rtl-agent-team:sva-extractor",
     prompt="Generate SVA property skeletons from docs/phase-3-uarch/*.md. Extract: FSM state assertions, protocol handshake properties, signal range constraints. Write skeleton bind files to sim/formal/. These are structural skeletons — actual RTL signal bindings will be completed in Phase 5a.",
     run_in_background=true)

Task(subagent_type="rtl-agent-team:cdc-checker",
     prompt="Analyze clock domain topology from docs/phase-3-uarch/*.md. Identify: clock domain boundaries, synchronizer requirements, crossing points. Generate preliminary CDC report. This will be updated with actual RTL in Phase 5b.",
     run_in_background=true)

Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Generate cocotb TB skeletons from docs/phase-3-uarch/*.md at sim/. Include: port connectivity structure, clock/reset generation, test vector scaffolds. Mark as SKELETON — full test logic deferred to Phase 5c. Use dut.sys_clk, dut.sys_rst_n, dut.i_*/dut.o_* signal naming.",
     run_in_background=true)

# --- Phase 4→5 Quality Gate ---
Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="READ-ONLY RTL design review. Read requirements.json, then read docs/phase-3-uarch/*.md, then read rtl/*/*.sv.
Perform the following checks:
1. **Functional Coverage Matrix**: For EVERY requirement in requirements.json, trace:
   requirement → uarch section → RTL module and approximate line range.
   Mark each requirement as IMPLEMENTED or MISSING. Any MISSING → FAIL.
   Save the functional completeness report to reviews/phase-4-rtl/functional-completeness.md in this format:
     # Phase 4 Review: Functional Completeness
     - Date: (today)
     - Reviewer: rtl-critic
     - Upper Spec: requirements.json, docs/phase-3-uarch/*.md
     - Verdict: PASS | FAIL
     ## Feature Coverage Checklist
     | REQ ID | uarch Section | RTL Module | Lines | Status |
     |--------|--------------|------------|-------|--------|
     ## Findings
     ## Verdict
2. **Code quality**: Proper FSM coding (enum states), no inferred latches, clean synchronous reset.
3. **Synthesizability**: No non-synthesizable constructs (#delay, initial in synth code),
   appropriate clock gating, no combinational loops.
4. **Coding convention compliance**: i_/o_ port prefix, {domain}_clk/{domain}_rst_n,
   u_ instance prefix, gen_ generate prefix, logic only (no reg/wire),
   always_ff/always_comb (no always @*), ANSI port style.
5. **Hierarchical compliance**: Does RTL add, remove, or alter any functionality
   compared to docs/phase-3-uarch/*.md? Unauthorized deviation → FAIL.
Save the full design review to reviews/phase-4-rtl/design-review.md in standard review Markdown format.
Output the Functional Coverage Matrix table, then:
verdict: PASS or FAIL + findings[]")

Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Run full lint on rtl/*/*.sv. Zero errors required. Review warnings for false positives. Report lint summary.
Save the lint report to reviews/phase-4-rtl/lint-report.md in this format:
  # Phase 4 Review: Lint Report
  - Date: (today)
  - Reviewer: lint-checker
  - Upper Spec: rtl/*/*.sv
  - Verdict: PASS | FAIL
  ## Findings
  ### [severity] Finding-N: ...
  ## Verdict
  PASS (0 errors, warnings reviewed) | FAIL: [error summary]
verdict: PASS (0 errors, warnings reviewed) or FAIL + error list[]")

# ============================================================
# Phase 5: Extensive Verification (Sub-Phases)
# ============================================================
Bash("mkdir -p reviews/phase-5-verify")

# --- Phase 5a: SVA + Formal (parallel start) ---
Task(subagent_type="rtl-agent-team:sva-extractor",
     prompt="Complete SVA properties using Stream B skeletons (sim/formal/, docs/phase-4-rtl/stream-b-sva-skeletons.md) + actual RTL (rtl/*/*.sv). Add RTL-specific signal bindings to skeletons. Follow systemverilog-assertion conventions.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run SymbiYosys formal verification on all SVA bind files in sim/formal/. Report counterexamples if any. Save results to reviews/phase-5-verify/formal-review.md in standard review Markdown format. verdict: PASS or FAIL + counterexamples[]")

# --- Phase 5b: CDC Analysis (parallel with 5a) ---
Task(subagent_type="rtl-agent-team:cdc-checker",
     prompt="Update preliminary CDC report (docs/phase-4-rtl/stream-b-cdc-preliminary.md) with final RTL (rtl/*/*.sv). Compare Stream B CDC predictions vs actual implementation. Verify synchronizers exist where Stream B identified crossing points. Save to reviews/phase-5-verify/cdc-report.md in standard review Markdown format. verdict: PASS or FAIL + findings[]")

# --- Phase 5c: Integration TB + Ref Model (parallel with 5a/5b) ---
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Complete cocotb TB skeletons from Stream B (docs/phase-4-rtl/stream-b-tb-skeletons.md) with actual test logic. Create integration testbench at sim/top/. Test end-to-end data flow through all modules. Include ref_model comparison for bitexact verification.")

Task(subagent_type="rtl-agent-team:func-verifier",
     prompt="Run cocotb integration tests with per-module parallelism and multi-seed (seeds: 1, 42, 123, 1337, 65536) against ref_model. Each module runs as an independent parallel task with run_in_background=true. 5 seeds × N modules = up to 5N parallel sim tasks.
After regression completes, produce a Requirement Traceability Matrix and save it to
reviews/phase-5-verify/requirement-traceability.md in this format:
  # Phase 5 Review: Requirement Traceability
  - Date: (today)
  - Reviewer: func-verifier
  - Upper Spec: requirements.json
  - Verdict: PASS | FAIL
  ## Feature Coverage Checklist
  | REQ ID | Test Name | Result | Status |
  |--------|-----------|--------|--------|
  ## Findings
  ## Verdict
  PASS | FAIL: [reason]
verdict: PASS or FAIL + findings[]")

# --- Phase 5d: Coverage Analysis (after 5a-5c) ---
Task(subagent_type="rtl-agent-team:coverage-analyst",
     prompt="Analyze line/toggle/FSM coverage from simulation results. Identify coverage gaps below target. Save to reviews/phase-5-verify/coverage-report.md in standard review Markdown format. If coverage < target, list specific uncovered areas for testbench-dev to address. verdict: PASS or FAIL + gap list[]")

# --- Phase 5e: Final Compliance Review (after 5a-5d) ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="READ-ONLY final spec compliance review. Read requirements.json, io_definition.json, architecture.md, rtl/*/*.sv, and ALL Phase 5 review results (formal-review.md, cdc-report.md, requirement-traceability.md, coverage-report.md).
Perform the FINAL end-to-end audit:
1. **Final Compliance Matrix**: For EVERY requirement in requirements.json, confirm:
   - (a) It is implemented in RTL (cite module and mechanism)
   - (b) At least one verification test covers it (cite test name)
   - (c) That test PASSED in the latest run
   Mark each requirement: VERIFIED / IMPLEMENTED-BUT-UNTESTED / MISSING.
   Any MISSING or IMPLEMENTED-BUT-UNTESTED → FAIL.
2. **Interface completeness**: All io_definition.json ports present and connected?
3. **Untested paths**: Any RTL functionality without verification coverage?
4. **Spec fidelity**: Has implementation drifted from original spec?
Save to reviews/phase-5-verify/final-compliance.md in standard review Markdown format.

5. **End-to-End Traceability Matrix**: Read and unify the 4 segmented traceability artifacts:
   - reviews/phase-2-architecture/feature-coverage.md (REQ → Arch)
   - reviews/phase-3-uarch/feature-preservation.md (Arch → μArch)
   - reviews/phase-4-rtl/functional-completeness.md (REQ → μArch → RTL)
   - reviews/phase-5-verify/requirement-traceability.md (REQ → Test → Result)
   Produce a unified matrix with columns:
   | REQ ID | Spec Section | Arch Block | μArch Module | RTL File:Line | Test Name | Result |
   Save to reviews/phase-5-verify/e2e-traceability.md in standard review Markdown format.
   Any row with a gap (empty cell) in the chain → flag as TRACEABILITY_GAP.

verdict: PASS or FAIL + findings[]")

# --- Phase 5→4 Feedback Loop (parallel UNIT_FIX) ---
# 1. Collect ALL FAIL results from 5a, 5b, 5c
# 2. Classify each: UNIT_FIX | INTEGRATION_FIX | DESIGN_FIX
# 3. Batch UNIT_FIX: group by module, launch parallel fixes for different modules
# 4. INTEGRATION_FIX → sequential rtl-bugfix
# 5. DESIGN_FIX → STOP and escalate to user
# 6. After all fixes: re-run affected sub-phases in parallel
# 7. Max 2 feedback loops per sub-phase
#
# Example: Parallel UNIT_FIX across sub-phases
# Phase 5a FAIL: SVA counterexample in module_a (UNIT_FIX)
# Phase 5c FAIL: cocotb assertion error in module_b (UNIT_FIX)
# → Different modules → parallel fix:
# Skill(skill="rtl-agent-team:rtl-bugfix",
#        args="Phase 5a formal FAIL in module_a. Counterexample: [details]. feedback_origin=5a-formal",
#        run_in_background=true)
# Skill(skill="rtl-agent-team:rtl-bugfix",
#        args="Phase 5c cocotb FAIL in module_b. Assertion: [details]. feedback_origin=5c-integration",
#        run_in_background=true)
# → After both fix: re-run 5a + 5c in parallel

# Gate Failure Handling: see references/gate-failure-handling.md for examples

# ============================================================
# Phase 6: Design Review & Documentation (2-wave parallel)
# ============================================================
Bash("mkdir -p reviews/phase-6-review")

# --- Phase 5→6 Artifact Gate ---
Read("reviews/phase-5-verify/final-compliance.md")
# → Verify verdict=PASS. If FAIL or missing → STOP.

# --- Wave 1: Code Quality + Design Quality (parallel) ---
Task(subagent_type="rtl-agent-team:code-quality-reviewer",
     model="opus",
     prompt="Perform intensive per-module code quality review for Phase 6.
Read requirements.json, docs/phase-3-uarch/*.md for context. Read ALL rtl/*/*.sv.
Read reviews/phase-4-rtl/design-review.md for prior findings.
Score each module on 5 dimensions (1-10). Detect anti-patterns. Assess cross-module consistency.
Save to reviews/phase-6-review/code-review.md.")

Task(subagent_type="rtl-agent-team:design-quality-reviewer",
     model="opus",
     prompt="Perform cross-phase design quality review for Phase 6.
Read ALL artifacts: requirements.json → architecture.md → docs/phase-3-uarch/*.md → rtl/*/*.sv.
Build hierarchical consistency matrix. Document design decisions. Assess interface quality.
Evaluate scalability. Inventory design debt. Classify Phase 5 bugs.
Save to reviews/phase-6-review/design-review.md.")

# Wait for Wave 1 completion

# --- Wave 2: Design Note + Improvement Analysis (parallel, after Wave 1) ---
Task(subagent_type="rtl-agent-team:design-note-writer",
     model="opus",
     prompt="Write comprehensive design note for Phase 6.
Read ALL artifacts and Phase 6 reviews (code-review.md, design-review.md).
Document each module: purpose, I/O, structure (Mermaid), algorithm, FSM, timing, edge cases.
Document system integration: data flow, control flow, modes, reset.
Save to reviews/phase-6-review/design-note.md.")

Task(subagent_type="rtl-agent-team:improvement-analyst",
     model="opus",
     prompt="Produce prioritized improvement recommendations for Phase 6.
Read Phase 6 reviews (code-review.md, design-review.md) and Phase 4/5 reviews.
Build Impact×Effort matrix. Highlight Quick Wins. Specify WHERE/WHAT/HOW for each.
Build long-term improvement roadmap.
Save to reviews/phase-6-review/improvements.md.")

# Wait for Wave 2 completion

# --- Phase 6 Completion Gate ---
# Bash("ls reviews/phase-6-review/code-review.md reviews/phase-6-review/design-review.md reviews/phase-6-review/design-note.md reviews/phase-6-review/improvements.md")
```
</Tool_Usage>

<Examples>
<Good>
User: "autopilot: implement H.264 CABAC encoder from spec"
→ Writes state file, runs Phase 1 (research). Artifact Gate: requirements.json exists. Quality Gate:
  spec-analyst self-reviews completeness (PASS), arch-designer checks feasibility (PASS).
  Proceeds to Phase 2. Architecture produced. Quality Gate: rtl-architect runs Feature Coverage
  Checklist — finds "arithmetic coding bypass mode" missing from architecture (FAIL).
  Passes findings to arch-designer for fix. Arch-designer adds bypass mode. Re-run Quality Gate (PASS).
  Continues through all phases. Phase 5 final Quality Gate produces Final Compliance Matrix: all
  requirements VERIFIED. Removes state file, reports summary.
</Good>
<Good>
Quality Gate detects upper-spec violation:
→ Phase 3→4 Quality Gate: rtl-architect finds docs/phase-3-uarch/entropy_coder.md changed the context table
  size from 460 (architecture.md) to 256 for "area savings". This is an upper-spec violation.
  IMMEDIATE STOP. Reports: "μArch altered Architecture decision: context table size 460→256.
  This violates Hierarchical Spec Compliance." Waits for user approval before proceeding.
</Good>
<Good>
Phase 5→4 Feedback Loop:
→ Phase 5a formal verification finds SVA counterexample in cabac_encoder.sv.
  Classified as UNIT_FIX (single module). Invokes rtl-bugfix with feedback_origin=5a-formal.
  rtl-coder fixes the logic error. lint-checker verifies. testbench-dev updates unit TB.
  eda-runner re-runs unit sim (PASS). Returns to Phase 5a: re-run formal (PASS).
  feedback_loops incremented to 1. Pipeline continues to Phase 5b.
</Good>
<Good>
Phase 5→4 DESIGN_FIX escalation:
→ Phase 5c integration test shows throughput 50% below spec. Classified as DESIGN_FIX —
  pipeline architecture needs rework. IMMEDIATE STOP. Reports to user:
  "Integration test reveals throughput gap. μArch pipeline depth may need increase from 3 to 5 stages."
  Waits for user approval before returning to Phase 3 (μArch).
</Good>
<Bad>
User: "quickly sketch a block diagram"
→ Do NOT invoke rtl-autopilot. Use arch-design or domain-consult directly.
</Bad>
<Bad>
Quality Gate returns FAIL but pipeline proceeds anyway:
→ NEVER skip a Quality Gate verdict. FAIL means the phase must be fixed before proceeding.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- **Artifact Gate fails twice** → pause and report missing artifacts to user
- **Quality Gate fails after 2 fix-and-retry cycles** → pause, present all accumulated findings to user, request guidance
- **Upper-Spec Violation detected at any Quality Gate** → IMMEDIATE STOP:
  1. Identify the violated upper phase and the specific violation
  2. Report to user with full context (which requirement/feature, how it was violated)
  3. DO NOT proceed — wait for user to approve rollback or waiver
  4. If approved, return to the appropriate upper phase and re-run from there
- **Phase 5→4 Feedback Loop exhausted** (2 cycles per sub-phase) → escalate to user with accumulated FAIL findings
- **Phase 5 DESIGN_FIX detected** → IMMEDIATE STOP, report upper-spec violation, wait for user approval
- **Verification phase fails after 2 retries** → invoke rtl-bug-repro skill, report findings
- **User says "cancel" or "stop"** → delete .rtl-agent-team/state/rtl-autopilot-state.json, report progress summary
</Escalation_And_Stop_Conditions>

<Parallel_Execution_Pattern>
Phase 4-5 use dependency-aware parallel execution patterns:

**Phase 4 parallel streams:**
- Stream A (RTL coding, wave-based) + Stream B (early verification): independent, run in parallel
- Stream B sub-tasks (SVA + CDC + TB skeletons): independent, run in parallel via `run_in_background: true`
- Merge point at Phase 4→5 Gate requires both streams complete

**Phase 5 sub-phases:**
- 5a (formal) + 5b (CDC) + 5c (integration): independent, run in parallel via `run_in_background: true`
- 5d (coverage): starts incrementally as modules complete 5a-5c (partial dependency)
- 5e (design review): requires ALL of 5a-5d complete (full dependency)

**Phase 5→4 feedback:**
- Parallel UNIT_FIX across different modules with `run_in_background: true`
- Sequential INTEGRATION_FIX (cross-module dependencies)
- After all fixes: re-run ONLY affected sub-phases in parallel

**Phase 6 waves:**
- Wave 1: `code-quality-reviewer` + `design-quality-reviewer` in parallel via `run_in_background: true`
- Wave 2 (after Wave 1): `design-note-writer` + `improvement-analyst` in parallel

**Task tool usage:**
- Use `run_in_background: true` for independent sub-tasks within a wave
- Wait for all background tasks before dependent phases
- Collect results via TaskOutput before proceeding
</Parallel_Execution_Pattern>

<Final_Checklist>
- [ ] State file written before starting
- [ ] Each phase passed BOTH Artifact Gate AND Quality Gate before proceeding
- [ ] **Hierarchical Spec Compliance** verified at every Quality Gate:
  - Phase 1→2: requirements are complete, consistent, and implementable
  - Phase 2→3: architecture covers 100% of requirements (Feature Coverage Checklist PASS) + 3-round iterative review converged (memory, performance, ref model consistency)
  - Phase 3→4: μArch preserves 100% of architecture features (Feature Preservation Checklist PASS) + 3-round iterative review converged (performance, interface, memory optimization)
  - Phase 4→5: RTL implements 100% of requirements (Functional Coverage Matrix PASS) + lint-clean + all unit tests PASS + basic integration PASS
  - Phase 4 Stream B: SVA skeletons, preliminary CDC report, TB skeletons generated
  - Phase 4: phase-4-summary.md generated
  - Phase 5 multi-seed regression: 5 seeds per module passed
  - Phase 5→4 feedback: UNIT_FIX failures in different modules fixed in parallel
  - Phase 5e: reviews/phase-5-verify/e2e-traceability.md exists (unified end-to-end traceability matrix)
  - Phase 5 final: every requirement is implemented, verified, and passing (Final Compliance Matrix PASS)
  - Phase 5: phase-5-summary.md generated
- [ ] No upper-spec violations were left unresolved
- [ ] Naming conventions enforced at every phase gate:
  - io_definition.json: `i_`/`o_`/`io_` prefix, `{domain}_clk`/`{domain}_rst_n`
  - architecture.md: data path names, clock/reset domain naming
  - docs/phase-3-uarch/*.md: all signal names, FSM states, instance prefixes
  - rtl/*/*.sv: lint-clean, naming compliant
- [ ] All 6 phases completed
- [ ] State file removed on clean completion
- [ ] Summary report generated with Final Compliance Matrix and Phase 6 deliverables
- [ ] **Review artifacts verified**: Read `references/review-checklist.md` and confirm all 26 mandatory files exist (+ 1 optional Phase 7)
</Final_Checklist>

<Advanced>
**Resume Protocol (5 steps):**

1. **Read**: Load `.rtl-agent-team/state/rtl-autopilot-state.json`. If missing, start fresh (Step 1).
2. **Migrate**: If `schema_version` is absent or `"1.0"`, upgrade to v2.0 schema in-place:
   - Add missing top-level fields (`current_phase_name`, `interrupted_reason`, `partial_work_summary`)
   - Add missing per-phase fields (`started_at`, `completed_at`, `gate_passed_at`, `review_rounds_completed`, `partial_work`)
   - Add phase-specific fields (Phase 4: streams/modules, Phase 5: sub-phases/fix_history, Phase 6: waves)
   - Write migrated state back to disk immediately
3. **Skip**: Iterate phases in order (1→6). For each phase with `status == "completed"` AND `gate_passed_at != null`, mark as skipped — do not re-execute.
4. **Resume**: For the first phase with `status == "in_progress"`:
   - Read `partial_work.completed_items` — these are done, do not redo
   - Read `partial_work.pending_items` — these need execution
   - Read `review_rounds_completed` — if iterative review was partial (e.g., 1 of 3), resume from next round
   - Phase 4: check `stream_a_status`/`stream_b_status` and `completed_modules`/`pending_modules`
   - Phase 5: check `completed_sub_phases`/`pending_sub_phases` and `fix_history`
   - Phase 6: check `completed_waves` and `current_wave`
5. **Context Load**: Read upstream documents for the resumed phase using the Context Manifest
   (`templates/context-manifest-phase-{N}.json`). Load `required_full_read` files first,
   then `required_summary_only` (via phase summary docs), skip `optional_on_demand`.

After successful resume, clear `interrupted_reason` and `partial_work_summary`.

Parallel phases (2 and 3) use separate state sub-keys to track each sub-task independently.
Templates: `templates/autopilot-state.json` (state file), `templates/review-report.md` (gate reports).
Templates: `templates/context-manifest-phase-{1..6}.json` (per-phase context manifests).
See `references/gate-failure-handling.md` for gate retry flow and upper-spec violation handling.
</Advanced>
