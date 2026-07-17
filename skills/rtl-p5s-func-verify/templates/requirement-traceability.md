# Phase 5 Review: Requirement Traceability

- **Date**: {{DATE}}
- **Reviewer**: func-verifier
- **Upper Spec**: `docs/phase-1-research/iron-requirements.json` (canonical) or legacy `docs/phase-1-research/requirements.json` (fallback)
- **Verdict**: {{VERDICT}}

## Requirement Traceability Matrix

When structured acceptance_criteria (with ac_id) exist:

| REQ ID | AC ID | Description | Test Case | Status |
|--------|-------|-------------|-----------|--------|
| REQ-U-001 | AC-1 | {{DESC}} | test_{{MODULE}}_basic | VERIFIED |
| REQ-U-001 | AC-2 | {{DESC}} | — | UNTESTED |

When no structured AC (REQ-level fallback):

| REQ ID | Description | Test Case | Status |
|--------|-------------|-----------|--------|
| REQ-001 | {{DESC}} | test_{{MODULE}}_basic | VERIFIED |
| REQ-003 | {{DESC}} | — | UNTESTED |

Status values: VERIFIED, FORMAL, PARTIAL, UNTESTED, NOT_VERIFIABLE

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

<!-- PASS — all Critical/High requirements/ac_ids VERIFIED or FORMAL -->
<!-- PARTIAL_PASS — some Critical/High ac_ids PARTIAL (WARNING at Stage 1, escalated to FAIL at Stage 3) -->
<!-- FAIL — M requirements/ac_ids UNTESTED, K with failing tests -->
