---
name: design-review-phase
description: "This skill should be used when Phase 5 verification is complete and intensive design review + documentation is needed. Orchestrates Phase 6: Design Review & Documentation with 4 specialized agents in 2 parallel waves."
---

<Purpose>
Orchestrate Phase 6: Design Review & Documentation — the final quality gate after Phase 5 verification.

Phase 6 produces four deliverables through two parallel waves:
- **Wave 1 (parallel)**: Code quality review + Design quality review
- **Wave 2 (parallel, after Wave 1)**: Design note + Improvement recommendations

This phase answers: "The code works and is verified — but is it GOOD code with GOOD design,
well-documented, and ready for maintenance/handover?"

**Entry Requirement**: Phase 5 `reviews/phase-5-verify/final-compliance.md` must exist with verdict=PASS.
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

These questions were answered ad-hoc in the H.264 TQ project and produced extremely
valuable artifacts (692-line code review, 545-line design review, 57KB design note).
Phase 6 formalizes this process for all RTL projects.
</Why_This_Exists>

<Execution_Policy>
- **Phase 5→6 Artifact Gate**: `reviews/phase-5-verify/final-compliance.md` must exist AND contain verdict=PASS
- Wave 1 agents (code-quality-reviewer, design-quality-reviewer) run in parallel
- Wave 2 agents (design-note-writer, improvement-analyst) run in parallel AFTER Wave 1 completes
  (Wave 2 agents reference Wave 1 outputs for richer analysis)
- **Phase 6 Completion Gate**: All 4 deliverables must exist:
  - `reviews/phase-6-review/code-review.md`
  - `reviews/phase-6-review/design-review.md`
  - `reviews/phase-6-review/design-note.md`
  - `reviews/phase-6-review/improvements.md`
- On agent failure: retry once, then escalate to user
- State tracking: update `.rtl-agent-team/state/rtl-autopilot-state.json` if running within autopilot
</Execution_Policy>

<Steps>
1. **Phase 5→6 Artifact Gate**:
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

4. **Wave 2 — Design Note & Improvement Analysis (parallel)**:
   - Launch `design-note-writer` and `improvement-analyst` concurrently
   - Both reference Wave 1 outputs for richer analysis
   - Wait for both to complete
   - Verify outputs exist:
     - `reviews/phase-6-review/design-note.md`
     - `reviews/phase-6-review/improvements.md`

5. **Phase 6 Completion Gate**:
   - Verify all 4 deliverables exist
   - Report summary to user with key highlights from each deliverable

6. **Final Summary Report**:
   - Code quality: average score, worst modules, HIGH finding count
   - Design quality: hierarchical consistency status, design debt count
   - Design note: page count, module coverage
   - Improvements: quick win count, total recommendation count
</Steps>

