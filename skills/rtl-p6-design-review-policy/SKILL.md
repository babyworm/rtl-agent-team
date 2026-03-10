---
name: rtl-p6-design-review-policy
description: "Policy rules, design note requirements, consistency check protocol, PDF generation pipeline, escalation rules, and checklists for Phase 6 design review. Pure reference — no orchestration."
user-invocable: false
---

# Phase 6 Design Review Policy

## Why Phase 6 Exists

Phase 4/5 gate reviews focus on spec compliance and functional correctness.
Phase 6 goes deeper:
- **Code quality**: Is the code maintainable, consistent, and free of anti-patterns?
- **Design quality**: Is the hierarchical design coherent with sound decisions?
- **Documentation**: Can a new engineer understand the design from documentation alone?
- **Improvements**: What should be fixed in the next iteration?

**Why 2-round consistency checks?**
Wave 1 and Wave 2 agents run independently — each produces its own scoring, terminology,
and severity labels. Without consistency enforcement, the same issue may be rated HIGH in
one document and MEDIUM in another, or identical concepts named differently across documents.

**Why decision rationale in design notes?**
A design note that only describes WHAT was built is half the story. Future engineers need:
- **WHY** this approach was chosen (alternatives considered, trade-offs evaluated)
- **HOW** modules connect (data flow, control dependencies, shared resources)
- **WHAT-IF** considerations (what changes if requirements shift)

## Execution Rules

- **Phase 5→6 Artifact Gate**: `reviews/phase-5-verify/final-compliance.md` must exist AND verdict=PASS
- Wave 1 agents run in parallel; CC1 after Wave 1 complete
- Wave 2 agents run in parallel AFTER CC1; CC2 after Wave 2 complete
- **Document Splitting**: Design notes exceeding line limits are split (see splitting rules)
- **PDF Generation**: `make pdf` in `reviews/phase-6-review/`
- **Quality Gate**: All deliverables must exist AND pass quality checks
  - On FAIL: iterate review → fix cycle (max 2 rounds)
  - On agent failure: retry once, then escalate to user
- State tracking: update `.rtl-agent-team/state/rat-auto-design-state.json` if running within autopilot

## Design Note Requirements

**Mandatory content per module (all 10 items)**:
1. **Purpose & Context**: What does this module do? Where in the hierarchy?
2. **Decision Rationale (WHY)**: Why this approach? Trade-offs evaluated? Constraints? Alternatives rejected?
3. **Module Connections (HOW)**: Data flow, control dependencies, shared resources, timing
4. **I/O Table**: Verified against actual RTL ports (port name, width, direction, description)
5. **Internal Structure**: D2 block diagram showing sub-modules, registers, muxes
6. **Algorithm Description**: Key equations/transforms
7. **FSM Diagrams**: Mermaid state diagram for every FSM (NOT ASCII art)
8. **Timing Diagrams**: Key timing waveforms (handshake, pipeline stages)
9. **Edge Cases & Gotchas**: Corner cases, what can go wrong
10. **What-If Considerations**: What changes if requirements shift

**System-level sections**: Architecture overview (D2), data/control flow, clock/reset architecture, mode operations, verification summary

**Document Splitting Rules**:

| Total Lines | Strategy | File Structure |
|-------------|----------|----------------|
| <= 300 | Single file | `design-note.md` |
| 300 - 800 | 2-3 files | `design-note-overview.md` + `design-note-{topic}.md` + `design-note-appendix.md` |
| > 800 | Per-module files | `design-note-overview.md` + `design-note-{module}.md` per module + `design-note-appendix.md` |

## Consistency Check Protocol

### CC1 — After Wave 1 (Code Review + Design Review)

| Check Item | What to Compare | Fix Action |
|------------|----------------|------------|
| Scoring scale | Both use 1-10 with same anchor points | Normalize to shared scale |
| Severity labels | HIGH/MEDIUM/LOW applied consistently | Re-rate using shared criteria |
| Terminology | Same concepts named identically | Adopt canonical terms |
| Finding overlap | Same issue in both reviews | Add cross-references |
| Module names | Consistent module naming | Standardize to rtl/ directory names |

### CC2 — After Wave 2 (All 4+ Deliverables)

| Check Item | What to Compare | Fix Action |
|------------|----------------|------------|
| Narrative coherence | Story told consistently across docs | Align narrative arc |
| Traceability | Every improvement traces to a finding | Add missing traces |
| Completeness | Design note covers all reviewed modules | Add missing modules |
| Terminology | All docs use same terms | Global terminology pass |
| No contradictions | No conflicting statements | Resolve conflicts |
| Diagram consistency | D2/Mermaid match textual descriptions | Update mismatched diagrams |

**CC log format** (appended to each corrected document):
```markdown
## Consistency Check {N} Log
- Date: YYYY-MM-DD
- Items checked: {count}
- Inconsistencies found: {count}
- Corrections applied: {list}
```

## PDF Generation

**Usage**:
```bash
cd reviews/phase-6-review
make pdf        # Generate design-note.pdf
make clean      # Remove generated files
make check-deps # Verify required tools
```

**Required tools**:

| Tool | Package | Purpose |
|------|---------|---------|
| pandoc | `sudo apt install pandoc` | Markdown to LaTeX |
| xelatex | `sudo apt install texlive-xetex texlive-fonts-recommended` | LaTeX to PDF |
| d2 | `curl -fsSL https://d2lang.com/install.sh \| sh -s --` | D2 block diagrams (optional) |
| mmdc | `npm install -g @mermaid-js/mermaid-cli` | Mermaid diagrams (optional) |

**Pipeline**: Discover design-note*.md → extract D2/Mermaid → render PNGs → replace blocks → combine → pandoc + xelatex → PDF with TOC

**Phase 7 Exploration**: For free exploration mode, see `rtl-p7-exploration-policy`.

## Escalation & Stop Conditions

- **Phase 5 not complete**: STOP, report that Phase 5 must pass first
- **Agent fails after 1 retry**: escalate to user with the specific error
- **Wave 1 partial failure**: retry once; if still fails, proceed with available results and note gap
- **Wave 2 partial failure**: retry once; if still fails, report partial results to user
- **CC finds > 10 inconsistencies**: flag as systematic issue, consider re-running the problematic wave
- **Document splitting fails**: fall back to single file, warn user about length

## Final Checklist

- [ ] Phase 5→6 Artifact Gate passed (final-compliance.md exists, verdict=PASS)?
- [ ] reviews/phase-6-review/ directory created?
- [ ] Wave 1 completed:
  - [ ] reviews/phase-6-review/code-review.md exists?
  - [ ] reviews/phase-6-review/design-review.md exists?
- [ ] CC1 completed:
  - [ ] Scoring alignment verified?
  - [ ] Terminology alignment verified?
  - [ ] Severity alignment verified?
  - [ ] CC1 log appended to Wave 1 documents?
- [ ] Wave 2 completed:
  - [ ] reviews/phase-6-review/design-note*.md exists?
  - [ ] reviews/phase-6-review/improvements.md exists?
  - [ ] Design note includes decision rationale (WHY/HOW/WHAT-IF)?
  - [ ] Design note includes D2 block diagrams + Mermaid flow/FSM diagrams?
  - [ ] Document splitting rules applied if needed?
- [ ] CC2 completed:
  - [ ] Narrative coherence verified?
  - [ ] Traceability verified?
  - [ ] Completeness verified?
  - [ ] CC2 log appended to all documents?
- [ ] All Phase 6 deliverables verified?
- [ ] Summary report generated with key highlights?
