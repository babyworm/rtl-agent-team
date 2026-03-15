---
name: rtl-block-interface-policy
description: "Policy skill defining interface design rules, timing contract format, and Phase 2 interface freeze criteria for block-parallel RTL development."
user-invocable: false
---

# Block-Parallel Interface Policy

## Interface File Naming Convention

All cross-block interfaces live in dedicated directories:

```
rtl/intf/{src}_{dst}_if.sv    # Per-interface SystemVerilog interface definition
rtl/pkg/codec_if_pkg.sv       # Shared types, parameters, enums for all interfaces
```

Interface files use the naming pattern `{source-block}_{destination-block}_if.sv`.
The package file `codec_if_pkg.sv` defines all shared types referenced by interfaces.

## Cross-Block Interface Inventory (8 Frozen Interfaces)

The following 8 interface files are frozen at Phase 2 exit and shared across blocks:

| File | Source | Destination | Purpose |
|------|--------|-------------|---------|
| `rtl/intf/entropy_tq_if.sv` | entropy | tq | Entropy-decoded coefficients to transform/quant |
| `rtl/intf/me_mc_if.sv` | me | mc | Motion vectors from estimation to compensation |
| `rtl/intf/mc_recon_if.sv` | mc | recon | Compensated prediction to reconstruction |
| `rtl/intf/intra_recon_if.sv` | intra | recon | Intra prediction to reconstruction |
| `rtl/intf/filter_dpb_if.sv` | filter | dpb | Filtered frames to decoded picture buffer |
| `rtl/intf/dpb_me_if.sv` | dpb | me | Reference frames from DPB to motion estimation |
| `rtl/intf/dpb_mc_if.sv` | dpb | mc | Reference frames from DPB to motion compensation |
| `rtl/intf/recon_filter_if.sv` | recon | filter | Reconstructed samples to deblocking filter |

**NOTE**: `recon_filter_if.sv` connects reconstruction to the filter block's input.
It is a frozen shared interface, NOT a filter-internal interface.

## Timing Contract Format

Every interface file MUST contain a timing contract as a structured comment block
immediately after the interface declaration header:

```systemverilog
// TIMING CONTRACT (Phase 3 locked):
//   Handshake: valid/ready, 1-cycle latency
//   Throughput: N pixels/cycle (or N coefficients/cycle)
//   Backpressure: ready deasserts within M cycles max
//   Pipeline depth: K stages from valid to data stable
//   Clock domain: {domain}_clk (or clk if single-domain)
```

Timing contracts are authored during Phase 3 (uArch) and locked before Phase 4.
Any timing contract change during Phase 4 requires coordinator approval and
re-verification of both source and destination blocks.

## Phase 2 Interface Freeze Criteria

### Frozen Artifacts

The following directories are frozen at Phase 2 exit:

| Directory | Contents | Freeze Scope |
|-----------|----------|--------------|
| `rtl/pkg/` | `codec_if_pkg.sv` — shared types and parameters | Full freeze |
| `rtl/intf/` | All 8 `*_if.sv` files listed above | Full freeze |

### Hash Verification Method

At Phase 2 exit, generate a hash manifest:

```bash
# Generate freeze manifest
find rtl/pkg/ rtl/intf/ -name '*.sv' -exec sha256sum {} \; | sort > .rtl-agent-team/state/interface-freeze-manifest.txt
```

At each merge point during Phase 4 block-parallel execution, verify the freeze:

```bash
# Verify no frozen file was modified
find rtl/pkg/ rtl/intf/ -name '*.sv' -exec sha256sum {} \; | sort > /tmp/current-manifest.txt
diff .rtl-agent-team/state/interface-freeze-manifest.txt /tmp/current-manifest.txt
```

If diff is non-empty, the merge MUST be rejected. The block worker that needs an
interface change must report to the coordinator, who escalates to the user.

### Freeze Violation Protocol

1. Block worker detects need for interface change
2. Worker sends `SendMessage` to coordinator: `FREEZE_VIOLATION_REQUEST: {interface_file} — {reason}`
3. Coordinator escalates to leader via `SendMessage`
4. Leader asks user for approval via `AskUserQuestion`
5. If approved: update interface, regenerate freeze manifest, notify ALL blocks
6. If rejected: worker must adapt implementation to existing interface

## Handshake Protocols

### Valid/Ready Protocol

All cross-block interfaces use the valid/ready handshake:

```
- Source asserts `valid` when data is available
- Destination asserts `ready` when it can accept data
- Transfer occurs on the cycle where BOTH valid AND ready are high
- Source MUST NOT deassert valid once asserted (until transfer completes)
- Source data MUST remain stable while valid is high and ready is low
```

### Backpressure Rules

- Destination MAY deassert `ready` at any time to apply backpressure
- Source MUST respect backpressure — no data loss on ready deassertion
- Maximum backpressure duration is specified per-interface in the timing contract
- If backpressure exceeds the specified maximum, the upstream block raises an error flag

### Multi-Beat Transfers

For interfaces carrying multi-beat data (e.g., coefficient blocks, pixel rows):

```
- `valid` asserts on first beat, stays high until last beat
- `last` signal indicates final beat of the transfer
- `ready` can deassert between beats (stall mid-transfer is allowed)
- Transfer length is fixed per interface (defined in codec_if_pkg.sv)
```
