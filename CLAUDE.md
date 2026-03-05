<!-- RTL-AGENT-TEAM:START -->
# RTL Agent Team — Claude Code Plugin for Agentic Silicon IP Design

## IMPORTANT — Project Identity

**This is a Claude Code plugin project.**
This is NOT a standalone application or RTL design project itself — it is a **plugin that enables
agentic coding for SystemVerilog-based Silicon IP design** within Claude Code.

When installed as a plugin, it provides 64 specialized agents, 56 skills, 8 hooks,
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

**이 프로젝트를 수정할 때, "plugin 개발"과 "plugin 동작"은 완전히 다른 컨텍스트입니다.**

| | Plugin 개발 (이 프로젝트에서 작업) | Plugin 동작 (사용자 프로젝트에서 실행) |
|---|---|---|
| **CWD** | `rtl-agent-team/` (plugin 소스) | 사용자의 RTL 프로젝트 |
| **이 CLAUDE.md** | ✅ 로드됨 (프로젝트 규칙) | ❌ 로드 안 됨 (plugin CLAUDE.md는 사용자에게 전달 불가) |
| **agents/*.md** | 소스 파일로 읽기 가능 | Agent 스폰 시 프롬프트로 주입 |
| **skills/*/SKILL.md** | 소스 파일로 읽기 가능 | Skill 호출 시 프롬프트로 주입 |
| **hooks/*.sh** | 소스 파일로 읽기 가능 | 이벤트 발생 시 자동 실행 |

**따라서**: Agent/Skill/Hook을 작성할 때는 반드시 **사용자 프로젝트 CWD에서 실행되는 상황**을 가정해야 합니다.
이 CLAUDE.md의 규칙이나 다른 plugin 내부 파일을 `Read()`로 참조하는 코드를 agent/skill에 넣으면 안 됩니다 —
사용자 프로젝트에는 그 파일이 존재하지 않습니다.

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
| 2 | `.claude/rules/*` (deployed by rtl-setup) | .sv/.svh/.v/.vh access | Coding conventions, verification gates |
| 3 | Subdirectory CLAUDE.md (deployed by rtl-setup) | Directory entry | Phase guides, tool usage |
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
- **Agent는 사용자가 직접 invoke할 수 없다** — `/agent-name`은 불가, 반드시 Action Skill이 `Task()`로 스폰
- **Action Skill이 진입점** — 사용자 → Agent를 연결하는 유일한 인터페이스 (phase 전제조건 검증)
- **Agent → Policy Skill 방향이 지식 흐름** — Agent가 Policy를 참조하지, Policy가 Agent를 제어하지 않음
- **Hook이 setup 체크** — `rtl-skill-activation.sh`가 setup 전제조건을 검증, Skill에서는 phase 전제조건만 검증

| Component | Location | Role | User-invocable |
|-----------|----------|------|----------------|
| **Action Skill** | `skills/*/SKILL.md` | 사용자 진입점 + phase 전제조건 게이트 | Yes (`/plugin:name`) |
| **Orchestrator Agent** | `agents/*-orchestrator.md` | 자율적 판단/실행, 서브에이전트 스폰 | No (Task로만 스폰) |
| **Specialist Agent** | `agents/*.md` | 단일 전문 작업 수행 | No (Task로만 스폰) |
| **Policy Skill** | `skills/*-policy/SKILL.md` | 규칙/기준 제공 (Agent가 `skills:` 로 참조) | No |

**방어 레이어**: Hook(setup 체크) → Skill(phase 전제조건) → Agent Step 0(setup+phase, Task()직접 스폰 대비)

### Plugin Development Best Practices

When modifying this plugin:

1. **Prompt injection efficiency** — Minimize always-on context (hook output), maximize on-demand loading (skills, rules, guides)
2. **Agent specialization** — Each agent has a focused, single-responsibility role. Avoid general-purpose agents
3. **Hook enforcement** — Quality gates MUST be enforced by hooks (Stop/PreToolUse/PostToolUse), never by LLM instruction compliance alone
4. **Skill completion criteria** — Every action skill must define criteria in `.rtl-agent-team/skill-completion-criteria.json`
5. **Phase pipeline integrity** — New features must respect the 6-phase pipeline ordering and gates
6. **Non-destructive deployment** — `rtl-setup` deploys rules/guides only if files don't already exist
7. **POSIX shell compatibility** — Hook scripts are invoked with `sh`, not `bash`. Use `[` not `[[`
8. **Skill as gate** — Action skills must validate phase prerequisites before spawning agents, not just delegate blindly
9. **Setup prerequisite** — Orchestrator agents check `.claude/rules/rtl-coding-conventions.md` as setup marker in Step 0
10. **Escalation ladder consistency** — Autopilot and skill completion loops use per-gate `N→2N→last-chance→user escalation` semantics; keep hooks, policies, and templates in sync
11. **Model policy** — Use `opus` for reasoning-heavy tasks; reserve `sonnet` for documentation generation or tool-result summarization only

### File Architecture

```
rtl-agent-team/                          # Plugin root
├── .claude-plugin/plugin.json           # Plugin manifest
├── CLAUDE.md                            # THIS FILE — plugin dev reference (NOT loaded by users)
├── agents/                              # 64 specialized agent definitions (.md)
├── skills/                              # 56 skills: 14 orchestrator entry-points + 14 policies + 22 action workflows + 4 conventions + 2 other
│   ├── rtl-orchestrate/SKILL.md         #   Internal routing SSOT + hook export source
│   ├── rtl-setup/templates/             #   Rules + guides deployed to user projects
│   │   ├── rules/ (3 files)             #     → .claude/rules/ in user project
│   │   └── guides/ (6 files)            #     → {dir}/CLAUDE.md in user project
│   └── {skill-name}/SKILL.md            #   Phase-specific workflow
├── hooks/                               # Event-driven enforcement
│   ├── hooks.json                       #   Hook registration config
│   ├── rtl-project-init-advisor.sh      #   SessionStart: setup advisor
│   ├── rtl-orchestrator-inject.sh       #   SessionStart: routing rules injection
│   ├── rtl-edit-tracker.sh              #   PostToolUse:Edit/Write: RTL modification tracking + P6 stale detection
│   ├── rtl-skill-activation.sh          #   PreToolUse:Skill: skill completion loop
│   ├── stop-gate.sh                     #   Stop: autopilot state gate
│   ├── rtl-verify-stop-gate.sh          #   Stop: RTL verification gate
│   ├── rtl-p6-cascade-gate.sh           #   Stop: Phase 6 cascade enforcement
│   └── rtl-skill-completion-gate.sh     #   Stop: skill completion enforcement
├── domain-packages/video-codec/         # H.264/H.265 domain knowledge
├── docker/Dockerfile                    # EDA environment container
├── plugins/systemverilog-lsp/           # SV LSP sub-plugin
├── tests/                               # Unit + integration test suite
├── scripts/post-install.sh              # One-time EDA environment check
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

## Coding Conventions (Core Overrides)

1. **Port prefix**: `i_`, `o_`, `io_` (NOT suffix). Clock/reset exempt
2. **Clock**: `clk` (single) or `{domain}_clk` (multiple, e.g., `sys_clk`). **Reset**: `rst_n` (single) or `{domain}_rst_n` (multiple). Active-low async
3. **No CamelCase**: `snake_case` or `ALL_CAPS` only. Parameters `ALL_CAPS`, localparam `L_` prefix
4. SV RTL: IEEE 1800-2009. SV Verification: IEEE 1800-2012. C ref model: C11. C++ BFM: C++17
5. Convention skills auto-applied by file extension (systemverilog, systemverilog-assertion, uvm, systemc)

Full rules: `.claude/rules/rtl-coding-conventions.md`. Verification gate: `.claude/rules/rtl-verification-gate.md`. Diagram rules: `.claude/rules/diagram-rules.md`.

## Hook-Based Enforcement

| Hook Script | Event | Enforcement |
|-------------|-------|-------------|
| `rtl-project-init-advisor.sh` | SessionStart | Advise `rtl-setup` if project not initialized |
| `rtl-orchestrator-inject.sh` | SessionStart | Inject routing rules + absolute rules for user projects |
| `rtl-edit-tracker.sh` | PostToolUse:Edit/Write | Track .sv file modifications for verification gate + Phase 6 stale detection |
| `rtl-skill-activation.sh` | PreToolUse:Skill | Activate skill completion loop with criteria |
| `stop-gate.sh` | Stop | Autopilot gate ladder enforcement (`N→2N→last-chance→user escalation`) + dynamic prompt injection |
| `rtl-verify-stop-gate.sh` | Stop | RTL verification gate (lint alone insufficient) |
| `rtl-p6-cascade-gate.sh` | Stop | Phase 6 cascade (RTL change after P6 → re-review) |
| `rtl-skill-completion-gate.sh` | Stop | Skill completion escalation ladder enforcement (`N→2N→last-chance→user escalation`) |
| `rtl-team-progress.sh` | PostToolUse:TaskUpdate | Team progress tracking during native team mode |

**State files**: Stored under `.rtl-agent-team/state/`. Pipeline state, verification gates, skill completion tracking.

## Native Team Mode (v0.4.0)

Phases 1-5 support **Claude Code native team mode**
using `TeamCreate`, `TaskCreate`, `SendMessage` for true parallel execution.

| Component | Purpose |
|-----------|---------|
| `agents/p1-research-team-orchestrator.md` | Tree-of-thought parallel candidate exploration |
| `agents/p2-arch-team-orchestrator.md` | Dual-stream architecture + RefC parallelism |
| `agents/p3-uarch-team-orchestrator.md` | Dual-stream uArch + BFM with 5-reviewer review |
| `agents/spec-to-uarch-team-orchestrator.md` | P1→P3 pipeline sequencing team orchestrators |
| `agents/p4-implement-team-orchestrator.md` | 10-wave pipeline with per-module parallelism |
| `agents/p5-verify-team-orchestrator.md` | 9-category verification with dependency graph |
| `skills/rtl-p1-research-team/SKILL.md` | User entry point: `/rtl-agent-team:rtl-p1-research-team` |
| `skills/rtl-p2-arch-team/SKILL.md` | User entry point: `/rtl-agent-team:rtl-p2-arch-team` |
| `skills/rtl-p3-uarch-team/SKILL.md` | User entry point: `/rtl-agent-team:rtl-p3-uarch-team` |
| `skills/rtl-spec-to-uarch-team/SKILL.md` | User entry point: `/rtl-agent-team:rtl-spec-to-uarch-team` |
| `skills/rtl-p4-implement-team/SKILL.md` | User entry point: `/rtl-agent-team:rtl-p4-implement-team` |
| `skills/rtl-p5-verify-team/SKILL.md` | User entry point: `/rtl-agent-team:rtl-p5-verify-team` |
| `agents/lib/team-worker-preamble.md` | Standard worker lifecycle protocol |
| `agents/lib/team-fallback.md` | Graceful degradation patterns |

**Team-awareness**: Stop hooks check `.rtl-agent-team/state/team-config.json` — workers bypass
gates, only the leader session is subject to stop enforcement. Hook concurrency is protected
by POSIX file locking (`hooks/lib/flock-util.sh`).

**Fallback**: If `TeamCreate` fails, orchestrators fall back to sequential `Task()` execution automatically.

<!-- RTL-AGENT-TEAM:END -->