<Tool_Usage>
```
# ============================================================
# Phase 5→6 Artifact Gate
# ============================================================
Read("reviews/phase-5-verify/final-compliance.md")
# → Verify verdict=PASS. If FAIL or missing → STOP.

Bash("mkdir -p reviews/phase-6-review")

# ============================================================
# Wave 1: Code Quality + Design Quality (parallel)
# ============================================================
Task(subagent_type="rtl-agent-team:code-quality-reviewer",
     model="opus",
     prompt="Perform intensive per-module code quality review for Phase 6.
Read requirements.json, uarch/*.md for context.
Read ALL rtl/src/*.sv files for full code review.
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
Read ALL design artifacts in order: requirements.json → architecture.md → uarch/*.md → rtl/src/*.sv.
Read Phase 4/5 review results for context.
Build hierarchical consistency matrix: trace every REQ through Spec→Arch→μArch→RTL.
Document major design decisions with rationale and trade-off assessment.
Assess interface quality (coupling, cohesion) for all module boundaries.
Evaluate scalability/extensibility of the current design.
Inventory design debt (TODOs, workarounds, known limitations).
Classify Phase 5 bugs as design-level vs implementation-level.
Save comprehensive review to reviews/phase-6-review/design-review.md.")

# Wait for Wave 1 completion, then verify:
# Read("reviews/phase-6-review/code-review.md")   → exists?
# Read("reviews/phase-6-review/design-review.md")  → exists?

# ============================================================
# Wave 2: Design Note + Improvement Analysis (parallel)
# ============================================================
Task(subagent_type="rtl-agent-team:design-note-writer",
     model="opus",
     prompt="Write comprehensive design note for Phase 6.
Read ALL artifacts: requirements.json, architecture.md, uarch/*.md, rtl/src/*.sv.
Read Phase 4/5/6 reviews for context: reviews/phase-4-rtl/*.md, reviews/phase-5-verify/*.md, reviews/phase-6-review/code-review.md, reviews/phase-6-review/design-review.md.
For each RTL module: document purpose, I/O table (verified against actual ports), internal structure (Mermaid), algorithm, FSM diagrams, timing, edge cases.
Document system-level integration: data flow, control flow, mode operations, reset sequence.
Include verification summary from Phase 5 results.
Produce self-contained document for future maintenance engineers.
Save to reviews/phase-6-review/design-note.md.")

Task(subagent_type="rtl-agent-team:improvement-analyst",
     model="opus",
     prompt="Analyze all review findings and produce prioritized improvement recommendations for Phase 6.
Read Phase 6 reviews: reviews/phase-6-review/code-review.md, reviews/phase-6-review/design-review.md.
Read Phase 4/5 reviews for additional context: reviews/phase-4-rtl/*.md, reviews/phase-5-verify/*.md.
Collect and deduplicate all findings across reviews.
Categorize: Functional Enhancement, Performance Optimization, Code Quality, Test Enhancement, Documentation, Design Debt.
Assess Impact (HIGH/MEDIUM/LOW) and Effort (HIGH/MEDIUM/LOW) for each.
Build Impact×Effort matrix with 4-quadrant classification.
Highlight Quick Wins (HIGH impact, LOW effort).
For each recommendation: specify WHERE (file:line), WHAT (change), HOW (approach).
Build long-term improvement roadmap (Phase A: immediate, Phase B: next iteration, Phase C: future).
Save to reviews/phase-6-review/improvements.md.")

# Wait for Wave 2 completion, then verify:
# Read("reviews/phase-6-review/design-note.md")    → exists?
# Read("reviews/phase-6-review/improvements.md")   → exists?

# ============================================================
# Phase 6 Completion Gate
# ============================================================
# Verify all 4 deliverables exist:
# Bash("ls reviews/phase-6-review/code-review.md reviews/phase-6-review/design-review.md reviews/phase-6-review/design-note.md reviews/phase-6-review/improvements.md")
# Report summary to user
```
</Tool_Usage>

<Examples>
<Good>
Phase 5 complete with verdict=PASS. Invoke design-review-phase skill.
→ Artifact Gate: reviews/phase-5-verify/final-compliance.md exists, verdict=PASS.
→ Wave 1: code-quality-reviewer scores all modules (avg 8.2/10), finds 3 HIGH issues.
   design-quality-reviewer confirms hierarchical consistency, identifies 2 design debt items.
→ Wave 2: design-note-writer produces 45KB design note covering all 8 modules with Mermaid diagrams.
   improvement-analyst produces 15 recommendations: 5 quick wins, 3 major projects, 4 fill-ins, 3 skips.
→ Completion Gate: all 4 deliverables verified. Summary reported to user.
</Good>
<Good>
Running within rtl-autopilot after Phase 5.
→ State file updated: phase=6, sub_phase="wave-1".
→ Wave 1 completes. State updated: sub_phase="wave-2".
→ Wave 2 completes. State updated: phase=6, status="complete".
→ Autopilot continues to final summary.
</Good>
<Bad>
Phase 5 final-compliance.md has verdict=FAIL.
→ Do NOT proceed to Phase 6. Report to user: "Phase 5 must pass before Phase 6 can begin."
</Bad>
<Bad>
Skipping Wave 1 and going directly to Wave 2.
→ NEVER skip Wave 1. Wave 2 agents depend on Wave 1 outputs for richer analysis.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- **Phase 5 not complete**: STOP, report that Phase 5 final-compliance.md must exist with verdict=PASS
- **Agent fails after 1 retry**: escalate to user with the specific error
- **Wave 1 partial failure**: retry the failed agent once. If still fails, proceed with available results and note the gap
- **Wave 2 partial failure**: retry the failed agent once. If still fails, report partial results to user
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Phase 5→6 Artifact Gate passed (final-compliance.md exists, verdict=PASS)?
- [ ] reviews/phase-6-review/ directory created?
- [ ] Wave 1 completed:
  - [ ] reviews/phase-6-review/code-review.md exists?
  - [ ] reviews/phase-6-review/design-review.md exists?
- [ ] Wave 2 completed:
  - [ ] reviews/phase-6-review/design-note.md exists?
  - [ ] reviews/phase-6-review/improvements.md exists?
- [ ] All 4 Phase 6 deliverables verified?
- [ ] Summary report generated with key highlights?
</Final_Checklist>
