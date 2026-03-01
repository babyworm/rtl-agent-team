---
name: rtl-p6-design-review
description: "Phase 6: Design Review & Documentation with 2-round consistency checks, detailed design notes with decision rationale, and PDF generation support."
---

<Purpose>
Orchestrate Phase 6: Design Review & Documentation — the final quality gate after Phase 5 verification.

Phase 6 produces four deliverables through two parallel waves with 2-round consistency checks:
- **Wave 1 (parallel)**: Code quality review + Design quality review
- **CC1 — Consistency Check 1**: Cross-check Wave 1 outputs for scoring/terminology/severity alignment
- **Wave 2 (parallel, after CC1)**: Design note + Improvement recommendations
- **CC2 — Consistency Check 2**: Cross-check ALL deliverables for narrative coherence, traceability, completeness

This phase answers: "The code works and is verified — but is it GOOD code with GOOD design,
well-documented, and ready for maintenance/handover?"

**Entry Requirement**: Phase 5 `reviews/phase-5-verify/final-compliance.md` must exist with verdict=PASS.

**Sub-skill naming**: Phase 6-specific sub-skills use `p6s` prefix (e.g., `rtl-p6s-*`).
</Purpose>

<Use_When>
- Phase 5 verification is complete (final-compliance.md verdict=PASS)
- Intensive code/design quality review is needed beyond Phase 4/5 gate reviews
- Design documentation (design note) needs to be produced for handover
- Improvement recommendations are needed for the next design iteration
- User requests "design review", "Phase 6", "design note", or "code review documentation"
</Use_When>

<Do_Not_Use_When>
- Phase 5 is not complete (final-compliance.md missing or verdict=FAIL)
- Only a single review type is needed (use the specific agent directly)
- Quick review without full documentation is sufficient (use rtl-critic directly)
- Design is still in active RTL coding (Phase 4) or verification (Phase 5)
</Do_Not_Use_When>

<Why_This_Exists>
Phase 4/5 gate reviews focus on spec compliance and functional correctness.
They answer: "Does the RTL implement the spec?" and "Is it verified?"

Phase 6 goes deeper:
- **Code quality**: Is the code maintainable, consistent, and free of anti-patterns?
- **Design quality**: Is the hierarchical design coherent with sound decisions?
- **Documentation**: Can a new engineer understand the design from documentation alone?
- **Improvements**: What should be fixed in the next iteration?

**Why 2-round consistency checks?**
Wave 1 and Wave 2 agents run independently — each produces its own scoring, terminology,
and severity labels. Without consistency enforcement, the same issue may be rated HIGH in
one document and MEDIUM in another, or identical concepts named differently across documents.
CC1 and CC2 catch and fix these inconsistencies before finalization.

**Why decision rationale in design notes?**
A design note that only describes WHAT was built is half the story. Future engineers need:
- **WHY** this approach was chosen (alternatives considered, trade-offs evaluated)
- **HOW** modules connect (data flow, control dependencies, shared resources)
- **WHAT-IF** considerations (what changes if requirements shift)
</Why_This_Exists>

<Execution_Policy>
- **Phase 5→6 Artifact Gate**: `reviews/phase-5-verify/final-compliance.md` must exist AND contain verdict=PASS
- Wave 1 agents (code-quality-reviewer, design-quality-reviewer) run in parallel
- **CC1**: After Wave 1, cross-check both reviews for consistency (scoring scale, terminology, severity alignment)
- Wave 2 agents (design-note-writer, improvement-analyst) run in parallel AFTER CC1
  (Wave 2 agents reference CC1-corrected Wave 1 outputs)
- **CC2**: After Wave 2, cross-check ALL 4 deliverables for narrative coherence and traceability
- **Document Splitting**: Design notes exceeding line limits are split into multiple files (see splitting rules)
- **PDF Generation**: `make pdf` in `reviews/phase-6-review/` produces combined PDF from all deliverables
- **Phase 6 Completion Quality Gate**: All deliverables must exist AND pass quality checks:
  - `reviews/phase-6-review/code-review.md` — `code-quality-reviewer` verdict must be PASS
  - `reviews/phase-6-review/design-review.md` — `design-quality-reviewer` verdict must be PASS
  - `reviews/phase-6-review/design-note*.md` — `design-note-writer` must produce complete document(s)
  - `reviews/phase-6-review/improvements.md` — `improvement-analyst` must produce recommendations
  - On FAIL: iterate review -> fix cycle (max 2 rounds, same as Phase 5)
  - On agent failure: retry once, then escalate to user
