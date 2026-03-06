---
name: rtl-p5s-perf-policy
description: "Policy rules, performance monitor naming conventions, BFM comparison thresholds (10% deviation), metric definitions, and verification checklists. Pure reference — no orchestration."
user-invocable: false
---

# Performance Verification Policy

## Performance Monitor Naming Conventions

Performance monitor instrumentation and testbenches MUST follow project conventions (CLAUDE.md):
- Signal references: `i_` prefix for inputs, `o_` prefix for outputs (e.g., `i_valid`, `o_stall`)
- Clock: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
- Reset: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
- Performance counter instances: `u_` prefix (e.g., `u_perf_counter`)
- Use `logic` for all signal declarations (NOT `reg`/`wire`)

## Escalation & Stop Conditions

- Performance deficit >20% vs BFM → escalate to rtl-architect for pipeline analysis
- BFM baseline file missing → run bfm-develop first, halt rtl-p5s-perf-verify
- Performance monitor uses wrong signal names → perf-verifier must fix before re-run

## Final Checklist

- [ ] Performance monitors use correct signal names (`i_`/`o_` prefix, `sys_clk`)
- [ ] Deterministic performance vectors used
- [ ] sim/{module}/*_perf.json written for all modules
- [ ] RTL vs BFM comparison done per metric
- [ ] All deviations >10% flagged with root cause analysis

## Stress Vector Patterns and Cycle-Accurate Measurement

Performance vectors should stress maximum throughput (back-to-back `i_valid` high, no gaps).
Also run a stall-stress vector (frequent `o_ready` deassertion) to expose stall handling bugs.
Use `$time` with `sys_clk` edges for cycle-accurate measurement in SV testbenches.
