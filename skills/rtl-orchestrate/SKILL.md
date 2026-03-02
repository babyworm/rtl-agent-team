---
name: rtl-orchestrate
description: "RTL design flow orchestration — complete skill routing table, agent delegation matrix, design rules, and pipeline reference. Invoke when navigating the RTL design flow, unsure which skill/agent to use, or need the full routing reference."
user_invocable: true
---

# RTL Design Flow — Orchestration Reference

Complete reference for orchestrating the RTL design pipeline. Use this when:
- Unsure which skill or agent to invoke for a given task
- Need the full routing table (natural language → skill mapping)
- Need the complete agent delegation matrix
- Want to review the design pipeline rules and principles

**This skill is informational — it injects routing context, not an action workflow.**

---

## Skill Routing Table

When RTL/HDL/FPGA/ASIC related tasks are detected, route to the appropriate skill:

| Pattern Detected | Skill to Invoke |
|-----------|------------|
| **--- Full Pipeline ---** | |
| "RTL design", "verilog", "FPGA", "ASIC", "chip design", "rtl-autopilot" | `/rtl-agent-team:rtl-autopilot` (command) |
| "setup", "initialize", "project start", "init", "docker image", "EDA docker" | `/rtl-agent-team:rtl-setup` |
| **--- Phase 1: Research ---** | |
| "spec analysis", "requirements", "paper research", "research" | `/rtl-agent-team:p1-spec-research` (command) |
| "codec consultation", "H.264", "H.265", "domain expert" | `/rtl-agent-team:domain-consult` |
| **--- Phase 2: Architecture ---** | |
| "architecture design" (RTL context) | `/rtl-agent-team:p2-arch-design` (command) |
| "architecture review", "arch review" | `/rtl-agent-team:arch-review` |
| "reference model", "ref model", "C model" | `/rtl-agent-team:ref-model` |
| "BFM", "bus functional model", "SystemC model" | `/rtl-agent-team:bfm-develop` |
| **--- Phase 3: μArch ---** | |
| "microarchitecture", "μArch", "uarch", "pipeline design" | `/rtl-agent-team:rtl-p3-uarch-design` (command) |
| **--- Pipeline Composition ---** | |
| "DSE", "design space exploration", "algorithm study", "architecture comparison" | `/rtl-agent-team:rtl-dse` (command) |
| "spec to uarch", "design only", "Phase 1-3", "design documents only" | `/rtl-agent-team:rtl-spec-to-uarch` (command) |
| "uarch to verify", "implement and verify", "Phase 4-5", "RTL from uarch" | `/rtl-agent-team:rtl-uarch-to-verify` (command) |
| "RD eval", "BD-PSNR", "BD-rate", "codec quality", "algorithm quality evaluation" | `/rtl-agent-team:codec-rd-eval` |
| "decoder conformance", "conformance stream", "conformance test", "decoder verify" | `/rtl-agent-team:codec-conformance-eval` |
| **--- Coding Conventions (auto-applied by extension/Phase) ---** | |
| `.sv`, `.svh`, `.v`, `.vh` RTL code generation | `/rtl-agent-team:systemverilog` |
| `.sv`, `.sva` (SVA, assertion, bind), formal assertion | `/rtl-agent-team:systemverilog-assertion` |
| UVM testbench, agent, sequence generation | `/rtl-agent-team:uvm` |
| `.cpp`, `.h` (SystemC/TLM), Phase 2/3 | `/rtl-agent-team:systemc` |
| **--- Phase 4: RTL ---** | |
| "bug fix", "RTL fix", "RTL bug", "functional error" | `/rtl-agent-team:rtl-p4s-bugfix` |
| "RTL coding", "module implementation", "SV writing" | `/rtl-agent-team:rtl-p4-implement` (command) |
| "refactoring", "RTL refactoring", "code cleanup" (RTL context) | `/rtl-agent-team:rtl-p4s-refactor` |
| "SV unit test", "unit test" (RTL context) | `/rtl-agent-team:rtl-p4s-unit-test` |
| "IP instance", "IP integration", "submodule connection" | `/rtl-agent-team:rtl-ip-instantiate` |
| "lint", "lint check" (RTL context) | `/rtl-agent-team:rtl-lint-check` |
| "synthesis", "yosys", "SDC" | `/rtl-agent-team:rtl-synth-check` |
| "documentation", "RTL docs" | `/rtl-agent-team:rtl-document` |
| "IP-XACT", "ipxact", "register map generation" | `/rtl-agent-team:rtl-ipxact-gen` |
| **--- Phase 5: Verify ---** | |
| "Phase 5", "verification pipeline", "extensive verification" | `/rtl-agent-team:rtl-p5-verify` (command) |
| "simulation", "functional verification", "testbench", "cocotb" | `/rtl-agent-team:rtl-p5s-func-verify` (command) |
| "UVM", "UVM verification", "sequence", "agent" (UVM context) | `/rtl-agent-team:rtl-p5s-uvm-verify` |
| "performance verification", "throughput", "latency measurement" | `/rtl-agent-team:rtl-p5s-perf-verify` |
| "formal", "SVA", "assertion" | `/rtl-agent-team:rtl-p5s-sva-check` |
| "CDC", "clock domain" | `/rtl-agent-team:rtl-p5s-cdc-verify` |
| "AXI", "APB", "AHB", "protocol" (RTL context) | `/rtl-agent-team:rtl-p5s-protocol-verify` |
| "coverage" | `/rtl-agent-team:rtl-p5s-coverage-analyze` |
| **--- Phase 6: Design Note ---** | |
| "design review", "Phase 6", "design note", "code review documentation" | `/rtl-agent-team:rtl-p6-design-review` (command) |
| **--- Phase 7: Exploration (optional) ---** | |
| "free exploration", "exploration", "Phase 7", "improvement exploration" | `/rtl-agent-team:rtl-p6-design-review` (command, exploration mode) |
| **--- Other Verification ---** | |
| "integration test", "cross-module test", "end-to-end test", "Tier 4" | `/rtl-agent-team:rtl-p5s-integration-test` |
| "regression", "multi-seed" | `/rtl-agent-team:rtl-p5s-func-verify` (Tier 3) |
| "RTL conformance", "RTL conformance test", "RTL golden comparison" | `/rtl-agent-team:rtl-conformance-test` |
| "bug reproduction", "bug repro", "waveform debug" | `/rtl-agent-team:rtl-bug-repro` |
| "model consistency", "RTL-model comparison" | `/rtl-agent-team:rtl-model-consistency` |

