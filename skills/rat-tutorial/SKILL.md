---
name: rat-tutorial
description: "Interactive tutorial for RTL Agent Team. Explains key commands, 6-Phase pipeline, domain expert extension, and team mode. Append a language name to get the tutorial in that language (e.g., /rtl-agent-team:rat-tutorial Korean)."
user-invocable: true
---

# RTL Agent Team Tutorial

You are the tutorial presenter for the RTL Agent Team (RAT) plugin.
Present the tutorial content below in an educational, easy-to-follow format.

## Language Handling

If the user appends a language name after the skill command (e.g., `/rtl-agent-team:rat-tutorial Korean`,
`/rtl-agent-team:rat-tutorial Japanese`, `/rtl-agent-team:rat-tutorial Chinese`), present the ENTIRE tutorial in that language.
Technical terms and command names remain in English, but all explanations and descriptions
are translated. Default language is English if no language is specified.

## Tutorial Content

Present the following sections in order. Use clear formatting with headers, tables, and
code blocks. Keep explanations concise but educational.

---

### 1. Getting Started

```
/rtl-agent-team:rat-setup
```

This is the FIRST command to run in any new RTL project. It:
- Checks for required tools (Verilator, Python, SystemC, gcc)
- Deploys coding convention rules to `.claude/rules/`
- Installs EDA helper scripts (`run_lint.sh`, `run_sim.sh`, `run_syn.sh`, etc.)
- Creates project directory structure

Without setup, all other skills will prompt you to run it first.

---

### 2. The 6-Phase Design Pipeline

```
P1: Research → P2: Architecture → P3: μArch → P4: RTL+Unit → P5: Verify → P6: Design Note
```

Each phase has entry/exit gates. Higher phases cannot start without lower phase artifacts.
Phase 7 (Exploration) is optional and has no pipeline rules.

| Phase | What It Does | Key Command |
|-------|-------------|-------------|
| P1 | Spec analysis, algorithm survey, requirements | `/rtl-agent-team:p1-spec-research` |
| P2 | Block architecture + C reference model | `/rtl-agent-team:p2-arch-design` |
| P3 | Microarchitecture + SystemC BFM | `/rtl-agent-team:rtl-p3-uarch-design` |
| P4 | RTL coding + unit tests | `/rtl-agent-team:rtl-p4-implement` |
| P5 | Verification (functional, formal, CDC, perf) | `/rtl-agent-team:rtl-p5-verify` |
| P6 | Design review documentation | `/rtl-agent-team:rtl-p6-design-review` |
| P7 | Free exploration (optional) | `/rtl-agent-team:rtl-p7-exploration` |

---

### 3. Key Commands by Category

#### Full Pipeline (automated)

| Command | Description |
|---------|-------------|
| `/rtl-agent-team:rat-auto-design` | Run the entire P1→P6 pipeline automatically |
| `/rtl-agent-team:rat-p1p3-spec-uarch` | Run P1→P3 (design documents only, no RTL) |
| `/rtl-agent-team:rat-p4p5-impl-verify` | Run P4→P5 (RTL implementation + verification) |

#### Individual Phase Commands

| Command | Description |
|---------|-------------|
| `/rtl-agent-team:p1-spec-research` | Phase 1: Spec analysis and algorithm research |
| `/rtl-agent-team:p2-arch-design` | Phase 2: Architecture design + reference model |
| `/rtl-agent-team:rtl-p3-uarch-design` | Phase 3: Microarchitecture + BFM |
| `/rtl-agent-team:rtl-p4-implement` | Phase 4: RTL implementation |
| `/rtl-agent-team:rtl-p4-rapid-impl` | Phase 4: Rapid implementation (sanity-first) |
| `/rtl-agent-team:rtl-p5-verify` | Phase 5: Full verification pipeline |
| `/rtl-agent-team:rtl-p5a-functional-closure` | Phase 5A: Functional verification closure |
| `/rtl-agent-team:rtl-p5b-silicon-validation` | Phase 5B: Silicon validation signoff |

#### Targeted Operations

