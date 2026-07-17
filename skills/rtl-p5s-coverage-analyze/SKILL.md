---
name: rtl-p5s-coverage-analyze
description: "P5 coverage closure: prioritizes coverage gaps and generates directed tests. Triggers 'coverage gaps', 'coverage below target', 'uncovered branches'."
user-invocable: true
argument-hint: "[module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Analyze simulation coverage data to identify uncovered lines, branches, and FSM states. Prioritize gaps by reachability and architectural significance, generate directed tests to close high-value gaps, and produce a convergence report. Outputs: `reviews/phase-5-verify/{module}-coverage-report.md` (gap list + PASS/FAIL verdict) and `sim/coverage/test_coverage_fill.py` (directed tests targeting identified gaps).
</Purpose>

<Use_When>
- A coverage report exists from a `rtl-p5s-func-verify` run.
- Coverage is below target (90% line, 80% toggle, 70% FSM).
- Preparing for a verification closure milestone.
</Use_When>

<Do_Not_Use_When>
- No coverage data exists yet — run `rtl-p5s-func-verify` first.
- Functional failures remain — fix failures before analyzing coverage.
- Only a single targeted test is needed — write it directly with `testbench-dev`.
</Do_Not_Use_When>

<Why_This_Exists>
Raw coverage reports are verbose and hard to prioritize. `coverage-analyst` identifies which uncovered areas are high-value vs unreachable, and `testbench-dev` writes targeted tests for the high-value gaps. This makes coverage closure systematic rather than relying on ad-hoc test addition. The iterative 3-round loop ensures convergence is tracked across test additions.
</Why_This_Exists>

## Prerequisites

- `sim/coverage/coverage.xml`, `.dat`, or `merged.info` must exist from a prior `rtl-p5s-func-verify` run.

If prerequisite is missing: WARNING — recommend running `/rtl-agent-team:rtl-p5s-func-verify` first. Proceed with available artifacts; orchestrator adapts scope.

<Assets>
| Path | Role |
|------|------|
| `templates/coverage-gap-report.md` | Gap report scaffold: summary section, high-value gap table, unreachable table, directed tests list, exclusions section. |
| `scripts/parse_coverage.py` | Deterministic coverage parser: reads lcov `.info` (from `merge_coverage.sh`) or raw Verilator `coverage.dat`, emits JSON with per-file/per-metric coverage %, ranked uncovered bins, and PASS/FAIL vs project targets. |
| `references/coverage-conventions.md` | Coverage targets, report schema, directed test style, exclusion approval rules, anti-patterns. |
| `examples/` | Worked examples: `merged.info` (lcov) + `coverage.dat` (Verilator native) inputs with committed expected JSON — see `examples/README.md`. |
</Assets>

<Responsibility_Boundary>
- **Scripts** handle deterministic parsing: coverage XML/DAT extraction produces line, toggle, and FSM coverage numbers per module.
- **LLM** handles interpretive analysis: gap prioritization (reachable vs unreachable), directed test design, and exclusion justification for the `rtl-coverage-exclusion-gate.sh` approval flow.
- Contract surface: report structure and coverage targets documented in `references/coverage-conventions.md`.
</Responsibility_Boundary>

<Execution>
1. Read `skills/rtl-p5s-coverage-analyze/references/coverage-conventions.md` for coverage targets, report structure, and exclusion approval rules.
2. Spawn `p5s-coverage-orchestrator` (see Tool_Usage) to run 3-round iterative analysis: parse the coverage report (deterministic extraction via `scripts/parse_coverage.py` — supports lcov `.info` and Verilator `coverage.dat`; `v_user` points count as the fsm metric), identify and prioritize gaps, generate directed tests, re-run simulation, and track convergence.
3. The orchestrator writes `reviews/phase-5-verify/{module}-coverage-report.md` using `templates/coverage-gap-report.md` as scaffold, populating high-value and unreachable gap tables.
4. The orchestrator writes `sim/coverage/test_coverage_fill.py` with one test function per targeted gap.
5. Any coverage exclusion bins (unreachable items) must go through the `rtl-coverage-exclusion-gate.sh` approval flow — do not apply exclusions silently.
6. Report the overall PASS/FAIL verdict and both output paths to the user.

Apply steps 1-6 to every requested module — do not stop after the first.
</Execution>

<Tool_Usage>
Coverage gap analysis orchestration:
```
Task(subagent_type="rtl-agent-team:p5s-coverage-orchestrator",
     prompt="Execute coverage gap analysis. User input: $ARGUMENTS")
```

Do not perform analysis work directly — the orchestrator manages 3-round iterative coverage analysis, directed test generation, and coverage convergence tracking.
</Tool_Usage>

<Examples>
<example index="1">
<scenario>Module has 85% line coverage and 65% FSM coverage after initial functional verification pass.</scenario>
<reference>skills/rtl-p5s-coverage-analyze/examples/</reference>
<expected_output>Gap report identifies 3 high-value uncovered FSM transitions and 2 uncovered error-handling branches; `test_coverage_fill.py` adds 5 directed tests; after re-run coverage reaches 91% line and 73% FSM — overall PASS.</expected_output>
</example>

<example index="2">
<scenario>Several uncovered branches are in dead-code paths gated by a compile-time parameter.</scenario>
<reference>skills/rtl-p5s-coverage-analyze/examples/</reference>
<expected_output>Unreachable table lists the dead-code branches with justification; exclusion request routed through `rtl-coverage-exclusion-gate.sh` before applying. Report notes exclusions pending user approval.</expected_output>
</example>

<example index="3">
<scenario>Coverage data file is absent — `sim/coverage/coverage.xml` does not exist.</scenario>
<reference>skills/rtl-p5s-coverage-analyze/examples/</reference>
<expected_output>WARNING emitted: `sim/coverage/coverage.xml` not found — recommend running `/rtl-agent-team:rtl-p5s-func-verify` first. Skill does not proceed to gap analysis.</expected_output>
</example>
</Examples>

<Escalation_And_Stop_Conditions>
- Coverage data absent → emit WARNING; do not fabricate numbers; stop.
- Functional failures remain → refuse to run; report that coverage from a failing simulation is unreliable.
- Exclusion of unreachable bins needed → route through `rtl-coverage-exclusion-gate.sh`; never apply silently.
- After 3 rounds coverage is still below target → report the residual gaps and recommend user review of the exclusion candidates.
</Escalation_And_Stop_Conditions>

## Output

- `reviews/phase-5-verify/{module}-coverage-report.md` — raw and post-exclusion coverage numbers, prioritized gap list, and PASS/FAIL verdict.
- `sim/coverage/test_coverage_fill.py` — directed tests generated to close identified high-value gaps.

<Final_Checklist>
- [ ] Coverage data read from `sim/coverage/coverage.xml` or `.dat` — no fabricated numbers.
- [ ] Gaps prioritized into high-value (reachable) and unreachable tables.
- [ ] Directed tests written in `test_coverage_fill.py` targeting high-value gaps only.
- [ ] Coverage exclusions routed through `rtl-coverage-exclusion-gate.sh` — none applied silently.
- [ ] `reviews/phase-5-verify/{module}-coverage-report.md` written with PASS/FAIL verdict.
- [ ] RTL source not modified.
</Final_Checklist>
