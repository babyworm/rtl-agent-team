# Workflow / ultracode Drivability Compatibility — Design & Findings

- Date: 2026-07-16
- Status: Implemented — initial safe edits shipped in v0.13.0; all five follow-up
  items shipped in v0.14.0
- Scope: hook and agent project-root resolution, spawn-context propagation, EDA
  runners, Makefile default goals, and the Workflow-driver gate contract

> **Historical boundary:** The original problem and initial-safe-edit sections below
> describe the v0.13.0 state. The current v0.14.0 contract is recorded in
> "Drivability verdict" and "Applied follow-up work."

## Original problem — CWD / project-root finding

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

**Current agent-side contract:** all agent headers resolve project-relative paths through
the same ladder: explicit `PROJECT_ROOT=<abs>` prompt line > spawn-context `project_root`
> `$RAT_PROJECT_ROOT` > process CWD. The spawn-context manifest now carries
`project_root`, so nested orchestrator spawns preserve the project location. Direct leaf
targeting remains a latency/observability recommendation, not a path-correctness
requirement.

**Preconditions:** the target project must be RAT-initialized (`.rat` or legacy
`.rtl-agent-team` marker present), and at least one project-root source in the ladder must
point to that project. Explicit prompt/environment roots must be absolute existing
directories.

## Applied follow-up work (v0.14.0)

The five items originally proposed after the v0.13.0 safe edits are now implemented:

1. **[APPLIED 2026-07-17 (this change set)]**
   **Agent Step-0 / path-convention parameterization (the robust half).** Extend the shared
   "Path convention" header line across all 99 agents + `agents/lib/step0-template.md` + the
   30 canonical orchestrator Step-0 blocks plus the three custom orchestrator path
   headers to resolve project-relative paths against `project_root`
   (from `.rat/state/spawn-context.json`) OR the `RAT_PROJECT_ROOT` env OR an explicit
   `PROJECT_ROOT=<abs>` prompt line, falling back to process CWD (legacy). The canonical
   Step-0 blocks are synchronized from `agents/lib/step0-template.md`.

2. **[APPLIED 2026-07-17 (this change set)]**
   **Ship `project_root` in the spawn-context manifest.** Mirror the existing `plugin_root`
   pattern: `SCTX_PROJECT_ROOT="${RAT_PROJECT_ROOT:-$SCTX_CWD}"` in
   `hooks/lib/spawn-context-util.sh`, emit `"project_root":"..."` in the manifest, and honor
   `CWD="${RAT_PROJECT_ROOT:-$CWD}"` in `rtl-spawn-context.sh` / `rtl-phase-state-bootstrap.sh`.
   This is a manifest **schema change** requiring a 4-way test update
   (`test_hooks.py`, `test_plugin_runtime_contract.py`, `test_agent_skill_structure.py`,
   `test_audit.py`).

3. **[APPLIED 2026-07-17 (this change set)]**
   **`PROJECT_ROOT` in deployed EDA templates.** Change each `PROJECT_ROOT="$(pwd)"` to
   `PROJECT_ROOT="${RAT_PROJECT_ROOT:-$(pwd)}"` in `scripts/run_sim.sh` and the deployed
   `run_lint.sh` / `run_syn.sh` / `run_cdc.sh` / `run_conformal.sh` / `run_formality.sh` /
   `run_regression_uvm.sh`. Backward-compatible, but touches user-deployed templates and only
   matters when subagent CWD != project root; it uses the same root contract above.

4. **[APPLIED 2026-07-17 → see `workflow-driver-gate-model.md`]**
   **Workflow-driver gate model (document only).** When an external Workflow owns phase/gate
   control flow in JS, the Rule-5 hard Stop-gate is superseded by JS gate logic, with a
   separate Rule-5 sanity check retained. Do **not** modify `rtl-verify-stop-gate.sh` —
   as-shipped Claude Code sessions still depend on the Stop gate for Rule 5.

5. **[APPLIED 2026-07-17 (this change set)]**
   **Explicit simulation target in executable helpers.** Documentation commands retained `make -C sim/{module}`.
   The top-level `sim_regression` target and regression
   runner added an explicit `sim` target so automation cannot silently select a helper goal.
