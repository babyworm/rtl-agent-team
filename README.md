> **한국어 문서**: [README_kr.md](./README_kr.md)

# RTL Agent Team

> A Claude Code plugin for automated RTL design and verification.
> 50 specialized AI agents + 37 skills automate the 6-Phase pipeline:
> Research → Architecture → μArch → RTL → Verify → Design Note.

A Claude Code plugin for automated RTL design and verification.

Automates the 6-Phase design pipeline (Research → Architecture → μArch → RTL → Verify → Design Note) with 50 specialized AI agents + 37 skills + 11 reference documents.

## Marketplace

This repository serves as the **RTL Agent Marketplace**, providing hardware design plugins.

| Plugin | Description | Version |
|--------|-------------|---------|
| **rtl-agent-team** | 50-agent RTL design pipeline (Research → Architecture → μArch → RTL → Verify → Design Note) | 0.1.0 |
| **systemverilog-lsp** | SystemVerilog/Verilog LSP (slang-server based — diagnostics, hover, go-to-definition, etc.) | 1.1.0 |

Additional plugins (domain knowledge packages, MCP servers, specialized skills, etc.) will be added to the Marketplace over time.

## Quick Start

```bash
# 1. Register the Marketplace
/plugin marketplace add babyworm/rtl-agent-team

# 2. Install plugins
/plugin install rtl-agent-team
/plugin install systemverilog-lsp   # (optional) SV LSP

# 3. Check environment
/rtl-agent-team:rtl-setup

# 4. Full automation (or "Design an H.264 TQ subsystem")
/rtl-agent-team:rtl-autopilot
```

## Installation

### Install from Claude Code chat (recommended)

```
/plugin marketplace add babyworm/rtl-agent-team
/plugin install rtl-agent-team
```

Verify installation: `/plugin`

### Install from CLI

```bash
claude plugin marketplace add babyworm/rtl-agent-team
claude plugin install rtl-agent-team
```

### Local symlink for development

When developing with direct access to the plugin source:

```bash
git clone https://github.com/babyworm/rtl-agent-team.git
ln -s "$(pwd)/rtl-agent-team" ~/.claude/plugins/local/rtl-agent-team
```

## Usage

### Full automation

```
/rtl-agent-team:rtl-autopilot
```

Runs the entire 6-Phase pipeline automatically. You can also use natural language, e.g., "Design an H.264 TQ subsystem".

### Pipeline composition (split execution)

```
/rtl-agent-team:rtl-dse              # Phase 1→2: Deep algorithm + architecture exploration (DSE)
/rtl-agent-team:rtl-spec-to-uarch    # Phase 1→3: Spec → μArch design documents
/rtl-agent-team:rtl-uarch-to-verify  # Phase 4→5: μArch → RTL implementation + verification
```

Split the pipeline for human review between design and implementation:
- `rtl-dse`: Deep Design Space Exploration — compare multiple algorithms and architecture candidates with quantitative trade-offs. Can also transform an existing functional C model into an architectural reference model. Stops at Phase 2 for review.
- `rtl-spec-to-uarch`: Standard Phase 1→3 — produce design documents through μArch. Stops for review before RTL.
- `rtl-uarch-to-verify`: Phase 4→5 — implement RTL and run full verification from approved μArch documents.

### Resume interrupted pipeline

If `rtl-autopilot` is interrupted, progress is saved automatically. Re-run the same command to resume from the last incomplete step — completed phases are skipped.

### Project initialization

```
/rtl-agent-team:rtl-setup
```

Creates the project directory structure and verifies EDA tool installation.

### Individual skills

```
/rtl-agent-team:rtl-lint-check        # RTL lint check
/rtl-agent-team:rtl-func-verify       # cocotb functional verification
/rtl-agent-team:rtl-synth-check       # Yosys synthesis
/rtl-agent-team:rtl-sva-check         # SVA formal verification
/rtl-agent-team:arch-design       # Architecture design
/rtl-agent-team:domain-consult    # Domain expert consultation
```

See the `skills/` directory for the full list of 37 skills.

## Project Artifact Structure

Each Phase's design artifacts (`docs/`) serve as inputs to the next Phase, forming a pipeline.
Spec compliance verdicts (`reviews/`) are managed separately.

```
docs/phase-1-research/ ──→ docs/phase-2-architecture/ ──→ docs/phase-3-uarch/
        ──→ docs/phase-4-rtl/ ──→ docs/phase-5-verify/ ──→ docs/phase-6-design-note/
        ──→ docs/phase-7-exploration/ (optional, free exploration)
```

