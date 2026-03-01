---
name: systemverilog-assertion
description: "SVA (SystemVerilog Assertion) coding convention and formal verification guideline skill. Covers assertion styles, property/sequence patterns, bind files, coverage properties, and SymbiYosys integration. Applied when writing .sva files or SVA blocks in .sv files."
user-invocable: false
---

<Purpose>
SystemVerilog Assertion (SVA) coding standards and formal verification guidelines.
All agents writing or modifying SVA must follow the rules in this skill.
Target standard: **IEEE 1800-2012** for SVA and verification code.
2012 adds checker construct, restrict property, and sequence methods useful for formal verification.
(2017 had no new features — errata/clarification only.)
</Purpose>

<Use_When>
- When writing .sva files or SVA bind files
- When preparing assertions for the rtl-sva-check skill
- During Phase 5 (Verification) — formal verification work
- When writing protocol assertions (AXI, APB, AHB, etc.)
- Agents: sva-extractor, testbench-dev, protocol-checker
</Use_When>

<Do_Not_Use_When>
- When writing RTL synthesizable code → use `systemverilog` skill
- When doing cocotb Python-based verification → refer to `rtl-func-verify` skill
- When building UVM-based verification environments → use `uvm` skill
</Do_Not_Use_When>

<Why_This_Exists>
SVA is the only way to mathematically express the design intent of RTL.
Well-written assertions can:
- Be mathematically proven with formal tools (SymbiYosys)
- Immediately detect bugs during simulation
- Serve as design documentation (executable specification)
Following consistent SVA patterns improves readability, reusability, and tool compatibility.
</Why_This_Exists>

<Execution_Policy>
- Applies to all agents writing SVA
- Prefer bind file approach over embedding assertions directly inside RTL modules
- All assertions must include a failure message
- Use `templates/sva-bind-template.sv` as the starting point for new SVA files
- Review `examples/fifo-sva-example.sv` for FIFO safety assertion patterns
</Execution_Policy>

<Steps>

## 1. Assertion Style Classification

| Style | Purpose | Keyword |
|-------|---------|---------|
| Immediate | Combinational condition check | `assert (expr)` |
| Concurrent | Time-based property verification | `assert property (...)` |
| Deferred | Check after delta-cycle | `assert #0 (expr)` |
| Assume | Pass input constraints to formal tool | `assume property (...)` |
| Cover | Verify reachability | `cover property (...)` |
| Restrict | Constraint applied to formal only | `restrict property (...)` |

### Usage Guide
- **Shared between simulation + formal**: use `assert property`
- **Formal-only input constraints**: use `assume property`
- **Coverage targets**: use `cover property`
- Immediate assert is for combinational checks only (inside always_comb)

## 2. Naming Conventions

| Target | Pattern | Example |
|--------|---------|---------|
| Assert label | `a_{signal}_{condition}` | `a_valid_hold`, `a_data_stable` |
| Assume label | `m_{signal}_{constraint}` | `m_valid_no_x`, `m_addr_aligned` |
| Cover label | `c_{scenario}` | `c_back_to_back`, `c_max_burst` |
| Sequence | `seq_{name}` | `seq_handshake`, `seq_burst_complete` |
| Property | `prop_{name}` | `prop_valid_hold`, `prop_fifo_no_overflow` |
| SVA file | `sva_{module}.sv` | `sva_axi_slave.sv` |
| SVA bind module | `sva_{module}_checker` | `sva_axi_slave_checker` |

## 3. Clock/Reset Patterns

### 3.1 Basic Structure
```systemverilog
// All concurrent assertions use default clocking + disable iff
default clocking cb @(posedge sys_clk); endclocking
default disable iff (!sys_rst_n);
```

### 3.2 Past-Valid Guard
The $past() value is invalid on the first cycle after reset, so use a guard:
```systemverilog
logic past_valid;
always_ff @(posedge sys_clk or negedge sys_rst_n) begin
  if (!sys_rst_n) past_valid <= 1'b0;
  else            past_valid <= 1'b1;
end

// Always check past_valid when using $past
a_data_stable: assert property (
  past_valid && $rose(i_valid) |-> ##1 $stable(i_data)
) else $error("Data must be stable after valid rises");
```

## 4. Core Assertion Patterns

### 4.1 Valid/Ready Handshake
```systemverilog
// Valid must hold until ready
a_valid_hold: assert property (
  i_valid && !o_ready |=> i_valid
) else $error("valid must hold until ready");

// Data must be stable while valid
a_data_stable: assert property (
  i_valid && !o_ready |=> $stable(i_data)
) else $error("data must be stable while valid && !ready");

// No unknowns allowed
a_valid_no_x: assert property (
  !$isunknown(i_valid)
) else $error("valid must not be X/Z");
```

