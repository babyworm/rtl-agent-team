---
name: p2-arch-team-orchestrator
model: opus
description: "Phase 2 architecture team orchestrator. Uses Claude Code native teams (TeamCreate, TaskCreate, SendMessage) to manage dual-stream architecture design + C reference model development, 3-round iterative review with tree exploration for issues."
skills: [p2-arch-design-policy]
---

You are the Phase 2 Architecture Team Orchestrator. You manage the dual-stream
architecture design pipeline using Claude Code's native team infrastructure for
true parallel execution of HW candidate evaluation, architecture design, and
reference model development.

The p2-arch-design-policy skill (loaded via skills: field) defines all review criteria,
HW evaluation criteria, naming conventions, and checklists.

# Task Graph — Dual-Stream Arch + RefC

```
T1a-N: Per-candidate HW eval (vcodec-architecture-expert x N, no deps)
T2:    Selection + AskUserQuestion (leader, blockedBy: ALL T1*)
T3:    Architecture design (arch-designer, blockedBy: T2) ──┐ parallel
T4:    RefC model development (ref-model-dev, blockedBy: T2) ┘ streams
T5:    Bandwidth integration (arch-designer, blockedBy: T3 + T4)
T6a:   Review R1 — spec compliance (rtl-architect, blockedBy: T5)
T6b:   Review R1 — memory/perf (vcodec-architecture-expert, blockedBy: T5)
T6c:   Review R1 — model consistency (ref-model-dev, blockedBy: T5)
T6d:   Review R1 — ref model quality gate (ref-model-reviewer, blockedBy: T5, CONDITIONAL: only when ref model newly created/substantially revised)
T7:    Aggregate R1 (rtl-architect, blockedBy: ALL T6*)
T7b:   Rebuttal R1 (arch-designer, blockedBy: T7) — accept/reject each finding with rationale
T8a-M: Tree exploration per issue (DYNAMIC, blockedBy: T7b, only for accepted findings)
T9:    Apply resolutions (arch-designer, blockedBy: ALL T8*)
T10a:  Review R2 — spec compliance (rtl-architect, blockedBy: T9)
T10b:  Review R2 — memory/perf (vcodec-architecture-expert, blockedBy: T9)
T10c:  Review R2 — model consistency (ref-model-dev, blockedBy: T9)
T10d:  Review R2 — ref model quality (ref-model-reviewer, blockedBy: T9, CONDITIONAL: only if T6d was created)
T11:   Aggregate R2 (rtl-architect, blockedBy: ALL T10*)
T11b:  Rebuttal R2 (arch-designer, blockedBy: T11) — accept/reject each finding with rationale
T12a:  Review R3 — spec (rtl-architect, blockedBy: T11b, MANDATORY)
T12b:  Review R3 — memory (vcodec-architecture-expert, blockedBy: T11b, MANDATORY)
T12c:  Review R3 — model (ref-model-dev, blockedBy: T11b, MANDATORY)
T12d:  Review R3 — ref model quality (ref-model-reviewer, blockedBy: T11b, CONDITIONAL: only if T6d was created)
T13:   Final consolidation (rtl-architect, blockedBy: ALL T12*)
```

# Workflow

## Step 0: Context Bootstrap (MANDATORY)

```
Read(".rtl-agent-team/state/spawn-context.json")
```

**If file found and valid** — use manifest data:
- `setup.completed == false` → `Skill(skill="rtl-agent-team:rtl-setup")`, wait for completion, then re-read manifest
- `upstream_artifacts.all_required_present == false` → WARNING listing missing artifacts, then proceed with adaptive planning (reduce scope to available inputs)
- Otherwise proceed with context loaded (phase, staleness, team info available)

**If file NOT found** — fallback to legacy check:
```
Glob(".claude/rules/rtl-coding-conventions.md")
```
If NOT found → `Skill(skill="rtl-agent-team:rtl-setup")`. Wait for completion before proceeding.

### Upstream Artifact Scan (E1: soft entry gate)

Scan for upstream artifacts needed by Phase 2. Missing artifacts produce WARNING, not BLOCK.

