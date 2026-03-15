---
name: rtl-p4-block-parallel
description: "Phase 4 block-parallel RTL implementation using 6 worktrees with Team coordination and upstream-first merge. Requires Phase 2 interfaces and Phase 3 uArch."
user-invocable: true
argument-hint: "[--all or specific block names]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate, AskUserQuestion
---

<Purpose>
Execute Phase 4 RTL implementation using block-parallel worktree strategy with Claude Code
native team infrastructure. Each of 6 codec blocks (entropy, tq, me, mc, intra, filter)
develops in an isolated git worktree, then merges upstream-first with contract test
verification at each merge point. The skill (main session) handles team lifecycle:
TeamCreate, coordinator + worker spawning, task monitoring, and cleanup.
</Purpose>

<Use_When>
- Phase 2 interfaces are frozen and Phase 3 uArch specs are complete
- User says "block parallel", "parallel blocks", "6-block implement"
- Video codec design with 6 independent blocks that benefit from worktree isolation
- Need maximum parallelism with merge-time contract verification
</Use_When>

<Do_Not_Use_When>
- Phase 2 interfaces not yet defined (run rtl-p2-arch-design first)
- Phase 3 uArch specs not complete (run rtl-p3-uarch-design first)
- Non-codec design without 6-block structure (use rtl-p4-implement-team instead)
- Single module only (use rtl-p4-implement for simpler flow)
- Only need a single module bug fix (use rtl-p4s-bugfix)
</Do_Not_Use_When>

## Prerequisites

Phase 2 interface freeze and Phase 3 uArch completion required:
- `rtl/pkg/codec_if_pkg.sv` must exist (Phase 2 interface package)
- At least one uArch spec in `docs/phase-3-uarch/` must exist

```python
# Soft advisory check — WARNING + fallback, NOT hard block
if not Glob("rtl/pkg/codec_if_pkg.sv"):
    print("WARNING: rtl/pkg/codec_if_pkg.sv not found — Phase 2 interfaces missing.")
    print("Falling back to rtl-p4-implement (sequential, non-team).")
    Skill(skill="rtl-agent-team:rtl-p4-implement", prompt=ARGUMENTS)
    return

if not Glob("docs/phase-3-uarch/*.md"):
    print("WARNING: docs/phase-3-uarch/ has no uArch specs — Phase 3 incomplete.")
    print("Falling back to rtl-p4-implement (sequential, non-team).")
    Skill(skill="rtl-agent-team:rtl-p4-implement", prompt=ARGUMENTS)
    return
```

## Resume Logic

Before starting fresh, check for existing state:

```python
state_path = ".rtl-agent-team/state/block-parallel-state.json"
state = Read(state_path)  # Returns None if not found

if state:
    # Verify safety conditions for resume
    # 1. Frozen hash must match current state of frozen paths
    current_hash = Bash("find rtl/pkg/ rtl/intf/ docs/phase-3-uarch/ -name '*.sv' -o -name '*.md' | sort | xargs sha256sum | sha256sum | cut -d' ' -f1")
    if current_hash != state["frozen_hash"]:
        print("WARNING: Design freeze hash mismatch — frozen artifacts changed since last run.")
        print("Cannot safely resume. Starting fresh.")
        state = None

    # 2. Base commit must be ancestor of HEAD
    if state:
        base_ok = Bash(f"git merge-base --is-ancestor {state['base_commit']} HEAD && echo yes || echo no")
        if base_ok.strip() != "yes":
            print("WARNING: Base commit is not ancestor of HEAD — history diverged.")
            print("Cannot safely resume. Starting fresh.")
            state = None

    # 3. Worktrees must still exist
    if state:
        for block, info in state["blocks"].items():
            if info.get("worktree_path") and info["status"] != "merged":
                wt_exists = Bash(f"test -d {info['worktree_path']} && echo yes || echo no")
                if wt_exists.strip() != "yes":
                    print(f"WARNING: Worktree for {block} missing at {info['worktree_path']}.")
                    print("Cannot safely resume. Starting fresh.")
                    state = None
                    break

    if state:
        print(f"Resuming block-parallel from phase: {state['phase']}, "
              f"blocks completed: {sum(1 for b in state['blocks'].values() if b['status'] == 'merged')}/6")
        # Skip to appropriate phase based on state
```