- State tracking: update `.rtl-agent-team/state/rtl-autopilot-state.json` if running within autopilot
</Execution_Policy>

<Steps>
1. **Phase 5->6 Artifact Gate**:
   - Verify `reviews/phase-5-verify/final-compliance.md` exists
   - Read the file and confirm verdict=PASS
   - If missing or FAIL: STOP and report to user — Phase 5 must pass first

2. **Setup review directory**:
   - `mkdir -p reviews/phase-6-review`

3. **Wave 1 — Code & Design Quality Reviews (parallel)**:
   - Launch `code-quality-reviewer` and `design-quality-reviewer` concurrently
   - Wait for both to complete
   - Verify outputs exist:
     - `reviews/phase-6-review/code-review.md`
     - `reviews/phase-6-review/design-review.md`

4. **CC1 — Consistency Check 1 (Wave 1 cross-check)**:
   - Read both Wave 1 deliverables
   - Cross-check for consistency:
     - **Scoring alignment**: Both reviews use the same 1-10 scale interpretation
     - **Terminology alignment**: Same concepts use the same terms across documents
     - **Severity alignment**: Same issue receives the same severity (HIGH/MEDIUM/LOW) in both
     - **Finding cross-reference**: Issues found by both reviewers reference each other
   - If inconsistencies found: correct the affected documents (edit in-place)
   - Log CC1 results as a section appended to each document

5. **Wave 2 — Design Note & Improvement Analysis (parallel)**:
   - Launch `design-note-writer` and `improvement-analyst` concurrently
   - Both reference CC1-corrected Wave 1 outputs for richer analysis
   - **Design note requirements** (see Design_Note_Requirements section):
     - Decision rationale (WHY), module connections (HOW), trade-offs
     - D2 diagrams for architecture/block structure, Mermaid for pipelines/FSMs
     - Split into multiple files if exceeding line limits
   - Wait for both to complete
   - Verify outputs exist:
     - `reviews/phase-6-review/design-note*.md` (single or split files)
     - `reviews/phase-6-review/improvements.md`

6. **CC2 — Consistency Check 2 (all deliverables cross-check)**:
   - Read ALL deliverables (code-review, design-review, design-note*, improvements)
   - Cross-check for consistency across ALL documents:
     - **Narrative coherence**: Do the documents tell a consistent story?
     - **Traceability**: Can every improvement recommendation be traced to a review finding?
     - **Completeness**: Does the design note cover all modules reviewed in code-review?
     - **Terminology**: Consistent naming across all 4+ documents
     - **No contradictions**: No conflicting statements between documents
   - If inconsistencies found: correct the affected documents (edit in-place)
   - Log CC2 results as a section appended to each document

7. **Phase 6 Completion Quality Gate**:
   - Verify all deliverables exist
   - Verify `code-review.md` and `design-review.md` contain verdict=PASS
   - If either verdict is FAIL: pass findings to relevant Wave 1 agent for correction, re-run Wave 1 -> CC1 -> Wave 2 -> CC2 (max 2 rounds)
   - Report summary to user with key highlights from each deliverable

8. **PDF Generation (optional)**:
   - If user requests PDF: run `make pdf` in `reviews/phase-6-review/`
   - Makefile handles: D2 + Mermaid extraction -> PNG rendering -> pandoc + xelatex -> PDF
   - Requires: pandoc, xelatex (texlive-xetex), d2 (D2 CLI), mmdc (mermaid-cli)

9. **Final Summary Report**:
   - Code quality: average score, worst modules, HIGH finding count
   - Design quality: hierarchical consistency status, design debt count
   - Design note: page count, module coverage, document split info
   - Improvements: quick win count, total recommendation count
   - CC1/CC2: inconsistencies found and corrected count
