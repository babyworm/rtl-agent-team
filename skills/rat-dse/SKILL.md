---
name: rat-dse
description: "Explore algorithms and architecture through Phase 3 (μArch + BFM). Use for DSE, architecture trade-offs, or comparing design trials."
user-invocable: true
argument-hint: "[spec-file or project-description]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, AskUserQuestion
---

Delegate using the current host as described in `{plugin_root}/runtime/model-selection.md`.

## Run or resume a trial

Run the first trial in the current project. The orchestrator owns Phase 1–3, the
phase gates, and one self-critique. Return its artifacts, observed verdicts and
open findings. A completed trial ends here.

Resolve the effective P1–P3 Codex review scope in the original project
using `{plugin_root}/runtime/phase-dispatch.md`. Pass only the per-phase
decisions as `review_scope`, including on resume and on an isolated trial.
Keep the project's local configuration in the original project.

```python
Task(subagent_type="rtl-agent-team:dse-orchestrator",
     prompt="PROJECT_ROOT=<absolute project root>\nRun or resume the DSE trial for $ARGUMENTS. Review scope: {review_scope}.")
```

## Compare a requested alternative

Start another trial only when the user requests one and identifies the change
to explore. Keep the current result available throughout the comparison.

1. Identify the baseline commit and trial inputs. When a checkpoint is needed,
   commit the design inputs, run recipe and decisions. Give each parallel EDA
   trial its own `RAT_EXPERIMENT_ID`; generated results stay under `experiment/<id>/`.
2. Create a dedicated branch and isolated worktree at the baseline commit
   with `git worktree add -b <trial-branch> <trial-path> <baseline-commit>`.
   Copy required uncommitted design inputs and baseline artifacts into that
   worktree. Retain both roots and the trial branch for comparison.

   ```python
   Task(subagent_type="rtl-agent-team:dse-orchestrator",
        prompt=f"PROJECT_ROOT={trial_path}\nNew trial {number} at {baseline_commit}. "
               f"Explore {change}. Review scope: {review_scope}.")
   ```

3. Compare each trial's P3 artifacts against its own P1/P2 iron requirements.
   Use its independent compliance report if the checked artifacts still match.
   For missing or stale evidence, invoke `rtl-agent-team:compliance-checker`
   with absolute paths under that trial's root for upstream iron, P3 iron,
   traceability, clock-domain map and protocol assignments. Write its report
   under the same root. Keep the two reports distinguishable.
4. Have `rtl-agent-team:rtl-architect` compare the requested trade-off, measured
   results, compliance verdicts, remaining ambiguities and HIGH findings. Record
   the comparison in `.rat/scratch/trial-comparison.md`. Ask which result to keep.
5. If the alternative is selected, commit its tracked trial changes and merge
   the trial branch into the original branch. Transfer selected untracked
   design outputs separately. If the baseline is selected, remove the worktree
   after confirming it contains only disposable trial changes. Keep both
   results while selection is pending.
