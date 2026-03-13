<!-- RTL-AGENT-TEAM:START -->
# RTL Agent Team — Claude Code Plugin for Agentic Silicon IP Design

## Language Rule

All LLM-consumed documents (agents/*.md, skills/*/SKILL.md, hook output, .claude/rules/*, CLAUDE.md guides)
MUST be written in **English**. English is more token-efficient than Korean, and since these files are
read by the LLM — not by humans — token efficiency takes priority.
User-facing conversation may use Korean, but plugin prompt content must remain English-only.

## IMPORTANT — Project Identity

**This is a Claude Code plugin project.**
This is NOT a standalone application or RTL design project itself — it is a **plugin that enables
agentic coding for SystemVerilog-based Silicon IP design** within Claude Code.

When installed as a plugin, it provides 87 specialized agents, 88 skills, 14 hooks,
and dynamic prompt injection mechanisms that orchestrate the full RTL design pipeline
from specification to verified silicon.

### Why Agentic Coding for Silicon IP

Silicon IP design is a **reliability-critical domain** — a single RTL bug can cost millions in re-spin.
Traditional sequential design is error-prone. This plugin addresses these challenges through:

1. **Phase-gated pipeline** — 6 mandatory phases with quality gates prevent premature progression
2. **Iterative review enforcement** — Higher abstraction levels require MORE review rounds (Cascading Quality principle). Phase 1-3 enforce minimum 3 rounds of review each
3. **Parallel agent execution** — Specialized agents (spec-analyst, rtl-coder, func-verifier, etc.) work concurrently within each phase, spawned as subagents via the Task tool
4. **Automated verification loops** — RTL changes trigger mandatory lint → TB → simulation cycles, enforced by Stop hooks (not by LLM compliance alone)
5. **Document-as-Memory** — Design artifacts persist across phases and agent boundaries, enabling resumability

### Plugin Runtime vs. Development Context (CRITICAL)

**"Plugin development" and "plugin runtime" are completely different contexts.**

| | Plugin Development (working in this repo) | Plugin Runtime (executing in user projects) |
|---|---|---|
| **CWD** | `rtl-agent-team/` (plugin source) | User's RTL project |
| **This CLAUDE.md** | Loaded (project rules) | NOT loaded (plugin CLAUDE.md cannot be delivered to users) |
| **agents/*.md** | Readable as source files | Injected as prompts when agents spawn |
| **skills/*/SKILL.md** | Readable as source files | Injected as prompts when skills are invoked |
| **hooks/*.sh** | Readable as source files | Auto-executed on events |

**Therefore**: When writing Agent/Skill/Hook content, always assume **execution in the user's project CWD**.
Do NOT put `Read()` calls referencing this CLAUDE.md or other plugin-internal files in agent/skill prompts —
those files do not exist in the user's project.

### Plugin Architecture: Dynamic Prompt Injection

Plugin CLAUDE.md is **NOT loaded** in user projects (Claude Code plugin architecture limitation).
Instead, this plugin uses **multi-layered dynamic prompt injection** to deliver rules and context:

```
[Always-on]  SessionStart hook  → Absolute Rules + Routing Table (~79 lines auto-injected)
[Path-scoped] .claude/rules/    → Coding conventions, verification gates (on .sv file access)
[On-demand]  Subdirectory CLAUDE.md → Phase-specific guides (on directory entry)
[Invoked]    Skill SKILL.md     → Full workflow instructions (on skill invocation)
[Spawned]    Agent .md          → Specialized agent prompts (on agent spawn)
```

| Layer | Mechanism | When Loaded | Content |
|-------|-----------|-------------|---------|
| 1 | `hooks/rtl-orchestrator-inject.sh` | Every RTL session | Routing, rules, principles |
| 2 | `.claude/rules/*` (deployed by rat-setup) | .sv/.svh/.v/.vh access | Coding conventions, verification gates |
| 3 | Subdirectory CLAUDE.md (deployed by rat-setup) | Directory entry | Phase guides, tool usage |
| 4 | Skill frontmatter | Session start (all) | Name + description (~2 lines each) |
| 5 | Skill SKILL.md body | Skill invocation | Full workflow (50-300 lines) |
| 6 | Agent prompt | Agent spawn | Role, constraints, output format |

**Progressive disclosure**: Session starts with ~130 lines (Layer 1 + Layer 4).
Additional layers load only when needed, keeping the context window efficient.

### Plugin Component Architecture (Design Principles)

This plugin follows a **Skill → Agent → Policy** architecture.

```
Action Skill (user entry point, /slash-command)
    ↓ Task(subagent_type="...")
Agent (autonomous executor, NOT user-invocable)
    ↓ skills: [policy-name]
Policy Skill (knowledge/rules reference)
```

**Why this layering matters:**
- **Agents cannot be directly invoked by users** — `/agent-name` is not possible; Action Skills must spawn them via `Task()`
- **Action Skill is the entry point** — the only interface connecting users to agents (validates phase prerequisites)
- **Knowledge flows Agent → Policy Skill** — agents reference policies, not the other way around
- **Hooks check setup** — `rtl-skill-activation.sh` validates setup prerequisites; skills validate only phase prerequisites

| Component | Location | Role | User-invocable |
|-----------|----------|------|----------------|
| **Action Skill** | `skills/*/SKILL.md` | User entry point + phase prerequisite gate | Yes (`/plugin:name`) |
| **Orchestrator Agent** | `agents/*-orchestrator.md` | Autonomous decision/execution, spawns sub-agents | No (Task-spawned only) |
| **Specialist Agent** | `agents/*.md` | Single specialized task execution | No (Task-spawned only) |
| **Policy Skill** | `skills/*-policy/SKILL.md` | Rules/criteria provider (referenced by agents via `skills:`) | No |

**Defense layers**: Hook(setup check) → Skill(phase soft advisory) → Agent Step 0(setup+phase, guards against direct Task() spawn)

### Plugin Development Best Practices

When modifying this plugin:

1. **Prompt injection efficiency** — Minimize always-on context (hook output), maximize on-demand loading (skills, rules, guides)
2. **Agent specialization** — Each agent has a focused, single-responsibility role. Avoid general-purpose agents
3. **Hook enforcement** — Quality gates MUST be enforced by hooks (Stop/PreToolUse/PostToolUse), never by LLM instruction compliance alone
4. **Skill completion criteria** — Action skills with completion enforcement must be listed in `skill-completion-criteria.json` (plugin root)
5. **Phase pipeline integrity** — New features must respect the 6-phase pipeline ordering and gates
6. **Non-destructive deployment** — `rat-setup` deploys rules/guides only if files don't already exist
7. **POSIX shell compatibility** — Hook scripts (`hooks/*.sh`) are invoked with `sh`, not `bash`. Use `[` not `[[`. Scripts in `scripts/` may use `bash` when specified via shebang
8. **Skill as soft advisory** — Action skills emit WARNING for missing phase prerequisites but proceed with available artifacts; only `rat-setup` is a hard block
9. **Setup prerequisite** — Orchestrator agents check `.claude/rules/rtl-coding-conventions.md` as setup marker in Step 0
10. **Escalation ladder consistency** — Autopilot and skill completion loops use per-gate `N→2N→last-chance→user escalation` semantics; keep hooks, policies, and templates in sync
11. **Model policy** — Use `opus` for reasoning-heavy tasks; reserve `sonnet` for documentation generation or tool-result summarization only
12. **Version bump checklist** — When bumping the plugin version, update ALL of the following in a single release-prep batch:
    - `package.json` (`version`)
    - `.claude-plugin/plugin.json` (`version`)
    - `.claude-plugin/marketplace.json` (`metadata.version` + `plugins[0].version`)
    - `README.md` + `README_kr.md` (Marketplace table version)
    - `CHANGELOG.md` (move `[Unreleased]` items into new versioned section with date)
    - Verify no stale version references remain: `grep -r '0\.OLD\.VER'`

### Intentional Design Decisions (Do Not Flag in Reviews)

1. **P1/P2 skill naming without `rtl-` prefix** — `p1-spec-research` and `p2-arch-design` intentionally omit the `rtl-` prefix because Phase 1 (Research) and Phase 2 (Architecture) are pre-RTL stages. The `rtl-` prefix is reserved for phases that involve RTL artifacts (P3+).
2. **Step 0 Context Bootstrap duplicated across 29 orchestrators** — Each orchestrator agent contains an identical ~12-line Step 0 block. This is intentional: agent prompts must be self-contained (no `#include`), the protocol is stable (unchanged since v0.6.8), and indirection via `agents/lib/` would add a Read() tool call per agent spawn. Bulk updates are achievable via `sed` or scripted replacement if the protocol ever changes.

### File Architecture

```
rtl-agent-team/                          # Plugin root
├── .claude-plugin/plugin.json           # Plugin manifest
├── CLAUDE.md                            # THIS FILE — plugin dev reference (NOT loaded by users)
├── agents/                              # 87 specialized agent definitions (.md)
│   └── lib/                             #   Shared agent protocols (team-worker-preamble.md,
│                                        #     team-worker-protocol.md, team-fallback.md,
│                                        #     domain-expert-discovery-protocol.md,
│                                        #     audit-output-protocol.md)
├── skills/                              # 88 skills: 50 action entry-points + 28 policies + 4 tool profiles + 4 conventions + 2 internal
│   ├── rtl-orchestrate/SKILL.md         #   Internal routing SSOT + hook export source
│   ├── rat-setup/templates/             #   Rules + guides deployed to user projects
│   │   ├── rules/ (3 files)             #     → .claude/rules/ in user project
│   │   └── guides/ (6 files)            #     → {dir}/CLAUDE.md in user project
│   └── {skill-name}/SKILL.md            #   Phase-specific workflow
├── hooks/                               # Event-driven enforcement
│   ├── hooks.json                       #   Hook registration config
│   ├── rtl-project-init-advisor.sh      #   SessionStart: setup advisor
│   ├── rtl-orchestrator-inject.sh       #   SessionStart: routing rules injection
│   ├── rtl-edit-tracker.sh              #   PostToolUse:Edit/Write/Bash: RTL modification tracking + P6 stale detection
│   ├── rtl-phase-state-bootstrap.sh     #   PreToolUse:Skill: phase state bootstrap
│   ├── rtl-skill-activation.sh          #   PreToolUse:Skill: skill completion loop
│   ├── stop-gate.sh                     #   Stop: autopilot state gate
│   ├── rtl-verify-stop-gate.sh          #   Stop: RTL verification gate
│   ├── rtl-p6-cascade-gate.sh           #   Stop: Phase 6 cascade enforcement
│   ├── rtl-skill-completion-gate.sh     #   Stop: skill completion enforcement
│   ├── rtl-audit-init.sh                #   PostToolUse:TaskCreate: audit session initialization
│   ├── rtl-audit-subagent.sh            #   PostToolUse:Task: per-subagent audit capture
│   ├── rtl-audit-spawn-complete.sh      #   PostToolUse:TaskCreate: audit spawn completion
│   ├── rtl-spawn-context.sh             #   PreToolUse:TaskCreate: spawn context manifest (experimental)
│   ├── rtl-team-progress.sh             #   PostToolUse:TaskUpdate: team progress tracking
│   └── lib/                             #   8 shared libs (json-util.sh, flock-util.sh, posix-util.sh,
│                                        #     hook-output-util.sh, spawn-context-util.sh,
│                                        #     team-gate-util.sh, audit-util.sh, artifact-map.sh)
├── domain-packages/
│   ├── video-codec/                     #   H.264/H.265 domain knowledge
│   └── video-processing/                #   Video processing domain knowledge
├── docker/Dockerfile                    # EDA environment container
├── plugins/systemverilog-lsp/           # SV LSP sub-plugin
├── tests/                               # Unit + integration test suite
├── scripts/                             # Utility scripts
│   ├── post-install.sh                  #   One-time EDA environment check
│   ├── sync_orchestrator_inject.sh      #   Regenerate condensed routing block in hook
│   └── ...                              #   (other helper scripts)
└── .rtl-agent-team/                     # Runtime state (gitignored, created per-project)
```

---

## Skill & Agent Routing

The authoritative routing table (natural language pattern → skill/agent mapping) lives in
`skills/rtl-orchestrate/SKILL.md` — the **single source of truth** for all routing decisions.

This routing is delivered via two mechanisms:
- **SessionStart hook** (`hooks/rtl-orchestrator-inject.sh`): condensed routing auto-injected for users
- **Internal reference skill** (`skills/rtl-orchestrate/SKILL.md`): full routing/delegation reference loaded by agents (not user-invocable)

Routing contract:
- User intent routes to **Action Skills first**.
- Orchestrator agents are spawned by Action Skills via `Task()`.
- Policy skills are loaded by orchestrators via `skills: [*-policy]`.

When adding or modifying skills/agents, update `skills/rtl-orchestrate/SKILL.md`, then run:
- `sh scripts/sync_orchestrator_inject.sh`
to regenerate the condensed routing block in `hooks/rtl-orchestrator-inject.sh`.

## Absolute Rules

1. Do not start RTL coding without a specification (spec-analyst first)
2. Do not write a Testbench without a Reference Model
3. Do not run synthesis without RTL code
4. Do not run Formal verification without passing Lint
5. **Do not declare completion after RTL modification without functional verification** (lint alone is insufficient)
6. **Do not proceed to Phase 5 without per-module unit tests upon Phase 4 completion** + Stream B artifacts
7. **When Phase 5 FAILs, allow a maximum of 2 Phase 4 feedback loops; escalate to user if exceeded**
8. **Do not proceed to Phase 6 without Phase 5 PASS** (final-compliance.md verdict=PASS required)
9. **Phase 7 is exempt from absolute rules** — free exploration allowed without pipeline Gate

## 6+1 Phase Design Pipeline

```
Phase 1: Research     → docs/phase-1-research/       (spec, domain knowledge)
Phase 2: Arch/Ref     → docs/phase-2-architecture/    + refc/ (C golden)
Phase 3: μArch/TLM    → docs/phase-3-uarch/           + BFM
Phase 4: RTL+Unit     → rtl/{module}/ + sim/{module}/  + docs/phase-4-rtl/
Phase 5: Verify       → sim/formal/ + docs/phase-5-verify/
Phase 6: Design Note  → reviews/phase-6-review/
Phase 7: Exploration  → docs/phase-7-exploration/      (optional, no pipeline rules)
```

Artifacts: `docs/phase-N-*/` (design guides), `reviews/phase-N-*/` (verdicts). Details in each directory's CLAUDE.md.

## Core Principles

**Hierarchical Spec Compliance**: Lower stages must never violate upper stage specs. Spec → Arch → μArch → RTL → Verify. Details in `skills/rtl-orchestrate/SKILL.md`.

**Cascading Quality**: Higher abstraction = more review iterations. Phase 1-3: min 3 rounds each. Fix at the top, not the bottom. Details in `skills/rtl-orchestrate/SKILL.md`.

**Document-as-Memory**: Design artifacts are persistent memory. Each phase reads upstream docs, writes downstream. Enables resumability. Details in `skills/rtl-orchestrate/SKILL.md`.

**Asymmetric Phase Gate Design**: Exit gates are strict (artifact existence verification required), entry gates are flexible (WARNING + proceed with available artifacts). This ensures downstream phases never receive incomplete inputs, while allowing upstream-incomplete phases to proceed with adaptive scope reduction. Details in `skills/rtl-orchestrate/SKILL.md`.

## Coding Conventions (Core Overrides)

1. **Port prefix**: `i_`, `o_`, `io_` (NOT suffix). Clock/reset exempt
2. **Clock**: `clk` (single) or `{domain}_clk` (multiple, e.g., `sys_clk`). **Reset**: `rst_n` (single) or `{domain}_rst_n` (multiple). Active-low async
3. **No CamelCase**: `snake_case` or `ALL_CAPS` only. Parameters `ALL_CAPS`, localparam `L_` prefix
4. SV RTL: IEEE 1800-2009. SV Verification: IEEE 1800-2012. C ref model: C11. C++ BFM: C++17
5. Convention skills auto-applied by file extension (systemverilog, systemverilog-assertion, uvm, systemc)

Full rules: `.claude/rules/rtl-coding-conventions.md`. Verification gate: `.claude/rules/rtl-verification-gate.md`. Diagram rules: `.claude/rules/diagram-rules.md`.

## Hook-Based Enforcement

All 14 hook scripts and their enforcement responsibilities are listed below.

| Hook Script | Event | Enforcement |
|-------------|-------|-------------|
| `rtl-project-init-advisor.sh` | SessionStart | Advise `rat-setup` if project not initialized |
| `rtl-orchestrator-inject.sh` | SessionStart | Inject routing rules + absolute rules for user projects |
| `rtl-edit-tracker.sh` | PostToolUse:Edit/Write/Bash | Track .sv file modifications for verification gate + Phase 6 stale detection |
| `rtl-phase-state-bootstrap.sh` | PreToolUse:Skill | Bootstrap phase state for skill invocation |
| `rtl-skill-activation.sh` | PreToolUse:Skill | Activate skill completion loop with criteria + same-skill re-invocation counter reset |
| `stop-gate.sh` | Stop | Autopilot gate ladder enforcement (`N→2N→last-chance→user escalation`) + dynamic prompt injection |
| `rtl-verify-stop-gate.sh` | Stop | RTL verification gate (lint alone insufficient) |
| `rtl-p6-cascade-gate.sh` | Stop | Phase 6 cascade (RTL change after P6 → re-review) + document mtime verification |
| `rtl-skill-completion-gate.sh` | Stop | Skill completion escalation ladder enforcement (`N→2N→last-chance→user escalation`) |
| `rtl-spawn-context.sh` | PreToolUse:TaskCreate | Spawn context manifest for direct Task() agent spawns (experimental) |
| `rtl-team-progress.sh` | PostToolUse:TaskUpdate | Team progress tracking during native team mode |
| `rtl-audit-init.sh` | SessionStart | Initialize audit session directory and trace log |
| `rtl-audit-subagent.sh` | SubagentStart/SubagentStop | Log subagent lifecycle events to audit trace |
| `rtl-audit-spawn-complete.sh` | PostToolUse:TaskCreate | Log spawn completion events to audit trace |

**State files**: Stored under `.rtl-agent-team/state/`. Pipeline state, verification gates, skill completion tracking.

## Native Team Mode (v0.6.6) — Orchestrator as Teammate Pattern

Phases 1-5 support **Claude Code native team mode**
using `TeamCreate`, `TaskCreate`, `SendMessage` for true parallel execution.

**Architecture**: Team lifecycle (TeamCreate/Agent/TeamDelete) is managed by the **skill**
(main session). The orchestrator is promoted to a **coordination teammate** via
`Agent(team_name=...)`, enabling it to use SendMessage to direct workers. Workers are
3-5 general-purpose teammates that spawn specialist `Task()` subagents internally.

```
Skill (main session = leader)
  ├── TeamCreate + team-config.json
  ├── TaskCreate (initial task graph)
  ├── Agent(coordinator) ← TEAMMATE (orchestrator)
  │     ├── TaskCreate/TaskList/TaskUpdate ✓
  │     └── SendMessage ✓ (to workers + leader)
  ├── Agent(worker) × 3-5
  │     └── Task(specialist) ← subagent calls
  ├── Leader: TaskList monitoring loop
  ├── TeamDelete()
  └── Cleanup (rm team-config.json)
```

| Component | Purpose |
|-----------|---------|
| `skills/rtl-p1-research-team/SKILL.md` | Team leader: creates team, spawns coordinator + 4 workers |
| `skills/rtl-p2-arch-team/SKILL.md` | Team leader: dual-stream arch + RefC (coordinator + 3 workers) |
| `skills/rtl-p3-uarch-team/SKILL.md` | Team leader: dual-stream uArch + BFM (coordinator + 3 workers) |
| `skills/rtl-p4-implement-team/SKILL.md` | Team leader: 10-wave pipeline (coordinator + 4 workers) |
| `skills/rtl-p5-verify-team/SKILL.md` | Team leader: 9-category verification (coordinator + 4 workers) |
| `skills/rat-p1p3-spec-uarch-team/SKILL.md` | Pipeline: sequences P1→P2→P3 team skills |
| `agents/p1-research-team-orchestrator.md` | Coordination teammate: task graph + SendMessage |
| `agents/p2-arch-team-orchestrator.md` | Coordination teammate: dual-stream tasks |
| `agents/p3-uarch-team-orchestrator.md` | Coordination teammate: uArch + BFM tasks |
| `agents/p4-implement-team-orchestrator.md` | Coordination teammate: 10-wave tasks |
| `agents/p5-verify-team-orchestrator.md` | Coordination teammate: verification tasks |
| `agents/lib/team-worker-preamble.md` | Standard worker lifecycle protocol |
| `agents/lib/team-worker-protocol.md` | Worker communication and coordination protocol |
| `agents/lib/team-fallback.md` | Graceful degradation patterns (Orchestrator as Teammate) |

**Team-awareness**: Stop hooks check `.rtl-agent-team/state/team-config.json` — coordinator
and workers bypass gates, only the leader session is subject to stop enforcement.
Hook concurrency is protected by POSIX file locking (`hooks/lib/flock-util.sh`).

**Fallback**: If `TeamCreate` fails at skill level, the skill falls back to the sequential
(non-team) orchestrator automatically.

<!-- RTL-AGENT-TEAM:END -->