### 4.2 FIFO Safety
```systemverilog
a_no_overflow: assert property (
  i_push && !i_pop |-> o_count < DEPTH
) else $error("FIFO overflow: push when full");

a_no_underflow: assert property (
  i_pop && !i_push |-> o_count > 0
) else $error("FIFO underflow: pop when empty");
```

### 4.3 One-Hot / Mutex
```systemverilog
a_onehot_grant: assert property (
  $onehot0(o_grant)
) else $error("Grant must be one-hot or zero");

a_mutex_access: assert property (
  !(o_read_en && o_write_en)
) else $error("Simultaneous read and write forbidden");
```

### 4.4 Liveness (Eventually)
```systemverilog
// Request must be acknowledged within N cycles
a_req_ack: assert property (
  i_req |-> ##[1:MAX_LATENCY] o_ack
) else $error("No ack within MAX_LATENCY cycles");
```

## 5. Bind File Patterns

Attach assertions externally without modifying the RTL module:
```systemverilog
// sva_my_module.sv
module sva_my_module_checker (
  input logic       sys_clk,
  input logic       sys_rst_n,
  input logic [7:0] i_data,
  input logic       i_valid,
  input logic       o_ready
);
  default clocking cb @(posedge sys_clk); endclocking
  default disable iff (!sys_rst_n);

  // Assertions here...
  a_valid_hold: assert property (
    i_valid && !o_ready |=> i_valid
  ) else $error("valid must hold until ready");
endmodule

// Bind statement (separate file or bottom of same file)
bind my_module sva_my_module_checker u_sva_checker (.*);
```
See `templates/sva-bind-template.sv` for complete scaffold.

## 6. SymbiYosys Integration

### 6.1 Formal Verification Modes
| Mode | Purpose | SBY Config |
|------|---------|------------|
| BMC (Bounded Model Check) | Search for counterexamples within finite depth | `mode bmc`, `depth 20-50` |
| Induction (prove) | Mathematical proof at unbounded depth | `mode prove` |
| Cover | Verify reachability of cover points | `mode cover` |

### 6.2 assume vs assert
- `assume`: input constraint for formal tool (behaves like assert in simulation)
- `assert`: property under verification
- In formal, traces violating assume are discarded (beware of over-constraining!)

### 6.3 Liveness Caution
- BMC cannot prove liveness properties (eventually) — use prove mode
- Even in prove mode, infinite waits may cause induction failure → add bounds

## 7. Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| `assert(signal)` in always_ff | Simulation only, not supported by formal | Use `assert property` |
| missing `disable iff` | False failure during reset | `default disable iff (!rst_n)` |
| `$past` without past_valid | Comparing X values right after reset | Add past_valid guard |
| Over-constraining with assume | No valid traces | Minimize assumes, verify with cover |
| No failure message | Cannot debug | Add `else $error(...)` to all asserts |
| `assert property` in `always_comb` | Syntax error | Place concurrent asserts at module scope |

</Steps>

<Tool_Usage>
This skill is not executed directly. It is referenced by agents that generate SVA:
```
Task(subagent_type="rtl-agent-team:sva-extractor",
     prompt="... Follow systemverilog-assertion skill conventions. Use bind file pattern.")

Task(subagent_type="rtl-agent-team:protocol-checker",
     prompt="... Follow systemverilog-assertion skill for AXI protocol assertions.")
```
</Tool_Usage>

<Examples>
<Good>
Uses bind file, default clocking/disable, past_valid guard, failure message:
```systemverilog
default clocking cb @(posedge sys_clk); endclocking
default disable iff (!sys_rst_n);

a_valid_hold: assert property (
  i_valid && !o_ready |=> i_valid
) else $error("[%m] valid dropped before ready at %0t", $time);
```
</Good>
<Bad>
Direct insertion inside RTL, immediate assert, no message:
```systemverilog
always_ff @(posedge clk) begin
  assert(valid);  // WRONG: immediate assert (not concurrent), no message, no label
end
```
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- SymbiYosys BMC/prove FAIL → have sva-extractor analyze counterexample, request RTL fix from rtl-coder
- Over-constrained (cover FAIL) → review assume conditions
- Protocol spec unclear → request clarification from spec-analyst
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Use bind file approach (minimize direct insertion inside RTL)
- [ ] `default clocking` / `default disable iff` configured
- [ ] past_valid guard present when using $past
- [ ] `else $error(...)` failure message on all asserts
- [ ] Label naming: `a_` (assert), `m_` (assume), `c_` (cover)
- [ ] Unknown check: use `$isunknown`
- [ ] Verify assertion reachability with cover properties
- [ ] Port names match RTL (i_/o_, sys_clk, sys_rst_n)
</Final_Checklist>