| Directory | Role | Notes |
|-----------|------|-------|
| `docs/phase-N-*/` | Phase-specific design documents (guide pipeline) | Phase N → Phase N+1 input |
| `reviews/phase-N-*/` | Spec compliance verdict (PASS/FAIL) | Verdict only, no data |
| `rtl/src/` | RTL SystemVerilog source code | Phase 4 code artifact |
| `tb/unit/`, `tb/formal/` | Testbenches | Phase 4-5 code artifacts |
| `ref_model/` | C golden reference model (DPI-C compatible) | Phase 2 code artifact |
| `docs/decisions/` | Architecture Decision Records (ADR) | Phase 2-3 decision rationale |
| `docs/lessons-learned.md` | Lessons learned from feedback loops | Accumulated across phases |

## Plugin Structure

```
rtl-agent-team/
├── .claude-plugin/
│   ├── plugin.json             # Plugin manifest (auto-discovery)
│   └── marketplace.json        # Marketplace definition
├── CLAUDE.md                   # 6-Phase pipeline rules
├── agents/                     # 50 agents (design/verification/review/EDA/domain)
├── skills/                     # 37 skills (SKILL.md + templates/ + examples/)
│   ├── systemverilog/          # RTL coding conventions (lowRISC + overrides)
│   ├── systemverilog-assertion/ # SVA coding conventions (bind, SymbiYosys)
│   ├── uvm/                    # UVM coding conventions (factory, TLM, coverage)
│   └── systemc/                # SystemC/TLM-2.0 (AT non-blocking, AMBA-PV)
├── references/                 # 11 detailed reference documents
│   ├── coding-style-guide.md   # SV naming conventions (detailed)
│   ├── axi-protocol-rules.md   # AXI4 per-channel SVA templates
│   ├── sva-patterns.md         # SVA temporal operators + pattern library
│   ├── cocotb-ecosystem.md     # cocotb API, cocotb-bus, coverage
│   └── ...                     # + 7 more (CDC, UVM, Yosys, SDC, etc.)
├── docker/                     # EDA tool Docker image
│   └── Dockerfile              # Open-source EDA full bundle
└── domain-packages/            # Domain knowledge packages
    └── video-codec/            # H.264/H.265 knowledge, conformance data
```

## Agent Team

### Agent Composition (50 agents, all Opus)

| Category | Count | Key Agents |
|----------|-------|------------|
| Design | 8 | spec-analyst, arch-designer, rtl-architect, uarch-designer, rtl-coder, rtl-critic, rtl-planner, rtl-explorer |
| Verification | 7 | testbench-dev, func-verifier, perf-verifier, sva-extractor, protocol-checker, coverage-analyst, waveform-analyzer |
| Specialized Review | 13 | cdc-reviewer, protocol-reviewer, formal-reviewer, power-analyzer, synthesis-reviewer, uvm-reviewer, cocotb-reviewer, ref-model-reviewer, requirement-tracer, regression-analyzer, equivalence-checker, integration-verifier, security-reviewer |
| Phase 6 Design Note | 4 | code-quality-reviewer, design-quality-reviewer, design-note-writer, improvement-analyst |
| EDA/Synthesis | 8 | eda-runner, synthesis-reporter, lint-checker, constraint-writer, timing-advisor, cdc-checker, clock-architect, dft-designer |
| Infrastructure | 3 | ipxact-generator, bfm-dev, ref-model-dev |
| Domain Experts | 7 | vcodec-chief-standard-expert, vcodec-syntax-entropy-expert, vcodec-prediction-expert, vcodec-transform-quant-expert, vcodec-filter-recon-expert, vcodec-architecture-expert, video-processing-expert |

### 6-Phase Pipeline (+Phase 7 Optional Exploration)

| Phase | Name | Key Agents | docs/ Artifacts | reviews/ Verdict |
|-------|------|------------|-----------------|------------------|
| 1 | Research | spec-analyst | requirements.json, io_definition.json, domain-analysis.md | research-review.md |
| 2 | Architecture + Ref Model | arch-designer, ref-model-dev | architecture.md | architecture-review.md |
| 3 | μArch + BFM | uarch-designer, bfm-dev | {module}.md (per module) | uarch-review.md |
| 4 | RTL + Unit Test | rtl-coder, lint-checker | module-descriptions.md, unit-test-design.md, Stream B artifacts | design-review.md |
| 5 | Verify | func-verifier, sva-extractor | unit-test-report.md, lint-report.md, etc. | final-compliance.md, e2e-traceability.md |
| 6 | Design Note | code-quality-reviewer, design-note-writer | design-note.md, improvements.md | code-review.md, design-review.md |
| 7 | Exploration (optional) | improvement-analyst | exploration-notes.md | exploration-review.md |

