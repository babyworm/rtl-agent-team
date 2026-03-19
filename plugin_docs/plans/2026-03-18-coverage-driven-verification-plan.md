# Coverage-Driven Verification Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance P4-P5 verification pipeline with test-plan-first workflow, coverage handoff, and acceptance-criteria-level traceability.

**Architecture:** Three sequential phases (GAP 2 → GAP 1 → GAP 4) modifying agent prompts, policy documents, and gate criteria. No code — all changes are to `.md` prompt files and `.json` configuration. Each phase stabilized before next begins.

**Tech Stack:** Markdown agent prompts, JSON schemas (iron-requirements, unit_results, skill-completion-criteria, phase-registry), POSIX shell hooks (read-only audit)

**Spec:** `plugin_docs/specs/2026-03-18-coverage-driven-verification-design.md`

---

## File Structure Overview

### Phase I: GAP 2 — Coverage Handoff (3 files)

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `agents/p5s-func-verify-orchestrator.md` | Step 0 artifact scan + Step 1 baseline loading |
| Modify | `agents/p5-verify-orchestrator.md` | Stage 1 V5 dispatch with baseline directive |
| Modify | `skills/rtl-p5s-func-verify-policy/SKILL.md` | "Tier 2 Baseline Utilization" policy section |

### Phase II: GAP 1 — Wave 0 Test Plan (10 files)

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `agents/test-plan-writer.md` | New agent: uarch spec → test plan document |
| Modify | `agents/p4-implement-orchestrator.md` | Wave 0 Step 0b: spawn test-plan-writer |
| Modify | `agents/p4-implement-team-orchestrator.md` | Wave 0 task in team task graph |
| Modify | `agents/testbench-dev.md` | Load test plan in Investigation Protocol |
| Modify | `skills/rtl-p4-implement-policy/SKILL.md` | Wave 0 Step 0b definition + gate |
| Modify | `skills/rtl-p4-implement/SKILL.md` | Skill description mentions test plan |
| Modify | `agents/p4-rtl-sanity-orchestrator.md` | Test plan existence check |
| Modify | `agents/p4-block-parallel-coordinator.md` | Block worker Wave 0 dispatch |
| Modify | `agents/coverage-analyst.md` | Read test plan for gap analysis |
| Modify | `agents/requirement-tracer.md` | Read test plan for REQ→scenario mapping |

### Phase III: GAP 4 — Acceptance Criteria (28 unique files, 7 steps)

See spec Section "Cascading Impact" for full file list organized by category (A-G).

---

## Phase I: GAP 2 — P4→P5 Coverage Handoff

### Task 1: P5 Func-Verify Orchestrator — Baseline Loading

**Files:**
- Modify: `agents/p5s-func-verify-orchestrator.md`

- [ ] **Step 1: Verify current state — no unit_results reference in Step 0**

Run: `grep -n 'unit_results' agents/p5s-func-verify-orchestrator.md`
Expected: No hits in Step 0 artifact scan block (may have hits elsewhere)

- [ ] **Step 2: Add unit_results.json to upstream artifact scan (Step 0)**

Find the Step 0 upstream artifact scan block (contains `Glob("rtl/**/*.sv")`).
Add after the last Glob line:

```
Glob("sim/**/*_unit_results.json")    # Tier 2 baseline (optional — graceful degradation if absent)
```

- [ ] **Step 3: Add Tier 2 baseline loading in Step 1**

Find the Step 1 section. Add after the existing module enumeration:

```
## Tier 2 Baseline Loading (GAP 2 enhancement)
For each module, check if `sim/{module}/{module}_unit_results.json` exists.
If found:
  - Read coverage baseline: line_pct, fsm_pct, toggle_pct
  - Read already-covered features list
  - Read func_coverage bins_hit/bins_total
  - Pass to downstream steps: "Tier 2 baseline available for {module}"
If not found:
  - Proceed without baseline (graceful degradation)
  - Log: "No Tier 2 baseline for {module} — CDTG starts from zero"
```

- [ ] **Step 4: Add baseline directive in Step 2 (cocotb TB generation)**

Find the Step 2 testbench-dev dispatch prompt. Add to the prompt:

```
If Tier 2 baseline is available for this module, build incrementally:
- Read sim/{module}/{module}_unit_results.json for already-covered features
- Focus new test scenarios on UNCOVERED features and FSM states
- Do not duplicate Tier 2 test vectors — extend coverage, not repeat it
```

- [ ] **Step 5: Add baseline pass-through in Step 3.5 (coverage analysis)**

Find the coverage-analyst dispatch (Step 3.5 or incremental coverage section). Add:

```
Include Tier 2 baseline in coverage-analyst prompt:
"Tier 2 achieved: FSM {fsm_pct}%, Line {line_pct}%, Toggle {toggle_pct}%.
Already covered features: {feature_list}.
Focus CDTG Round 1 on uncovered FSM states and untested code paths."
```

- [ ] **Step 6: Validate**

Run: `grep -c 'unit_results\|Tier 2 baseline\|Tier 2 Baseline' agents/p5s-func-verify-orchestrator.md`
Expected: ≥4 hits (Step 0, Step 1, Step 2, Step 3.5)

- [ ] **Step 7: Commit**

```bash
git add agents/p5s-func-verify-orchestrator.md
git commit -m "feat(GAP2): add Tier 2 baseline loading to P5 func-verify orchestrator"
```

### Task 2: P5 Verify Orchestrator — Baseline Dispatch

