---
name: rtl-p4s-refactor-policy
description: "Policy rules, refactoring decision criteria, naming convention audit rules, equivalence proof requirements, escalation rules, and checklists for RTL refactoring. Pure reference — no orchestration."
user-invocable: false
---

# RTL Refactoring Policy

## Refactoring Decision Criteria

- Module >500 lines: consider splitting
- 3+ modules share similar code: extract common module
- Naming inconsistency flagged by rtl-critic: rename pass
- Missing parameterization: add parameters for magic numbers
- Refactoring is selective — not all modules need it

## Naming Convention Audit Rules

Refactoring plans MUST include naming convention audit:
- Ports: `i_`/`o_`/`io_` prefix (NOT suffix `_i`/`_o`) — flag violations for correction
- Clocks: `clk` (single domain) or `{domain}_clk` (multiple domains) — flag `clk_i`, `clk_sys`
- Resets: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains) — flag `rst_ni`
- Instances: `u_` prefix — flag missing prefix
- Generates: `gen_` prefix — flag missing prefix
- `logic` only — flag any `reg`/`wire` usage

Common refactoring patterns:
- `data_i` -> `i_data`, `valid_o` -> `o_valid` (suffix to prefix)
- `clk_i` -> `clk` or `sys_clk` (suffix clock to conformant name)
- `rst_ni` -> `rst_n` or `sys_rst_n` (suffix reset to conformant name)
- `fifo_inst` -> `u_fifo` (missing instance prefix)
- `reg [7:0] data` -> `logic [7:0] data` (reg to logic)

When renaming ports, prefer **sv-renamer** (https://github.com/babyworm/sv-renamer) when installed:
```bash
# Dry-run preview
sv_renamer.py --dir rtl/ --recursive --prefix i_ --dry-run --report json
# Apply + verify equivalence
sv_renamer.py --dir rtl/ --recursive --prefix i_
sv_semantic_diff.py --before original/ --after rtl/  # formal equivalence check
```
If sv-renamer is not installed, use Grep to find ALL instantiation sites across the codebase
and update them in the same task.

## Equivalence Proof Policy

- Cosmetic/style-only cleanup: lint + smoke simulation sufficient
- Any change touching combinational/sequential logic, reset, clock enable, or constraints intent:
  invoke equivalence-checker (RTL-vs-RTL) before completion
- Formal equivalence via SymbiYosys (requires sv2v conversion first):
  ```bash
  sv2v rtl/{module}/*.sv -o rtl/{module}/{module}_v2v.v
  cd sim/formal/ && sby -f {module}.sby   # .sby must reference _v2v.v, not .sv
  ```

## Escalation & Stop Conditions

- Equivalence check fails → revert to original, report diff to user
- Refactoring plan conflicts with uarch spec → pause, flag to user
- For large module splits, update all instantiation sites in the same task to maintain consistency

## Final Checklist

- [ ] All changed files pass lint (verilator --lint-only -Wall + slang --lint-only)
- [ ] Equivalence verified (formal or smoke sim)
- [ ] No instantiation sites broken
- [ ] Refactoring plan followed exactly
- [ ] All port names use `i_`/`o_`/`io_` prefix (NOT suffix `_i`/`_o`)
- [ ] All clocks: `clk` or `{domain}_clk` — NOT `clk_i`
- [ ] All resets: `rst_n` or `{domain}_rst_n` — NOT `rst_ni`
- [ ] All instances: `u_` prefix, generates: `gen_` prefix
- [ ] No `reg`/`wire` keywords — `logic` only
