---
title: rtl-document Asset Bundle Design
date: 2026-05-12
status: draft
owners: babyworm
relates_to:
  - plugin_docs/plans/2026-03-20-skill-improvement-candidates.md
---

# rtl-document Asset Bundle — Design Spec

## 1. Context & Motivation

The `rtl-document` skill is one of 11 action skills flagged as asset-poor in
`plugin_docs/plans/2026-03-20-skill-improvement-candidates.md`. Its SKILL.md
body is large (107 lines) and the `templates/` directory contains a single
Markdown scaffold; no scripts, references, or worked examples exist.

The skill is also one of the most frequently invoked utility skills (every RTL
module produced by Phase 4 should have a `docs/rtl/{module}.md`). Improving its
output quality has high leverage on user-perceived plugin quality.

The reference pattern for "well-equipped" skills in this plugin is
`rtl-p5s-func-verify`, which carries seven asset files split across
`templates/`, `scripts/`, `references/`, `examples/` and a lean 43-line
SKILL.md. This spec ports that pattern to `rtl-document` and codifies the
"asset bundle pattern" so the remaining 10 candidate skills can replicate it.

### Out of scope

- Refactoring the other 10 candidate skills (covered by a follow-up plan).
- Migrating the rtl-agent-team plugin convention from `templates/` to
  `assets/` (the plugin-dev guide's preferred name). This plugin's existing
  skills uniformly use `templates/`; consistency wins over conformance to the
  external guide.
- Replacing `rtl-explorer` as the fallback agent.

## 2. Goals & Non-goals

| Goals | Non-goals |
|-------|-----------|
| Achieve "asset bundle pattern" parity with `rtl-p5s-func-verify`. | Adding new agent types. |
| Reduce SKILL.md body to lean reference (target ~60-90 lines, <1,000 words). | Changing the deployed output path (`docs/rtl/{module}.md`). |
| Add a deterministic parser (`extract_module_doc.py`) so LLM only handles interpretive content. | Removing the manual-fallback path via `rtl-explorer`. |
| Ship three worked examples covering small/medium/large module complexity. | Generating UVM, formal, or coverage docs (separate skills). |
| Apply Anthropic prompting best-practice review to SKILL.md (XML tags, imperative form, `<example>`, scope literalism). | Re-writing the existing template markdown — the current `module-doc-template.md` is good. |

## 3. Architecture

### 3.1 Directory layout

```
skills/rtl-document/
├── SKILL.md                              # lean entry-point (~85 lines)
├── templates/
│   ├── module-doc-template.md            # EXISTING — main Markdown skeleton
│   ├── port-table-snippet.md             # NEW — port table format + clk/rst kind column
│   ├── fsm-section-snippet.md            # NEW — FSM table + Mermaid stateDiagram-v2
│   └── block-diagram-snippet.d2          # NEW — D2 block diagram for sub-instance tree
├── scripts/
│   ├── extract_module_doc.py             # NEW — Verible-based deterministic extractor
│   └── render_doc.py                     # NEW — JSON + template → final Markdown
├── references/
│   └── doc-conventions.md                # NEW — naming, tables, diagram tools, anti-patterns
└── examples/
    ├── simple_fifo.md                    # NEW — small datapath, single clock
    ├── axi_stream_bridge.md              # NEW — multi-domain, protocol grouping
    └── cabac_encoder_excerpt.md          # NEW — FSM-heavy, sub-instance tree
```

### 3.2 Asset-category responsibilities

| Category | Purpose | When LLM consults it |
|----------|---------|----------------------|
| `templates/` | Markdown skeletons composed into output. | `render_doc.py` reads and instantiates per JSON. |
| `scripts/` | Deterministic, repeatable extraction and rendering. | Run by Bash; output consumed downstream. |
| `references/` | Convention/format guide for ambiguous decisions. | Read once per session before filling markers. |
| `examples/` | Few-shot anchors of tone, depth, layout. | Read at least one whose complexity matches the target module. |

### 3.3 Data flow

```
rtl/{module}/{module}.sv
    │
    ▼
extract_module_doc.py  ──►  /tmp/{module}.json
                                │
                                ▼
render_doc.py + templates/  ──►  docs/rtl/{module}.md
                                  (contains <!-- LLM_FILL: ... --> markers)
                                │
                                ▼
LLM reads references/ + examples/, replaces every marker.
                                │
                                ▼
Final docs/rtl/{module}.md.
```

Separation of *deterministic* (script JSON) and *interpretive* (LLM marker
fill) is the central contract surface and is documented in
`<Responsibility_Boundary>` inside SKILL.md.

## 4. Component Design

### 4.1 `scripts/extract_module_doc.py`

**Responsibility**: Extract objectively determinable structure from a SV file.

**CLI**:
```bash
python3 scripts/extract_module_doc.py \
  --rtl rtl/<module>/<module>.sv \
  [--syn-report syn/synth_report.txt] \
  [--out /tmp/<module>.json]
```

**Output schema** (excerpt; full schema lives in the script's docstring):

```json
{
  "module_name": "cabac_encoder",
  "file": "rtl/cabac_encoder/cabac_encoder.sv",
  "parameters": [{"name": "DATA_WIDTH", "type": "int", "default": "32", "line": 12}],
  "ports": [
    {"name": "sys_clk",   "dir": "input", "width": 1,  "domain": "sys", "kind": "clock"},
    {"name": "sys_rst_n", "dir": "input", "width": 1,  "domain": "sys", "kind": "reset"},
    {"name": "i_data",    "dir": "input", "width": 32, "domain": "sys", "kind": "data"}
  ],
  "instances": [{"name": "u_range_coder", "module": "range_coder", "line": 145}],
  "fsm_candidates": [
    {"state_register": "state", "type_name": "state_e",
     "states": ["ST_IDLE", "ST_ENCODE", "ST_FLUSH"]}
  ],
  "clock_domains": ["sys"],
  "convention_violations": [
    {"signal": "data_i", "rule": "Use i_/o_/io_ prefix (not suffix)", "line": 42}
  ],
  "synth_summary": {"area_um2": 12450, "wns_ns": 0.21, "tns_ns": -3.4}
}
```

**Parser choice**: `verible-verilog-syntax --export_json`. Rationale:

- Already part of the plugin's lint pipeline (`skills/lint-tool-profiles`).
- Single CLI dependency; no Python package install.
- Designed by Google for JSON export use cases.

`pyslang` and `slang --ast-json` rejected on the dependency-vs-value axis.

**Failure modes**:

| Condition | Exit code | Behavior |
|-----------|-----------|----------|
| `verible-verilog-syntax` not found on PATH | 2 | stderr message; SKILL.md fallback to `rtl-explorer`. |
| SV parse error | 3 | First syntax error file:line on stderr. |
| Empty module (no ports) | 0 | Empty arrays + warning. |
| FSM register inference ambiguous | 0 | `fsm_candidates: []` (LLM may add manually). |

Generated instance names containing `$` or `\` must parse — the same hardening
that PPA Codex review R13 applied to the synthesis-report regex applies here.

### 4.2 `scripts/render_doc.py`

**Responsibility**: Combine JSON + selected template snippets into the final
Markdown. Inject `<!-- LLM_FILL: ... -->` markers where interpretive content
belongs.

**CLI**:
```bash
python3 scripts/render_doc.py \
  --json /tmp/<module>.json \
  --template-dir skills/rtl-document/templates/ \
  --out docs/rtl/<module>.md
```

**Dependencies**: Python 3 standard library only (`json`, `string.Template` or
simple `{{KEY}}` substitution — no Jinja2).

**Snippet composition rules**:

- Include `fsm-section-snippet.md` only if `fsm_candidates` is non-empty.
- Include `block-diagram-snippet.d2` only if `len(instances) >= 2`.
- Always include `port-table-snippet.md` if `ports` is non-empty.

**Marker locations**:

```
<!-- LLM_FILL: functional description (100-200 chars) -->
<!-- LLM_FILL: FSM state semantics — per-state, 1-2 lines -->
<!-- LLM_FILL: design rationale / integration notes -->
```

The marker list is fixed; adding new marker kinds requires updating both
`doc-conventions.md` and SKILL.md `<Responsibility_Boundary>`.

### 4.3 `templates/`

| File | Purpose | Selected when |
|------|---------|---------------|
| `module-doc-template.md` | Top-level skeleton, fixed section order. | Always. |
| `port-table-snippet.md` | Port table format reminder (column order, kind tagging). | `ports` non-empty. |
| `fsm-section-snippet.md` | FSM table + Mermaid skeleton. | `fsm_candidates` non-empty. |
| `block-diagram-snippet.d2` | D2 block diagram with placeholder edges. | `len(instances) >= 2`. |

Selective inclusion keeps small-module output clean (no empty FSM section).

### 4.4 `references/doc-conventions.md`

Target: ≤200 lines (refs that are too long get skipped). Sections:

1. Naming (`i_/o_/io_`, `{domain}_clk`, `{domain}_rst_n`, `u_*`, `UPPER_CASE`,
   `L_*`).
2. Table formats (column order, header conventions).
3. Diagram selection (block → D2 per `<markdown_diagram_rule>`; FSM → Mermaid
   `stateDiagram-v2`; flow → Mermaid `flowchart`).
4. Length guidance (Overview 100-200 chars; per-state 1-2 lines).
5. Anti-patterns (leftover `{{PLACEHOLDER}}`, generic "This module does X",
   describing what the code already says).

### 4.5 `examples/`

Three worked outputs covering the complexity spectrum. Each example is
generated by running the full pipeline (`extract_module_doc.py` →
`render_doc.py` → manual marker fill) so they double as living regression
tests.

| Example | Complexity | Patterns demonstrated |
|---------|------------|----------------------|
| `simple_fifo.md` | Small | Port table only; no FSM, no D2. |
| `axi_stream_bridge.md` | Medium | Multi-domain ports grouped by interface; D2 block diagram. |
| `cabac_encoder_excerpt.md` | Large | FSM table + Mermaid + D2 + sub-instance tree. |

## 5. SKILL.md Re-shape

### 5.1 Compression strategy

| Existing section | Lines | Action |
|------------------|-------|--------|
| `<Steps>` (5-step prose) | 17 | Replaced by `<Execution>` referencing scripts (5 numbered lines). |
| `<Tool_Usage>` (Task() prompts) | 19 | Reduced to a fallback Task() example only. |
| `<Examples>` (Good/Bad prose) | 13 | Moved to `examples/*.md` files + 3 `<example>` blocks in SKILL.md. |
| `<Why_This_Exists>` | 4 | Kept and tightened. |
| Other sections | 54 | Kept; tightened. |

### 5.2 New sections

| Section | Content |
|---------|---------|
| `<Assets>` | Table of every asset path + its role — discovery aid. |
| `<Responsibility_Boundary>` | Explicit deterministic-vs-interpretive contract. |

### 5.3 Anthropic prompting best-practice application

Each row below maps a recommendation from
`platform.claude.com/docs/.../claude-prompting-best-practices` and the
`plugin-dev:skill-development` skill onto a concrete change.

| Recommendation | Concrete change in SKILL.md |
|----------------|----------------------------|
| Third-person `description` with specific triggers (skill-dev). | Expanded `description` lists six trigger phrases: "document this RTL module", "generate module docs", etc. |
| Imperative/infinitive body (skill-dev). | Steps rewritten to start with verbs ("Run", "Read", "Open", "Replace", "Report") instead of narrative ("rtl-explorer reads…"). |
| XML structure for clarity (Anthropic). | All sections wrapped in XML tags (`<Purpose>`, `<Use_When>`, `<Assets>`, etc.). |
| Examples in `<example>` tags, 3-5 examples covering edge cases (Anthropic). | Three `<example index="N">` blocks with scenario/reference/expected_output sub-elements. |
| State scope explicitly (Anthropic, Opus 4.7 literalism). | `<Execution>` step 5 reads: "Replace every `<!-- LLM_FILL: ... -->` marker. Apply to all such markers — do not stop after the first." |
| Tell what to do, not what not to do (Anthropic). | "RTL source not modified" stays as a checklist item (positive: a closed-checkbox condition), not a body-text "Do not". |
| Provide motivation (Anthropic). | `<Why_This_Exists>` retained and now explains the deterministic-vs-interpretive split. |
| Progressive disclosure (skill-dev). | Detailed convention rules moved to `references/doc-conventions.md`. Body word count ≈ 600 (well under the 1,500-2,000 target). |
| Reference resources clearly (skill-dev). | `<Assets>` table lists every path. `<Execution>` cites specific files. |
| Avoid duplication (skill-dev). | Naming conventions live only in `references/doc-conventions.md`; SKILL.md mentions but does not re-state them. |

### 5.4 Final SKILL.md draft

```markdown
---
name: rtl-document
description: This skill should be used when the user asks to "document this RTL module", "generate module docs", "create port table for X", "RTL documentation pass", "refresh RTL docs after change", or when a new RTL module needs Markdown documentation with port/parameter/instance tables and a synthesis summary.
user-invocable: true
argument-hint: "[module-name | --all]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Generate per-module Markdown documentation for SystemVerilog RTL — port table, parameter table, instance table, FSM section, and synthesis summary. Output: docs/rtl/{module}.md.
</Purpose>

<Use_When>
- A new RTL module needs documentation.
- Module documentation has become stale after RTL changes.
- A pre-release documentation pass is required.
- The user asks to "document this module", "generate port table", or "refresh RTL docs".
</Use_When>

<Do_Not_Use_When>
- Architecture specification writing is needed → use p2-arch-design.
- IP-XACT XML generation is needed → use rtl-ipxact-gen.
- Synthesis-only reporting is needed → use rtl-synth-check.
</Do_Not_Use_When>

<Why_This_Exists>
RTL documentation written by hand drifts from implementation. Auto-extraction from SV source keeps port tables, parameter lists, and instance trees accurate. The skill splits work between a deterministic parser (objective structure) and the LLM (functional description, FSM semantics, design rationale), making the contract surface explicit and regression-debuggable.
</Why_This_Exists>

## Prerequisites

- RTL files exist under `rtl/**/*.sv`.
- Optional: synthesis report at `syn/synth_report.txt` for area/timing summary.

If the prerequisite is missing: WARNING — recommend running `/rtl-agent-team:rtl-p4-implement` first. Proceed with available artifacts; the orchestrator adapts scope.

<Assets>
| Path | Role |
|------|------|
| `templates/module-doc-template.md` | Main Markdown skeleton (Overview/Params/Ports/Clocks/Instances/Diagram). |
| `templates/port-table-snippet.md` | Port-table format with `i_/o_/io_` prefix, `{domain}_clk`/`{domain}_rst_n`, kind column. |
| `templates/fsm-section-snippet.md` | FSM table plus Mermaid `stateDiagram-v2` skeleton. |
| `templates/block-diagram-snippet.d2` | D2 block diagram for sub-instance hierarchy. |
| `scripts/extract_module_doc.py` | Verible-based deterministic extractor — emits JSON for ports/params/instances/FSM/conventions. |
| `scripts/render_doc.py` | JSON + template → `docs/rtl/{module}.md` with `<!-- LLM_FILL: ... -->` markers. |
| `references/doc-conventions.md` | Naming rules, table format, diagram-tool choice, anti-patterns. |
| `examples/simple_fifo.md` | Small datapath, single domain — minimal baseline. |
| `examples/axi_stream_bridge.md` | AXI4-Stream + APB control, two clock domains — protocol grouping. |
| `examples/cabac_encoder_excerpt.md` | FSM-heavy + sub-instance tree — full template usage. |
</Assets>

<Responsibility_Boundary>
- **Scripts** handle deterministic extraction: module name, ports, parameters, instances, FSM-candidate states, clock-domain inference from naming, convention violations.
- **LLM** handles interpretive content: functional description, FSM state semantics, design rationale, integration notes.
- `<!-- LLM_FILL: ... -->` markers in rendered output mark the contract surface. Replace each marker; never delete.
</Responsibility_Boundary>

<Execution>
1. Run `python3 skills/rtl-document/scripts/extract_module_doc.py --rtl rtl/{module}/{module}.sv [--syn-report syn/synth_report.txt] --out /tmp/{module}.json`. If exit code 2 (verible missing), fall back to manual extraction via `rtl-explorer` (see Tool_Usage).
2. Run `python3 skills/rtl-document/scripts/render_doc.py --json /tmp/{module}.json --template-dir skills/rtl-document/templates/ --out docs/rtl/{module}.md`. The script composes `module-doc-template.md` with the optional snippets — `port-table-snippet.md` when ports exist, `fsm-section-snippet.md` when `fsm_candidates` is non-empty, `block-diagram-snippet.d2` when there are two or more instances.
3. Read `skills/rtl-document/references/doc-conventions.md` once for naming/format/diagram rules.
4. Open at least one matching `skills/rtl-document/examples/*.md` for tone reference — pick the example whose complexity (small / multi-domain / FSM-heavy) is closest to the target module.
5. Replace every `<!-- LLM_FILL: ... -->` marker in `docs/rtl/{module}.md`. Apply to all such markers in the file — do not stop after the first.
6. Report the generated file path to the user.

Apply steps 1-6 to every requested module. When `--all` is passed, fan out using one task per module in parallel.
</Execution>

<Tool_Usage>
Manual-extraction fallback (when verible is unavailable):
```
Task(subagent_type="rtl-agent-team:rtl-explorer",
     prompt="Document RTL module per skills/rtl-document/. Read rtl/{module}/{module}.sv, extract ports/parameters/instances/FSM, apply project naming conventions, and fill the LLM_FILL markers in docs/rtl/{module}.md.")
```

Synthesis summary:
```
Task(subagent_type="rtl-agent-team:synthesis-reporter",
     prompt="Summarize syn/synth_report.txt and syn/timing_report.txt for the docs/rtl/{module}.md synthesis section.")
```
</Tool_Usage>

<Examples>
<example index="1">
<scenario>Small datapath module, no FSM, single clock domain.</scenario>
<reference>skills/rtl-document/examples/simple_fifo.md</reference>
<expected_output>Port table only; FSM and D2 sections omitted by render_doc.py because the JSON has empty fsm_candidates and one instance or fewer.</expected_output>
</example>

<example index="2">
<scenario>AXI-Stream bridge with two clock domains.</scenario>
<reference>skills/rtl-document/examples/axi_stream_bridge.md</reference>
<expected_output>Ports grouped by AXI / APB; Clock Domains table lists both `sys` and `pixel`; D2 block diagram shows the async-FIFO bridge.</expected_output>
</example>

<example index="3">
<scenario>FSM-heavy codec module with multiple sub-instances.</scenario>
<reference>skills/rtl-document/examples/cabac_encoder_excerpt.md</reference>
<expected_output>FSM table with Mermaid `stateDiagram-v2`; D2 block diagram for the sub-instance tree; functional description references the relevant standard section.</expected_output>
</example>
</Examples>

<Escalation_And_Stop_Conditions>
- `extract_module_doc.py` returns SV parse error → report file:line; do not fabricate ports. Ask the user to fix the syntax first.
- FSM register cannot be inferred → JSON has `fsm_candidates: []`. Add an FSM section manually only when a state machine clearly exists and the state register is identifiable.
- Synthesis report absent → omit the Synthesis Summary section; note the absence in the document footer.
- Port name violates convention (e.g., `data_i` suffix) → record in `convention_violations` and surface the violation at the top of the generated doc. Do not rewrite the RTL.
</Escalation_And_Stop_Conditions>

## Output

- `docs/rtl/{module}.md` — per-module documentation.
- `/tmp/{module}.json` — intermediate extraction (transient; not committed).

<Final_Checklist>
- [ ] `docs/rtl/{module}.md` exists for every requested module.
- [ ] Port table lists every port with `i_/o_/io_` prefix; clock/reset rows tagged `kind=clock|reset`.
- [ ] Parameters use `UPPER_SNAKE_CASE`.
- [ ] Instance table uses `u_` prefix.
- [ ] All `<!-- LLM_FILL: ... -->` markers replaced.
- [ ] RTL source not modified.
- [ ] Synthesis Summary included when `syn/synth_report.txt` exists.
- [ ] Convention violations flagged at the top of the doc when any were found.
</Final_Checklist>
```

Approximate metrics for the draft:

- **Lines**: ~95 (frontmatter + body + checklist).
- **Words**: ~640 — well below the 1,500-2,000 target, leaving headroom for
  future tuning without bloat.
- **Lean ratio**: `<Steps>` (17 lines, prose) collapsed into `<Execution>`
  (8 lines, numbered).

## 6. Migration & Rollout

| Stage | Action |
|-------|--------|
| Implementation | Land scripts, templates, references, examples in one commit; SKILL.md re-shape in a second commit to keep diffs reviewable. |
| Dogfooding | Re-generate the three example outputs by running the full pipeline against real modules in the plugin's test fixtures. Commit the regenerated files. |
| Tests | Add a unit test that parses every `examples/*.md` and asserts no stray `<!-- LLM_FILL: ... -->` markers remain; add a smoke test that runs `extract_module_doc.py` against a fixture module and validates JSON schema. |
| CI | Wire both tests into the existing pytest job (`tests/unit/`). |
| Docs | Update `plugin_docs/plans/2026-03-20-skill-improvement-candidates.md` to mark `rtl-document` complete and point future skills at this design as the reference pattern. |

## 7. Open Questions

- Should `extract_module_doc.py` cache JSON output (e.g., under
  `.rat/state/rtl-document-cache/`) to avoid re-parsing unchanged files in
  `--all` mode? Default proposal: no caching in v1 — measure first.
- Should convention violations escalate to a hook gate? Default proposal: no
  — `rtl-document` is a generator, not a verifier; surfacing the violation in
  the doc itself is sufficient.
- Should the `examples/` files reference real plugin fixtures or generic
  module names? Default proposal: generic names so the examples are
  self-contained and do not assume a particular user project layout.

## 8. Success Criteria

1. `rtl-document` SKILL.md body ≤ 1,000 words.
2. All four asset categories (`templates/`, `scripts/`, `references/`,
   `examples/`) present and populated.
3. Three worked examples generated by the actual pipeline; all
   `<!-- LLM_FILL: ... -->` markers replaced.
4. Smoke test (`extract_module_doc.py` against fixture) passes in CI.
5. The "asset bundle pattern" is documented well enough that the next 10
   candidate skills can be migrated by repetition rather than redesign.