**Files:**
- Modify: `agents/p5-verify-orchestrator.md`

- [ ] **Step 1: Add unit_results.json to upstream artifact scan (Step 0)**

Find the Step 0 upstream scan block. Add:

```
Glob("sim/**/*_unit_results.json")    # Tier 2 baseline for coverage handoff
```

- [ ] **Step 2: Add baseline directive in Stage 1 V5 dispatch**

Find the V5 (functional regression) dispatch in Stage 1. Add to the dispatch prompt:

```
Load Tier 2 baseline from sim/{module}/{module}_unit_results.json for each module.
Pass baseline coverage data to CDTG for incremental gap closure.
```

- [ ] **Step 3: Validate**

Run: `grep -c 'unit_results\|Tier 2 baseline' agents/p5-verify-orchestrator.md`
Expected: ≥2 hits

- [ ] **Step 4: Commit**

```bash
git add agents/p5-verify-orchestrator.md
git commit -m "feat(GAP2): add Tier 2 baseline to P5 verify orchestrator dispatch"
```

### Task 3: P5 Func-Verify Policy — Baseline Utilization Section

**Files:**
- Modify: `skills/rtl-p5s-func-verify-policy/SKILL.md`

- [ ] **Step 1: Add "Tier 2 Baseline Utilization" section**

Add before the existing "Escalation" section (or at end of coverage-related sections):

```markdown
## Tier 2 Baseline Utilization

When Tier 2 unit test results (`sim/{module}/{module}_unit_results.json`) are available
from Phase 4, the CDTG pipeline MUST operate incrementally:

1. **Load baseline**: Read Tier 2 coverage metrics (line_pct, fsm_pct, toggle_pct)
   and already-covered features from unit_results.json
2. **Prioritize gaps**: CDTG Round 1 focuses on uncovered FSM states, untested code
   paths, and features not exercised in Tier 2
3. **Avoid duplication**: Do not regenerate test vectors that duplicate Tier 2 coverage.
   Extend coverage, not repeat it
4. **Graceful degradation**: If Tier 2 results are absent (e.g., module skipped P4 unit
   testing), proceed from zero baseline. Log warning but do not block

Coverage targets remain unchanged: Line ≥ 90%, Toggle ≥ 80%, FSM ≥ 70%.
The baseline only affects CDTG prioritization, not target thresholds.
```

- [ ] **Step 2: Validate**

Run: `grep -c 'Tier 2 Baseline' skills/rtl-p5s-func-verify-policy/SKILL.md`
Expected: ≥1 hit (section heading)

- [ ] **Step 3: Commit**

```bash
git add skills/rtl-p5s-func-verify-policy/SKILL.md
git commit -m "feat(GAP2): add Tier 2 Baseline Utilization policy section"
```

### Task 4: Phase I Regression + Validation

- [ ] **Step 1: Run full test suite**

Run: `cd ~/work/rtl-agent-team && pytest tests/ -v`
Expected: All existing tests PASS

- [ ] **Step 2: Run Phase I validation grep patterns**

```bash
grep -n 'unit_results' agents/p5s-func-verify-orchestrator.md | head -5
grep -n 'unit_results' agents/p5-verify-orchestrator.md | head -5
grep -n 'Tier 2 Baseline' skills/rtl-p5s-func-verify-policy/SKILL.md
```

Expected: All return relevant hits

- [ ] **Step 3: Phase I complete checkpoint**

Phase I (GAP 2) is complete. 3 files modified. Proceed to Phase II.

---

## Phase II: GAP 1 — Wave 0 Test Plan

### Task 5: Create test-plan-writer Agent

**Files:**
- Create: `agents/test-plan-writer.md`

- [ ] **Step 1: Write agent definition**

Create `agents/test-plan-writer.md` with this content:

```markdown
---
description: "Test plan generation specialist — derives test scenarios from uarch spec using ECP/BVA/STT/DT methodology"
model: sonnet
skills:
  - test-design-policy
---

# Test Plan Writer

You are a test plan generation specialist. You produce structured test plan documents
from microarchitecture specifications, mapping every requirement to concrete test scenarios.

## Input

- `docs/phase-3-uarch/{module}.md` — microarchitecture specification
- `docs/phase-3-uarch/iron-requirements.json` — REQ-U-* requirements with priorities
- `test-design-policy` skill — ECP/BVA/STT/DT methodology (auto-loaded via skills field)

## Output

- `sim/{module}/{module}_test_plan.md` — structured test plan document

## Process

1. **Read** uarch spec for the target module. Extract:
   - FSM states and transitions (if any)
   - Pipeline stages and latency
   - Protocol interfaces (valid/ready, AXI, etc.)
   - Datapath operations and widths

2. **Read** iron-requirements.json. Filter REQ-U-* entries relevant to this module.

3. **Apply test design techniques** (from test-design-policy):
   - **ECP** (all modules): Identify equivalence classes for each input signal.
     Select one representative value per class as test scenario.
   - **BVA** (all modules): For each bounded input, generate boundary values:
     unsigned W-bit: 0, 1, 2^(W-1)-1, 2^(W-1), 2^W-2, 2^W-1
   - **STT** (FSM modules only): Build state transition matrix.
     Generate scenarios for every valid transition + key illegal transitions.
     Skip for purely combinational modules.
   - **DT** (modules with ≥3 boolean controls): Build decision table for
     boolean control combinations. Skip if fewer than 3 boolean controls.

4. **Generate error injection plan**:
   - Protocol violation scenarios (if protocol interface exists)
   - Backpressure stress scenarios (if valid/ready interface)
   - Reset during active operation
   - Invalid/reserved input encodings (per uarch spec)
   - Arithmetic overflow/underflow (if datapath present)

5. **Design planned coverage model**:
   - Name covergroups: cg_{feature} (e.g., cg_fsm, cg_handshake, cg_datapath)
   - Name coverpoints: cp_{specific} (e.g., cp_idle_to_active, cp_backpressure_long)
   - Estimate expected bin count
   - Note Tier 2 targets: FSM ≥ 50%, Line ≥ 60%

6. **Write** test plan to `sim/{module}/{module}_test_plan.md` using the format below.

## Output Format

```markdown
# Test Plan: {module}
- Source: docs/phase-3-uarch/{module}.md
- Iron Requirements: docs/phase-3-uarch/iron-requirements.json
- Generated: YYYY-MM-DD by test-plan-writer

