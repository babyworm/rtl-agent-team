---
name: rtl-uarch-to-verify
description: "This skill should be used when implementing RTL and running verification from existing microarchitecture documents (Phase 4→5). Requires completed Phase 1-3 artifacts as prerequisites. Produces RTL code, unit tests, and full verification with Phase 5→4 feedback loops — stopping before Design Note phase."
---

<Purpose>
Drive the RTL design pipeline through Phases 4→5 (RTL Implementation → Verification) using existing
Phase 1-3 design documents as input, then STOP before Phase 6 (Design Note).

This skill is the "implementation half" of the pipeline, intended for workflows where:
- Design documents (Phase 1-3) have been completed and reviewed (via rtl-spec-to-uarch or manually)
- RTL implementation and verification should proceed from approved μArch specs
- Design Note phase is handled separately (via rtl-design-review-phase)

**Prerequisites**: This skill REQUIRES completed Phase 1-3 artifacts. It will verify their existence
and quality gate status before proceeding. If prerequisites are not met, the skill reports what is
missing and suggests running rtl-spec-to-uarch first.

**Hierarchical Spec Compliance Principle:**
Lower phases MUST NOT violate upper phase specifications:
  Spec → Architecture → μArch → RTL → Verification
RTL must faithfully implement the μArch design. Verification must validate against the original Spec.

**Design Priority Order:**
1. Functional Correctness (highest) — Every required feature in Spec works exactly
2. Interface Compliance — Ports, protocols, timing interfaces match Architecture
3. Timing/Performance — Throughput, latency targets met
4. Area/Power (lowest)

**Document-as-Memory Principle:**
Phase 4 reads Phase 1-3 documents as input context. Phase 5 reads Phase 4 artifacts.
No agent needs to "remember" another agent's output — it reads the document.
This enables resumability: any phase can restart by re-reading its input documents.

State is persisted at .rtl-agent-team/state/rtl-uarch-to-verify-state.json for resumability.
</Purpose>

<Use_When>
- Phase 1-3 design documents are complete and human-reviewed
- Resuming RTL implementation after design review approval
- Starting RTL coding from existing μArch specs (produced by rtl-spec-to-uarch or manually)
- Implementing and verifying a design that was planned in a separate session
</Use_When>

<Do_Not_Use_When>
- No μArch documents exist yet (use rtl-spec-to-uarch or rtl-autopilot first)
- Full end-to-end automation from spec is needed (use rtl-autopilot instead)
- Only a single phase-specific task is needed (use rtl-code, rtl-func-verify, etc.)
- Design Note phase is needed (use rtl-design-review-phase after this skill completes)
</Do_Not_Use_When>

<Why_This_Exists>
In practice, RTL implementation starts after design review — not immediately after μArch.
This skill enables the standard industry workflow:
1. rtl-spec-to-uarch produces design documents (Phase 1-3)
2. Human architect reviews and approves μArch
3. rtl-uarch-to-verify implements and verifies RTL (Phase 4-5)
4. rtl-design-review-phase produces design notes (Phase 6)

Separating design from implementation also enables:
- Different sessions/teams for design vs implementation
- Resuming implementation after days/weeks of human review
- Re-running implementation with modified μArch without re-running research/architecture
</Why_This_Exists>

<Execution_Policy>
- State file (.rtl-agent-team/state/rtl-uarch-to-verify-state.json) tracks progress for resumability
- **Prerequisite verification** MUST pass before any work begins (Step 1)
- Independent sub-tasks within a phase run in parallel via concurrent Task() calls
- **Dual-Layer Phase Gates** are hard stops between Phase 4 and Phase 5:
  1. **Artifact Gate**: Required files/directories exist (fast check)
  2. **Quality Gate**: Reviewer agent(s) verify quality AND hierarchical spec compliance
