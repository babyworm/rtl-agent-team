# Gate Failure Handling Reference

> This document is the detailed reference for the `rtl-autopilot` skill.
> For core rules, see `<Steps>` in `skills/rtl-autopilot/SKILL.md`.

## 1. Phase Gate Overview

A Gate Review is performed upon completion of each Phase in the 5-Phase pipeline:

```
Phase 1 → [Gate 1] → Phase 2 → [Gate 2] → Phase 3 → [Gate 3] → Phase 4 → [Gate 4] → Phase 5 → [Gate 5]
Research    Review    Arch/Ref    Review    μArch/BFM    Review    RTL         Review    Verify      Final
```

## 2. Gate Review Checklist

### Gate 1: Research → Architecture

| Item | Verification | On Failure |
|------|--------------|------------|
| Requirements completeness | All functional requirements documented | Return to Phase 1 |
| Feasibility | Technical constraint analysis complete | Request user confirmation |
| Domain knowledge | Required expertise acquired | Invoke domain-consult |

### Gate 2: Architecture → μArch

| Item | Verification | On Failure |
|------|--------------|------------|
| Feature Coverage | All REQs mapped to Arch blocks | Return to Phase 2 |
| Interface definition | io_definition.json completeness | Add missing ports |
| Reference Model | ref_model build + basic tests pass | Re-run ref-model-dev |
| Block diagram | Mermaid diagram exists | Supplement via arch-designer |

### Gate 3: μArch → RTL

| Item | Verification | On Failure |
|------|--------------|------------|
| Feature Preservation | Arch features preserved in μArch | Return to Phase 3 |
| Timing analysis | Critical path estimation | Adjust μArch pipeline |
| BFM smoke test | 1 AT transaction succeeds | Fix via bfm-dev |

### Gate 4: RTL → Verify

| Item | Verification | On Failure |
|------|--------------|------------|
| Functional Completeness | All REQs implemented in RTL | Return to Phase 4 |
| Lint PASS | Verilator + Verible 0 warnings | Fix via rtl-coder |
| Synthesis PASS | Yosys latch-free | Fix via rtl-coder |
| Convention compliance | i_/o_, sys_clk, ALL_CAPS, etc. | Fix via rtl-coder |

### Gate 5: Final

| Item | Verification | On Failure |
|------|--------------|------------|
| Regression PASS | All seeds pass | Fix bugs and re-run |
| Coverage ≥ target | Line ≥ 95%, Func ≥ 90% | Write additional tests |
| Requirement Traceability | Tests exist for all REQs | Add missing tests |

## 3. Gate Failure Retry Flow

```
Gate Review
    │
    ├── PASS → Proceed to next Phase
    │
    └── FAIL
         │
         ├── Severity: MINOR (1-2 items below threshold)
         │    └── Fix affected items only → Re-verify (max 2 times)
         │
         ├── Severity: MAJOR (3+ items or critical item)
         │    └── Return to previous Phase → Full rework
         │
         └── Severity: BLOCKER (upper spec violation)
              └── Report to user → Spec change approval required
```

### Retry Rules

| Rule | Description |
|------|-------------|
| Max 2 retries | On MINOR failure, attempt fixes twice in the same Phase |
| Over 2 failures | Return to previous Phase (possible structural issue) |
| BLOCKER halts immediately | Cannot proceed without user approval |

## 4. Upper Spec Violation Handling

> **Core principle: Lower stages must never violate the spec of upper stages.**

### 4.1 Violation Detection

| Violation Type | Detection Method | Example |
|----------------|------------------|---------|
| Feature omission | Feature Coverage Checklist | REQ-003 missing from Arch |
| Interface change | io_definition comparison | Port added/removed |
| Performance shortfall | Timing analysis | Target frequency not met |
| Protocol change | Arch review | Arbitrary change from AXI → APB |

### 4.2 Handling Violations

```
Violation detected
    │
    ├── Feature omission
    │    ├── Can implement → Add implementation in current Phase
    │    └── Cannot implement → Return to upper Phase + user approval
    │
    ├── Interface change
    │    ├── Compatible (port addition) → Update Arch docs and proceed
    │    └── Incompatible (port removal/change) → Return to Arch Phase
    │
    └── Performance shortfall
         ├── Solvable via μArch optimization → Modify μArch
         └── Fundamental structural change needed → Return to Arch Phase
```

### 4.3 User Approval Request Format

```markdown
## ⚠️ Upper Spec Violation Detected

**Phase**: Phase 3 (μArch) → Phase 2 (Architecture) violation
**Type**: Feature Omission
**Detail**: REQ-003 (burst transfer support) cannot be implemented in μArch
**Reason**: Supporting burst in single-cycle processing structure requires full pipeline redesign
**Options**:
1. Return to Architecture and redesign for burst support
2. Defer REQ-003 to v2 (user approval required)
3. Performance compromise: limit burst length (max 4 beats)

**Recommendation**: Option 1 (full burst support)
```

## 5. Phase Gate Report Locations

```
reviews/
├── phase-1-research/research-review.md
├── phase-2-architecture/
│   ├── feature-coverage.md          ← REQ → Arch mapping
│   └── architecture-review.md
├── phase-3-uarch/
│   ├── feature-preservation.md      ← Arch → μArch mapping
│   └── uarch-review.md
├── phase-4-rtl/
│   ├── functional-completeness.md   ← REQ → RTL mapping
│   ├── design-review.md
│   └── lint-report.md
└── phase-5-verify/
    ├── requirement-traceability.md  ← REQ → Test mapping
    └── final-compliance.md
```

## 6. Automatic State Tracking

Gate pass/fail results are recorded in `.rtl-agent-team/state/rtl-autopilot-state.json`:

```json
{
  "current_phase": 3,
  "gates": {
    "gate_1": { "status": "PASS", "date": "2025-01-15" },
    "gate_2": { "status": "PASS", "date": "2025-01-16", "retries": 1 },
    "gate_3": { "status": "PENDING" }
  },
  "violations": [],
  "blocked": false
}
```
