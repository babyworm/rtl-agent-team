# Review Documents

## Principle

**Data in `docs/`, verdict in `reviews/`.**
Example: formal verification data → `docs/phase-5-verify/`, spec compliance judgment → `reviews/phase-5-verify/final-compliance.md`.

## Artifact Structure

```
reviews/
├── phase-1-research/
│   └── research-review.md
├── phase-2-architecture/
│   ├── architecture-review-r{1,2,3}.md    # 3-round iterative
│   ├── architecture-review.md             # Consolidated verdict
│   ├── feature-coverage.md                # 100% REQ mapping to arch blocks
│   ├── ref-model-feature-coverage.md      # 100% REQ-F-* to C model code paths
│   └── architecture-diagram.md            # D2 block diagram
├── phase-3-uarch/
│   ├── uarch-review-r{1,2,3}.md           # 3-round iterative
│   ├── uarch-review.md                    # Consolidated verdict
│   ├── feature-preservation.md            # 100% preserved
│   ├── bfm-feature-coverage.md            # 100% REQ-F-* to BFM modules
│   └── pipeline-diagram.md               # Mermaid pipeline/flow
├── phase-4-rtl/
│   ├── functional-completeness.md         # REQ → uarch → RTL traceability
│   ├── design-review.md                   # RTL vs μArch verdict
│   └── lint-report.md
├── phase-5-verify/
│   ├── formal-review.md
│   ├── cdc-report.md
│   ├── requirement-traceability.md
│   ├── coverage-report.md
│   ├── final-compliance.md                # Final verdict vs original Spec
│   └── e2e-traceability.md               # REQ→Arch→μArch→RTL→Test→Result
├── phase-6-review/
│   ├── code-review.md, design-review.md
│   ├── design-note.md, improvements.md
└── phase-7-exploration/
    └── exploration-review.md
```

## Review Markdown Format

All verdict reports follow this structure:

```markdown
# [Phase] Review: [Title]
- Date: YYYY-MM-DD
- Reviewer: [Agent Name]
- Upper Spec: [Referenced Upper Document]
- Verdict: PASS | FAIL

## Feature Coverage Checklist
| REQ ID | Requirement | Status | Implementation Location |
|--------|-------------|--------|------------------------|
| REQ-001 | ... | COVERED | module.sv:42 |
| REQ-002 | ... | MISSING | — |

## Findings
### [severity] Finding-1: ...

## Verdict
PASS | FAIL: [Reason]
```

## Iterative Review Structure

Phases 1, 2, and 3 use 3-round iterative reviews:
- Round 1 (`*-review-r1.md`): Initial review
- Round 2 (`*-review-r2.md`): Address R1 findings
- Round 3 (`*-review-r3.md`): Final pass (mandatory)
- Consolidated (`*-review.md`): Final verdict

<!-- rat-version: 0.7.7 -->
