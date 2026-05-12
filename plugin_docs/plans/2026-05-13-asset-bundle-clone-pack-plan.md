# Asset Bundle Clone Pack — Implementation Plan

> **Goal:** Replicate the asset-bundle pattern (established by `rtl-document` in v0.11.0) across the 10 remaining candidate skills listed in `plugin_docs/plans/2026-03-20-skill-improvement-candidates.md`.

**Architecture:** Each migrated skill gains the four canonical asset directories (`templates/`, `scripts/`, `references/`, `examples/`), a domain-specific `references/{name}-conventions.md` (≤150 lines), and a lean SKILL.md restructured to the `<Assets>` + `<Responsibility_Boundary>` pattern. Deep script/example fills are deferred to per-skill follow-up PRs — this PR delivers **uniform structure + entry-point doc + minimal asset scaffolds** so every skill can be deep-filled independently afterwards.

**Tech Stack:** Markdown only for this PR. No Python/SV implementations. Reuses the pattern documented in §5.3 of `plugin_docs/specs/2026-05-12-rtl-document-asset-bundle-design.md`.

**Spec (lightweight):** The rtl-document spec serves as the reference; no separate spec is needed because the migration is mechanical pattern application, not new design.

---

## Migration matrix

| # | Skill | Current lines | Current assets | Migration scope (this PR) |
|---|-------|---------------|---------------|---------------------------|
| 1 | `rtl-bug-repro` | 103 | T·S· (2) | + `references/{bug-repro-conventions.md}` + `examples/.gitkeep`; SKILL.md → lean asset-bundle form. |
| 2 | `rtl-ipxact-gen` | 99 | T··· (1) | + `scripts/.gitkeep` + `references/ipxact-conventions.md` + `examples/.gitkeep`; SKILL.md → lean. |
| 3 | `rtl-p5s-perf-verify` | 56 | T··· (1) | + `scripts/.gitkeep` + `references/perf-verify-conventions.md` + `examples/.gitkeep`; SKILL.md → lean. |
| 4 | `rtl-p5s-coverage-analyze` | 57 | T··· (1) | + `scripts/.gitkeep` + `references/coverage-conventions.md` + `examples/.gitkeep`; SKILL.md → lean. |
| 5 | `rtl-p5s-integration-test` | 71 | T··· (1) | + `scripts/.gitkeep` + `references/integration-test-conventions.md` + `examples/.gitkeep`; SKILL.md → lean. |
| 6 | `ref-model` | 196 | T··· (4) | + `scripts/.gitkeep` + `references/ref-model-conventions.md` + `examples/.gitkeep`; SKILL.md → lean (compress from 196 → ~110 lines). |
| 7 | `bfm-develop` | 141 | T··· (1) | + `scripts/.gitkeep` + `references/bfm-conventions.md` + `examples/.gitkeep`; SKILL.md → lean. |
| 8 | `rtl-ip-instantiate` | 101 | T··· (1) | + `scripts/.gitkeep` + `references/ip-instantiate-conventions.md` + `examples/.gitkeep`; SKILL.md → lean. |
| 9 | `rtl-model-consistency` | 100 | T·S· (2) | + `references/model-consistency-conventions.md` + `examples/.gitkeep`; SKILL.md → lean. |
| 10 | `rtl-conformance-test` | 107 | T·S· (2) | + `references/conformance-test-conventions.md` + `examples/.gitkeep`; SKILL.md → lean. |

## File pattern (per skill)

Each migrated skill ends with this minimum structure:

```
skills/{skill-name}/
├── SKILL.md                                 # lean asset-bundle form, ~80-130 lines
├── templates/                               # EXISTING — preserved
│   └── ...                                  #   existing template(s)
├── scripts/                                 # NEW or existing
│   └── .gitkeep                             #   placeholder; deep-fill in follow-up PR
├── references/                              # NEW
│   └── {short-name}-conventions.md          #   domain-specific guide, ≤150 lines
└── examples/                                # NEW
    └── .gitkeep                             #   placeholder; deep-fill in follow-up PR
```