- Quality Gate verdicts are structured: `PASS` or `FAIL + findings[]`
- On Artifact Gate failure: retry the failed phase once, then escalate to user
- On Quality Gate failure: pass findings back to the phase's worker agent for correction, then re-run Quality Gate
- Maximum 2 Quality Gate retry cycles per phase before escalating to user
- **Phase 5→4 Feedback Loop**: On Phase 5 sub-phase FAIL, classify as UNIT_FIX/INTEGRATION_FIX/DESIGN_FIX and handle accordingly (max 2 feedback loops per sub-phase)
- On interruption: state file is preserved with detailed context for resumability:
  - Set `interrupted_reason`, `partial_work_summary`
  - For Phase 4: update `completed_modules`, `stream_a_status`, `stream_b_status`
  - For Phase 5: update `completed_sub_phases`, `fix_history`
- **Context Manifest**: Each phase has a manifest that declares required files
- **Termination**: After Phase 5 Final Compliance Gate PASS, generate summary, then STOP. Do NOT proceed to Phase 6
</Execution_Policy>

<Steps>
1. **Prerequisite Verification** (MANDATORY — must pass before any work begins):
   Verify the following artifacts exist and are valid:

   | Artifact | Required Check |
   |----------|---------------|
   | `docs/phase-3-uarch/*.md` | At least one μArch module spec exists |
   | `reviews/phase-3-uarch/uarch-review.md` | File exists AND contains `Verdict: PASS` |
   | `docs/phase-1-research/requirements.json` | File exists (needed for traceability) |
   | `docs/phase-1-research/io_definition.json` | File exists (needed for port verification) |
   | `refc/*/*.c` | At least one C reference model source exists |
   | `docs/phase-3-uarch/phase-3-summary.md` | File exists (Phase 3 summary for context) |

   **On prerequisite failure**:
   - Report which artifacts are missing
   - Suggest: "Run `/rtl-agent-team:rtl-spec-to-uarch` to complete Phase 1-3 design documents first"
   - DO NOT proceed — exit immediately

   **Intake Checklist (from rtl-spec-to-uarch):**
   - [ ] Phase 3 summary exists: `docs/phase-3-uarch/phase-3-summary.md`
   - [ ] All μArch specs exist: `docs/phase-3-uarch/{module}.md` for each module
   - [ ] Phase 3 review passed: `reviews/phase-3-uarch/uarch-review.md` verdict=PASS
   - [ ] Feature preservation verified: `reviews/phase-3-uarch/feature-preservation.md`
   - [ ] State file updated: `.rtl-agent-team/rtl/{module}/phase-3-complete.json`
   - [ ] Context manifest ready: `templates/context-manifest-phase-4.json` references valid files

   **On prerequisite PASS**:
   - Read `reviews/phase-3-uarch/uarch-review.md` to confirm PASS verdict

   **Context Manifest Preload Validation** (Phase 4 start):
   - Load `templates/context-manifest-phase-4.json`
   - For each `required_full_read` entry: verify file exists, read into context
   - For each `required_summary_only` entry: verify referenced phase summaries exist
   - If ANY required file missing: STOP with clear error listing missing files
   - `optional_on_demand` files: skip validation, load lazily during execution

   Context loading:
   - Read required_full_read files (docs/phase-3-uarch/*.md, io_definition.json)
   - Read required_summary_only files (phase-1-summary.md, phase-2-summary.md)

---

1.5. **Initialize / Resume state**:
   - If `.rtl-agent-team/state/rtl-uarch-to-verify-state.json` exists:
     - **Resume check**: read state, skip completed phases/modules, resume from last action
     - Phase 4 resume: check `completed_modules` vs `pending_modules`, resume `stream_a_status`/`stream_b_status`
     - Phase 5 resume: check `completed_sub_phases` vs `pending_sub_phases`
     - Clear `interrupted_reason` and `partial_work_summary` after successful resume
   - If state file does not exist:
     - Write new state: phase=4, sub_phase=null, feedback_loops=0, max_feedback_loops=2, pipeline_scope="phase-4-to-5"

---

2. **Phase 4 — RTL Implementation + Early Verification (PARALLEL STREAMS)**
   Two parallel streams run simultaneously:
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
     - **Functional Coverage Check**: for each requirement in requirements.json, trace it through uarch to RTL implementation. Produce a coverage matrix: requirement -> uarch section -> RTL module/line. Flag any requirement with no RTL implementation as FAIL
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

   **Phase 4→5 Summary Validation:**
   - Verify `docs/phase-4-rtl/phase-4-summary.md` exists
   - If missing: delegate to `rtl-architect` (model=sonnet) to generate from Phase 4 artifacts
   - Summary must follow `templates/phase-summary.md` format

---

3. **Phase 5 — Extensive Verification (Sub-Phases)**
   - **Review artifacts setup**: `mkdir -p reviews/phase-5-verify`

   **Context Manifest Preload Validation** (Phase 5 start):
   - Load `templates/context-manifest-phase-5.json`
   - For each `required_full_read` entry: verify file exists, read into context
   - For each `required_summary_only` entry: verify phase summary exists
   - If ANY required file missing: STOP with clear error listing missing files
   - `optional_on_demand` files: skip validation, load lazily during execution

   - Phase 5 is structured into 5 sub-phases (some can run in parallel)
   - State tracking: uses `sub_phase`, `feedback_loops`, `max_feedback_loops` fields

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
   - `eda-runner`: run cocotb regression — **per-module parallel + multi-seed (5 seeds: 1, 42, 123, 1337, 65536 x N modules)**
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
     - **End-to-End Traceability Matrix**: unify segmented traceability artifacts:
       - reviews/phase-2-architecture/feature-coverage.md (REQ → Arch)
       - reviews/phase-3-uarch/feature-preservation.md (Arch → μArch)
       - reviews/phase-4-rtl/functional-completeness.md (REQ → μArch → RTL)
       - reviews/phase-5-verify/requirement-traceability.md (REQ → Test → Result)
       Produce unified matrix: | REQ ID | Spec Section | Arch Block | μArch Module | RTL File:Line | Test Name | Result |
       Any row with a gap → flag as TRACEABILITY_GAP
       Save to `reviews/phase-5-verify/e2e-traceability.md`
   - `rtl-critic`: comprehensive design review
   - Output: `reviews/phase-5-verify/final-compliance.md`, `reviews/phase-5-verify/e2e-traceability.md`

   **Phase 5→4 Feedback Loop (with parallel UNIT_FIX):**
   - Collect ALL FAIL results from sub-phases 5a, 5b, 5c before starting fixes
   - Classify each FAIL:
     - **UNIT_FIX**: resolvable by fixing a single module (e.g., SVA counterexample, assertion failure)
     - **INTEGRATION_FIX**: requires inter-module interface modification
     - **DESIGN_FIX**: requires architecture-level design change (-> user approval mandatory)
   - **Batch UNIT_FIX across sub-phases:**
     - Group all UNIT_FIX failures by module
     - If failures are in DIFFERENT modules -> launch parallel rtl-bugfix tasks (one per module)
     - If failures are in SAME module -> sequential fix within single rtl-bugfix task
     - Each rtl-bugfix follows: analyze -> fix -> lint -> TB -> sim
     - All parallel fixes run concurrently with `run_in_background: true`
   - INTEGRATION_FIX: always sequential (cross-module dependencies)
   - After ALL fixes complete: re-run ONLY affected sub-phases in parallel
   - Maximum 2 feedback loops per sub-phase (escalate to user if exceeded)
   - **Lesson Learned Recording** (after each successful feedback fix):
     - Delegate to `rtl-coder` (model=sonnet): append a lesson entry to `docs/lessons-learned.md`
       using `templates/lessons-learned-entry.md` format.
     - Record: symptom, root cause, fix applied, prevention strategy, related REQ/module/ADR
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

   **Phase 5 Summary Generation** (after Quality Gate PASS):
   - Delegate to `rtl-architect` (model=sonnet): read all Phase 5 artifacts and generate
     `docs/phase-5-verify/phase-5-summary.md` using `templates/phase-summary.md` format.

   **Phase 5 Summary Validation:**
   - Verify `docs/phase-5-verify/phase-5-summary.md` exists
   - If missing: delegate to `rtl-architect` (model=sonnet) to generate from Phase 5 artifacts
   - Summary must follow `templates/phase-summary.md` format

---

4. **On completion**: update state file with all phases completed, report summary.

   **Completion Report** (presented to user):
   - Phase 4 artifacts: rtl/*/*.sv (module count), sim/*/*.sv, Stream B artifacts
   - Phase 5 artifacts: formal-review.md, cdc-report.md, requirement-traceability.md, coverage-report.md
   - Final compliance: reviews/phase-5-verify/final-compliance.md verdict=PASS
   - Feedback loop count and lessons learned
   - Next step: "Run `/rtl-agent-team:rtl-design-review-phase` to produce design notes and improvement recommendations"

   **Do NOT proceed to Phase 6.** The pipeline stops here.

---

**Gate Failure Handling:**
- **Quality Gate FAIL (same-level fix)**: pass findings to the phase's worker agent for correction. Re-run Quality Gate after fix. Max 2 retry cycles per gate
- **Upper-Spec Violation detected**: STOP immediately. Report to user — DO NOT proceed without approval
- **Artifact Gate FAIL**: retry the phase once, then escalate to user

**Coding Convention Enforcement (all phases):**
See CLAUDE.md "Coding Conventions" section for full rules (language standards + Core Overrides).
Summary: i_/o_/io_ port prefix, {domain}_clk/{domain}_rst_n, u_ instances, gen_ generates, logic only.
</Steps>

<Tool_Usage>
```
# ============================================================
# Prerequisite Verification (MUST pass before any work)
# ============================================================
Read("docs/phase-3-uarch/")           # Verify μArch docs exist
Read("reviews/phase-3-uarch/uarch-review.md")  # Verify PASS verdict
Read("docs/phase-1-research/requirements.json") # Verify requirements exist
Read("docs/phase-1-research/io_definition.json") # Verify I/O spec exists
Glob("refc/*/*.c")                    # Verify ref model exists

# If any missing → report and EXIT
# If all present → load Context Manifest for Phase 4

# ============================================================
# Context Loading (Phase 4 Context Manifest)
# ============================================================
# required_full_read:
Read("docs/phase-3-uarch/*.md")        # All μArch specs
Read("docs/phase-1-research/requirements.json")
Read("docs/phase-1-research/io_definition.json")
# required_summary_only:
Read("docs/phase-1-research/phase-1-summary.md")
Read("docs/phase-2-architecture/phase-2-summary.md")

# ============================================================
# Phase 4: RTL Implementation (parallel streams)
# ============================================================
Bash("mkdir -p reviews/phase-4-rtl")

# Stream A: RTL coding (wave-based)
Skill(skill="rtl-agent-team:rtl-code")

# Stream B: Early verification framework (parallel with Stream A)
Task(subagent_type="rtl-agent-team:sva-extractor",
     prompt="Generate SVA property skeletons from docs/phase-3-uarch/*.md. Save to docs/phase-4-rtl/stream-b-sva-skeletons.md and sim/formal/.")
Task(subagent_type="rtl-agent-team:cdc-checker",
     prompt="Analyze clock domain topology from docs/phase-3-uarch/*.md. Save preliminary CDC report to docs/phase-4-rtl/stream-b-cdc-preliminary.md.")
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Generate cocotb TB skeletons from docs/phase-3-uarch/*.md. Save to docs/phase-4-rtl/stream-b-tb-skeletons.md and sim/.")

# Phase 4→5 Quality Gate
Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="Review RTL against μArch specs and requirements.json. Produce functional coverage matrix.
Save to reviews/phase-4-rtl/functional-completeness.md and reviews/phase-4-rtl/design-review.md.")
Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Run full lint pass on rtl/. Save to reviews/phase-4-rtl/lint-report.md.")

# Phase 4 Summary
Task(subagent_type="rtl-agent-team:rtl-architect", model="sonnet",
     prompt="Read all Phase 4 artifacts. Generate docs/phase-4-rtl/phase-4-summary.md.")

# ============================================================
# Phase 5: Extensive Verification (sub-phases)
# ============================================================
Bash("mkdir -p reviews/phase-5-verify")

# 5a + 5b + 5c in parallel
Task(subagent_type="rtl-agent-team:sva-extractor",
     prompt="Complete SVA properties using Stream B skeletons + actual RTL. Run SymbiYosys.
Output: reviews/phase-5-verify/formal-review.md")

Task(subagent_type="rtl-agent-team:cdc-checker",
     prompt="Update CDC report with final RTL. Compare Stream B predictions vs actual.
Output: reviews/phase-5-verify/cdc-report.md")

Task(subagent_type="rtl-agent-team:func-verifier",
     prompt="Run cocotb regression: RTL vs ref_model comparison. Multi-seed (5 seeds: 1, 42, 123, 1337, 65536).
Output: reviews/phase-5-verify/requirement-traceability.md")

# 5d: Coverage analysis
Task(subagent_type="rtl-agent-team:coverage-analyst",
     prompt="Analyze line/toggle/FSM coverage. Generate additional tests if below target.
Output: reviews/phase-5-verify/coverage-report.md")

# 5e: Final compliance + e2e traceability (after 5a-5d)
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="Final Compliance Matrix: every requirement implemented, verified, passing.
Unify segmented traceability (feature-coverage, feature-preservation, functional-completeness, requirement-traceability) into e2e matrix.
Output: reviews/phase-5-verify/final-compliance.md, reviews/phase-5-verify/e2e-traceability.md")

# Phase 5 Summary
Task(subagent_type="rtl-agent-team:rtl-architect", model="sonnet",
     prompt="Read all Phase 5 artifacts. Generate docs/phase-5-verify/phase-5-summary.md.")

# ============================================================
# STOP — Pipeline ends here
# ============================================================
# Report completion summary to user
# Suggest: "Run /rtl-agent-team:rtl-design-review-phase to produce design notes"
```
</Tool_Usage>

<Examples>
**Example 1: Start from completed μArch**
```
User: "μArch 문서가 완성됐어. RTL 구현하고 검증까지 진행해줘."
→ Invoke /rtl-agent-team:rtl-uarch-to-verify
→ Prerequisite check: all Phase 1-3 artifacts present, uarch-review.md PASS ✓
→ Phase 4: RTL coding (Stream A) + SVA/CDC/TB skeletons (Stream B) in parallel
→ Phase 4→5 Gate: lint-clean, unit tests PASS, Stream B ready
→ Phase 5: Formal + CDC + cocotb + coverage + final compliance
→ STOP: "Phase 4-5 완료. final-compliance.md PASS. /rtl-agent-team:rtl-design-review-phase로 Design Note를 생성하세요."
```

**Example 2: Missing prerequisites**
```
User: "RTL 구현 시작해줘."
→ Invoke /rtl-agent-team:rtl-uarch-to-verify
→ Prerequisite check: docs/phase-3-uarch/ is empty ✗
→ STOP: "Phase 3 μArch 문서가 없습니다. /rtl-agent-team:rtl-spec-to-uarch를 먼저 실행하세요."
```

**Example 3: Phase 5 feedback loop**
```
→ Phase 5a: SVA formal finds counterexample in module_x
→ Phase 5c: cocotb finds mismatch in module_y
→ Classify: both are UNIT_FIX (different modules)
→ Launch parallel rtl-bugfix: module_x + module_y simultaneously
→ Re-run 5a + 5c in parallel after fixes
→ Both PASS → continue to 5d, 5e
```

**Example 4: After rtl-spec-to-uarch**
```
User: (previously ran rtl-spec-to-uarch, reviewed μArch, approved)
User: "설계 문서 검토 완료. RTL 구현 진행해."
→ Invoke /rtl-agent-team:rtl-uarch-to-verify
→ All prerequisites present from previous rtl-spec-to-uarch run
→ Proceeds with Phase 4→5
```
</Examples>

<Escalation_And_Stop_Conditions>
- Prerequisites not met → report missing artifacts, suggest rtl-spec-to-uarch
- Phase 4 Quality Gate fails after 2 retries → ask user for RTL implementation direction
- Phase 5 sub-phase fails after 2 feedback loops → escalate to user
- DESIGN_FIX detected → STOP immediately, report upper-spec violation to user
- Coverage below target after additional test generation → ask user for acceptable threshold
</Escalation_And_Stop_Conditions>

<Parallel_Execution_Pattern>
Phase 5 sub-phases use a dependency-aware parallel execution pattern:

**Independent sub-phases (parallel):**
- 5a (formal) + 5b (CDC) + 5c (integration): independent, run in parallel via `run_in_background: true`
- Each sub-phase completes independently and reports results

**Dependent sub-phases (sequential):**
- 5d (coverage): starts incrementally as modules complete 5a-5c (partial dependency)
- 5e (design review): requires ALL of 5a-5d complete (full dependency)

**Phase 4 parallel streams:**
- Stream A (RTL coding) + Stream B (early verification): independent, run in parallel
- Merge point at Phase 4→5 Gate requires both streams complete

**Task tool usage:**
- Use `run_in_background: true` for independent sub-phases within a wave
- Wait for all background tasks before dependent phases
- Collect results via TaskOutput before proceeding
- Phase 5→4 feedback: parallel UNIT_FIX across different modules with `run_in_background: true`
</Parallel_Execution_Pattern>

<Final_Checklist>
Before reporting completion, verify ALL of the following:
- [ ] Prerequisites: all Phase 1-3 artifacts verified present
- [ ] Phase 4 Stream A: rtl/*/*.sv exist, all lint-clean
- [ ] Phase 4 Stream A: sim/*/tb_*.sv exist for all modules
- [ ] Phase 4 Stream A: unit tests all PASS
- [ ] Phase 4 Stream B: SVA skeletons in sim/formal/ and docs/phase-4-rtl/stream-b-sva-skeletons.md
- [ ] Phase 4 Stream B: CDC preliminary report in docs/phase-4-rtl/stream-b-cdc-preliminary.md
- [ ] Phase 4 Stream B: TB skeletons in docs/phase-4-rtl/stream-b-tb-skeletons.md
- [ ] Phase 4: reviews/phase-4-rtl/functional-completeness.md shows 100% coverage
- [ ] Phase 4: reviews/phase-4-rtl/design-review.md verdict=PASS
- [ ] Phase 4: reviews/phase-4-rtl/lint-report.md zero errors
- [ ] Phase 4: phase-4-summary.md generated
- [ ] Phase 5a: reviews/phase-5-verify/formal-review.md exists
- [ ] Phase 5b: reviews/phase-5-verify/cdc-report.md exists
- [ ] Phase 5c: reviews/phase-5-verify/requirement-traceability.md exists
- [ ] Phase 5d: reviews/phase-5-verify/coverage-report.md exists
- [ ] Phase 5e: reviews/phase-5-verify/e2e-traceability.md exists (unified traceability matrix)
- [ ] Phase 5e: reviews/phase-5-verify/final-compliance.md verdict=PASS
- [ ] Phase 5: phase-5-summary.md generated
- [ ] State file updated with all phases completed
- [ ] Pipeline did NOT proceed to Phase 6

If ANY item is unchecked → DO NOT report completion. Fix the issue first.
</Final_Checklist>