---

## Agent Delegation Table

RTL tasks must be delegated to specialized agents. This applies to tasks handling `.sv`, `.svh`, `.v`, `.vh` files or using EDA tools.

### Design Agents
| Task Type | Agent | Model |
|----------|-------|-------|
| Specification analysis | `spec-analyst` | Opus |
| Architecture design | `arch-designer` | Opus |
| Architecture review | `rtl-architect` | Opus |
| μArch design | `uarch-designer` | Opus |
| RTL coding | `rtl-coder` | Opus |
| RTL review | `rtl-critic` | Opus |
| Design planning | `rtl-planner` | Opus |
| Codebase exploration | `rtl-explorer` | Opus |

### Verification Agents
| Task Type | Agent | Model |
|----------|-------|-------|
| Testbench development | `testbench-dev` | Opus |
| Functional verification | `func-verifier` | Opus |
| Performance verification | `perf-verifier` | Opus |
| SVA extraction/writing | `sva-extractor` | Opus |
| Protocol compliance | `protocol-checker` | Opus |
| Coverage analysis | `coverage-analyst` | Opus |
| Waveform analysis | `waveform-analyzer` | Opus |

### Expert Review Agents (spawn directly or through skills)
| Task Type | Agent | Model |
|----------|-------|-------|
| CDC design review | `cdc-reviewer` | Opus |
| Protocol design review | `protocol-reviewer` | Opus |
| Formal quality review | `formal-reviewer` | Opus |
| Power analysis | `power-analyzer` | Opus |
| Synthesis results review | `synthesis-reviewer` | Opus |
| UVM TB quality review | `uvm-reviewer` | Opus |
| Requirement traceability | `requirement-tracer` | Opus |
| cocotb TB quality review | `cocotb-reviewer` | Opus |
| Reference model review | `ref-model-reviewer` | Opus |
| Regression analysis | `regression-analyzer` | Opus |
| Equivalence checking | `equivalence-checker` | Opus |
| Integration verification | `integration-verifier` | Opus |
| Hardware security review | `security-reviewer` | Opus |

### Phase 6 Agents
| Task Type | Agent | Model |
|----------|-------|-------|
| Code quality review | `code-quality-reviewer` | Opus |
| Design quality review | `design-quality-reviewer` | Opus |
| Design document writing | `design-note-writer` | Opus |
| Improvement analysis | `improvement-analyst` | Opus |

### EDA/Infrastructure Agents
| Task Type | Agent | Model |
|----------|-------|-------|
| EDA tool execution | `eda-runner` | Opus |
| Synthesis metrics | `synthesis-reporter` | Opus |
| Lint checking | `lint-checker` | Opus |
| SDC constraint generation | `constraint-writer` | Opus |
| Timing analysis (STA) | `timing-advisor` | Opus |
| CDC static analysis | `cdc-checker` | Opus |
| Clock architecture review | `clock-architect` | Opus |
| DFT design | `dft-designer` | Opus |
| IP-XACT generation | `ipxact-generator` | Opus |
| BFM development | `bfm-dev` | Opus |
| Reference model development | `ref-model-dev` | Opus |