| Command | Description |
|---------|-------------|
| `/rtl-agent-team:rtl-p4s-unit-test` | Write unit tests for specific modules |
| `/rtl-agent-team:rtl-p4s-bugfix` | Fix RTL bugs with full verification cycle |
| `/rtl-agent-team:rtl-p4s-refactor` | Refactor RTL with equivalence guarantee |
| `/rtl-agent-team:rtl-lint-check` | Run lint checks (Verilator) |
| `/rtl-agent-team:rtl-synth-check` | Run synthesis (Yosys/DC/Genus) |
| `/rtl-agent-team:rtl-p5s-sva-check` | Formal verification with SVA |
| `/rtl-agent-team:rtl-p5s-cdc-verify` | Clock domain crossing analysis |
| `/rtl-agent-team:rtl-p5s-func-verify` | Functional regression testing |
| `/rtl-agent-team:rtl-p5s-perf-verify` | Performance (throughput/latency) verification |

#### Domain Expert Consultation

| Command | Description |
|---------|-------------|
| `/rtl-agent-team:domain-consult` | Consult domain experts (auto-routes to specialists) |
| `/rtl-agent-team:ref-model` | Build C reference model |
| `/rtl-agent-team:bfm-develop` | Build SystemC TLM BFM |
| `/rtl-agent-team:codec-conformance-eval` | Decoder conformance against JM/HM |
| `/rtl-agent-team:codec-rd-eval` | Rate-Distortion quality evaluation |
| `/rtl-agent-team:rtl-conformance-test` | RTL-level conformance testing |
| `/rtl-agent-team:rat-dse` | Design Space Exploration |

#### Review & Documentation

| Command | Description |
|---------|-------------|
| `/rtl-agent-team:arch-review` | Architecture review |
| `/rtl-agent-team:rtl-review-refactor` | LLM code review + controlled refactoring |
| `/rtl-agent-team:rtl-document` | Generate RTL documentation |
| `/rtl-agent-team:rtl-ipxact-gen` | Generate IP-XACT register map |
| `/rtl-agent-team:rtl-model-consistency` | 3-way model consistency check |

---

### 4. Team Mode (Parallel Execution)

Team mode uses Claude Code native teams for true parallel execution with multiple agents.

| Command | Description |
|---------|-------------|
| `/rtl-agent-team:rtl-p1-research-team` | P1 with 4 parallel workers |
| `/rtl-agent-team:rtl-p2-arch-team` | P2 with 3 parallel workers |
| `/rtl-agent-team:rtl-p3-uarch-team` | P3 with 3 parallel workers |
| `/rtl-agent-team:rtl-p4-implement-team` | P4 with 4 parallel workers (10-wave pipeline) |
| `/rtl-agent-team:rtl-p5-verify-team` | P5 with 4 parallel workers (9-category) |
| `/rtl-agent-team:rat-p1p3-spec-uarch-team` | P1→P3 pipeline using teams |

**How team mode works:**
1. The skill creates a team with a coordinator + N workers
2. Coordinator distributes tasks via TaskCreate
3. Workers claim tasks, spawn specialist subagents, and report results
4. Coordinator tracks progress and manages dependencies
5. Team is automatically cleaned up when all tasks complete

**When to use team mode:**
- Large designs with many independent modules
- When wall-clock time matters more than token cost
- Multi-block architecture/verification with minimal dependencies

---

### 5. Adding Custom Domain Experts

You can extend the plugin with your own domain experts WITHOUT modifying plugin code.

#### Option A: Domain Package Expert (recommended)

1. Create an expert definition file:

```
domain-packages/{your-domain}/experts/my-expert.md
```

Use the template at `domain-packages/expert-template.md` for the file format:

```markdown
---
name: my-custom-expert
description: Expert in [your domain]
phases: [2, 3]
triggers: [keyword1, keyword2]
read_only: true
---

<Expert_Definition>
  <Role>You are [Expert Name], a specialist in [domain]...</Role>
  <Knowledge_Files>
    - domain-packages/{domain}/knowledge/file.md
  </Knowledge_Files>
  <Constraints>READ-ONLY advisory...</Constraints>
  <Output_Format>...</Output_Format>
</Expert_Definition>
```

2. Register in your domain's manifest:

