# Workflow-Driver Gate Model — Rule-5 Supersession Semantics

- Date: 2026-07-17
- Status: Documented decision (no code change — documentation only)
- Origin: `plugin_docs/specs/workflow-ultracode-compat.md` item 4, originally
  proposed-only and implemented in v0.14.0
- Validation: 2026-07-15 huffman_vld flow-test —
  `plugin_docs/plans/2026-07-15-vld-flowtest-design.md`

## 1. Context

Pipeline Rule 5 ("no completion after RTL modification without functional
verification") is the plugin's only **hard** gate. In as-shipped Claude Code
sessions it is enforced by the Stop hook `hooks/rtl-verify-stop-gate.sh`, which
blocks session stop until `.rat/state/rtl-verify-done` (or `rtl-verify-waiver`)
exists.

When an external **Workflow** driver (the ultracode "orchestrator-as-workflow"
model) owns phase/gate control flow in JS and calls plugin agents, the Stop hook
is not the operative enforcement point: the JS driver
decides when a phase is complete, and its per-phase gate functions run before
any completion is declared.

## 2. Decision

| Aspect | Decision |
|--------|----------|
| Rule-5 enforcement under a Workflow driver | **Functionally superseded** by JS gate logic (e.g., G5: bitexact vector comparison + randomized regression PASS + formal safety proof) |
| Semantic equivalence | The JS gate and the Stop hook enforce the same invariant — "RTL change ⇒ functional sim must pass before completion". Validated in the 2026-07-15 huffman_vld flow-test: all phases PASS, independently verified, and a separate Rule-5 hook sanity check confirmed native Stop-gate behavior (blocks without `rtl-verify-done`, passes with it) |
| `rtl-verify-stop-gate.sh` | **MUST NOT be modified.** As-shipped Claude Code sessions (no Workflow driver) still depend on the Stop hook as the sole hard enforcement of Rule 5. Supersession is a runtime property of the Workflow context, not a change to the plugin |
| Workflow-side sanity check | A Workflow driver **SHOULD retain a Rule-5 sanity check**: before declaring pipeline completion, verify `.rat/state/rtl-verify-done` exists (and postdates the last RTL edit), or rerun the functional simulation. This guards against a JS gate bug silently passing an unverified RTL change |

```mermaid
flowchart LR
    subgraph asShipped["As-shipped Claude Code session"]
        A[RTL edit] --> B[rtl-edit-tracker]
        B --> C{Stop hook:\nrtl-verify-stop-gate.sh}
        C -->|no rtl-verify-done| D[Block stop]
        C -->|rtl-verify-done| E[Session may stop]
    end
    subgraph wfDriven["Workflow-driven (ultracode)"]
        F[RTL edit via leaf agent] --> G{JS phase gate\nG5 Rule-5 equiv}
        G -->|FAIL| H[Loop back to P4]
        G -->|PASS| I[Rule-5 sanity check:\nrtl-verify-done or re-sim]
        I --> J[Declare completion]
    end
```

## 3. Preconditions (Workflow driver contract)

These are prerequisites for the supersession to be sound; without them the
driver operates on the wrong project root and neither gate model is trustworthy
(see `workflow-ultracode-compat.md` for full derivation):

1. **RAT-initialized root** — the selected project root must contain the `.rat`
   or legacy `.rtl-agent-team` marker.
2. **Project-root ladder** — provide the correct root through at least one source
   understood by every agent header: explicit `PROJECT_ROOT=<abs>` prompt line >
   spawn-context `project_root` > `$RAT_PROJECT_ROOT` > process CWD. Explicit
   prompt/environment roots must be absolute existing directories.
3. **Spawn-context propagation** — initialize the leader from the correct project
   root before dispatch. `hooks/lib/spawn-context-util.sh` then records
   `project_root`, so nested `Task()` spawns retain the same path contract.

## 4. Non-goals

- No change to `hooks/rtl-verify-stop-gate.sh` or any other Stop hook.
- No plugin-side detection of "Workflow-driven mode" — the supersession is
  entirely a property of the external driver, and the Stop hook remains active
  (and harmless) in the leader session if one exists.
- No relaxation of Rule 5 itself: both gate models enforce the identical
  invariant; only the enforcement point moves.
