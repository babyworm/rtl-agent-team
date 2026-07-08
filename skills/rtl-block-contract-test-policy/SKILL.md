---
name: rtl-block-contract-test-policy
description: "Internal reference: rtl block contract test policy (agent-loaded; do not invoke)."
user-invocable: false
---

# Block-Parallel Contract Test Policy

## Contract Test Directory Structure

Each block maintains its contract tests under:

```
sim/{block}/contract/
    {block}_if_contract_tb.sv    # Interface compliance tests
    {block}_timing_check.sv      # Timing assertion checks
    {block}_stub.sv              # Mock for counterpart blocks
```

## Three Contract Test File Types

### 1. Interface Compliance Test (`{block}_if_contract_tb.sv`)

Verifies that the block's ports conform to the frozen interface definitions:

- Port names match `rtl/intf/*_if.sv` signal names
- Port widths match `rtl/pkg/codec_if_pkg.sv` type definitions
- Valid/ready handshake protocol compliance (no valid drop, data stability)
- Multi-beat transfer length matches interface specification
- All required interface signals are connected (no dangling ports)

### 2. Timing Assertion Check (`{block}_timing_check.sv`)

Verifies timing contracts embedded in interface files:

- Handshake latency within specified bounds
- Throughput meets minimum rate (pixels/cycle or coefficients/cycle)
- Backpressure duration does not exceed maximum specified in timing contract
- Pipeline depth matches declared value
- Clock domain crossings use proper synchronization (where applicable)

### 3. Counterpart Stub (`{block}_stub.sv`)

Provides a mock implementation of the block for use by other blocks' tests:

- Implements all output interfaces with configurable response patterns
- Accepts all input interfaces and logs received data
- Supports programmable backpressure injection (for stress testing)
- Minimal logic — behavioral model only, NOT synthesizable
- Auto-generated from interface definitions where possible

## Merge-Time Verification Procedure

### Execution Order

When merging a block into the integrated trunk, execute tests in this order:

1. **Target block contract test**: Run the merging block's own contract tests
   ```
   sim/{block}/contract/{block}_if_contract_tb.sv    → PASS required
   sim/{block}/contract/{block}_timing_check.sv      → PASS required
   ```

2. **Cross-block integration test**: Run integration tests with already-merged upstream blocks
   ```
   sim/integration/{upstream}_{block}_integration_tb.sv  → PASS required
   ```
   Uses real upstream block (already merged) + stubs for not-yet-merged downstream blocks.

### Upstream-First Merge Sequence

Blocks merge in dependency order — upstream blocks first:

```
1. entropy   (no upstream dependency — merges first)
2. tq        (depends on: entropy)
3. me        (depends on: dpb for references, but dpb merges later — use dpb_stub)
4. mc        (depends on: me, dpb — use dpb_stub)
5. intra     (depends on: none for merge — reconstruction is downstream)
6. filter    (depends on: reconstruction output)
```

**Rationale**: Upstream-first ensures that when a block merges, its upstream
dependencies are already real (not stubs), providing higher-fidelity integration tests.

**Exception**: `me` and `mc` depend on `dpb` for reference frames, but `dpb` is a
downstream consumer of `filter`. Use `dpb_stub.sv` for `me`/`mc` merge tests, then
re-run integration tests after `dpb` merges.

## PASS/FAIL Criteria

### Per-Test Verdict

- **PASS**: Zero assertion failures, all protocol checks clean, timing within bounds
- **FAIL**: Any assertion failure, protocol violation, or timing contract breach

### Retry Policy

On FAIL, the merge-time verification allows up to 3 retry attempts:

```
Attempt 1: Run contract tests → FAIL
  → Block worker fixes the issue, re-runs
Attempt 2: Run contract tests → FAIL
  → Block worker applies second fix, re-runs
Attempt 3: Run contract tests → FAIL
  → ESCALATE to user via coordinator
```

After 3 consecutive failures:
1. Coordinator marks the block as `MERGE_BLOCKED`
2. Coordinator sends `SendMessage` to leader: `MERGE_BLOCKED: {block} — {failure_summary}`
3. Leader escalates to user via `AskUserQuestion`
4. Remaining blocks continue merging independently (skip blocked block's downstream)

### Cross-Block Regression

After each successful merge, re-run all previously merged blocks' contract tests
to ensure the new block introduction does not break existing integrations.

## Stub Generation Rules

### When to Generate Stubs

- At Phase 4 start: generate stubs for ALL 6 blocks from interface definitions
- Stubs are placed in `sim/{block}/contract/{block}_stub.sv`
- Stubs are updated if interface definitions change (requires freeze violation approval)

### Stub Content Requirements

Each stub MUST provide:

```systemverilog
module {block}_stub (
    // All ports matching the block's interface connections
    // Directly derived from rtl/intf/*_if.sv
);

    // 1. Default output drivers (valid=0, data=0)
    // 2. Programmable response mode:
    //    - IDLE: all outputs deasserted
    //    - ECHO: reflect inputs after N-cycle delay
    //    - PATTERN: output predefined test vectors
    // 3. Backpressure injection:
    //    - ready deassertion probability (0-100%)
    //    - maximum consecutive stall cycles
    // 4. Transaction logging:
    //    - Log all input transactions to file
    //    - Configurable verbosity level

endmodule
```

### Stub Replacement During Merge

As blocks merge in upstream-first order, stubs are progressively replaced:

```
Before entropy merge:  ALL blocks use stubs
After entropy merge:   entropy is real, others use stubs
After tq merge:        entropy + tq are real, others use stubs
...
After filter merge:    ALL blocks are real, no stubs needed
```

Each merge step replaces one stub with the real block in integration tests.
Previously passing integration tests MUST be re-run with the real block.
