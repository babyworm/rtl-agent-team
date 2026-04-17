---
name: ppa-optimizer-dc-policy
description: "Policy rules, weights defaults, timing-first heuristic, convergence criteria, DC Tcl fragments, and rollback protocol for the DC-based PPA optimization pipeline. Pure reference — no orchestration."
user-invocable: false
---

# PPA Optimizer (DC-based) — Policy Reference

This is a **policy skill**: it defines rules and reference material consumed by
the `ppa-optimizer-dc` agent and the `ppa-optimizer-dc-orchestrator`. It is not
user-invocable.

## Optimization Philosophy

**Timing-first.** EDA tools (DC `compile_ultra -retime -gate_clock`) already
perform exhaustive optimization search; LLM RTL patches add value only where
tools cannot reach: missed clock gating opportunities, ill-shaped critical
paths solvable via pipelining, operand isolation on idle arithmetic blocks.
**Escalate to the user early when improvement stalls.**

## Default Weights

```
timing = 0.7
power  = 0.2
area   = 0.1
```

Loaded from `requirements.json["ppa_targets"]["weights"]`. Sum is normalized to
1.0 at runtime; a sum <= 0 is treated as a hard configuration error.

## Default Convergence Thresholds

```
delta_pct          = 2.0    # normal convergence Δ band
streak_required    = 3      # consecutive iterations with |Δ|<delta_pct
early_plateau_pct  = 1.0    # early-plateau Δ band (iter 1-2)
max_cycles         = 4      # hard stop unless user overrides
```

All overridable via `requirements.json["ppa_targets"]["convergence"]`.

## Three-Tier Termination

| Tier | Condition | Action |
|------|-----------|--------|
| Early plateau | At iter 1 or 2, every observed `|Δ_weighted|` < `early_plateau_pct` | Halt, emit `reviews/ppa-opt/early-plateau-escalation.md`, report to user |
| Normal convergence | Streak of `streak_required` iterations with `|Δ_weighted|` < `delta_pct` OR all targets met | Run full Phase 5 regression, emit `.rat/state/ppa-opt-done` |
| Max cycles | `iter == max_cycles` | Record best-so-far, escalate to user |

## Timing-First Heuristic (rule priority)

```
Rule 1 (HIGHEST · aggressive):  Timing closure
    - WNS < 0 → critical-path pipelining, retiming, logic restructuring
    - Logic levels > 12 @ 100 MHz → register rebalancing
    - REJECT any patch worsening WNS by more than 20 ps

Rule 2 (MAIN · safe):  Clock gating coverage
    - Identify ungated register banks (always_ff without enable)
    - Add enable conditions DC could not auto-infer
    - Goal: gating_efficiency_pct  80% → 90%+

Rule 3 (SECONDARY · timing-neutral):  Operand isolation
    - Target: multiplier / divider with idle cycles > 50%
    - Accepted only when timing slack unchanged

Rule 4 (SECONDARY · timing-neutral):  Resource sharing
    - Target: duplicate operator instances
    - Accepted only when timing slack unchanged
```

### Reject Set

- Any patch worsening WNS by more than 20 ps
- Any patch creating inferred latches
- Any patch touching `frozen_scope`

## Scope Semantics

```
allowed_edit_scope:
  rtl/{target_module}/**/*.sv

frozen_scope:
  rtl/common/**
  rtl/pkg/**
  rtl/intf/**
```

Every iteration runs `validate_patch_scope.py` on the generated `patch.diff`.
Violation → rollback (scoped `git checkout -- 'rtl/<target>/'`) + halt.

## Rollback Protocol

All of these trigger rollback + halt:

- Patch touches `frozen_scope`
- Equivalence check FAIL
- Smoke regression FAIL
- Timing regression > 20 ps (Δ_wns < −0.02 ns)

Rollback is implemented as `git checkout -- 'rtl/<target>/' && git clean -fd -- 'rtl/<target>/'`
to confine reversion to `allowed_edit_scope`. Iteration artifacts under
`docs/ppa-opt/iter-{N}/` are preserved for forensics. Prior to
the loop starting, the skill asserts a clean working tree.

## DC Tcl Fragment

See `templates/dc-compile-ppa.tcl`. Sourced by `run_syn.sh --tool dc_shell` via
the `--extra-script` option when `PPA_OPT_MODE=1`.

## PPA Brief Scaffold

When `requirements.json` is missing `ppa_targets`, the skill writes back the
content of `templates/ppa-brief-scaffold.json` and halts with user prompt.

## Early-Plateau Escalation Report Template

```markdown
# reviews/ppa-opt/early-plateau-escalation.md

## Verdict: EARLY_PLATEAU

{if data_points < 2}
> **Caution:** Only {N} iteration delta point(s) observed before plateau detection.
> Single-point plateau detection indicates the loop halted conservatively; consider
> forcing one additional iteration via `requirements.json["ppa_targets"]["convergence"]["max_cycles"]`
> before relying on this conclusion.
{endif}

EDA tool auto-optimization appears saturated; RTL-level patches yielded
< {early_plateau_pct}% weighted improvement over the observed iterations.

## Iteration history

| iter | wns_ns | power_mw | area_um2 | weighted_Δ |
|------|--------|----------|----------|------------|
| ...  | ...    | ...      | ...      | ...        |

## Current bottleneck (from latest ppa-report.json)

- Critical path: {from} → {to} (slack {slack_ns} ns, {logic_levels} logic levels)
- Power hotspot: {group} {pct}%, clock network {clock_pct}%
- Clock gating efficiency: {gating_efficiency_pct}%

## Recommended user actions

1. Review μArch (pipeline depth, algorithm variant)
2. Relax spec targets (clock / power budget)
3. Evaluate technology changes (stdcell library, Vt mix)
4. Force continuation via:
   requirements.json["ppa_targets"]["convergence"]["max_cycles"] = N  (N > 4)
```

## Phase Integer Mapping

The `ppa-opt` phase is identified in `phase-registry.json` by the string key
`"ppa-opt"` with `"order": 5.5` (semantic: between P5 verify and P6 design-note).
For POSIX shell compatibility, `sctx_skill_to_phase()` emits integer `8`.

| Registry phase | Integer | Role |
|----------------|---------|------|
| `"ppa-opt"`    | 8       | Post-Verify PPA optimization |

Rationale: the integer space 1–7 is reserved for canonical pipeline phases.
Integer 8 is used for the optional post-verify stage. Any future phases beyond
7 should follow this extension pattern and also declare `"integer_map": <N>`
in the registry entry so the dual encoding stays discoverable.

## References

- Synopsys Design Compiler User Guide — `compile_ultra`, `set_clock_gating_style`
- Synopsys Power Compiler User Guide — `set_power_opt`, `report_power -analysis_effort`
- Weste & Harris, *CMOS VLSI Design* — clock gating methodology
