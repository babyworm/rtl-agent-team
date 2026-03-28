# Design Documentation

## Artifact Structure

```
docs/
├── phase-1-research/          # → Input for Phase 2
│   ├── requirements.json      # Requirements list
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

### Cascading Quality Principle

Higher abstraction = MORE iterative refinement. A defect at architecture costs orders of magnitude more at RTL.

| Phase | Mandatory Review Iterations |
|-------|-----------------------------|
| Phase 1: Research | 3 rounds (chief-coordinated) |
| Phase 2: Architecture | 3 rounds (memory, performance, ref model) |
| Phase 3: μArch | 3 rounds (performance, interface, memory) |
| Phase 4: RTL | 10-Wave pipeline (write→lint→review→fix→test→CDC→protocol→refactor→gate) |
| Phase 5: Verify | Sub-phase parallel |

Iteration count may increase beyond 3 if convergence is not achieved.
**Principle**: refine thoroughly at the top, execute efficiently at the bottom.

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

## Diagram Syntax Reference

**D2 block diagrams:**
````
```d2
top_module -> sub_a: data [32]
top_module -> sub_b: ctrl
```
````

**Tool install**: D2: `curl -fsSL https://d2lang.com/install.sh | sh -s --` or `brew install d2`. Mermaid: `npm install -g @mermaid-js/mermaid-cli`

<!-- rat-version: 0.7.7 -->
