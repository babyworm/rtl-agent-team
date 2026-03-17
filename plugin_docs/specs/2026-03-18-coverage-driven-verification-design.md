# Coverage-Driven Verification Enhancement Design

> Date: 2026-03-18
> Status: Draft (post-review revision 2)
> Scope: P3 exit → P4 Wave 0-10 → P5 V5/V6/Stage 3
> Impact: 32 unique files (1 new + 31 modified)

## Motivation

The current P4-P5 pipeline has three structural gaps that weaken coverage-driven verification:

1. **No Test Plan Before Implementation** — RTL is written first (Wave 1-5), testbenches designed
   after (Wave 6a/6b). Requirements-to-test mapping happens reactively, risking coverage gaps.
2. **No P4→P5 Coverage Handoff** — P4 Tier 2 achieves FSM≥50%, Line≥60% but P5 CDTG starts
   fresh, duplicating effort on already-covered regions.
3. **No Acceptance Criteria Granularity** — A REQ with 3 acceptance criteria is marked "covered"
   if any single test maps to it. Individual criteria are not tracked.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Test plan timing | Wave 0 expanded (Preparation + Test Plan), refined in Wave 6a/6b | TDD philosophy: plan tests from spec before implementation |
| Wave numbering | Expand existing Wave 0 internally (Step 0a + Step 0b). No renumbering. "10-Wave" label unchanged | Avoids cascading 15+ file updates for wave count references |
| Coverage handoff | P5 reads P4 Tier 2 results as baseline | Avoid redundant CDTG on already-covered regions |
| Acceptance criteria | Structured `ac_id` with `test_method` and `verifiable` | Enables criteria-level traceability and precise gap detection |
| Implementation order | GAP 2 → GAP 1 → GAP 4 (sequential) | Smallest-to-largest impact; each step stabilized before next |
| Backward compatibility | Fallback to `req_ids` when `acceptance_criteria` absent or empty | Existing projects continue working without migration |

---

## GAP 2: P4→P5 Coverage Handoff

### Problem

P4 Tier 2 coverage data (`sim/{module}/{module}_unit_results.json`) is not consumed by P5.
P5 CDTG starts from scratch, duplicating effort on already-covered FSM states and code paths.

Note: `phase-registry.json` already declares `sim/` as P5 required artifact, but no P5
orchestrator actually reads the Tier 2 coverage data for baseline initialization.

### Design

P5 func-verify orchestrator reads Tier 2 results as initial baseline. CDTG prioritizes
uncovered regions identified by comparing current coverage against Tier 2 data.

**Handoff artifact**: `sim/{module}/{module}_unit_results.json` (already exists, no schema change)

**Flow**:

```
P4 Wave 6b output:
  sim/{module}/{module}_unit_results.json
    ├── coverage: {line_pct, fsm_pct, toggle_pct}
    ├── features: [{name, status, req_ids}]
    └── func_coverage: {covergroups_defined, bins_hit, bins_total}

P5 Step 0 (enhanced — upstream artifact scan):
  Glob("sim/**/*_unit_results.json")   ← NEW: add to artifact scan
  If found: baseline_available = true
  If missing: WARNING, proceed without baseline (graceful degradation)

P5 Step 1 (enhanced):
  Read unit_results.json for each module
    ├── Extract "already covered features" list
    ├── Identify coverage baseline (e.g., FSM 55%, Line 63%)
    └── Pass to CDTG: "focus on uncovered FSM states: [S_ERROR, S_FLUSH]"

P5 CDTG Round 1:
  coverage-analyst receives baseline
    └── Directive: "Tier 2 achieved FSM 55%, Line 63%.
         Uncovered states: [S_ERROR, S_FLUSH]. Prioritize these."
```

### Files Modified (3)

| File | Change |
|------|--------|
| `agents/p5s-func-verify-orchestrator.md` | Step 0: add `Glob("sim/**/*_unit_results.json")` to upstream artifact scan. Step 1: add Tier 2 result loading per module. Step 2: "build incrementally on Tier 2 baseline" directive. Step 3.5: pass baseline to coverage-analyst. |
| `agents/p5-verify-orchestrator.md` | Step 0: add `Glob("sim/**/*_unit_results.json")` to upstream scan. Stage 1 V5 dispatch: include "load Tier 2 baseline" in func-verify prompt. |
| `skills/rtl-p5s-func-verify-policy/SKILL.md` | New section: "Tier 2 Baseline Utilization" — CDTG must operate incrementally above Tier 2 coverage, not from scratch. If baseline unavailable, proceed from zero (graceful degradation). |

