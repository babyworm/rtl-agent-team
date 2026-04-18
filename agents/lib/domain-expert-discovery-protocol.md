# Domain Expert Discovery Protocol

Follow the structured output annotation protocol defined in `agents/lib/audit-output-protocol.md`.

Orchestrators reference this protocol to dynamically discover and spawn domain experts
from `domain-packages/*/manifest.json` and project-local directories.

## When to Discover

Run discovery in **Step 0.5** (after setup check, before main workflow):
- Phase 1-3 orchestrators: discover experts for consultation and review
- Phase 4-5 orchestrators: discover experts for verification guidance
- DSE / exploration orchestrators: discover experts for domain-specific evaluation

## Discovery Steps

### Step 1: Find Domain Packages

```
Glob("domain-packages/*/manifest.json")
```

If no manifests found → skip discovery, proceed without domain experts.

### Step 2: Filter by Current Phase

For each manifest, read the `agents` array. Filter experts whose `phase_intensity`
matches the current phase with intensity `primary` or `support`:

```
Read("domain-packages/{domain}/manifest.json")
→ agents[].phase_intensity.{current_phase} ∈ {"primary", "support"}
```

### Step 3: Build Expert Roster

For each matching expert, record:

| Field | Source | Purpose |
|-------|--------|---------|
| `id` | manifest | Unique identifier |
| `source` | manifest | `"plugin"` or `"local"` |
| `plugin_id` | manifest (plugin only) | `Task(subagent_type=...)` value |
| `file` | manifest (local only) | Path to expert definition `.md` |
| `triggers` | manifest | Keywords that match this expert's specialty |
| `phase_intensity` | manifest | How strongly this expert participates |

### Step 4: Spawn Experts

When the orchestrator needs domain consultation:

**Plugin expert** (`source: "plugin"`):
```
Task(subagent_type="{plugin_id}",
     prompt="{task description}")
```
This is deterministic — the agent is registered in the plugin's agents/ directory.

**Local expert** (`source: "local"`):
```
expert_content = Read("domain-packages/{domain}/{file}")
Task(subagent_type="rtl-agent-team:domain-expert",
     prompt="<expert-definition>\n{expert_content}\n</expert-definition>\n\n<task>\n{task}\n</task>")
```
This uses the generic domain-expert runner agent.

### Step 5: Project-Local Experts (Optional)

Check for project-local experts outside domain-packages:
```
Glob(".claude/domain-experts/*.md")
```

If found, treat as `source: "local"` with no manifest entry.
Read frontmatter for `phases` and `triggers`:
```yaml
---
name: my-custom-expert
phases: [2, 3]
triggers: [keyword1, keyword2]
---
```

## Trigger Matching

Orchestrators use triggers for automatic expert selection:
1. Extract keywords from the current task/spec (e.g., "CABAC", "deblocking", "SRAM")
2. Match against each expert's `triggers` array
3. Spawn experts with matching triggers

For manual selection (e.g., review rounds), use `phase_intensity` to determine
which experts participate.

## Priority Rules

| Priority | Expert Source | Spawn Method |
|----------|-------------|--------------|
| 1 (highest) | Plugin agent (`source: "plugin"`) | `Task(subagent_type=plugin_id)` |
| 2 | Domain-package local (`source: "local"`) | `Task(subagent_type=domain-expert)` |
| 3 (lowest) | Project-local (`.claude/domain-experts/`) | `Task(subagent_type=domain-expert)` |

When both a plugin agent and a local expert cover the same trigger,
the plugin agent takes priority (deterministic routing).

## Backward Compatibility

If an orchestrator does not find any `domain-packages/*/manifest.json`:
- Hardcoded domain expert references in the orchestrator still work
- No behavioral change from pre-discovery versions

Orchestrators SHOULD prefer manifest-based discovery but MAY retain
hardcoded fallbacks for critical domain experts during the migration period.

## Example: P3 uArch Orchestrator Discovery

```
# Step 0.5: Domain Expert Discovery
manifests = Glob("domain-packages/*/manifest.json")
# Found: domain-packages/video-codec/manifest.json

manifest = Read("domain-packages/video-codec/manifest.json")
# Filter for phase 3 (microarchitecture):
#   vcodec-architecture-expert: primary → INCLUDE
#   video-processing-expert: primary → INCLUDE
#   vcodec-syntax-entropy-expert: support → INCLUDE
#   vcodec-chief-standard-expert: low → SKIP

# Later in Step 3 (review):
Task(subagent_type="rtl-agent-team:vcodec-architecture-expert",
     prompt="Review SRAM organization for H.265 intra prediction block...")
```