## Design Freeze Snapshot

Capture a hash of all frozen artifacts before starting parallel work:

```python
# Generate frozen hash from interface + uArch artifacts
frozen_hash = Bash("find rtl/pkg/ rtl/intf/ docs/phase-3-uarch/ -name '*.sv' -o -name '*.md' 2>/dev/null | sort | xargs sha256sum 2>/dev/null | sha256sum | cut -d' ' -f1").strip()
base_commit = Bash("git rev-parse HEAD").strip()

# Save design freeze state
Write(".rtl-agent-team/state/design-freeze.json", json.dumps({
    "frozen_hash": frozen_hash,
    "base_commit": base_commit,
    "frozen_paths": ["rtl/pkg/", "rtl/intf/", "docs/phase-3-uarch/"],
    "created_at": ISO_TIMESTAMP
}))
```

## Execution

### Step 1: Team Creation

```python
# ALL-OR-NOTHING: if TeamCreate fails, fall back entirely to sequential
try:
    TeamCreate(team_name="p4-block-parallel", description="6-block parallel RTL implementation with worktree isolation")
except:
    # Per team-fallback.md: NO hybrid worktree+main mix
    print("WARNING: TeamCreate failed. Falling back to rtl-p4-implement (sequential, non-team).")
    Skill(skill="rtl-agent-team:rtl-p4-implement", prompt=ARGUMENTS)
    return
```

### Step 2: Write team-config.json

```python
Write(".rtl-agent-team/state/team-config.json", json.dumps({
    "team_mode": true,
    "team_name": "p4-block-parallel",
    "leader_session_id": "<current_session_id>",
    "coordinator_name": "coordinator",
    "worker_count": 6,
    "phase": "p4",
    "created_at": ISO_TIMESTAMP
}))
```

### Step 3: Prepare Directories

```python
Bash("mkdir -p reviews/phase-4-rtl docs/phase-4-rtl .rtl-agent-team/scratch/phase-4")
```

### Step 4: Initialize State

```python
blocks = ["entropy", "tq", "me", "mc", "intra", "filter"]
merge_order = ["entropy", "tq", "me", "mc", "intra", "filter"]

state = {
    "phase": "implement",
    "created_at": ISO_TIMESTAMP,
    "leader_session_id": "<current_session_id>",
    "base_commit": base_commit,
    "frozen_hash": frozen_hash,
    "merge_frontier_commit": base_commit,
    "blocks": {
        block: {
            "status": "pending",
            "worktree_path": None,
            "worktree_branch": None,
            "lint_pass": false,
            "unit_test_pass": false,
            "contract_test_pass": false,
            "merge_commit": None
        } for block in blocks
    },
    "merge_order": merge_order,
    "current_merge_index": 0
}

Write(".rtl-agent-team/state/block-parallel-state.json", json.dumps(state))
```

### Step 5: Create Worktrees

