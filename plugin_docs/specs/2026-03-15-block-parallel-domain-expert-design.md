# Block-Parallel RTL Development with Enhanced Domain Experts

**Date**: 2026-03-15
**Status**: Implemented
**Scope**: RTL Agent Team plugin enhancement for video codec IP design

> **archival shipped record:** This design records the implemented v0.9.0 feature.
> Forward-looking wording below is historical context, not active implementation work.

## 1. Problem Statement

The current RTL Agent Team plugin executes Phase 4 (RTL implementation) sequentially or via
generic team mode. Video codec designs consist of 6 largely independent processing blocks
(entropy, TQ, intra prediction, motion estimation, motion compensation, in-loop filter) that
can be developed in parallel. Additionally, the existing 4 **block-level** sub-domain experts (syntax, prediction, TQ, filter —
excluding chief, architecture, and performance coordination roles) lack the depth needed for
block-level RTL guidance, and the prediction expert conflates two distinct hardware datapaths
(intra vs inter).

## 2. Goals

1. **Domain expert enhancement** — Deepen knowledge base, split prediction expert 3-way, expand
   expert role to include RTL implementation guidance (knowledge injection, not direct coding)
2. **Worktree-based block-parallel development** — 6 independent git worktrees for maximum
   parallelism with code isolation during Phase 4
3. **Interface-First + Contract Test** — Phase 2 interface lock, Phase 3 timing verification,
   contract tests at every merge point
4. **Autonomous execution mode** — `rat-ultraloop` skill for unattended implement-review-improve
   cycles with design freeze enforcement

## 3. Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Prediction expert split | 3-way (intra, ME, MC) | ME architecture complexity warrants dedicated expert; intra/inter are separate HW datapaths |
| Worktree granularity | 1:1 block mapping (6 worktrees) | Maximum parallelism, minimal merge conflict |
| Execution mechanism | Team + Worktree hybrid | Team for coordination (SendMessage), worktree for code isolation |
| Merge order | Upstream-first: entropy→TQ→ME→MC→intra→filter | Follows codec processing pipeline; filter merges last for full integration |
| Phase mapping | Worktree branch at Phase 4 entry | Phase 2-3 complete interface + μArch on main first |
| Interface management | Interface-First (Phase 2) + timing (Phase 3) + contract test (merge) | Minimizes cross-block mismatch risk |
| Autonomous mode | Separate skill (`rat-ultraloop`) | Separates execution mode from workflow logic; reusable |
| Design freeze | Hash-based verification per cycle | Prevents autonomous loops from altering architecture |

## 4. Domain Expert Restructuring

### 4.1 Prediction Expert 3-Way Split

| Current | New | Core Domain |
|---------|-----|-------------|
| `vcodec-prediction-expert` (DELETE) | `vcodec-intra-pred-expert` | Angular/planar/DC modes, reference sample construction |
| | `vcodec-me-expert` | IME/FME search algorithms, MV prediction (AMVP/merge), reference frame management |
| | `vcodec-mc-expert` | Sub-pixel interpolation filters, bi-prediction, weighted prediction, reference block fetching |

### 4.2 Updated Block-Level Sub-Domain Expert Map (4 → 6)

> Note: This count excludes coordination/cross-cutting roles (chief, architecture, performance)
> which remain unchanged. Total video-codec domain agents: 7 existing + 2 net new = 9.

| # | Expert | Key Domain | Model |
|---|--------|-----------|-------|
| 1 | `vcodec-syntax-entropy-expert` | NAL, CABAC/CAVLC, DPB (existing) | opus |
| 2 | `vcodec-intra-pred-expert` | Angular/planar/DC, reference samples (NEW) | opus |
| 3 | `vcodec-me-expert` | IME/FME, MV prediction, AMVP/merge (NEW) | opus |
| 4 | `vcodec-mc-expert` | Sub-pel interpolation, bi-prediction (NEW) | opus |
| 5 | `vcodec-transform-quant-expert` | DCT/DST, quantization, RDOQ (existing) | opus |
| 6 | `vcodec-filter-recon-expert` | Deblocking, SAO, reconstruction (existing) | opus |

### 4.3 Knowledge Base Expansion (14 new files)