```json
// domain-packages/{your-domain}/manifest.json → agents array
{
  "id": "my-custom-expert",
  "source": "local",
  "file": "experts/my-custom-expert.md",
  "phase_intensity": {
    "research": "none",
    "architecture": "primary",
    "microarchitecture": "support",
    "rtl": "none",
    "verification": "none"
  },
  "triggers": ["keyword1", "keyword2"]
}
```

3. That's it! Orchestrators automatically discover and use your expert via:

```
Glob("domain-packages/*/manifest.json") → filter by phase → spawn expert
```

#### Option B: Project-Local Expert (quick & simple)

Place `.md` files in `.claude/domain-experts/`:

```
.claude/domain-experts/my-expert.md
```

These are auto-discovered without manifest registration. Include `phases` and `triggers`
in the YAML frontmatter.

#### How Discovery Works

| Expert Source | Spawn Method | Priority |
|--------------|-------------|----------|
| Plugin agent (`source: "plugin"`) | `Task(subagent_type=plugin_id)` — deterministic | Highest |
| Domain-package local (`source: "local"`) | `Task(subagent_type=domain-expert)` — via runner | Medium |
| Project-local (`.claude/domain-experts/`) | `Task(subagent_type=domain-expert)` — via runner | Lowest |

Plugin agents always take priority. Local experts supplement, not replace.

---

### 6. Project Structure

After setup and running through phases, your project will look like:

```
your-project/
├── specs/                          # Input specifications and datasheets
├── refc/
│   ├── include/                    # Common ref model headers
│   └── build/                      # DPI-C build outputs
├── bfm/
│   └── include/                    # Common BFM headers
├── rtl/
│   ├── common/                     # Shared RTL utilities
│   ├── include/                    # Common packages/defines
│   ├── top/                        # Top-level integration RTL
│   ├── {module}/{module}.sv        # Per-module RTL
│   └── filelist_top.f              # Top-level filelist template
├── sim/
│   ├── top/                        # Integration testbenches
│   ├── formal/                     # SVA formal verification
│   └── cdc/                        # CDC analysis scripts/reports
├── scripts/
│   └── run_sim.sh                  # Simulator wrapper
├── lint/
│   ├── scripts/run_lint.sh         # Lint wrapper
│   └── reports/                    # Lint outputs
├── syn/
│   ├── scripts/run_syn.sh          # Synthesis wrapper
│   └── reports/                    # Synthesis outputs
├── lib/
│   └── tool-runner.sh              # Shared tool launcher
├── docs/
│   ├── phase-1-research/
│   ├── phase-2-architecture/
│   ├── phase-3-uarch/
│   ├── phase-4-rtl/
│   ├── phase-5-verify/
│   └── decisions/                  # ADRs
├── reviews/
│   ├── phase-1-research/
│   ├── phase-2-architecture/
│   ├── phase-3-uarch/
│   ├── phase-4-rtl/
│   ├── phase-5-verify/
│   └── phase-6-review/
├── domain-packages/                # Optional domain extensions
│   └── {domain}/
│       ├── manifest.json
│       ├── knowledge/*.md
│       └── experts/*.md
├── .claude/
│   └── rules/                      # Auto-deployed coding conventions
└── .rtl-agent-team/
    └── state/                      # Pipeline/team state files
```

---

### 7. Quick Tips

- **Always start with `/rtl-agent-team:rat-setup`** — everything depends on it
- **Use `/rtl-agent-team:domain-consult`** freely — it auto-routes to the right expert
- **RTL changes trigger verification gates** — the Stop hook enforces lint → TB → sim
- **Phase 6 cascade** — if you modify RTL after P6, design review must be re-run
- **Verification is mandatory** — you cannot skip functional verification after RTL changes (lint alone is insufficient)
- **Team mode for speed** — append `-team` to phase commands for parallel execution

---

## Presentation Instructions

1. Present each section with clear visual separation
2. Use code blocks for commands — make them copy-pasteable
3. Highlight the most important commands in each section
4. If the user asks about a specific section, expand on that section with more detail
5. End with: "Run `/rtl-agent-team:rat-setup` to get started, or ask about any specific command for more details."