```python
# ALL-OR-NOTHING: if any worktree fails, clean up all and fall back
worktree_ok = True
for block in blocks:
    branch = f"p4-block-{block}"
    wt_path = f"../{project_name}-wt-{block}"
    result = Bash(f"git worktree add -b {branch} {wt_path} HEAD 2>&1")
    if result.returncode != 0:
        worktree_ok = False
        break
    state["blocks"][block]["worktree_path"] = wt_path
    state["blocks"][block]["worktree_branch"] = branch
    state["blocks"][block]["status"] = "worktree-ready"

if not worktree_ok:
    # Clean up any created worktrees
    for block in blocks:
        if state["blocks"][block].get("worktree_path"):
            Bash(f"git worktree remove --force {state['blocks'][block]['worktree_path']} 2>/dev/null")
    Bash("rm -f .rtl-agent-team/state/block-parallel-state.json")
    TeamDelete()
    Bash("rm -f .rtl-agent-team/state/team-config.json")
    print("WARNING: Worktree creation failed. Falling back to rtl-p4-implement (sequential, non-team).")
    Skill(skill="rtl-agent-team:rtl-p4-implement", prompt=ARGUMENTS)
    return

Write(".rtl-agent-team/state/block-parallel-state.json", json.dumps(state))
```

### Step 6: Initial Task Graph

```python
# Create task graph BEFORE spawning agents so tasks exist when workers start
# 6 parallel implementation tasks (pre-assigned to specific workers via owner)
for block in blocks:
    TaskCreate(
        subject=f"Implement: {block}",
        description=f"Implement {block} block in worktree {state['blocks'][block]['worktree_path']}. "
                    f"Read docs/phase-3-uarch/{block}.md, spawn domain expert, "
                    f"delegate to rtl-coder, run lint, create unit tests. "
                    f"Report ready-for-merge when complete.",
        owner=f"worker-{block}"   # Pre-assigned to specific worker
    )
```

### Step 7: Spawn Coordinator

```python
Agent(team_name="p4-block-parallel",
      subagent_type="rtl-agent-team:p4-block-parallel-coordinator",
      name="coordinator",
      description="Block-parallel coordination: 6-block task graph + merge sequencing",
      prompt="You are the Phase 4 block-parallel coordinator in team 'p4-block-parallel'. "
             "Manage the 6-block task graph using TaskCreate/TaskList/TaskUpdate. "
             "Direct workers via SendMessage. "
             "Read .rtl-agent-team/state/block-parallel-state.json for worktree assignments. "
             "Orchestrate upstream-first merge sequence after all blocks complete. "
             "Signal leader when integration gate passes. User input: $ARGUMENTS")
```

### Step 8: Spawn 6 Workers

```python
block_descriptions = {
    "entropy": "Entropy coding block (CABAC/CAVLC, syntax elements). No upstream dependency.",
    "tq": "Transform/quantization block (DCT, Hadamard, QP mapping). Depends on entropy interface.",
    "me": "Motion estimation block (block matching, SAD/SATD, search patterns). Uses dpb_stub for references.",
    "mc": "Motion compensation block (interpolation, sub-pixel, bi-prediction). Depends on me + dpb_stub.",
    "intra": "Intra prediction block (angular, planar, DC modes). Independent for merge.",
    "filter": "Deblocking filter block (boundary strength, filtering decisions). Depends on reconstruction.",
}

for block in blocks:
    Agent(team_name="p4-block-parallel",
          subagent_type="rtl-agent-team:p4-block-worker",
          name=f"worker-{block}",
          description=f"P4 block worker: {block}",
          prompt=f"Your assigned block: {block}. "
                 f"Description: {block_descriptions[block]} "
                 f"Worktree path: {state['blocks'][block]['worktree_path']}. "
                 f"Worktree branch: {state['blocks'][block]['worktree_branch']}. "
                 f"Use the worktree_path above as absolute path for ALL file operations "
                 f"(RTL coding, lint, unit tests). cd into worktree_path or use absolute paths. "
                 f"You run in main CWD for coordination (SendMessage, TaskUpdate), but "
                 f"spawn rtl-coder/lint/test subagents with worktree_path in their prompt. "
                 f"Read {state['blocks'][block]['worktree_path']}/docs/phase-3-uarch/{block}.md for uArch spec. "
                 f"Read frozen interfaces from {state['blocks'][block]['worktree_path']}/rtl/intf/ and "
                 f"{state['blocks'][block]['worktree_path']}/rtl/pkg/codec_if_pkg.sv. "
                 f"DO NOT modify files under rtl/pkg/ or rtl/intf/ (frozen). "
                 f"Report completion to coordinator via SendMessage. "
                 f"Naming: i_/o_ prefixes, snake_case, clk/{{domain}}_clk, rst_n/{{domain}}_rst_n.")
```

