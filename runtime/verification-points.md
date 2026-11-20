# Spec and refC simulation points

Select points before writing stimulus. Walk the in-scope requirements and acceptance
criteria against the original spec and observable refC behavior. Keep a point when
a distinct event, invariant or expected output could otherwise go unchecked.
Link each P3 simulation criterion by its exact `ac_id`. A `cocotb` or
`assertion` criterion needs its own outcome check. Use `test_method: coverpoint`
for a criterion whose entire obligation is reaching a specified event. Track
formal and inspection criteria in the existing traceability matrix.
No extra review round is needed for a settled point.

P3 writes `sim/verification-points.json`. Use a stable, project-unique ID per bin
or check and cite the REQ or structured AC. For example:

```json
{"points": [{
  "id": "clip.upper.compare", "kind": "scoreboard", "requirement": "REQ-F-002",
  "source": "spec §2.1 and refc/clip.c#clip_u8", "inputs": ["refc/clip.c"],
  "trigger": "an accepted input exceeds 255", "expected_result": "output equals 255",
  "confidence": "high", "basis": "The spec limit and the model's upper branch agree."
}]}
```

Use `high` when the source establishes why the behavior matters and fixes the
trigger and expected observation. Select a refC branch only for its observable
effect. Use `low` when sources disagree about scope, trigger or result.
Record what would decide it in `basis`; add `resolution` with the deciding
source or user decision before relying on it. A behavioral model can define
transaction values. Timing, reset and handshake assertions need a hardware contract.
The runner hashes local C sources cited in `source`. List other model files
and golden vectors used by the check in `inputs`. For an external refC, pin
the model actually used in `oracle_revision` (full commit ID or SHA-256).

## Recording a run

Use the configured simulation runner. Export the existing monitor or simulator
counters as one plain summary line per point per seed before the final verdict,
including zero counts. The records also work without a vendor coverage merger.

| Kind | Runtime record | What to count |
| --- | --- | --- |
| `coverpoint` | `RAT_COV_BIN <id> <hits> <minimum>` | Sampled occurrences of that bin. End the bin inventory with `RAT_COV_END <bin-count>`. |
| `assertion` | `RAT_CHECK_POINT <id> <completed> <failures>` | Enabled attempts whose antecedent fired and whose consequent was evaluated. |
| `scoreboard` | `RAT_CHECK_POINT <id> <completed> <failures>` | Actual RTL-to-oracle comparisons under the planned trigger. |

`minimum_hits` defaults to 1. Closure compares the current target with the raw
counts and counts each seed summary once. Any nonzero `failures` makes the
simulation fail, including runs that print a generic PASS.

Put the applicable runner IDs in `simulation_runs` in
`docs/phase-5-verify/judgment.json`. Bundled P5 invokes the comparison at handoff.
For split P5A, run `python3 {plugin_root}/scripts/gates/simulation_points.py --root <project>`.
Both read the recorded runtime logs. On older projects, update installed helpers
with `rat-init-project --update`. Reuse counts when their oracle and seed
boundaries can be verified. Rerun only the points missing that evidence.
