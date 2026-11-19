Close verification from settled acceptance criteria and the P4 unit results.
Choose applicable checks by actual behavior, interfaces, clocks and constraints.
For each selected item, record its requirement/ac_id, stimulus/observation,
expected result and measurement. Unclear latency, tolerance or legal-input bounds
remain open questions; a PASS under an invented threshold does not settle them.

Stage 1 covers per-module lint, functional regression, coverage and any applicable
formal, CDC, protocol, performance and synthesis checks. Respect dependencies:
formal needs passing lint; a bus or clock-domain check needs that interface/domain
to exist. Stage 2 covers top-level flow, integration tests and system results.
Stage 3 consolidates requirement traceability and final compliance. Select the
configured simulator/framework, not a second toolchain. Full concurrent SVA is
commercial-formal only; OSS SBY uses sv2v on DUT RTL plus a compatible harness.
No proof timeout or structural CDC scan is signoff evidence.

Save reports under reviews/phase-5-verify/ and machine-readable simulation results
under sim/. Maintain docs/phase-5-verify/verification-tracker.json and judgment.json.
Raw and post-exclusion coverage use configured targets, with default line 90%,
toggle 80%, FSM 70%, branch 80%, functional 95%. Non-standard exclusions require a
user decision bound to the current exclusion fingerprint. Critical/High untested
or PARTIAL acceptance criteria block final closure; NOT_VERIFIABLE items need an
explicit reason rather than fabricated tests. Record req-to-test and e2e traceability.

Repair the concrete failed scope, then rerun affected checks. RTL_FIX returns to
P4 bugfix, UARCH_FIX to P3, INTEGRATION_FIX handles cross-module behavior. At most
two P5-to-P4 failed feedback cycles precede escalation. Do not repeat successful
reviews, seeds, formal tasks or coverage passes merely to raise confidence.
Write reviews/phase-5-verify/final-compliance.md with one `Verdict: PASS` or
`Verdict: FAIL` field and the measured scope.
P5A functional closure and P5B silicon validation remain separate capabilities.
