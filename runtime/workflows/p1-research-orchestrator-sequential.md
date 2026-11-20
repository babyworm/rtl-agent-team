Produce a settled functional specification for Phase 2 from the supplied spec or
seed. Use spec-analyst for requirements; use goal-clarifier only for a material
unanswered question. A complete short spec is sufficient. Preserve explicit user
choices and cite the spec clause or supplied behavioral refC symbol/test that
establishes each observable behavior. Keep conflicting sources and their affected
expectations open. Research a normative reference or consult a domain
expert only for a concrete uncertainty; do not commission tutorials or alternatives
when the selected approach already fits.

Deliver docs/phase-1-research/{iron-requirements.json,open-requirements.json,
io_definition.json,timing_constraints.json,domain-analysis.md,feature-coverage.md,
spec-feature-inventory.json}. Empty open requirements are valid. Every feature
identified in the source must map to a requirement or an explicit scope decision;
compare the inventory with the final requirements once. Do not invent requirements
from general codec knowledge. Each acceptance criterion needs an observable result.

Review the assembled spec once with rtl-architect and any domain specialist needed
for an actual standards question. Save reviews/phase-1-research/research-review.md.
Record decisions and material ambiguities in judgment.json. An unresolved conflict
cannot become iron merely because an average score or confidence is high.
Produce the phase summary and ADRs for significant decisions, then report the
handoff gate and remaining open choices. Further design analysis belongs to P2.
