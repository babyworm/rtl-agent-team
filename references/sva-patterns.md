# SVA Temporal Operator Reference and Pattern Library

> This document is the detailed reference for the `rtl-sva-check` skill.
> For core rules, see `<Steps>` in `skills/rtl-sva-check/SKILL.md`.

## 1. Temporal Operators

### 1.1 Sequence Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `##N` | After N cycles | `a ##1 b` — b one cycle after a |
| `##[M:N]` | Range of M to N cycles | `a ##[1:3] b` — b within 1 to 3 cycles |
| `##[0:$]` | Eventually | `a ##[0:$] b` — b sometime after a |
| `[*N]` | N consecutive repetitions | `a[*3]` — a for 3 consecutive cycles |
| `[*M:N]` | M to N repetitions | `a[*1:5]` — 1 to 5 consecutive times |
| `[*0:$]` | Zero or more repetitions | `a[*0:$]` — zero or more consecutive times |
| `[=N]` | Non-consecutive N times | `a[=3]` — total 3 times (gaps allowed) |
| `[->N]` | Non-consecutive goto N times | `a[->3]` — until the 3rd occurrence of a |

### 1.2 Property Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `\|->` | Overlapping implication | `a \|-> b` — check b in same cycle as a |
| `\|=>` | Non-overlapping implication | `a \|=> b` — check b in cycle after a |
| `not` | Negation | `not (a ##1 b)` — sequence does not occur |
| `and` | Both hold | `p1 and p2` |
| `or` | At least one holds | `p1 or p2` |
| `if...else` | Conditional | `if(cond) p1 else p2` |
| `until` | Holds until | `a until b` — a holds until b |
| `s_until` | Strong until | Guarantees b eventually occurs |
| `eventually` | Eventually holds | `s_eventually(a)` — a holds eventually |

### 1.3 System Functions

| Function | Meaning | Notes |
|----------|---------|-------|
| `$rose(sig)` | 0 to 1 transition | |
| `$fell(sig)` | 1 to 0 transition | |
| `$stable(sig)` | Value unchanged | |
| `$changed(sig)` | Value changed | |
| `$past(sig, N)` | Value N cycles ago | **past_valid guard required** |
| `$onehot(sig)` | exactly one bit high | |
| `$onehot0(sig)` | at most one bit high | |
| `$isunknown(sig)` | Contains X or Z | |
| `$countones(sig)` | Number of bits set to 1 | |

## 2. Assertion Pattern Library

### 2.1 Valid/Ready Handshake

```systemverilog
// Valid holds until ready
a_valid_hold: assert property (
  i_valid && !o_ready |=> i_valid
) else $error("[%m] valid dropped before ready");

// Data stable while valid && !ready
a_data_stable: assert property (
  i_valid && !o_ready |=> $stable(i_data)
) else $error("[%m] data changed while waiting for ready");

// No X/Z on control signals
a_valid_no_x: assert property (
  !$isunknown(i_valid)
) else $error("[%m] valid is X/Z");

a_ready_no_x: assert property (
  !$isunknown(o_ready)
) else $error("[%m] ready is X/Z");
```

### 2.2 FIFO Safety

```systemverilog
// No push when full
a_no_overflow: assert property (
  i_push && !i_pop |-> !o_full
) else $error("[%m] FIFO overflow");

// No pop when empty
a_no_underflow: assert property (
  i_pop && !i_push |-> !o_empty
) else $error("[%m] FIFO underflow");

// Count consistency
a_count_range: assert property (
  o_count >= 0 && o_count <= DEPTH
) else $error("[%m] count out of range");

// Empty/Full vs count
a_empty_iff: assert property (
  o_empty == (o_count == 0)
) else $error("[%m] empty flag mismatch");

a_full_iff: assert property (
  o_full == (o_count == DEPTH)
) else $error("[%m] full flag mismatch");
```

### 2.3 FSM Safety

```systemverilog
// One-hot state encoding
a_state_onehot: assert property (
  $onehot(state_q)
) else $error("[%m] state not one-hot");

// No deadlock (always eventually leaves non-idle state)
a_no_deadlock: assert property (
  (state_q != ST_IDLE) |-> s_eventually(state_q == ST_IDLE)
) else $error("[%m] FSM deadlock");

// Known state (no X)
a_state_known: assert property (
  !$isunknown(state_q)
) else $error("[%m] state is X/Z");
```

### 2.4 Pipeline Valid Propagation

```systemverilog
// Stage valid propagation (with stall)
a_pipe_valid: assert property (
  stage1_valid && !i_stall |=> stage2_valid
) else $error("[%m] pipeline valid not propagated");

// Data follows valid through pipeline
a_pipe_data: assert property (
  stage1_valid && !i_stall |=> (stage2_data == $past(stage1_data))
) else $error("[%m] pipeline data corruption");
```

### 2.5 AXI Protocol (Basic)

```systemverilog
// AW channel: AWVALID holds until AWREADY
a_aw_valid_hold: assert property (
  i_awvalid && !o_awready |=> i_awvalid
) else $error("[%m] AWVALID dropped");

// W channel: WVALID holds until WREADY
a_w_valid_hold: assert property (
  i_wvalid && !o_wready |=> i_wvalid
) else $error("[%m] WVALID dropped");

// B channel: BVALID holds until BREADY
a_b_valid_hold: assert property (
  o_bvalid && !i_bready |=> o_bvalid
) else $error("[%m] BVALID dropped");

// Write response only after write
a_b_after_w: assert property (
  $rose(o_bvalid) |-> ##[0:$] $past(i_wvalid && o_wready && i_wlast)
) else $error("[%m] BRESP without prior write");
```

### 2.6 Reset Behavior

```systemverilog
// After reset, outputs are known values
a_reset_output: assert property (
  !sys_rst_n |=> (o_valid == 1'b0) && (o_data == '0)
) else $error("[%m] output not reset");

// No activity during reset
a_reset_inactive: assert property (
  !sys_rst_n |-> !o_valid
) else $error("[%m] output active during reset");
```

### 2.7 Liveness (Bounded Response)

```systemverilog
// Request gets response within MAX_LATENCY cycles
a_bounded_resp: assert property (
  i_req |-> ##[1:MAX_LATENCY] o_ack
) else $error("[%m] no response within %0d cycles", MAX_LATENCY);
```

## 3. Suitable Patterns by Formal Verification Mode

| Pattern | BMC | Prove | Cover |
|---------|-----|-------|-------|
| Handshake valid/ready | O | O | — |
| FIFO overflow/underflow | O | O | — |
| FSM one-hot | O | O | — |
| No deadlock (s_eventually) | X | O | — |
| Bounded response | O (depth >= MAX_LATENCY) | O | — |
| Reachability | — | — | O |
| Back-to-back transfer | — | — | O |
| Max burst length | — | — | O |

## 4. assume vs assert Guide

| Situation | Use | Example |
|-----------|-----|---------|
| DUT internal property | `assert` | `a_fifo_no_overflow` |
| Input constraint (formal) | `assume` | `m_valid_no_x` |
| Input protocol (formal) | `assume` | `m_valid_stable` |
| Coverage goal | `cover` | `c_back_to_back` |
| Formal-only constraint | `restrict` | `restrict property (i_mode == 2'b01)` |

**Over-constraint prevention**: Write a corresponding `cover` for every `assume` to verify that the assume leaves valid traces.
