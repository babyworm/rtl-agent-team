---
name: rtl-spec-to-uarch
description: "This skill should be used when completing design documents from spec through microarchitecture (Phase 1→3). Produces research artifacts, block architecture, reference model, microarchitecture specs, and BFM with full quality gates and 3-round iterative reviews — stopping before RTL implementation for human review."
---

<Purpose>
Drive the RTL design pipeline through Phases 1→3 (Research → Architecture → μArch) with enforced dual-layer phase gates, then STOP for human review before RTL implementation.

This skill produces all design documents needed to begin RTL coding, without generating any RTL code.
It is the "design half" of the pipeline, intended for workflows where:
- A human architect reviews the μArch before proceeding to RTL
- The design documents are handed off to a separate team for implementation
- Iterative design exploration is needed before committing to implementation

**Hierarchical Spec Compliance Principle:**
Lower phases MUST NOT violate upper phase specifications:
  Spec → Architecture → μArch
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
to ALL downstream phases. Time is NOT a constraint at upper levels — it is better to spend
extra review rounds perfecting architecture than to discover fundamental issues during RTL.

Graduated iteration by abstraction level:
  Phase 1 (Research): 3 mandatory rounds (existing — chief-coordinated)
  Phase 2 (Architecture): 3 mandatory rounds — memory, performance, ref model consistency
  Phase 3 (μArch): 3 mandatory rounds — performance, interface, memory optimization

Iteration count can be increased beyond 3 if convergence is not achieved.
The principle: **refine thoroughly at the top, execute efficiently at the bottom.**

**Document-as-Memory Principle:**
Design artifacts (docs/, reviews/) serve as persistent memory across phases and agents.
Each phase reads upstream documents as input context and writes downstream documents as output.
This eliminates direct agent-to-agent state coupling and enables resumability — any phase can
restart by re-reading its input documents.

State is persisted at .rtl-agent-team/state/rtl-spec-to-uarch-state.json for resumability.
</Purpose>

<Use_When>
- Completing design documents (Spec → μArch) before human review
- The design team wants to review architecture/μArch before committing to RTL implementation
- Separating design exploration from implementation for iterative refinement
- Creating a complete design package for handoff to an implementation team
</Use_When>

<Do_Not_Use_When>
- Full end-to-end automation is needed (use rtl-autopilot instead)
- Only a single phase needs to run (use the phase-specific skill: p1-spec-research, p2-arch-design, rtl-p3-uarch-design)
- RTL implementation is needed (use rtl-uarch-to-verify for Phase 4→5)
- Design documents already exist and only RTL coding is needed
</Do_Not_Use_When>

<Why_This_Exists>
In practice, RTL design teams rarely go from spec to RTL in a single uninterrupted run.
Design review checkpoints between μArch and RTL are standard industry practice because:
- Architecture decisions are expensive to change after RTL coding begins
- Human architects bring domain expertise that improves μArch quality
- Design documents serve as the contract between design and implementation teams
- Iterative exploration at the architecture level prevents costly RTL rework

This skill provides the "design half" of rtl-autopilot, producing all artifacts needed
for rtl-uarch-to-verify to begin RTL implementation.
</Why_This_Exists>

<Execution_Policy>
- State file (.rtl-agent-team/state/rtl-spec-to-uarch-state.json) tracks progress for resumability
- Independent sub-tasks within a phase run in parallel via concurrent Task() calls
- **Dual-Layer Phase Gates** are hard stops between every phase:
  1. **Artifact Gate**: Required files/directories exist (fast check)
  2. **Quality Gate**: Reviewer agent(s) verify quality AND hierarchical spec compliance
