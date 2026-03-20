# Coverage Gap Analysis Report: {{MODULE_NAME}}

> Generated: {{DATE}}
> Source: {{COVERAGE_DB_PATH}}

## Coverage Summary

| Metric | Target | Achieved | Status |
|--------|--------|----------|--------|
| Line coverage | 90% | {{LINE_PCT}}% | {{PASS/FAIL}} |
| Toggle coverage | 80% | {{TOGGLE_PCT}}% | {{PASS/FAIL}} |
| FSM state coverage | 70% | {{FSM_PCT}}% | {{PASS/FAIL}} |
| Functional coverage | 95% | {{FUNC_PCT}}% | {{PASS/FAIL}} |

## High-Priority Gaps (uncovered × risk)

| Priority | Bin / Line | Type | Requirement | Risk | Suggested Test |
|----------|-----------|------|-------------|------|----------------|
| P1 | {{BIN_NAME}} | functional | {{REQ_ID}} | {{RISK}} | {{TEST_SUGGESTION}} |
| P2 | {{LINE_RANGE}} | line | {{REQ_ID}} | {{RISK}} | {{TEST_SUGGESTION}} |

### Risk Classification

- **Critical**: Uncovered bin maps to Critical/High acceptance criterion (ac_id)
- **High**: Uncovered FSM state or transition in the main datapath
- **Medium**: Uncovered toggle on control signals
- **Low**: Uncovered line in error/exception handling path

## Functional Coverage Bins

### {{COVERGROUP_NAME}}

| Bin | Hits | Target | Status | Mapped Requirement |
|-----|------|--------|--------|-------------------|
| {{BIN}} | {{HITS}} | {{TARGET}} | {{COVERED/UNCOVERED}} | {{REQ_ID}} |

## FSM Coverage

### {{FSM_NAME}}

| State | Visited | Transitions Covered | Missing Transitions |
|-------|---------|--------------------|--------------------|
| {{STATE}} | {{YES/NO}} | {{COVERED_LIST}} | {{MISSING_LIST}} |

## Directed Test Recommendations

Based on gap analysis, the following directed tests would close the highest-priority gaps:

1. **{{TEST_NAME}}**: Target {{BIN_NAME}} by applying {{STIMULUS_DESCRIPTION}}
2. **{{TEST_NAME}}**: Cover {{STATE}} → {{STATE}} transition via {{SCENARIO}}

## Convergence Trend

| Round | Line | Toggle | FSM | Functional | Tests Added |
|-------|------|--------|-----|------------|-------------|
| R1 (initial) | {{PCT}} | {{PCT}} | {{PCT}} | {{PCT}} | — |
| R2 (directed) | {{PCT}} | {{PCT}} | {{PCT}} | {{PCT}} | {{N}} |
| R3 (closure) | {{PCT}} | {{PCT}} | {{PCT}} | {{PCT}} | {{N}} |