## Requirements Coverage Map
| REQ ID | Description | Test Scenarios | Method |
|--------|------------|----------------|--------|

## Test Scenarios
### TS-NNN: {descriptive name}
- Derived from: {REQ-U-NNN}, {technique}({details})
- Stimulus: {input sequence}
- Expected: {output/behavior}
- Coverage target: {covergroup.coverpoint}

## Coverage Model (Planned)
- Covergroups: {list}
- Expected bins: ~{count}
- Target: FSM≥50%, Line≥60% (Tier 2 gate)

## Error Injection Plan
| Category | Scenarios |
|----------|----------|

## Technique Applicability
| Technique | Applied | Reason |
|-----------|---------|--------|
```

## Constraints

- **Document only** — do NOT write RTL or testbench code
- Must reference every REQ-U-* from iron-requirements relevant to this module
- Each test scenario must trace to at least one REQ-U-*
- Test scenario IDs (TS-NNN) must be unique within the module
- If acceptance_criteria exist on a REQ-U-*, map each AC to specific test scenarios
```

- [ ] **Step 2: Validate agent structure**

Run: `head -5 agents/test-plan-writer.md`
Expected: YAML frontmatter with description, model, skills fields

Run: `grep -c 'ECP\|BVA\|STT\|DT' agents/test-plan-writer.md`
Expected: ≥4 (all 4 techniques referenced)

- [ ] **Step 3: Commit**

```bash
git add agents/test-plan-writer.md
git commit -m "feat(GAP1): create test-plan-writer agent definition"
```

### Task 6: Expand Wave 0 in P4 Implement Orchestrator

**Files:**
- Modify: `agents/p4-implement-orchestrator.md`

- [ ] **Step 1: Read current Wave 0 structure**

Run: `grep -n 'Wave 0\|Step 0' agents/p4-implement-orchestrator.md | head -10`
Understand the existing Wave 0: Preparation block location and content.

- [ ] **Step 2: Add Step 0b after existing Wave 0 content**

Find the end of the current Wave 0 block (after module enumeration, mkdir, TODO list).
Insert before Wave 1:

```markdown
### Step 0b: Test Plan Generation

For each module identified in Step 0a, spawn test-plan-writer in parallel:

```
Task(subagent_type="rtl-agent-team:test-plan-writer",
     prompt="Generate test plan for module {module}.
     Read docs/phase-3-uarch/{module}.md and docs/phase-3-uarch/iron-requirements.json.
     Apply ECP, BVA, STT (if FSM), DT (if ≥3 boolean controls).
     Output: sim/{module}/{module}_test_plan.md")
```

**Gate**: All modules must have `sim/{module}/{module}_test_plan.md` before proceeding to Wave 1.
If test-plan-writer fails for a module, retry once. On second failure, proceed with WARNING
and mark module as "test-plan-pending" for Wave 6a to generate.
```

- [ ] **Step 3: Validate**

Run: `grep -n 'Step 0b\|test-plan-writer\|test_plan' agents/p4-implement-orchestrator.md`
Expected: ≥3 hits

- [ ] **Step 4: Commit**

```bash
git add agents/p4-implement-orchestrator.md
git commit -m "feat(GAP1): add Wave 0 Step 0b test plan generation to P4 orchestrator"
```

### Task 7: Update P4 Team Orchestrator

**Files:**
- Modify: `agents/p4-implement-team-orchestrator.md`

- [ ] **Step 1: Add Wave 0 test-plan task to task graph**

Find the task graph definition (where Wave 0/1/2 tasks are defined).
Add test-plan task after preparation task, before Wave 1 tasks:

```
t_test_plan_{module}: {
  description: "Generate test plan for {module}",
  agent: "test-plan-writer",
  blockedBy: [t_prep],
  blocks: [t_w1_{module}]
}
```

- [ ] **Step 2: Validate**

Run: `grep -c 'test.plan\|test_plan' agents/p4-implement-team-orchestrator.md`
Expected: ≥2 hits

- [ ] **Step 3: Commit**

```bash
git add agents/p4-implement-team-orchestrator.md
git commit -m "feat(GAP1): add test plan task to P4 team orchestrator task graph"
```

### Task 8: Update testbench-dev to Load Test Plan

**Files:**
- Modify: `agents/testbench-dev.md`

- [ ] **Step 1: Add test plan loading in Investigation Protocol**

Find the `<Investigation_Protocol>` section (numbered steps 1-13).
Add as Step 0 INSIDE the tag, before existing Step 1:

```markdown
### Step 0: Load Test Plan (if available)

Check if `sim/{module}/{module}_test_plan.md` exists.
If found:
  - Read the test plan. Extract test scenarios (TS-NNN), coverage model, error injection plan.
  - Use the test plan as the PRIMARY source for test vector derivation.
  - During Steps 4a-4e, supplement the test plan (do not replace existing scenarios).
If not found:
  - Proceed with uarch-spec-driven derivation (existing behavior).
  - Log: "No test plan found — deriving test vectors from uarch spec directly."
```

Also update existing Step 4 (line ~69, "Read the test plan to identify...") to:
```
Read the test plan (loaded in Step 0) to identify: directed tests, random tests,
corner cases, error scenarios. If Step 0 found no test plan, derive these from
uarch spec directly.
```
This removes the duplicate file read and makes Step 4 reference Step 0's loaded plan.

- [ ] **Step 2: Add test plan refinement in existing Step 2 (or relevant TB writing step)**

Find the section where testbench-dev writes test code. Add:

```markdown
When writing test functions from a test plan:
- Map each TS-NNN to one cocotb test function
- Include comment: `# From test plan: TS-NNN`
- After RTL-specific discoveries (new states, undocumented paths), append new scenarios
  to the test plan file (do not delete existing scenarios)
```

- [ ] **Step 3: Validate**

Run: `grep -c 'test_plan\|test plan\|TS-NNN' agents/testbench-dev.md`
Expected: ≥3 hits

- [ ] **Step 4: Commit**

```bash
git add agents/testbench-dev.md
git commit -m "feat(GAP1): add test plan loading to testbench-dev Investigation Protocol"
```

### Task 9: Update P4 Policy, Skill Description, and Remaining Orchestrators

**Files:**
- Modify: `skills/rtl-p4-implement-policy/SKILL.md`
- Modify: `skills/rtl-p4-implement/SKILL.md`
- Modify: `agents/p4-rtl-sanity-orchestrator.md`
- Modify: `agents/p4-block-parallel-coordinator.md`

- [ ] **Step 1: Update P4 implement policy — Wave 0 Step 0b**

Find the Wave 0 definition in `skills/rtl-p4-implement-policy/SKILL.md`.
Expand the Wave 0 description to include Step 0b:

```markdown
**Wave 0: Preparation + Test Plan**
- Step 0a: Module enumeration, directory creation, TODO list (existing)
- Step 0b: Test plan generation per module via test-plan-writer agent
  - Gate: sim/{module}/{module}_test_plan.md exists for every module
  - Failure: retry once, then proceed with WARNING (Wave 6a must generate missing plans)
```

- [ ] **Step 2: Update P4 implement skill description**

In `skills/rtl-p4-implement/SKILL.md`, find the description of the pipeline.
Add mention of test plan:

```
Wave 0 includes test plan generation (Step 0b) — test scenarios are derived from
uarch spec before RTL implementation begins, following TDD principles.
```

- [ ] **Step 3: Update P4 rapid/sanity orchestrator**

In `agents/p4-rtl-sanity-orchestrator.md`, find the preparation/setup section. Add:

```
Check if sim/{module}/{module}_test_plan.md exists for each module.
If missing and time permits, spawn test-plan-writer before TB generation.
If missing in rapid mode, proceed — testbench-dev will derive vectors from uarch spec.
```

- [ ] **Step 4: Update block-parallel coordinator**

In `agents/p4-block-parallel-coordinator.md`, find the block worker dispatch.
Add test plan generation to each block's preparation:

```
Each block worker MUST generate test plan (Step 0b) before Wave 1 RTL coding.
Dispatch test-plan-writer per block module in the block's worktree.
```

- [ ] **Step 5: Validate all 4 files**

```bash
grep -c 'Step 0b\|test.plan' skills/rtl-p4-implement-policy/SKILL.md
grep -c 'test plan' skills/rtl-p4-implement/SKILL.md
grep -c 'test_plan\|test.plan' agents/p4-rtl-sanity-orchestrator.md
grep -c 'test.plan\|test_plan' agents/p4-block-parallel-coordinator.md
```
Expected: ≥1 hit per file

- [ ] **Step 6: Commit**

```bash
git add skills/rtl-p4-implement-policy/SKILL.md skills/rtl-p4-implement/SKILL.md agents/p4-rtl-sanity-orchestrator.md agents/p4-block-parallel-coordinator.md
git commit -m "feat(GAP1): update P4 policy, skill, and orchestrators for Wave 0 test plan"
```

### Task 10: Add Test Plan Consumption to P5 Agents

**Files:**
- Modify: `agents/coverage-analyst.md`
- Modify: `agents/requirement-tracer.md`

- [ ] **Step 1: Update coverage-analyst**

Find the Investigation Protocol or input section in `agents/coverage-analyst.md`. Add:

```markdown
## Test Plan Input (if available)
When analyzing coverage gaps, check for `sim/{module}/{module}_test_plan.md`.
If found:
  - Read the planned coverage model (covergroups, coverpoints, expected bins)
  - Compare planned bins against actual coverage data
  - Report gaps as: "Planned bin {cg.cp} not hit — TS-NNN was supposed to cover this"
  - This provides structured gap→test-scenario→requirement traceability
If not found: proceed with code-coverage-only analysis (existing behavior).
```

- [ ] **Step 2: Update requirement-tracer**

Find the Investigation Protocol in `agents/requirement-tracer.md`. Add:

```markdown
## Test Plan Input (if available)
When building the Requirement Traceability Matrix, check for `sim/{module}/{module}_test_plan.md`.
If found:
  - Read the Requirements Coverage Map from the test plan
  - Use as the authoritative REQ→test-scenario mapping
  - Verify each TS-NNN has a corresponding test function in the codebase
  - Report: "TS-NNN planned but no test function found" as UNTESTED
If not found: derive mapping from test code comments (# Covers: REQ-NNN) only.
```

- [ ] **Step 3: Validate**

```bash
grep -c 'test_plan\|test plan' agents/coverage-analyst.md
grep -c 'test_plan\|test plan' agents/requirement-tracer.md
```
Expected: ≥2 hits per file

- [ ] **Step 4: Commit**

```bash
git add agents/coverage-analyst.md agents/requirement-tracer.md
git commit -m "feat(GAP1): add test plan consumption to coverage-analyst and requirement-tracer"
```

### Task 11: Update Routing Table + Phase II Regression

**Files:**
- Modify: `skills/rtl-orchestrate/SKILL.md`

- [ ] **Step 1: Add test-plan-writer to agent catalog in rtl-orchestrate**

Find the agent catalog section in `skills/rtl-orchestrate/SKILL.md`.
Add entry:

```
| test-plan-writer | Test plan generation from uarch spec (ECP/BVA/STT/DT) | Spawned by P4 orchestrators in Wave 0 Step 0b |
```

- [ ] **Step 2: Regenerate hook routing block**

Run: `sh scripts/sync_orchestrator_inject.sh`
Expected: Success (routing block regenerated in hooks/rtl-orchestrator-inject.sh)

- [ ] **Step 3: Run full test suite**

Run: `cd ~/work/rtl-agent-team && pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 4: Verify agent count**

Run: `ls agents/*.md | wc -l`
Expected: 94 (was 93, +1 test-plan-writer)

- [ ] **Step 5: Commit routing update**

```bash
git add skills/rtl-orchestrate/SKILL.md hooks/rtl-orchestrator-inject.sh
git commit -m "feat(GAP1): add test-plan-writer to routing table, regenerate hook"
```

- [ ] **Step 6: Phase II complete checkpoint**

Phase II (GAP 1) is complete. 10 files modified (1 new + 9 modified). Proceed to Phase III.

---

## Phase III: GAP 4 — Acceptance Criteria Schema

### Task 12: Step 1 — Schema Definitions (Category A: 5 files)

**Files:**
- Modify: `skills/rtl-p4s-unit-test-policy/SKILL.md`
- Modify: `skills/rtl-p5s-func-verify-policy/SKILL.md`
- Modify: `skills/rtl-p5s-coverage-policy/SKILL.md`
- Modify: `skills/rtl-p5s-integration-test-policy/SKILL.md`
- Modify: `skills/rtl-p3-uarch-policy/SKILL.md`

- [ ] **Step 1: Update unit_results.json schema in rtl-p4s-unit-test-policy**

Find the result JSON schema section. Add `ac_ids` field:

```json
{
  "features": [
    {
      "name": "...",
      "status": "PASS|FAIL",
      "req_ids": ["REQ-U-NNN"],
      "ac_ids": ["REQ-U-NNN.AC-M"]
    }
  ]
}
```

Add rule: "When the requirement has `acceptance_criteria` in iron-requirements.json, `ac_ids` MUST be populated for each covered criterion. When `acceptance_criteria` is absent or empty, `ac_ids` field may be omitted (backward compatible)."

- [ ] **Step 2: Update RTM format in rtl-p5s-func-verify-policy**

Find the RTM format section. Add AC-level columns:

```markdown
| REQ ID | AC ID | Description | Test Case | Status |
```

Add rule: "VERIFIED judgment at criteria level when AC exists. When no AC, operate at REQ level."

- [ ] **Step 3: Update CDTG gap format in rtl-p5s-coverage-policy**

Find the Directed Test Guidance table format. Add ac_id column:

```markdown
| Gap ID | Uncovered Bin | ac_id (if applicable) | Constraint | Sequence | Expected |
```

- [ ] **Step 4: Update integration test policy**

In `skills/rtl-p5s-integration-test-policy/SKILL.md`, find req_ids references. Add:

```
Integration test results may optionally include `ac_ids` for AC-level traceability.
When acceptance_criteria exist on a requirement, integration tests SHOULD tag ac_ids
where feasible. This is advisory at Tier 4 (not required for gate).
```

- [ ] **Step 5: Update P3 uarch policy — iron-requirements schema**

In `skills/rtl-p3-uarch-policy/SKILL.md`, find the iron-requirements schema. Add:

```json
{
  "id": "REQ-U-NNN",
  "description": "...",
  "priority": "Critical|High|Medium|Low",
  "acceptance_criteria": [
    {
      "ac_id": "REQ-U-NNN.AC-M",
      "description": "measurable criterion",
      "test_method": "assertion|cocotb|formal|inspection",
      "verifiable": true
    }
  ]
}
```

Add: "Every REQ-U-* SHOULD have ≥1 acceptance criterion. P3 exit gate: advisory WARNING if any REQ-U-* has no AC."

- [ ] **Step 6: Validate all 5 files**

```bash
grep -c 'ac_ids\|ac_id\|acceptance_criteria' skills/rtl-p4s-unit-test-policy/SKILL.md skills/rtl-p5s-func-verify-policy/SKILL.md skills/rtl-p5s-coverage-policy/SKILL.md skills/rtl-p5s-integration-test-policy/SKILL.md skills/rtl-p3-uarch-policy/SKILL.md
```
Expected: ≥1 per file

- [ ] **Step 7: Commit**

```bash
git add skills/rtl-p4s-unit-test-policy/SKILL.md skills/rtl-p5s-func-verify-policy/SKILL.md skills/rtl-p5s-coverage-policy/SKILL.md skills/rtl-p5s-integration-test-policy/SKILL.md skills/rtl-p3-uarch-policy/SKILL.md
git commit -m "feat(GAP4-step1): add ac_ids/acceptance_criteria to schema definitions (5 files)"
```

### Task 13: Step 2 — Upstream P3 Producers (Category E: 3 files)

**Files:**
- Modify: `agents/uarch-designer.md`
- Modify: `skills/rtl-p3-uarch-design/SKILL.md`
- Modify: `agents/p3-uarch-orchestrator.md`

- [ ] **Step 1: Update uarch-designer**

Find the iron-requirements generation section. Add:

```
When generating iron-requirements.json, include acceptance_criteria array for each REQ-U-*:
- Each criterion has: ac_id (format: REQ-U-NNN.AC-M), description, test_method, verifiable
- Minimum 1 acceptance criterion per requirement
- test_method: "assertion" for protocol properties, "cocotb" for functional behavior,
  "formal" for invariants, "inspection" for non-automatable criteria (set verifiable: false)
```

- [ ] **Step 2: Update P3 uarch design skill**

In `skills/rtl-p3-uarch-design/SKILL.md`, find the P3 exit gate section. Add:

```
Advisory check: every REQ-U-* in iron-requirements.json should have ≥1 acceptance_criteria entry.
WARNING (not hard-block) if any REQ-U-* has no AC. The uarch-designer agent should be
prompted to add missing criteria before P3 exit.
```

- [ ] **Step 3: Update P3 uarch orchestrator**

In `agents/p3-uarch-orchestrator.md`, find the iron-requirements generation prompt. Add:

```
Include acceptance_criteria in each REQ-U-* entry. Format:
"acceptance_criteria": [{"ac_id": "REQ-U-NNN.AC-1", "description": "...", "test_method": "cocotb", "verifiable": true}]
Aim for ≥1 AC per requirement. Mark non-automatable criteria as verifiable: false.
```

- [ ] **Step 4: Validate**

```bash
grep -c 'acceptance_criteria' agents/uarch-designer.md skills/rtl-p3-uarch-design/SKILL.md agents/p3-uarch-orchestrator.md
```
Expected: ≥1 per file

- [ ] **Step 5: Commit**

```bash
git add agents/uarch-designer.md skills/rtl-p3-uarch-design/SKILL.md agents/p3-uarch-orchestrator.md
git commit -m "feat(GAP4-step2): add acceptance_criteria generation to P3 upstream (3 files)"
```

### Task 14: Step 3 — Schema Producers (Category B: 5 files)

**Files:**
- Modify: `agents/testbench-dev.md`
- Modify: `agents/test-plan-writer.md`
- Modify: `agents/p4s-unit-test-orchestrator.md`
- Modify: `agents/p5s-func-verify-orchestrator.md`
- Modify: `agents/sva-extractor.md`

Each file MUST include the fallback instruction:
> "When the requirement has no `acceptance_criteria` or the array is empty,
> fall back to `# Covers: REQ-U-012` (no .AC-N suffix). Do not fail or skip."

- [ ] **Step 1: Update testbench-dev — ac_ids tagging**

Add to the test function writing section:

```
When writing test functions, include coverage comments:
- If acceptance_criteria exist: `# Covers: REQ-U-012.AC-1`
- If no acceptance_criteria: `# Covers: REQ-U-012` (no .AC-N suffix)
Do not fail or skip when acceptance_criteria is absent or empty.
```

- [ ] **Step 2: Update test-plan-writer — ac_id mapping**

Add to the test scenario section:

```
When acceptance_criteria exist on a REQ-U-*, map each AC to specific test scenarios:
- TS-NNN → covers REQ-U-012.AC-1, REQ-U-012.AC-2
When no acceptance_criteria exist, map at REQ level only:
- TS-NNN → covers REQ-U-012
```

- [ ] **Step 3: Update p4s-unit-test-orchestrator — ac_ids collection**

Find Step 5 (result JSON collection). Add:

```
Collect ac_ids from test comments (# Covers: REQ-U-NNN.AC-M) into the result JSON.
If no AC-tagged comments found for a feature, check iron-requirements:
  - If requirement has acceptance_criteria: WARNING "ac_ids not tagged for {feature}"
  - If no acceptance_criteria: populate req_ids only (backward compatible)
```

Find Step 5c (gate). Add:

```
When iron-requirements has acceptance_criteria for a REQ-U-*:
  Gate: ac_ids populated for features covering that requirement
When no acceptance_criteria: existing req_ids gate applies
```

- [ ] **Step 4: Update p5s-func-verify-orchestrator — ac_ids in RTM and cocotb**

Find Step 2 (cocotb TB generation). Add:

```
Tag test functions with ac_ids when acceptance_criteria exist:
- `# Covers: REQ-U-012.AC-1` for each covered criterion
- Fall back to `# Covers: REQ-U-012` when no AC
```

Find Step 5 (RTM generation). Add:

```
Generate RTM with AC-level columns when acceptance_criteria exist:
| REQ ID | AC ID | Description | Test Case | Status |
When no AC, use existing REQ-level format.
```

- [ ] **Step 5: Update sva-extractor — AC bind comments**

Add to the SVA property generation section:

```
Include AC coverage comments in SVA bind files:
- If acceptance_criteria exist: `// Covers: REQ-U-012.AC-1`
- If no acceptance_criteria: `// Covers: REQ-U-012`
```

- [ ] **Step 6: Validate all 5 files**

```bash
grep -c 'ac_ids\|AC-[0-9]' agents/testbench-dev.md agents/test-plan-writer.md agents/p4s-unit-test-orchestrator.md agents/p5s-func-verify-orchestrator.md agents/sva-extractor.md
```
Expected: ≥1 per file

- [ ] **Step 7: Commit**

```bash
git add agents/testbench-dev.md agents/test-plan-writer.md agents/p4s-unit-test-orchestrator.md agents/p5s-func-verify-orchestrator.md agents/sva-extractor.md
git commit -m "feat(GAP4-step3): add ac_ids tagging to schema producers with fallback (5 files)"
```

### Task 15: Step 4 — Schema Consumers (Category C: 7 files)

**Files:**
- Modify: `agents/compliance-checker.md`
- Modify: `agents/requirement-tracer.md`
- Modify: `agents/coverage-analyst.md`
- Modify: `agents/p5-verify-orchestrator.md`
- Modify: `agents/p5a-functional-closure-orchestrator.md`
- Modify: `skills/rtl-p5-verify/SKILL.md`
- Modify: `skills/rtl-p5-verify-team/SKILL.md`

- [ ] **Step 1: Update compliance-checker — polymorphic AC handling**

Find the acceptance_criteria iteration section (already exists). Enhance:

```
When iterating acceptance_criteria:
- If item is a string (P1/P2 format): treat as single criterion at REQ level
- If item is an object with ac_id (P3 format): track at ac_id level
  For each ac_id, verify a test exists with matching ac_ids tag
  Report UNTESTED for any ac_id without test coverage
```

- [ ] **Step 2: Update requirement-tracer — AC-level RTM columns**

Add AC-level RTM support:

```
When building RTM and requirement has structured acceptance_criteria (object array with ac_id):
- Add per-AC rows: | REQ ID | AC ID | Description | Test Case | Status |
- Status per AC: VERIFIED, FORMAL, PARTIAL, UNTESTED, NOT_VERIFIABLE
- UNTESTED Critical/High AC → FAIL (blocks P6)
When acceptance_criteria is string array or absent: existing REQ-level RTM
```

- [ ] **Step 3: Update coverage-analyst — ac_id in gap reports**

Add:

```
When reporting coverage gaps, include ac_id reference if available:
- "Gap G01: cg_handshake.cp_backpressure not hit — relates to REQ-U-012.AC-3"
When no ac_id available, reference REQ only.
```

- [ ] **Step 4: Update p5-verify-orchestrator — Stage 3 AC-level audit**

Find Stage 3 traceability audit. Add:

```
Traceability audit operates at AC level when structured acceptance_criteria exist:
- Each Critical/High ac_id must be VERIFIED or FORMAL
- UNTESTED Critical/High ac_id → FAIL (blocks P6 entry)
When no structured AC: existing REQ-level audit
```

- [ ] **Step 5: Update p5a-functional-closure-orchestrator**

Find the functional closure gate. Add:

```
Functional closure includes AC coverage when acceptance_criteria exist:
- All Critical/High ac_ids must have VERIFIED or FORMAL status
When no structured AC: existing closure gate applies
```

- [ ] **Step 6: Audit and update rtl-p5-verify/SKILL.md and rtl-p5-verify-team/SKILL.md**

Both files already reference `acceptance_criteria` in freetext form.
Update to reference the new structured ac_id format:

```
Replace freetext "acceptance_criteria" references with:
"acceptance_criteria (structured format with ac_id when available from P3)"
```

- [ ] **Step 7: Validate all 7 files**

```bash
grep -c 'ac_ids\|ac_id' agents/compliance-checker.md agents/requirement-tracer.md agents/coverage-analyst.md agents/p5-verify-orchestrator.md agents/p5a-functional-closure-orchestrator.md skills/rtl-p5-verify/SKILL.md skills/rtl-p5-verify-team/SKILL.md
```
Expected: ≥1 per file

- [ ] **Step 8: Commit**

```bash
git add agents/compliance-checker.md agents/requirement-tracer.md agents/coverage-analyst.md agents/p5-verify-orchestrator.md agents/p5a-functional-closure-orchestrator.md skills/rtl-p5-verify/SKILL.md skills/rtl-p5-verify-team/SKILL.md
git commit -m "feat(GAP4-step4): add ac_ids consumption to verifiers and consumers (7 files)"
```

### Task 16: Step 5 — Gate/Completion Criteria (Category D: 5 files)

**Files:**
- Modify: `skills/rtl-p4-implement-policy/SKILL.md`
- Modify: `skills/rtl-p5-verify-policy/SKILL.md`
- Modify: `skills/rtl-p5a-functional-closure-policy/SKILL.md`
- Modify: `skill-completion-criteria.json`
- Modify: `phase-registry.json`

- [ ] **Step 1: Update P4 implement policy — Wave 6b gate**

Find Wave 6b gate criteria. Add:

```
When iron-requirements has acceptance_criteria for a REQ-U-*:
  ac_ids populated for each unit test feature covering that requirement (advisory, not hard-block at P4)
```

- [ ] **Step 2: Update P5 verify policy — module graduation**

Find Module Graduation Gate. Add:

```
AC-level VERIFIED condition for Critical/High requirements when structured AC exists:
  Every Critical/High ac_id must have status VERIFIED or FORMAL for module graduation
```

- [ ] **Step 3: Update functional verify policy — P5A closure**

Find P5A closure gate. Add:

```
Functional closure includes AC-level coverage when structured acceptance_criteria exist.
All Critical/High ac_ids must be VERIFIED or FORMAL for P5A closure.
```

- [ ] **Step 4: Update skill-completion-criteria.json**

Read the file. The format uses pipe-delimited strings for each skill.
For skills `rtl-p4-implement`, `rtl-p4-implement-team`, `rtl-p4s-unit-test`,
`rtl-p5-verify`, `rtl-p5-verify-team`, `rtl-p5s-func-verify`:
append `|ac-coverage-check` to each skill's existing `completion_criteria` string.

Example: `"completion_criteria": "rtl-written|lint-pass|...|ac-coverage-check"`

- [ ] **Step 5: Update phase-registry.json**

Read the file. Find the `skills` section (pipe-delimited `completion_criteria` strings).
For the same skills listed in Step 4, append `|ac-coverage-check` to the
`completion_criteria` string, matching `skill-completion-criteria.json` updates.

- [ ] **Step 6: Validate 4-way sync**

```bash
grep -c 'ac_ids' skills/rtl-p4-implement-policy/SKILL.md skills/rtl-p5-verify-policy/SKILL.md skills/rtl-p5a-functional-closure-policy/SKILL.md skill-completion-criteria.json phase-registry.json
```
Expected: ≥1 per file

- [ ] **Step 7: Commit**

```bash
git add skills/rtl-p4-implement-policy/SKILL.md skills/rtl-p5-verify-policy/SKILL.md skills/rtl-p5a-functional-closure-policy/SKILL.md skill-completion-criteria.json phase-registry.json
git commit -m "feat(GAP4-step5): add ac_ids to gate/completion criteria, 4-way sync (5 files)"
```

### Task 17: Step 6 — Team Mode Parity (Category F: 3 files)

**Files:**
- Modify: `agents/p4-implement-team-orchestrator.md`
- Modify: `agents/p5-verify-team-orchestrator.md`
- Modify: `agents/p4-block-parallel-coordinator.md`

- [ ] **Step 1: Update P4 team orchestrator — Wave 6b ac_ids gate**

Find Wave 6b task definition. Add ac_ids gate symmetric with non-team:

```
Wave 6b task gate: ac_ids populated when acceptance_criteria exist (advisory)
Matches non-team p4-implement-orchestrator Wave 6b gate
```

- [ ] **Step 2: Update P5 team orchestrator — AC-level traceability**

Find verification task definitions. Add:

```
V5/V6 tasks: AC-level traceability when structured acceptance_criteria exist
RTM output: AC-level columns matching non-team p5-verify-orchestrator
```

- [ ] **Step 3: Update block-parallel coordinator — ac_ids directive**

Find block worker TB dispatch. Add:

```
Block worker test generation: tag ac_ids when acceptance_criteria exist.
Fallback: tag req_ids only when no AC.
```

- [ ] **Step 4: Validate parity**

```bash
grep -c 'ac_ids' agents/p4-implement-team-orchestrator.md agents/p5-verify-team-orchestrator.md agents/p4-block-parallel-coordinator.md
```
Expected: ≥1 per file

- [ ] **Step 5: Commit**

```bash
git add agents/p4-implement-team-orchestrator.md agents/p5-verify-team-orchestrator.md agents/p4-block-parallel-coordinator.md
git commit -m "feat(GAP4-step6): sync ac_ids handling in team mode orchestrators (3 files)"
```

### Task 18: Final Regression + Post-Implementation

- [ ] **Step 1: Full test suite**

Run: `cd ~/work/rtl-agent-team && pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Agent count verification**

Run: `ls agents/*.md | wc -l`
Expected: 94

- [ ] **Step 3: Verify ac_ids propagation**

```bash
echo "=== ac_ids total references ===" && grep -r 'ac_ids' --include='*.md' --include='*.json' | wc -l
```
Expected: ≥28 (across 28 GAP 4 files)

- [ ] **Step 4: Update CLAUDE.md agent count**

Change `93 specialized agents` → `94 specialized agents` in CLAUDE.md

- [ ] **Step 5: Update README and README_kr agent count**

Change agent count 93 → 94 in both files

- [ ] **Step 6: Update CHANGELOG.md**

Add to `[Unreleased]` section:

```markdown
### Added
- Test plan generation (Wave 0 Step 0b) before RTL implementation — TDD-style verification
- P4→P5 coverage handoff — P5 CDTG uses Tier 2 baseline for incremental gap closure
- Structured acceptance criteria (ac_id) in iron-requirements.json with criteria-level traceability
- New `test-plan-writer` agent for spec-driven test scenario derivation
```

- [ ] **Step 7: Commit post-implementation updates**

```bash
git add CLAUDE.md README.md README_kr.md CHANGELOG.md
git commit -m "docs: update agent count (94), changelog for coverage-driven verification"
```

- [ ] **Step 8: Update Obsidian documentation**

Update `~/obsidian/claude/rtl-agent-team/` docs to reflect:
- Agent count: 93 → 94
- Wave 0 expansion (Step 0a + 0b)
- AC schema in test verification pipeline
- New test-plan-writer agent

- [ ] **Step 9: Final verification complete**

All 3 phases complete. 32 unique files modified (1 new + 31 modified).