### Domain Expert Agents
| Task Type | Agent | Model |
|----------|-------|-------|
| Codec chief expert | `vcodec-chief-standard-expert` | Opus |
| Syntax/entropy expert | `vcodec-syntax-entropy-expert` | Opus |
| Prediction expert | `vcodec-prediction-expert` | Opus |
| Transform/quantization expert | `vcodec-transform-quant-expert` | Opus |
| Filter/reconstruction expert | `vcodec-filter-recon-expert` | Opus |
| Codec architecture expert | `vcodec-architecture-expert` | Opus |
| Video processing expert | `video-processing-expert` | Opus |

---

## Absolute Rules (Hard Gates)

These rules MUST be enforced at all times. Violation of any rule is a pipeline-blocking error.

1. **No RTL without Spec**: Do not start RTL coding without a specification (spec-analyst first)
2. **No TB without Ref Model**: Do not write a Testbench without a Reference Model
3. **No Synthesis without RTL**: Do not run synthesis without RTL code
4. **No Formal without Lint**: Do not run Formal verification without passing Lint
5. **Verification Required**: Do not declare completion after RTL modification without functional verification (lint alone is insufficient)
6. **Unit Tests for Phase Gate**: Do not proceed to Phase 5 without per-module unit tests upon Phase 4 completion + Stream B early verification artifacts (SVA skeletons, CDC preliminary, TB skeletons)
7. **Feedback Loop Limit**: When Phase 5 FAILs, allow a maximum of 2 Phase 4 feedback loops; escalate to user if exceeded
8. **Phase 5 PASS Required**: Do not proceed to Phase 6 without Phase 5 PASS (final-compliance.md verdict=PASS required)
9. **Phase 7 Exempt**: Phase 7 is exempt from absolute rules — free exploration allowed without pipeline Gate

---

## Core Design Principles

### Hierarchical Spec Compliance
Lower stages must never violate the spec of upper stages.

```
Requirements(Spec) → Architecture → μArch → RTL → Verification
    ↑ Each stage must comply with the decisions of the stage to its left
```

- Architecture must implement all required functions from the Spec
- μArch must comply with Architecture's block boundaries and interfaces
- RTL must faithfully implement the μArch design
- Verification must validate against the original Spec requirements
- If functional changes needed → return to the upstream stage and obtain user approval

**Design priorities (RTL quality criteria):**
1. Functional Correctness (highest)
2. Interface Compliance
3. Timing/Performance
4. Area/Power

### Cascading Quality
Higher abstraction levels require MORE iterative refinement.

| Phase | Mandatory Review Iterations |
|-------|---------------------------|
| Phase 1: Research | 3 rounds (chief-coordinated) |
| Phase 2: Architecture | 3 rounds (memory, performance, ref model) |
| Phase 3: μArch | 3 rounds (performance, interface, memory) |
| Phase 4: RTL | 10-Wave pipeline (write→lint→review→fix→test→CDC→protocol→refactor→gate) |
| Phase 5: Verify | Sub-phase parallel |

Time is NOT a constraint at upper levels. Spend extra review rounds perfecting architecture and μArch.

### Document-as-Memory
Design artifacts serve as persistent memory across phases and agents.

```
requirements.json → arch-designer → architecture.md → uarch-designer → docs/phase-3-uarch/*.md → rtl-coder
reviews/phase-N/ → Quality Gate → next phase proceeds or fails
```

- Each phase reads upstream documents as input context and writes downstream documents as output
- No agent needs to "remember" another agent's output — it reads the document
- Enables resumability: any phase can restart by re-reading its input documents
- Each phase generates `phase-N-summary.md` on completion for downstream context efficiency

---

## Phase 1 Proactive Requirement Clarification

If the user's request is ambiguous or incomplete in Phase 1, proactively use AskUserQuestion to clarify.

**When to use AskUserQuestion:**
- Target resolution/frame rate/codec not specified
- Interface protocol (AXI/APB/custom) not specified
- Clock frequency or timing constraints unclear
- Functional scope ambiguous (encoder/decoder/both, profiles/levels)
- spec-analyst flags `[AMBIGUITY]` or `[CONFLICT]`

**When NOT to use:**
- User provided a detailed spec document
- Standard has only one valid interpretation
- Matter decided by design convention (e.g., active-low reset)

---

## Mandatory Verification After RTL Changes

This rule applies to ALL tasks that modify `.sv/.svh/.v/.vh` files.

| Step | Description | Required |
|------|-------------|----------|
| 1. Modify | Change RTL code | Required |
| 2. Lint | Pass `verilator --lint-only -Wall` | Required |
| 3. TB | Create or update testbench for modified module | **Required** |
| 4. Sim | Run cocotb/verilator simulation and PASS | **Required** |

