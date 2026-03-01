# Regression Report

- **Date**: {{DATE}}
- **Simulator**: {{SIMULATOR}}
- **Verdict**: {{VERDICT}}

## Seed Results

| Seed | Tests Run | Passed | Failed | Status |
|------|-----------|--------|--------|--------|
| 1 | {{N}} | {{N}} | {{N}} | PASS |
| 42 | {{N}} | {{N}} | {{N}} | PASS |
| 1337 | {{N}} | {{N}} | {{N}} | FAIL |
| 65536 | {{N}} | {{N}} | {{N}} | PASS |
| 123 | {{N}} | {{N}} | {{N}} | PASS |

## Summary

- **Seeds executed**: {{TOTAL_SEEDS}}
- **Pass rate**: {{PASS_RATE}}%
- **Failed seeds**: {{FAILED_SEED_LIST}}

## Coverage

| Metric | Target | Achieved | Status |
|--------|--------|----------|--------|
| Line | >=90% | {{LINE_COV}}% | {{STATUS}} |
| Toggle | >=80% | {{TOGGLE_COV}}% | {{STATUS}} |
| Branch | — | {{BRANCH_COV}}% | informational |
| FSM State | >=70% | {{FSM_COV}}% | {{STATUS}} |

## Failures Detail

### Seed {{SEED}}: {{TEST_NAME}}

- **Error**: {{ERROR_MESSAGE}}
- **Waveform**: sim/regression/seed_{{SEED}}_waveform.vcd
- **Log**: sim/regression/seed_{{SEED}}.log

## Verdict

{{VERDICT}}: {{REASON}}
