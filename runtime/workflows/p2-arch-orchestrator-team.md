Use the same phase goals and artifact contract as sequential mode:
read `{plugin_root}/runtime/workflows/p2-arch-orchestrator-sequential.md`.

## Coordination Teammate Role

The main session created the team and owns its lifecycle.
FORBIDDEN: TeamCreate, TeamDelete, Agent(team_name=...).
ALLOWED: TaskCreate, TaskList, TaskUpdate, SendMessage, and the tools needed for
assigned artifacts. Direct existing workers through the task graph. Use blockedBy
only for actual input/output dependencies; do not manufacture parallel tasks.
Workers with restricted writes use `.rat/scratch/<phase>/`; integrate those outputs
at their final paths without delegating away the user's unresolved decisions.

Signal completion ONLY after the phase gate, required measurements, compliance,
phase summary and significant ADRs are complete. A drained task list alone does not
establish completion. Report measured failures and material ambiguity to the leader.
Do not start another review or create replacement workers merely to raise confidence.
