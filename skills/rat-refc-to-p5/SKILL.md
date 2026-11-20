---
name: rat-refc-to-p5
description: "Implement hardware from an existing behavioral C reference model and run Phase 5 verification. Use for 'refc to RTL', 'C model to hardware', or 'refc to P5'."
user-invocable: true
argument-hint: "<C source file or model directory> [hardware constraints] [--resume]"
allowed-tools: Bash, Read, Write, Edit, Grep, Glob, Skill, Task, AskUserQuestion
---

Use the supplied behavioral C model as the functional reference for RTL
implementation. Stop after Phase 5. Follow the host dispatch instructions in
`{plugin_root}/runtime/model-selection.md`.

Resolve the supplied file or directory relative to the RTL project. Keep the
original model intact. Run `rat-init-project` first if the target project is
uninitialized. Record its location, revision or source digest, and the
build/run command used for verification. Run an existing model test or capture
expected outputs on representative inputs before using the model as an oracle.
If the model cannot be run, stop before P2 handoff and report the missing
dependency or test interface.

| Phase | Action skill | Handoff |
| --- | --- | --- |
| P1 | `p1-spec-research` | Derive observable behavior, input/output domains, state and acceptance examples from the model and its tests. Ask once for missing hardware constraints that affect the design or for behavior the model leaves ambiguous. |
| P2 | `p2-arch-design` | Design the hardware architecture and runnable `refc/` handoff. Reuse or wrap the supplied model where practical. Compare RTL-oriented adaptations against the unchanged original on shared vectors and the specified comparison criteria. |
| P3 | `rtl-p3-uarch-design` | Define the microarchitecture, validate the BFM against the accepted reference and select simulation points from spec clauses and observable refC behavior. |
| P4 | `rtl-p4-implement` | Implement RTL and obtain passing lint and functional unit-test evidence. |
| P5 | `rtl-p5-verify` | Verify the implemented design against the original oracle or its validated adapter. Reconcile the planned points with simulation evidence and record the final compliance verdict. |

Pass the original model path, confirmed constraints and applicable golden
vectors to each phase. Treat the model as evidence for functionality. Derive
interface, latency, throughput, reset, and numeric comparison requirements from
the supplied constraints or settle them with the user where needed.

Use each phase owner's measured results and
`{plugin_root}/scripts/gates/phase_gate.py --root <project> --phase <number>`
before advancing. Follow `{plugin_root}/runtime/phase-dispatch.md` for optional
Codex cross-review. Record the model identity, review scope and current
handoffs in `.rat/state/rat-refc-to-p5-state.json`. Set `status` to `in_progress`
and `current_skill` to the phase skill before dispatch. When the pipeline needs
a user decision, set `orchestration_control.needs_user_decision` to true before
asking and clear it when the answer arrives. Set `status` to `completed`
after the P5 gate passes. On resume, reuse evidence
only when its inputs still match. A changed model or hardware constraint
invalidates affected downstream evidence. After P5, report
`reviews/phase-5-verify/final-compliance.md`, the measured RTL comparison, and
any open or failed checks.
