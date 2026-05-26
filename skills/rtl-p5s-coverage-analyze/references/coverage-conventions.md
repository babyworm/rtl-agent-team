# Coverage Analysis Conventions

A quick reference for `rtl-p5s-coverage-analyze`. Stays under 150 lines so it can be consulted in one read.

## 1. Naming & output structure

| Element | Convention | Example |
|---------|-----------|---------|
| Coverage input | `sim/coverage/coverage.xml` or `sim/coverage/coverage.dat` | |
| Gap report | `reviews/phase-5-verify/{module}-coverage-report.md` | |
| Directed test script | `sim/coverage/test_coverage_fill.py` | |
| Report scaffold | `templates/coverage-gap-report.md` | |
| Coverage targets | 90% line, 80% toggle, 70% FSM (project defaults) | |

Coverage targets are project defaults from `.claude/rules/rtl-coding-conventions.md` and the
Phase 5 verification gate. If the user specifies different targets, use those instead and
document the override in the report header.

## 2. Output schema

### reviews/phase-5-verify/{module}-coverage-report.md structure

```markdown
# Coverage Analysis Report — {module}

## Summary
Overall verdict: PASS | FAIL
Line coverage:   {N}% (target: 90%)
Toggle coverage: {N}% (target: 80%)
FSM coverage:    {N}% (target: 70%)

## Coverage Gaps — Prioritized
### High Value (reachable, architectural significance)
| Location | Type | Uncovered Items | Priority | Reason |
|----------|------|-----------------|----------|--------|

### Low Value / Unreachable
| Location | Type | Reason Unreachable |
|----------|------|--------------------|

## Directed Tests Generated
{List of test cases added to test_coverage_fill.py, one line each.}

## Exclusions Applied
{Any coverage exclusion bins approved via rtl-coverage-exclusion-gate.sh.}
```

### sim/coverage/test_coverage_fill.py

Directed test generator output. One test function per coverage gap targeted.
Use cocotb or the project's existing test framework (match the style of existing
tests in `sim/{module}/test_*.py`).

## 3. Length guidance

- Coverage report: 40–80 lines. The gap table should include only the top 10 high-value
  gaps if there are many — note the total count.
- Directed test script: one test function per gap, 10–30 lines each. Do not write
  exhaustive tests here — targeted stimulus only.
- Per-gap description in the table: 1 line for Reason column.

## 4. Anti-patterns

- Do not declare coverage PASS if any target is unmet — report actual numbers and verdict FAIL.
- Do not fabricate coverage numbers — read from the actual coverage report file.
- Do not skip the unreachable analysis — marking unreachable items as excluded requires
  the `rtl-coverage-exclusion-gate.sh` approval flow; do not apply exclusions silently.
- Do not generate broad randomized tests to hit coverage targets — generate directed tests
  that target specific uncovered branches or FSM transitions.
- Do not run coverage analysis while functional failures remain — coverage from a failing
  simulation is not reliable.
- Follow `<markdown_diagram_rule>` and `.claude/rules/rtl-coding-conventions.md` for any
  diagrams or code snippets included in the report.