**Anti-pattern (prohibited):** RTL modify → lint pass → "done"
**Correct flow:** RTL modify → lint pass → TB create/update → simulation PASS → "done"

**Gate signals:**
- Verification done: `touch .rtl-agent-team/state/rtl-verify-done`
- Waiver (non-functional changes): `touch .rtl-agent-team/state/rtl-verify-waiver`

**Phase 4 Parallel Streams:**
- Stream A: RTL coding (wave-based) → lint → unit TB → unit sim
- Stream B: SVA skeletons + CDC topology + TB skeletons (from uarch, parallel with Stream A)

---

## 6+1 Phase Design Pipeline (+Phase 7 Optional)

```
Phase 1: Research    → docs/phase-1-research/       (spec, domain knowledge)
Phase 2: Arch/Ref    → docs/phase-2-architecture/    + refc/ (C golden)
Phase 3: μArch/TLM   → docs/phase-3-uarch/           + BFM
Phase 4: RTL+Unit    → rtl/{module}/ + sim/{module}/  + docs/phase-4-rtl/
Phase 5: Verify      → sim/formal/ + docs/phase-5-verify/
Phase 6: Design Note → reviews/phase-6-review/
Phase 7: Exploration → docs/phase-7-exploration/      (optional, no pipeline rules)
```

**Artifact separation:**
- `docs/phase-N-*/` = Design artifacts (guides for next phase)
- `reviews/phase-N-*/` = Verdict documents (upper spec compliance check)

---

## 4-Tier Testing Hierarchy

| Tier | Name | Skill | Prerequisite |
|------|------|-------|-------------|
| 1 | Smoke Test | `rtl-p4-implement` Wave 4 | Lint pass |
| 2 | Unit Test | `rtl-p4s-unit-test` | Tier 1 pass |
| 3 | Module Regression | `rtl-p5s-func-verify` | Tier 2 pass |
| 4 | Integration | `rtl-p5s-integration-test` | Tier 3 pass |

Coverage targets (Tier 3): line ≥ 90%, toggle ≥ 80%, FSM ≥ 70%

---

## Coding Conventions (Core Overrides)

1. **Port prefix**: `i_`, `o_`, `io_` required (NOT suffix `_i`, `_o`). Clock/reset are exceptions (no prefix)
2. **Clock**: `clk` (single) or `{domain}_clk` (multiple). **Reset**: `rst_n` or `{domain}_rst_n`. Active-low async
3. **No CamelCase**: Parameters → `ALL_CAPS`. Localparam → `L_` prefix. Enum values → `ALL_CAPS`. All identifiers `snake_case` or `ALL_CAPS`
4. **Language Standards**: SV RTL IEEE 1800-2009, SV Verification IEEE 1800-2012, C ref model C11, C++ BFM C++17
5. **Convention skills auto-applied by file extension** (see Skill Routing Table above)

Full coding rules: `.claude/rules/rtl-coding-conventions.md`
Verification gate rules: `.claude/rules/rtl-verification-gate.md`
Diagram rules: `.claude/rules/diagram-rules.md`

---

## Domain Packages

Domain packages provide pre-built knowledge bases. Active packages:

| Package | Path | Manifest |
|---------|------|----------|
| video-codec | `domain-packages/video-codec/` | `domain-packages/video-codec/manifest.json` |

Domain expert agents MUST read relevant knowledge files from `domain-packages/{domain}/knowledge/` BEFORE producing analysis.

---

## Hook-Based Enforcement

| Hook | Event | Purpose |
|------|-------|---------|
| `rtl-orchestrator-inject.sh` | SessionStart | Inject routing rules and absolute rules |
| `rtl-project-init-advisor.sh` | SessionStart | Advise rtl-setup if project not initialized |
| `rtl-edit-tracker.sh` | PostToolUse:Edit/Write | Track RTL file modifications |
| `rtl-skill-activation.sh` | PreToolUse:Skill | Activate skill completion loop |
| `stop-gate.sh` | Stop | Pipeline state gate |
| `rtl-verify-stop-gate.sh` | Stop | RTL verification gate |
| `rtl-p6-cascade-gate.sh` | Stop | Phase 6 cascade enforcement |
| `rtl-skill-completion-gate.sh` | Stop | Skill completion enforcement |

## State Files

- `.rtl-agent-team/state/rtl-autopilot-state.json` — Full pipeline progress
- `.rtl-agent-team/state/rtl-verify-done` — RTL verification completion gate
- `.rtl-agent-team/state/rtl-verify-waiver` — Verification waiver
- `.rtl-agent-team/state/skill-active.json` — Skill completion loop state
- `.rtl-agent-team/state/phase6-stale` — Phase 6 cascade marker
- `.rtl-agent-team/state/phase6-cascade-done` — Phase 6 cascade completion
- `.rtl-agent-team/state/rtl-modified-files.txt` — Modified RTL file tracking
