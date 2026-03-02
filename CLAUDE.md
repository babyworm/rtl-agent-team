<!-- RTL-AGENT-TEAM:START -->
# RTL Agent Team — Claude Code Plugin for Agentic Silicon IP Design

## IMPORTANT — Project Identity

**This is a Claude Code plugin project.**
This is NOT a standalone application or RTL design project itself — it is a **plugin that enables
agentic coding for SystemVerilog-based Silicon IP design** within Claude Code.

When installed as a plugin, it provides 60+ specialized agents, 45+ skills, 8 hooks,
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

### Plugin Development Best Practices

When modifying this plugin:

1. **Prompt injection efficiency** — Minimize always-on context (hook output), maximize on-demand loading (skills, rules, guides)
2. **Agent specialization** — Each agent has a focused, single-responsibility role. Avoid general-purpose agents
3. **Hook enforcement** — Quality gates MUST be enforced by hooks (Stop/PreToolUse/PostToolUse), never by LLM instruction compliance alone
4. **Skill completion criteria** — Every action skill must define criteria in `.rtl-agent-team/skill-completion-criteria.json`
5. **Phase pipeline integrity** — New features must respect the 6-phase pipeline ordering and gates
6. **Non-destructive deployment** — `rtl-setup` deploys rules/guides only if files don't already exist
7. **POSIX shell compatibility** — Hook scripts are invoked with `sh`, not `bash`. Use `[` not `[[`

### File Architecture

```
rtl-agent-team/                          # Plugin root
├── .claude-plugin/plugin.json           # Plugin manifest
├── CLAUDE.md                            # THIS FILE — plugin dev reference (NOT loaded by users)
├── agents/                              # 60+ specialized agent definitions (.md)
├── commands/                            # 11 orchestrator command definitions (.md)
├── skills/                              # 45+ phase-specific workflow skills
│   ├── rtl-orchestrate/SKILL.md         #   On-demand routing reference
│   ├── rtl-setup/templates/             #   Rules + guides deployed to user projects
│   │   ├── rules/ (3 files)             #     → .claude/rules/ in user project
│   │   └── guides/ (6 files)            #     → {dir}/CLAUDE.md in user project
│   └── {skill-name}/SKILL.md            #   Phase-specific workflow
├── hooks/                               # Event-driven enforcement
│   ├── hooks.json                       #   Hook registration config
│   ├── rtl-project-init-advisor.sh      #   SessionStart: setup advisor
│   ├── rtl-orchestrator-inject.sh       #   SessionStart: routing rules injection
│   ├── rtl-edit-tracker.sh              #   PostToolUse:Edit/Write: RTL modification tracking
│   ├── rtl-skill-activation.sh          #   PreToolUse:Skill: skill completion loop
│   ├── stop-gate.sh                     #   Stop: pipeline state gate
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

This routing is delivered to end users via two mechanisms:
- **SessionStart hook** (`hooks/rtl-orchestrator-inject.sh`): condensed routing auto-injected
- **On-demand skill** (`/rtl-agent-team:rtl-orchestrate`): full reference when invoked

When adding or modifying skills/agents, update `skills/rtl-orchestrate/SKILL.md` and
sync the condensed version in `hooks/rtl-orchestrator-inject.sh`.

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
4. SV RTL: IEEE 1800-2009. SV Verification: IEEE 1800-2012. C ref model: C11
5. Convention skills auto-applied by file extension (see Skill Invocation Rules)

Full rules: `.claude/rules/rtl-coding-conventions.md`. Verification gate: `.claude/rules/rtl-verification-gate.md`.

## Hook-Based Enforcement

| Hook Script | Event | Enforcement |
|-------------|-------|-------------|
| `rtl-project-init-advisor.sh` | SessionStart | Advise `rtl-setup` if project not initialized |
| `rtl-orchestrator-inject.sh` | SessionStart | Inject routing rules + absolute rules for user projects |
| `rtl-edit-tracker.sh` | PostToolUse:Edit/Write | Track .sv file modifications for verification gate |
| `rtl-skill-activation.sh` | PreToolUse:Skill | Activate skill completion loop with criteria |
| `stop-gate.sh` | Stop | Pipeline state gate (blocks premature exit) |
| `rtl-verify-stop-gate.sh` | Stop | RTL verification gate (lint alone insufficient) |
| `rtl-p6-cascade-gate.sh` | Stop | Phase 6 cascade (RTL change after P6 → re-review) |
| `rtl-skill-completion-gate.sh` | Stop | Skill completion enforcement (max iterations) |

**State files**: Stored under `.rtl-agent-team/state/`. Pipeline state, verification gates, skill completion tracking.

<!-- RTL-AGENT-TEAM:END -->