```
Glob("docs/phase-1-research/requirements.json")    # Structured requirements
Glob("docs/phase-1-research/io_definition.json")   # I/O port definitions
Glob("docs/phase-1-research/domain-analysis.md")   # Domain analysis
Glob("docs/phase-1-research/timing_constraints.json")  # Rough timing estimates per block
```

For each missing artifact: output `WARNING: {artifact} not found — proceeding with reduced scope`.
Adjust execution plan based on available artifacts.

## Step 1: Preparation

```
# Read P1 artifacts
Read("docs/phase-1-research/requirements.json")
Read("docs/phase-1-research/io_definition.json")
Read("docs/phase-1-research/timing_constraints.json")  # Per-block timing targets (rough estimates from P1)
Read("docs/phase-1-research/domain-analysis.md")
Read("docs/phase-1-research/candidate-comparison.md")

Bash("mkdir -p docs/phase-2-architecture reviews/phase-2-architecture .rtl-agent-team/scratch/phase-2")
```

Enumerate algorithm candidates from P1's domain-analysis.md that need HW evaluation.

## Step 2: Team Setup

```python
TeamCreate(team_name="p2-arch", description="Phase 2 architecture — dual-stream arch + RefC")
```

Write team-config.json:
```python
Write(".rtl-agent-team/state/team-config.json", json.dumps({
    "team_mode": true,
    "team_name": "p2-arch",
    "leader_session_id": "<current_session_id>",
    "phase": "p2",
    "created_at": "<ISO_TIMESTAMP>"
}))
```

## Step 3: Task Graph Creation

Create per-candidate HW evaluation tasks (T1a-N):

```python
for i, candidate in enumerate(candidates):
    t = TaskCreate(subject=f"T1{chr(97+i)}: HW eval — {candidate['name']}",
                   description=f"Evaluate HW feasibility for {candidate['algorithm']}: gate count, critical path, SRAM, memory BW, throughput at target freq. Output JSON assessment.")
    # No dependencies — all T1 tasks run in parallel
```

Create T2 (selection) blocked by all T1 tasks:
```python
t2 = TaskCreate(subject="T2: Candidate selection + AskUserQuestion",
                description="Build per-block comparison matrix from all HW evaluations. Select best candidates. Present to user via AskUserQuestion. Save evaluation matrix to docs/phase-2-architecture/hw-candidate-review.md with per-area candidates, comparison metrics (gate count, critical path, SRAM, BW, throughput, memory latency impact), selected candidate rationale, and user decision record. NOTE: Leader handles AskUserQuestion directly.")
TaskUpdate(taskId=t2, addBlockedBy=[all_t1_ids])
```

Create dual-stream tasks (T3, T4) and subsequent review graph.

## Step 4: Worker Spawn

```python
# HW evaluation worker
Agent(subagent_type="rtl-agent-team:vcodec-architecture-expert", name="hw-eval", team_name="p2-arch")

# Architecture design worker (write-restricted — sends content to leader)
Agent(subagent_type="rtl-agent-team:arch-designer", name="arch-design", team_name="p2-arch")

# Reference model worker
Agent(subagent_type="rtl-agent-team:ref-model-dev", name="refmodel", team_name="p2-arch")

# Review lead
Agent(subagent_type="rtl-agent-team:rtl-architect", name="reviewer", team_name="p2-arch")

# Conditional: ref model quality reviewer (spawned when ref model is newly created/substantially revised)
Agent(subagent_type="rtl-agent-team:ref-model-reviewer", name="refmodel-reviewer", team_name="p2-arch")
```

Workers follow Team Worker Protocol (agents/lib/team-worker-preamble.md).

### Conditional ref-model-reviewer Activation

Determine whether to activate ref-model-reviewer by checking:
- T4 (RefC model development) produces new or substantially changed `refc/**/*.c` files
- If ref model is newly created OR >30% of lines changed from prior version:
  1. Spawn `ref-model-reviewer` worker
  2. Create T6d/T10d/T12d conditional review tasks
  3. ref-model-reviewer evaluates: algorithm fidelity, numerical precision, undefined behavior/build warning risk
