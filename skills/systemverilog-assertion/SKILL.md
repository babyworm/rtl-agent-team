---
name: systemverilog-assertion
description: "systemverilog-assertion project conventions (loaded by writer agents; do not invoke)."
user-invocable: false
---

<Purpose>
SVA project conventions and formal-flow rules for .sva files and SVA blocks in .sv files.
Standard SVA semantics (property/sequence operators, assert/assume/cover/restrict usage) are
assumed known. Target standard: **IEEE 1800-2012** for SVA and verification code
(2012 adds checker, restrict property, sequence methods; 2017 was errata-only).
</Purpose>

<Use_When>
- Writing .sva files, SVA bind files, or protocol assertions (AXI/APB/AHB); preparing for `rtl-p5s-sva-check`
- Agents: sva-extractor, testbench-dev, protocol-checker
</Use_When>

<Do_Not_Use_When>
- Synthesizable RTL → `systemverilog` skill; cocotb verification → `rtl-p5s-func-verify` skill; UVM environments → `uvm` skill
</Do_Not_Use_When>

<Execution_Policy>
- **Bind-file-first**: prefer bind files over embedding assertions inside RTL modules
- Every assertion is labeled and carries a failure message (`else $error(...)`)
- New SVA file scaffold + handshake (valid-hold/data-stable) patterns: `templates/sva-bind-template.sv`;
  FIFO safety/liveness/coverage patterns: `examples/fifo-sva-example.sv`
</Execution_Policy>

<Steps>

## 1. Naming Conventions

| Target | Pattern | Example |
|--------|---------|---------|
| Assert label | `a_{signal}_{condition}` | `a_valid_hold`, `a_data_stable` |
| Assume label | `m_{signal}_{constraint}` | `m_valid_no_x`, `m_addr_aligned` |
| Cover label | `c_{scenario}` | `c_back_to_back`, `c_max_burst` |
| Sequence | `seq_{name}` | `seq_handshake`, `seq_burst_complete` |
| Property | `prop_{name}` | `prop_valid_hold`, `prop_fifo_no_overflow` |
| SVA file | `sva_{module}.sv` | `sva_axi_slave.sv` |
| SVA bind module | `sva_{module}_checker` | `sva_axi_slave_checker` |

## 2. Clock/Reset Patterns

### 2.1 Basic Structure
```systemverilog
// All concurrent assertions use default clocking + disable iff
default clocking cb @(posedge sys_clk); endclocking
default disable iff (!sys_rst_n);
```

### 2.2 Past-Valid Guard
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

## 3. Assertion Hygiene (Project Requirements)

- Every assertion has a label (per §1 naming) AND a failure message: `else $error("[%m] ... at %0t", $time)`
- Concurrent asserts at module scope only — never `assert property` inside `always_comb`,
  never bare immediate `assert(sig)` inside `always_ff` (simulation-only, invisible to formal)
- Unknown checks use `$isunknown`; verify assertion reachability with `cover property`
- Minimize `assume property` (over-constraining discards traces); validate assumes with cover
- One-hot/mutex: `a_onehot_grant: assert property ($onehot0(o_grant));` — mutual exclusion:
  `assert property (!(o_read_en && o_write_en));`
- Bounded liveness: `a_req_ack: assert property (i_req |-> ##[1:MAX_LATENCY] o_ack);`
  (unbounded eventually is unprovable by BMC — see §5.3)
- Handshake pattern reference: `templates/sva-bind-template.sv`; FIFO safety/liveness:
  `examples/fifo-sva-example.sv`

## 4. Bind-File-First Policy

Attach assertions externally via a `sva_{module}_checker` module + `bind` statement — do NOT
modify the RTL module. The checker module ports mirror the RTL port names verbatim
(`i_`/`o_` prefixes, `sys_clk`, `sys_rst_n`), so the bind uses `(.*)`:
```systemverilog
bind my_module sva_my_module_checker u_sva_checker (.*);
```
Complete scaffold (checker module + default clocking/disable + bind): `templates/sva-bind-template.sv`.

## 5. SymbiYosys Integration

### 5.0 sv2v Conversion (Mandatory for SymbiYosys/Yosys)
SymbiYosys uses Yosys internally, which has limited SystemVerilog support.
**RTL `.sv` files must be converted to Verilog via sv2v before running sby:**
```bash
sv2v rtl/{module}/*.sv -o rtl/{module}/{module}_v2v.v
```
- The `.sby` config `[files]` section must list the converted `_v2v.v` file, not `.sv`
- SVA bind files / property files (`sva_*.sv`) do **NOT** need conversion — they are read with `-formal -sv` by SymbiYosys
- The RTL that the SVA binds **to** needs sv2v conversion

### 5.1 Formal Verification Modes
| Mode | Purpose | SBY Config |
|------|---------|------------|
| BMC (Bounded Model Check) | Search for counterexamples within finite depth | `mode bmc`, `depth 20-50` |
| Induction (prove) | Mathematical proof at unbounded depth | `mode prove` |
| Cover | Verify reachability of cover points | `mode cover` |

### 5.2 assume vs assert
- `assume`: input constraint for formal tool (behaves like assert in simulation)
- `assert`: property under verification
- In formal, traces violating assume are discarded (beware of over-constraining!)

### 5.3 Liveness Caution
- BMC cannot prove liveness properties (eventually) — use prove mode
- Even in prove mode, infinite waits may cause induction failure → add bounds

</Steps>

<Tool_Usage>
This skill is not executed directly. It is referenced by agents that generate SVA
(e.g., sva-extractor, protocol-checker). Agents should follow the conventions defined here.
</Tool_Usage>

<Examples>
Bind file with default clocking/disable, past_valid guard, and labeled+messaged assertions:
`templates/sva-bind-template.sv` and `examples/fifo-sva-example.sv`.
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
