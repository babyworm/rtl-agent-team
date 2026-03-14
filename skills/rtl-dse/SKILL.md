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
```

The orchestrator runs Phase 1→3, performs self-critique, re-runs with findings,
and asks the user if results are satisfactory.

### User Satisfaction Loop

If the orchestrator reports the user is NOT satisfied:

1. Collect user feedback from the orchestrator's report
2. Create a new trial in an isolated worktree
3. Run the orchestrator again with user feedback
4. Compare trials using compliance-checker
5. Present comparison, let user select the better trial

```python
# Trial N (N >= 2): run in worktree for safe comparison
trial_number = 2
user_feedback = "<feedback from previous trial>"

Task(subagent_type="rtl-agent-team:dse-orchestrator",
     isolation="worktree",
     prompt=f"""Execute DSE Trial {trial_number}.
     Previous trial feedback: {user_feedback}
     Previous trial artifacts are on the main branch for reference.
     Address the user's specific concerns in this iteration.
     User input: $ARGUMENTS""")
```

### Trial Comparison

After Trial N completes, compare against the current best:

```python
Task(subagent_type="rtl-agent-team:compliance-checker",
     prompt="""Compare two DSE trials for iron requirement quality.
     Trial A (current best): iron-requirements.json from main branch
     Trial B (new trial): iron-requirements.json from worktree
     Compare: requirement count, acceptance_criteria measurability,
     compliance verdict, ambiguity scores, open item resolution quality.
     Output structured comparison report.""")
```

Present comparison table to user via AskUserQuestion.
User selects the better trial:
- If Trial N selected → merge worktree changes
- If current best selected → discard worktree

Repeat until user is satisfied.

### Completion

When user is satisfied, report the pre-implementation package summary:
- Iron requirements (P1+P2+P3) = absolute rules for Phase 4
- Architecture + ref C model = structural blueprint
- μArch specs + BFM = executable design model
- DPI bridge template = ready for RTL comparison

Suggest: `/rtl-agent-team:rtl-p4-implement` for Phase 4 RTL implementation.
