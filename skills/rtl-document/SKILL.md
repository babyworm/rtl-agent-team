---
name: rtl-document
description: "Generate Markdown docs for an RTL module (ports, registers, FSM, ARM figures) — 'document this module', 'port table', 'refresh RTL docs'."
user-invocable: true
argument-hint: "[module-name | --all]"
allowed-tools: Read, Write, Edit, Task, Grep, Glob
---

Delegate using the current host as described in `{plugin_root}/runtime/model-selection.md`.

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
| `templates/fsm-section-snippet.md` | FSM table plus a PNG figure link. The SVG is drawn beside it. |
| `references/figures/ctrl-bitfield.svg` | ARM bit-field bar format sample. Insert the PNG. |
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
1. Run `python3 {plugin_root}/skills/rtl-document/scripts/extract_module_doc.py --rtl rtl/{module}/{module}.sv [--syn-report syn/synth_report.txt] --out /tmp/{module}.json` (`{plugin_root}` = plugin root resolved from `.rat/state/spawn-context.json`). If exit code 2 (verible missing), fall back to manual extraction via `rtl-explorer` (see Tool_Usage).
2. Run `python3 {plugin_root}/skills/rtl-document/scripts/render_doc.py --json /tmp/{module}.json --template-dir {plugin_root}/skills/rtl-document/templates/ --out docs/rtl/{module}.md`. The script composes `module-doc-template.md` with `fsm-section-snippet.md` when `fsm_candidates` is non-empty, and a block-diagram PNG link when there are two or more instances.
3. Read `references/doc-conventions.md` once for naming, figures, length, and registers.
4. Open at least one matching `examples/*.md` for tone reference — pick the example whose complexity (small / multi-domain / FSM-heavy) is closest to the target module.
5. Replace every `<!-- LLM_FILL: ... -->` marker in `docs/rtl/{module}.md`. Apply to all such markers in the file — do not stop after the first.
6. Draw each figure as SVG in ARM Developer's Guide style. If a diagram-design skill is available, use it to draw the SVG. Otherwise draw the SVG. Convert it to the PNG the markdown already links. Keep the SVG beside the PNG. Do not leave a D2 or Mermaid fence.
7. Report the generated file path to the user.

Apply steps 1-7 to every requested module. When `--all` is passed, fan out using one task per module in parallel.
</Execution>

<Tool_Usage>
Manual-extraction fallback (when verible is unavailable):
```
Task(subagent_type="rtl-agent-team:rtl-explorer",
     prompt="Document RTL module per skills/rtl-document/. Read rtl/{module}/{module}.sv, extract ports/parameters/instances/FSM, apply project naming conventions, and fill the LLM_FILL markers in docs/rtl/{module}.md.")
```

Synthesis summary:
```
"${RAT_PYTHON:-python3}" {plugin_root}/scripts/parse_synthesis.py --root <project> --tool <selected-tool> --log <synthesis-log>
```
</Tool_Usage>

<Examples>
<example index="1">
<scenario>Small datapath module, no FSM, single clock domain.</scenario>
<reference>examples/simple_fifo.md</reference>
<expected_output>Port table and a Registers section. FSM and the block-diagram PNG are omitted because the JSON has empty fsm_candidates and one instance or fewer.</expected_output>
</example>

<example index="2">
<scenario>AXI-Stream bridge with two clock domains.</scenario>
<reference>examples/axi_stream_bridge.md</reference>
<expected_output>Ports grouped by AXI / APB; Clock Domains table lists both `sys` and `pixel`; the block diagram is an ARM SVG inserted as PNG.</expected_output>
</example>

<example index="3">
<scenario>FSM-heavy codec module with multiple sub-instances.</scenario>
<reference>examples/cabac_encoder_excerpt.md</reference>
<expected_output>FSM table and sub-instance tree, each an ARM SVG inserted as PNG. Functional description references the relevant standard section. Every register field is decided and explained.</expected_output>
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
- [ ] Each figure is an ARM SVG inserted as PNG. No D2 or Mermaid fence remains.
- [ ] Every register field has bits, access, reset, and its read and write effect. No register: the section says `_None._`.
- [ ] RTL source not modified.
- [ ] Synthesis Summary included when `syn/synth_report.txt` exists.
- [ ] Convention violations flagged at the top of the doc when any were found.
</Final_Checklist>