```
domain-packages/video-codec/knowledge/
  # Intra prediction (NEW)
  ├── intra-prediction-modes.md
  ├── intra-reference-sample.md
  # Motion estimation (NEW)
  ├── me-search-algorithms.md
  ├── mv-prediction.md
  # Motion compensation (NEW)
  ├── mc-interpolation-filters.md
  ├── weighted-prediction.md
  # Syntax/entropy deepening (NEW)
  ├── cabac-context-tables.md
  ├── cavlc-coding-tables.md
  ├── nal-unit-types.md
  # Transform/quantization deepening (NEW)
  ├── butterfly-operations.md
  ├── quantization-matrices.md
  ├── rdoq-algorithm.md
  # Filter/reconstruction deepening (NEW)
  ├── deblocking-boundary-strength.md
  └── sao-classification.md
```

### 4.4 Expert Role Expansion

Experts remain READ-ONLY (`disallowedTools: Write, Edit`). The role expansion is conceptual:

| Mode | Phases 1-3 | Phase 4 (in worktree) |
|------|-----------|----------------------|
| **Advisory** (existing) | Spec interpretation, algorithm analysis, architecture proposals | — |
| **RTL Guide** (new) | — | μArch→RTL translation guidance, interface compliance verification, coding pattern suggestions |

**Separation of concerns**: Experts inject **What/Why** (domain knowledge, implementation
priorities, verification strategies). RTL agents execute **How** (actual .sv code writing).
Phase 4 block-parallel implementation is fundamentally about injecting domain knowledge into
implementation and verification specialists.

### 4.5 Keyword Routing Partition (domain-consult update)

After the 3-way split, the single `vcodec-prediction-expert` routing row in
`skills/domain-consult/SKILL.md` must be replaced with three distinct rows:

| Keywords | Expert | Domain |
|----------|--------|--------|
| intra prediction, angular mode, planar mode, DC mode, intra reference sample, intra mode decision, neighboring sample, intra smoothing | `vcodec-intra-pred-expert` | Intra prediction (spatial, single-frame) |
| motion estimation, ME, search algorithm, IME, FME, TZ search, diamond search, hexagonal search, MV prediction, AMVP, merge mode, MV candidate, search range, reference frame selection, ME hardware | `vcodec-me-expert` | Motion Estimation (temporal search) |
| motion compensation, MC, sub-pel interpolation, half-pel, quarter-pel, bi-prediction, weighted prediction, reference block fetch, interpolation filter, MC hardware, luma interpolation, chroma interpolation | `vcodec-mc-expert` | Motion Compensation (temporal reconstruction) |

**Ambiguous keyword resolution**: Keywords that could map to multiple experts:
- "reference frame" → `vcodec-me-expert` (selection) or `vcodec-mc-expert` (fetching): route to ME if context is search/selection, route to MC if context is interpolation/fetching
- "motion vector" → route to `vcodec-me-expert` by default (MV is produced by ME, consumed by MC)
- Cross-domain prediction question (intra vs inter RD decision) → route to `vcodec-chief-standard-expert`

## 5. Worktree-Based Block-Parallel Workflow

### 5.1 New Skill: `rtl-p4-block-parallel`

```yaml
name: rtl-p4-block-parallel
description: "Phase 4 block-parallel RTL implementation using 6 worktrees
              with Team coordination and upstream-first merge"
user-invocable: true
prerequisites:
  - Phase 2 interface locked (rtl/pkg/codec_if_pkg.sv exists)
  - Phase 3 μArch + timing spec complete (docs/phase-3-uarch/ complete)
```

### 5.2 Worktree-to-Block Mapping

| Worktree Branch | Block | Directory | Dedicated Expert | Merge Order |
|----------------|-------|----------|-----------------|-------------|
| `block/entropy` | Syntax + Entropy | `rtl/entropy/` | `vcodec-syntax-entropy-expert` | 1st |
| `block/tq` | Transform + Quant | `rtl/tq/` | `vcodec-transform-quant-expert` | 2nd |
| `block/me` | Motion Estimation | `rtl/me/` | `vcodec-me-expert` | 3rd |
| `block/mc` | Motion Compensation | `rtl/mc/` | `vcodec-mc-expert` | 4th |
| `block/intra` | Intra Prediction | `rtl/intra/` | `vcodec-intra-pred-expert` | 5th |
| `block/filter` | Filter + Recon + DPB | `rtl/filter/` | `vcodec-filter-recon-expert` | 6th |

