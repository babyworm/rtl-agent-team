---
name: rat-ultraloop
description: "Autonomous implement-review-improve loop with 30-min auto-continue and design freeze enforcement. Wraps target skills for unattended execution."
user-invocable: true
argument-hint: "<target-skill-name>"
---

<Purpose>
Execute an autonomous implement-review-improve loop that wraps a target skill (typically
rtl-p4-block-parallel) for unattended long-running execution. Each cycle: execute/continue
the target skill, dispatch an ultraloop-reviewer for quality assessment, apply improvements,
run contract tests, and verify design freeze integrity. Supports 30-minute auto-continue
via stop-gate.sh escalation pattern.
</Purpose>

<Use_When>
- Running long implementation tasks unattended (e.g., block-parallel Phase 4)
- User says "ultraloop", "autonomous loop", "unattended implement"
- Want automated implement-review-improve cycles with quality gates
- Design decisions are finalized and Phase 2/3 are complete
</Use_When>

<Do_Not_Use_When>
- Design decisions still pending (need user input for architecture choices)
- Phase 2 interfaces not yet frozen (run rtl-p2-arch-design first)
- Phase 3 uArch specs not complete (run rtl-p3-uarch-design first)
- Quick single-module fix (use rtl-p4s-bugfix instead)
</Do_Not_Use_When>

## Invocation

```
/rtl-agent-team:rat-ultraloop rtl-p4-block-parallel
```

The argument specifies the target skill to wrap in the autonomous loop.

## Design Freeze Snapshot

Before starting the loop, capture a hash of all frozen artifacts:

```python
frozen_hash = Bash("find rtl/pkg/ rtl/intf/ docs/phase-3-uarch/ -name '*.sv' -o -name '*.md' 2>/dev/null | sort | xargs sha256sum 2>/dev/null | sha256sum | cut -d' ' -f1").strip()

Write(".rat/state/design-freeze.json", json.dumps({
    "frozen_hash": frozen_hash,
    "frozen_paths": ["rtl/pkg/", "rtl/intf/", "docs/phase-3-uarch/"],
    "created_at": ISO_TIMESTAMP
}))
```

## Autonomous Loop

```python
target_skill = ARGUMENTS  # e.g., "rtl-p4-block-parallel"
max_cycles = 10

# Initialize ultraloop state
# last_cycle_timestamp: Unix epoch seconds (date +%s)
Write(".rat/state/ultraloop-state.json", json.dumps({
    "mode": "ultraloop",
    "target_skill": target_skill,
    "cycle": 0,
    "max_cycles": max_cycles,
    "frozen_hash": frozen_hash,
    "last_cycle_timestamp": int(time.time()),
    "auto_continue_minutes": 30
}))

for cycle in range(1, max_cycles + 1):
    print(f"=== Ultraloop Cycle {cycle}/{max_cycles} ===")

    # Update state
    ultraloop_state["cycle"] = cycle
    ultraloop_state["last_cycle_timestamp"] = int(time.time())  # Unix epoch seconds (date +%s)
    Write(".rat/state/ultraloop-state.json", json.dumps(ultraloop_state))

    # --- (a) Execute/continue target skill ---
    Skill(skill=f"rtl-agent-team:{target_skill}", prompt="--resume")

    # --- (b) Dispatch ultraloop-reviewer (READ-ONLY subagent) ---
    review_result = Task(
        subagent_type="rtl-agent-team:ultraloop-reviewer",
        description=f"Ultraloop review cycle {cycle}",
        prompt=f"Review cycle {cycle} of ultraloop targeting {target_skill}. "
               f"Assess RTL quality, contract test coverage, and design freeze integrity. "
               f"Read .rat/state/block-parallel-state.json for block status. "
               f"Read .rat/state/design-freeze.json for freeze hash. "
               f"Output structured review with per-block assessment and verdict."
    )

    # --- (c) Apply improvements from reviewer recommendations ---
    # Parse reviewer output for Priority 1 (Must Fix) items
    # Apply fixes to RTL code based on specific file:line recommendations
    # The SKILL applies changes — the reviewer is READ-ONLY
    if review_result.verdict == "IMPROVEMENTS_NEEDED":
        for recommendation in review_result.priority_1:
            # Apply each must-fix recommendation
            apply_improvement(recommendation)

    # --- (d) Run contract tests ---
    for block in active_blocks:
        Bash(f"cd sim/{block}/contract && make run_contract 2>&1")

    # --- (e) Freeze verification ---
    current_hash = Bash("find rtl/pkg/ rtl/intf/ docs/phase-3-uarch/ -name '*.sv' -o -name '*.md' 2>/dev/null | sort | xargs sha256sum 2>/dev/null | sha256sum | cut -d' ' -f1").strip()

    if current_hash != frozen_hash:
        # FAIL-CLOSED: stash violations, do not destructively revert
        Bash(f"git stash push -m 'freeze-violation-cycle-{cycle}'")
        print(f"FREEZE VIOLATION detected in cycle {cycle}. Changes stashed.")
        print("Halting ultraloop. User review required.")

        # Clean up ultraloop state so stop-gate.sh stops blocking
        Bash("rm -f .rat/state/ultraloop-state.json")
        generate_user_report(cycle, "FREEZE_VIOLATION")
        break

    # --- (f) Output cycle summary ---
    print(f"Cycle {cycle} complete. Verdict: {review_result.verdict}")

    # --- (g) Check auto-termination conditions ---
    # Condition 1: All blocks merged + contract tests PASS
    block_state = Read(".rat/state/block-parallel-state.json")
    all_merged = all(b["status"] == "merged" for b in block_state["blocks"].values())
    all_contracts_pass = all(b["contract_test_pass"] for b in block_state["blocks"].values())
    if all_merged and all_contracts_pass:
        print("All blocks merged and contract tests PASS. Ultraloop complete.")
        Bash("rm -f .rat/state/ultraloop-state.json")
        generate_user_report(cycle, "COMPLETE")
        break

    # Condition 2: Clean review (no improvements found)
    if review_result.verdict == "CLEAN":
        print("Clean review — no further improvements needed. Ultraloop complete.")
        Bash("rm -f .rat/state/ultraloop-state.json")
        generate_user_report(cycle, "CLEAN")
        break

    # Condition 3: Max cycles reached
    if cycle == max_cycles:
        print(f"Max cycles ({max_cycles}) reached. Saving state for manual review.")
        Bash("rm -f .rat/state/ultraloop-state.json")
        generate_user_report(cycle, "MAX_CYCLES")
        break

    # Condition 4: Token exhaustion imminent
    # (Detect via context window usage or explicit signal)
    if token_budget_low():
        Bash("rm -f .rat/state/ultraloop-state.json")
        generate_user_report(cycle, "TOKEN_EXHAUSTION")
        break

    # --- (h) Wait for user input (30-min auto-continue) ---
    # Leverages stop-gate.sh escalation pattern:
    # The ultraloop-state.json with auto_continue_minutes=30 signals
    # stop-gate.sh to auto-continue after 30 minutes of inactivity.
    # If user returns within 30 minutes, they can provide input or cancel.
```

