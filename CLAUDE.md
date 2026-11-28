<!-- RTL-AGENT-TEAM:START -->
# RTL Agent Team — Claude Code Plugin for Agentic Silicon IP Design

## Language Rule

All LLM-consumed documents (agents/*.md, skills/*/SKILL.md, hook output, .claude/rules/*, CLAUDE.md guides)
MUST be written in **English**. English is more token-efficient than Korean, and since these files are
read by the LLM — not by humans — token efficiency takes priority.
User-facing conversation may use Korean, but plugin prompt content must remain English-only.

## Private site data

Keep real SSH aliases/hosts, usernames, tool/library paths, environment setup and
raw site reports outside this plugin repository in the user's private data directory.
Never copy them into documentation, examples, tests or evaluation results. Use
synthetic `.invalid` hosts and invented paths in reusable fixtures.

## IMPORTANT — Project Identity

**This is a Claude Code plugin project.**
This is NOT a standalone application or RTL design project itself — it is a **plugin that enables
agentic coding for SystemVerilog-based Silicon IP design** within Claude Code.

When installed as a plugin, it provides 91 specialized agents, 56 skills, 18 hooks,
and dynamic prompt injection mechanisms that orchestrate the full RTL design pipeline
from specification to verified silicon.

### Why Agentic Coding for Silicon IP

Silicon IP design is a **reliability-critical domain** — a single RTL bug can cost millions in re-spin.
Traditional sequential design is error-prone. This plugin addresses these challenges through:

1. **Phase-gated pipeline** — 6 mandatory phases with quality gates prevent premature progression
2. **Light review** — One review against the evidence, then stop and name the open items. A further round runs only when the user asks. With no measurement, the model's confidence is the gate: one spec reading, or one architecture choice, passes. Do not iterate to raise it. Low confidence is named and asked once. Lint, simulation, formal, coverage, synthesis, CDC, and model comparison are judged from the measured result. Confidence does not override a measurement. Prompts state the goal, the constraints, the evidence, and the done condition. Leave effort at the session default. (D5, 2026-11-15. Supersedes Cascading Quality's mandatory rounds.)
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
[Always-on]  SessionStart hook  → Pipeline Rules + Routing Table (~113 lines / ~10.4KB auto-injected in RAT projects)
[Path-scoped] .claude/rules/    → Coding conventions, verification gates (on .sv file access)
[On-demand]  Subdirectory CLAUDE.md → Phase-specific guides (on directory entry)
[Invoked]    Skill SKILL.md     → Full workflow instructions (on skill invocation)
[Spawned]    Agent .md          → Specialized agent prompts (on agent spawn)
```

| Layer | Mechanism | When Loaded | Content |
|-------|-----------|-------------|---------|
| 1 | `hooks/rtl-orchestrator-inject.sh` | Every RTL session | Routing, rules, principles |
| 2 | `.claude/rules/*` (deployed by rat-init-project) | .sv/.svh/.v/.vh access | Coding conventions, verification gates |
| 3 | Subdirectory CLAUDE.md (deployed by rat-init-project) | Directory entry | Phase guides, tool usage |
| 4 | Skill frontmatter | Session start (all) | Name + description (~2 lines each) |
| 5 | Skill SKILL.md body | Skill invocation | Full workflow (50-300 lines) |
| 6 | Agent prompt | Agent spawn | Role, constraints, output format |

**Progressive disclosure**: additional layers load only when needed, keeping the context
window efficient. Three sources are always-on and are the ones to budget:

| Always-on source | Size | Contract |
|---|---:|---|
| Agent frontmatter (`name` + `description` × 91) | ~19.5 KB | none yet — largest, least governed |
| Skill frontmatter (`name` + `description` × 56) | ~9.8 KB | action skills ≤160 chars; internal/convention skills carry minimal one-liners |
| SessionStart hook injection (Layer 1) | ~10.4 KB | RAT-marked projects only |

Keep the description budget under control: the harness truncates skill descriptions
when the total gets too large, which silently destroys routing. This is observable —
v0.10.6 shipped 19.0 KB of skill descriptions and, in a session with several other
plugins installed, ~50 rtl-agent-team skills were listed with **no description at all**.
Two facts constrain any fix: `user-invocable: false` does NOT remove a skill from the
listing (the flag blocks invocation, not the budget charge), and the budget is shared
across every installed plugin, so this plugin's share must stay lean regardless.
Routing targets in the hook injection must stay fully qualified
(`/rtl-agent-team:<name>`) — the Skill tool requires the exact `plugin:skill` form,
so shortening them to bare names to save bytes trades a routing failure mode for
a rounding error.

**Hook output schema (SessionStart)**: Claude Code validates SessionStart hook stdout
against a JSON schema — `hookSpecificOutput.hookEventName` is mandatory. Layer 1 above
delivers its routing markdown via the `additionalContext` field of that envelope:

```json
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"<markdown>"}}
```

Raw markdown stdout fails schema validation and is silently dropped (with a validator
error visible in `claude --debug` logs). Since v1.0.0 the hook encodes at **session
start**: `hooks/lib/session_inject.py` reads the SSOT block in
`skills/rtl-orchestrate/SKILL.md` and prints the envelope, so there is no generated copy
to resync. The `.rat`/`.rtl-agent-team` marker check runs in sh first and still emits the
minimal envelope (`{"hookSpecificOutput":{"hookEventName":"SessionStart"}}`) when no
project marker is present, without starting Python. Without Python >= the floor the hook
emits that envelope plus one `systemMessage` naming rat-doctor. Separately, `rtl-eda-context.sh` gives sessions and subagents a short
settings lookup hint when project or user configuration exists, even before init.

### Plugin Component Architecture (Design Principles)

This plugin follows a **Skill → Agent → Policy** architecture.

```
Action Skill (user entry point, /slash-command)
    ↓ Task(subagent_type="...")
Agent (autonomous executor, NOT user-invocable)
    ↓ generated policy fragments
Embedded contract (dev source: plugin_docs/agent-lib/policies/)
```

**Why this layering matters:**
- **Agents cannot be directly invoked by users** — `/agent-name` is not possible; Action Skills must spawn them via `Task()`
- **Action Skill is the entry point** — the only interface connecting users to agents (validates phase prerequisites)
- **Policies are embedded in consumers** — the policy manifest and sync script own those contracts
- **Hooks check setup** — `rtl-skill-activation.sh` validates setup prerequisites; skills validate only phase prerequisites

| Component | Location | Role | User-invocable |
|-----------|----------|------|----------------|
| **Action Skill** | `skills/*/SKILL.md` | User entry point + phase prerequisite gate | Yes (`/plugin:name`) |
| **Orchestrator Agent** | `agents/*-orchestrator.md` | Autonomous decision/execution, spawns sub-agents | No (Task-spawned only) |
| **Specialist Agent** | `agents/*.md` | Single specialized task execution | No (Task-spawned only) |
| **Policy Fragment** | `plugin_docs/agent-lib/policies/*.md` | Generated into consumers, absent from skill discovery | No |

**Defense layers**: Hook(setup check) → Skill(phase soft advisory) → Agent Step 0(setup+phase, guards against direct Task() spawn)

### Plugin Development Best Practices

When modifying this plugin:

1. **Prompt injection efficiency** — Minimize always-on context (hook output), maximize on-demand loading (skills, rules, guides)
2. **Agent specialization** — Each agent has a focused, single-responsibility role. Avoid general-purpose agents
3. **Hook enforcement** — Quality gates MUST be enforced by hooks (Stop/PreToolUse/PostToolUse), never by LLM instruction compliance alone
4. **Skill completion criteria** — Action skills with completion enforcement must be listed in `skill-completion-criteria.json` (plugin root)
5. **Phase pipeline integrity** — New features must respect the 6-phase pipeline ordering and gates
6. **Non-destructive deployment** — `rat-init-project` deploys rules/guides only if files don't already exist
7. **Hook launchers in POSIX sh, logic in Python** — `hooks.json` runs every hook as `sh "<hook>.sh"`, so entry points stay POSIX sh (`[` not `[[`; checked by shellcheck in CI). Parsing JSON, evidence or Markdown belongs in Python modules under `hooks/lib/*.py`, started through `rat_select_python` (`hooks/lib/python-util.sh`). The Python floor is `RAT_PYTHON_MIN` / `scripts/rat_compat.py` `MIN_PYTHON` (3.9; Python 2 unsupported), enforced by `tests/unit/test_python_compat.py` and the CI matrix (floor, middle, newest). A launcher must stay safe without Python: a Stop gate blocks, SessionStart emits a valid envelope. Start Python only when there is work (the verify gate skips it on a Stop with nothing tracked) and stay well inside the hook timeout. Older hooks still carry short inline Python heredocs (edit tracker, phase-state bootstrap); they select it with `rat_select_python` and move into `hooks/lib/*.py` when their logic next changes. The Stop budget stays one sh implementation (`stop-budget-util.sh`) for every gate. Scripts in `scripts/` may use `bash` when specified via shebang, but must run on bash 3.2 (macOS); `tests/unit/test_bash_portability.py` rejects bash 4+ constructs, and the `test-macos` CI job runs the suite with `/bin/bash` 3.2 and openrsync first on PATH. Hooks never start Apple's `/usr/bin/python3` install stub (`rat_python_stub`)
8. **Skill as soft advisory** — Action skills emit WARNING for missing phase prerequisites but proceed with available artifacts; only `rat-init-project` is a hard block
9. **Setup prerequisite** — Orchestrator agents check `.claude/rules/rtl-coding-conventions.md` as setup marker in Step 0
10. **Executable contracts** — Fix recurring mechanical failures in code and add a reproducer to CI. Use prompts for decisions that require interpreting requirements or evidence. Rerun checks in the affected scope.
11. **Model policy**. Match the actual task complexity to a tier on the running host using `runtime/model-selection.md`. Keep explicit model choices and session effort. When a native delegate has no applicable model override, inherit its host session.
12. **CI before push (CRITICAL)** — Always run `pytest tests/unit/ -x -q` locally before pushing to `main`. Shell scripts under `set -eo pipefail` are especially fragile — a single unguarded `grep` no-match can silently crash a script. CI failures on `main` block all contributors
13. **Plugin docs location** — Plugin development documents (specs, plans, design docs) go in `plugin_docs/`, never in `docs/`. `docs/` is gitignored — it is reserved for user project artifacts deployed by `rat-init-project`. If `git add -f` is needed, the file is in the wrong location
14. **Release versions** — Release from `main` using Semantic Versioning (`MAJOR.MINOR.PATCH`). Keep these files in sync in the release commit and tag that commit `vMAJOR.MINOR.PATCH`.
    - `package.json` (`version`)
    - `.claude-plugin/plugin.json` (`version`)
    - `.claude-plugin/marketplace.json` (`metadata.version` + `plugins[0].version`)
    - `README.md` + `README_kr.md` (version references)
    - `CHANGELOG.md` (move `[Unreleased]` items into new versioned section with date)
    - Verify no stale version references remain: `grep -r 'OLD\.VER' package.json .claude-plugin/ README.md README_kr.md`
    - **Sub-plugin sha pin (marketplace.json)**: when bumping a github-source sub-plugin (e.g., `systemverilog-lsp`), use the **commit sha**, not the annotated tag-object sha. `git rev-parse <tag>` returns the tag-object sha for annotated tags; `git rev-parse <tag>^{commit}` always returns the commit sha. They are equal only for lightweight tags. Verify with `git cat-file -t <sha>` — must print `commit`, never `tag`. v0.10.5 pinned a tag-object sha by mistake; v0.10.6 corrected it.
15. **Hook stdout must be valid JSON when non-empty** — Claude Code validates hook output against per-event schemas (`hookSpecificOutput.hookEventName` is mandatory for SessionStart, PreToolUse, PostToolUse). Raw text stdout silently fails validation. To inject context, embed JSON-encoded content inside `additionalContext` (SessionStart) or `permissionDecisionReason` (PreToolUse). For large or multi-line content, encode in the hook's Python module (`json.dumps`), never with shell string escaping. Canonical pattern: `hooks/rtl-orchestrator-inject.sh` + `hooks/lib/session_inject.py`. Validation: `echo '{"cwd":"<dir>"}' | sh hooks/<hook>.sh | python3 -m json.tool`.
    Gates never emit `"continue": false`: it overrides `decision: "block"` and `permissionDecision: "deny"`, ends the turn, and drops the reason. Stop gates block and notify only through `stopu_gate` (`hooks/lib/stop-budget-util.sh`). They hand user decisions over with `stopu_gate … 0`, which shows the notice once per chain.
16. **`agents/` must stay flat — no subdirectories** — Claude Code discovers agents by scanning `agents/` **recursively** (`plugin.json` has no `agents` field, so auto-discovery applies). A `.md` file in any subdirectory is registered as a real, spawnable agent named `rtl-agent-team:<subdir>:<stem>`, described as "Agent from rtl-agent-team plugin", granted **all tools**, and carrying no role prompt — an unconstrained agent in the always-on registry. Shared prompt fragments and sync templates belong in `plugin_docs/agent-lib/`. v0.14.1 and earlier leaked 6 phantom agents this way from `agents/lib/`; guarded since v0.14.2 by `test_agents_dir_has_no_nested_markdown`. Note the trap: the agent test fixture globs `agents/*.md` non-recursively, so nested files are invisible to every other agent test.
17. **Hook context comes from the hook input's root, and the project from `rat_project_dir`.** Claude Code reports the session's current directory as `cwd`, and a `cd` persists. So every hook resolves the project with `rat_project_dir` (it walks up to `$CLAUDE_PROJECT_DIR`; the root marker wins) and re-bases `CWD=$(dirname "$RAT_DIR")` before building any path. Read session fields with `jsonu_get_root_string` or `jsonu_session_id`, never from `tool_input`. `test_hooks_honor_project_root_override` enforces the re-base; `test_session_id_comes_from_the_hook_input_root` and `test_agent_cwd_does_not_move_the_session_project` pin the root reads, and `test_hooks_read_session_fields_from_the_input_root` forbids reading one through `jsonu_get_input_string` or by hand (it lists the three hand scans, which read inputs without `tool_input`).

### Intentional Design Decisions (Do Not Flag in Reviews)

1. **P1/P2 skill naming without `rtl-` prefix** — `p1-spec-research` and `p2-arch-design` intentionally omit the `rtl-` prefix because Phase 1 (Research) and Phase 2 (Architecture) are pre-RTL stages. The `rtl-` prefix is reserved for phases that involve RTL artifacts (P3+).
2. **Step 0 Context Bootstrap duplicated across 20 orchestrators** — These 20 orchestrator agents carry the canonical block synchronized from `plugin_docs/agent-lib/step0-template.md` (`bash scripts/sync_step0.sh --dry-run`). This is intentional: agent prompts must be self-contained (no `#include`), and indirection via `plugin_docs/agent-lib/` would add a Read() tool call per agent spawn. `p5a-functional-closure-orchestrator`, `p5b-silicon-validation-orchestrator`, and `ppa-optimizer-dc-orchestrator` use custom preconditions/state files instead of the canonical block; all three still use the shared project-root path convention in their headers.

### File Architecture

```
rtl-agent-team/                          # Plugin root
├── .claude-plugin/plugin.json           # Plugin manifest
├── CLAUDE.md                            # THIS FILE — plugin dev reference (NOT loaded by users)
├── agents/                              # 91 specialized agent definitions (.md), FLAT — no subdirs
│                                        #   (agents/ is scanned RECURSIVELY: any nested .md
│                                        #    becomes a phantom agent — see rule 16 below)
├── skills/                              # 56 skills: 51 action entry-points + 4 conventions + 1 internal; policy fragments are generated into agents
│   ├── rtl-orchestrate/SKILL.md         #   Internal routing SSOT + hook export source
│   ├── rat-init-project/templates/      #   Rules + guides deployed to user projects
│   │   ├── rules/ (2 files)             #     → .claude/rules/ in user project
│   │   └── guides/ (6 files)            #     → {dir}/CLAUDE.md in user project
│   └── {skill-name}/SKILL.md            #   Phase-specific workflow
├── hooks/                               # Event-driven enforcement (18 hook scripts)
│   ├── hooks.json                       #   Hook registration config
│   ├── rtl-orchestrator-inject.sh       #   SessionStart: routing rules injection
│   ├── rtl-audit-init.sh                #   SessionStart: audit session initialization
│   ├── rtl-parser-warning.sh            #   SessionStart: sed-fallback warning in RAT projects
│   ├── rtl-eda-context.sh               #   SessionStart/SubagentStart: EDA settings lookup hint + env
│   ├── rtl-skill-expansion.sh           #   UserPromptExpansion: slash-command skill expansion bootstrap + activation
│   ├── rtl-edit-tracker.sh              #   PreToolUse/PostToolUse/PostToolUseFailure:Edit/Write/Bash: RTL tracking + P6 stale
│   ├── rtl-phase-state-bootstrap.sh     #   PreToolUse+PostToolUse:Skill: phase state bootstrap
│   ├── rtl-skill-activation.sh          #   PreToolUse+PostToolUse:Skill: skill completion loop
│   ├── rtl-team-owner.sh                #   PostToolUse:Edit/Write: team-owner.json fingerprint recording
│   ├── rtl-team-progress.sh             #   PostToolUse:TaskUpdate: team progress tracking + heartbeat
│   ├── rtl-spawn-context.sh             #   PreToolUse:Agent: spawn context manifest
│   ├── rtl-audit-spawn-complete.sh      #   PostToolUse:Agent: audit spawn completion
│   ├── rtl-audit-subagent.sh            #   SubagentStart/SubagentStop: per-subagent audit capture
│   ├── rtl-verify-stop-gate.sh          #   Stop: RTL verification gate
│   ├── rtl-p6-cascade-gate.sh           #   Stop: Phase 6 cascade enforcement
│   ├── rtl-skill-completion-gate.sh     #   Stop: skill completion enforcement
│   ├── rtl-coverage-exclusion-gate.sh   #   Stop: coverage exclusion approval enforcement
│   ├── stop-gate.sh                     #   Stop: autopilot state gate
│   └── lib/                             #   shared sh libs (json-util.sh, flock-util.sh, posix-util.sh,
│                                        #     hook-output-util.sh, spawn-context-util.sh,
│                                        #     team-gate-util.sh, audit-util.sh, artifact-map.sh,
│                                        #     compliance-gate-util.sh, rat-dir-util.sh, stop-budget-util.sh,
│                                        #     skill-event-util.sh, python-util.sh) + Python hook logic
│                                        #     (verify_gate.py, session_inject.py)
├── plugin_docs/                         # Plugin development documents (tracked)
│   ├── specs/                           #   Design specifications
│   ├── plans/                           #   Implementation plans
│   └── agent-lib/                       #   Shared agent prompt fragments — dev sources synced
│                                        #     INTO agents/*.md, never loaded at runtime
│                                        #     (team-worker-preamble.md, team-worker-protocol.md,
│                                        #      team-fallback.md, domain-expert-discovery-protocol.md,
│                                        #      audit-output-protocol.md, step0-template.md)
├── domain-packages/
│   ├── video-codec/                     #   H.264/H.265 domain knowledge
│   └── video-processing/                #   Video processing domain knowledge
├── docker/Dockerfile                    # EDA environment container
├── .claude-plugin/marketplace.json      # Marketplace; systemverilog-lsp is an external GitHub source
├── tests/                               # Unit + integration test suite
├── scripts/                             # Utility scripts
│   ├── post-install.sh                  #   One-time EDA environment check
│   ├── rat_compat.py                    #   Python floor and compatibility level (parses under any Python)
│   └── ...                              #   (other helper scripts)
└── .rat/                                # Runtime state (gitignored, created per-project)
```

---

## Skill & Agent Routing

The authoritative routing table (natural language pattern → skill/agent mapping) lives in
`skills/rtl-orchestrate/SKILL.md` — the **single source of truth** for all routing decisions.

This routing is delivered via two mechanisms:
- **SessionStart hook** (`hooks/rtl-orchestrator-inject.sh`): condensed routing auto-injected for users
- **Internal reference skill** (`skills/rtl-orchestrate/SKILL.md`): the maintainer-facing SSOT and the sync source for the hook above. It carries both `user-invocable: false` and `disable-model-invocation: true`, so **nothing loads it at runtime** — not users, not the model, not agents. Anything the runtime must know has to travel through the `SESSIONSTART_HOOK_EXPORT` block (or through an agent/skill prompt); content that lives only in the body reaches no one. v0.14.1 lost pipeline rules 10-11 (the PPA-Opt gates) this way.

Routing contract:
- User intent routes to **Action Skills first**.
- Orchestrator agents are spawned by Action Skills via `Task()`.
- Policy fragments are generated into their consuming agents by `scripts/sync_agent_policies.py`; convention skills remain preloaded.

When adding or modifying skills/agents, update `skills/rtl-orchestrate/SKILL.md`. The
SessionStart hook reads its export block at session start, so no regeneration step exists.

## Pipeline Rules (policy + enforcement map)

These rules define the canonical pipeline order. Enforcement is intentionally
asymmetric: **Rule 5 is hook-enforced (hard gate)**, the rest are **policy
declarations** carried through skill entry prerequisites. Missing upstream
artifacts at skill entry produce `WARNING: ... not found — proceeding with
reduced scope` rather than a hard block, per the "Asymmetric Phase Gate
Design" principle (exit gates strict, entry gates flexible — see Core
Principles below). Direct skill invocation that bypasses the pipeline
order will therefore warn but still execute with adaptive scope.

| # | Rule | Enforcement |
|---|------|-------------|
| 1 | Do not start RTL coding without a specification (spec-analyst first) | Policy — skill entry warning |
| 2 | Do not write a Testbench without a Reference Model | Policy — skill entry warning |
| 3 | Do not run synthesis without RTL code | Policy — skill entry warning |
| 4 | Do not run Formal verification without passing Lint | Policy — skill entry warning (`rtl-p5s-sva-check`) |
| 5 | **Do not declare completion after RTL modification without functional verification** (lint alone is insufficient) | **Hard — `rtl-verify-stop-gate.sh` blocks the stop (Claude keeps working) until `.rat/state/rtl-verify-done` or `rtl-verify-waiver` is present. It hands the decision to the user after `RAT_STOP_BLOCK_LIMIT` (default 3) blocks without progress in one continuation chain, or from the chain's seventh Stop on, whichever comes first. The seventh-Stop bound follows `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP`. While a background agent or workflow is in flight, the gate lets the Stop through and enforces at the Stop of the turn its completion starts; the no-progress count carries over. `verification.stop_gate` = `notify` or `off` relaxes it per project (the user's decision); `eda_runner.py verify-run` turns a project's own runner, local or remote, into evidence.** |
| 6 | Do not proceed to Phase 5 without per-module unit tests upon Phase 4 completion + Stream B artifacts | Policy — skill entry warning (`rtl-p5-verify`) |
| 7 | When Phase 5 FAILs, allow a maximum of 2 Phase 4 feedback loops; escalate to user if exceeded | Policy — loop counter tracked by phase state; escalation advisory |
| 8 | Do not proceed to Phase 6 without Phase 5 PASS (final-compliance.md verdict=PASS required) | Policy — skill entry warning (`rtl-p6-design-review`); orchestrator rechecks verdict |
| 9 | Phase 7 is exempt from pipeline rules | N/A (by design) |
| 10 | Do not start DC-based PPA optimization without Phase 5 PASS | Policy — skill entry warning |
| 11 | Every PPA-Opt iteration must pass equivalence + smoke before accepting patch | Policy — orchestrator/skill internal guard (fail → rollback; not hook-enforced) |

**Intent**: The pipeline rules act as an **SSOT contract**, not as executable
guards. Hook-enforcement is reserved for cases where a silent bypass would
compromise correctness guarantees (Rule 5, because RTL-without-verify is the
single most likely source of undetected regressions). All other rules rely on
phase skills emitting warnings and orchestrators adapting scope — this keeps
the pipeline resumable and tolerant of partial re-runs. If you need stricter
enforcement for a specific rule, add a hook in `hooks/*.sh` rather than
strengthening the policy text here.

## 6+1 Phase Design Pipeline

```
Phase 1: Research     → docs/phase-1-research/       (spec, domain knowledge)
Phase 2: Arch/Ref     → docs/phase-2-architecture/    + refc/ (C golden)
Phase 3: μArch/TLM    → docs/phase-3-uarch/           + BFM
Phase 4: RTL+Unit     → rtl/{module}/ + sim/{module}/  + docs/phase-4-rtl/
Phase 5: Verify       → formal/ + docs/phase-5-verify/
Phase 6: Design Note  → reviews/phase-6-review/
Phase 7: Exploration  → docs/phase-7-exploration/      (optional, no pipeline rules)
(optional) Post-Verify PPA  → docs/ppa-opt/             (DC-based loop, between P5 and P6)
```

Artifacts: `docs/phase-N-*/` (design guides), `reviews/phase-N-*/` (verdicts). Details in each directory's CLAUDE.md.

## Core Principles

**Hierarchical Spec Compliance**: Lower stages must never violate upper stage specs. Spec → Arch → μArch → RTL → Verify. Details in `skills/rtl-orchestrate/SKILL.md`.

**Light review**: One review against the evidence, then stop and name the open items. A further round only when the user asks. With no measurement, the model's confidence is the gate: one spec reading, or one architecture choice, passes. Do not iterate to raise it. Low confidence is named and asked once. Lint, simulation, formal, coverage, synthesis, CDC, and model comparison are judged from the measured result. Confidence does not override a measurement. Prompts state the goal, the constraints, the evidence, and the done condition. Leave effort at the session default. Details in `skills/rtl-orchestrate/SKILL.md`.

**Document-as-Memory**: Design artifacts are persistent memory. Each phase reads upstream docs, writes downstream. Enables resumability. Details in `skills/rtl-orchestrate/SKILL.md`.

**Asymmetric Phase Gate Design**: Exit gates are strict (artifact existence verification required), entry gates are flexible (WARNING + proceed with available artifacts). This ensures downstream phases never receive incomplete inputs, while allowing upstream-incomplete phases to proceed with adaptive scope reduction. Details in `skills/rtl-orchestrate/SKILL.md`.

**Cross-Phase Artifact Functional Consistency**: Each phase produces verification artifacts (Phase 2 refC, Phase 3 BFM, Phase 4 unit tests, Phase 5 testbenches) that MUST be functionally validated against their upstream reference — not merely checked for existence and compilation. Validation gates must verify **functional correctness** (output comparison), not just **structural correctness** (file exists + compiles).

- **Phase 1 (Research)**: Excluded — produces requirements, not executable verification artifacts.
- **Phase 2 refC**: If an external golden C model is provided (e.g., JM/HM for H.264/H.265, vendor-supplied model at `vendor_ref/` or similar), refC must produce bitexact-matching output against it. If no external golden exists, refC must satisfy Phase 1 requirements via self-test.
- **Phase 3 BFM** (enforced via G4b gate): Builds on Phase 2 refC with timing/pipeline detail. BFM per-block functional output must match refC output (data correctness, bitexact or within documented tolerance). The BFM validation gate must run both models with shared test vectors, compare per-block outputs, and FAIL on mismatch.
- **Phase 4 unit tests** (enforced: refC comparison via DPI-C/file; gap: BFM I/O logs not yet consumed): Verify RTL against Phase 2 refC golden output. BFM I/O log integration planned.
- **Phase 5 testbenches** (enforced: refC-based oracle comparison): Validate RTL against Phase 1 requirements using Phase 2 refC as oracle.
- **Phase 6 (Design Note)**: Excluded — documentation/review phase, no executable verification artifacts.

A verification artifact that compiles but produces wrong output is worse than no artifact — it provides false confidence and propagates errors downstream. Details in `skills/rtl-orchestrate/SKILL.md`.

## Coding Conventions (Core Overrides)

1. **Port prefix**: `i_`, `o_`, `io_` (NOT suffix). Clock/reset exempt
2. **Clock**: `clk` (single) or `{domain}_clk` (multiple, e.g., `sys_clk`). **Reset**: `rst_n` (single) or `{domain}_rst_n` (multiple). Active-low async
3. **No CamelCase**: `snake_case` or `ALL_CAPS` only. Parameters `ALL_CAPS`, localparam `L_` prefix
4. SV RTL: IEEE 1800-2009. SV Verification: IEEE 1800-2012. C ref model: C11. C++ BFM: C++17
5. Convention skills are loaded by writer agents via their `skills:` frontmatter (rtl-coder→systemverilog, bfm-dev→systemc, testbench-dev/sva-extractor/protocol-checker→systemverilog-assertion/uvm); naming basics also enforced by the deployed `.claude/rules` file on .sv access
6. **No forward references**: all declarations before logic blocks (IEEE 1800 §12.5). Xcelium strictly enforces declaration ordering

Full rules: `.claude/rules/rtl-coding-conventions.md`. Verification gate: `.claude/rules/rtl-verification-gate.md`. Diagram rules: `<markdown_diagram_rule>` in CLAUDE.md (or `.claude/rules/diagram-rules.md` fallback).

## Hook-Based Enforcement

All 18 hook scripts and their enforcement responsibilities are listed below.

| Hook Script | Event | Enforcement |
|-------------|-------|-------------|
| `rtl-orchestrator-inject.sh` | SessionStart | Inject routing rules + pipeline rules for user projects |
| `rtl-audit-init.sh` | SessionStart | Initialize audit session directory and trace log |
| `rtl-parser-warning.sh` | SessionStart | Warn in RAT projects when neither `jq` nor Python is available for JSON parsing |
| `rtl-eda-context.sh` | SessionStart, SubagentStart | Inject short EDA settings lookup hint and export `CLAUDE_PLUGIN_DATA` when configured |
| `rtl-skill-expansion.sh` | UserPromptExpansion | Run phase state bootstrap and skill activation for `/rtl-agent-team:*` slash commands |
| `rtl-edit-tracker.sh` | PreToolUse, PostToolUse, PostToolUseFailure:Edit/Write/Bash | Track .sv file modifications for verification gate, Phase 6 stale detection, and background task tracking |
| `rtl-phase-state-bootstrap.sh` | PreToolUse:Skill, PostToolUse:Skill | Bootstrap phase state and enforce phase-entry preconditions for skill invocation |
| `rtl-skill-activation.sh` | PreToolUse:Skill, PostToolUse:Skill | Setup and phase advisory before the call; completion-loop state (criteria, same-skill counter reset) once the call ran |
| `rtl-team-owner.sh` | PostToolUse:Edit/Write | Record owning session and `team-config.json` fingerprint in `team-owner.json` |
| `rtl-team-progress.sh` | PostToolUse:TaskUpdate | Team progress tracking during native team mode; an in-process teammate's TaskUpdate refreshes team-config.json (team heartbeat) |
| `rtl-spawn-context.sh` | PreToolUse:Agent | Spawn context manifest for agent spawns |
| `rtl-audit-spawn-complete.sh` | PostToolUse:Agent | Log spawn completion events to audit trace |
| `rtl-audit-subagent.sh` | SubagentStart, SubagentStop | Log subagent lifecycle events to audit trace |
| `rtl-verify-stop-gate.sh` | Stop | RTL verification gate (lint alone insufficient) |
| `rtl-p6-cascade-gate.sh` | Stop | Phase 6 cascade (RTL change after P6 → re-review) + document mtime verification |
| `rtl-skill-completion-gate.sh` | Stop | Bounded completion reminder; no automatic review ladder |
| `rtl-coverage-exclusion-gate.sh` | Stop | Coverage exclusion approval (non-standard bins require user confirmation) |
| `stop-gate.sh` | Stop | Autopilot pauses for a user decision after two failed measured repairs at the active gate |

**State files**: Stored under `.rat/state/`. Pipeline state, verification gates, skill completion tracking, and each Stop gate's no-progress budget (`stop-budget-<gate-id>.txt`).

## Native Team Mode

P1–P5 run sequentially by default. When the user requests a team, the phase
skill follows `runtime/workflows/team-leader.md`. The main session creates the
team and starts the phase orchestrator as its coordinator. The coordinator
assigns workers to independent tasks and reports the phase gate result. The
leader shuts down the team after that message. If team creation fails, the
skill uses the sequential entry point.

The main session writes `.rat/state/team-config.json`. The Write hook records
the owning session and the file fingerprint in `.rat/state/team-owner.json`.
A current, matching record lets Stop hooks distinguish workers from the leader.
After two hours without in-process teammate activity, the Stop gates, edit
tracker and skill activation remove stale team configuration.

<!-- RTL-AGENT-TEAM:END -->
