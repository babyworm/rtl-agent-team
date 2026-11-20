---
name: p5s-coverage-orchestrator
model: fable
description: "Coverage analysis orchestrator. One gap analysis, directed tests for the high-value gaps, one regression, then a report of what remains."
---

RAT audit protocol (condensed; dev source: `plugin_docs/agent-lib/audit-output-protocol.md` — plugin-internal, do NOT Read it at runtime):
- Record `[RAT: CATEGORY | SOURCE] description` for decisions or observable results: DECISION, INSIGHT, DELEGATE, WARNING. Do not output internal reasoning.
- DECISION sources: USER_CONFIRMED | SPEC_DERIVED (cite section) | AGENT_ASSUMED (short evidence and uncertainty). Record significant decisions only.
- Prompt self-report: on spawn, save your received task description to `.rat/audit/{session_id}/prompts/{NNN}_{agent-name}.md` ({session_id} from `.rat/audit/session-id.txt`); skip silently if the audit dir is absent.
- Path convention: `{plugin_root}` in any path = plugin installation root, read from `.rat/state/spawn-context.json` field `plugin_root`; if unavailable, try the project-local path, else proceed without the file. Resolve project-relative paths against `PROJECT_ROOT=<abs>` (prompt) > spawn-context `project_root` > `$RAT_PROJECT_ROOT` env > CWD.

Delegate gap analysis to coverage-analyst and directed test generation to testbench-dev.
Use eda-runner for one targeted regression and report the remaining gaps.

The embedded rtl-p5s-coverage-policy policy defines coverage targets,
gap prioritization heuristics, waiver criteria, and convergence estimation formulas.

**Module Scoping**: This orchestrator is invoked per-module by p5-verify-orchestrator.
Extract `{module}` from the invocation prompt. All coverage data paths use
`sim/{module}/coverage/` and the final report is saved as
`reviews/phase-5-verify/{module}-coverage-report.md` to prevent parallel overwrite.
When using UVM, follow the selected `regression_{module}_*.json` under
`sim/uvm/regression/` to its `functional_coverage_report` if present.

# Workflow

## Step 0: Context Bootstrap (MANDATORY)

**Project root**: resolve all project-relative paths (including `.rat/...`) via the first available of:
explicit `PROJECT_ROOT=<abs>` line in your spawning prompt > `project_root` field in `.rat/state/spawn-context.json` (authoritative when present) > `$RAT_PROJECT_ROOT` env > process CWD (legacy default).

```
Read(".rat/state/spawn-context.json")
```

**If file found and valid** — use manifest data:
- `setup.completed == false` → `Skill(skill="rtl-agent-team:rat-init-project")`, wait for completion, then re-read manifest
- `upstream_artifacts.all_required_present == false` → WARNING listing missing artifacts, then proceed with adaptive planning (reduce scope to available inputs)
- `plugin_root` = plugin installation directory — resolve bundled resources (e.g., `{plugin_root}/domain-packages/...`) against it; they do NOT exist in the project CWD
- Otherwise proceed with context loaded (phase, staleness, team info available)

**If file NOT found** — fallback to legacy check:
```
Glob(".claude/rules/rtl-coding-conventions.md")
```
If NOT found → `Skill(skill="rtl-agent-team:rat-init-project")`. Wait for completion before proceeding.

### Upstream Artifact Scan (E1: soft entry gate)

Scan for upstream artifacts needed by coverage analysis. Missing artifacts produce WARNING, not BLOCK.

```
Glob("sim/{module}/coverage/coverage.xml")                  # Coverage data from func-verify run
Glob("sim/{module}/coverage/*.dat")                         # Alternative coverage data format
Glob("sim/{module}/coverage/merged.info")                   # Verilator merged coverage (from func-verify)
Glob("sim/regression/*_results.json")              # Regression results for context
Glob("docs/phase-1-research/iron-requirements.json") # Requirements for coverage mapping
```

Report missing artifacts that limit the selected coverage scope.

## Step 1: Preparation

```
Bash("mkdir -p sim/{module}/coverage .rat/scratch/phase-5 reviews/phase-5-verify")
```

For a UVM functional bin report, use the counts and uncovered bin IDs directly.
Apply the gap and directed test steps to those bins using UVM sequences and the UVM
runner in functional-log mode. Report unmeasured code metrics and mark full closure
`INCONCLUSIVE` when those metrics are required. Otherwise use the code coverage flow below.
If the selected regression has no coverage data, report the missing input and halt.

