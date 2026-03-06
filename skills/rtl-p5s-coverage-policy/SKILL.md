---
name: rtl-p5s-coverage-policy
description: "Policy rules, coverage targets (90% line, 80% toggle, 70% FSM), gap prioritization heuristics, 3-round iterative refinement protocol, and checklists. Pure reference — no orchestration."
user-invocable: false
---

# Coverage Analysis Policy

## Coverage Targets

| Metric | Target |
|--------|--------|
| Line coverage | ≥ 90% |
| Toggle coverage | ≥ 80% |
| FSM coverage | ≥ 70% |

## Coverpoint Iterative Refinement (minimum 3 rounds)

Coverage coverpoint extraction and test generation must iterate at least 3 times:

- **Round 1 (Initial Analysis)**: Identify all uncovered lines, branches, FSM states/transitions. Prioritize gaps (HIGH/MED/LOW). Generate first batch of directed tests for HIGH gaps.
- **Round 2 (Deepen)**: Re-analyze coverage after Round 1 tests. Identify newly reachable but still uncovered paths. Add cross-coverage points (e.g., cmd × size, state × error). Target MED gaps. Check for unreachable code (waiver candidates).
- **Round 3 (Close)**: Final coverage push. Add corner-case stimulus for remaining gaps. Verify coverage targets met (line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%). Document waived bins with justification.
- **Additional rounds**: Continue until coverage targets are met or all remaining gaps are justified as waived.

Each round produces a progress note at `.rtl-agent-team/scratch/phase-5/coverage-iteration-r{N}.md`.

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

For each HIGH/CRITICAL gap, coverage-analyst outputs:

| Gap ID | Uncovered Bin | Constraint | Sequence | Expected Behavior |
|--------|--------------|------------|----------|-------------------|
| G01 | `cg_input.cp_data[overflow]` | `i_data >= 2^(WIDTH-1)` | `i_valid=1 → wait 1 cycle → check o_overflow` | `o_overflow` asserted within 2 cycles |
| G02 | `cg_fsm.cp_transition[IDLE→ERR]` | `i_error=1 && state==IDLE` | `reset → i_valid=0 → i_error=1` | FSM transitions to ERR state |

Fields:
- **Constraint**: Signal value ranges or conditions that must hold to reach the uncovered bin
- **Sequence**: Temporal ordering of stimulus (clock-cycle-level when possible)
- **Expected Behavior**: Observable DUT response that confirms the bin was hit

### Testbench-Dev Consumption

testbench-dev reads the Directed Test Guidance table and generates one cocotb test function
per row. Each test:
1. Applies the **Constraint** as signal assignments
2. Follows the **Sequence** as a cycle-accurate stimulus plan
3. Asserts the **Expected Behavior** as a pass/fail check

### Convergence Loop

```
Round N: coverage-analyst → Directed Test Guidance table
         testbench-dev    → test_coverage_fill_rN.py (one test per guidance row)
         eda-runner       → regression with new tests → updated coverage
Round N+1: coverage-analyst re-analyzes → new guidance for remaining gaps
```

This iterates until coverage targets are met or all remaining gaps are justified as waived.

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

Convergence estimation: if N random seeds cover M% of bins, estimate additional seeds needed
using the formula: seeds_needed ≈ N × ln(100/(100-target)) / ln(100/(100-M)).
This is approximate — directed tests are always more efficient for specific uncovered bins.
