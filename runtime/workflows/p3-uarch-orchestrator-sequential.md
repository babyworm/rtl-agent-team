Map the accepted P2 architecture and reference model into implementable per-module
microarchitecture. Use uarch-designer and bfm-dev for distinct design/model outputs.
Specify interfaces, datapath widths, state transitions, clocks/resets, memory
latencies and storage allocation only to the detail needed to implement and test
this design. Carry REQ-A-* and REQ-F/P-* traceability into REQ-U-*.
Before stimulus, the phase owner writes the shared `sim/verification-points.json`
from the spec, supplied refC/tests and settled hardware constraints. Follow
`{plugin_root}/runtime/verification-points.md` for selection, extraction confidence
and evidence. Preserve point IDs when resuming.

Deliver docs/phase-3-uarch/{<module>.md,iron-requirements.json,
open-requirements.json,clock-domain-map.md,protocol-assignments.md,judgment.json},
BFM sources under bfm/, and a single uarch review under reviews/phase-3-uarch/.
G4a is BFM build success. G4b is output comparison against the P2 refC on shared
vectors (bitexact or an explicitly specified tolerance). G4c is the required
interface/performance observation log. All three need actual results. A compiled
BFM with wrong outputs fails. Diagnose the failing refC/BFM scope and repair it;
a max of two failed repair cycles permits escalation, not two mandatory cycles.

Resolve remaining OPEN-2-* items before RTL handoff. Write an empty open list when
none remain; no further phase-specific open file is introduced. Record user decisions
for genuinely unresolved material choices rather than selecting by average score.
Perform compliance against P1/P2 iron, one microarchitecture review, phase summary
and significant ADRs.
