# CDC Verification Patterns Reference

## Synchronizer Types

| Type | Use For | Implementation |
|------|---------|----------------|
| 2-FF Synchronizer | Single-bit signals | Two flip-flops in series in receiving domain |
| 3-FF Synchronizer | High-frequency crossings | Three flip-flops for extra MTBF margin |
| Gray Code FIFO | Multi-bit counters | Gray-encode pointer before crossing |
| Handshake Synchronizer | Multi-bit data bus | REQ/ACK handshake with data hold |
| Pulse Synchronizer | Single-cycle pulses | Toggle-based pulse transfer |
| MUX Synchronizer | Multi-bit data (low rate) | Synchronized select signal gates data MUX |

## Common CDC Violations

| Violation | Risk | Description |
|-----------|------|-------------|
| Missing synchronizer | Critical | Signal crosses domain without any flip-flop synchronization |
| Single-FF sync | Critical | Only one synchronization flip-flop (insufficient MTBF) |
| Multi-bit crossing without gray/handshake | Critical | Bus value can be sampled mid-transition (glitch) |
| Convergence after sync | High | Multiple synchronized signals re-converge (may not be coherent) |
| Reset domain crossing | High | Async reset used in wrong clock domain |
| Fanout from synchronized signal | Medium | Large fanout may cause timing issues on sync path |
| Quasi-static signal unsynchronized | Low | Slowly-changing config signal crosses without sync |

## CDC Analysis Checklist

### Structural Checks (Static Analysis)
1. **Clock domain identification**: Map every register to its clock domain
2. **Crossing enumeration**: List all signals that cross between domains
3. **Synchronizer presence**: Verify each crossing has appropriate synchronizer type
4. **Reconvergence check**: Signals from same source must arrive coherently
5. **Reset synchronization**: Async resets properly synchronized in each domain

### Protocol Checks
1. **Handshake completeness**: REQ→ACK→deassert sequence for all handshake crossings
2. **Gray code validity**: Only one bit changes per clock cycle in gray-coded signals
3. **Data stability**: Bus data stable for full synchronization latency during transfer
4. **FIFO pointer sync**: Read/write pointers properly gray-encoded before crossing

## Edge Cases & Pitfalls

These are areas where incorrect design choices are common. When reviewing or generating
CDC-related RTL, apply these rules explicitly.

### Non-Power-of-2 Async FIFO Depth

Standard Gray code requires 2^N entries to guarantee single-bit change on wrap.
Non-power-of-2 depth breaks this at the wrap point (N-1 → 0 may flip multiple bits).

| Approach | Pros | Cons | Recommendation |
|----------|------|------|----------------|
| **Round up to 2^N** | Safe, simple, standard Gray code works | Wastes memory | **Preferred** — default choice unless memory-constrained |
| **Symmetric pointer (ping-pong)** | No memory waste, 1-bit change preserved | Doubles pointer range, complex full/empty logic | Use only with proven reference design |
| **Johnson counter** | 1-bit change per step | Fixed 2N-state cycle (N-bit register), not arbitrary depth | Only for very small, fixed-size buffers |
| **Binary pointer + handshake** | Works for any depth | Higher latency, lower throughput | When FIFO throughput is not critical |
| **Almost-full/empty flags** | Reduces crossing frequency | Still requires synchronized remote pointer for flag generation | Good for flow control with conservative margin |

**Rule**: When non-2^N FIFO depth is used, the design MUST document which approach
is taken and why. Verify that the wrap-point transition changes at most 1 bit
in the encoding used for crossing. Flag as CAUTION if the approach cannot be
verified structurally.

### Reconvergence

Multiple signals from the same source domain crossing to the same destination domain
independently can arrive at different cycles due to independent synchronizer latency.

```
Source domain A:          Dest domain B:
  q_addr  ──→ 2FF sync ──→ synced_addr
  q_valid ──→ 2FF sync ──→ synced_valid   ← may arrive 1 cycle apart!
```

**Risk**: `synced_valid` may assert while `synced_addr` still holds the old value.
**Fix**: Use handshake or FIFO to transfer addr+valid together, OR use MUX sync
where valid is the control and addr is the data (addr must be held stable while valid
is asserted, until the destination domain captures or acknowledges).

