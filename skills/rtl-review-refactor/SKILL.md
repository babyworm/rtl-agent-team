---
name: rtl-review-refactor
description: "LLM-based code review and controlled refactoring workflow. Separates findings, safe refactors, and mandatory re-validation gates."
user-invocable: true
argument-hint: "[scope: module|block|top]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Run structured review/refactor workflow with explicit severity and re-validation policy.
</Purpose>

<Use_When>
- Need structured LLM review findings and safe refactoring plan
- Want replayable validation after code changes
- Need cross-cutting quality work inside/after phase execution (typically P4/P5/P6)
</Use_When>

<Do_Not_Use_When>
- Requirements or architecture are still unstable
- This workflow is not a replacement for the phase pipeline itself
  (it is cross-cutting support for review/refactor within/after phases)
- Need to advance core phase progression (P1-P6)
  (use phase action skills, then apply this workflow as support)
</Do_Not_Use_When>

## Execution

Task(subagent_type="rtl-agent-team:review-refactor-orchestrator",
     prompt="Run review/refactor workflow for scope: $ARGUMENTS")
