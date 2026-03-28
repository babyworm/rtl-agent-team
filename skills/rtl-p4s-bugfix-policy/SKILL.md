---
name: rtl-p4s-bugfix-policy
description: "Policy rules, mandatory sequence, parallel UNIT_FIX decision tree, escalation rules, and checklists for the RTL bug fix workflow. Pure reference — no orchestration."
user-invocable: false
---

# RTL Bug Fix Policy

## Mandatory 4-Step Sequence (per module)

1. **Analyze** → identify root cause and affected modules
2. **Fix + Lint** → modify RTL, run `verilator --lint-only -Wall` (max 3 lint rounds)
3. **TB** → create or update testbench (at least 1 test per modified module)
4. **Functional Verification** → run simulation, ALL tests must PASS

Each step can only proceed after the previous step is complete.
Lint is a necessary condition, NOT sufficient — simulation is required.

## Parallel UNIT_FIX Decision Tree

| Failure Pattern | Handling | Parallelism |
|----------------|----------|-------------|
| Different modules, UNIT_FIX | Parallel rtl-p4s-bugfix, one per module | `run_in_background: true` |
| Same module, multiple failures | Sequential within single task | No |
| INTEGRATION_FIX (cross-module) | Always sequential | No |
| Mixed UNIT_FIX + INTEGRATION_FIX | INTEGRATION_FIX first, then UNIT_FIX in parallel | Partial |

Verification-done marker created ONLY after ALL parallel fixes pass functional verification.

## Phase 5→4 Feedback Mode

| Fix Type | After Fix | Re-verify |
|----------|-----------|-----------|
| UNIT_FIX (SVA fail) | lint → unit TB → unit sim | Only affected Phase 5 sub-phase |
| UNIT_FIX (sim fail) | lint → unit TB → unit sim | Only affected Phase 5 sub-phase |
| INTEGRATION_FIX | lint → unit TB + integration TB → sim | 5b + 5c |

In feedback mode: lesson-learned recording is **mandatory** (not just recommended).

## Escalation & Stop Conditions

- Lint fails 3 times → escalate to rtl-architect for design review
- Cannot write TB (no ref model) → write minimal self-checking TB, report ref model requirement to user
- Simulation fails after 2 fix iterations → escalate to waveform-analyzer + rtl-bug-repro skill
- Simulator not installed → eda-runner provides installation instructions

## TB Signal Naming Convention

- `dut.sys_clk`, `dut.sys_rst_n` (clock/reset)
- `dut.i_*`, `dut.o_*` (input/output ports)
- TB check: `ls sim/*/test_*.py sim/*/tb_*.sv 2>/dev/null`

## Advanced Rules

**Integration bugs (multi-module)**:
- Both per-module unit TBs AND top-level integration TB needed
- Unit TBs: verify individual module I/O
- Integration TB: verify data flow between modules

**When regression suite available**:
- Recommended to re-run full regression after fix
- Use rtl-p5s-func-verify skill for multi-seed verification

**Compound mode bugs (e.g., MODE_RECON)**:
- Test individual modes first, then compound mode tests, then mode transition scenarios

## Final Checklist

- [ ] Bug root cause identified
- [ ] RTL fix complete
- [ ] Lint passed (verilator --lint-only -Wall, 0 errors)
- [ ] TB created or updated (at least 1 test per modified module)
- [ ] Bug reproduction scenario included as a test case
- [ ] **Functional simulation executed (cocotb or verilator sim)**
- [ ] **All tests PASS**
- [ ] **Verification-done marker created (.rat/state/rtl-verify-done)**
- [ ] TB signal naming convention followed
- [ ] Multi-module failures classified (UNIT_FIX vs INTEGRATION_FIX)
- [ ] Independent UNIT_FIX modules fixed in parallel (not sequentially)
- [ ] All parallel fixes passed functional verification before verify-done marker
