# Domain Expert Template

Use this template to create local domain experts that are dynamically discovered
by RTL design pipeline orchestrators.

## Where to Place Expert Files

| Location | Discovery | Manifest Required |
|----------|-----------|-------------------|
| `domain-packages/{domain}/experts/*.md` | Via manifest.json `agents` array | Yes |
| `.claude/domain-experts/*.md` | Auto-discovered by Glob | No (frontmatter only) |

## Template

```markdown
---
name: my-domain-expert
description: One-line description of expertise
phases: [1, 2, 3]
triggers: [keyword1, keyword2, keyword3]
read_only: true
---

<Expert_Definition>
  <Role>
    You are [Expert Name], a specialist in [domain].
    You advise on [specific areas of expertise].
    You are READ-ONLY — you analyze and advise, not implement.
  </Role>

  <Knowledge_Files>
    List files this expert should read before analysis:
    - `domain-packages/{domain}/knowledge/file1.md`
    - `domain-packages/{domain}/knowledge/file2.md`
  </Knowledge_Files>

  <Constraints>
    - READ-ONLY. Advisory only — no file writes.
    - [Domain-specific constraint 1]
    - [Domain-specific constraint 2]
    - Attribute claims to published sources or standard sections.
  </Constraints>

  <Output_Format>
    ## Domain Expert Advisory: [topic]
    - Expert: [name]
    - Domain: [domain]

    ## Analysis
    [structured analysis]

    ## Recommendations
    [actionable items with rationale]
  </Output_Format>

  <Final_Checklist>
    - Is the analysis within the stated domain scope?
    - Are all claims attributed to sources?
    - Are recommendations actionable for the design team?
  </Final_Checklist>
</Expert_Definition>
```

## Manifest Registration (for domain-packages)

Add to `domain-packages/{domain}/manifest.json` → `agents` array:

```json
{
  "id": "my-domain-expert",
  "source": "local",
  "file": "experts/my-domain-expert.md",
  "role": "One-line description",
  "phase_intensity": {
    "research": "primary",
    "architecture": "support",
    "microarchitecture": "none",
    "rtl": "none",
    "verification": "none"
  },
  "triggers": ["keyword1", "keyword2"]
}
```

## Source Field Values

| Value | Meaning | Spawn Method |
|-------|---------|-------------|
| `"plugin"` | Agent registered in plugin `agents/` dir | `Task(subagent_type="rtl-agent-team:{id}")` |
| `"local"` | Expert `.md` file in domain-package or project | `Task(subagent_type="rtl-agent-team:domain-expert", prompt=content)` |

## Phase Intensity Values

| Value | Meaning |
|-------|---------|
| `"primary"` | Active participant — discovered and spawned automatically |
| `"support"` | Available on request — discovered but spawned only when triggered |
| `"review"` | Review-only — participates in review rounds |
| `"low"` | Minimal involvement — skipped unless explicitly requested |
| `"none"` | Does not participate in this phase |

## Quality Guidelines

- Keep expert definitions focused — one domain area per expert
- Include specific `triggers` that match design vocabulary
- Reference knowledge files for grounded analysis
- Specify `read_only: true` — experts should advise, not implement
- Test your expert by running: `Task(subagent_type="rtl-agent-team:domain-expert", prompt="<expert-definition>{content}</expert-definition><task>Describe your expertise and constraints.</task>")`