</Steps>

<Design_Note_Requirements>
The design note is the primary deliverable of Phase 6. It must be comprehensive enough
for a new engineer to understand the complete design without reading RTL source code.

**Mandatory content per module**:
1. **Purpose & Context**: What does this module do? Where does it sit in the hierarchy?
2. **Decision Rationale (WHY)**:
   - Why was this approach chosen over alternatives?
   - What trade-offs were evaluated? (area vs. speed, complexity vs. flexibility)
   - What constraints drove the design? (timing, interface, standard requirements)
   - What alternatives were considered and rejected? (with reasons)
3. **Module Connections (HOW)**:
   - Data flow: Where does input come from? Where does output go?
   - Control dependencies: What module controls this one? What does this one control?
   - Shared resources: What is shared with other modules? (memories, buses, clocks)
   - Timing relationships: Latency from input to output, pipeline stages
4. **I/O Table**: Verified against actual RTL ports (port name, width, direction, description)
5. **Internal Structure**: D2 block diagram showing sub-modules, registers, muxes
6. **Algorithm Description**: What algorithm is implemented? Key equations/transforms
7. **FSM Diagrams**: Mermaid state diagram for every FSM in the module (NOT ASCII art)
8. **Timing Diagrams**: Key timing waveforms (handshake, pipeline stages)
9. **Edge Cases & Gotchas**: What can go wrong? What are the corner cases?
10. **What-If Considerations**: What changes if requirements shift? (e.g., wider data path, new mode)

**System-level sections**:
- Architecture overview with D2 block diagram
- System data flow and control flow
- Clock and reset architecture
- Mode operations and configuration
- Verification summary from Phase 5

**Document Splitting Rules**:
| Total Lines | Strategy | File Structure |
|-------------|----------|----------------|
| <= 300 | Single file | `design-note.md` |
| 300 - 800 | 2-3 files | `design-note-overview.md` + `design-note-{topic}.md` + `design-note-appendix.md` |
| > 800 | Per-module files | `design-note-overview.md` + `design-note-{module}.md` per module + `design-note-appendix.md` |

When splitting:
- `design-note-overview.md`: Architecture overview, system-level sections, decision rationale summary
- `design-note-{module}.md`: Per-module detailed documentation (all 10 mandatory items)
- `design-note-appendix.md`: Verification summary, glossary, cross-references

The Makefile in `reviews/phase-6-review/` automatically discovers and orders split files for PDF generation.
</Design_Note_Requirements>

<PDF_Generation>
A Makefile is provided at `reviews/phase-6-review/Makefile` for generating PDF from design note markdown files.

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
| pandoc | `sudo apt install pandoc` | Markdown to LaTeX conversion |
| xelatex | `sudo apt install texlive-xetex texlive-fonts-recommended` | LaTeX to PDF |
| d2 | `curl -fsSL https://d2lang.com/install.sh \| sh -s --` | D2 block diagram rendering (optional, gracefully skipped) |
| mmdc | `npm install -g @mermaid-js/mermaid-cli` | Mermaid flow/FSM diagram rendering (optional, gracefully skipped) |

**Pipeline**:
1. Discover design-note*.md files (ordered: overview -> modules (sorted) -> appendix)
2. Extract D2 code blocks (block diagrams) and Mermaid code blocks (flows/FSMs) from markdown
3. Render D2 blocks to PNG via d2 CLI (skipped if d2 not installed)
4. Render Mermaid blocks to PNG via mmdc (skipped if mmdc not installed)
5. Replace diagram blocks with image references in preprocessed markdown
6. Combine all markdown files with page breaks
7. Generate PDF via pandoc + xelatex with table of contents

**Features**:
- Automatic document ordering (overview first, appendix last)
- D2 block diagram rendering + Mermaid flow/FSM diagram rendering
- Table of contents with 3-level depth
- Section numbering
- Syntax-highlighted code blocks
- Clickable links
</PDF_Generation>

