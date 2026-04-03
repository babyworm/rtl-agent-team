---
name: rtl-p5s-coverage-analyze
description: "This skill should be used when analyzing functional coverage reports to identify gaps and prioritize additional test generation."
user-invocable: true
argument-hint: "[module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
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

<Execution_Policy>
- Use `skills/rtl-p5s-coverage-analyze/templates/coverage-gap-report.md` as report scaffold
</Execution_Policy>

<Why_This_Exists>
Raw coverage reports are verbose and hard to prioritize. coverage-analyst identifies
which uncovered areas are high-value vs unreachable. testbench-dev then writes
targeted tests for the high-value gaps, making coverage closure systematic.
</Why_This_Exists>

## Prerequisites

Coverage data from rtl-p5s-func-verify required:
- `sim/coverage/coverage.xml` (or `.dat`) must exist

If prerequisite is missing: WARNING — recommend running `/rtl-agent-team:rtl-p5s-func-verify` first.
Proceed with available artifacts — orchestrator will adapt scope.

## Execution

Task(subagent_type="rtl-agent-team:p5s-coverage-orchestrator",
     prompt="Execute coverage gap analysis. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages 3-round iterative coverage analysis,
directed test generation, and coverage convergence tracking.

## Output

- `reviews/phase-5-verify/{module}-coverage-report.md` — raw and post-exclusion coverage numbers, prioritized gap list, and PASS/FAIL verdict
- `sim/coverage/test_coverage_fill.py` — directed tests generated to close identified gaps
