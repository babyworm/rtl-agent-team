---
name: rtl-p5s-func-verify-policy
description: "Policy rules, multi-seed strategy, coverage targets, signal naming conventions, traceability format, and checklists for Tier 3 module-level cocotb regression. Pure reference — no orchestration."
user-invocable: false
---

# Tier 3 Functional Verification Policy

## Testing Tier Context

```
Tier 1: Smoke Test     — connectivity, R/W, basic ops (rtl-p4-implement Wave 4)
Tier 2: Unit Test      — reference comparison, uarch features (rtl-p4s-unit-test)
Tier 3: Module Regr.   — cocotb multi-seed (THIS POLICY)
Tier 4: Integration    — cross-module, end-to-end (rtl-p5s-integration-test)
```

Tier transition rules:
- Tier 2 PASS (rtl-p4s-unit-test) → Tier 3 eligible
- Tier 3 PASS or PARTIAL_PASS (this skill) → Tier 4 eligible (rtl-p5s-integration-test)
  (PARTIAL_PASS = some Critical/High ac_ids PARTIAL; WARNING at Stage 1, escalated to FAIL at Stage 3)
- Tier 3 FAIL → fix via rtl-p4s-bugfix, re-run Tier 2 then Tier 3

## cocotb Signal Naming Convention

cocotb test files MUST use correct signal names matching RTL port conventions:
- Signal access: `dut.i_data` (NOT `dut.data_i`), `dut.o_valid` (NOT `dut.valid_o`)
- Clock: `dut.clk` (single domain) or `dut.sys_clk` (multiple domains) — NOT `dut.clk_i`
- Reset: `dut.rst_n` (single domain) or `dut.sys_rst_n` (multiple domains) — NOT `dut.rst_ni`
- cocotb clock utility: `cocotb.clock.Clock(dut.sys_clk, 10, units="ns")`
- Reset sequence: drive `dut.sys_rst_n.value = 0`, wait, then `dut.sys_rst_n.value = 1`

## Multi-Seed Strategy

- Default 5 seeds: 1, 42, 123, 1337, 65536 (configurable via `sim/regression/seed_list.txt`)
- Each seed tests different random stimulus ordering
- A module passes multi-seed regression only when ALL seeds pass
- Use `COCOTB_RESOLVE_X=RANDOM` for X-state handling
- Use `RANDOM_SEED={seed}` for reproducibility

## Execution Strategy

- **Local-first runtime**: default to local execution on current host (`--mode local`)
- **Default parallel budget**: use `max(1, nproc-2)` unless user explicitly overrides `--parallel`
- **AWS usage policy**: `aws-batch` is allowed only when the user explicitly asks to use AWS
  and explicit gate/runner wiring exists (`RTL_ALLOW_AWS=1`, `RTL_AWS_BATCH_RUNNER`)
- **Pipelined**: as each module's TB completes → immediately launch sim (don't wait for all TBs)
- **Module-level parallelism**: each module's TB + sim runs as an independent parallel task
- **Multi-seed parallelism**: queue 5 seeds × N modules; local active workers stay within `max(1, nproc-2)`
- **Incremental coverage**: coverage-analyst starts partial analysis on completed modules
- **Early termination**: >5% failure rate across seeds → halt and report immediately

## Coverage Targets

| Metric | Target |
|--------|--------|
| Line coverage | ≥ 90% |
| Toggle coverage | ≥ 80% |
| FSM coverage | ≥ 70% |

Below target: testbench-dev generates additional tests → re-run regression.

## Coverage Collection

```bash
# Verilator compilation with coverage
make -C sim/{module} SIM=verilator EXTRA_ARGS="--coverage --trace-fst" TOPLEVEL=dut MODULE=test_dut

# Merge multi-seed coverage data
verilator_coverage --write-info merged.info seed_*/coverage.dat

# Coverage HTML report
genhtml sim/coverage/merged.info -o sim/coverage/html/ --title "Regression Coverage"
```

## Regression Scripts

```bash
# Automated multi-seed regression
bash skills/rtl-p5s-func-verify/scripts/run_regression.sh \
  --mode local --seeds "1 42 123 1337 65536" --sim verilator

# Optional override when user explicitly asks
bash skills/rtl-p5s-func-verify/scripts/run_regression.sh \
  --mode local --parallel "$(($(nproc)-2))" --seeds "1 42 123 1337 65536" --sim verilator

# Coverage merge
bash skills/rtl-p5s-func-verify/scripts/merge_coverage.sh \
  --format verilator --output sim/coverage/merged.info
```

## Requirement Traceability Matrix Format

Save to `reviews/phase-5-verify/requirement-traceability.md`:

### AC-Level Format (when structured acceptance_criteria with ac_id exist in iron-requirements)

When `iron-requirements.json` contains structured `acceptance_criteria` entries (object arrays with `ac_id`
fields), the RTM uses AC-level granularity:

```markdown
# Phase 5 Review: Requirement Traceability
- Date: YYYY-MM-DD
- Reviewer: func-verifier
- Upper Spec: iron-requirements.json
- Verdict: PASS | PARTIAL_PASS | FAIL

## Feature Coverage Checklist
| REQ ID | AC ID | Description | Test Case | Status |
|--------|-------|-------------|-----------|--------|

## Findings
### [severity] Finding-N: ...

## Verdict
PASS | PARTIAL_PASS | FAIL: [reason]
- PASS: all Critical/High ac_ids VERIFIED or FORMAL
- PARTIAL_PASS: some Critical/High ac_ids PARTIAL (WARNING at Stage 1, escalated to FAIL at Stage 3)
- FAIL: Critical/High ac_ids UNTESTED or tests failing
```