<Tool_Usage>
```
# ============================================================
# Phase 5->6 Artifact Gate
# ============================================================
Read("reviews/phase-5-verify/final-compliance.md")
# -> Verify verdict=PASS. If FAIL or missing -> STOP.

Bash("mkdir -p reviews/phase-6-review")

# ============================================================
# Wave 1: Code Quality + Design Quality (parallel)
# ============================================================
Task(subagent_type="rtl-agent-team:code-quality-reviewer",
     model="opus",
     prompt="Perform intensive per-module code quality review for Phase 6.
Read requirements.json, docs/phase-3-uarch/*.md for context.
Read ALL rtl/*/*.sv files for full code review.
Read reviews/phase-4-rtl/design-review.md for prior findings to track.
Read reviews/phase-5-verify/*.md for verification-discovered issues.
Score each module on 5 dimensions (correctness, synthesizability, style, maintainability, testability) on 1-10 scale.
Detect anti-patterns: magic numbers, deep nesting, oversized modules, code duplication.
Assess cross-module consistency: naming, FSM style, parameter usage.
Track resolution of Phase 4/5 findings.
Save comprehensive review to reviews/phase-6-review/code-review.md.")

Task(subagent_type="rtl-agent-team:design-quality-reviewer",
     model="opus",
     prompt="Perform cross-phase design quality review for Phase 6.
Read ALL design artifacts in order: requirements.json -> architecture.md -> docs/phase-3-uarch/*.md -> rtl/*/*.sv.
Read Phase 4/5 review results for context.
Build hierarchical consistency matrix: trace every REQ through Spec->Arch->uArch->RTL.
Document major design decisions with rationale and trade-off assessment.
Assess interface quality (coupling, cohesion) for all module boundaries.
Evaluate scalability/extensibility of the current design.
Inventory design debt (TODOs, workarounds, known limitations).
Classify Phase 5 bugs as design-level vs implementation-level.
Save comprehensive review to reviews/phase-6-review/design-review.md.")

# Wait for Wave 1 completion, then verify outputs exist

# ============================================================
# CC1: Consistency Check 1 (Wave 1 cross-check)
# ============================================================
# Read both Wave 1 deliverables
# Cross-check: scoring alignment, terminology, severity, finding cross-references
# Correct inconsistencies in-place
# Append CC1 log section to each document

# ============================================================
# Wave 2: Design Note + Improvement Analysis (parallel)
# ============================================================
Task(subagent_type="rtl-agent-team:design-note-writer",
     model="opus",
     prompt="Write comprehensive design note for Phase 6.
Read ALL artifacts: requirements.json, architecture.md, docs/phase-3-uarch/*.md, rtl/*/*.sv.
Read CC1-corrected Phase 6 reviews: reviews/phase-6-review/code-review.md, reviews/phase-6-review/design-review.md.
Read Phase 4/5 reviews for context.

CRITICAL — Decision Rationale:
For EVERY module, document:
- WHY this approach was chosen (alternatives considered, trade-offs evaluated)
- HOW this module connects to others (data flow, control dependencies, shared resources)
- WHAT-IF considerations (what changes if requirements shift)

CRITICAL — Diagrams (D2 + Mermaid):
Use D2 for: architecture overview block diagram, per-module internal structure block diagram.
Use Mermaid for: FSM state diagrams, pipeline timing, data/control flow.
Do NOT use ASCII art for any diagram.

CRITICAL — Document Splitting:
If total content exceeds 300 lines, split into multiple files:
- design-note-overview.md: Architecture overview, system-level, decision rationale summary
- design-note-{module}.md: Per-module detailed documentation
- design-note-appendix.md: Verification summary, glossary, cross-references
If <= 300 lines: single design-note.md

For each RTL module document ALL 10 mandatory items (see SKILL.md Design_Note_Requirements).
Save to reviews/phase-6-review/design-note.md (or split files).")

Task(subagent_type="rtl-agent-team:improvement-analyst",
     model="opus",
     prompt="Analyze all review findings and produce prioritized improvement recommendations for Phase 6.
Read CC1-corrected Phase 6 reviews: reviews/phase-6-review/code-review.md, reviews/phase-6-review/design-review.md.
Read Phase 4/5 reviews for additional context.
Collect and deduplicate all findings across reviews.
Categorize: Functional Enhancement, Performance Optimization, Code Quality, Test Enhancement, Documentation, Design Debt.
Assess Impact (HIGH/MEDIUM/LOW) and Effort (HIGH/MEDIUM/LOW) for each.
Build Impact x Effort matrix with 4-quadrant classification.
Highlight Quick Wins (HIGH impact, LOW effort).
For each recommendation: specify WHERE (file:line), WHAT (change), HOW (approach).
Build long-term improvement roadmap (Phase A: immediate, Phase B: next iteration, Phase C: future).
Save to reviews/phase-6-review/improvements.md.")

# Wait for Wave 2 completion, then verify outputs exist

# ============================================================
# CC2: Consistency Check 2 (all deliverables cross-check)
# ============================================================
# Read ALL deliverables
# Cross-check: narrative coherence, traceability, completeness, terminology, no contradictions
# Correct inconsistencies in-place
# Append CC2 log section to each document

# ============================================================
# Phase 6 Completion Gate
# ============================================================
# Verify all deliverables exist
# Verify code-review.md and design-review.md contain verdict=PASS
# Report summary to user

# ============================================================
# PDF Generation (optional, on user request)
# ============================================================
# Bash("cd reviews/phase-6-review && make pdf")
```
</Tool_Usage>