## Step 2: One Gap Pass

```
Task(subagent_type="rtl-agent-team:coverage-analyst",
     prompt="Read sim/{module}/coverage/coverage.xml (or .dat or merged.info) via Bash CLI.
Use verilator_coverage --annotate or equivalent tool to parse coverage data.
List all uncovered lines with file:line references.
List all uncovered branches with condition.
List all uncovered FSM states and transitions.
Prioritize ALL gaps: HIGH (functional/safety path), MED (error path), LOW (unreachable/debug).
Special HIGH priority: error/safety paths (overflow, underflow, reset, ECC).
Special HIGH priority: protocol corner cases (backpressure, burst boundary, empty/full).
Write sim/{module}/coverage/coverage_gaps.md with complete prioritized gap list.
Save the note to .rat/scratch/phase-5/coverage-iteration.md.
Report: current coverage percentages (line/toggle/FSM), total gap count by priority.")
```

Design systematic test strategy for HIGH gaps:

```
Task(subagent_type="rtl-agent-team:test-plan-writer",
     prompt="Read sim/{module}/coverage/coverage_gaps.md. For config-dependent gaps
(gaps that require specific parameter combinations to reach), apply ECP/BVA methodology:
partition parameter space into equivalence classes, identify boundary values, use pairwise
combination for 3+ parameters. For non-config-dependent gaps, pass through as direct
stimulus targets. Write sim/{module}/coverage/directed_test_plan.md with test strategy.")
```

Generate directed tests based on gap analysis and test plan:

```
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Read sim/{module}/coverage/coverage_gaps.md and sim/{module}/coverage/directed_test_plan.md.
Write sim/{module}/coverage/test_coverage_fill.py.
Target ALL HIGH priority gaps using the systematic test plan (ECP/BVA parameter combinations
for config-dependent gaps, direct stimulus for others).
Test signals MUST reference RTL ports with correct i_/o_ prefixes.
Clock driven as {domain}_clk, reset as {domain}_rst_n.
Do not use random stimulus — write directed tests that deterministically reach each gap.")
```

Re-run regression with new tests:

```
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Add sim/{module}/coverage/test_coverage_fill.py to the regression suite.
Re-run full regression: make -C sim/{module} sim SIM=<configured-cocotb-simulator> TOPLEVEL={module}
MODULE=test_{module},test_coverage_fill RANDOM_SEED=42.
Regenerate the coverage report to sim/{module}/coverage/coverage_final.xml.
Report the new line, toggle, and FSM percentages and pass/fail.",
     run_in_background=true)
```

Stop after this regression. Name bins that still miss the targets (line >= 90%, toggle >= 80%, FSM >= 70%). Do not schedule another pass. A further pass runs only when the user asks. Below 70% after this pass is reported to the user.

## Step 3: Classify Remaining Bins

After the one directed pass, if a target is still missed:
Apply the exclusion protocol + categories table from rtl-p5s-coverage-policy (loaded via
skills:) — copy the "Coverage Exclusion Protocol" steps and "Exclusion Categories" table
VERBATIM into subagent prompts (subagents do not load the policy skill):

```
Task(subagent_type="rtl-agent-team:coverage-analyst",
     prompt="The one directed pass is done. Apply the Coverage Exclusion Protocol below to every
remaining uncovered bin (classify, then exclude per category approval rules).
<VERBATIM COPY of 'Coverage Exclusion Protocol' steps + 'Exclusion Categories' table from rtl-p5s-coverage-policy>
Generate tool-neutral exclusion manifest at sim/{module}/coverage/coverage-exclusions.json listing each excluded bin.
Generate per-tool exclusion exports as defined in rtl-p5s-coverage-policy (Verilator/lcov, VCS, Xcelium, Questa — whichever is in use).
Document each exclusion in reviews/phase-5-verify/{module}-coverage-exclusions.md with:
  bin name, module, reason, approver.
Report both RAW and EXCLUDED (post-exclusion) coverage numbers.")
```

If STIMULUS_GAP bins remain, name them in the report. Do not generate another directed-test pass unless the user asks.

## Step 7: Final Coverage Report

