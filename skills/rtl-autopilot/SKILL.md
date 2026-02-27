---
name: rtl-autopilot
description: "This skill should be used when starting a full RTL design pipeline from spec to verification. Orchestrates 6-phase flow (Research → Architecture → μArch → RTL → Verify → Design Note) with dual-layer phase gates and hierarchical spec compliance."
---

<Purpose>
Drive the complete RTL design pipeline through five sequential phases with enforced dual-layer phase gates.
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
- On interruption: state file is preserved; re-invoking this skill resumes from last phase
</Execution_Policy>

<Steps>
1. **Initialize state**: write .rtl-agent-team/state/rtl-autopilot-state.json with phase=1, sub_phase=null, feedback_loops=0, max_feedback_loops=2

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

---

3. **Phase 2 — Architecture + Reference Model (parallel)**: invoke arch-design and ref-model skills concurrently
   - architecture.md interface tables must use `i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n` naming
   - **Review artifacts setup**: `mkdir -p reviews/phase-2-architecture`

   **Phase 2→3 Artifact Gate**: architecture.md + block_diagram + ref_model/src/*.cpp exist

   **Phase 2→3 Quality Gate (Architecture Review)**:
   - `rtl-architect` reviews architecture.md against requirements.json:
     - **Feature Coverage Checklist**: enumerate every functional requirement from requirements.json and confirm it is addressed in architecture.md. Flag any missing feature as FAIL
       - **Save checklist to `reviews/phase-2-architecture/feature-coverage.md`** in standard review Markdown format
     - Block decomposition: are blocks well-bounded with clear responsibilities?
     - Interface adequacy: do inter-block interfaces carry all required signals?
     - Port naming compliance: `i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n`
     - **Save full review to `reviews/phase-2-architecture/architecture-review.md`** in standard review Markdown format
   - **Architecture Diagram**: Save Mermaid block diagram to `reviews/phase-2-architecture/architecture-diagram.md`
     - Include a `graph TD` Mermaid diagram showing top-level block decomposition and connectivity
   - `rtl-critic` performs synthesizability pre-assessment:
     - Are there architectural patterns known to cause synthesis issues?
     - Clock domain crossing strategy defined where needed?
   - **Verdict**: PASS if Spec feature coverage is 100% AND no structural defects; FAIL + findings otherwise

---

4. **Phase 3 — μArch + BFM (parallel)**: invoke uarch-design and bfm-develop skills concurrently
   - uarch/*.md register/signal names must follow: `i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n`, `u_` instances, `gen_` generates
   - **Review artifacts setup**: `mkdir -p reviews/phase-3-uarch`

   **Phase 3→4 Artifact Gate**: uarch/*.md + bfm/ directory exist

   **Phase 3→4 Quality Gate (μArch Review)**:
   - `rtl-architect` reviews uarch/*.md against architecture.md:
     - **Block boundary alignment**: does each uarch document correspond 1:1 to an architecture block? Flag any split/merge that deviates from architecture.md
     - **Feature preservation**: for each feature assigned to a block in architecture.md, verify the corresponding uarch/*.md describes its implementation. Flag any feature dropped or altered
       - **Save feature preservation checklist to `reviews/phase-3-uarch/feature-preservation.md`** in standard review Markdown format
     - Pipeline depth and staging: is the proposed pipeline feasible for target frequency?
     - Timing path analysis: are there combinational paths that clearly violate timing?
     - Signal/register naming compliance with conventions
     - **Save full review to `reviews/phase-3-uarch/uarch-review.md`** in standard review Markdown format
   - **Pipeline Diagram**: Save Mermaid pipeline diagram to `reviews/phase-3-uarch/pipeline-diagram.md`
     - Include a `graph LR` Mermaid diagram showing pipeline stages and data flow
   - **Verdict**: PASS if architecture is fully and faithfully decomposed into μArch with no feature loss AND timing paths are reasonable; FAIL + findings otherwise

---

5. **Phase 4 — RTL Implementation**: invoke rtl-code skill (parallel per module)
   - Enforce: `logic` only (no `reg`/`wire`), `always_ff`/`always_comb`, ANSI port style
   - **Review artifacts setup**: `mkdir -p reviews/phase-4-rtl`

   **Phase 4→5 Artifact Gate**: rtl/src/*.sv exist and all lint-clean + tb/unit/tb_*.sv exist for all modules + sim/unit/*_results.txt exist and all PASS + basic integration smoke test PASS

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

---

6. **Phase 5 — Extensive Verification (Sub-Phases)**
   - **Review artifacts setup**: `mkdir -p reviews/phase-5-verify`
   - Phase 5 is structured into 5 sub-phases (some can run in parallel)
   - State tracking: uses `sub_phase`, `feedback_loops`, `max_feedback_loops` fields in `rtl-autopilot-state.json`

   **Phase 5a: SVA Generation + Formal Verification (parallel with 5b/5c)**
   - `sva-extractor`: generate SVA properties based on uarch/*.md
   - `eda-runner`: run formal verification with SymbiYosys
   - Output: `reviews/phase-5-verify/formal-review.md`

   **Phase 5b: CDC Analysis (parallel with 5a/5c)**
   - `cdc-checker`: analyze multiple clock domains
   - Output: `reviews/phase-5-verify/cdc-report.md`

   **Phase 5c: Integration TB + Ref Model Comparison (parallel with 5a/5b)**
   - `testbench-dev`: create cocotb integration TB
   - `func-verifier`: extensive RTL vs ref_model comparison
   - `eda-runner`: run cocotb regression (multiple seeds)
   - Output: `reviews/phase-5-verify/requirement-traceability.md`

   **Phase 5d: Coverage Analysis (after 5a-5c complete)**
   - `coverage-analyst`: analyze line/toggle/FSM coverage
   - If below target: `testbench-dev` generates additional tests
   - Output: `reviews/phase-5-verify/coverage-report.md`

   **Phase 5e: Extensive Design Review (after 5a-5d complete)**
   - `rtl-architect`: Final Compliance Matrix (end-to-end audit)
     - **Final Feature Completeness Audit**: re-read every requirement from requirements.json and confirm: (a) it is implemented in RTL, (b) it has at least one verification test covering it, (c) that test passed
     - Interface completeness: are all ports in io_definition.json present and connected in the top-level RTL?
     - Untested paths: identify any functionality that lacks verification coverage
   - `rtl-critic`: comprehensive design review
   - Output: `reviews/phase-5-verify/final-compliance.md`

   **Phase 5→4 Feedback Loop:**
   - When a FAIL is detected in a Phase 5 sub-phase, classify the FAIL type:
     - **UNIT_FIX**: resolvable by fixing a single module (e.g., SVA counterexample, assertion failure)
     - **INTEGRATION_FIX**: requires inter-module interface modification
     - **DESIGN_FIX**: requires architecture-level design change (→ user approval mandatory)
   - UNIT_FIX / INTEGRATION_FIX handling:
     1. Automatically invoke `rtl-bugfix` skill (with feedback_origin specified)
     2. Fix → lint → update unit TB → unit sim → confirm PASS
     3. Return to the corresponding Phase 5 sub-phase for re-verification
     4. Maximum 2 feedback loops per sub-phase (escalate to user if exceeded)
   - DESIGN_FIX handling:
     1. IMMEDIATE STOP — classified as upper-spec violation
     2. Report to user: violation details + impact scope + recommended action
     3. After user approval, return to Phase 3 (μArch) or Phase 2 (Architecture)

   **Phase 5 Completion Artifact Gate**: all verification sub-phases (5a-5e) pass

   **Phase 5 Completion Quality Gate (Final Spec Compliance Review)**:
   - `func-verifier` produces Requirement Traceability Matrix:
     - **Save to `reviews/phase-5-verify/requirement-traceability.md`** in standard review Markdown format
   - `rtl-architect` performs end-to-end review via Phase 5e results:
     - **Save final compliance review to `reviews/phase-5-verify/final-compliance.md`** in standard review Markdown format
   - **Verdict**: PASS if every original requirement is implemented, verified, and passing; FAIL + findings otherwise

---

7. **Phase 6 — Design Review & Documentation**: invoke design-review-phase skill

   **Phase 5→6 Artifact Gate**: `reviews/phase-5-verify/final-compliance.md` exists AND verdict=PASS

   **Phase 6 Execution** (2-wave parallel):
   - **Wave 1 (parallel)**: `code-quality-reviewer` + `design-quality-reviewer` — code quality scoring + cross-phase design consistency
   - **Wave 2 (parallel, after Wave 1)**: `design-note-writer` + `improvement-analyst` — comprehensive design note + prioritized improvement recommendations

   **Phase 6 Completion Gate**: All 4 deliverables exist:
   - `reviews/phase-6-review/code-review.md`
   - `reviews/phase-6-review/design-review.md`
   - `reviews/phase-6-review/design-note.md`
   - `reviews/phase-6-review/improvements.md`

---

8. **On completion**: remove state file, report summary with final compliance matrix and Phase 6 deliverables

---

**Gate Failure Handling:**
- **Quality Gate FAIL (same-level fix)**: pass findings to the phase's worker agent for correction. Re-run Quality Gate after fix. Max 2 retry cycles per gate
- **Upper-Spec Violation detected**: STOP immediately. Identify which upper phase is violated (e.g., "μArch dropped Feature X that Architecture requires"). Return to the violated upper phase. Report violation details to user — DO NOT proceed without user approval
- **Artifact Gate FAIL**: retry the phase once, then escalate to user

**Coding Convention Enforcement (all phases):**
- Port naming: inputs `i_`, outputs `o_`, bidirectional `io_` (NOT suffix `_i`/`_o`)
- Clock: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
- Reset: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
- Instances: `u_` prefix; generates: `gen_` prefix
- Use `logic` everywhere (`reg`/`wire` forbidden)
- Base style: lowRISC SystemVerilog Coding Style Guide with above overrides
</Steps>

<Tool_Usage>
```
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
# Phase 2: Architecture + Reference Model (parallel)
# ============================================================
Bash("mkdir -p reviews/phase-2-architecture")

Task(subagent_type="rtl-agent-team:arch-designer",
     prompt="Design architecture from requirements.json and io_definition.json. All interface signals must use i_/o_ prefix, {domain}_clk/{domain}_rst_n naming. Produce architecture.md and block_diagram.")
Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Implement C++ ref model at ref_model/src/ from requirements.json. Must be bitexact vs JM/HM.")

# --- Phase 2→3 Quality Gate ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="READ-ONLY architecture review. Read requirements.json, then read architecture.md.
Perform the following checks:
1. **Feature Coverage Checklist**: List EVERY functional requirement from requirements.json.
   For each, state whether architecture.md addresses it and where (section/block).
   Mark COVERED or MISSING. Any MISSING item → FAIL.
   Save the checklist to reviews/phase-2-architecture/feature-coverage.md in this format:
     # Phase 2 Review: Feature Coverage
     - Date: (today)
     - Reviewer: rtl-architect
     - Upper Spec: requirements.json
     - Verdict: PASS | FAIL
     ## Feature Coverage Checklist
     | REQ ID | Description | Architecture Block | Status |
     |--------|-------------|-------------------|--------|
     ## Findings
     ## Verdict
2. **Block decomposition**: Are blocks well-bounded with single responsibilities?
3. **Interface adequacy**: Do inter-block interfaces carry all signals needed for the requirements?
4. **Port naming**: Verify all interface tables use i_/o_ prefix, {domain}_clk/{domain}_rst_n.
5. **Hierarchical compliance**: Does architecture introduce any feature not in requirements.json?
   Unauthorized additions → FAIL.
Save the full architecture review to reviews/phase-2-architecture/architecture-review.md in standard review Markdown format.
Also save a Mermaid block diagram to reviews/phase-2-architecture/architecture-diagram.md showing
the top-level block decomposition (use graph TD with block names and connections).
Output the Feature Coverage Checklist table, then:
verdict: PASS or FAIL + findings[]")

Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="READ-ONLY synthesizability pre-assessment. Read architecture.md.
Evaluate:
1. Are there architectural patterns known to cause synthesis difficulties?
2. Is the clock domain crossing strategy defined for all multi-domain interfaces?
3. Are memory structures (FIFOs, RAMs) sized and typed appropriately?
4. Any combinational loop risks in the proposed block connectivity?
verdict: PASS or FAIL + findings[]")

# ============================================================
# Phase 3: μArch + BFM (parallel)
# ============================================================
Bash("mkdir -p reviews/phase-3-uarch")

Task(subagent_type="rtl-agent-team:uarch-designer",
     prompt="Produce uarch/*.md from architecture.md. All signal names must use i_/o_ prefix, {domain}_clk/{domain}_rst_n, u_ instances, gen_ generates.")
Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="Implement SystemC TLM BFMs at bfm/src/ from architecture.md. Interface names must match io_definition.json.")

# --- Phase 3→4 Quality Gate ---
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="READ-ONLY μArch review. Read architecture.md, then read all uarch/*.md files.
Perform the following checks:
1. **Block boundary alignment**: Does each uarch document correspond 1:1 to an architecture block?
   Flag any block that was split, merged, or renamed without architecture.md approval.
2. **Feature preservation**: For each feature assigned to a block in architecture.md,
   verify the corresponding uarch/*.md describes its detailed implementation.
   List each feature and mark PRESERVED or DROPPED. Any DROPPED item → FAIL.
   Save the feature preservation checklist to reviews/phase-3-uarch/feature-preservation.md in this format:
     # Phase 3 Review: Feature Preservation
     - Date: (today)
     - Reviewer: rtl-architect
     - Upper Spec: architecture.md
     - Verdict: PASS | FAIL
     ## Feature Coverage Checklist
     | Feature | Architecture Block | μArch Doc | Status |
     |---------|-------------------|-----------|--------|
     ## Findings
     ## Verdict
3. **Pipeline/timing feasibility**: Is the proposed pipeline depth achievable at target frequency?
   Are there obvious critical paths that span too many logic levels?
4. **Signal naming compliance**: i_/o_ ports, {domain}_clk/{domain}_rst_n, u_ instances, gen_ generates.
5. **Hierarchical compliance**: Does any μArch document alter a decision made in architecture.md
   (e.g., change interface width, remove a port, alter FSM states)? Any such change → FAIL.
Save the full μArch review to reviews/phase-3-uarch/uarch-review.md in standard review Markdown format.
Also save a Mermaid pipeline diagram to reviews/phase-3-uarch/pipeline-diagram.md showing
the pipeline stages and data flow (use graph LR with stage names and connections).
Output the Feature Preservation Checklist table, then:
verdict: PASS or FAIL + findings[]")

# ============================================================
# Phase 4: RTL Implementation (parallel per module)
# ============================================================
Bash("mkdir -p reviews/phase-4-rtl")

Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Implement rtl/src/{module}.sv from uarch/{module}.md. Use logic only (no reg/wire), i_/o_ port prefix, {domain}_clk/{domain}_rst_n, u_ instances, gen_ generates. Run lint after writing.")

# --- Phase 4→5 Quality Gate ---
Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="READ-ONLY RTL design review. Read requirements.json, then read uarch/*.md, then read rtl/src/*.sv.
Perform the following checks:
1. **Functional Coverage Matrix**: For EVERY requirement in requirements.json, trace:
   requirement → uarch section → RTL module and approximate line range.
   Mark each requirement as IMPLEMENTED or MISSING. Any MISSING → FAIL.
   Save the functional completeness report to reviews/phase-4-rtl/functional-completeness.md in this format:
     # Phase 4 Review: Functional Completeness
     - Date: (today)
     - Reviewer: rtl-critic
     - Upper Spec: requirements.json, uarch/*.md
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
   compared to uarch/*.md? Unauthorized deviation → FAIL.
Save the full design review to reviews/phase-4-rtl/design-review.md in standard review Markdown format.
Output the Functional Coverage Matrix table, then:
verdict: PASS or FAIL + findings[]")

Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Run full lint on rtl/src/*.sv. Zero errors required. Review warnings for false positives. Report lint summary.
Save the lint report to reviews/phase-4-rtl/lint-report.md in this format:
  # Phase 4 Review: Lint Report
  - Date: (today)
  - Reviewer: lint-checker
  - Upper Spec: rtl/src/*.sv
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
     prompt="Generate SVA properties from uarch/*.md specifications. Write bind files for each module at tb/formal/. Follow systemverilog-assertion conventions.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run SymbiYosys formal verification on all SVA bind files in tb/formal/. Report counterexamples if any. Save results to reviews/phase-5-verify/formal-review.md in standard review Markdown format. verdict: PASS or FAIL + counterexamples[]")

# --- Phase 5b: CDC Analysis (parallel with 5a) ---
Task(subagent_type="rtl-agent-team:cdc-checker",
     prompt="Analyze all clock domain crossings in rtl/src/*.sv. Check synchronizer presence, FIFO usage, and handshake protocols. Save CDC report to reviews/phase-5-verify/cdc-report.md in standard review Markdown format. verdict: PASS or FAIL + findings[]")

# --- Phase 5c: Integration TB + Ref Model (parallel with 5a/5b) ---
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Create cocotb integration testbench at tb/cocotb/. Test end-to-end data flow through all modules. Include ref_model comparison for bitexact verification.")

Task(subagent_type="rtl-agent-team:func-verifier",
     prompt="Run cocotb integration tests with multiple seeds against ref_model.
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
     prompt="READ-ONLY final spec compliance review. Read requirements.json, io_definition.json, architecture.md, rtl/src/*.sv, and ALL Phase 5 review results (formal-review.md, cdc-report.md, requirement-traceability.md, coverage-report.md).
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
verdict: PASS or FAIL + findings[]")

# --- Phase 5→4 Feedback Loop ---
# On any Phase 5 sub-phase FAIL:
#   1. Classify: UNIT_FIX | INTEGRATION_FIX | DESIGN_FIX
#   2. UNIT_FIX/INTEGRATION_FIX → invoke rtl-bugfix skill with feedback_origin
#   3. DESIGN_FIX → STOP and escalate to user
#   4. Max 2 feedback loops per sub-phase
# Example:
# Skill(skill="rtl-agent-team:rtl-bugfix",
#        args="Phase 5a formal FAIL. Counterexample: [details]. feedback_origin=5a-formal")

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
Read requirements.json, uarch/*.md for context. Read ALL rtl/src/*.sv.
Read reviews/phase-4-rtl/design-review.md for prior findings.
Score each module on 5 dimensions (1-10). Detect anti-patterns. Assess cross-module consistency.
Save to reviews/phase-6-review/code-review.md.")

Task(subagent_type="rtl-agent-team:design-quality-reviewer",
     model="opus",
     prompt="Perform cross-phase design quality review for Phase 6.
Read ALL artifacts: requirements.json → architecture.md → uarch/*.md → rtl/src/*.sv.
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
→ Phase 3→4 Quality Gate: rtl-architect finds uarch/entropy_coder.md changed the context table
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
- **Verification phase fails after 2 retries** → invoke bug-repro skill, report findings
- **User says "cancel" or "stop"** → delete .rtl-agent-team/state/rtl-autopilot-state.json, report progress summary
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] State file written before starting
- [ ] Each phase passed BOTH Artifact Gate AND Quality Gate before proceeding
- [ ] **Hierarchical Spec Compliance** verified at every Quality Gate:
  - Phase 1→2: requirements are complete, consistent, and implementable
  - Phase 2→3: architecture covers 100% of requirements (Feature Coverage Checklist PASS)
  - Phase 3→4: μArch preserves 100% of architecture features (Feature Preservation Checklist PASS)
  - Phase 4→5: RTL implements 100% of requirements (Functional Coverage Matrix PASS) + lint-clean + all unit tests PASS + basic integration PASS
  - Phase 5 final: every requirement is implemented, verified, and passing (Final Compliance Matrix PASS)
- [ ] No upper-spec violations were left unresolved
- [ ] Naming conventions enforced at every phase gate:
  - io_definition.json: `i_`/`o_`/`io_` prefix, `{domain}_clk`/`{domain}_rst_n`
  - architecture.md: interface signal names, clock/reset naming
  - uarch/*.md: all signal names, FSM states, instance prefixes
  - rtl/src/*.sv: lint-clean, naming compliant
- [ ] All 6 phases completed
- [ ] State file removed on clean completion
- [ ] Summary report generated with Final Compliance Matrix and Phase 6 deliverables
- [ ] **Review artifacts saved to reviews/ directory:**
  - reviews/phase-1-research/research-review.md
  - reviews/phase-2-architecture/feature-coverage.md
  - reviews/phase-2-architecture/architecture-review.md
  - reviews/phase-2-architecture/architecture-diagram.md (Mermaid block diagram)
  - reviews/phase-3-uarch/feature-preservation.md
  - reviews/phase-3-uarch/uarch-review.md
  - reviews/phase-3-uarch/pipeline-diagram.md (Mermaid pipeline diagram)
  - reviews/phase-4-rtl/functional-completeness.md
  - reviews/phase-4-rtl/design-review.md
  - reviews/phase-4-rtl/lint-report.md
  - reviews/phase-5-verify/requirement-traceability.md
  - reviews/phase-5-verify/formal-review.md
  - reviews/phase-5-verify/cdc-report.md
  - reviews/phase-5-verify/coverage-report.md
  - reviews/phase-5-verify/final-compliance.md
  - reviews/phase-6-review/code-review.md
  - reviews/phase-6-review/design-review.md
  - reviews/phase-6-review/design-note.md
  - reviews/phase-6-review/improvements.md
</Final_Checklist>

<Advanced>
Resume: read existing state file, skip completed phases, continue from current phase.
Parallel phases (2 and 3) use separate state sub-keys to track each sub-task independently.
Templates: `templates/autopilot-state.json` (state file), `templates/review-report.md` (gate reports).
See `references/gate-failure-handling.md` for gate retry flow and upper-spec violation handling.
</Advanced>