AC-level status values per criterion:
- `VERIFIED` — AC covered by a passing test
- `FORMAL` — AC proved by formal verification
- `PARTIAL` — AC partially covered (some test cases pass, scope limited)
- `UNTESTED` — AC exists but no test covers it
- `NOT_VERIFIABLE` — AC has `verifiable: false` (inspection-only); document in RTM, excluded from
  automated coverage tracking

VERIFIED judgment is made at the individual criterion level when `ac_id` fields are present.

### REQ-Level Format (backward compatible — when no structured AC)

When `acceptance_criteria` is absent or contains a plain string array (P1/P2 format), the RTM uses
the existing REQ-level format:

```markdown
## Feature Coverage Checklist
| REQ ID | Test Name | Result | Status |
|--------|-----------|--------|--------|
```

Verdict rules (Tier 3 module-level, aligns with Stage 1 2-tier model):
- `PASS` — all requirements (or acceptance criteria) verified with passing tests
- `PARTIAL_PASS` — some Critical/High ac_ids are PARTIAL (not yet VERIFIED/FORMAL).
  At Stage 1 module graduation: WARNING (proceed). At Stage 3 final audit: escalated to FAIL.
- `FAIL` — M requirements/criteria UNTESTED, K with failing tests
- Any REQ (or AC) UNTESTED → testbench-dev must generate additional tests
- PARTIAL Critical/High ac_ids → WARNING at this stage, must be resolved before Stage 3

## cocotb Ecosystem Quick Reference

- **cocotb-bus**: Base classes for Driver, Monitor, and Scoreboard
- **cocotbext-axi**: Ready-to-use AXI4/AXI4-Lite/AXI4-Stream masters and slaves
  - Example: `AxiLiteMaster(AxiLiteBus.from_prefix(dut, "s_axi"), dut.sys_clk, dut.sys_rst_n, reset_active_level=False)`
  - Stream: `AxiStreamSource(AxiStreamBus.from_prefix(dut, "s_axis"), dut.sys_clk, dut.sys_rst_n)`
- **cocotb-coverage**: Functional coverage with `@CoverPoint` and `@CoverCross` decorators
  - Example: `@CoverPoint("top.data", bins=[range(0,64), range(64,256)])`
- **TestFactory**: Parameterized test generation
  - Example: `TestFactory(run_test).add_option("width", [8,16,32]).generate_tests()`

See `references/cocotb-ecosystem.md` for complete API reference.

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

## Backward Traceability Policy

Test failure reports MUST include requirement impact analysis:
- Every failed test must list its affected req_ids and ac_ids (from `# Covers:` comments)
- Failed tests without coverage comments are flagged as UNTRACEABLE
- Failure Impact Summary table is mandatory in regression reports
- Priority classification: Critical/High → BLOCKING, Medium/Low → WARNING, unmapped → UNTRACEABLE

This policy ensures that test failures are immediately connected to requirements,
enabling prioritized debugging and requirement-level risk assessment.

## Escalation & Stop Conditions

- cocotb not installed → halt, provide install command (`pip install cocotb`)
- Failure persists after 2 RTL fix rounds → escalate to rtl-architect with waveform analysis
- Coverage below 80% after full regression → invoke rtl-p5s-coverage-analyze skill
- cocotb signal name mismatch error → testbench-dev must fix to use `i_`/`o_` convention
- Requirements with NO TEST COVERAGE after additional test generation → escalate to user
- Requirement traceability verdict FAIL with persistent test failures → escalate to rtl-p4-implement

## Final Checklist

- [ ] All cocotb tests use correct signal names (`dut.i_*`, `dut.o_*`, `dut.sys_clk`, `dut.sys_rst_n`)
- [ ] All test vectors run to completion
- [ ] RTL vs ref model comparison done per vector
- [ ] Waveform analysis done for all failures
- [ ] sim/coverage/coverage.xml generated
- [ ] sim/regression/*_result.json written per test
- [ ] Multi-seed regression passed (5 seeds per module: 1, 42, 123, 1337, 65536)
- [ ] Per-module pipelined execution used (TB → sim without waiting for all TBs)
- [ ] Coverage merged across seeds (sim/coverage/merged.info or sim/coverage/coverage.xml)
- [ ] Coverage targets met: line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%
- [ ] sim/regression/seed_{seed}_results.json written per seed
- [ ] Early termination applied if failure rate >5%
- [ ] Requirement Traceability Matrix produced (AC-level when structured acceptance_criteria exist, REQ-level otherwise)
- [ ] Every REQ-NNN in iron-requirements.json (preferred) or requirements.json (fallback) covered by at least one test
- [ ] When structured AC exists: every Critical/High ac_id is VERIFIED, FORMAL, or PARTIAL (PARTIAL = PARTIAL_PASS verdict at Stage 1, escalated to FAIL at Stage 3 final audit). UNTESTED = FAIL.
- [ ] All covered requirements pass their tests (or failures escalated)
- [ ] Traceability verdict is PASS or PARTIAL_PASS (PARTIAL_PASS = WARNING at Stage 1, escalated to FAIL at Stage 3)
- [ ] reviews/phase-5-verify/requirement-traceability.md saved