> **Additional pipeline artifacts:** Each Phase (1-5) generates `phase-N-summary.md` for downstream context compression. Phase 4 Stream B produces SVA/CDC/TB skeletons in parallel with RTL coding. Phase 2-3 record Architecture Decision Records in `docs/decisions/`.

### Coding Convention Skills

| Skill | Target | Key Content |
|-------|--------|-------------|
| `systemverilog` | `.sv`, `.svh`, `.v`, `.vh` | lowRISC + project overrides, Power, FPGA, Pipelining |
| `systemverilog-assertion` | SVA, bind files | assume/assert/cover, SymbiYosys, bind patterns |
| `uvm` | UVM testbench | factory, TLM ports, coverage, phase callback |
| `systemc` | `.cpp`, `.h` (SystemC) | TLM-2.0 AT non-blocking, AMBA-PV (AXI/AHB/APB), Memory Manager, PEQ |

### 3-Layer Documentation Structure (Progressive Disclosure)

| Layer | Location | Role |
|-------|----------|------|
| Core rules | `skills/*/SKILL.md` → `<Steps>` | Mandatory rules that agents always read |
| Situational guides | `skills/*/SKILL.md` → `<Advanced>` | Referenced only in specific optimization/scenarios |
| Detailed references | `references/*.md` | Command references, pattern libraries, protocol details |

## EDA Tools

The `eda-runner` agent executes local EDA CLI tools directly via Bash.

| Tool | Purpose | Required |
|------|---------|----------|
| verilator | Simulation + Lint | Required |
| verible | Style Lint + Formatting | Required |
| yosys | Synthesis | Required |
| cocotb (Python) | Functional verification | Required |
| iverilog | Alternative simulator | Optional |
| slang | IEEE 1800 semantic Lint | Optional |
| sby (SymbiYosys) | Formal verification | Optional |
| gtkwave | Waveform viewer | Optional |

Use `/rtl-agent-team:rtl-setup` to check tool installation status.

### Docker EDA Image (Recommended)

If installing EDA tools individually is cumbersome, you can build a Docker image containing all tools:

```bash
# Build image (one-time)
docker build -t rtl-eda-tools docker/

# Run with project mounted
docker run -it --rm -v $(pwd):/workspace -w /workspace rtl-eda-tools

# Build with specific versions
docker build -t rtl-eda-tools \
  --build-arg VERILATOR_VERSION=5.024 \
  --build-arg SLANG_VERSION=v6.0 \
  --build-arg SYSTEMC_VERSION=3.0.2 \
  docker/
```

Included tools: Verilator, Verible, Yosys, Icarus Verilog, slang, SystemC/TLM-2.0, SymbiYosys (+ boolector, z3), GTKWave, cocotb, cocotb-bus, cocotbext-axi, gcc/g++.

You can also build from Claude Code: "Build the EDA Docker image" or run `/rtl-agent-team:rtl-setup` and select the Docker option.

## Marketplace Structure

This repository operates as a **marketplace**, not a single plugin.

```
rtl-agent-team/                          # Marketplace root
├── .claude-plugin/
│   ├── plugin.json                      # rtl-agent-team plugin manifest
│   └── marketplace.json                 # Marketplace definition (plugin list)
├── agents/                              # rtl-agent-team agents (50)
├── skills/                              # rtl-agent-team skills (37)
├── references/                          # Reference documents (11)
├── plugins/
│   └── systemverilog-lsp/               # SV LSP plugin (standalone)
└── domain-packages/                     # Domain knowledge packages
    └── video-codec/                     # H.264/H.265 codec knowledge
```

To add a new plugin to the Marketplace, add an entry to the `plugins` array in `marketplace.json`:
- Same repo: `"source": "./plugins/new-plugin"`
- External repo: `"source": {"source": "github", "repo": "owner/repo"}`

## Development

This plugin is purely declarative (`.md` + `.json` files only) — no build step required.

```bash
git clone https://github.com/babyworm/rtl-agent-team.git
ln -s "$(pwd)/rtl-agent-team" ~/.claude/plugins/local/rtl-agent-team
```

## License

MIT
