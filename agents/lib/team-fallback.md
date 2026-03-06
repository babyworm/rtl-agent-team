# Team Mode Graceful Degradation Patterns

Follow the structured output annotation protocol defined in `agents/lib/audit-output-protocol.md`.

When using Claude Code native teams (TeamCreate, SendMessage, TaskCreate),
failures can occur at multiple points. This document defines fallback behaviors.

## Architecture: Orchestrator as Teammate

Team lifecycle is managed by the **skill (main session)** as leader. The skill calls
TeamCreate, spawns a coordinator teammate (orchestrator) and 3-5 general-purpose workers.
The coordinator manages the task graph and directs workers via SendMessage.

```
Skill (main session = leader)
  ├── TeamCreate(team_name="pN-...")
  ├── Write(team-config.json)
  ├── TaskCreate (initial task graph)
  ├── Agent(team_name=..., name="coordinator", subagent_type=...orchestrator)
  ├── Agent(team_name=..., name="worker-N") × 3-5
  │     └── Task(specialist) for expert work
  ├── Leader: TaskList monitoring loop
  ├── TeamDelete()
  └── Bash("rm team-config.json")
```

## TeamCreate Failure

Since TeamCreate is now called by the skill (main session), this failure should
be rare. If it occurs:

1. Log the failure reason
2. Fall back to sequential `Task()` execution using the non-team orchestrator
3. Do NOT create `team-config.json` — hooks will behave normally

```python
# In skill execution — TeamCreate is at skill level (main session)
try:
    TeamCreate(team_name="p4-implement", description="Phase 4 RTL implementation")
except:
    # Fallback: use sequential non-team orchestrator via Task()
    Task(subagent_type="rtl-agent-team:p4-implement-orchestrator",
         description="P4 sequential fallback",
         prompt="Execute Phase 4 RTL implementation (sequential mode).")
```

## SendMessage Failure

If `SendMessage()` fails between coordinator and workers:

1. Workers write results to filesystem as artifacts (always done regardless)
2. The coordinator monitors task completion via TaskList
3. Artifact paths follow standard conventions:
   - RTL: `rtl/{module}/{module}.sv`
   - Reviews: `reviews/phase-N-*/`
   - State: `.rtl-agent-team/state/`

## Worker Crash / Timeout

If a worker agent dies or stops responding:

1. Coordinator detects via TaskList (task stays `in_progress` with no update)
2. Coordinator sends alert to leader via SendMessage
3. Coordinator marks the task as failed and continues with remaining tasks
4. On completion, coordinator reports incomplete tasks to the leader
5. The skill may re-invoke with `--resume` to handle incomplete work

## Leader Crash (Skill Session)

If the skill session (team leader) dies:

1. Workers complete their current task, write artifacts, then shut down
2. On next session start, user can resume by re-invoking the team skill
3. The team skill reads existing artifacts and skips completed modules
4. Stale `team-config.json` (>2h) is ignored by hooks

## Coordinator Crash

If the coordination teammate (orchestrator) dies:

1. Workers continue processing tasks from the shared task list
2. No new dynamic tasks will be created until coordinator is replaced
3. The leader detects coordinator absence via TaskList monitoring
4. The leader can spawn a replacement coordinator teammate
5. If replacement fails, leader performs cleanup (TeamDelete, rm team-config.json)
6. User can re-invoke with `--resume` to continue

## Fallback Decision Matrix

| Failure | Detection | Fallback | User Action |
|---------|-----------|----------|-------------|
| TeamCreate fails (skill) | Exception on create | Sequential non-team orchestrator | None (automatic) |
| SendMessage fails | Exception on send | Filesystem-based artifacts | None (automatic) |
| Worker crash | Stale task in TaskList | Coordinator marks failed, continues | Re-invoke with --resume |
| Coordinator crash | Leader TaskList monitoring | Leader spawns replacement | Re-invoke with --resume |
| Skill session crash | Session termination | Workers self-terminate | Re-invoke team skill |
| All retries exhausted | Retry count > 2 | Stop and report | User decides next step |
