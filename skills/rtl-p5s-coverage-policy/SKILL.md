---
name: rtl-p5s-coverage-policy
description: "Internal reference: rtl p5s coverage policy (agent-loaded; do not invoke)."
user-invocable: false
---

# Coverage Analysis Policy

## Coverage Targets

| Metric | Target | Evaluated On |
|--------|--------|-------------|
| Line coverage | ≥ 90% | Post-exclusion |
| Toggle coverage | ≥ 80% | Post-exclusion |
| FSM coverage | ≥ 70% | Post-exclusion |

Raw coverage is always reported alongside post-exclusion numbers for transparency.

## Coverpoint Iterative Refinement (minimum 3 rounds)

Coverage coverpoint extraction and test generation must iterate at least 3 times:

- **Round 1 (Initial Analysis)**: Identify all uncovered lines, branches, FSM states/transitions. Prioritize gaps (HIGH/MED/LOW). Generate first batch of directed tests for HIGH gaps.
- **Round 2 (Deepen)**: Re-analyze coverage after Round 1 tests. Identify newly reachable but still uncovered paths. Add cross-coverage points (e.g., cmd × size, state × error). Target MED gaps. Check for unreachable code (waiver candidates).
- **Round 3 (Close)**: Final coverage push. Add corner-case stimulus for remaining gaps. Verify coverage targets met (line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%). Document waived bins with justification.
- **Additional rounds**: Continue until coverage targets are met or all remaining gaps are justified as waived.

Each round produces a progress note at `.rat/scratch/phase-5/coverage-iteration-r{N}.md`.

## Escalation & Stop Conditions

- LOW priority gaps flagged as unreachable → report to user, recommend dead code removal
- Coverage tool format unrecognized → halt, ask user for coverage format (Icarus, VCS, etc.)
- Coverage below 70% after gap fill → escalate to rtl-architect for structural review

## Final Checklist

- [ ] sim/coverage/coverage_gaps.md written with all gaps prioritized
- [ ] New tests written for all HIGH priority gaps
- [ ] Coverage improvement measured and reported
- [ ] Unreachable code gaps flagged separately

## CDTG Feedback Protocol (Coverage → Testbench-Dev)

When coverage-analyst identifies HIGH/CRITICAL gaps, it must produce a **Directed Test Guidance** table
that testbench-dev can directly consume. This closes the Coverage-Driven Test Generation loop
with structured, actionable feedback — not just gap descriptions.

### Feedback Format (coverage-analyst → testbench-dev)