<Consistency_Check_Protocol>
**CC1 — After Wave 1 (Code Review + Design Review)**:

| Check Item | What to Compare | Fix Action |
|------------|----------------|------------|
| Scoring scale | Both use 1-10 with same anchor points | Normalize to shared scale definition |
| Severity labels | HIGH/MEDIUM/LOW applied consistently | Re-rate using shared criteria |
| Terminology | Same concepts named identically | Adopt canonical terms |
| Finding overlap | Same issue in both reviews | Add cross-references |
| Module names | Consistent module naming | Standardize to rtl/ directory names |

**CC2 — After Wave 2 (All 4+ Deliverables)**:

| Check Item | What to Compare | Fix Action |
|------------|----------------|------------|
| Narrative coherence | Story told consistently across docs | Align narrative arc |
| Traceability | Every improvement traces to a finding | Add missing traces |
| Completeness | Design note covers all reviewed modules | Add missing modules |
| Terminology | All docs use same terms | Global terminology pass |
| No contradictions | No conflicting statements | Resolve conflicts |
| Diagram consistency | D2/Mermaid diagrams match textual descriptions | Update mismatched diagrams |

Each CC round:
1. Read all target documents
2. Build comparison table
3. List all inconsistencies found
4. Fix each inconsistency in-place (Edit tool)
5. Append CC log section at the end of each corrected document:
   ```markdown
   ## Consistency Check {N} Log
   - Date: YYYY-MM-DD
   - Items checked: {count}
   - Inconsistencies found: {count}
   - Corrections applied: {list}
   ```
</Consistency_Check_Protocol>

<Examples>
<Good>
Phase 5 complete with verdict=PASS. Invoke rtl-p6-design-review skill.
-> Artifact Gate: reviews/phase-5-verify/final-compliance.md exists, verdict=PASS.
-> Wave 1: code-quality-reviewer scores all modules (avg 8.2/10), finds 3 HIGH issues.
   design-quality-reviewer confirms hierarchical consistency, identifies 2 design debt items.
-> CC1: Found 2 inconsistencies — severity mismatch for FSM naming issue (HIGH vs MEDIUM),
   different terms for same concept ("pipeline stall" vs "backpressure"). Corrected both.
-> Wave 2: design-note-writer produces 950-line design note, split into:
   design-note-overview.md (180 lines), design-note-entropy.md (200 lines),
   design-note-itq.md (220 lines), design-note-appendix.md (150 lines).
   Each module section includes WHY/HOW/WHAT-IF with D2 block diagrams and Mermaid flow/FSM diagrams.
   improvement-analyst produces 15 recommendations: 5 quick wins, 3 major projects, 4 fill-ins, 3 skips.
-> CC2: Found 1 inconsistency — improvement recommendation references "entropy_decoder"
   but design note uses "entropy_dec". Standardized to "entropy_dec".
