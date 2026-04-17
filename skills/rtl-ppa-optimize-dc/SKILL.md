---
name: rtl-ppa-optimize-dc
description: "One-shot Design Compiler–based PPA optimization iteration. Runs DC synthesis, parses reports into JSON, generates RTL patch, validates scope, verifies equivalence + smoke, computes delta, and emits convergence verdict. Requires Phase 5 PASS and dc_shell/genus in PATH."
user-invocable: true
argument-hint: "[top-module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, Skill
---

<Purpose>
Execute ONE iteration of the DC-based PPA optimization loop against a verified
RTL design. Produces `docs/ppa-opt/iter-{N}/` with the synthesis reports, RTL
patch, equivalence/smoke evidence, and a convergence verdict. For automated
iteration until convergence, use `rat-ultraloop-ppa` instead.
</Purpose>

<Use_When>
- User says "PPA optimize", "DC PPA", "power/timing/area optimize"
- A single exploratory PPA iteration is desired
- Debugging the PPA loop mechanics without auto-continue
</Use_When>

<Do_Not_Use_When>
- Phase 5 verification has not passed (use rtl-p5-verify first)
- No `dc_shell` nor `genus` available (this skill hard-fails)
- Full automatic iteration is wanted (use `rat-ultraloop-ppa`)
- RTL still under active development (finish Phase 4 first)
</Do_Not_Use_When>

## Prerequisites

- `reviews/phase-5-verify/final-compliance.md` verdict=PASS (soft advisory —
  warns and proceeds if absent)
- `dc_shell` OR `genus` in PATH (HARD — fail on absence)
- `requirements.json["ppa_targets"]` populated (HARD — writeback scaffold and halt)
- Git working tree clean under `allowed_edit_scope` (no uncommitted changes AND no
  untracked files in `rtl/${PPA_TOP}` — untracked files would be silently deleted by
  rollback `git clean -fd`)
- `syn/scripts/run_syn.sh` deployed by `rat-init-project`

## Invocation

```
/rtl-agent-team:rtl-ppa-optimize-dc [top_module]
```

When `top_module` is omitted, reads from `requirements.json["top_module"]`.

## Execution

```
# Step 1: Bootstrap ppa-loop-state.json if absent
if not exists(".rat/state/ppa-loop-state.json"):
    Write(".rat/state/ppa-loop-state.json", initial_state(
        target_module=ARGUMENTS or requirements.top_module,
        max_cycles=requirements.ppa_targets.convergence.max_cycles or 4
    ))

# Step 2: Check preconditions (fail fast)

# Validate PPA_TOP: must be a non-empty, strict SV identifier
PPA_TOP="${ARGUMENTS:-$(python3 -c 'import json; print(json.load(open("requirements.json"))["top_module"])' 2>/dev/null)}"

if [ -z "${PPA_TOP}" ]; then
    echo "ERROR: PPA_TOP must be provided via argument or requirements.json['top_module']" >&2
    exit 1
fi

# Reject any PPA_TOP that is not a plain identifier — prevents shell injection
# and the 'empty scope wipes rtl/' footgun when PPA_TOP expansion defaults.
case "${PPA_TOP}" in
    *[!A-Za-z0-9_]*|[!A-Za-z_]*)
        echo "ERROR: PPA_TOP='${PPA_TOP}' must match [A-Za-z_][A-Za-z0-9_]* (no shell metachars, no path segments)" >&2
        exit 1
        ;;
esac

# Validate PPA_LIBERTY and PPA_SDC paths — reject shell metachars, must be existing regular files
for _var in PPA_LIBERTY PPA_SDC; do
    _val=$(eval "printf '%s' \"\${$_var:-}\"")
    if [ -z "${_val}" ]; then
        continue   # unset is OK; orchestrator checks specifics later
    fi
    case "${_val}" in
        *[\`\$\;\&\|\<\>\"\'\ ]*)
            echo "ERROR: ${_var}='${_val}' contains unsafe shell characters" >&2
            exit 1
            ;;
    esac
    if [ ! -f "${_val}" ]; then
        echo "ERROR: ${_var}='${_val}' is not a regular file" >&2
        exit 1
    fi
done

assert shutil_which("dc_shell") or shutil_which("genus"), \
    "Commercial synthesis (dc_shell or genus) required"

# Hard precondition: no uncommitted changes AND no untracked files in allowed_edit_scope
if [ -n "$(git status --porcelain -- rtl/${PPA_TOP})" ]; then
    echo "ERROR: working tree must be clean under rtl/${PPA_TOP} (commit or stash first)" >&2
    exit 1
fi
# Note: Untracked files within `rtl/${PPA_TOP}` MUST be committed or removed before
# starting — otherwise rollback `git clean -fd` would delete them silently.

# Step 3: Advance cycle counter
state.cycle += 1
Write(".rat/state/ppa-loop-state.json", state)

# Step 4: Dispatch orchestrator (it writes Rule 5 marker unconditionally on convergence)
Task(subagent_type="rtl-agent-team:ppa-optimizer-dc-orchestrator",
     description=f"PPA iteration {state.cycle}",
     prompt="Execute one PPA optimization iteration. Read .rat/state/ppa-loop-state.json for scope and history.")
```

Do not perform per-iteration work directly. The orchestrator handles all
synthesis / parsing / patching / equivalence / convergence.

## Completion

The skill reports the verdict returned by the orchestrator. If verdict is
`CONVERGED_STREAK` or `CONVERGED_TARGETS`:
- Write `.rat/state/rtl-verify-done` (Rule 5 satisfaction marker — orchestrator
  also writes this idempotently; both writes are safe)
- Recommend running `rtl-p5-verify` for full regression confirmation

NOTE: The one-shot skill does NOT emit `ppa-opt-done`. To declare true
convergence (and trigger Phase 6 cascade re-review), use `rat-ultraloop-ppa`
which runs the mandatory final `/rtl-agent-team:rtl-p5-verify --mode=final
--source=ppa-opt` regression before writing `ppa-opt-done`.

Otherwise, the skill returns the verdict and exits. For `CONTINUE`, the user
invokes again or switches to `rat-ultraloop-ppa`.