> **DPB and Reconstruction ownership**: DPB (Decoded Picture Buffer) and the reconstruction
> path (prediction + residual combining) are implemented in the `block/filter` worktree.
> `vcodec-filter-recon-expert` covers the **physical implementation** scope (deblocking, SAO,
> reconstruction, DPB SRAM). DPB **management logic** (reference picture marking, bumping
> process, reference picture set construction) remains under `vcodec-syntax-entropy-expert`
> advisory scope — the filter worktree implements what syntax-entropy specifies.
> Consequently, `recon_filter_if.sv` is an **internal interface** within the filter worktree,
> while `filter_dpb_if.sv`, `dpb_me_if.sv`, and `dpb_mc_if.sv` are **cross-block interfaces**
> owned by the filter worktree's output boundary.

### 5.3 Team Structure (Team + Worktree Hybrid)

```
Skill (leader session)
  │
  ├── TeamCreate("p4-block-parallel")
  │     # 7 Agent() calls follow: 1 coordinator + 6 block-workers
  │
  ├── Agent(team_name="p4-block-parallel") → Coordinator (p4-block-parallel-coordinator)
  │     Role:
  │     - Monitor 6 worker progress (TaskList/SendMessage)
  │     - Mediate cross-block interface questions
  │     - Determine merge readiness
  │     - Trigger contract tests
  │
  ├── Worker × 6 (teammate: general-purpose)
  │     Each worker internally:
  │     ├── Task(isolation="worktree")  ← code isolation
  │     │     ├── domain expert (knowledge injection)
  │     │     ├── rtl-coder (implementation)
  │     │     ├── lint-checker (static analysis)
  │     │     └── unit test authoring + execution
  │     └── SendMessage → coordinator (completion/issue reports)
  │
  ├── Leader: merge loop
  │     for block in [entropy, tq, me, mc, intra, filter]:
  │       1. worktree branch → main merge
  │       2. contract test execution
  │       3. FAIL → request fix from worker
  │       4. PASS → next block merge
  │
  └── TeamDelete + worktree cleanup
```

### 5.4 Worker Internal Execution Flow

```
1. Read μArch document (docs/phase-3-uarch/{block}/)
2. Spawn domain expert → receive implementation guide
   "Key implementation points for this block: [...]"
   "Interface timing contract: [...]"
3. Spawn rtl-coder → implement .sv files
   - Reference expert guide + μArch document
   - Shared interfaces (codec_if_pkg.sv) as read-only reference
4. lint-checker → static analysis
5. Unit test authoring + execution (block standalone verification)
6. SendMessage(coordinator, "block/{name} ready for merge")
```

## 6. Interface-First + Contract Test Framework

### 6.1 Phase 2 Interface Artifacts

```
rtl/pkg/codec_if_pkg.sv          ← common type/parameter definitions
rtl/intf/entropy_tq_if.sv        ← entropy ↔ TQ coefficient exchange
rtl/intf/me_mc_if.sv             ← ME → MC (MV + reference info)
rtl/intf/mc_recon_if.sv          ← MC → reconstruction (inter prediction)
rtl/intf/intra_recon_if.sv       ← intra → reconstruction (intra prediction)
rtl/intf/filter_dpb_if.sv        ← filter → DPB (reference frame store)

# NOTE: recon_filter_if.sv is NOT a Phase 2 shared interface.
# Reconstruction → filter is internal to the block/filter worktree
# (owned by vcodec-filter-recon-expert). It is defined and maintained
# inside rtl/filter/ during Phase 4, not frozen at Phase 2.
rtl/intf/dpb_me_if.sv            ← DPB → ME (reference frame read)
rtl/intf/dpb_mc_if.sv            ← DPB → MC (reference block fetching)
```

### 6.2 Phase 3 Timing Contracts

Each interface file includes cycle-level timing contracts as structured comments:

```systemverilog
// TIMING CONTRACT (Phase 3 locked):
//   Handshake: valid/ready, 1-cycle latency
//   Throughput: 1 coefficient/cycle sustained
//   Backpressure: ready deassert → valid must hold stable
//   Pipeline depth: 3 cycles from valid to downstream consumption
```