### Validation

- `pytest tests/` regression PASS
- Verify: p5s-func-verify-orchestrator Step 0 includes `Glob("sim/**/*_unit_results.json")`
- Verify: p5s-func-verify-orchestrator Step 1 references `{module}_unit_results.json` loading
- Verify: rtl-p5s-func-verify-policy has "Tier 2 Baseline Utilization" section

---

## GAP 1: Wave 0 Test Plan

### Problem

P4 is implement-first: RTL written (Wave 1-5), then testbench-dev derives test vectors
ad-hoc (Wave 6). Test scenarios are not planned from requirements before implementation.

### Design

Expand existing Wave 0 (Preparation) to include test plan generation. The existing
"module enumeration + mkdir" becomes Step 0a, and test plan generation becomes Step 0b.

**Key decision**: Wave 0 expands internally; no wave renumbering. The "10-Wave pipeline"
label remains accurate (Waves 1-10 are the main execution waves; Wave 0 is preparation).

**New agent**: `test-plan-writer`

**New artifact**: `sim/{module}/{module}_test_plan.md`

**Pipeline change**: Wave 0 gains Step 0b (test plan generation)

```
Wave 0: Preparation + Test Plan (expanded)
  Step 0a (existing): Module enumeration, mkdir, TODO list
  Step 0b (NEW): Test Plan generation
    test-plan-writer per module (parallel):
      Input:  docs/phase-3-uarch/{module}.md
              docs/phase-3-uarch/iron-requirements.json
              skills: [rtl-test-design-policy]
      Process:
        1. Extract features from uarch spec (FSM, pipeline, protocol, datapath)
        2. Map each feature to REQ-U-* from iron-requirements
        3. Apply ECP → equivalence class representative scenarios (all modules)
        4. Apply BVA → boundary value scenarios per input signal (all modules)
        5. Apply STT → FSM transition matrix scenarios (FSM modules only; skip for combinational)
        6. Apply DT → boolean combination matrix scenarios (modules with ≥3 boolean controls)
        7. Generate error injection plan
        8. Design planned coverage model (covergroups + expected bins)
      Output: sim/{module}/{module}_test_plan.md
  Gate: test plan exists for every module before proceeding to Wave 1

Wave 1-5: RTL implementation (unchanged)

Wave 6a (enhanced): Smoke + Test Plan Refinement
  testbench-dev reads {module}_test_plan.md
    ├── Discovers additional states/paths from RTL not in uarch spec
    ├── Updates test plan with RTL-specific scenarios (append, do not delete)
    └── Runs smoke test

Wave 6b (enhanced): Tier 2 Unit FROM Test Plan
  testbench-dev generates tests from test plan
    ├── TS-NNN → cocotb test function 1:1 mapping
    ├── Test plan gaps marked after execution
    └── Gate: ref_mismatches=0, FSM≥50%, Line≥60%
```

### Test Plan Artifact Format

