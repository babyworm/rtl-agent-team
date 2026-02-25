# Phase {{PHASE_NUM}} Review: {{REVIEW_TITLE}}

- **Date**: {{DATE}}
- **Reviewer**: {{REVIEWER_AGENT}}
- **Upper Spec**: {{UPPER_SPEC_FILES}}
- **Verdict**: {{VERDICT}}

## Feature Coverage Checklist

| REQ ID | Description | {{TARGET_COLUMN}} | Status |
|--------|-------------|-------------------|--------|
| REQ-001 | {{DESC}} | {{TARGET}} | COVERED |
| REQ-002 | {{DESC}} | {{TARGET}} | COVERED |
| REQ-003 | {{DESC}} | {{TARGET}} | MISSING |

## Findings

### [BLOCKER] Finding-1: {{TITLE}}
- **Location**: {{FILE}}:{{LINE}}
- **Upper Spec Reference**: {{REQ_ID}} / {{SPEC_SECTION}}
- **Description**: {{DETAILED_DESCRIPTION}}
- **Impact**: {{IMPACT}}

### [WARN] Finding-2: {{TITLE}}
- **Location**: {{FILE}}:{{LINE}}
- **Description**: {{DETAILED_DESCRIPTION}}

### [SUGGESTION] Finding-3: {{TITLE}}
- **Description**: {{DETAILED_DESCRIPTION}}

## Hierarchical Compliance

- **Upper spec violations**: {{COUNT}} (any > 0 is automatic FAIL)
- **Feature coverage**: {{COVERED}}/{{TOTAL}} ({{PCT}}%)
- **Convention violations**: {{CONV_COUNT}}

## Verdict

{{VERDICT}}: {{REASON}}

<!--
PASS — all [N] requirements covered, no upper-spec violations
FAIL — [M] of [N] requirements have issues:
  MISSING: REQ-003, REQ-007
  PARTIAL: REQ-005
  UPPER-SPEC VIOLATION: REQ-009 (changed from architecture decision)
-->
