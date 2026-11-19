# Phase 6 Design Review Policy


## Execution Rules

- **Phase 5→6 Artifact Gate**: `reviews/phase-5-verify/final-compliance.md` must exist AND verdict=PASS
- Wave 1 agents run in parallel; CC1 after Wave 1 complete
- Wave 2 agents run in parallel AFTER CC1; CC2 after Wave 2 complete
- **Document Splitting**: Design notes exceeding line limits are split (see splitting rules)
- **PDF Generation**: `make pdf` in `reviews/phase-6-review/`
- **Quality Gate**: All deliverables must exist AND pass quality checks
  - On FAIL: fix the named inconsistencies once, then report what remains. Do not repeat a wave.
  - On agent failure: retry once, then escalate to user
- State tracking: update `.rat/state/rat-auto-design-state.json` if running within autopilot

## Design Note Requirements

**Mandatory content per module**:
1. **Purpose & Context**: What this module does, and where it sits. One to three sentences.
2. **Decision Rationale (WHY)**: Why this approach. The trade-off. The rejected alternative.
3. **Module Connections (HOW)**: Data flow, control dependencies, shared resources, timing
4. **I/O Table**: Verified against actual RTL ports (port name, width, direction, description)
5. **Internal Structure**: ARM SVG inserted as PNG. Sub-modules, registers, muxes.
6. **Registers**: Name, offset, access, reset, bit-field PNG, and one explained field per field. No register: `_None._`.
7. **Algorithm Description**: Key equations or transforms
8. **FSM**: ARM SVG inserted as PNG for every FSM. No ASCII art.
9. **Timing**: Latency, throughput, and the handshake or pipeline waveform as an ARM SVG inserted as PNG
10. **Edge Cases & Gotchas**: Corner cases, and what goes wrong
11. **What-If Considerations**: What changes if a requirement shifts

**System-level sections**: Architecture overview as an ARM SVG inserted as PNG, data/control flow, clock/reset architecture, mode operations, verification summary

**Prose**: the heading states the point. The first sentence is the conclusion. At most three sentences in a paragraph. One idea per section.

**Figures**: if a diagram-design skill is available, use it to draw the SVG. Otherwise draw the SVG. White background, thin black strokes, left-to-right flow, nested rectangles, signal names on the wires. Insert the PNG and keep the SVG beside it. Convert with `rsvg-convert` or `magick`. Do not paste the SVG. Do not leave a D2 or Mermaid fence.

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
| Diagram consistency | Each PNG matches the text, and the SVG sits beside it | Replace the mismatched figure |

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
| rsvg-convert or magick | librsvg, or ImageMagick | SVG to the PNG the note already inserts |

**Pipeline**: Discover design-note*.md. Each figure is already a PNG next to its SVG. Combine, then pandoc + xelatex, PDF with TOC.

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
  - [ ] Design note figures are ARM SVG inserted as PNG, and every register field is explained?
  - [ ] Document splitting rules applied if needed?
- [ ] CC2 completed:
  - [ ] Narrative coherence verified?
  - [ ] Traceability verified?
  - [ ] Completeness verified?
  - [ ] CC2 log appended to all documents?
- [ ] All Phase 6 deliverables verified?
- [ ] Summary report generated with key highlights?