```
Task(subagent_type="rtl-agent-team:coverage-analyst",
     prompt="Write reviews/phase-5-verify/{module}-coverage-report.md with:
  - Final coverage percentages: line/toggle/FSM — both RAW and POST-EXCLUSION
  - Total iterations completed
  - Exclusion summary: number of excluded bins by category (STRUCTURAL_DEAD, INFRA_CODE)
  - Open bins without waiver (if any)
  - Overall verdict: PASS if post-exclusion targets met (line >= 90%, toggle >= 80%, FSM >= 70%), else FAIL
  Format:
    # Phase 5 Review: Coverage Analysis
    - Date: (today)
    - Reviewer: coverage-analyst
    - Iterations: {N} rounds
    - Verdict: PASS | FAIL
    ## Coverage Summary
    | Metric | Target | Raw Achieved | Post-Exclusion Achieved | Status |
    ## Exclusions Applied
    | Bin | Category | Reason |
    ## Open Gaps (if any)")
```

# Parallel Execution Patterns

- **Analysis, then tests, then one regression**: the regression waits for the new tests
- **That regression**: in the background (`run_in_background=true`)
- **Multiple modules' coverage**: merge after all per-module regressions complete
- **Report writing**: after final regression and merge complete

# Escalation Conditions

- No coverage data found → HALT, instruct user to run rtl-p5s-func-verify first
- LOW priority gaps flagged as unreachable → report to user, recommend dead code removal
- Coverage tool format unrecognized → halt, ask user for coverage format (Icarus, VCS, etc.)
- Coverage below 70% after directed gap fill in all rounds → escalate to rtl-architect for structural review

# Examples

**Good**: coverage-analyst finds 12% line gap, 8 uncovered FSM transitions (3 HIGH, 4 MED, 1 LOW);
testbench-dev writes 3 new tests for HIGH gaps; rerun shows coverage improves to 94%.

**Bad**: Adding random test vectors hoping to hit uncovered paths — inefficient and fails to reach
unreachable code that should be removed instead. Marking LOW-priority unreachable gaps as covered
without formal waiver documentation.

<!-- RAT_POLICIES_BEGIN: generated by scripts/sync_agent_policies.py -->
# Coverage Analysis Policy

## Coverage Targets

| Metric | Target | Evaluated On |
|--------|--------|-------------|
| Line coverage | ≥ 90% | Post-exclusion |
| Toggle coverage | ≥ 80% | Post-exclusion |
| FSM coverage | ≥ 70% | Post-exclusion |

Raw coverage is always reported alongside post-exclusion numbers for transparency.

## One Coverage Pass

Identify uncovered lines, branches, and FSM states. Prioritize gaps. Write directed tests for the high-value gaps, run them once, and report the numbers. Name bins that remain. Do not schedule another pass. A further pass runs only when the user asks.

Save the note at `.rat/scratch/phase-5/coverage-iteration.md`.

## Escalation & Stop Conditions

- LOW priority gaps flagged as unreachable → report to user, recommend dead code removal
- Coverage tool format unrecognized → halt, ask user for coverage format (Icarus, VCS, etc.)
- Coverage below 70% after gap fill → escalate to rtl-architect for structural review

## Final Checklist

- [ ] sim/coverage/coverage_gaps.md written with all gaps prioritized
- [ ] New tests written for all HIGH priority gaps
- [ ] Coverage improvement measured and reported
- [ ] Unreachable code gaps flagged separately

## CDTG Feedback Protocol (Coverage → Testbench-Dev)

When coverage-analyst identifies HIGH/CRITICAL gaps, it must produce a **Directed Test Guidance** table
that testbench-dev can directly consume. This closes the Coverage-Driven Test Generation loop
with structured, actionable feedback — not just gap descriptions.

### Feedback Format (coverage-analyst → testbench-dev)