- Quality Gate verdicts are structured: `PASS` or `FAIL + findings[]`
- On Artifact Gate failure: retry the failed phase once, then escalate to user
- On Quality Gate failure: pass findings back to the phase's worker agent for correction, then re-run Quality Gate
- **On upper-spec violation**: return to the violated upper phase (e.g., Architecture violates Spec → return to Phase 1). Report violation to user and DO NOT proceed without approval
- Maximum 2 Quality Gate retry cycles per phase before escalating to user
- On interruption: state file is preserved with detailed context for resumability
- **Context Manifest**: Each phase has a manifest (`templates/context-manifest-phase-{N}.json`) that declares required_full_read, required_summary_only, and optional_on_demand files
- **Scratchpad for intra-phase communication**: During iterative reviews, agents write findings to `.rtl-agent-team/scratch/phase-{N}/` as temporary working files
- **Termination**: After Phase 3 Quality Gate PASS, generate summary + ADR, then STOP. Do NOT proceed to Phase 4
</Execution_Policy>

<Steps>
1. **Initialize state**: write .rtl-agent-team/state/rtl-spec-to-uarch-state.json with phase=1, sub_phase=null, feedback_loops=0, max_feedback_loops=2, pipeline_scope="phase-1-to-3"

1.5. **Resume check** (if state file already exists):
   - Read `.rtl-agent-team/state/rtl-spec-to-uarch-state.json`
   - **Schema migration**: if `schema_version` is missing or `"1.0"`, migrate to v2.0:
     - Add `schema_version: "2.0"`, `current_phase`, `current_phase_name`, `interrupted_reason`, `partial_work_summary`
     - Add per-phase fields: `started_at`, `completed_at`, `gate_passed_at`, `review_rounds_completed`, `partial_work`
   - **Skip completed phases**: for each phase where `status == "completed"` AND `gate_passed_at != null`, skip entirely
   - **Resume in-progress phase**: read `partial_work.completed_items` to determine what is already done
     - Skip completed items, continue from `partial_work.current_action`
     - Resume review rounds from `review_rounds_completed` (e.g., if 1 of 3 rounds done, start at round 2)
   - **Context reload**: read upstream documents for the resumed phase per Context Manifest
   - Clear `interrupted_reason` and `partial_work_summary` after successful resume

---