### Step 9: Leader Monitoring Loop

```python
while True:
    tasks = TaskList()
    all_done = all(t.status == "completed" for t in tasks)
    if all_done:
        break

    # Read state for progress tracking
    state = Read(".rtl-agent-team/state/block-parallel-state.json")

    # Check for MERGE_BLOCKED escalations
    for block, info in state["blocks"].items():
        if info["status"] == "merge-blocked":
            # Escalate to user
            AskUserQuestion(f"Block {block} merge is blocked after 3 contract test failures. "
                           f"Review the failure details and decide: retry, skip, or abort?")

    # Continue polling
```

### Step 10: Merge Phase

The coordinator drives upstream-first merge sequence:
```
Merge order: entropy -> tq -> me -> mc -> intra -> filter
```

At each merge point:
1. Verify interface freeze (hash check rtl/pkg/ + rtl/intf/)
2. Merge worktree branch: `git merge --no-ff p4-block-{block}`
3. Run target block contract tests
4. Run cross-block integration with already-merged upstream
5. If PASS: update `merge_frontier_commit`, advance `current_merge_index`
6. If FAIL: retry up to 3 times (per contract test policy), then MERGE_BLOCKED

### Step 11: Cleanup

```python
# Remove worktrees
for block in blocks:
    wt_path = state["blocks"][block]["worktree_path"]
    branch = state["blocks"][block]["worktree_branch"]
    if wt_path:
        Bash(f"git worktree remove {wt_path} 2>/dev/null")
    if branch:
        Bash(f"git branch -d {branch} 2>/dev/null")

# Team cleanup
TeamDelete()
Bash("rm -f .rtl-agent-team/state/team-config.json")
Bash("rm -rf .rtl-agent-team/scratch/phase-4/")
```

## State Persistence

Full state is maintained at `.rtl-agent-team/state/block-parallel-state.json`:

```json
{
  "phase": "merge",
  "created_at": "2026-03-15T10:00:00Z",
  "leader_session_id": "session-abc123",
  "base_commit": "abc1234",
  "frozen_hash": "sha256:deadbeef...",
  "merge_frontier_commit": "def5678",
  "blocks": {
    "entropy": {
      "status": "merged",
      "worktree_path": "../project-wt-entropy",
      "worktree_branch": "p4-block-entropy",
      "lint_pass": true,
      "unit_test_pass": true,
      "contract_test_pass": true,
      "merge_commit": "aaa1111"
    },
    "tq": {
      "status": "implementing",
      "worktree_path": "../project-wt-tq",
      "worktree_branch": "p4-block-tq",
      "lint_pass": false,
      "unit_test_pass": false,
      "contract_test_pass": false,
      "merge_commit": null
    }
  },
  "merge_order": ["entropy", "tq", "me", "mc", "intra", "filter"],
  "current_merge_index": 1
}
```

State is updated by both the coordinator (block status) and the skill (merge progress).

## Fallback

**ALL-OR-NOTHING**: Per `agents/lib/team-fallback.md` contract:
- If TeamCreate fails: fall back entirely to `rtl-p4-implement` (sequential, non-team)
- If ANY worktree creation fails: clean up all worktrees, fall back to `rtl-p4-implement` (sequential, non-team)
- NO hybrid worktree+main mix is allowed

## Compliance Notes

- After each block implementation completes (lint + unit test), the coordinator invokes
  compliance-checker against P1+P2+P3 iron requirements
- RTL implementation must comply with all upstream iron requirements
- Per-block compliance ensures regressions are caught before the merge phase
- Interface freeze is verified at every merge point via hash comparison