```markdown
# Test Plan: {module}
- Source: docs/phase-3-uarch/{module}.md
- Iron Requirements: docs/phase-3-uarch/iron-requirements.json
- Generated: YYYY-MM-DD by test-plan-writer

## Requirements Coverage Map
| REQ ID | Description | Test Scenarios | Method |
|--------|------------|----------------|--------|
| REQ-U-012 | valid/ready handshake | TS-001, TS-002, TS-003 | cocotb + SVA |

## Test Scenarios
### TS-001: Normal handshake single-beat transfer
- Derived from: REQ-U-012, ECP(valid class: single-beat)
- Stimulus: i_valid=1, i_data=0xAB → wait ready → check o_data
- Expected: transfer completes in 1 cycle
- Coverage target: cg_handshake.cp_single_beat

### TS-002: Backpressure exceeding 16 cycles
- Derived from: REQ-U-012, BVA(ready deassert duration: boundary=16)
- Stimulus: i_valid=1, ready held low 17 cycles
- Expected: data integrity preserved, no protocol violation
- Coverage target: cg_handshake.cp_backpressure_long

### TS-003: Reset during active transfer
- Derived from: REQ-U-012, Error Injection(reset mid-transaction)
- Stimulus: active transfer → rst_n=0 → release → verify clean state
- Expected: FSM returns to spec-defined reset state, no residual data
- Coverage target: cg_fsm.cp_reset_recovery

## Coverage Model (Planned)
- Covergroups: cg_handshake, cg_fsm, cg_datapath
- Expected bins: ~25
- Target: FSM≥50%, Line≥60% (Tier 2 gate)

## Error Injection Plan
| Category | Scenarios |
|----------|----------|
| Protocol violation | valid deassert mid-transfer |
| Backpressure stress | ready low >16 cycles (legal stall) |
| Reset | mid-transaction, back-to-back reset |
| Invalid input | reserved encoding (per uarch spec) |
| Arithmetic | overflow/underflow at boundaries |

## Technique Applicability
| Technique | Applied | Reason |
|-----------|---------|--------|
| ECP | Yes | All modules have input signals |
| BVA | Yes | All modules have bounded inputs |
| STT | Yes/No | Only if module has FSM (skip for combinational) |
| DT | Yes/No | Only if module has ≥3 boolean control inputs |
```

### test-plan-writer Agent Design

```yaml
Role: Test plan generation specialist
Input: uarch spec + iron-requirements + rtl-test-design-policy
Output: sim/{module}/{module}_test_plan.md per module
Skills: [rtl-test-design-policy]
Spawn: One Task() per module, parallel execution
Constraints:
  - Must reference every REQ-U-* from iron-requirements
  - Must apply ECP and BVA unconditionally
  - Must apply STT only when FSM is present in uarch spec (skip for combinational modules)
  - Must apply DT only when ≥3 boolean control inputs exist
  - Must include error injection plan
  - Must include planned coverage model with explicit covergroup/bin names
  - Does NOT write code — only produces test plan document
```

### Files Modified (10)

| File | Change | Difficulty |
|------|--------|-----------|
| `agents/test-plan-writer.md` | **NEW**. Agent definition per above design | Medium |
| `agents/p4-implement-orchestrator.md` | Wave 0: add Step 0b after existing Step 0a. Spawn test-plan-writer per module | Low |
| `agents/p4-implement-team-orchestrator.md` | Wave 0 task graph: add test-plan task after preparation | Low |
| `agents/testbench-dev.md` | Investigation Protocol Step 0: load `{module}_test_plan.md`. Step 2: refine plan with RTL-discovered paths. Append, do not delete existing scenarios | Low |
| `skills/rtl-p4-implement-policy/SKILL.md` | Wave 0 expanded definition: Step 0a + Step 0b. Test plan gate: plan exists per module | Low |
| `skills/rtl-p4-implement/SKILL.md` | Skill description: mention test plan in Wave 0 | Low |
| `agents/p4-rtl-sanity-orchestrator.md` | Check test plan existence; if missing in rapid mode, generate before TB | Low |
| `agents/p4-block-parallel-coordinator.md` | Block worker dispatch: include Step 0b test plan generation | Low |
| `agents/coverage-analyst.md` | Read `{module}_test_plan.md` for planned bin mapping when analyzing gaps | Low |
| `agents/requirement-tracer.md` | Read `{module}_test_plan.md` for authoritative REQ→test-scenario mapping | Low |

### Supplementary: Routing Table Update

After creating `test-plan-writer.md`:
- Add entry to `skills/rtl-orchestrate/SKILL.md` agent catalog
- Run `sh scripts/sync_orchestrator_inject.sh` to regenerate hook routing block

### Validation

- `pytest tests/` regression PASS
- Verify: p4-implement-orchestrator Wave 0 has Step 0a (preparation) + Step 0b (test plan)
- Verify: testbench-dev Investigation Protocol references `{module}_test_plan.md`
- Verify: test-plan-writer agent references rtl-test-design-policy via skills field
- Verify: coverage-analyst and requirement-tracer reference `{module}_test_plan.md`
- Verify: `grep -r 'test-plan-writer' agents/ skills/` returns expected references

---

## GAP 4: Acceptance Criteria Schema

### Problem

