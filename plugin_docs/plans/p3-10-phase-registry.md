# P3-10: Single Source Phase Metadata Registry

## Problem

Three independent shell case statements encode the same skill→phase relationship:

1. **Phase mapper** (`hooks/lib/spawn-context-util.sh:16-30`) — 33 skills → phase number
2. **Compliance bootstrap** (`hooks/rtl-phase-state-bootstrap.sh:47-60`) — 14 primary skills → iron paths
3. **Artifact map** (`hooks/lib/artifact-map.sh:8-99`) — phase number → artifact paths

Plus two related maps:
4. **Agent→skill** (`hooks/rtl-spawn-context.sh:35-74`) — 33 agents → skill names
5. **Completion criteria** (`skill-completion-criteria.json`) — 29 skills → criteria strings

All five must be kept in sync manually. v0.7.6 and v0.7.7 each shipped drift bugs.

## Solution

Create `phase-registry.json` as the **single source of truth**, then generate derived shell code.

### Registry Schema

```json
{
  "_schema_version": "1.0",
  "skills": {
    "p1-spec-research": {
      "phase": 1,
      "primary": true,
      "iron_upstream": [],
      "open_requirements": "",
      "completion_criteria": "spec-analysis-complete|review-rounds-done|artifacts-written|iron-open-classified|ambiguity-pass"
    },
    "p2-arch-design": {
      "phase": 2,
      "primary": true,
      "iron_upstream": ["docs/phase-1-research/iron-requirements.json"],
      "open_requirements": "docs/phase-1-research/open-requirements.json",
      "completion_criteria": "arch-review-complete|ref-model-built|artifacts-written|open-resolved|compliance-pass|ambiguity-pass"
    },
    "rtl-p4s-bugfix": {
      "phase": 4,
      "primary": false,
      "completion_criteria": "fix-applied|lint-pass|test-pass"
    }
  },
  "agents": {
    "p1-research-orchestrator": "p1-spec-research",
    "p2-arch-orchestrator": "p2-arch-design",
    "p4-block-parallel-coordinator": "rtl-p4-block-parallel"
  },
  "phases": {
    "1": {
      "required": [{"path": "specs", "role": "spec-documents"}],
      "optional": []
    },
    "2": {
      "required": [
        {"path": "docs/phase-1-research/iron-requirements.json", "role": "p1-iron-requirements"},
        {"path": "docs/phase-1-research/io_definition.json", "role": "p1-io-definition"},
        {"path": "docs/phase-1-research/domain-analysis.md", "role": "p1-domain-analysis"},
        {"path": "docs/phase-1-research/timing_constraints.json", "role": "p1-timing-constraints"}
      ],
      "optional": [
        {"path": "docs/phase-1-research/open-requirements.json", "role": "p1-open-requirements"}
      ]
    }
  }
}
```

### Generation Script: `scripts/generate-phase-maps.sh`

Reads `phase-registry.json` and produces:

| Output | Method |
|--------|--------|
| `hooks/lib/spawn-context-util.sh` partial | Replace `sctx_skill_to_phase()` between markers |
| `hooks/rtl-phase-state-bootstrap.sh` partial | Replace compliance case between markers |
| `hooks/rtl-spawn-context.sh` partial | Replace agent→skill case between markers |
| `hooks/lib/artifact-map.sh` full | Regenerate `artmap_required`/`artmap_optional` |
| `skill-completion-criteria.json` full | Regenerate from registry |

Each target file gets `# BEGIN GENERATED` / `# END GENERATED` markers (same pattern as `rtl-orchestrator-inject.sh`).

### Implementation Steps

1. **Add markers to 4 target files** (non-breaking, code-preserving)
   - `spawn-context-util.sh`: wrap `sctx_skill_to_phase()` in markers
   - `rtl-phase-state-bootstrap.sh`: wrap compliance case in markers
   - `rtl-spawn-context.sh`: wrap agent mapping case in markers
   - `artifact-map.sh`: wrap full functions in markers

2. **Create `phase-registry.json`** from current shell code
   - Python script to parse existing case statements → JSON
   - Merge with skill-completion-criteria.json

3. **Create `scripts/generate-phase-maps.sh`**
   - Reads registry JSON (requires jq)
   - Generates shell case statements
   - Uses atomic write (tmp + mv) for each target
   - Validates generated output matches expected structure

4. **Add validation test** `test_registry_sync`
   - Verifies all 4 generated files are current (run generator, diff, fail if changed)
   - Replaces current `TestMappingSyncParity` with stronger guarantee

5. **Update CLAUDE.md** — document registry as the source of truth

### Effort: ~4 hours | Risk: Medium (touching 4 hook files)

### Rollback: Markers are inert comments; generation is optional until validated.

### Dependencies
- `jq` required for generation script (already a recommended dependency)
- P1-1 drift detection test serves as safety net during transition

### Migration Strategy
- Phase 1: Add markers + create registry (no behavior change)
- Phase 2: Create generator + validate output matches current
- Phase 3: Switch to generated workflow (update CLAUDE.md checklist)
