# Phase 5 Review: Requirement Traceability

- **Date**: {{DATE}}
- **Reviewer**: func-verifier
- **Upper Spec**: requirements.json
- **Verdict**: {{VERDICT}}

## Requirement Traceability Matrix

| REQ ID | Description | Test Name | Test Result | Status |
|--------|-------------|-----------|-------------|--------|
| REQ-001 | {{DESC}} | test_{{MODULE}}_basic | PASS | COVERED |
| REQ-002 | {{DESC}} | test_{{MODULE}}_edge | PASS | COVERED |
| REQ-003 | {{DESC}} | — | — | NO COVERAGE |

## Coverage Summary

- **Requirements total**: {{TOTAL_REQ}}
- **With test coverage**: {{COVERED_REQ}} ({{COVERAGE_PCT}}%)
- **Passing tests**: {{PASSING_REQ}}
- **Failing tests**: {{FAILING_REQ}}
- **No coverage**: {{UNCOVERED_REQ}}

## Findings

### [BLOCKER] Finding-1: {{REQ_ID}} has no test coverage
- Requirement: {{DESCRIPTION}}
- Action needed: testbench-dev must generate tests targeting this requirement

### [WARN] Finding-2: {{REQ_ID}} test fails
- Requirement: {{DESCRIPTION}}
- Test: {{TEST_NAME}}
- Failure: {{FAILURE_DESCRIPTION}}

## Verdict

{{VERDICT}}: {{REASON}}

<!-- PASS — all [N] requirements verified with passing tests -->
<!-- FAIL — [M] requirements without test coverage, [K] requirements with failing tests -->
