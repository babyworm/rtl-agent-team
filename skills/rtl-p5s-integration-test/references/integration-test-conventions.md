# Integration Test Conventions

A quick reference for `rtl-p5s-integration-test`. Stays under 150 lines so it can be consulted in one read.

## 1. Naming & output structure

| Element | Convention | Example |
|---------|-----------|---------|
| Integration TB | `sim/top/integration_tb.sv` (based on template) | |
| Results JSON | `sim/top/integration_results.json` | |
| Integration report | `reviews/phase-5-verify/integration-test-report.md` | |
| TB scaffold | `templates/integration-tb-template.sv` | |
| Top-level instance | `u_dut_top` | |
| Port prefix | `i_/o_/io_` per project convention | see `.claude/rules/rtl-coding-conventions.md` |
| Clock naming | `{domain}_clk` for multi-domain; `clk` for single | |
| Reset naming | `{domain}_rst_n` (active-low async) | |

This is **Tier 4** testing. Tier ordering:
```
Tier 1: Smoke        — rtl-p4-implement Wave 4
Tier 2: Unit         — rtl-p4s-unit-test
Tier 3: Module Regr. — rtl-p5s-func-verify
Tier 4: Integration  — THIS SKILL
```
Do not run Tier 4 until Tier 2 and Tier 3 are PASS or PARTIAL_PASS for all modules.

## 2. Output schema

### sim/top/integration_results.json

```json
{
  "run_timestamp": "ISO-8601",
  "tier": 4,
  "overall_verdict": "PASS|FAIL|PARTIAL_PASS",
  "tests": [
    {
      "name": "{test_name}",
      "category": "connectivity|data_flow|reset_propagation|handshake|end_to_end",
      "verdict": "PASS|FAIL",
      "failure_detail": ""
    }
  ]
}
```

Test categories and what they verify:
- `connectivity`: width/direction mismatches at module boundaries (static)
- `data_flow`: data traverses pipeline end-to-end with correct values
- `reset_propagation`: all sub-modules reach idle state after reset de-assertion
- `handshake`: valid/ready (or req/ack) protocol observed across all interfaces
- `end_to_end`: output matches reference model for a representative input

### reviews/phase-5-verify/integration-test-report.md structure

```markdown
# Integration Test Report (Tier 4)

## Summary
Overall verdict: PASS | FAIL | PARTIAL_PASS

## Test Results
| Category | Test Name | Verdict | Notes |
|----------|-----------|---------|-------|

## Failures
{For each FAIL: module boundary, signal path, first failure cycle.}

## Recommendation
{PASS: proceed to final compliance / rtl-p6-design-review.
 FAIL: identify which module boundaries failed; recommend targeted Tier 2/3 re-run.}
```

## 3. Length guidance

- Integration report: 40–80 lines. Failures section: 3–8 lines per failing test.
- Results JSON: one entry per test case. Do not aggregate multiple tests into one entry.
- Recommendation: 3–6 lines. Reference the specific module boundaries or signal paths.

## 4. Anti-patterns

- Do not run Tier 4 integration tests when individual modules still fail Tier 2 unit tests —
  integration failures in that state cannot be reliably attributed to interface issues.
- Do not use a monolithic stimulus that exercises every feature — write one test per category
  so failures are isolated.
- Do not fabricate cross-module reference comparison values — use the Phase 2 refC model
  output as the oracle for end-to-end tests.
- Do not skip the static connectivity check — width mismatches at module boundaries must be
  caught before dynamic simulation is run.
- Do not report PASS if any `end_to_end` or `data_flow` test fails, even if `connectivity`
  and `reset_propagation` pass.
- Follow `<markdown_diagram_rule>` and `.claude/rules/rtl-coding-conventions.md` for any
  waveform excerpts or signal-path diagrams included in the report.
