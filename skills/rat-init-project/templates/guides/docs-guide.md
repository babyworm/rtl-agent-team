# Design Documentation

## Artifact Structure

```
docs/
├── phase-1-research/          # → Input for Phase 2
│   ├── iron-requirements.json # Settled functional (REQ-F)/performance (REQ-P) requirements, binding
│   ├── open-requirements.json # Research topics (OPEN-N) Phase 2 must resolve into decisions
│   ├── io_definition.json     # I/O port spec
│   ├── timing_constraints.json # Rough timing estimates per block
│   ├── domain-analysis.md     # Domain analysis (algorithms, standards, per-block timing targets)
│   ├── candidate-comparison.md # Pareto-optimal candidate comparison matrix
│   ├── selected-approach.md   # Selected candidate with rationale
│   ├── literature-survey.md   # HW architecture pattern survey
│   ├── solution-tree.json     # Solution path tree (structured)
│   └── phase-1-summary.md     # Compressed summary (auto-generated)
├── phase-2-architecture/      # → Input for Phase 3
│   ├── architecture.md        # Block architecture (module hierarchy, datapath, timing)
│   └── phase-2-summary.md
├── phase-3-uarch/             # → Input for Phase 4
│   ├── {module_name}.md       # Per-module microarchitecture
│   └── phase-3-summary.md
├── phase-4-rtl/               # → Input for Phase 5
│   ├── module-descriptions.md
│   ├── unit-test-design.md
│   ├── stream-b-sva-skeletons.md
│   ├── stream-b-cdc-preliminary.md
│   ├── stream-b-tb-skeletons.md
│   └── phase-4-summary.md
├── phase-5-verify/            # → Input for Phase 6
│   ├── unit-test-report.md
│   ├── integration-report.md
│   ├── ref-rtl-model-consistency.md
│   ├── lint-report.md
│   ├── synthesis-estimate.md
│   └── phase-5-summary.md
├── decisions/                 # Architecture Decision Records
│   └── ADR-{NNN}.md          # Per-decision record (context, options, decision, consequences)
├── lessons-learned.md         # Cross-phase lessons (appended per bug fix)
└── phase-7-exploration/       # Free exploration (no pipeline rules)
    └── exploration-notes.md
```

## Design Principles

### Hierarchical Spec Compliance

Lower stages must never violate upper stage specs:
```
Requirements(Spec) → Architecture → μArch → RTL → Verification
    ↑ Each stage must comply with the decisions of the stage to its left
```

1. Architecture must implement ALL required Spec functions (no reduction for convenience)
2. μArch must comply with Architecture's block boundaries and interfaces
3. RTL must faithfully implement μArch design
4. Verification validates against original Spec (not tailored to RTL)

**Design priorities**: Functional Correctness > Interface Compliance > Timing/Performance > Area/Power

**Phase Gate checks**: Feature Coverage Checklist, interface change tracking, user approval for deviations.

### Light Review

One review against the evidence, then stop and name the open items. A further pass runs only when the user asks. With no measurement, the model's confidence is the gate: the spec has one reading, or one architecture choice fits. Do not iterate to raise confidence. Low confidence is named and asked once. Lint, simulation, formal, coverage, synthesis, and model comparison are judged from the measured result. Confidence does not override a measurement.

| Phase | Review |
|-------|--------|
| Phase 1: Research | One chief review of the requirements |
| Phase 2: Architecture | One review (memory, performance, reference model) |
| Phase 3: μArch | One review (performance, interface, memory) |
| Phase 4: RTL | Implement, lint, one functional check |
| Phase 5: Verify | Check the requirements once |

Prompts state the goal, the constraints, the evidence, and the done condition.

### Document-as-Memory Principle

Design artifacts serve as persistent memory across phases and agents.
Each phase reads upstream docs as input and writes downstream docs as output.
No agent needs to "remember" — it reads the document.

