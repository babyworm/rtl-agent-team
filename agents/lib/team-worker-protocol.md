# Team Worker Protocol (Inline Reference)

Follow the structured output annotation protocol defined in `agents/lib/audit-output-protocol.md`.

This is the concise inline protocol for specialist agents operating as workers
in a Claude Code native team. For the full lifecycle reference, see `team-worker-preamble.md`.

## Protocol Steps

When spawned with `team_name` parameter, follow these steps:

1. **INIT**: Team membership is managed by Claude Code natively.
   Identify self (name) and coordinator from team context.
2. **CLAIM**: Call `TaskList()` → find first task where status="pending",
   owner is empty or matches your name, and blockedBy is empty.
   Claim it with `TaskUpdate(taskId, status="in_progress", owner=my_name)`.
   **Prefer tasks in ID order** (lowest ID first).
3. **DELEGATE**: For specialist work beyond your scope, spawn
   `Task(subagent_type="rtl-agent-team:<specialist>", prompt="...")`.
   Incorporate the specialist's results before reporting.
4. **EXECUTE**: Perform the work described in the task. Save artifacts to filesystem.
5. **REPORT**: `TaskUpdate(taskId, status="completed")` then
   `SendMessage(type="message", recipient="coordinator", content=result_summary, summary="short status")`.
6. **NEXT**: Call `TaskList()` again. If more pending tasks available, go to Step 2.
7. **IDLE**: If no tasks available, send `SendMessage(type="message", recipient="coordinator", content="Standing by — no pending tasks", summary="Standing by")`.
8. **SHUTDOWN**: On `shutdown_request`, respond with `SendMessage(type="shutdown_response", request_id=<from_request>, approve=true)`.

## Error Handling

- **Task failure**: Mark task completed with failure details in description. Notify coordinator. Do NOT retry.
- **Missing dependencies**: Skip tasks with non-empty blockedBy. Check TaskList later.
- **Specialist subagent failure**: Report failure to coordinator with error details.

## Non-Team Mode

When spawned WITHOUT `team_name` (traditional Task() invocation),
ignore this protocol entirely and execute the task from the prompt directly.

You may also be spawned as a Task() subagent by a teammate worker.
In that case, return results directly (no SendMessage needed).
