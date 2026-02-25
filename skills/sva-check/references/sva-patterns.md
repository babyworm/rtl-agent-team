# SVA Pattern Library for RTL Verification

## Temporal Operator Quick Reference

| Operator | Meaning | Example |
|----------|---------|---------|
| `\|->` | Overlapping implication | `req \|-> ack` (ack same cycle as req) |
| `\|=>` | Non-overlapping implication (1 cycle delay) | `req \|=> ack` (ack next cycle) |
| `##N` | Exact delay of N cycles | `req ##2 ack` (ack 2 cycles after req) |
| `##[M:N]` | Delay range | `req ##[1:3] ack` (ack 1-3 cycles after) |
| `##[0:$]` | Eventually (unbounded) | `req ##[0:$] ack` (ack sometime after) |
| `[*N]` | Exact repetition | `sig[*3]` (sig high for 3 consecutive cycles) |
| `[*M:N]` | Repetition range | `sig[*1:4]` (sig high for 1-4 cycles) |
| `[->N]` | Goto repetition | `sig[->2]` (sig true exactly twice, non-consecutive OK) |
| `[=N]` | Non-consecutive repetition | `sig[=2]` (sig true twice, any spacing) |
| `$rose(s)` | Signal rose this cycle | `$rose(i_valid) \|-> ##[1:5] $rose(o_ack)` |
| `$fell(s)` | Signal fell this cycle | `$fell(sys_rst_n) \|-> !o_valid` |
| `$stable(s)` | Signal unchanged | `i_valid && !o_ready \|=> $stable(i_data)` |
| `$past(s,N)` | Value N cycles ago | `o_valid \|-> $past(i_valid, LATENCY)` |

## Common SVA Patterns

### 1. Valid/Ready Handshake (AXI-style)
```systemverilog
// Data must be stable while valid is high and ready is low
ap_data_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (i_valid && !o_ready) |=> $stable(i_data)
);

// Valid must not deassert without ready
ap_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (i_valid && !o_ready) |=> i_valid
);

// No output valid during reset
ap_no_valid_in_reset: assert property (
  @(posedge sys_clk)
  !sys_rst_n |-> !o_valid
);
```

### 2. FIFO Safety
```systemverilog
// No write when full
ap_no_write_when_full: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (full && i_wr_en) |-> 1'b0  // should never happen
);

// No read when empty
ap_no_read_when_empty: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (empty && i_rd_en) |-> 1'b0
);

// Count bounded
ap_count_bounded: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  count <= DEPTH
);
```

### 3. FSM Safety
```systemverilog
// One-hot state encoding check
ap_onehot: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  $onehot(state_q)
);

// No unknown states
ap_no_x_state: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  !$isunknown(state_q)
);

// Deadlock freedom: always eventually return to IDLE
cp_no_deadlock: cover property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  (state_q != IDLE) ##[1:100] (state_q == IDLE)
);
```

### 4. Pipeline Invariants
```systemverilog
// Pipeline latency: output valid exactly LATENCY cycles after input valid
ap_pipeline_latency: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  $rose(i_valid) |-> ##LATENCY o_valid
);

// Pipeline data integrity: output matches delayed input
ap_pipeline_data: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  o_valid |-> (o_data == $past(expected_transform(i_data), LATENCY))
);
```

### 5. Reset Behavior
```systemverilog
// All outputs deasserted during reset
ap_reset_outputs: assert property (
  @(posedge sys_clk)
  !sys_rst_n |-> (o_valid == 1'b0 && o_data == '0)
);

// FSM resets to IDLE
ap_reset_fsm: assert property (
  @(posedge sys_clk)
  !sys_rst_n |=> (state_q == IDLE)
);
```

## SymbiYosys Engine Selection

| Engine | Mode | Best For |
|--------|------|----------|
| `smtbmc boolector` | BMC, prove | General purpose, good default |
| `smtbmc z3` | BMC, prove | Arithmetic-heavy designs |
| `smtbmc yices` | BMC, prove | Bitvector-heavy, often fastest |
| `abc pdr` | prove only | Unbounded proof via PDR, no depth limit needed |
| `aiger btormc` | BMC only | Very fast for small designs |
| `abc sim3` | BMC only | Simulation-based, good for large state spaces |

## Safe $past Usage Pattern

```systemverilog
// Guard $past with a past_valid flag to avoid undefined behavior on first cycle
logic past_valid;
always_ff @(posedge sys_clk or negedge sys_rst_n)
  if (!sys_rst_n) past_valid <= 1'b0;
  else            past_valid <= 1'b1;

ap_safe_past: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  past_valid |-> ($past(i_data) == expected)
);
```