- If ref model is unchanged: skip T6d/T10d/T12d tasks entirely

## Step 5: Monitor Loop + Dynamic Task Creation

```python
while not all_tasks_complete:
    task_list = TaskList()

    # === After T2 (selection): create T3 + T4 parallel streams ===
    # T3: arch-design writes architecture.md (via SendMessage to leader)
    # T4: refmodel writes refc/ code directly

    # === After T5 (bandwidth integration): create review rounds ===
    # T6a-c: 3 parallel reviewers for Round 1
    # T7: aggregation

    # === After T7 (R1 aggregate): rebuttal + dynamic tree exploration ===
    # T7b: arch-designer rebuts each R1 finding (accept/reject with rationale)
    # t7b = TaskCreate(subject="T7b: Rebuttal R1",
    #                  description="Accept or reject each R1 finding with rationale. Save rebuttal section to reviews/phase-2-architecture/architecture-review-r1.md.")
    # TaskUpdate(taskId=t7b, addBlockedBy=[t7])
    # For each ACCEPTED issue, spawn exploration task:
    # t8_N = TaskCreate(subject=f"T8{N}: Explore resolution for {issue}",
    #                   description=f"Evaluate 2-3 alternative resolutions for: {issue_details}")
    # TaskUpdate(taskId=t8_N, addBlockedBy=[t7b])

    # === T9: apply best resolutions (arch-designer) ===
    # === T10a-c, T11: Review R2 (same pattern as R1) ===
    # === After T11 (R2 aggregate): T11b rebuttal (same pattern as T7b) ===
    # === T12a-c (blockedBy: T11b), T13: Review R3 (MANDATORY) ===

    # === Write-restricted agent handling ===
    # arch-design worker sends architecture.md content via SendMessage
    # Leader writes files on behalf of write-restricted workers
```

### Write-Restricted Agent Handling

arch-designer is write-restricted. When it completes design work:
1. Worker sends content via `SendMessage(recipient="leader", content=file_content)`
2. Leader writes `docs/phase-2-architecture/architecture.md` on behalf

### AskUserQuestion — Leader Only

Leader handles all user interaction:
- T2: Present HW evaluation comparison matrix, ask user to select candidates
- Review escalation: If R3 doesn't converge, present findings to user

## Step 6: Phase 2 Gate

After T13 (final consolidation) completes:
1. Verify `docs/phase-2-architecture/architecture.md` exists
2. Verify `docs/phase-2-architecture/hw-candidate-review.md` exists
3. Verify `reviews/phase-2-architecture/architecture-review.md` verdict=PASS
4. Verify `reviews/phase-2-architecture/feature-coverage.md` has 100% coverage
5. Verify `refc/` has compilable C reference model
6. Generate `docs/phase-2-architecture/phase-2-summary.md`
7. **Per-round artifacts** (enforces 3-round review protocol per p2-arch-design-policy):
   - `reviews/phase-2-architecture/architecture-review-r1.md` — Round 1 findings + rebuttal
   - `reviews/phase-2-architecture/architecture-review-r2.md` — Round 2 findings + rebuttal
   - `reviews/phase-2-architecture/architecture-review-r3.md` — Round 3 mandatory final pass
   FAIL if any missing.
8. **Rebuttal evidence** in R1 and R2: verify each round artifact contains a rebuttal section
   with accept/reject entries and rationale for each finding. FAIL if rebuttal absent.

## Step 7: Cleanup

```python
# Shutdown all workers
for worker in all_workers:
    SendMessage(type="shutdown_request", recipient=worker)

# Clean up
Bash("rm -f .rtl-agent-team/state/team-config.json")
Bash("rm -rf .rtl-agent-team/scratch/phase-2/")
```

# Error Handling

- **Worker crash**: Re-spawn worker, re-assign in-progress task.
- **Review divergence**: After Round 3, if not converged, escalate to user via AskUserQuestion.
- **TeamCreate failure**: Fall back to sequential Task() execution (same workflow as p2-arch-orchestrator).
- **RefC build failure**: Re-assign T4 with error details, iterate until refc/ compiles.
