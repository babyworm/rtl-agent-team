# Team Mode Graceful Degradation Patterns

When using Claude Code native teams (TeamCreate, SendMessage, TaskCreate),
failures can occur at multiple points. This document defines fallback behaviors.

## TeamCreate Failure

If `TeamCreate()` fails (e.g., feature not available, permission error):

1. Log the failure reason
2. Fall back to sequential `Task()` execution (legacy mode)
3. Do NOT create `team-config.json` — hooks will behave normally
4. Continue with the same task graph, but execute sequentially

```python
try:
    TeamCreate(team_name="p4-implement", description="Phase 4 RTL implementation")
except:
    # Fallback: use sequential Task() execution
    for module in modules:
        Task(subagent_type="rtl-agent-team:rtl-coder",
             prompt=f"Implement {module} from uarch spec")
```

## SendMessage Failure

If `SendMessage()` fails between leader and workers:

1. Workers write results to filesystem as artifacts (always done regardless)
2. Leader polls filesystem for completion markers instead of waiting for messages
3. Artifact paths follow standard conventions:
   - RTL: `rtl/{module}/{module}.sv`
   - Reviews: `reviews/phase-N-*/`
   - State: `.rtl-agent-team/state/`

## Worker Crash / Timeout

If a worker agent dies or stops responding:

1. Leader detects via TaskList (task stays `in_progress` with no update)
2. Leader re-spawns a replacement worker of the same type
3. Leader re-assigns the stuck task to the new worker via TaskUpdate
4. Max 2 re-spawn attempts per task; after that, escalate to user

```python
# Detection: task in_progress for too long without update
stale_tasks = [t for t in TaskList() if t.status == "in_progress" and t.age > timeout]
for task in stale_tasks:
    # Re-spawn worker
    Agent(subagent_type=task.agent_type, name=f"{task.worker}-retry", team_name=team)
    TaskUpdate(task.id, owner=f"{task.worker}-retry")
```

## Leader Crash

If the team leader (orchestrator) dies:

1. Workers detect stale progress file (`.rtl-agent-team/state/team-progress.json`
   not updated for > 5 minutes)
2. Workers complete their current task, write artifacts, then shut down
3. On next session start, user can resume by re-invoking the team skill
4. The team skill reads existing artifacts and skips completed modules

## Fallback Decision Matrix

| Failure | Detection | Fallback | User Action |
|---------|-----------|----------|-------------|
| TeamCreate fails | Exception on create | Sequential Task() | None (automatic) |
| SendMessage fails | Exception on send | Filesystem polling | None (automatic) |
| Worker crash | Stale task in TaskList | Re-spawn + re-assign | None (max 2 retries) |
| Leader crash | Stale progress file | Workers self-terminate | Re-invoke team skill |
| All retries exhausted | Retry count > 2 | Stop and report | User decides next step |
