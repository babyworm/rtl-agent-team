---
name: rat-ultraloop-ppa
description: "Auto-loop wrapper for DC-based PPA optimization. Repeats rtl-ppa-optimize-dc until convergence, early-plateau escalation, or max_cycles. 30-min auto-continue support. Emits final report + marks rtl-verify-done on normal convergence."
user-invocable: true
argument-hint: "[top-module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, Skill, AskUserQuestion
---

<Purpose>
Drive the DC-based PPA optimization loop to convergence. Wraps
`rtl-ppa-optimize-dc` in an auto-repeat loop with three termination tiers:
early plateau, normal convergence, max cycles. On normal convergence, runs
full Phase 5 regression and writes `rtl-verify-done` + `ppa-opt-done`.
</Purpose>

<Use_When>
- User says "ultraloop PPA", "PPA auto-loop", "optimize PPA until converge"
- Verified RTL ready for PPA refinement
- Industrial flow with dc_shell/genus available
</Use_When>

<Do_Not_Use_When>
- Preconditions of rtl-ppa-optimize-dc are not met
- User wants a single iteration only (use rtl-ppa-optimize-dc)
- Design is still under architectural change (freeze first)
</Do_Not_Use_When>

## Invocation

```
/rtl-agent-team:rat-ultraloop-ppa [top_module]
```

## Loop Body

```python
import json, time, shutil, subprocess, pathlib

TOP = ARGUMENTS or json.load(open("requirements.json"))["top_module"]

# Hard preconditions
assert shutil.which("dc_shell") or shutil.which("genus"), \
    "rat-ultraloop-ppa requires dc_shell or genus in PATH"

req = json.load(open("requirements.json"))
assert "ppa_targets" in req, \
    "requirements.json missing ppa_targets — run rtl-ppa-optimize-dc once to scaffold"

max_cycles = int(req["ppa_targets"].get("convergence", {}).get("max_cycles", 4))

# Initialize state
state_path = pathlib.Path(".rat/state/ppa-loop-state.json")
if not state_path.exists():
    state = {
        "mode": "ppa-loop",
        "cycle": 0,
        "max_cycles": max_cycles,
        "weights": req["ppa_targets"].get("weights", {"timing":0.7, "power":0.2, "area":0.1}),
        "convergence": {
            "delta_pct": req["ppa_targets"].get("convergence", {}).get("delta_pct", 2.0),
            "streak_required": req["ppa_targets"].get("convergence", {}).get("streak", 3),
            "early_plateau_pct": req["ppa_targets"].get("convergence", {}).get("early_plateau_pct", 1.0),
            "history": [],
        },
        "allowed_edit_scope": [f"rtl/{TOP}/**/*.sv"],
        "frozen_scope": ["rtl/common/**", "rtl/pkg/**", "rtl/intf/**"],
        "last_cycle_timestamp": int(time.time()),
        "auto_continue_minutes": 30,
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2))

# Iterate
for cycle in range(1, max_cycles + 1):
    verdict = Skill(skill="rtl-agent-team:rtl-ppa-optimize-dc", prompt=TOP)
    verdict = verdict.strip().splitlines()[-1].strip()

    if verdict in ("CONVERGED_STREAK", "CONVERGED_TARGETS"):
        # Full Phase 5 regression confirmation
        Skill(skill="rtl-agent-team:rtl-p5-verify", prompt="--mode=final --source=ppa-opt")
        pathlib.Path(".rat/state/rtl-verify-done").write_text(f"ppa-opt-converge cycle {cycle}\n")
        pathlib.Path(".rat/state/ppa-opt-done").write_text(f"converge cycle {cycle}\n")
        generate_final_report("CONVERGED", cycle)
        pathlib.Path(state_path).unlink()
        break

    if verdict == "EARLY_PLATEAU":
        generate_plateau_report(cycle)
        pathlib.Path(state_path).unlink()
        break

    if verdict == "MAX_CYCLES":
        generate_final_report("MAX_CYCLES", cycle)
        pathlib.Path(state_path).unlink()
        break

    # CONTINUE — next iteration
    continue

else:
    # Safety net (should not reach here due to MAX_CYCLES check above)
    generate_final_report("LOOP_EXIT_UNEXPECTED", cycle)
    pathlib.Path(state_path).unlink()
```

## Final Report (`docs/ppa-opt/final-report.md`)

```markdown
# PPA Optimization Final Report

- Target module: {TOP}
- Cycles executed: {N} / {max_cycles}
- Exit reason: CONVERGED | EARLY_PLATEAU | MAX_CYCLES

## Iteration history

| iter | wns_ns | power_mw | area_um2 | weighted_Δ |

## Best-so-far iteration
- iter: {best_iter}
- wns_ns: {}  power_mw: {}  area_um2: {}

## Next steps
- If CONVERGED: full Phase 5 regression passed → proceed to Phase 6 design note
- If EARLY_PLATEAU: see reviews/ppa-opt/early-plateau-escalation.md
- If MAX_CYCLES: consider raising max_cycles in requirements.json["ppa_targets"]["convergence"]
```

## 30-Min Auto-Continue

Reuses the `stop-gate.sh` escalation pattern: when
`.rat/state/ppa-loop-state.json` is present with `mode == "ppa-loop"` and
`last_cycle_timestamp + auto_continue_minutes*60 > now`, the hook auto-continues
instead of stopping.