2. **Phase 1 — Research**: invoke p1-spec-research skill
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

   **Phase 1→2 Summary Validation**:
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

   invoke p2-arch-design and ref-model skills concurrently
   - arch-designer + ref-model-dev produce initial artifacts concurrently
   - architecture.md interface tables must use `i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n` naming
   - **Review artifacts setup**: `mkdir -p reviews/phase-2-architecture .rtl-agent-team/scratch/phase-2`
   - **Cascading Quality: 3-round mandatory iterative review** coordinated by rtl-architect:
     - Parallel reviewers each round:
       (a) `rtl-architect`: spec compliance (Feature Coverage Checklist) + structural review
       (b) `vcodec-architecture-expert`: memory access patterns, performance analysis (SRAM sizing, bandwidth, access conflicts)
       (c) `ref-model-dev`: architecture <-> C model consistency (block mapping, data flow, interface alignment)
     - Round 1-2: review -> targeted feedback -> revision (only experts with findings re-run)
     - Round 3 mandatory even if converged: cross-block interface audit + memory conflict analysis + ref model code review
     - After 3 rounds if not converged -> escalate to user via AskUserQuestion
     - User may request additional rounds beyond 3 ("set iterations to N")
   - `rtl-critic` performs synthesizability pre-assessment (parallel with Round 1)

   **Phase 2→3 Artifact Gate**: architecture.md + block_diagram + refc/*/*.c exist

   **Phase 2→3 Quality Gate (Architecture Review)**:
   - 3-round iterative review converged (or gaps escalated and user-approved)
   - **Feature Coverage Checklist**: 100% of REQ-NNN mapped to architecture blocks
     - **Save checklist to `reviews/phase-2-architecture/feature-coverage.md`** in standard review Markdown format
   - Memory access review PASS: all large blocks have viable memory strategy
   - Architecture <-> ref model consistency PASS: block mapping + data flow + interface alignment
   - Ref model code review: quality, bitexact correctness verified
   - **Architecture Diagram**: Save D2 block diagram to `reviews/phase-2-architecture/architecture-diagram.md`
   - Per-round review artifacts: architecture-review-r1.md, r2.md, r3.md
   - **Save consolidated review to `reviews/phase-2-architecture/architecture-review.md`** in standard review Markdown format
   - **Verdict**: PASS if Spec feature coverage is 100% AND no structural defects AND iterative review converged; FAIL + findings otherwise

   **Phase 2 Summary Generation** (after Quality Gate PASS, before Phase 3 starts):
   - Delegate to `rtl-architect` (model=sonnet): read all Phase 2 artifacts and generate
     `docs/phase-2-architecture/phase-2-summary.md` using `templates/phase-summary.md` format.
   - This summary is used by Phase 4+ as compressed context via `required_summary_only`.

   **Phase 2→3 Summary Validation**:
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

   invoke rtl-p3-uarch-design and bfm-develop skills concurrently
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
     - After 3 rounds if not converged -> escalate to user via AskUserQuestion
     - User may request additional rounds beyond 3

   **Phase 3 Artifact Gate**: docs/phase-3-uarch/*.md + bfm/ directory exist

   **Phase 3 Quality Gate (μArch Review)**:
   - 3-round iterative review converged (or gaps escalated and user-approved)
   - **Feature Preservation Checklist**: 100% of architecture features preserved in μArch
     - **Save checklist to `reviews/phase-3-uarch/feature-preservation.md`** in standard review Markdown format
   - Block boundary alignment: 1:1 correspondence with architecture.md
   - Memory access optimization PASS: SRAM banking, port conflicts, access scheduling reviewed
   - μArch <-> ref model consistency PASS: behavior, data widths, fixed-point formats aligned
   - **Pipeline Diagram**: Save Mermaid pipeline diagram to `reviews/phase-3-uarch/pipeline-diagram.md`
   - Per-round review artifacts: uarch-review-r1.md, r2.md, r3.md
   - **Save consolidated review to `reviews/phase-3-uarch/uarch-review.md`** in standard review Markdown format
   - **Verdict**: PASS if architecture is fully and faithfully decomposed into μArch with no feature loss AND timing paths are reasonable AND iterative review converged; FAIL + findings otherwise

   **Phase 3 Summary Generation** (after Quality Gate PASS):
   - Delegate to `rtl-architect` (model=sonnet): read all Phase 3 artifacts and generate
     `docs/phase-3-uarch/phase-3-summary.md` using `templates/phase-summary.md` format.
   - This summary is used by Phase 5+ as compressed context via `required_summary_only`.

   **Phase 3 Summary Validation:**
   - Verify `docs/phase-3-uarch/phase-3-summary.md` exists
   - If missing: delegate to `rtl-architect` (model=sonnet) to generate from Phase 3 artifacts
   - Summary must follow `templates/phase-summary.md` format

   **Phase 3 ADR Recording** (after summary):
   - Delegate to `uarch-designer` (model=sonnet): identify 3-5 key μArch decisions made
     during Phase 3 (e.g., pipeline depth, SRAM banking strategy, FSM decomposition, handshake protocol).
   - For each decision, create `docs/decisions/ADR-{NNN}.md` using `templates/adr-template.md` format.
   - Link each ADR to relevant architecture.md sections and upstream Phase 2 ADRs.

---

**Parallel Execution Pattern:**
Phase 2 iterative review runs parallel reviewers each round:
- `rtl-architect` + `vcodec-architecture-expert` + `ref-model-dev`: independent, parallel via `run_in_background: true`
- Wait for all background tasks before aggregating round feedback
- Collect results via TaskOutput before proceeding to next round or gate

Phase 3 iterative review similarly runs parallel reviewers:
- `rtl-architect` + `timing-advisor` + `vcodec-architecture-expert` + `ref-model-dev`: parallel
- Same wait/collect pattern as Phase 2

**Handoff Checklist (rtl-spec-to-uarch → rtl-uarch-to-verify):**
Before reporting completion, verify handoff readiness:
- [ ] Phase 3 summary exists: `docs/phase-3-uarch/phase-3-summary.md`
- [ ] All μArch specs exist: `docs/phase-3-uarch/{module}.md` for each module
- [ ] Phase 3 review passed: `reviews/phase-3-uarch/uarch-review.md` verdict=PASS
- [ ] Feature preservation verified: `reviews/phase-3-uarch/feature-preservation.md`
- [ ] State file updated: `.rtl-agent-team/rtl/{module}/phase-3-complete.json`
- [ ] Context manifest ready: `templates/context-manifest-phase-4.json` references valid files

---

5. **On completion**: update state file with all phases completed, report summary.

   **Completion Report** (presented to user):
   - Phase 1 artifacts: requirements.json, io_definition.json, domain-analysis.md
   - Phase 2 artifacts: architecture.md, refc/*/*.c, architecture-review.md (PASS)
   - Phase 3 artifacts: docs/phase-3-uarch/*.md, bfm/, uarch-review.md (PASS)
   - ADR count and key decisions
   - Next step: "Run `/rtl-agent-team:rtl-uarch-to-verify` to begin RTL implementation + verification"

   **Do NOT proceed to Phase 4.** The pipeline stops here for human review.

---

**Gate Failure Handling:**
- **Quality Gate FAIL (same-level fix)**: pass findings to the phase's worker agent for correction. Re-run Quality Gate after fix. Max 2 retry cycles per gate
- **Upper-Spec Violation detected**: STOP immediately. Identify which upper phase is violated. Return to the violated upper phase. Report violation details to user — DO NOT proceed without user approval
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
     prompt="READ-ONLY self-review. Read requirements.json you produced. Verify completeness and consistency.
Save review to reviews/phase-1-research/research-review.md.
verdict: PASS or FAIL + findings[]")

Task(subagent_type="rtl-agent-team:arch-designer",
     prompt="READ-ONLY feasibility review. Read requirements.json and io_definition.json.
Evaluate each requirement for RTL implementation feasibility.
verdict: PASS or FAIL + findings[]")

# Phase 1 Summary
Task(subagent_type="rtl-agent-team:rtl-architect", model="sonnet",
     prompt="Read all Phase 1 artifacts. Generate docs/phase-1-research/phase-1-summary.md.")

# ============================================================
# Phase 2: Architecture + Reference Model (parallel + 3-round review)
# ============================================================
Bash("mkdir -p reviews/phase-2-architecture .rtl-agent-team/scratch/phase-2")

# Parallel: architecture design + reference model development
Skill(skill="rtl-agent-team:p2-arch-design")    # 3-round iterative review internally
Skill(skill="rtl-agent-team:ref-model")      # C golden model

# Synthesizability pre-assessment (parallel with Round 1)
Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="READ-ONLY synthesizability pre-assessment. Read architecture.md.")

# Phase 2→3 Quality Gate
# Check: reviews/phase-2-architecture/architecture-review.md verdict=PASS
# Check: reviews/phase-2-architecture/feature-coverage.md 100% coverage
# Clean up scratch: rm -rf .rtl-agent-team/scratch/phase-2/

# Phase 2 Summary + ADR
Task(subagent_type="rtl-agent-team:rtl-architect", model="sonnet",
     prompt="Read all Phase 2 artifacts. Generate docs/phase-2-architecture/phase-2-summary.md.")
Task(subagent_type="rtl-agent-team:arch-designer", model="sonnet",
     prompt="Identify 3-5 key architectural decisions. Create ADRs in docs/decisions/.")

# ============================================================
# Phase 3: μArch + BFM (parallel + 3-round review)
# ============================================================
Bash("mkdir -p reviews/phase-3-uarch .rtl-agent-team/scratch/phase-3")

# Parallel: μArch design + BFM development
Skill(skill="rtl-agent-team:rtl-p3-uarch-design")   # 3-round iterative review internally
Skill(skill="rtl-agent-team:bfm-develop")         # SystemC TLM BFMs

# Phase 3 Quality Gate
# Check: reviews/phase-3-uarch/uarch-review.md verdict=PASS
# Check: reviews/phase-3-uarch/feature-preservation.md 100% preserved
# Clean up scratch: rm -rf .rtl-agent-team/scratch/phase-3/

# Phase 3 Summary + ADR
Task(subagent_type="rtl-agent-team:rtl-architect", model="sonnet",
     prompt="Read all Phase 3 artifacts. Generate docs/phase-3-uarch/phase-3-summary.md.")
Task(subagent_type="rtl-agent-team:uarch-designer", model="sonnet",
     prompt="Identify 3-5 key μArch decisions. Create ADRs in docs/decisions/.")

# ============================================================
# STOP — Pipeline ends here for human review
# ============================================================
# Report completion summary to user
# Suggest: "Run /rtl-agent-team:rtl-uarch-to-verify to begin RTL implementation"
```
</Tool_Usage>

<Examples>
**Example 1: New design from spec**
```
User: "specs/ 디렉토리에 UART 스펙이 있어. μArch까지 설계 문서를 완성해줘."
→ Invoke /rtl-agent-team:rtl-spec-to-uarch
→ Phase 1: Analyze UART spec → requirements.json, io_definition.json
→ Phase 2: Architecture design + C reference model (parallel) + 3-round review
→ Phase 3: μArch design + BFM (parallel) + 3-round review
→ STOP: "Phase 1-3 완료. μArch 문서를 검토 후 /rtl-agent-team:rtl-uarch-to-verify로 RTL 구현을 시작하세요."
```

**Example 2: Resume interrupted pipeline**
```
User: "이전에 중단된 설계를 이어서 진행해줘."
→ Read .rtl-agent-team/state/rtl-spec-to-uarch-state.json
→ Phase 1 completed, Phase 2 in-progress (round 2 of 3)
→ Resume Phase 2 from round 2
→ Continue to Phase 3
→ STOP after Phase 3 PASS
```

**Example 3: Design exploration**
```
User: "두 가지 아키텍처를 비교하고 싶어. 먼저 설계 문서만 만들어줘."
→ Invoke /rtl-agent-team:rtl-spec-to-uarch
→ Produces complete design documents through μArch
→ User reviews, compares, decides on architecture
→ User can re-run with different constraints or proceed to rtl-uarch-to-verify
```
</Examples>

<Escalation_And_Stop_Conditions>
- Phase 1 Quality Gate fails after 2 retries → ask user to clarify/refine spec
- Phase 2 Quality Gate fails after 2 retries → ask user for architecture direction
- Phase 3 Quality Gate fails after 2 retries → ask user for μArch decisions
- Upper-spec violation detected → STOP and report to user immediately
- Any phase cannot be completed due to missing information → use AskUserQuestion
</Escalation_And_Stop_Conditions>

<Final_Checklist>
Before reporting completion, verify ALL of the following:
- [ ] Phase 1: requirements.json, io_definition.json, domain-analysis.md exist
- [ ] Phase 1: reviews/phase-1-research/research-review.md verdict=PASS
- [ ] Phase 1: phase-1-summary.md generated
- [ ] Phase 2: architecture.md exists with proper naming conventions
- [ ] Phase 2: refc/*/*.c exists
- [ ] Phase 2: reviews/phase-2-architecture/architecture-review.md verdict=PASS
- [ ] Phase 2: reviews/phase-2-architecture/feature-coverage.md shows 100% coverage
- [ ] Phase 2: phase-2-summary.md generated
- [ ] Phase 2: ADRs recorded in docs/decisions/
- [ ] Phase 3: docs/phase-3-uarch/*.md exist (per-module μArch)
- [ ] Phase 3: bfm/ directory exists
- [ ] Phase 3: reviews/phase-3-uarch/uarch-review.md verdict=PASS
- [ ] Phase 3: reviews/phase-3-uarch/feature-preservation.md shows 100% preserved
- [ ] Phase 3: phase-3-summary.md generated
- [ ] Phase 3: ADRs recorded in docs/decisions/
- [ ] Scratch directories cleaned (phase-2, phase-3)
- [ ] State file updated with all phases completed
- [ ] Pipeline did NOT proceed to Phase 4

If ANY item is unchecked → DO NOT report completion. Fix the issue first.
</Final_Checklist>
