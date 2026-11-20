# DSE policy

## Decisions

Treat functional correctness, interface compliance, timing/performance, and
area/power as the default priority order. Use the project's stated constraints
and priorities when selecting among feasible options.

Record the choice, evidence, and remaining uncertainty in the algorithm or
architecture ADR. When the evidence supports a choice with high confidence,
proceed. When an unresolved interpretation would change the architecture,
acceptance criteria, or verification plan, ask once about that concrete
trade-off and record the answer. Requirements without a measurable pass
condition remain open.

In `domain-analysis.md`, compare viable algorithms by the factors that affect
the decision, e.g. operations/input, memory bandwidth and access pattern,
parallelism, fixed-point precision, rounding, and quality or area impact.
For each feasible architecture in `architecture-candidates.md`, record its D2
block diagram, estimated area, critical path, latency, throughput and memory
bandwidth. Distinguish measurements from estimates.

## Phase gates and handoff

Record PASS or FAIL with evidence at each gate. Use existing reports when
their inputs are current. On PASS retain `docs/phase-{N}-*/phase-{N}-summary.md`
and consolidate review evidence before cleaning trial-local scratch.

| Gate | Required artifacts and evidence |
| --- | --- |
| P1 → P2 | P1 `iron-requirements.json` (REQ-F/P, measurable acceptance criteria), `open-requirements.json` (OPEN-1, candidates and evaluation criteria), `io_definition.json`, `timing_constraints.json`, `domain-analysis.md`, and algorithm ADR. The research review confirms requirement clarity, classification and RTL feasibility. |
| P2 → P3 | `architecture.md`, architecture candidates and selection ADR, `refc/*.c` and P2 `iron-requirements.json` (REQ-A with `resolved_from`). Each OPEN-1 item has a reasoned resolution. The architecture review passes, `reviews/phase-2-architecture/feature-coverage.md` maps 100% of requirements to blocks, and independent compliance against P1 passes. |
| P3 → critique | Per-module μArch specs, P3 `iron-requirements.json` (REQ-U with `resolved_from`), `clock-domain-map.md`, `protocol-assignments.md`, and a Phase 4 DPI bridge template. The μArch review passes, `req-uarch-traceability.md` covers 100% of requirements, independent compliance against P1/P2 passes, and no requirements remain open. C/SystemC BFM build and simulation agree with the reference model on shared inputs. |

For independent compliance, give `rtl-agent-team:compliance-checker` the
trial's upstream iron and downstream artifacts. Keep each report in that
trial's root. If evidence is missing, report the affected check as unverified.

### Reference model inputs

A transformed reference model uses C11, architecture-aligned block functions,
per-block context and external-memory read/write interfaces. Keep it clockless
and DPI-C compatible. Run identical vectors through both models and record
any bitexact divergence. For a codec trade-off that needs RD measurements or
decoder conformance, use `/rtl-agent-team:codec-rd-eval` or
`/rtl-agent-team:codec-conformance-eval` when the relevant inputs are available.

## Self-critique

Review the completed package once for missed requirements, architectural
bottlenecks, μArch feasibility, BFM test gaps and cross-phase contradictions.
Save HIGH/MEDIUM/LOW findings with their evidence in
`reviews/dse-self-critique.md`. A finding that invalidates a gate must appear
in the final verdict. End the trial after reporting its results. Only an
explicit request for an alternative starts another trial in the calling skill.
