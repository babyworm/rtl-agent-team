---
name: rtl-p5s-coverage-analyze
description: "This skill should be used when analyzing functional coverage reports to identify gaps and prioritize additional test generation."
---

<Purpose>
Analyze simulation coverage data to identify uncovered lines, branches, and FSM states.
Generate a prioritized list of coverage gaps and new test cases to close them.
Outputs: sim/coverage/coverage_gaps.md + sim/coverage/test_coverage_fill.py.
</Purpose>

<Use_When>
- Coverage report exists from a rtl-p5s-func-verify run
- Coverage is below target (90% line, 80% toggle, 70% FSM)
- Preparing for verification closure milestone
</Use_When>

<Do_Not_Use_When>
- No coverage data exists yet (run rtl-p5s-func-verify first)
- Functional failures exist (fix failures before analyzing coverage)
- Only a single test is needed (write it directly with testbench-dev)
</Do_Not_Use_When>

<Why_This_Exists>
Raw coverage reports are verbose and hard to prioritize. coverage-analyst identifies
which uncovered areas are high-value vs unreachable. testbench-dev then writes
targeted tests for the high-value gaps, making coverage closure systematic.
</Why_This_Exists>

<Execution_Policy>
- coverage-analyst reads coverage data and identifies gaps by priority
- testbench-dev writes new cocotb tests targeting the identified gaps
- Rerun regression to verify coverage improvement
- Report final coverage delta
</Execution_Policy>

<Steps>
1. coverage-analyst reads sim/coverage/coverage.xml (or .dat) via Bash CLI tools:
   - Lists uncovered lines with file:line
   - Lists uncovered branches with condition
   - Lists uncovered FSM states and transitions
   - Notes signal names using project convention (i_/o_ prefixes, {domain}_clk/{domain}_rst_n)
2. coverage-analyst prioritizes gaps: HIGH (functional path), MED (error path), LOW (unreachable)
3. coverage-analyst writes sim/coverage/coverage_gaps.md with prioritized gap list
4. **Coverpoint Iterative Refinement (minimum 3 rounds)**:
   Coverage coverpoint extraction and test generation must iterate at least 3 times:
   - **Round 1 (Initial Analysis)**: Identify all uncovered lines, branches, FSM states/transitions. Prioritize gaps (HIGH/MED/LOW). Generate first batch of directed tests for HIGH gaps.
   - **Round 2 (Deepen)**: Re-analyze coverage after Round 1 tests. Identify newly reachable but still uncovered paths. Add cross-coverage points (e.g., cmd × size, state × error). Target MED gaps. Check for unreachable code (waiver candidates).
   - **Round 3 (Close)**: Final coverage push. Add corner-case stimulus for remaining gaps. Verify coverage targets met (line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%). Document waived bins with justification.
   - **Additional rounds**: Continue until coverage targets are met or all remaining gaps are justified as waived.
   Each round produces a progress note at `.rtl-agent-team/scratch/phase-5/coverage-iteration-r{N}.md`.
5. testbench-dev writes sim/coverage/test_coverage_fill.py targeting HIGH gaps
   - Test signals reference RTL ports with correct i_/o_ prefixes
   - Clock driven as {domain}_clk, reset as {domain}_rst_n
6. Report: current coverage %, gap count by priority, new tests added, iteration count
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:coverage-analyst",
     prompt="Analyze sim/coverage/coverage.xml. List uncovered lines, branches, and FSM states. Prioritize gaps as HIGH/MED/LOW. Write sim/coverage/coverage_gaps.md.")

Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Read sim/coverage/coverage_gaps.md. Write sim/coverage/test_coverage_fill.py targeting all HIGH priority gaps. Each test must exercise the specific uncovered condition.")
```
</Tool_Usage>

<Examples>
<Good>
coverage-analyst finds 12% line gap, 8 uncovered FSM transitions (3 HIGH, 4 MED, 1 LOW);
testbench-dev writes 3 new tests for HIGH gaps; rerun shows coverage improves to 94%.
</Good>
<Bad>
Adding random test vectors hoping to hit uncovered paths — inefficient and fails to
reach unreachable code that should be removed instead.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- LOW priority gaps flagged as unreachable → report to user, recommend dead code removal
- Coverage tool format unrecognized → halt, ask user for coverage format (Icarus, VCS, etc.)
- Coverage below 70% after gap fill → escalate to rtl-architect for structural review
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] sim/coverage/coverage_gaps.md written with all gaps prioritized
- [ ] New tests written for all HIGH priority gaps
- [ ] Coverage improvement measured and reported
- [ ] Unreachable code gaps flagged separately
</Final_Checklist>

<Advanced>
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
</Advanced>
