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
- Tier 3 PASS (this skill) → Tier 4 eligible (rtl-p5s-integration-test)
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

## Regression Scripts (absorbed from rtl-regression-run)

```bash
# Automated multi-seed regression
bash skills/rtl-regression-run/scripts/run_regression.sh \
  --mode local --seeds "1 42 123 1337 65536" --sim verilator

# Optional override when user explicitly asks
bash skills/rtl-regression-run/scripts/run_regression.sh \
  --mode local --parallel "$(($(nproc)-2))" --seeds "1 42 123 1337 65536" --sim verilator

# Coverage merge
bash skills/rtl-regression-run/scripts/merge_coverage.sh \
  --format verilator --output sim/coverage/merged.info
```

## Requirement Traceability Matrix Format

Save to `reviews/phase-5-verify/requirement-traceability.md`:

```markdown
# Phase 5 Review: Requirement Traceability
- Date: YYYY-MM-DD
- Reviewer: func-verifier
- Upper Spec: requirements.json
- Verdict: PASS | FAIL

## Feature Coverage Checklist
| REQ ID | Test Name | Result | Status |
|--------|-----------|--------|--------|

## Findings
### [severity] Finding-N: ...

## Verdict
PASS | FAIL: [reason]
```

Verdict rules:
- `PASS` — all requirements verified with passing tests
- `FAIL` — M requirements without test coverage, K requirements with failing tests
- Any REQ with NO TEST COVERAGE → testbench-dev must generate additional tests

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
- [ ] Requirement Traceability Matrix produced with per-REQ-NNN mapping
- [ ] Every REQ-NNN in requirements.json covered by at least one test
- [ ] All covered requirements pass their tests (or failures escalated)
- [ ] Traceability verdict is PASS
- [ ] reviews/phase-5-verify/requirement-traceability.md saved