`req_ids: ["REQ-U-012"]` checks requirement existence only. A REQ with 3 acceptance
criteria is marked "covered" if any single test maps to it. Individual criteria are
not tracked, leading to false confidence in verification completeness.

### Schema Changes

#### iron-requirements.json (P3 output)

Before:
```json
{"id": "REQ-U-012", "description": "valid/ready handshake", "priority": "Critical"}
```

After:
```json
{
  "id": "REQ-U-012",
  "description": "valid/ready handshake protocol",
  "priority": "Critical",
  "acceptance_criteria": [
    {
      "ac_id": "REQ-U-012.AC-1",
      "description": "valid must not change while ready=0",
      "test_method": "assertion",
      "verifiable": true
    },
    {
      "ac_id": "REQ-U-012.AC-2",
      "description": "ready assertion completes transfer within 1 cycle",
      "test_method": "cocotb",
      "verifiable": true
    },
    {
      "ac_id": "REQ-U-012.AC-3",
      "description": "backpressure >16 cycles must not corrupt data",
      "test_method": "cocotb",
      "verifiable": true
    }
  ]
}
```

#### unit_results.json (P4 Tier 2 output)

Before:
```json
{"name": "handshake_basic", "status": "PASS", "req_ids": ["REQ-U-012"]}
```

After:
```json
{
  "name": "handshake_basic",
  "status": "PASS",
  "req_ids": ["REQ-U-012"],
  "ac_ids": ["REQ-U-012.AC-1", "REQ-U-012.AC-2"]
}
```

#### RTM (P5 output)

Before:
```markdown
| REQ ID | Test Case | Status |
```

After:
```markdown
| REQ ID | AC ID | Description | Test Case | Status |
|--------|-------|-------------|-----------|--------|
| REQ-U-012 | AC-1 | valid stable during !ready | sva_handshake:12 | FORMAL |
| REQ-U-012 | AC-2 | transfer completion | test_handshake:62 | VERIFIED |
| REQ-U-012 | AC-3 | backpressure integrity | test_bp:30 | VERIFIED |
```

### Backward Compatibility

**Global rule**: Apply consistently across ALL producer and consumer files.

```
IF iron-requirements entry has acceptance_criteria AND array is non-empty:
  → Producers: tag ac_ids per covered criterion (e.g., # Covers: REQ-U-012.AC-1)
  → Consumers: verify ALL ac_ids covered; UNTESTED at AC level
  → RTM: report at AC level
ELIF acceptance_criteria is absent OR is empty array []:
  → Producers: tag req_ids only (e.g., # Covers: REQ-U-012, no .AC-N suffix)
  → Consumers: verify at req_ids level (existing behavior)
  → RTM: report at REQ level (existing behavior)
```

**Per-file fallback instructions**: Every Category B (producer) file MUST include:
> "When the requirement has no `acceptance_criteria` or the array is empty,
> fall back to `# Covers: REQ-U-012` (no .AC-N suffix). Do not fail or skip."

### Schema Evolution: P1/P2 String Arrays vs P3 Structured Objects

The `acceptance_criteria` field has different formats across phases:

```
P1 (research):  "acceptance_criteria": ["criterion 1", "criterion 2"]    ← string array
P2 (arch):      "acceptance_criteria": ["criterion 1", "criterion 2"]    ← string array
P3 (uarch):     "acceptance_criteria": [{ac_id, description, ...}]       ← object array (NEW)
```

**Coexistence rules**:
- P1/P2 `acceptance_criteria` as string arrays remain **unchanged**. This spec does NOT modify P1/P2 formats.
- P3 introduces the structured object-array format with `ac_id` fields. Only P3+ consumers use `ac_id` tracking.
- `compliance-checker.md` already generically iterates `acceptance_criteria` items. It must handle both:
  - String item: treat the entire string as a single criterion (existing behavior)
  - Object item: extract `ac_id` and `description` for structured tracking (new behavior)
- When compliance-checker encounters P1/P2 string-array format, it operates at req_ids level (no ac_id tracking possible). When it encounters P3 object-array format, it operates at ac_id level.
- **Explicit audit in Category C**: compliance-checker change description must verify polymorphic handling of string vs object `acceptance_criteria` items.

### Cascading Impact — Full File List (28 files across 7 categories)

