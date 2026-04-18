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

# The LLM executes the following iterative protocol. The block below is
# CONCEPTUAL pseudo-code (Skill() is not a callable Python function) —
# the real mechanism is a slash-command invocation followed by reading
# the verdict file that the orchestrator writes.
```

## Loop Protocol (the LLM executes these steps iteratively)

For each cycle in 1..max_cycles:

1. **Invoke action skill** — call `/rtl-agent-team:rtl-ppa-optimize-dc <TOP>`.
   This runs exactly one PPA iteration via the orchestrator, which writes
   `docs/ppa-opt/iter-{cycle}/verdict.txt` on completion.

1a. **Refresh auto-continue timestamp** — update `last_cycle_timestamp` in
    `.rat/state/ppa-loop-state.json` to the current epoch seconds BEFORE
    invoking `rtl-ppa-optimize-dc`. This ensures the 30-minute
    `stop-gate.sh` window restarts each cycle, not only at loop start.
    ```python
    import json, time, pathlib, os, tempfile, fcntl

    STATE_PATH = pathlib.Path(".rat/state/ppa-loop-state.json")
    LOCK_PATH = str(STATE_PATH) + ".lock"

    with open(LOCK_PATH, "a") as lock_f:                 # long-lived lock file; never replaced
        fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            s = json.loads(STATE_PATH.read_text())
            s["last_cycle_timestamp"] = int(time.time())
            dir_ = STATE_PATH.parent
            fd, tmp = tempfile.mkstemp(prefix=".ppa-state-", dir=str(dir_))
            try:
                with os.fdopen(fd, "w") as tmp_f:
                    json.dump(s, tmp_f, indent=2)
                os.replace(tmp, str(STATE_PATH))         # atomic swap
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        finally:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
    ```
    Uses the same atomic lock-file + `os.replace()` pattern as `compute_delta.py`:
    a `.lock` file is held via `fcntl.flock` during the read-modify-write cycle,
    and the updated state is written to a temp file then atomically renamed
    onto the canonical path. This prevents `stop-gate.sh` from observing a
    truncated state file between steps.

2. **Read verdict** — read `docs/ppa-opt/iter-{cycle}/verdict.txt`. Expected
   values: `CONTINUE`, `CONVERGED_STREAK`, `CONVERGED_TARGETS`, `EARLY_PLATEAU`,
   `MAX_CYCLES`, `TIMING_REGRESSION`.

3. **Dispatch by verdict:**

   - **`CONVERGED_STREAK` or `CONVERGED_TARGETS`**:
     - Invoke `/rtl-agent-team:rtl-p5-verify --mode=final --source=ppa-opt`
       for full regression confirmation.
     - Write `.rat/state/rtl-verify-done` with `ppa-opt-converge cycle {cycle}\n`.
     - Write `.rat/state/ppa-opt-done` with `converge cycle {cycle}\n` (triggers
       P6 cascade re-review if the design-note was written prior).
     - Generate `docs/ppa-opt/final-report.md` (see template below).
     - Remove `.rat/state/ppa-loop-state.json`.
     - Exit the loop.

   - **`EARLY_PLATEAU`**:
     - Generate `reviews/ppa-opt/early-plateau-escalation.md`.
     - Remove `.rat/state/ppa-loop-state.json`.
     - Exit the loop.

   - **`MAX_CYCLES`**:
     - Generate `docs/ppa-opt/final-report.md` with exit_reason `MAX_CYCLES`
       (best-so-far iteration recorded).
     - Remove `.rat/state/ppa-loop-state.json`.
     - Exit the loop.

   - **`TIMING_REGRESSION`**:
     - Orchestrator already rolled back the patch via `git checkout -- rtl/<top>`.
     - Generate `reviews/ppa-opt/timing-regression-escalation.md`.
     - Remove `.rat/state/ppa-loop-state.json`.
     - Exit the loop.

   - **`CONTINUE`**:
     - Proceed to the next cycle (increment cycle counter, re-enter step 1).

4. **Safety net** — if the loop falls through `max_cycles` without a terminal
   verdict (should not happen), generate final-report with exit_reason
   `LOOP_EXIT_UNEXPECTED` and remove the state file.

> **Note**: The per-cycle refresh of `last_cycle_timestamp` (step 1a) is
> critical: `stop-gate.sh` uses it to decide whether the 30-min auto-continue
> window is still active. Without it, long DC iterations would be interrupted
> 30 minutes after loop start even when the loop is making progress.

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