**Context Summarization**: Each phase generates `phase-N-summary.md`. Downstream phases use summaries
(via `summary only` in Context Preload) instead of full docs, reducing context window consumption.
Full documents are only loaded when declared as `required (full read)` or on-demand.
Intra-phase scratchpad: `.rat/scratch/phase-{N}/` (cleaned on phase completion).

## Phase 1 — Proactive Requirement Clarification

Use AskUserQuestion to clarify when:
- Target resolution/frame rate/codec not specified
- Interface protocol (AXI/APB/custom) not specified
- Clock frequency or timing constraints unclear
- Functional scope ambiguous (encoder/decoder/both, supported profiles/levels, etc.)
- spec-analyst flags `[AMBIGUITY]` or `[CONFLICT]`
- Interpretations conflict between domain experts

Do NOT ask when: detailed spec provided, standard has one valid interpretation, decidable by convention.

## Domain Packages

Domain packages provide pre-built knowledge bases at `domain-packages/{domain}/`.

**Active**:
- `video-codec` (`domain-packages/video-codec/manifest.json`)
- `video-processing` (`domain-packages/video-processing/manifest.json`)

Domain expert agents MUST read knowledge files from `domain-packages/{domain}/knowledge/` BEFORE analysis.

| Knowledge File | Relevant Agents | Phase |
|---|---|---|
| `h264-spec-summary.md` | All vcodec experts, chief | Phase 1-2 |
| `h265-spec-summary.md` | All vcodec experts, chief | Phase 1-2 |
| `jm-function-map.md` | spec-analyst, ref-model-dev | Phase 1-2 |
| `throughput-tables.md` | video-processing-expert, arch-designer | Phase 1-3 |
| `fixed-point-conventions.md` | vcodec-transform-quant-expert, vcodec-architecture-expert | Phase 1-3 |
| `hw-architecture-survey.md` | vcodec-architecture-expert, arch-designer | Phase 2-3 |

Conformance data: `domain-packages/video-codec/conformance/`
Templates: `domain-packages/video-codec/templates/`
Agent coordination workflows: See `manifest.json` `agent_coordination` section.

Video-processing package key files:
| Knowledge File | Relevant Agents | Phase |
|---|---|---|
| `v4l2-pixfmt-overview.md` | all `vproc-*` experts | Phase 1-2 |
| `v4l2-storage-layout.md` | `vproc-color-format-expert`, `vproc-denoise-expert` | Phase 1-3 |
| `v4l2-yuv-rgb-bayer-formats.md` | `vproc-color-format-expert`, `vproc-image-processing-expert` | Phase 1-2 |
| `v4l2-colorspace-quantization.md` | `vproc-color-format-expert`, `vproc-image-processing-expert` | Phase 1-2 |
| `format-conversion-recipes.md` | all `vproc-*` experts | Phase 2-4 |
| `fourcc-cheatsheet.md` | all `vproc-*` experts | Phase 1-3 |

## Reader-facing figures

A design note and `docs/rtl` author each figure as SVG and insert the PNG.

If a diagram-design skill is available, use it to draw the SVG. Otherwise draw the SVG.

ARM Developer's Guide style: white background, thin black strokes, left-to-right data flow, nested rectangles, signal names on the wires.

`![Figure N-M. One-line caption.](figures/name.png)`

Keep the SVG beside the PNG. Convert with `rsvg-convert -o figures/name.png figures/name.svg` or `magick figures/name.svg figures/name.png`. If neither exists, or the conversion fails, say so and keep the SVG. Do not paste SVG source into the markdown.

A register is a bit-field bar. MSB is on the left. Bit numbers sit above the cells. One box per field. Reserved is light gray. Every field has bits, access, reset, and what a read returns and a write does. Choose a missing access or reset, say that the choice was made in the doc, and explain the effect. Do not invent a field.

Prose: the heading states the point. The first sentence is the conclusion. At most three sentences. One idea per section.

Architecture and μArch working notes still use D2 for a block diagram and Mermaid for an FSM or a flow.

<!-- rat-version: 0.7.7 -->
