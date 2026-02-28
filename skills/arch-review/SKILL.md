---
name: arch-review
description: "This skill should be used when conducting architecture review with area/performance/power tradeoff analysis. Saves review reports to reviews/ directory."
---

<Purpose>
Review RTL architecture for consistency with the microarchitecture spec, timing feasibility,
and code quality. All agents operate READ-ONLY — no modifications are made.
Outputs: reviews/phase-2-architecture/architecture-review.md with findings per reviewer.
</Purpose>

<Use_When>
- RTL implementation is complete and needs architecture sign-off
- Microarchitecture spec (docs/phase-3-uarch/*.md) exists for comparison
- Pre-tapeout architecture review gate
- Suspecting architectural mismatch after late RTL changes
</Use_When>

<Do_Not_Use_When>
- RTL is not yet lint-clean (fix lint first with rtl-lint-check)
- Only functional bugs need diagnosis (use rtl-bug-repro instead)
- Architecture changes are also requested (arch-review is READ-ONLY)
</Do_Not_Use_When>

<Why_This_Exists>
Architecture review catches structural mismatches between spec and implementation
that functional tests cannot detect. Three independent reviewers with different
focus areas (structure, timing, quality) provide broader coverage than a single pass.
</Why_This_Exists>

<Execution_Policy>
- All three agents run in parallel, READ-ONLY
- rtl-architect checks spec-to-RTL consistency
- timing-advisor checks pipeline depth, clock domain structure, timing feasibility
- rtl-critic checks code quality, maintainability, synthesis-friendliness
- Findings aggregated into single report — no RTL changes
</Execution_Policy>

<Steps>
1. Read requirements.json, docs/phase-3-uarch/*.md, and rtl/*/*.sv to pass context
2. `mkdir -p reviews/phase-2-architecture`
3. Run three agents in parallel (all READ-ONLY):
   a. rtl-architect: spec vs RTL structure review **+ requirements.json full coverage check**
   b. timing-advisor: pipeline and timing feasibility review
   c. rtl-critic: code quality and synthesis review
4. **rtl-architect produces a Feature Coverage Checklist (MANDATORY output):**
   - Read requirements.json and check every REQ-NNN item against RTL implementation
   - Per-requirement status:
     ```
     REQ-001: implemented in cabac_encoder.sv — COVERED
     REQ-002: implemented in input_buffer.sv — COVERED
     REQ-005: NOT FOUND in any RTL module — MISSING
     REQ-008: partially implemented in transform.sv (missing edge case) — PARTIAL
     ```
   - Summary verdict:
     ```
     VERDICT: PASS — all [N] requirements covered in RTL
     ```
     or:
     ```
     VERDICT: FAIL — [M] of [N] requirements have spec violations
       MISSING: REQ-005, REQ-012
       PARTIAL: REQ-008
     ```
5. Aggregate findings into `reviews/phase-2-architecture/architecture-review.md`
6. **Ensure review result is saved in standard review Markdown format:**
   - If the file already exists (from Phase 2 Quality Gate), update it with the latest review results
   - Format:
     ```markdown
     # Phase 2 Review: Architecture Review
     - Date: YYYY-MM-DD
     - Reviewer: rtl-architect, timing-advisor, rtl-critic
     - Upper Spec: requirements.json, docs/phase-3-uarch/*.md
     - Verdict: PASS | FAIL

     ## Feature Coverage Checklist
     | REQ ID | RTL Module | Status |
     |--------|-----------|--------|

     ## Findings
     ### [severity] Finding-N: ...

     ## Verdict
     PASS | FAIL: [reason]
     ```
7. Categorize issues: BLOCKER / WARN / SUGGESTION
   - Any MISSING requirement is automatically a BLOCKER
   - Any PARTIAL requirement is at minimum a WARN
</Steps>

<Tool_Usage>
```
Bash("mkdir -p reviews/phase-2-architecture")

Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="READ-ONLY review. (1) Read requirements.json and check every REQ-NNN item for implementation in rtl/. Produce a Feature Coverage Checklist with per-REQ status: COVERED, PARTIAL, or MISSING. (2) Compare docs/phase-3-uarch/*.md against rtl/. List any spec-RTL mismatches, missing modules, or unspecified additions. Verify port naming follows project convention: i_ prefix for inputs, o_ prefix for outputs, io_ prefix for bidirectional. Save the review result to reviews/phase-2-architecture/architecture-review.md in standard review Markdown format with Date, Reviewer (rtl-architect, timing-advisor, rtl-critic), Upper Spec (requirements.json, docs/phase-3-uarch/*.md), Verdict, Feature Coverage Checklist table, Findings, and Verdict sections. If the file already exists, update it with the latest review results. Output final verdict: VERDICT: PASS or VERDICT: FAIL — [N] spec violations found.")

Task(subagent_type="rtl-agent-team:timing-advisor",
     prompt="READ-ONLY review. Analyze rtl/ pipeline depth, clock domains ({domain}_clk naming, e.g. sys_clk), and reset strategy ({domain}_rst_n naming, e.g. sys_rst_n). Flag timing feasibility concerns and any clock/reset naming violations.")

Task(subagent_type="rtl-agent-team:rtl-critic",
     prompt="READ-ONLY review. Assess rtl/ code quality: synthesizability, coding style (lowRISC base with project overrides: i_/o_/io_ port prefixes, {domain}_clk/{domain}_rst_n naming, logic only, u_ instance prefix, gen_ generate prefix), maintainability. List issues with severity.")
```
</Tool_Usage>

<Coding_Convention_Requirements>
Reviewers must verify these project-specific conventions (overrides lowRISC defaults):
- Port prefixes: `i_` (input), `o_` (output), `io_` (bidirectional) — NOT suffix `_i`/`_o`
- Clock naming: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
- Reset naming: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
- Data types: `logic` only — `reg`/`wire` forbidden
- Instance prefix: `u_` (e.g., `u_fifo`) — generate prefix: `gen_`
- Any deviation from these conventions is at minimum a WARN finding
</Coding_Convention_Requirements>

<Examples>
<Good>
Three parallel reviews complete; rtl-architect finds missing error-handling state in FSM (BLOCKER);
timing-advisor flags 7-stage pipeline exceeding timing budget (WARN); rtl-critic notes inconsistent
reset polarity (WARN). All reported in reviews/phase-2-architecture/architecture-review.md, no RTL touched.
</Good>
<Bad>
Having rtl-architect also fix the issues it finds — mixing review with implementation defeats
the READ-ONLY audit purpose.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- BLOCKER found → surface immediately to user before completing report
- Spec document missing → halt, inform user that docs/phase-3-uarch/*.md is required
- Conflicting findings between reviewers → include both perspectives in report
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All three agents ran READ-ONLY with no file modifications
- [ ] reviews/phase-2-architecture/architecture-review.md written with findings per reviewer
- [ ] **Feature Coverage Checklist included with per-REQ-NNN status**
- [ ] **rtl-architect verdict output: VERDICT: PASS or VERDICT: FAIL — [N] spec violations found**
- [ ] Any MISSING requirement categorized as BLOCKER
- [ ] Issues categorized as BLOCKER / WARN / SUGGESTION
- [ ] BLOCKERs highlighted prominently in report
- [ ] **reviews/phase-2-architecture/architecture-review.md saved (or updated) with review result**
</Final_Checklist>