#### Category A: Schema Definition (Source of Truth) — 5 files

| File | Change |
|------|--------|
| `skills/rtl-p4s-unit-test-policy/SKILL.md` | Add `ac_ids` field to unit_results.json schema. Tier 2 PASS requires ac_ids populated when AC exists |
| `skills/rtl-p5s-func-verify-policy/SKILL.md` | RTM format gains AC-level columns. VERIFIED judgment at criteria level |
| `skills/rtl-p5s-coverage-policy/SKILL.md` | CDTG gap references include ac_id when available |
| `skills/rtl-p5s-integration-test-policy/SKILL.md` | Integration test req_ids extended with optional ac_ids for AC-level traceability |
| `skills/rtl-p3-uarch-policy/SKILL.md` | iron-requirements schema definition with acceptance_criteria array spec |

#### Category B: Schema Producers (Writers) — 5 files

Each file MUST include the per-file fallback instruction (see Backward Compatibility above).

| File | Change |
|------|--------|
| `agents/testbench-dev.md` | Mandate `# Covers: REQ-U-012.AC-1` comment per test function. Fallback: `# Covers: REQ-U-012` when no AC |
| `agents/test-plan-writer.md` | Include ac_id mapping in test scenarios when AC exists. Fallback: req_id only |
| `agents/p4s-unit-test-orchestrator.md` | Step 5: collect ac_ids into result JSON (parse from test comments or explicit mapping). Step 5c: gate checks AC coverage when AC exists |
| `agents/p5s-func-verify-orchestrator.md` | Step 5: AC-level RTM. Step 2: ac_ids tagging in cocotb TB. Fallback: req_ids only |
| `agents/sva-extractor.md` | SVA property bind comment: `// Covers: REQ-U-012.AC-1`. Fallback: `// Covers: REQ-U-012` |

#### Category C: Schema Consumers (Readers/Verifiers) — 7 files

| File | Change |
|------|--------|
| `agents/compliance-checker.md` | Forward-trace at ac_id level when AC exists. "All AC tested" verification. NOTE: already iterates acceptance_criteria — enhance to use structured ac_id format |
| `agents/requirement-tracer.md` | RTM AC-level columns. UNTESTED judgment per AC |
| `agents/coverage-analyst.md` | Gap reports reference uncovered ac_ids. Read test plan for planned bin→AC mapping |
| `agents/p5-verify-orchestrator.md` | Stage 3 traceability audit at AC level |
| `agents/p5a-functional-closure-orchestrator.md` | Functional closure gate includes AC coverage |
| `skills/rtl-p5-verify/SKILL.md` | Audit existing `acceptance_criteria` references — update to use structured ac_id schema |
| `skills/rtl-p5-verify-team/SKILL.md` | Same audit — align with structured ac_id format |

#### Category D: Gate/Completion Criteria (4-way sync) — 5 files

| File | Change |
|------|--------|
| `skills/rtl-p4-implement-policy/SKILL.md` | Wave 6b gate: ac_ids populated condition (when AC exists). Advisory, not hard-block |
| `skills/rtl-p5-verify-policy/SKILL.md` | Module graduation: AC-level VERIFIED condition for Critical/High |
| `skills/rtl-functional-verify-policy/SKILL.md` | P5A closure gate includes AC coverage |
| `skill-completion-criteria.json` | Add ac_ids verification to relevant skills |
| `phase-registry.json` | completion_check includes AC coverage |

#### Category E: Upstream Producers (P3) — 3 files

Note: `rtl-p3-uarch-policy/SKILL.md` is in Category A (schema definition). P3-specific exit gate rules are added to the same file in the Category A change.

| File | Change |
|------|--------|
| `agents/uarch-designer.md` | Mandate acceptance_criteria array in iron-requirements generation (≥1 AC per REQ-U-*) |
| `skills/rtl-p3-uarch-design/SKILL.md` | P3 exit: advisory check "every REQ-U-* should have ≥1 AC" (WARNING, not hard-block — enforced by agent prompt, not hook) |
| `agents/p3-uarch-orchestrator.md` | iron-requirements generation prompt includes AC writing directive |

#### Category F: Team Mode Parity — 3 files