The canonical table format (columns: Gap ID | Uncovered Bin | Constraint | Sequence |
Expected Behavior) is OWNED by the coverage-analyst agent prompt ("Directed Test Guidance"
output format) — the producer. Field semantics:
- **Constraint**: Signal value ranges or conditions that must hold to reach the uncovered bin
- **Sequence**: Temporal ordering of stimulus (clock-cycle-level when possible)
- **Expected Behavior**: Observable DUT response that confirms the bin was hit
- **ac_id linkage**: not a table column — gaps map to acceptance criteria in the gap report
  text (e.g., "Gap G01 ... relates to REQ-U-012.AC-3", per coverage-analyst's ac_id protocol);
  when no structured AC exists, reference the REQ ID instead

### Testbench-Dev Consumption

testbench-dev reads the Directed Test Guidance table and generates one cocotb test function
per row. Each test:
1. Applies the **Constraint** as signal assignments
2. Follows the **Sequence** as a cycle-accurate stimulus plan
3. Asserts the **Expected Behavior** as a pass/fail check

### One Fill

```
coverage-analyst → Directed Test Guidance table
test-plan-writer  → test plan (ECP/BVA for config-dependent gaps)
testbench-dev    → test_coverage_fill.py (one test per guidance row)
eda-runner       → one regression with the new tests
```

Then report remaining bins. Classify them. Do not start another fill unless the user asks.

## Systematic Parameter Space Analysis (Config-Dependent Gaps)

When coverage gaps depend on configuration/parameter combinations (e.g., PPS settings,
QP values, pixel formats, buffer sizes), test-plan-writer applies systematic test design
methodology before testbench-dev generates tests:

1. **Equivalence Class Partitioning (ECP)**: Partition each parameter into equivalence classes
   that produce the same coverage behavior. Example for a rate control module:
   - bits_per_pixel: {low (< 4), medium (4-8), high (> 8)}
   - initial_qp: {min boundary, mid-range, max boundary}
   - pixel_entropy: {flat, textured, edge-heavy}

2. **Boundary Value Analysis (BVA)**: For each parameter, test at min, min+1, nominal, max-1, max

3. **Combination strategy**: Use pairwise/all-pairs for 3+ parameters to keep test count
   manageable while covering all 2-way interactions

4. **Trigger condition**: coverage-analyst identifies gaps that correlate with specific parameter
   configurations (e.g., "toggle coverage low on RC buffer overflow path — only reachable when
   bits_per_pixel < 4 AND initial_qp > 45") → test-plan-writer is invoked for systematic
   parameter space partitioning

test-plan-writer produces `sim/{module}/coverage/directed_test_plan.md` which testbench-dev
consumes alongside the Directed Test Guidance table.

## Coverage Exclusion Protocol

When the one directed pass still misses a target:

1. **After that pass**: classify every remaining uncovered bin. Do not wait for a second pass.
2. **Uncovered bin analysis**: Classify each uncovered bin as:
   - STIMULUS_GAP: Reachable but not exercised → add directed test
   - STRUCTURAL_DEAD: Unreachable code (parameter guard, unimplemented feature) → exclude with waiver
   - INFRA_CODE: TB/UVM infrastructure not under test → exclude from report scope
3. **Exclusion file**: Generate tool-neutral exclusion manifest (`coverage-exclusions.json`)
   listing each excluded bin. Per-tool export: Verilator/lcov `--remove` filter, VCS URG `-elfile`,
   Xcelium IMC exclusion file, or Questa UCDB exclusion as applicable
4. **Documentation**: Record each exclusion in `reviews/phase-5-verify/{module}-coverage-exclusions.md`
   with: bin name, module, reason, approver
5. **Approval**: Default approver is coverage-analyst (automated) for standard exclusion categories
   (UVM/TB infrastructure, parameter guards, toggle on wide buses). Non-standard exclusions
   (unimplemented features, any bin where spec applicability is ambiguous) require user approval
   via AskUserQuestion before finalizing
6. **Adjusted targets**: Report both raw and excluded coverage numbers

### Exclusion Categories

| Category | Example | Action | Approval |
|----------|---------|--------|----------|
| UVM/TB infrastructure | uvm_pkg, tb_*, axi4s_if | Always exclude | Auto (coverage-analyst) |
| Parameter guards | `if (BPC > 16)` | Exclude (dead by design) | Auto (coverage-analyst) |
| Toggle on wide buses | 128-bit output upper bits | Exclude if functionally verified | Auto (coverage-analyst) |
| Unimplemented features | 4:2:2 chroma paths (out-of-scope) | Exclude only if explicitly out-of-scope or parameter-disabled; escalate if required by spec | **User** (AskUserQuestion) |
| Ambiguous spec applicability | Any bin where it is unclear whether the spec requires coverage | Escalate — exclude only with explicit confirmation | **User** (AskUserQuestion) |

## Coverage Data Processing and Gap Prioritization

Coverage data processing with Verilator:
```bash
# Annotate source files with coverage data
verilator_coverage --annotate coverage_annotated/ coverage.dat

# Convert to lcov for HTML reports
verilator_coverage --write-info coverage.info coverage.dat
genhtml coverage.info -o sim/coverage/html/
```

Gap prioritization heuristics:
- **Critical**: uncovered error/safety paths (overflow, underflow, reset, ECC)
- **High**: uncovered protocol corner cases (backpressure, burst boundary, empty/full)
- **Medium**: uncovered performance paths (stall, pipeline bubble)
- **Low**: uncovered debug/diagnostic paths (no functional impact)
- **Waive**: structurally unreachable code (dead FSM states, impossible combinational conditions)

### Benign vs Critical Gap Assessment

Not all uncovered bins indicate missing tests. Before generating directed tests, coverage-analyst
must classify each gap as **critical** (requires test) or **benign** (can be documented and accepted):

| Condition | Classification | Action |
|-----------|---------------|--------|
| DUT structurally cannot produce the stimulus (e.g., input idle never asserted because DUT always drives ready) | Benign | Document with RTL evidence (file:line) |
| Gap requires specific config that is out-of-scope | Benign | Document as config-excluded |
| Gap is reachable but requires rare multi-cycle sequence | Critical | test-plan-writer designs directed stimulus |
| Gap correlates with a specific parameter configuration | Critical | test-plan-writer applies ECP/BVA on config space |
| Gap involves cross-module data flow not exercised | Critical | Escalate to integration-verifier |

Benign gaps are recorded in the coverage report with justification (not silently excluded).

### Per-Metric Convergence Tracking

Track convergence independently for each coverage metric:

| Metric | Tracked Separately | Why |
|--------|-------------------|-----|
| Line | Yes | May converge early (often 90%+ in first iteration) |
| Toggle | Yes | Wide buses converge slowly; upper bits rarely toggle |
| FSM | Yes | Small state space; usually converges quickly |
| Branch | Yes | Conditional paths may need config-specific tests |
| Functional | Yes | Depends on covergroup design quality |

Report each metric on its own. A metric that misses its target is named. Do not run another pass to make the number move.

## Toggle Coverage Interpretation

When toggle coverage converges below target despite diverse stimulus:

1. **Per-signal toggle analysis**: identify signals with < 10% toggle rate
2. **Root cause classification**:
   - STIMULUS: Data values don't exercise full range → add directed sequence
   - PARAMETERIZATION: Bus wider than needed for current config → **design issue, not test issue**
   - STRUCTURAL: Tied/constant signals → exclude with waiver
3. **If PARAMETERIZATION**: file as design improvement recommendation (Phase 3 bus width
   parameterization violation), do NOT add more test sequences
4. **Anti-pattern**: repeatedly adding sequences for structurally-zero upper bits on
   over-wide buses — this wastes regression time without coverage improvement

### Detection Heuristic
When coverage-analyst observes a module where:
- Upper N bits of a wide bus have 0% toggle across ALL seeds and ALL tests
- Lower bits have normal toggle (> 50%)
→ Classify as PARAMETERIZATION, not STIMULUS_GAP. Report the bus width vs actual
data range mismatch and recommend parameterized width derivation per `rtl-p3-uarch-policy`.

### Configuration-to-Code-Path Mapping

When designs have configurable parameters that activate different code paths (e.g., PPS settings
in codecs, mode registers in processors, feature enables in peripherals):

1. **test-plan-writer** must identify which parameters control which code paths, as a mapping
   table with columns `| Parameter | Value Range | Code Path Activated | Coverage Impact |`
   (e.g., `mode_reg = BYPASS → bypass datapath activated → branch coverage in {module}_ctrl`)

2. **coverage-analyst** uses this mapping to diagnose coverage gaps:
   - Gap in rate_control branch? → Check if low-bpp config was tested
   - Gap in recon_engine toggle? → Check if high-QP config was tested

3. **testbench-dev** generates test variants with config constraints matched to uncovered paths

Convergence estimation: if N random seeds cover M% of bins, estimate additional seeds needed
using the formula: seeds_needed ≈ N × ln(100/(100-target)) / ln(100/(100-M)).
This is approximate — directed tests are always more efficient for specific uncovered bins.

## Approval evidence

Write structured exclusions to `reviews/phase-5-verify/coverage-exclusions.json`
(`exclusions` array; each non-standard entry has `requires_user_approval: true`).
After an explicit user confirmation, record that answer with
`{plugin_root}/scripts/coverage_approval.py approve --root <project> --decision <answer>`.
Approval is bound to the current exclusion fingerprint; an added or changed entry
requires a new user decision. A bare marker cannot approve exclusions.
<!-- RAT_POLICIES_END -->
