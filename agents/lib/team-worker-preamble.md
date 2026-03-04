# Team Worker Protocol

This document defines the standard protocol for agents operating as workers
within a Claude Code native team (TeamCreate/SendMessage/TaskCreate).

## Worker Lifecycle

### 1. Initialization
When spawned with `team_name` parameter:
- Read team config from `~/.claude/teams/{team_name}/config.json` (Claude Code native)
  and project state from `.rtl-agent-team/state/team-config.json` (plugin state)
- Identify self (name) and leader from team config members list
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
5. `SendMessage(type="message", recipient=leader, content=result_summary)`

### 4. Result Reporting
After completing a task, send a concise message to the leader:
```
SendMessage(
    type="message",
    recipient="<leader_name>",
    content="V1 Lint for module_x: PASS. 0 errors, 2 warnings (waived). Report: reviews/phase-5-verify/lint-module_x.md",
    summary="V1 Lint module_x PASS"
)
```

### 5. Shutdown
When receiving a `shutdown_request`:
```
SendMessage(
    type="shutdown_response",
    request_id="<from_request>",
    approve=true
)
```

## Error Handling

- **Task failure**: Mark task as completed with failure note in description.
  Send failure details to leader. Do NOT retry automatically — leader decides.
- **Missing dependencies**: If a task's blockedBy is not empty, skip it.
  Check TaskList again later.
- **Filesystem conflicts**: Use the flock-util pattern for shared state files.

## Artifact Conventions

Workers save results following the Phase 5 directory convention:
```
reviews/phase-5-verify/        # Verdict reports (lint-{module}.md, etc.)
sim/coverage/                  # Coverage data
sim/formal/                    # Formal verification results
sim/cdc/                       # CDC analysis results
```

## Non-Team Fallback

When spawned WITHOUT `team_name` (traditional Task() invocation),
ignore this protocol entirely. Execute the task described in the prompt
and return results directly.