-> Completion Gate: all deliverables verified. Summary reported to user.
-> PDF: `make pdf` generates design-note.pdf (12 pages, 2 D2 + 2 Mermaid diagrams rendered).
</Good>
<Good>
Running within rtl-autopilot after Phase 5.
-> State file updated: phase=6, sub_phase="wave-1".
-> Wave 1 completes. State updated: sub_phase="cc1".
-> CC1 completes. State updated: sub_phase="wave-2".
-> Wave 2 completes. State updated: sub_phase="cc2".
-> CC2 completes. State updated: phase=6, status="complete".
-> Autopilot continues to final summary.
</Good>
<Bad>
Phase 5 final-compliance.md has verdict=FAIL.
-> Do NOT proceed to Phase 6. Report to user: "Phase 5 must pass before Phase 6 can begin."
</Bad>
<Bad>
Skipping CC1 and going directly to Wave 2.
-> NEVER skip consistency checks. Wave 2 agents depend on CC1-corrected Wave 1 outputs.
</Bad>
<Bad>
Design note only describes WHAT each module does, without WHY or HOW.
-> Every module section MUST include decision rationale (WHY), module connections (HOW),
   and what-if considerations. A description-only note is incomplete.
</Bad>
<Bad>
Producing a single 1200-line design-note.md without splitting.
-> Documents exceeding 800 lines MUST be split into per-module files.
</Bad>
</Examples>

<Phase_7_Exploration_Mode>
When invoked with exploration mode (user requests "Phase 7", "exploration", "free exploration"):
- **Entry**: Phase 6 completion is recommended but NOT required (Phase 7 is exempt from pipeline gates)
- **Guard Rails**:
  - Pipeline absolute rules (Phase Gate) do NOT apply — free exploration allowed
  - Existing `rtl/` files must NOT be directly modified (use exploration branch)
  - Results stored in `docs/phase-7-exploration/exploration-notes.md`
  - Successful exploration -> ADR creation + formal pipeline integration proposal
  - Scope: algorithm alternatives, optimization experiments, technology evaluation
  - Prohibited: production RTL changes, verification bypass, feature additions without spec change
- **Output**: `reviews/phase-7-exploration/exploration-review.md` with findings and integration recommendations
</Phase_7_Exploration_Mode>

<Parallel_Execution_Pattern>
Phase 6 uses a 2-wave parallel execution pattern with 2-round consistency checks:

```
Wave 1 (parallel) -> CC1 -> Wave 2 (parallel) -> CC2 -> Completion Gate
```

**Wave 1 (parallel, independent)**:
- `code-quality-reviewer` + `design-quality-reviewer` run concurrently via `run_in_background: true`
- Wait for both to complete before CC1

**CC1 (sequential)**:
- Cross-check Wave 1 outputs for consistency
- Fix inconsistencies in-place
- Must complete before Wave 2 starts

**Wave 2 (parallel, depends on CC1)**:
- `design-note-writer` + `improvement-analyst` run concurrently
- Both reference CC1-corrected Wave 1 outputs
- Wait for both to complete before CC2

**CC2 (sequential)**:
- Cross-check ALL deliverables for consistency
- Fix inconsistencies in-place
- Must complete before Completion Gate

Task tool usage:
- Use `run_in_background: true` for independent agents within a wave
- Wait for all background tasks before CC and dependent wave
- Collect results via TaskOutput before proceeding
</Parallel_Execution_Pattern>

<Escalation_And_Stop_Conditions>
- **Phase 5 not complete**: STOP, report that Phase 5 final-compliance.md must exist with verdict=PASS
- **Agent fails after 1 retry**: escalate to user with the specific error
- **Wave 1 partial failure**: retry the failed agent once. If still fails, proceed with available results and note the gap
- **Wave 2 partial failure**: retry the failed agent once. If still fails, report partial results to user
- **CC finds > 10 inconsistencies**: flag as systematic issue, consider re-running the problematic wave
- **Document splitting fails**: fall back to single file, warn user about length
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Phase 5->6 Artifact Gate passed (final-compliance.md exists, verdict=PASS)?
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
</Final_Checklist>
