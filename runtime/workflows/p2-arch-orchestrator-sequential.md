Design a block architecture and executable C reference model from Phase 1 iron
requirements, the selected algorithm, and remaining architectural questions.
Resolve only choices that affect the requested design. One viable architecture is
sufficient; compare alternatives only when the evidence leaves a real tradeoff.
Use arch-designer and ref-model-dev where their distinct outputs justify delegation.
Consult clock-architect or a domain expert only for an unresolved clock/domain or
standards issue. Keep upstream authority P1 above architectural preferences.

Deliver docs/phase-2-architecture/{architecture.md,iron-requirements.json,
open-requirements.json,bandwidth_report.json,judgment.json}, the runnable model under
refc/, and reviews/phase-2-architecture/architecture-review.md. Map each REQ-A-* to
its upstream requirements. Record memory latency, bandwidth, interfaces, precision,
and PPA assumptions for the actual blocks; do not invent a process/library target.

Build and functionally self-test the reference model, comparing an available golden
model on shared vectors. Compilation alone does not validate its outputs. Review
the architecture and model consistency once; ref-model-reviewer is useful for a
new or materially changed model, not as a compulsory repeat. Repair measured
mismatches and rerun affected checks, with at most two failed repair cycles before
requesting direction. Complete compliance against P1 iron, phase summary and ADRs.
Missing inputs limit the supported design scope; disclose that limit at handoff.
