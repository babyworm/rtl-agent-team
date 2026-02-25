---
name: coverage-analyze
description: "This skill should be used when analyzing functional coverage reports to identify gaps and prioritize additional test generation."
---

<Purpose>
Analyze simulation coverage data to identify uncovered lines, branches, and FSM states.
Generate a prioritized list of coverage gaps and new test cases to close them.
Outputs: coverage/coverage_gaps.md + tb/cocotb/test_coverage_fill.py.
</Purpose>

<Use_When>
- Coverage report exists from a func-verify or regression-run run
- Coverage is below target (90% line, 80% toggle, 70% FSM)
- Preparing for verification closure milestone
</Use_When>

<Do_Not_Use_When>
- No coverage data exists yet (run func-verify first)
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
1. coverage-analyst reads coverage/coverage.xml (or .dat) via Bash CLI tools:
   - Lists uncovered lines with file:line
   - Lists uncovered branches with condition
   - Lists uncovered FSM states and transitions
   - Notes signal names using project convention (i_/o_ prefixes, {domain}_clk/{domain}_rst_n)
2. coverage-analyst prioritizes gaps: HIGH (functional path), MED (error path), LOW (unreachable)
3. coverage-analyst writes coverage/coverage_gaps.md with prioritized gap list
4. testbench-dev writes tb/cocotb/test_coverage_fill.py targeting HIGH gaps
   - Test signals reference RTL ports with correct i_/o_ prefixes
   - Clock driven as {domain}_clk, reset as {domain}_rst_n
5. Report: current coverage %, gap count by priority, new tests added
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:coverage-analyst",
     prompt="Analyze coverage/coverage.xml. List uncovered lines, branches, and FSM states. Prioritize gaps as HIGH/MED/LOW. Write coverage/coverage_gaps.md.")

Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Read coverage/coverage_gaps.md. Write tb/cocotb/test_coverage_fill.py targeting all HIGH priority gaps. Each test must exercise the specific uncovered condition.")
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
- [ ] coverage/coverage_gaps.md written with all gaps prioritized
- [ ] New tests written for all HIGH priority gaps
- [ ] Coverage improvement measured and reported
- [ ] Unreachable code gaps flagged separately
</Final_Checklist>
