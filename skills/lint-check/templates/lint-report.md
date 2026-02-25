# Lint Report: {{MODULE_NAME}}

- **Date**: {{DATE}}
- **Reviewer**: lint-checker
- **Target**: {{TARGET_FILES}}
- **Verdict**: {{VERDICT}}

## Tool Results Summary

| Tool | Errors | Warnings | Info |
|------|--------|----------|------|
| Verilator | {{VERILATOR_ERRORS}} | {{VERILATOR_WARNINGS}} | {{VERILATOR_INFO}} |
| Verible | {{VERIBLE_ERRORS}} | {{VERIBLE_WARNINGS}} | {{VERIBLE_INFO}} |
| slang | {{SLANG_ERRORS}} | {{SLANG_WARNINGS}} | {{SLANG_INFO}} |
| Convention | {{CONV_ERRORS}} | - | - |

## Critical Violations (MUST fix)

<!-- Verilator: BLKANDNBLK, LATCH, CASEINCOMPLETE, MULTIDRIVEN -->

| # | Tool | File:Line | Rule | Description |
|---|------|-----------|------|-------------|
| 1 | {{TOOL}} | {{FILE}}:{{LINE}} | {{RULE}} | {{DESCRIPTION}} |

## Major Warnings

<!-- Verilator: WIDTH, UNDRIVEN, SYNCASYNCNET, UNSIGNED, CMPCONST -->

| # | Tool | File:Line | Rule | Description |
|---|------|-----------|------|-------------|

## Convention Violations

<!-- i_/o_ prefix, {domain}_clk, {domain}_rst_n, logic only, u_ instance, gen_ generate -->

| # | File:Line | Rule | Found | Expected |
|---|-----------|------|-------|----------|

## Waivers Applied

<!-- From .verilator.vlt if present -->

| Rule | File | Lines | Reason |
|------|------|-------|--------|

## Verdict

{{VERDICT}}: {{REASON}}

- Total violations: {{TOTAL}}
- Critical: {{CRITICAL_COUNT}} (must be 0 to pass)
- Major: {{MAJOR_COUNT}}
- Convention: {{CONVENTION_COUNT}}
