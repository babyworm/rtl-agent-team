# Team Worker Protocol


This document defines the standard protocol for agents operating as workers
within a Claude Code native team (TeamCreate/SendMessage/TaskCreate).

> **Orchestrator as Teammate**: The team leader is the skill (main session).
> The skill calls TeamCreate, spawns a coordinator teammate (orchestrator) and
> 3-5 general-purpose workers. The coordinator manages the task graph via
> TaskCreate/TaskList/TaskUpdate and directs workers via SendMessage.
> Workers communicate with the coordinator via SendMessage and pick up tasks
> from the shared task list. For specialist work, workers spawn Task() subagents.

```
Skill (main session = leader)
  ├── TeamCreate
  ├── TaskCreate (initial graph)
  ├── Agent(coordinator) ← TEAMMATE (orchestrator)
  │   ├── TaskCreate/TaskList/TaskUpdate ✓
  │   └── SendMessage ✓ (to workers + leader)
  ├── Agent(worker) × 3-5
  │   └── Task(specialist) ← subagent calls
  ├── Leader: TaskList monitoring loop
  ├── TeamDelete
  └── Cleanup
```

## Worker Lifecycle

### 1. Initialization
When spawned with `team_name` parameter:
- Team membership is managed by Claude Code natively (via TeamCreate/SendMessage)
- Identify self (name) and coordinator from native team context
- Read `.rat/state/team-config.json` for plugin state only (team_mode, phase)
- Call `TaskList()` to discover available tasks

### 2. Task Claim Loop
```
while true:
    tasks = TaskList()
    my_task = find first task where:
        - status == "pending"
        - owner is empty OR owner == my_name
        - blockedBy list is empty (all dependencies resolved)
    if my_task:
        TaskUpdate(taskId=my_task.id, status="in_progress", owner=my_name)
        execute_task(my_task)
    else:
        # No available tasks — wait for assignment or shutdown
        break
```

**Prefer tasks in ID order** (lowest ID first) when multiple tasks are available.

### 3. Task Execution
For each claimed task:
1. `TaskUpdate(status="in_progress")`
2. Perform the work described in task description
3. Save artifacts to filesystem (results, reports, logs)
4. `TaskUpdate(status="completed")`
5. `SendMessage(type="message", recipient="coordinator", content=result_summary)`

### 4. Specialist Delegation
For tasks requiring specialist expertise beyond your scope, spawn a Task() subagent:
```python
Task(subagent_type="rtl-agent-team:<specialist-name>",
     description="<short description>",
     prompt="<detailed task prompt with context>")
```
After the specialist returns, incorporate its results and report to the coordinator.

### 5. Result Reporting
After completing a task, send a concise message to the coordinator:
```
SendMessage(
    type="message",
    recipient="coordinator",
    content="V1 Lint for module_x: PASS. 0 errors, 2 warnings (waived). Report: reviews/phase-5-verify/lint-module_x.md",
    summary="V1 Lint module_x PASS"
)
```

### 6. Shutdown
When receiving a `shutdown_request` from the coordinator:
```
SendMessage(
    type="shutdown_response",
    request_id="<from_request>",
    approve=true
)
```

## Error Handling

- **Task failure**: Mark task as completed with failure note in description.
  Send failure details to coordinator. Do NOT retry automatically — coordinator decides.
- **Missing dependencies**: If a task's blockedBy is not empty, skip it.
  Check TaskList again later.
- **Filesystem conflicts**: Use the flock-util pattern for shared state files.
- **Specialist subagent failure**: Report failure to coordinator with error details.
  Coordinator will decide whether to retry or reassign.

## Artifact Conventions

Workers save results following the phase directory convention:
```
reviews/phase-N-*/          # Verdict reports (lint-{module}.md, etc.)
sim/coverage/               # Coverage data
formal/                 # Formal verification results
lint/cdc/                    # CDC analysis results
```

## Non-Team Fallback

When spawned WITHOUT `team_name` (traditional Task() invocation),
ignore this protocol entirely. Execute the task described in the prompt
and return results directly.