### 6.3 Contract Test Structure

```
sim/{block}/contract/
  ├── {block}_if_contract_tb.sv    ← interface compliance verification
  ├── {block}_timing_check.sv     ← timing contract assertions
  └── {block}_stub.sv             ← counterpart block stub (mock)
```

**Merge-time execution order:**
1. Target block's contract test
2. Cross-block integration test with already-merged upstream blocks
3. Both PASS → merge confirmed; FAIL → fix request to worker

## 7. Autonomous Execution: `rat-ultraloop`

### 7.1 Core Principle

> **Implementation, review, and improvement iterate autonomously.
> Design decisions (Phase 2-3 locked artifacts) are NEVER modified.**

### 7.2 Design Freeze Boundary

| Frozen (immutable) | Improvable |
|---|---|
| Interface definitions (`rtl/pkg/`, `rtl/intf/`) | RTL implementation code (`rtl/{block}/*.sv`) |
| μArch documents (`docs/phase-3-uarch/`) | Testbenches (`sim/{block}/`) |
| Timing contracts | Code quality (lint fixes, refactoring) |
| Block partition structure | Unit test coverage expansion |
| Merge order | Contract test reinforcement |

### 7.3 Skill Definition

```yaml
name: rat-ultraloop
description: "Autonomous implement-review-improve loop with 30-min
              auto-continue. Design freeze enforced."
user-invocable: true
```

### 7.4 Execution Flow

```
User: /rtl-agent-team:rat-ultraloop rtl-p4-block-parallel
  │
  ├── 1. Design Freeze snapshot
  │     - sha256 hash of rtl/pkg/, rtl/intf/, docs/phase-3-uarch/
  │     → .rtl-agent-team/state/design-freeze.json
  │
  ├── 2. Autonomous loop
  │     ┌─────────────────────────────────────┐
  │     │  IMPLEMENT → REVIEW → IMPROVE       │
  │     │       ↑                    │        │
  │     │       └────────────────────┘        │
  │     └─────────────────────────────────────┘
  │
  │     Per cycle:
  │     ├── (a) Execute implementation/improvement
  │     ├── (b) Dispatch code-reviewer (automated review)
  │     ├── (c) Apply improvements from review results
  │     ├── (d) Run contract tests
  │     ├── (e) Design Freeze verification ← hash comparison
  │     │       FAIL → immediate revert + WARNING logged
  │     ├── (f) Output cycle summary
  │     └── (g) Wait for user input (30 minutes)
  │             ├── Response received → follow user direction
  │             └── 30min timeout → start next cycle automatically
  │
  ├── 3. Auto-termination conditions
  │     ├── All blocks merged + contract tests PASS
  │     ├── No improvements found (clean review)
  │     ├── Max cycles reached (default: 10)
  │     └── Token exhaustion imminent → save state + exit
  │
  └── 4. User return
        .rtl-agent-team/state/ultraloop-report.md:
        "=== rat-ultraloop Results ===
         Cycles executed: 4
         Block status: entropy(merged) tq(merged) me(review-done) ...
         Improvements applied: 12 lint warnings resolved, 3 unit tests added
         Design Freeze: INTACT (no violations)
         Pending decisions: ME block search range optimization (user judgment needed)"
```

### 7.5 Design Freeze Verification

```
Per cycle end:
  current_hash = sha256(rtl/pkg/ + rtl/intf/ + docs/phase-3-uarch/)
  if current_hash != frozen_hash:
      # FAIL-CLOSED: halt cycle, do NOT destructively revert
      log("DESIGN FREEZE VIOLATION detected — cycle halted")
      git stash push -m "freeze-violation-cycle-N" -- rtl/pkg/ rtl/intf/ docs/phase-3-uarch/
      Record violation details (which files changed, diff summary)
      Halt autonomous loop → report to user for manual resolution
      # User can: inspect stash, accept changes (update freeze hash), or drop stash
```

**Design philosophy**: Follows the existing DSE pattern of "isolate then promote" — violations
are quarantined (stashed), not destroyed. The user retains the ability to inspect and decide.
This is consistent with `rat-dse/SKILL.md`'s worktree comparison approach where both trial
and baseline are preserved until the user makes an explicit selection.