| File | Change |
|------|--------|
| `agents/p4-implement-team-orchestrator.md` | Wave 6b task: ac_ids gate synced with non-team |
| `agents/p5-verify-team-orchestrator.md` | Verification tasks: AC-level traceability synced |
| `agents/p4-block-parallel-coordinator.md` | Block worker TB: ac_ids directive |

#### Category G: Hook Libraries — 0 files (audited, no change needed)

`hooks/lib/artifact-map.sh` was audited: it only maps file paths to roles and checks file existence.
It does NOT validate JSON schema fields. Therefore, no modification is required for ac_ids awareness.

### Edge Cases

| Edge Case | Handling |
|-----------|---------|
| Module with no FSM | test-plan-writer skips STT. Coverage model omits FSM covergroup. Tier 2 FSM coverage gate N/A for this module |
| Module with <3 boolean controls | test-plan-writer skips DT. Other 3 techniques still applied |
| `acceptance_criteria` absent | All consumers fallback to req_ids-only (backward compatible) |
| `acceptance_criteria` is empty array `[]` | Treat as absent — same fallback as missing field |
| AC exists but `verifiable: false` | Exclude from coverage tracking. Document in RTM as "NOT_VERIFIABLE" |
| Partial AC coverage (some AC tested, some not) | Per-AC status in RTM: VERIFIED/PARTIAL/UNTESTED independently |

### Implementation Order within GAP 4

```
Step 1: Schema definitions (Category A: 5 files)
  └── Validate: grep all 5 files for ac_id/ac_ids/acceptance_criteria consistency
  └── Validate: empty-array handling specified in each schema

Step 2: Upstream P3 (Category E: 4 files)
  └── Validate: uarch-designer prompt mandates ≥1 AC per REQ-U-*
  └── Validate: P3 exit gate is advisory (WARNING not hard-block)

Step 3: Producers (Category B: 5 files)
  └── Validate: every producer file contains per-file fallback instruction
  └── Validate: testbench-dev tags ac_ids, unit_results JSON contains ac_ids
  └── Validate: p4s-unit-test-orchestrator Step 5 collects ac_ids, Step 5c checks coverage

Step 4: Consumers (Category C: 7 files)
  └── Validate: compliance-checker AC-level forward-trace works
  └── Validate: requirement-tracer AC-level RTM columns present
  └── Validate: rtl-p5-verify and rtl-p5-verify-team aligned with structured ac_id

Step 5: Gate/Completion (Category D: 5 files)
  └── Validate: 4-way sync test (schema ↔ gate ↔ checklist ↔ completion)
  └── Validate: grep ac_ids across all 5 files confirms consistent field name

Step 6: Team parity (Category F: 3 files)
  └── Validate: team ↔ non-team orchestrator diff shows symmetric ac_ids handling

Step 7: Hook library audit (Category G: 0 files — no change needed)
  └── Confirmed: artifact-map.sh checks file existence only, not schema fields
  └── No modification required
```

---

## Implementation Phases

### Phase I: GAP 2 — Coverage Handoff (3 files)

**Scope**: p5s-func-verify-orchestrator, p5-verify-orchestrator, p5s-func-verify-policy

**Validation**:
- `pytest tests/` regression PASS
- `grep -n 'unit_results' agents/p5s-func-verify-orchestrator.md` returns Step 0 + Step 1 hits
- `grep -n 'Tier 2 Baseline' skills/rtl-p5s-func-verify-policy/SKILL.md` returns section heading

### Phase II: GAP 1 — Wave 0 Test Plan (10 files)

**Scope**: NEW test-plan-writer.md + 9 file modifications

**Validation**:
- `pytest tests/` regression PASS
- `grep -n 'Step 0b\|test-plan-writer\|test_plan' agents/p4-implement-orchestrator.md` returns Wave 0 expansion
- `grep -n 'test_plan' agents/testbench-dev.md` returns Investigation Protocol reference
- `grep -n 'test_plan' agents/coverage-analyst.md agents/requirement-tracer.md` confirms P5 consumption
- `grep -rn 'test-plan-writer' skills/rtl-orchestrate/SKILL.md` confirms routing entry
- Agent count: 93 → 94

### Phase III: GAP 4 — Acceptance Criteria (28 files, 7 steps)

**Scope**: Schema change + all producers/consumers/gates/team parity (hook audit: no change needed)