The canonical table format (columns: Gap ID | Uncovered Bin | Constraint | Sequence |
Expected Behavior) is OWNED by the coverage-analyst agent prompt ("Directed Test Guidance"
output format) — the producer. Field semantics:
- **Constraint**: Signal value ranges or conditions that must hold to reach the uncovered bin
- **Sequence**: Temporal ordering of stimulus (clock-cycle-level when possible)
- **Expected Behavior**: Observable DUT response that confirms the bin was hit
- **ac_id linkage**: not a table column — gaps map to acceptance criteria in the gap report
  text (e.g., "Gap G01 ... relates to REQ-U-012.AC-3", per coverage-analyst's ac_id protocol);
  when no structured AC exists, reference the REQ ID instead

### Testbench-Dev Consumption

testbench-dev reads the Directed Test Guidance table and generates one cocotb test function
per row. Each test:
1. Applies the **Constraint** as signal assignments
2. Follows the **Sequence** as a cycle-accurate stimulus plan
3. Asserts the **Expected Behavior** as a pass/fail check

### Convergence Loop

```
Round N: coverage-analyst → Directed Test Guidance table
         test-plan-writer  → systematic test plan (ECP/BVA for config-dependent gaps)
         testbench-dev    → test_coverage_fill_rN.py (one test per guidance row + plan)
         eda-runner       → regression with new tests → updated coverage
Round N+1: coverage-analyst re-analyzes → new guidance for remaining gaps
```

This iterates until coverage targets are met or all remaining gaps are justified as waived.

## Systematic Parameter Space Analysis (Config-Dependent Gaps)

When coverage gaps depend on configuration/parameter combinations (e.g., PPS settings,
QP values, pixel formats, buffer sizes), test-plan-writer applies systematic test design
methodology before testbench-dev generates tests:

1. **Equivalence Class Partitioning (ECP)**: Partition each parameter into equivalence classes
   that produce the same coverage behavior. Example for a rate control module:
   - bits_per_pixel: {low (< 4), medium (4-8), high (> 8)}
   - initial_qp: {min boundary, mid-range, max boundary}
   - pixel_entropy: {flat, textured, edge-heavy}

2. **Boundary Value Analysis (BVA)**: For each parameter, test at min, min+1, nominal, max-1, max

3. **Combination strategy**: Use pairwise/all-pairs for 3+ parameters to keep test count
   manageable while covering all 2-way interactions

4. **Trigger condition**: coverage-analyst identifies gaps that correlate with specific parameter
   configurations (e.g., "toggle coverage low on RC buffer overflow path — only reachable when
   bits_per_pixel < 4 AND initial_qp > 45") → test-plan-writer is invoked for systematic
   parameter space partitioning

test-plan-writer produces `sim/{module}/coverage/directed_test_plan.md` which testbench-dev
consumes alongside the Directed Test Guidance table.

## Coverage Exclusion Protocol

When coverage-driven regression converges without meeting targets:

1. **Convergence detection**: 2 consecutive iterations with < 0.5% improvement → converged
2. **Uncovered bin analysis**: Classify each uncovered bin as:
   - STIMULUS_GAP: Reachable but not exercised → add directed test
   - STRUCTURAL_DEAD: Unreachable code (parameter guard, unimplemented feature) → exclude with waiver
   - INFRA_CODE: TB/UVM infrastructure not under test → exclude from report scope
3. **Exclusion file**: Generate tool-neutral exclusion manifest (`coverage-exclusions.json`)
   listing each excluded bin. Per-tool export: Verilator/lcov `--remove` filter, VCS URG `-elfile`,
   Xcelium IMC exclusion file, or Questa UCDB exclusion as applicable
4. **Documentation**: Record each exclusion in `reviews/phase-5-verify/{module}-coverage-exclusions.md`
   with: bin name, module, reason, approver
5. **Approval**: Default approver is coverage-analyst (automated) for standard exclusion categories
   (UVM/TB infrastructure, parameter guards, toggle on wide buses). Non-standard exclusions
   (unimplemented features, any bin where spec applicability is ambiguous) require user approval
   via AskUserQuestion before finalizing
6. **Adjusted targets**: Report both raw and excluded coverage numbers

### Exclusion Categories

| Category | Example | Action | Approval |
|----------|---------|--------|----------|
| UVM/TB infrastructure | uvm_pkg, tb_*, axi4s_if | Always exclude | Auto (coverage-analyst) |
| Parameter guards | `if (BPC > 16)` | Exclude (dead by design) | Auto (coverage-analyst) |
| Toggle on wide buses | 128-bit output upper bits | Exclude if functionally verified | Auto (coverage-analyst) |
| Unimplemented features | 4:2:2 chroma paths (out-of-scope) | Exclude only if explicitly out-of-scope or parameter-disabled; escalate if required by spec | **User** (AskUserQuestion) |
| Ambiguous spec applicability | Any bin where it is unclear whether the spec requires coverage | Escalate — exclude only with explicit confirmation | **User** (AskUserQuestion) |

## Coverage Data Processing and Gap Prioritization

Coverage data processing with Verilator:
```bash
# Annotate source files with coverage data
verilator_coverage --annotate coverage_annotated/ coverage.dat

# Convert to lcov for HTML reports
verilator_coverage --write-info coverage.info coverage.dat
genhtml coverage.info -o sim/coverage/html/
```

Gap prioritization heuristics:
- **Critical**: uncovered error/safety paths (overflow, underflow, reset, ECC)
- **High**: uncovered protocol corner cases (backpressure, burst boundary, empty/full)
- **Medium**: uncovered performance paths (stall, pipeline bubble)
- **Low**: uncovered debug/diagnostic paths (no functional impact)
- **Waive**: structurally unreachable code (dead FSM states, impossible combinational conditions)

### Benign vs Critical Gap Assessment

Not all uncovered bins indicate missing tests. Before generating directed tests, coverage-analyst
must classify each gap as **critical** (requires test) or **benign** (can be documented and accepted):

| Condition | Classification | Action |
|-----------|---------------|--------|
| DUT structurally cannot produce the stimulus (e.g., input idle never asserted because DUT always drives ready) | Benign | Document with RTL evidence (file:line) |
| Gap requires specific config that is out-of-scope | Benign | Document as config-excluded |
| Gap is reachable but requires rare multi-cycle sequence | Critical | test-plan-writer designs directed stimulus |
| Gap correlates with a specific parameter configuration | Critical | test-plan-writer applies ECP/BVA on config space |
| Gap involves cross-module data flow not exercised | Critical | Escalate to integration-verifier |

Benign gaps are recorded in the coverage report with justification (not silently excluded).

### Per-Metric Convergence Tracking

Track convergence independently for each coverage metric:

| Metric | Tracked Separately | Why |
|--------|-------------------|-----|
| Line | Yes | May converge early (often 90%+ in first iteration) |
| Toggle | Yes | Wide buses converge slowly; upper bits rarely toggle |
| FSM | Yes | Small state space; usually converges quickly |
| Branch | Yes | Conditional paths may need config-specific tests |
| Functional | Yes | Depends on covergroup design quality |

A metric is converged when 2 consecutive rounds show < 0.5% improvement FOR THAT METRIC.
Overall convergence requires ALL metrics either meeting target or individually converged.
This prevents aggregate convergence masking a single lagging metric.

## Toggle Coverage Interpretation

When toggle coverage converges below target despite diverse stimulus:

1. **Per-signal toggle analysis**: identify signals with < 10% toggle rate
2. **Root cause classification**:
   - STIMULUS: Data values don't exercise full range → add directed sequence
   - PARAMETERIZATION: Bus wider than needed for current config → **design issue, not test issue**
   - STRUCTURAL: Tied/constant signals → exclude with waiver
3. **If PARAMETERIZATION**: file as design improvement recommendation (Phase 3 bus width
   parameterization violation), do NOT add more test sequences
4. **Anti-pattern**: repeatedly adding sequences for structurally-zero upper bits on
   over-wide buses — this wastes regression time without coverage improvement

### Detection Heuristic
When coverage-analyst observes a module where:
- Upper N bits of a wide bus have 0% toggle across ALL seeds and ALL tests
- Lower bits have normal toggle (> 50%)
→ Classify as PARAMETERIZATION, not STIMULUS_GAP. Report the bus width vs actual
data range mismatch and recommend parameterized width derivation per `rtl-p3-uarch-policy`.

### Configuration-to-Code-Path Mapping

When designs have configurable parameters that activate different code paths (e.g., PPS settings
in codecs, mode registers in processors, feature enables in peripherals):

1. **test-plan-writer** must identify which parameters control which code paths, as a mapping
   table with columns `| Parameter | Value Range | Code Path Activated | Coverage Impact |`
   (e.g., `mode_reg = BYPASS → bypass datapath activated → branch coverage in {module}_ctrl`)

2. **coverage-analyst** uses this mapping to diagnose coverage gaps:
   - Gap in rate_control branch? → Check if low-bpp config was tested
   - Gap in recon_engine toggle? → Check if high-QP config was tested

3. **testbench-dev** generates test variants with config constraints matched to uncovered paths

Convergence estimation: if N random seeds cover M% of bins, estimate additional seeds needed
using the formula: seeds_needed ≈ N × ln(100/(100-target)) / ln(100/(100-M)).
This is approximate — directed tests are always more efficient for specific uncovered bins.