The same hash-based verification also applies during `rtl-p4-block-parallel` execution
(not only ultraloop) to prevent worktree workers from modifying frozen interfaces. In the
block-parallel context, a freeze violation in a worktree halts that worker and reports to
the coordinator via SendMessage.

### 7.6 30-Minute Auto-Continue Mechanism

The 30-minute timeout uses the existing autopilot/stop-gate escalation pattern:

1. After each cycle, the skill outputs a summary and enters a **soft stop** state
2. `stop-gate.sh` detects ultraloop is active via state file and applies escalation ladder:
   - First stop: "Cycle N complete. Waiting for user input. Auto-continue in 30 min."
   - The skill records `last_cycle_timestamp` in state file
3. If the user does not provide input, the next Stop hook check compares
   `current_time - last_cycle_timestamp > 30min` and allows auto-continuation
4. If the user provides input at any point, normal interactive mode resumes

This leverages the existing hook infrastructure without requiring a new polling mechanism.
The 30-minute threshold is configurable in `ultraloop-state.json`.

## 8. Error Handling and Fallback

### 8.1 Prerequisite Failures

| Situation | Behavior |
|-----------|----------|
| Phase 2 interface not locked | WARNING + guide to `rtl-p2-arch-design`; if user proceeds, fall back to `rtl-p4-implement-team` (sequential, no block-parallel) |
| Phase 3 μArch incomplete | WARNING + guide to `rtl-p3-uarch-design`; if user proceeds, fall back to `rtl-p4-implement-team` (sequential) |
| Partial μArch completion | WARNING + create worktrees only for completed blocks |

> **Soft advisory contract**: Consistent with CLAUDE.md "action skills emit WARNING for missing
> phase prerequisites but proceed with available artifacts." This skill never hard-blocks;
> instead it degrades gracefully to sequential execution when prerequisites are insufficient
> for safe parallel operation.

### 8.2 Worktree/Team Failures

| Situation | Fallback |
|-----------|----------|
| `TeamCreate` failure | Fall back entirely to `rtl-p4-implement-team` (sequential orchestrator) |
| Individual worktree creation failure | Fall back entirely to `rtl-p4-implement-team` (sequential orchestrator) — no hybrid mix of worktree + main |
| Worker crash/timeout | Coordinator detects → 1 retry → failure escalates to leader |

> **All-or-nothing fallback**: Consistent with `plugin_docs/agent-lib/team-fallback.md` contract —
> partial worktree/main hybrids violate isolation guarantees and leave remaining worktrees
> based on stale mainline without rebasing. If any infrastructure component (team or worktree)
> fails, the entire execution degrades to the sequential non-team orchestrator.

### 8.3 Merge Failures

| Situation | Behavior |
|-----------|----------|
| Merge conflict | Coordinator identifies conflicting files → worker fixes → retry |
| Contract test FAIL | Send failure details to worker → fix in worktree → re-merge (max 3 attempts) |
| 3+ failures | Leader escalates to user |

### 8.4 Suspend and Resume

```json
// .rtl-agent-team/state/block-parallel-state.json
{
  "phase": "merge",
  "created_at": "2026-03-15T14:30:00Z",
  "leader_session_id": "session-abc123",
  "base_commit": "90dd3e0",
  "frozen_hash": "sha256:a1b2c3d4...",
  "merge_frontier_commit": "def456",
  "blocks": {
    "entropy": {"status": "merged", "commit": "abc123", "worktree_path": null},
    "tq":      {"status": "merged", "commit": "def456", "worktree_path": null},
    "me":      {"status": "worktree-ready", "branch": "block/me", "worktree_path": "/path/to/repo-wt-me"},
    "mc":      {"status": "in-progress", "branch": "block/mc", "worktree_path": "/path/to/repo-wt-mc"},
    "intra":   {"status": "in-progress", "branch": "block/intra", "worktree_path": "/path/to/repo-wt-intra"},
    "filter":  {"status": "in-progress", "branch": "block/filter", "worktree_path": "/path/to/repo-wt-filter"}
  },
  "merge_order": ["entropy","tq","me","mc","intra","filter"],
  "current_merge_index": 2
}
```