**Validation per step** (concrete grep patterns):
- Step 1: `grep -c 'ac_ids\|ac_id\|acceptance_criteria' skills/rtl-p4s-unit-test-policy/SKILL.md skills/rtl-p5s-func-verify-policy/SKILL.md skills/rtl-p5s-coverage-policy/SKILL.md skills/rtl-p5s-integration-test-policy/SKILL.md skills/rtl-p3-uarch-policy/SKILL.md`
- Step 2: `grep -c 'acceptance_criteria' agents/uarch-designer.md agents/p3-uarch-orchestrator.md`
- Step 3: `grep -c 'ac_ids\|AC-[0-9]' agents/testbench-dev.md agents/test-plan-writer.md agents/p4s-unit-test-orchestrator.md agents/p5s-func-verify-orchestrator.md agents/sva-extractor.md`
- Step 4: `grep -c 'ac_ids\|ac_id' agents/compliance-checker.md agents/requirement-tracer.md agents/coverage-analyst.md agents/p5-verify-orchestrator.md agents/p5a-functional-closure-orchestrator.md skills/rtl-p5-verify/SKILL.md skills/rtl-p5-verify-team/SKILL.md`
- Step 5: `grep -c 'ac_ids' skills/rtl-p4-implement-policy/SKILL.md skills/rtl-p5-verify-policy/SKILL.md skills/rtl-functional-verify-policy/SKILL.md skill-completion-criteria.json phase-registry.json`
- Step 6: Diff team vs non-team orchestrators for symmetric ac_ids handling
- Step 7: `grep -c 'ac_ids\|acceptance_criteria' hooks/lib/artifact-map.sh` (audit)
- Final: `pytest tests/` full regression PASS

---

## Post-Implementation Verification

After all 3 phases complete:

1. `pytest tests/` — full regression (existing tests must pass)
2. Agent count verification: 93 → 94 (test-plan-writer added)
3. Skill count: 92 (unchanged — no new skills)
4. Hook count: 14 (unchanged — no new hooks)
5. CLAUDE.md agent count update: 93 → 94
6. README/README_kr agent count update
7. Routing table: `skills/rtl-orchestrate/SKILL.md` updated + `sh scripts/sync_orchestrator_inject.sh`
8. Obsidian documentation update (agent count, Wave 0 expansion, AC schema)
9. CHANGELOG.md entry
10. `grep -r 'acceptance_criteria\|ac_ids' --include='*.md' --include='*.json' | wc -l` — confirm expected reference count

## Impact Summary

| Phase | Listed Files | New | Modified | Category |
|-------|-------------|-----|----------|----------|
| GAP 2 | 3 | 0 | 3 | P5 orchestrators + policy |
| GAP 1 | 10 | 1 | 9 | P4 orchestrators + P5 consumers + routing |
| GAP 4 | 28 | 0 | 28 | Schema + producers + consumers + gates + P3 + team |
| **Unique Total** | **32** | **1** | **31** | (10 files shared between GAPs — listed in latest GAP) |

**Shared files** (10): Files appearing in multiple GAPs are modified incrementally per phase.
- GAP 1 → GAP 4 (7): testbench-dev, test-plan-writer, p4-implement-team-orchestrator,
  p4-block-parallel-coordinator, rtl-p4-implement-policy, coverage-analyst, requirement-tracer
- GAP 2 → GAP 4 (3): p5s-func-verify-orchestrator, p5-verify-orchestrator, rtl-p5s-func-verify-policy

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| GAP 4 cascading regression | Sequential 7-step implementation with per-step grep validation |
| Team ↔ non-team drift | Category F applied last, with explicit diff-based parity check |
| Backward incompatibility | Fallback specified globally AND per-producer-file; empty array treated as absent |
| Test plan overhead (Wave 0) | test-plan-writer is document-only (no simulation). Parallel per-module spawn |
| Stale test plans | Wave 6a/6b refinement updates plans from RTL reality (append-only) |
| Wave numbering confusion | Wave 0 expanded internally (Step 0a + 0b); no renumbering needed |
| Missing files in cascade | Categories A-G with explicit grep validation per step |
| No-FSM / no-DT modules | test-plan-writer conditionally skips STT/DT; documented in edge cases |
