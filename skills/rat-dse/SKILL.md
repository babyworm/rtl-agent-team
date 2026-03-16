---
name: rat-dse
description: "Iterative Design Space Exploration covering Phase 1→3: spec analysis, algorithm study, architecture exploration, μArch design, and C/SystemC BFM creation. Self-critique loop with user-controlled trial iteration and worktree-based comparison."
user-invocable: true
argument-hint: "[spec-file or project-description]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion
---

<Purpose>
Execute deep, iterative Design Space Exploration through Phase 1 (Research + Algorithm
Exploration), Phase 2 (Architecture DSE + Reference C Model), and Phase 3 (μArch + BFM).
Produces a complete pre-implementation package with self-critique refinement.

Key differentiator: DSE includes a self-critique loop (agent critically reviews its own
output, then re-runs Phase 1→3 with findings incorporated) and supports user-controlled
trial iteration via git worktrees for safe comparison.
</Purpose>

<Use_When>
- Need to explore multiple algorithm/architecture candidates before committing
- User says "DSE", "design space exploration", "compare architectures"
- Have an existing functional model to transform into HW-friendly form
- Want deep algorithm study with trade-off analysis through μArch + BFM
- Want iterative refinement with the ability to compare trial results
</Use_When>

<Do_Not_Use_When>
- Already have architecture and μArch decided (use rtl-p4-implement)
- Need the full pipeline including RTL and verification (use rat-auto-design)
- Only need spec research without architecture exploration (use p1-spec-research)
</Do_Not_Use_When>

## Prerequisites

None — DSE is an independent exploration entry point.

## Execution

### Trial 1 (current branch)

```python
Task(subagent_type="rtl-agent-team:dse-orchestrator",
     prompt="Execute DSE Trial 1. User input: $ARGUMENTS")

# After orchestrator completes Trial 1 (including self-critique + re-run):
# Commit only DSE-produced artifacts as the "current best" (avoid sweeping unrelated work)
Bash("git add -f docs/phase-1-research/ docs/phase-2-architecture/ docs/phase-3-uarch/ docs/decisions/ reviews/phase-1-research/ reviews/phase-2-architecture/ reviews/phase-3-uarch/ reviews/dse-self-critique.md refc/ bfm/ .rtl-agent-team/state/rat-dse-state.json .rtl-agent-team/state/compliance-report.json && git commit -m 'dse: Trial 1 complete'")
```

The orchestrator runs Phase 1→3, performs self-critique, re-runs with findings,
and asks the user if results are satisfactory.

### User Satisfaction Loop

If the orchestrator reports the user is NOT satisfied:

1. Collect user feedback from the orchestrator's report
2. Create a new trial in an isolated worktree (preserves current best on main)
3. Run the orchestrator again with user feedback
4. Run independent compliance checks on BOTH trials (current best + new)
5. Compare trials via rtl-architect structured comparison
6. Present comparison, user selects the better trial
7. If new trial selected → merge worktree; if current best selected → discard worktree

```python
# Trial N (N >= 2): run in worktree for safe comparison
# The worktree starts from the current best commit, so all prior artifacts are available
trial_number = 2
user_feedback = "<feedback from previous trial>"

# Agent(isolation="worktree") returns worktree_path and worktree_branch in its result
# CRITICAL: Reset state file so orchestrator does a fresh start, not resume
trial_result = Task(subagent_type="rtl-agent-team:dse-orchestrator",
     isolation="worktree",
     prompt=f"""Execute DSE Trial {trial_number}. THIS IS A NEW TRIAL — ignore any
     existing rat-dse-state.json (delete it and fresh-start).
     Previous trial feedback: {user_feedback}
     Previous trial artifacts are available as starting point.
     Address the user's specific concerns in this iteration.
     User input: $ARGUMENTS""")

# Capture worktree path AND branch from the agent result for comparison + merge
worktree_path = trial_result.worktree_path      # e.g., "/path/to/repo-worktree-abc123"
worktree_branch = trial_result.worktree_branch  # e.g., "worktree-abc123"
```

### Trial Comparison

After Trial N completes, run independent compliance checks on BOTH trials.
**CRITICAL**: Use explicit absolute paths so each check reads the correct trial's artifacts.

```python
# Run compliance-checker on CURRENT BEST trial (main branch, current working directory)
Task(subagent_type="rtl-agent-team:compliance-checker",
     prompt="""Compliance check for current best trial.
     upstream_iron: ['docs/phase-1-research/iron-requirements.json',
                     'docs/phase-2-architecture/iron-requirements.json']
     target_artifacts: ['docs/phase-3-uarch/iron-requirements.json',
                        'docs/phase-3-uarch/req-uarch-traceability.md',
                        'docs/phase-3-uarch/clock-domain-map.md',
                        'docs/phase-3-uarch/protocol-assignments.md']
     Read only the above files from the CURRENT WORKING DIRECTORY.
     Save report to .rtl-agent-team/state/compliance-report-current.json""")

# Run compliance-checker on NEW trial (worktree — use absolute paths from worktree_path)
Task(subagent_type="rtl-agent-team:compliance-checker",
     prompt=f"""Compliance check for new trial.
     upstream_iron: ['{worktree_path}/docs/phase-1-research/iron-requirements.json',
                     '{worktree_path}/docs/phase-2-architecture/iron-requirements.json']
     target_artifacts: ['{worktree_path}/docs/phase-3-uarch/iron-requirements.json',
                        '{worktree_path}/docs/phase-3-uarch/req-uarch-traceability.md',
                        '{worktree_path}/docs/phase-3-uarch/clock-domain-map.md',
                        '{worktree_path}/docs/phase-3-uarch/protocol-assignments.md']
     Read only the above files using ABSOLUTE PATHS (worktree location).
     Save report to {worktree_path}/.rtl-agent-team/state/compliance-report-new.json""")
```

Then use rtl-architect to produce a structured comparison using both reports
and artifacts from both locations:

```python
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt=f"""Compare DSE Trial results.
     Trial A (current best): read artifacts from current working directory
       - Compliance report: .rtl-agent-team/state/compliance-report-current.json
     Trial B (new trial): read artifacts from {worktree_path}/
       - Compliance report: {worktree_path}/.rtl-agent-team/state/compliance-report-new.json
     Produce comparison table: iron requirement count, acceptance_criteria
     measurability, compliance verdicts, ambiguity scores, open item
     resolution quality, self-critique HIGH findings remaining.
     Output: .rtl-agent-team/scratch/trial-comparison.md""")
```

Present comparison to user via AskUserQuestion.
User selects the better trial:
- If Trial N selected → merge worktree branch into current branch, then commit as new baseline:
  ```python
  Bash(f"git merge {worktree_branch} && git add -f docs/ reviews/ refc/ bfm/ .rtl-agent-team/state/ && git commit -m 'dse: Trial {trial_number} promoted to current best'")
  ```
- If current best selected → discard worktree (no changes to main branch)

Repeat until user is satisfied. Each iteration compares against the latest committed baseline.

### Completion

When user is satisfied, report the pre-implementation package summary:
- Iron requirements (P1+P2+P3) = absolute rules for Phase 4
- Architecture + ref C model = structural blueprint
- μArch specs + BFM = executable design model
- DPI bridge template = ready for RTL comparison

Suggest: `/rtl-agent-team:rtl-p4-implement` for Phase 4 RTL implementation.
