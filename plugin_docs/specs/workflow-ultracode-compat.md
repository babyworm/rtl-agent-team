# Workflow / ultracode Drivability Compatibility — Design & Findings

- Date: 2026-07-16
- Status: safe_edits applied; larger agent Step-0 parameterization proposed_only (NOT applied)
- Scope: `hooks/lib/rat-dir-util.sh`, `hooks/rtl-orchestrator-inject.sh`,
  `skills/rat-init-project/templates/{cocotb-makefile,Makefile}`,
  `skills/rat-init-project/SKILL.md`,
  `skills/rtl-p5s-func-verify/scripts/run_regression.sh`,
  `agents/func-verifier.md`, `tests/unit/test_hooks.py`

## Problem — CWD / project-root finding

An external **Workflow** driver (the "ultracode" orchestrator-as-workflow model) can
drive the plugin's phase pipeline by calling **leaf specialist agents** directly (JS owns
phase/gate control flow, native fan-out per phase, resumable/observable runs). The blocker
is a CWD mismatch:

- **Subagents default to the plugin repo CWD**, not the user's RTL project. Bare relative
  paths (`docs/`, `rtl/`, `sim/`, `reviews/`, `.rat/`) therefore resolve against the
  plugin source tree, not the project root. (Confirmed empirically via a CWD probe — see
  `plugin_docs/plans/2026-07-15-vld-flowtest-design.md` §3.)
- The plugin's **hooks** resolve the project root from the session CWD (via
  `hooks/lib/rat-dir-util.sh` `rat_is_project` / `rat_project_dir`, plus the standalone
  SessionStart hook `rtl-orchestrator-inject.sh`). When the driver's CWD is not the project
  root, gate/state/audit files land in the wrong place.

Two operational criteria gate "Workflow-drivable":

1. **Hooks resolve the right project root via an env override** — so a driver can point all
   hooks at the real root regardless of subagent CWD.
2. **Generated cocotb Makefiles work with a bare `make`** — so a JS driver that shells out
   `make -C sim/{module}` (no explicit target) actually runs the sim, not a no-op.

## What was applied (safe_edits)

All edits are backward-compatible supersets: with `RAT_PROJECT_ROOT` unset and no custom
per-module target, behavior is byte-identical to before.

| # | File | Change |
|---|------|--------|
| 1 | `skills/rat-init-project/templates/cocotb-makefile` | **Primary root fix.** `.DEFAULT_GOAL := sim` inserted after `TOPLEVEL_LANG = verilog`. This is the sole cocotb-Makefile producer (only `Makefile.sim` include). Makes bare `make` == `make sim` even when a custom `ref:`/DPI target is prepended above the include; propagates to every per-module Makefile adapted from this template. |
| 2 | `hooks/lib/rat-dir-util.sh` | **Env-root override.** `[ -d "${RAT_PROJECT_ROOT:-}" ] && set -- "$RAT_PROJECT_ROOT"` as the first body line of both `rat_is_project()` and `rat_project_dir()`. When `RAT_PROJECT_ROOT` is set **and is an existing directory**, it replaces the caller-supplied dir for the `.rat`/`.rtl-agent-team` marker check; unset, empty, **or not a directory** ⇒ falls back to the legacy CWD logic UNCHANGED. The return-1-if-no-marker existence contract is preserved (an overriding dir with no marker still fails). `set -u` safe (`${..:-}`) and `set -e` safe (AND-OR non-final exemption). Covers all sourcing hooks + `spawn-context-util` + `audit-util`. |
| 3 | `hooks/rtl-orchestrator-inject.sh` | The SessionStart hook does **not** source `rat-dir-util.sh` (stays dependency-free), so it carries its own guard: honor `RAT_PROJECT_ROOT` right after CWD resolution. Completes hook coverage. Unset ⇒ unchanged; JSON output re-validated. |
| 4 | `agents/func-verifier.md` | One-line note: generated per-module cocotb Makefiles MUST set `.DEFAULT_GOAL := sim` (or make custom `ref:`/DPI targets prerequisites of `sim`) so a bare `make` runs the sim. (The plan identified no dedicated per-module-Makefile *generator* agent/policy; the template is the sole producer — func-verifier is the fallback surface that writes Makefile targets.) |
| 5 | `skills/rat-init-project/templates/Makefile` | Defense-in-depth: `sim_regression` runs `$(MAKE) -C sim/$(TOP) sim` (explicit target) to avoid a silent RC=0 no-op if a per-module default goal is ever not `sim`. Top-level `.DEFAULT_GOAL := help` left untouched. |
| 6 | `skills/rtl-p5s-func-verify/scripts/run_regression.sh` | Defense-in-depth: `run_seed()` runs `make -C "$TB_DIR" sim SIM=...` (explicit target), same silent-pass hardening. |
| 7 | `skills/rat-init-project/SKILL.md` | Step 5 adapter note: per-module Makefiles MUST retain `.DEFAULT_GOAL := sim` or make helper targets (`ref`/DPI) prerequisites of `sim`, else bare `make` no-ops. |
| 8 | `tests/unit/test_hooks.py` | `TestRatDirUtil`: override honored when set (`rat_project_dir` + `rat_is_project`), override ignored when empty (legacy path), and existence contract preserved when `RAT_PROJECT_ROOT` points at a marker-less directory (returns 1). |

