Implement the requested modules against Phase 3 microarchitecture and all upstream
iron requirements. Use the preloaded SystemVerilog convention where applicable.
Plan work from real module dependencies, not a prescribed number of waves. Use
rtl-coder for independent module work; preserve disjoint outputs when delegating.
Use the P3 point IDs in unit tests and module test plans. A test-plan-writer
may refine stimulus or propose a missing point. The phase owner integrates agreed
additions into `sim/verification-points.json` before running affected tests,
following `{plugin_root}/runtime/verification-points.md`. Use the upstream oracle.

For each changed module, run the configured lint wrapper and a functional unit
simulation against the reference model. scripts/run_sim.sh and the regression
runners record source-bound evidence; a marker or zero-check TB cannot pass.
Unit results under sim/**/*_unit_results.json include traced REQ/ac_ids, mismatch
counts, coverage and functional-coverage results. Follow the configured targets;
retest only affected behavior after an edit. A refactor additionally needs
behavioral equivalence. Use equivalence-checker when that measured comparison is
needed, rather than performing an unrelated second review.

Produce RTL/filelists and docs/phase-4-rtl/ module documentation. Stream B early
artifacts are stream-b-sva-skeletons.md, stream-b-cdc-preliminary.md, and
stream-b-tb-skeletons.md. Record not-applicable scope explicitly, not fake PASS.
Run synthesis/CDC/protocol checks required by the design and distinguish structural
checks from measured signoff. Keep library prerequisites and report unmapped
estimates as such. Review implementation once, repair concrete findings, then
handoff after unit tests and upstream compliance pass. RTL edits always require
functional verification, including edits made during review.
