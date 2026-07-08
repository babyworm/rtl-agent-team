---
name: rtl-p7-exploration-policy
description: "Internal reference: rtl p7 exploration policy (agent-loaded; do not invoke)."
user-invocable: false
---

# Phase 7 Exploration Policy

## Why Phase 7 Exists

Phases 1-6 enforce strict pipeline gates for production quality. Phase 7 provides a
**safe sandbox** for investigating alternatives without production risk:
- Algorithm alternatives that may improve area/performance/power
- Optimization experiments on existing modules
- Technology evaluation (new tools, methodologies, IP blocks)
- "What-if" scenarios from Phase 6 design review findings

## Exemptions

Phase 7 is **exempt from all pipeline rules** (Rule 9):
- No Phase 5 PASS requirement
- No Phase 6 completion requirement
- No verification gate enforcement
- No cascading quality enforcement

## Guard Rails

Despite exemptions, guard rails prevent accidental production impact:

| Rule | Rationale |
|------|-----------|
| Existing `rtl/` files must NOT be directly modified | Protect production RTL |
| Use exploration branch for any code experiments | Isolation from main branch |
| Results stored in `docs/phase-7-exploration/` | Separate from production docs |
| No verification bypass for production code | Exploration cannot weaken existing quality |
| No feature additions without spec change proposal | Changes must flow through pipeline |

## Scope

**Allowed**:
- Algorithm alternatives analysis and comparison
- Optimization experiments (area, power, timing trade-offs)
- Technology evaluation (new EDA tools, IP blocks, methodologies)
- Prototype implementations in exploration branch
- Performance modeling and estimation

**Prohibited**:
- Direct modification of production RTL files
- Verification bypass for production modules
- Feature additions without formal spec change
- Modifying pipeline state or phase gate artifacts

## ADR Workflow

Successful exploration produces an Architecture Decision Record:
- Location: `docs/decisions/ADR-{NNN}.md`
- Content: Context, Decision, Alternatives, Consequences
- Integration proposal: How to formally bring exploration results into the pipeline
- Required phase: Which pipeline phase must be re-entered for formal integration

### Structured Re-entry Metadata (MANDATORY in ADR)

Every ADR from Phase 7 must include a YAML frontmatter block for pipeline re-entry:

```yaml
---
adr_id: ADR-{NNN}
status: accepted | proposed | superseded
affected_phases: [P1, P2]        # Which phases need re-work if this ADR is adopted
stale_artifacts:                  # Specific docs that become stale
  - docs/phase-1-research/requirements.json
  - docs/phase-2-architecture/architecture.md
re_entry_point: P1               # Recommended phase to re-enter
re_entry_skill: p1-spec-research # Skill to invoke for re-entry
impact_summary: "New algorithm requires spec update + architecture re-partition"
---
```

**How this integrates with existing pipeline:**
- Orchestrators already check upstream artifact mtimes in Step 0 (E1 entry gate)
- When an ADR is adopted and upstream docs are updated, downstream orchestrators
  will detect mtime staleness and flag affected sections for targeted re-design
- No rat-setup modification needed — existing staleness detection handles re-entry naturally

## Output Artifacts

| Artifact | Location | Content |
|----------|----------|---------|
| Exploration notes | `docs/phase-7-exploration/exploration-notes.md` | Detailed findings, data, analysis |
| Exploration review | `reviews/phase-7-exploration/exploration-review.md` | Summary, conclusions, recommendations |
| ADR (if successful) | `docs/decisions/ADR-{NNN}.md` | Formal decision record with integration proposal |

## Escalation

- Exploration reveals production RTL bug → file via `rtl-p4s-bugfix`, do NOT fix in exploration branch
- Exploration requires spec change → propose via `p1-spec-research`, do NOT modify spec directly
- Exploration scope exceeds single session → document partial results, resume later