Note on this task's narrowed scope: items 1 (`.DEFAULT_GOAL`), the env override in
`rat-dir-util.sh`, and the func-verifier note were the deliverables re-verified/applied
here. The `rat-dir-util.sh` guard was tightened from the earlier `[ -n ... ]` (non-empty)
to `[ -d ... ]` (existing directory), so a non-directory `RAT_PROJECT_ROOT` now falls back
to the legacy logic unchanged rather than forcing a resolution failure — a strict superset
that still passes all four `TestRatDirUtil` env-override tests (they all point the env at
real directories).

## Drivability verdict

**`ultracode_workflow_ready: true`** — the two operational criteria are met:

1. Hooks resolve the right project root via `RAT_PROJECT_ROOT` (covers the sourcing
   gate/state/audit hooks + the standalone SessionStart injector). Unset ⇒ byte-identical.
2. Generated cocotb Makefiles run under a bare `make` (`.DEFAULT_GOAL := sim`), verified
   against GNU make even with a prepended `ref:`/DPI target.

**Residual (Workflow-side, NOT a plugin defect):** the env override redirects **hooks**
(and, if adopted, EDA runners) but does **not** redirect a leaf agent's own Read/Write/Edit
file I/O — those still resolve bare relative paths against the subagent process CWD (the
plugin repo by default). Therefore the external Workflow MUST additionally:

- set each **leaf agent's CWD** to the project root, and/or
- inject an absolute `PROJECT_ROOT=<abs>` line into each **leaf-agent** prompt.

Recommendation (from the flow-test): drive **leaf specialist agents** directly rather than
multi-level orchestrators, so nested `Task()` spawns cannot silently drop the
`PROJECT_ROOT` contract.

**Preconditions:** the target project must be RAT-initialized (`.rat` marker present) or the
env override falls back to `$CWD/.rat`; and `RAT_PROJECT_ROOT` must be an absolute path to an
existing directory.

## Proposed-only (future plan — NOT applied)

The durable fix for agent-side I/O is a schema change + mass edit, intentionally excluded
from the safe_edits set. Track as a future plan.
(Per-item status as of 2026-07-17: all 5 items APPLIED — see each item's status tag.)

1. **[APPLIED 2026-07-17 (this change set)]**
   **Agent Step-0 / path-convention parameterization (the robust half).** Extend the shared
   "Path convention" header line across all 99 agents + `agents/lib/step0-template.md` + the
   33 orchestrator Step-0 blocks to resolve project-relative paths against `project_root`
   (from `.rat/state/spawn-context.json`) OR the `RAT_PROJECT_ROOT` env OR an explicit
   `PROJECT_ROOT=<abs>` prompt line, falling back to process CWD (legacy). Scriptable via
   `sed` (uniform header), but a mass edit across orchestrators — **excluded** from
   safe_edits by task rule. Recommended driver target: leaf specialists, not orchestrators.

2. **[APPLIED 2026-07-17 (this change set)]**
   **Ship `project_root` in the spawn-context manifest.** Mirror the existing `plugin_root`
   pattern: `SCTX_PROJECT_ROOT="${RAT_PROJECT_ROOT:-$SCTX_CWD}"` in
   `hooks/lib/spawn-context-util.sh`, emit `"project_root":"..."` in the manifest, and honor
   `CWD="${RAT_PROJECT_ROOT:-$CWD}"` in `rtl-spawn-context.sh` / `rtl-phase-state-bootstrap.sh`.
   This is a manifest **schema change** requiring a 4-way test update
   (`test_hooks.py`, `test_plugin_runtime_contract.py`, `test_agent_skill_structure.py`,
   `test_audit.py`) — hence proposed-only.

3. **[APPLIED 2026-07-17 (this change set)]**
   **`PROJECT_ROOT` in deployed EDA templates.** Change each `PROJECT_ROOT="$(pwd)"` to
   `PROJECT_ROOT="${RAT_PROJECT_ROOT:-$(pwd)}"` in `scripts/run_sim.sh` and the deployed
   `run_lint.sh` / `run_syn.sh` / `run_cdc.sh` / `run_conformal.sh` / `run_formality.sh` /
   `run_regression_uvm.sh`. Backward-compatible, but touches user-deployed templates and only
   matters when subagent CWD != project root; roll out with the prompt contract above.

4. **[APPLIED 2026-07-17 → see `workflow-driver-gate-model.md`]**
   **Workflow-driver gate model (document only).** When an external Workflow owns phase/gate
   control flow in JS, the Rule-5 hard Stop-gate is superseded by JS gate logic, with a
   separate Rule-5 sanity check retained. Do **not** modify `rtl-verify-stop-gate.sh` —
   as-shipped Claude Code sessions still depend on the Stop gate for Rule 5.

5. **[APPLIED 2026-07-17 (this change set)]**
   **Cosmetic `make sim` in docs (optional).** Switch documented `make -C sim/{module} ...`
   invocations to `make sim ...` across ~15 agent/policy/guide surfaces. Redundant once the
   `.DEFAULT_GOAL := sim` template fix is in place; purely for guidance consistency.
