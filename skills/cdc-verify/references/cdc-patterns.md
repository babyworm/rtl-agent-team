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
