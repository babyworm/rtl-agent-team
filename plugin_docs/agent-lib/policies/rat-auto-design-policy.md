# RTL Auto-Design Policy

## Handoff evidence

The phase owner applies its gate and returns the verdict, artifacts and open
issues. The pipeline checks both the artifact gate in `phase-registry.json`
and the phase's quality evidence. A structural PASS cannot prove behavior.
Preserve functional requirements before interface, timing/performance and
area/power preferences. A conflict with an accepted upstream specification
requires a user decision on the requirement or design.

| Phase | Evidence for the handoff |
| --- | --- |
| P1 research | Settled iron requirements, deferred opens, I/O and constraints, feature coverage, and review for contradictions or implementation ambiguity. |
| P2 architecture | Architecture and REQ-A traceability to P1, bandwidth assumptions, architecture review and functional comparison of the C reference model. |
| P3 microarchitecture | Module specs, REQ-U traceability and resolved opens. The BFM builds, matches the reference C model on shared inputs and records required interface/performance observations. |
| P4 implementation | Lint, synthesizability, reference-checked functional unit simulation for changed RTL, and integration evidence. Retain Stream B SVA, CDC and TB artifacts for P5 with the applicable scope. |
| P5 verification | Applicable measurement reports, requirement and end-to-end traceability, and `reviews/phase-5-verify/final-compliance.md` with an explicit PASS before P6. |
| P6 review | Passing code and design reviews plus the design note and improvements document under `reviews/phase-6-review/`. |

Keep phase summaries and significant architecture decisions in their existing
paths. Use the phase owner's configured thresholds, requirement identifiers and
reference model. An out-of-scope check needs a reason in the evidence. Record
confidence for judgments, and ask once when a material ambiguity changes
behavior, interfaces, constraints or the expected verification result.

## Measured repairs and user decisions

For a missing artifact, produce the missing result. For a failed measurement,
repair the identified defect and rerun only affected checks. Within a single
gate the budget is **two failed measured repairs**. The original failure
identifies the defect. Increment `orchestration_control.active_gate_primary_attempts`
when the attempted repair still fails. Do not repeat a successful review or
schedule another review to raise confidence.

At the limit set `orchestration_control.needs_user_decision=true` and record the
failure, attempted repair, measured result and requested decision. For a known
upper-spec violation, set `upper_spec_blocking=true` and ask immediately.
Resume after the user resolves the outstanding decision. Clear the corresponding
decision flag and retain the evidence in the gate record. Preserve active counters
for an unfinished gate. Reset them on transition to a new gate or after a user
decision authorizes another repair. For old state the Stop hook counts primary
plus fallback attempts toward the same limit. Retain that history. Legacy strategy and last-chance fields never schedule work.

For P5 feedback, route a module defect (`UNIT_FIX`) to the affected P4 module;
rerun its lint and functional simulation after changing RTL. Recheck shared
interfaces and integration for an `INTEGRATION_FIX`. A `DESIGN_FIX` requires
the upstream decision before implementation resumes. Record the affected
subphase, defect and outcome in the existing fix history. A child phase's
failed repair counts toward its gate budget when the pipeline resumes.
