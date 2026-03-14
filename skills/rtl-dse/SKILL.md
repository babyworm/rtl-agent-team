---
name: rtl-dse
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
# Commit all Trial 1 artifacts as the "current best"
Bash("git add docs/ reviews/ refc/ bfm/ .rtl-agent-team/state/ && git commit -m 'dse: Trial 1 complete'")
```

The orchestrator runs Phase 1→3, performs self-critique, re-runs with findings,
and asks the user if results are satisfactory.

### User Satisfaction Loop

If the orchestrator reports the user is NOT satisfied:

1. Collect user feedback from the orchestrator's report
2. Create a new trial in an isolated worktree (preserves current best on main)
3. Run the orchestrator again with user feedback
4. Run independent compliance check on new trial
5. Compare trials via rtl-architect structured comparison
6. Present comparison, user selects the better trial
7. If new trial selected → merge worktree; if current best selected → discard worktree

```python
# Trial N (N >= 2): run in worktree for safe comparison
# The worktree starts from the current best commit, so all prior artifacts are available
trial_number = 2
user_feedback = "<feedback from previous trial>"

Task(subagent_type="rtl-agent-team:dse-orchestrator",
     isolation="worktree",
     prompt=f"""Execute DSE Trial {trial_number}.
     Previous trial feedback: {user_feedback}
     Previous trial artifacts are available as starting point.
     Address the user's specific concerns in this iteration.
     User input: $ARGUMENTS""")

# After Trial N completes in worktree:
# The Agent tool with isolation="worktree" returns the worktree path and branch.
# If no changes were made, worktree is auto-cleaned.
# If changes were made, compare against current best before merging.
```

### Trial Comparison

After Trial N completes, compare against the current best using independent
compliance checks on each trial (not peer comparison — compliance-checker
validates upstream→downstream, not trial-vs-trial):

```python
# Run compliance-checker on the NEW trial's own P1→P3 chain
Task(subagent_type="rtl-agent-team:compliance-checker",
     prompt="""Compliance check for Trial N.
     upstream_iron: ['docs/phase-1-research/iron-requirements.json',
                     'docs/phase-2-architecture/iron-requirements.json']
     target_artifacts: ['docs/phase-3-uarch/iron-requirements.json',
                        'docs/phase-3-uarch/req-uarch-traceability.md']
     Read only the above files and compare directly.""")
```

Then use rtl-architect to produce a structured comparison:

```python
Task(subagent_type="rtl-agent-team:rtl-architect",
     prompt="""Compare DSE Trial results.
     Trial A (current best): read artifacts from main branch
     Trial B (new trial): read artifacts from worktree
     Produce comparison table: iron requirement count, acceptance_criteria
     measurability, compliance verdicts, ambiguity scores, open item
     resolution quality, self-critique HIGH findings remaining.
     Output: .rtl-agent-team/scratch/trial-comparison.md""")
```

Present comparison to user via AskUserQuestion.
User selects the better trial:
- If Trial N selected → merge worktree changes into current branch
- If current best selected → discard worktree

Repeat until user is satisfied.

### Completion

When user is satisfied, report the pre-implementation package summary:
- Iron requirements (P1+P2+P3) = absolute rules for Phase 4
- Architecture + ref C model = structural blueprint
- μArch specs + BFM = executable design model
- DPI bridge template = ready for RTL comparison

Suggest: `/rtl-agent-team:rtl-p4-implement` for Phase 4 RTL implementation.