**Rule**: When 2+ signals from the same source FF group cross to the same destination,
flag as CAUTION unless they share a common synchronization mechanism (handshake, FIFO, MUX sync).

### Combinational Logic Before Synchronizer

Combinational logic between the source FF and the first synchronizer FF can produce
glitches that violate the setup/hold window of the sync FF.

```
Source FF ──→ [AND/OR/MUX] ──→ Sync FF1 ──→ Sync FF2   ← GLITCH RISK
Source FF ──→ Sync FF1 ──→ Sync FF2                      ← CORRECT
```

**Rule**: The input to the first synchronizer FF should be driven directly by a
register output (no combinational logic in between). Flag as CAUTION if combinational
logic is detected on the path.

### Fan-out Before Synchronization Complete

Using the signal after the first sync FF but before the second creates a partially-synchronized path.

```
Source FF ──→ Sync FF1 ──→ Sync FF2
                  │
                  └──→ Logic X   ← STILL METASTABLE, unsafe!
```

**Rule**: No fan-out from intermediate sync FFs. Only the output of the final sync FF
(FF2 for 2-FF, FF3 for 3-FF) may drive destination logic.

### Reset Domain Crossing

Async reset signals crossing domains must use a **reset synchronizer**:
async assert (immediate), sync deassert (synchronized to destination clock).

```systemverilog
// CORRECT: async assert, sync deassert
always_ff @(posedge dest_clk or negedge src_rst_n) begin
  if (!src_rst_n) begin
    rst_sync_ff1 <= 1'b0;
    rst_sync_ff2 <= 1'b0;
  end else begin
    rst_sync_ff1 <= 1'b1;
    rst_sync_ff2 <= rst_sync_ff1;
  end
end
assign dest_rst_n = rst_sync_ff2;
```

**Rule**: Async reset used in a different clock domain without reset synchronizer → VIOLATION.

### Clock Gating and CDC

Clock-gated domains share the same source clock but the gated version may stop.
When the gated clock resumes, FFs in the gated domain may sample stale data
from the ungated domain.

**Rule**: Treat gated and ungated versions of the same clock as **related but distinct**
domains. Crossings between them require at minimum data stability verification.
Flag as CAUTION (not VIOLATION, since they are phase-related).

### Quasi-Static Signals

Configuration registers written once at startup and never changed during operation.
Technically a CDC path, but safe if the signal is stable before any destination
domain logic uses it.

**Rule**: If a signal can be proven quasi-static (written only during reset/config phase,
stable during operation), it may be waived. But the waiver must be explicit —
do not silently skip quasi-static crossings.

## CDC Constraint Patterns (SDC)

```tcl
# Define clock domains
create_clock -name sys_clk -period 10.0 [get_ports sys_clk]
create_clock -name axi_clk -period 8.0  [get_ports axi_clk]
create_clock -name codec_clk -period 5.0 [get_ports codec_clk]

# Set clock groups (asynchronous relationship)
set_clock_groups -asynchronous \
  -group {sys_clk} \
  -group {axi_clk} \
  -group {codec_clk}

# False path for synchronized signals (2-FF sync)
set_false_path -from [get_pins u_sync_*/D] -to [get_pins u_sync_*/Q]

# Max delay for handshake crossings
set_max_delay -datapath_only 5.0 \
  -from [get_clocks sys_clk] -to [get_clocks axi_clk]
```

## Open-Source CDC Tools

| Tool | Capability | Command |
|------|------------|---------|
| Yosys + custom script | Basic crossing detection | `yosys -p "read_verilog -sv *.sv; hierarchy -check; proc; scc"` |
| Verilator | `SYNCASYNCNET` warning | `verilator --lint-only -Wall` |
| slang | CDC-aware semantic checks | `slang --lint-only` |

For comprehensive CDC analysis, commercial tools (Synopsys SpyGlass CDC, Cadence Conformal CDC,
Siemens Questa CDC) provide formal proof of synchronizer correctness.