## SKILL.md restructure template

Apply to every migrated skill:

```markdown
---
name: {skill-name}
description: This skill should be used when the user asks to "{trigger phrase 1}", "{phrase 2}", "{phrase 3}", ... (>= 3 trigger phrases, third-person form).
user-invocable: true
argument-hint: "{...}"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
{One paragraph, what the skill produces, where output lands.}
</Purpose>

<Use_When>
- {Trigger scenario 1}
- {Trigger scenario 2}
- ...
</Use_When>

<Do_Not_Use_When>
- {Conflict scenario 1 with redirection target}
- ...
</Do_Not_Use_When>

<Why_This_Exists>
{Two sentences: motivation + the deterministic-vs-interpretive split that this skill embodies.}
</Why_This_Exists>

## Prerequisites
{Brief list; soft warnings only, per CLAUDE.md "Skill as soft advisory".}

<Assets>
| Path | Role |
|------|------|
| `templates/{...}` | {role} |
| `scripts/{...}` | (placeholder — deep-fill in follow-up PR) |
| `references/{name}-conventions.md` | Naming/format/anti-pattern guide for this domain. |
| `examples/` | (placeholder — deep-fill in follow-up PR) |
</Assets>

<Responsibility_Boundary>
- **Scripts** handle deterministic extraction or generation.
- **LLM** handles interpretive content.
- Contract surface markers (or output schema) documented in references.
</Responsibility_Boundary>

<Execution>
{Numbered steps that delegate to the appropriate orchestrator/specialist via Task(), with "Apply to every X" scope literalism.}
</Execution>

<Examples>
<example index="1">
<scenario>{...}</scenario>
<expected_output>{...}</expected_output>
</example>
<example index="2">{...}</example>
<example index="3">{...}</example>
</Examples>

<Escalation_And_Stop_Conditions>
- ...
</Escalation_And_Stop_Conditions>

## Output
- `{...}` — {role}

<Final_Checklist>
- [ ] ...
</Final_Checklist>
```

## references/{name}-conventions.md template

≤150 lines. Sections:
1. Naming conventions specific to this skill's output.
2. Output schema (where applicable).
3. Length / style guidance per output element.
4. Anti-patterns (refuse-to-invent rules).

## Task list

Each task = single skill migration = single commit.

- [ ] **Task 1**: rtl-bug-repro — references + examples + lean SKILL.md.
- [ ] **Task 2**: rtl-ipxact-gen — scripts + references + examples + lean SKILL.md.
- [ ] **Task 3**: rtl-p5s-perf-verify — scripts + references + examples + lean SKILL.md.
- [ ] **Task 4**: rtl-p5s-coverage-analyze — same.
- [ ] **Task 5**: rtl-p5s-integration-test — same.
- [ ] **Task 6**: ref-model — same; also compress SKILL.md from 196 → ~110 lines.
- [ ] **Task 7**: bfm-develop — same.
- [ ] **Task 8**: rtl-ip-instantiate — same.
- [ ] **Task 9**: rtl-model-consistency — references + examples + lean SKILL.md.
- [ ] **Task 10**: rtl-conformance-test — same.
- [ ] **Task 11**: Add structural unit test `tests/unit/test_asset_bundle_pack.py` asserting each of the 10 skills has the 4 canonical directories and a `references/*.md` ≤150 lines.
- [ ] **Task 12**: Update `plugin_docs/plans/2026-03-20-skill-improvement-candidates.md` — mark all 11 entries done (1 prior + 10 new); update Reference Pattern footnote to cite v0.11.0 + this PR.
- [ ] **Task 13**: Push + PR.

## Success criteria

1. All 10 skills have `templates/scripts/references/examples/` directories present.
2. Each has a `references/{name}-conventions.md` of ≤ 150 lines.
3. Each SKILL.md has the seven canonical sections in the asset-bundle template.
4. Single test file validates the structural invariants for all 10 skills.
5. Full unit suite green (no regression).
6. Candidates plan updated: all 11 entries marked done.