## Auto-Termination Conditions

The loop terminates when any of these conditions is met:

1. **All blocks merged + contract tests PASS** -- target skill completed successfully
2. **Clean review** -- ultraloop-reviewer reports no improvements needed
3. **Max cycles reached** -- default 10 cycles, configurable via state
4. **Freeze violation** -- frozen artifacts modified, stash + halt (FAIL-CLOSED)
5. **Token exhaustion imminent** -- clean up ultraloop state, save progress, exit gracefully

On token exhaustion detection, the skill MUST remove `ultraloop-state.json` before exiting
to prevent `stop-gate.sh` from treating the next session as an active ultraloop:
```python
Bash("rm -f .rat/state/ultraloop-state.json")
generate_user_report(cycle, "TOKEN_EXHAUSTION")
```
If the session terminates abruptly without cleanup, `stop-gate.sh` will detect a stale
timestamp (elapsed > threshold) and allow normal stopping in the next session.

## State Persistence

Maintained at `.rat/state/ultraloop-state.json`:

```json
{
  "mode": "ultraloop",
  "target_skill": "rtl-p4-block-parallel",
  "cycle": 3,
  "max_cycles": 10,
  "frozen_hash": "sha256:deadbeef...",
  "last_cycle_timestamp": 1742064600,
  "auto_continue_minutes": 30
}
```

## User Return Report

Generated at `.rat/state/ultraloop-report.md` on loop completion or halt:

```markdown
# Ultraloop Execution Report

## Summary
- **Target skill**: rtl-p4-block-parallel
- **Cycles completed**: 3 / 10
- **Exit reason**: ALL_MERGED / CLEAN / MAX_CYCLES / FREEZE_VIOLATION / TOKEN_EXHAUSTION

## Block Status
| Block | Status | Lint | Unit Test | Contract Test |
|-------|--------|------|-----------|---------------|
| entropy | merged | PASS | PASS | PASS |
| tq | merged | PASS | PASS | PASS |
| me | implementing | PASS | FAIL | - |
| ... | ... | ... | ... | ... |

## Improvements Applied
- Cycle 1: Fixed entropy CABAC table indexing (rtl/entropy/entropy.sv:142)
- Cycle 2: Added missing backpressure handling in tq (rtl/tq/tq.sv:88)
- Cycle 3: No improvements needed

## Design Freeze Status
- **Status**: INTACT
- **Hash**: sha256:deadbeef...

## Pending Decisions
- me block unit test failure: SAD computation mismatch (needs user review)
```

## 30-Min Auto-Continue

The auto-continue mechanism leverages the existing `stop-gate.sh` escalation pattern:

1. The `ultraloop-state.json` file contains `auto_continue_minutes: 30`
2. When `stop-gate.sh` fires and detects ultraloop mode, it checks:
   - If `last_cycle_timestamp` + `auto_continue_minutes` > current time: auto-continue
   - If user has returned (interactive input detected): yield to user
3. This avoids idle sessions while allowing user override at any time