**Resume safety contract**: On resume, the skill MUST verify:
1. `frozen_hash` matches current state of `rtl/pkg/` + `rtl/intf/` + `docs/phase-3-uarch/`
2. `base_commit` is an ancestor of current HEAD (no history rewrite)
3. `merge_frontier_commit` matches actual HEAD (no external merges occurred)
4. All `worktree_path` entries still exist on disk (worktrees not cleaned up)

If any check fails, resume is rejected with a diagnostic message. This is consistent with
`rat-dse/SKILL.md`'s use of `worktree_path` and `worktree_branch` as explicit coordination
state, and with `team-gate-util.sh`'s reliance on `leader_session_id` and `created_at`.

- Session interruption → state file saved
- Re-execution (`/rtl-agent-team:rtl-p4-block-parallel`) detects state file → resume
- Worktree branches persist in git → reconnectable

## 9. New Plugin Components Summary

### 9.1 New Agent Files

| File | Role | Model |
|------|------|-------|
| `agents/vcodec-intra-pred-expert.md` | Intra prediction domain expert | opus |
| `agents/vcodec-me-expert.md` | Motion Estimation domain expert | opus |
| `agents/vcodec-mc-expert.md` | Motion Compensation domain expert | opus |
| `agents/p4-block-parallel-coordinator.md` | 6-block parallel coordination orchestrator | opus |
| `agents/p4-block-worker.md` | Per-block worktree execution worker | opus |
| `agents/ultraloop-reviewer.md` | Autonomous review with freeze verification | opus |

### 9.2 New Skill Files

| File | Type | Role |
|------|------|------|
| `skills/rtl-p4-block-parallel/SKILL.md` | Action | Entry point: team create → worktree branch → merge loop |
| `skills/rtl-block-contract-test-policy/SKILL.md` | Policy | Contract test criteria and procedures |
| `skills/rtl-block-interface-policy/SKILL.md` | Policy | Interface design rules + timing contract spec |
| `skills/rat-ultraloop/SKILL.md` | Action | Autonomous implement-review-improve loop |

### 9.3 New Knowledge Files

14 files under `domain-packages/video-codec/knowledge/` (see Section 4.3).

### 9.4 Modified Existing Files

| File | Change |
|------|--------|
| `domain-packages/video-codec/manifest.json` | Remove prediction-expert, add 3 new experts, register 14 knowledge files, update `standard_support_matrix.agent_coverage` arrays ("prediction" → "intra","me","mc"), update `agent_coordination` workflow references for phases 1, 4, 5 |
| `skills/rtl-orchestrate/SKILL.md` | Add new skills/agents to routing table |
| `skills/domain-consult/SKILL.md` | Split prediction routing → intra/ME/MC |
| `hooks/rtl-orchestrator-inject.sh` | Auto-regenerated via `sync_orchestrator_inject.sh` |
| `skill-completion-criteria.json` | Add `rtl-p4-block-parallel` completion criteria |

### 9.5 Explicitly Unchanged

- `skills/rtl-p4-implement-team/` — Generic P4 team preserved for non-codec projects
- `skills/rat-dse/` — DSE skill unchanged
- `agents/domain-expert.md` — Generic runner unchanged
- 6+1 Phase pipeline structure — unchanged
- `hooks/hooks.json` — no new hooks required; existing `stop-gate.sh` extended for ultraloop state detection

### 9.6 Hook Implications

| Existing Hook | Worktree Impact | Action Needed |
|---------------|-----------------|---------------|
| `rtl-edit-tracker.sh` | Edits in worktree paths may not be detected (tracks CWD-relative `.sv` files) | Verify worktree path detection; may need absolute path handling |
| `stop-gate.sh` | Must recognize ultraloop state for 30-min auto-continue | Extend state file check to include `ultraloop-state.json` |
| `rtl-verify-stop-gate.sh` | Worktree workers should bypass main-session verification gate | Already bypassed for team workers via `team-config.json` check |
| `rtl-skill-completion-gate.sh` | `rtl-p4-block-parallel` needs completion criteria | Add entry to `skill-completion-criteria.json` (listed in 9.4) |

Design freeze enforcement uses hash verification in skill logic (Section 7.5), consistent with
the pattern where phase gates are hook-enforced but design-level invariants are skill-enforced.
A dedicated freeze hook is not needed because the freeze boundary (interface files) does not
change during normal block development — only ultraloop's autonomous improvement cycles risk
accidental modification.
