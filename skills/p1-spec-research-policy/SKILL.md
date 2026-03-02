---
name: p1-spec-research-policy
description: "Quality criteria, review protocols, naming conventions, artifact format specifications, and checklists for the Phase 1 research pipeline. Pure reference — no orchestration."
user-invocable: false
---

# Phase 1 Research Policy

## Core Principles

### AskUserQuestion-First
Every ambiguity, design choice, or scope decision MUST be resolved via AskUserQuestion
BEFORE proceeding. Do not assume — ask. The cost of asking is low; the cost of a wrong
assumption cascades to all later phases.

### Domain-Consult-First
Actively invoke domain-consult to acquire domain expert knowledge on algorithms, standards,
coding tools, filter characteristics, and HW implementation trade-offs. Do not research
in isolation. Domain experts provide knowledge; spec-analyst captures results as structured artifacts.

### Propose, Do Not Decide
Present algorithm/tool candidates with trade-offs. Let the user make final selections.
Architecture-level decisions (pipeline, block partitioning, memory hierarchy) are Phase 2's
responsibility. Phase 1 surveys and recommends; Phase 2 designs.

### Exhaustive Tree Exploration
Spawn maximum agents in parallel to explore all solution paths. Every feasible approach
must be investigated and compared before committing. Skip ONLY if user specifies exact
algorithm + architecture (even then, explore at least 2 variants for validation).

## Spec Refinement Criteria

AskUserQuestion MUST cover these areas (skip items already provided by user):
- Target codec, profile, level (e.g., H.264 High Profile Level 4.1)
- Target resolution and framerate (e.g., 1080p@60fps, 4K@30fps)
- Encoder, decoder, or both
- Interface protocol (AXI4, AXI4-Lite, APB, custom)
- Clock frequency target and process node (ASIC vs FPGA)
- Feature scope restrictions (e.g., "TQ only", "intra-only")
- Priority trade-off preference (throughput vs area vs power vs quality)

## 3-Round Chief Review Protocol

Mandatory 3 rounds, coordinated by vcodec-chief-standard-expert:
- **Round 1**: Cross-block data flow completeness, dependencies, performance constraints,
  fixed-point constraints, cross-block issues, [AMBIGUITY]/[CONFLICT] status
- **Round 2**: Convergence assessment. Even if converged, proceed to Round 3
- **Round 3**: Mandatory final quality pass. Remaining gaps → escalate via AskUserQuestion

Review criteria per round:
1. Data flow: inputs/outputs defined at every block boundary
2. Dependencies: which block produces/consumes what data
3. Performance: throughput, latency, bandwidth as specific numbers
4. Fixed-point: bit widths, rounding modes per block
5. Cross-block issues: RDOQ↔Entropy dependency, ME↔MC pipeline, etc.
6. Ambiguities: all resolved or promoted to [ARCHITECTURE_DECISION]

User may override round count: "set iterations to N" → N rounds (minimum 1).

## Requirements JSON Schema

Each requirement MUST have:
- `"id": "REQ-NNN"` — unique, sequential from REQ-001
- Spec section reference for traceability
- Both functional and non-functional requirements receive IDs

## Port Naming Conventions (io_definition.json)

- Inputs: `i_` prefix (e.g., `i_data`, `i_valid`) — NOT suffix `_i`
- Outputs: `o_` prefix (e.g., `o_result`, `o_ready`) — NOT suffix `_o`
- Bidirectional: `io_` prefix (e.g., `io_sda`)
- Clocks: `clk` (single domain) or `{domain}_clk` (e.g., `sys_clk`) — NOT `clk_i`
- Resets: `rst_n` (single domain) or `{domain}_rst_n` (e.g., `sys_rst_n`) — NOT `rst_ni`
- Single clock domain defaults to `sys_clk` / `sys_rst_n`

## Self-Verification Format

Save to `reviews/phase-1-research/research-review.md`:
```
# Phase 1 Review: Research Completeness
- Date: YYYY-MM-DD
- Reviewer: spec-analyst
- Upper Spec: specs/
- Verdict: PASS | FAIL

## Feature Coverage Checklist
| Spec Section | Requirement ID | Status |

## Findings
### [severity] Finding-N: ...

## Verdict
PASS | FAIL: [reason]
```

## Escalation & Stop Conditions

- Spec document not found → report to user, halt
- Conflicting requirements between experts → flag conflict in domain-analysis.md, ask user
- Chief not converged after 3 rounds → escalate remaining gaps to user with specific questions
- Sub-domain expert returns [DOMAIN_UNCERTAINTY] → AskUserQuestion before proceeding

## Final Checklist

- [ ] requirements.json exists and is valid JSON
- [ ] Every requirement has unique `"id": "REQ-NNN"` field
- [ ] io_definition.json exists and is valid JSON
- [ ] io_definition.json port names use `i_`/`o_`/`io_` prefix (NOT suffix)
- [ ] io_definition.json clocks use `{domain}_clk`, resets use `{domain}_rst_n`
- [ ] domain-analysis.md exists with cross-block dependency matrix
- [ ] No unresolved requirement conflicts
- [ ] vcodec-chief-standard-expert declared Architecture-Ready (or gaps escalated)
- [ ] Self-verification verdict produced (PASS or REVIEW_NEEDED)
- [ ] Spec feature count vs requirements.json count documented
- [ ] reviews/phase-1-research/research-review.md saved
- [ ] docs/phase-1-research/solution-tree.md exists
- [ ] docs/phase-1-research/candidate-comparison.md exists
- [ ] docs/phase-1-research/selected-approach.md exists
- [ ] docs/phase-1-research/literature-survey.md exists
- [ ] Tree exploration used maximum parallel agents (8-20 leaf + 4 cross-cutting)
- [ ] domain-consult invoked at least once
- [ ] Algorithm/tool candidates presented with trade-offs (NOT pre-selected)
- [ ] AskUserQuestion used at every ambiguity point (no unresolved assumptions)
