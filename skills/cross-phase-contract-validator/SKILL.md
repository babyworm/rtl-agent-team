---
name: cross-phase-contract-validator
description: "Validate spec contracts across phase boundaries (P3 uarch to P4 RTL to P5 verify): port widths, memory class, REQ traceability. Use at P4/P5 entry."
user-invocable: true
argument-hint: "[phase-boundary: p3-p4 | p4-p5]"
allowed-tools: Bash, Read, Write, Grep, Glob
---

<Purpose>
Validate spec consistency across phase boundaries. Catches mismatches between upstream
specifications and downstream implementations that individual phase gates cannot detect.
</Purpose>

<Use_When>
- P4 entry (before Wave 1): validate P3 uarch → P4 RTL contract
- P5 entry (before Stage 1): validate P4 RTL → P5 verification contract
- After P4 bugfix feedback loops: re-validate contracts after RTL changes
- Manual invocation: user suspects cross-phase inconsistency
</Use_When>

<Do_Not_Use_When>
- Within a single phase (use phase-specific review agents instead)
- Phase 7 exploration (exempt from pipeline gates)
</Do_Not_Use_When>

## Phase Boundary: P3→P4 Checks

### 1. Port Width Consistency
Compare across three sources — all must agree:
- `docs/phase-2-architecture/io_definition.json` (if exists): port widths
- `docs/phase-3-uarch/*.md`: interface width specifications
- `rtl/*/*.sv`: actual module port declarations

For each port: `io_definition[width] == uarch_spec[width] == RTL_port_width`.
Mismatch → CRITICAL.

### 2. Memory Classification Match
For each storage element in P3 uarch docs:
- If P3 says "SRAM wrapper" → P4 RTL MUST contain `sram_sp`/`sram_tp`/`sram_dp` instance
- If P3 says "register file" → P4 RTL should use `logic [...] name [...]` array
- Anti-pattern: P3 says "SRAM 512×104" but P4 has `logic [103:0] mem [511:0]` with
  combinational read → CRITICAL (register array where SRAM required)
- Check: `DEPTH * WIDTH > 4096` and no SRAM wrapper instantiated → CRITICAL

### 3. Pipeline Depth Match
For each module with pipeline specification in P3:
- P3 spec states N pipeline stages
- P4 RTL should have N `always_ff` sequential stages (±1 tolerance)
- Check: count `stage_*` or sequential register chains in RTL
- Mismatch beyond ±1 → MAJOR

### 4. Bus Width Parameterization
For each FIFO/bus width defined in P3 with a derivation formula:
- P4 RTL `localparam` MUST use the same formula (derived from parameters)
- Anti-pattern: P3 says `WIDTH = PIXELS * COMPONENTS * (BPC+1) + META` but P4 has
  `localparam L_FIFO_W = 672` → MAJOR
- Check: grep for `localparam.*WIDTH.*=.*[0-9]+;` where a corresponding parameter exists

### 5. REQ→RTL Traceability
For each REQ-U-* in `docs/phase-3-uarch/iron-requirements.json`:
- At least one RTL module must implement it
- Check: REQ-U-* ID appears in RTL file header comments (`// REQ: REQ-U-NNN`)
  or in `docs/phase-4-rtl/functional-completeness.md`
- Missing REQ → CRITICAL

## Phase Boundary: P4→P5 Checks

### 6. Unit Test Existence
For each RTL module in `rtl/*/`:
- `sim/{module}/tb_{module}.sv` or equivalent must exist
- `sim/{module}/{module}_unit_results.json` must exist with `ref_mismatches=0`
- Missing → CRITICAL (P5 requires per-module unit tests from P4)

### 7. Stream B Artifact Completeness
Verify Stream B artifacts from P4 are present for P5 consumption:
- `docs/phase-4-rtl/stream-b-sva-skeletons.md` → contains `property`/`assert` per module
- `docs/phase-4-rtl/stream-b-cdc-preliminary.md` → references clock domain names
- `docs/phase-4-rtl/stream-b-tb-skeletons.md` → references REQ tags per module
- `docs/phase-4-rtl/stream-b-synth-estimate.md` → no inferred latches
- Missing or empty → MAJOR

### 8. Coverage Infrastructure Readiness
- `sim/uvm/coverage/hier.cfg` exists (if UVM flow) → TB infrastructure excluded from coverage
- Coverage collector maps to REQ-U-* requirements
- Missing → WARNING (not blocking, but coverage results will be skewed)

## Execution

Read all upstream artifacts, perform checks, generate report:

```
Glob("docs/phase-3-uarch/*.md")
Glob("docs/phase-3-uarch/iron-requirements.json")
Glob("docs/phase-2-architecture/io_definition.json")
Glob("rtl/*/*.sv")
Glob("sim/*/tb_*.sv")
Glob("sim/*/*_unit_results.json")
```

For each check: collect evidence (file:line citations), classify (CRITICAL/MAJOR/WARNING/INFO).

## Output

Write `reviews/cross-phase-contract-validation.md`:
```markdown
# Cross-Phase Contract Validation
- Date: YYYY-MM-DD
- Boundary: P3→P4 | P4→P5
- Verdict: PASS | FAIL

## Check Results
| # | Check | Status | Evidence |
|---|-------|--------|----------|
| 1 | Port width consistency | PASS/FAIL | file:line details |
| 2 | Memory classification | PASS/FAIL | ... |
| ... | ... | ... | ... |

## Critical Findings
[details with file:line citations]

## Recommendations
[actionable fix suggestions]
```

## Gate Behavior

- **CRITICAL findings**: FAIL — blocks phase entry
- **MAJOR findings**: FAIL — blocks phase entry
- **WARNING**: PASS with advisory — proceed but flag for attention
- **INFO**: PASS — informational only
