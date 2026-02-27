<!-- RTL-AGENT-TEAM:START -->
# RTL Agent Team - Plugin Instructions

## Skill Invocation Rules

When RTL/HDL/FPGA/ASIC related tasks are detected, use this plugin's specialized skills.

| Pattern Detected | Skill to Invoke |
|-----------|------------|
| **--- Full Pipeline ---** | |
| "RTL design", "verilog", "FPGA", "ASIC", "chip design", "rtl-autopilot" | `/rtl-agent-team:rtl-autopilot` |
| "setup", "initialize", "project start", "init", "docker image", "EDA docker" | `/rtl-agent-team:rtl-setup` |
| **--- Phase 1: Research ---** | |
| "spec analysis", "requirements", "paper research", "research" | `/rtl-agent-team:research-analyze` |
| "codec consultation", "H.264", "H.265", "domain expert" | `/rtl-agent-team:domain-consult` |
| **--- Phase 2: Architecture ---** | |
| "architecture design" (RTL context) | `/rtl-agent-team:arch-design` |
| "architecture review", "design review" | `/rtl-agent-team:arch-review` |
| "reference model", "ref model", "C model" | `/rtl-agent-team:ref-model` |
| "BFM", "bus functional model", "SystemC model" | `/rtl-agent-team:bfm-develop` |
| **--- Phase 3: μArch ---** | |
| "microarchitecture", "μArch", "uarch", "pipeline design" | `/rtl-agent-team:rtl-uarch-design` |
| **--- Coding Conventions (auto-applied by extension/Phase) ---** | |
| `.sv`, `.svh`, `.v`, `.vh` RTL code generation | `/rtl-agent-team:systemverilog` |
| `.sva`, SVA bind files, formal assertion | `/rtl-agent-team:systemverilog-assertion` |
| UVM testbench, agent, sequence generation | `/rtl-agent-team:uvm` |
| `.cpp`, `.h` (SystemC/TLM), Phase 2/3 | `/rtl-agent-team:systemc` |
| **--- Phase 4: RTL ---** | |
| "bug fix", "RTL fix", "bug fix", "RTL bug", "functional error" | `/rtl-agent-team:rtl-bugfix` |
| "RTL coding", "module implementation", "SV writing" | `/rtl-agent-team:rtl-code` |
| "refactoring", "RTL refactoring", "code cleanup" (RTL context) | `/rtl-agent-team:rtl-refactor` |
| "documentation", "RTL docs" | `/rtl-agent-team:rtl-document` |
| "IP instance", "IP integration", "submodule connection" | `/rtl-agent-team:rtl-ip-instantiate` |
| "IP-XACT", "ipxact", "register map generation" | `/rtl-agent-team:rtl-ipxact-gen` |
| "lint", "lint check" (RTL context) | `/rtl-agent-team:rtl-lint-check` |
| "synthesis", "synthesis", "yosys", "SDC" | `/rtl-agent-team:rtl-synth-check` |
| **--- Phase 5: Verify ---** | |
| "simulation", "functional verification", "testbench", "cocotb" | `/rtl-agent-team:rtl-func-verify` |
| "SV unit test", "unit test" (RTL context) | `/rtl-agent-team:rtl-sv-unit-test` |
| "UVM", "UVM verification", "sequence", "agent" (UVM context) | `/rtl-agent-team:rtl-uvm-verify` |
| "performance verification", "throughput", "latency measurement" | `/rtl-agent-team:rtl-perf-verify` |
| "formal", "SVA", "assertion" | `/rtl-agent-team:rtl-sva-check` |
| "CDC", "clock domain" | `/rtl-agent-team:rtl-cdc-verify` |
| "AXI", "APB", "AHB", "protocol" (RTL context) | `/rtl-agent-team:rtl-protocol-verify` |
| "coverage", "coverage" | `/rtl-agent-team:rtl-coverage-analyze` |
| **--- Expert Reviews ---** | |
| "CDC review", "CDC design review", "synchronization strategy review" | Delegate directly to `cdc-reviewer` agent |
| "protocol review", "AXI design review", "interface review" | Delegate directly to `protocol-reviewer` agent |
| "formal review", "SVA review", "assertion quality" | Delegate directly to `formal-reviewer` agent |
| "power analysis", "power analysis", "clock gating review" | Delegate directly to `power-analyzer` agent |
| "synthesis review", "synthesis review", "area/timing review" | Delegate directly to `synthesis-reviewer` agent |
| "UVM review", "testbench review", "TB quality" | Delegate directly to `uvm-reviewer` agent |
| "requirement tracing", "traceability", "feature coverage", "spec verification status" | Delegate directly to `requirement-tracer` agent |
| "cocotb review", "cocotb quality", "Python TB review" | Delegate directly to `cocotb-reviewer` agent |
| "reference model review", "ref model verification", "golden model review" | Delegate directly to `ref-model-reviewer` agent |
| "regression analysis", "flaky test", "seed analysis", "coverage convergence" | Delegate directly to `regression-analyzer` agent |
| "equivalence checking", "equivalence", "RTL vs netlist" | Delegate directly to `equivalence-checker` agent |
| "integration verification", "integration", "module connection check", "top-level" | Delegate directly to `integration-verifier` agent |
| "security review", "security", "side-channel", "fault injection" | Delegate directly to `security-reviewer` agent |
| **--- EDA Experts ---** | |
| "DFT", "scan chain", "BIST", "JTAG", "testability" | Delegate directly to `dft-designer` agent |
| "clock architecture", "clock tree", "PLL", "clock gating review" | Delegate directly to `clock-architect` agent |
| **--- Phase 6: Design Note ---** | |
| "design review", "design review", "Phase 6", "design note", "code review documentation" | `/rtl-agent-team:rtl-design-review-phase` |
| **--- Phase 7: Exploration (optional) ---** | |
| "free exploration", "exploration", "Phase 7", "improvement exploration", "experimental improvement" | `/rtl-agent-team:rtl-design-review-phase` (exploration mode) |
| **--- Other Verification ---** | |
| "regression", "regression", "multi-seed" | `/rtl-agent-team:rtl-regression-run` |
| "conformance", "conformance test", "golden comparison" | `/rtl-agent-team:rtl-conformance-test` |
| "bug reproduction", "bug repro", "waveform debug" | `/rtl-agent-team:rtl-bug-repro` |
| "model consistency", "RTL-model comparison", "model consistency" | `/rtl-agent-team:rtl-model-consistency` |

## IMPORTANT — Phase 1 Proactive Requirement Clarification

> **If the user's request is ambiguous or incomplete in Phase 1, proactively use AskUserQuestion to clarify requirements.**
>
> The purpose of Phase 1 is to secure complete and clear requirements.
> Entering Phase 2 in an ambiguous state may require redesigning the entire architecture.
>
> **When to use AskUserQuestion:**
> - When target resolution/frame rate/codec is not specified
> - When interface protocol (AXI/APB/custom) is not specified
> - When clock frequency or timing constraints are unclear
> - When functional scope is ambiguous (encoder/decoder/both, supported profiles/levels, etc.)
> - When spec-analyst flags `[AMBIGUITY]` or `[CONFLICT]`
> - When interpretations conflict between domain experts
>
> **When NOT to use AskUserQuestion:**
> - When the user has already provided a detailed spec document
> - When a standard has only one valid interpretation
> - When the matter can be decided by design convention (e.g., active-low reset)
>
> **Flow:**
> ```
> Receive user request → Assess requirement completeness → AskUserQuestion if insufficient
> → Incorporate answers → Delegate to spec-analyst/domain expert → Re-ask if [AMBIGUITY] found
> → Finalize requirements → Proceed to Phase 2
> ```

## Absolute Rules

1. Do not start RTL coding without a specification (spec-analyst first)
2. Do not write a Testbench without a Reference Model
3. Do not run synthesis without RTL code
4. Do not run Formal verification without passing Lint
5. **Do not declare completion after RTL modification without functional verification** (lint alone is insufficient)
6. **Do not proceed to Phase 5 without per-module unit tests upon Phase 4 completion** (tb/unit/tb_{module}.sv required) + Stream B early verification artifacts (SVA skeletons, CDC report, TB skeletons)
7. **When Phase 5 FAILs, allow a maximum of 2 Phase 4 feedback loops; escalate to user if exceeded**
8. **Do not proceed to Phase 6 without Phase 5 PASS** (final-compliance.md verdict=PASS required)
9. **Phase 7 is exempt from absolute rules** — free exploration allowed without pipeline Gate

## IMPORTANT — Mandatory Verification After RTL Changes

> **This rule applies to all tasks that modify .sv/.svh/.v/.vh files.**
>
> **Passing lint does NOT equal functional correctness verification. Lint is a necessary condition, not a sufficient one.**
>
> The following 4 steps must be completed when modifying RTL files:
>
> | Step | Description | Required |
> |------|------|----------|
> | 1. Modify | Change RTL code | Required |
> | 2. Lint | Pass `verilator --lint-only -Wall` | Required |
> | 3. TB | Create or update testbench for the modified module | **Required** |
> | 4. Functional Verification | Run cocotb/verilator simulation and PASS | **Required** |
>
> **Hook-based enforcement mechanism:**
> - `PostToolUse:Edit/Write` hook automatically tracks .sv file modifications
> - `Stop` hook blocks session termination without functional verification
> - Upon verification completion, release the gate with `touch .rtl-agent-team/state/rtl-verify-done`
> - When verification is unnecessary (e.g., comment-only changes): `touch .rtl-agent-team/state/rtl-verify-waiver`
>
> **Anti-pattern (prohibited):**
> ```
> RTL modify → lint pass → "done" ← This is NOT done
> ```
>
> **Correct flow:**
> ```
> RTL modify → lint pass → TB create/update → simulation PASS → "done"
> ```
>
> **Phase 4 Parallel Streams (rtl-autopilot mode):**
> ```
> Stream A: RTL coding (wave-based) → lint → unit TB → unit sim
> Stream B: SVA skeletons + CDC topology + TB skeletons (from uarch, parallel with Stream A)
> Merge: Phase 4→5 Gate (Stream A PASS + Stream B artifacts ready)
> ```
>
> | 5. Phase 5 Integration | On Phase 5 FAIL, automatic feedback → rtl-bugfix → fix → re-verify (max 2 times) | Automatic |
>
> This rule is structured as the `/rtl-agent-team:rtl-bugfix` skill.

## IMPORTANT — Hierarchical Spec Compliance

> **This principle is the top-level rule that applies to all Phases, all agents, and all reviews.**
>
> **Lower stages must never violate the spec of upper stages.**
>
> ```
> Requirements(Spec) → Architecture → μArch → RTL → Verification
>     ↑ Each stage must comply with the decisions of the stage to its left
> ```
>
> 1. **Architecture must implement all required functions from the Spec.**
>    - Deleting or reducing required functions for architectural convenience is prohibited
>    - If functional changes are needed, return to the Spec stage and obtain user approval
>
> 2. **μArch must comply with Architecture's block boundaries and interfaces.**
>    - Arbitrarily changing block boundaries for timing/design convenience is prohibited
>    - If block partitioning changes are needed, return to the Architecture stage
>
> 3. **RTL must faithfully implement the μArch design.**
>    - Omitting functions or changing interfaces for implementation convenience is prohibited
>
> 4. **Verification must validate against the original Spec requirements.**
>    - Tests must not be tailored to the RTL — they must be tailored to the Spec
>
> **Design priorities (RTL quality criteria):**
>
> | Priority | Item | Description |
> |---------|------|------|
> | 1 (Highest) | **Functional Correctness** | Do all required functions from the Spec work correctly? |
> | 2 | **Interface Compliance** | Do ports, protocols, and timing interfaces match the Architecture? |
> | 3 | **Timing/Performance** | Are throughput, latency, and clock frequency targets met? |
> | 4 | **Area/Power** | Is resource usage reasonable? |
>
> **Items to verify during Phase Gate reviews:**
> - Whether any functions are missing compared to the upper spec (Feature Coverage Checklist)
> - Whether any interfaces have changed compared to the upper spec
> - If changes exist: valid justification + user approval status

## IMPORTANT — Cascading Quality Principle

> **Higher abstraction levels require MORE iterative refinement.**
>
> Good research → good architecture → good μArch → good RTL.
> A defect at the architecture level costs orders of magnitude more to fix at RTL
> than if caught during architecture review.
>
> **Time is NOT a constraint at upper levels.** Spend extra review rounds perfecting
> architecture and μArch rather than discovering fundamental issues during RTL coding.
>
> | Phase | Abstraction | Mandatory Review Iterations |
> |-------|------------|---------------------------|
> | Phase 1: Research | Highest | 3 rounds (chief-coordinated) |
> | Phase 2: Architecture | High | 3 rounds (memory, performance, ref model) |
> | Phase 3: μArch | Medium | 3 rounds (performance, interface, memory) |
> | Phase 4: RTL | Low | Wave-based lint+sim |
> | Phase 5: Verify | Lowest | Sub-phase parallel |
>
> Iteration count may be increased beyond 3 if convergence is not achieved.
> The principle: **refine thoroughly at the top, execute efficiently at the bottom.**

## IMPORTANT — Document-as-Memory Principle

> **Design artifacts serve as persistent memory across phases and agents.**
>
> Each phase reads upstream documents as input context and writes downstream documents as output.
> No agent needs to "remember" another agent's output — it reads the document.
>
> ```
> requirements.json → arch-designer → architecture.md → uarch-designer → uarch/*.md → rtl-coder
> reviews/phase-N/ → Quality Gate → next phase proceeds or fails
> ```
>
> This enables resumability: any phase can restart by re-reading its input documents.
> Intra-phase communication (iterative reviews) uses scratchpad files at
> `.rtl-agent-team/scratch/phase-{N}/` which are cleaned on phase completion.
>
> **Context Summarization**: Each phase generates a `phase-N-summary.md` on completion.
> Downstream phases use these summaries (via `required_summary_only` in Context Manifest)
> instead of reading full upstream documents, reducing context window consumption.
> Full documents are only loaded when declared as `required_full_read` or on-demand.

## 6-Phase Design Pipeline (+Phase 7 Optional Exploration)

Design artifacts for each Phase are stored in `docs/phase-N-*/` and serve as input (guides) for the next Phase.
Upper spec compliance verification results (verdict) are stored in `reviews/phase-N-*/`.

```
Phase 1: Research    → docs/phase-1-research/      (natural language spec, domain knowledge)
Phase 2: Arch/Ref    → docs/phase-2-architecture/   (block architecture) + ref_model/ (C golden)
                       + 3-round iterative review (memory, performance, ref model consistency)
Phase 3: μArch/TLM   → docs/phase-3-uarch/         (microarchitecture) + BFM
                       + 3-round iterative review (performance, interface, memory optimization)
Phase 4: RTL+Unit    → rtl/src/ + tb/unit/ + docs/phase-4-rtl/ (module design docs, unit design)
                       Stream A: RTL implementation (wave-based parallel coding + lint + unit test)
                       Stream B: Early verification framework (SVA skeletons, CDC topology, TB skeletons)
Phase 5: Verify      → tb/formal/ + docs/phase-5-verify/ (verification reports, lint, synthesis estimates)
                       Leverages Stream B artifacts from Phase 4 for faster verification startup
Phase 6: Design Note → docs/phase-6-design-note/    (design documents, improvement recommendations)
Phase 7: Exploration → docs/phase-7-exploration/    (free exploration, pipeline rules not applied)
```

> **Phase 7 is an optional stage.** Pipeline absolute rules (Phase Gate) do not apply,
> and it is a process for freely exploring improvements to the existing design.

## Delegation Rules

RTL tasks must be delegated to specialized agents. This applies to tasks that handle `.sv`, `.v`, `.vhd` files or use EDA tools.

| Task Type | Delegated Agent | Model |
|----------|-----------------|------|
| **--- Design ---** | | |
| Specification analysis | `rtl-agent-team:spec-analyst` | Opus |
| Architecture design | `rtl-agent-team:arch-designer` | Opus |
| Architecture review | `rtl-agent-team:rtl-architect` | Opus |
| μArch design | `rtl-agent-team:uarch-designer` | Opus |
| RTL coding | `rtl-agent-team:rtl-coder` | Opus |
| RTL review | `rtl-agent-team:rtl-critic` | Opus |
| Design planning | `rtl-agent-team:rtl-planner` | Opus |
| Codebase exploration | `rtl-agent-team:rtl-explorer` | Opus |
| **--- Verification ---** | | |
| Testbench development | `rtl-agent-team:testbench-dev` | Opus |
| Functional verification | `rtl-agent-team:func-verifier` | Opus |
| Performance verification | `rtl-agent-team:perf-verifier` | Opus |
| SVA extraction/writing | `rtl-agent-team:sva-extractor` | Opus |
| Protocol compliance checking | `rtl-agent-team:protocol-checker` | Opus |
| Coverage analysis | `rtl-agent-team:coverage-analyst` | Opus |
| Waveform analysis | `rtl-agent-team:waveform-analyzer` | Opus |
| **--- Expert Reviews ---** | | |
| CDC design review | `rtl-agent-team:cdc-reviewer` | Opus |
| Protocol design review | `rtl-agent-team:protocol-reviewer` | Opus |
| Formal quality review | `rtl-agent-team:formal-reviewer` | Opus |
| Power analysis | `rtl-agent-team:power-analyzer` | Opus |
| Synthesis results review | `rtl-agent-team:synthesis-reviewer` | Opus |
| UVM TB quality review | `rtl-agent-team:uvm-reviewer` | Opus |
| Requirement traceability | `rtl-agent-team:requirement-tracer` | Opus |
| cocotb TB quality review | `rtl-agent-team:cocotb-reviewer` | Opus |
| Reference model review | `rtl-agent-team:ref-model-reviewer` | Opus |
| Regression analysis | `rtl-agent-team:regression-analyzer` | Opus |
| Equivalence checking | `rtl-agent-team:equivalence-checker` | Opus |
| Integration verification | `rtl-agent-team:integration-verifier` | Opus |
| Hardware security review | `rtl-agent-team:security-reviewer` | Opus |
| **--- Phase 6: Design Note ---** | | |
| In-depth code quality review | `rtl-agent-team:code-quality-reviewer` | Opus |
| Design quality review | `rtl-agent-team:design-quality-reviewer` | Opus |
| Design document writing | `rtl-agent-team:design-note-writer` | Opus |
| Improvement analysis | `rtl-agent-team:improvement-analyst` | Opus |
| **--- EDA/Synthesis ---** | | |
| EDA tool execution | `rtl-agent-team:eda-runner` | Opus |
| Synthesis metric extraction | `rtl-agent-team:synthesis-reporter` | Opus |
| Lint checking | `rtl-agent-team:lint-checker` | Opus |
| SDC constraint generation | `rtl-agent-team:constraint-writer` | Opus |
| Timing analysis (STA) | `rtl-agent-team:timing-advisor` | Opus |
| CDC static analysis | `rtl-agent-team:cdc-checker` | Opus |
| Clock architecture review | `rtl-agent-team:clock-architect` | Opus |
| DFT design | `rtl-agent-team:dft-designer` | Opus |
| **--- Infrastructure ---** | | |
| IP-XACT generation | `rtl-agent-team:ipxact-generator` | Opus |
| BFM development | `rtl-agent-team:bfm-dev` | Opus |
| Reference Model development | `rtl-agent-team:ref-model-dev` | Opus |
| **--- Domain Experts ---** | | |
| Codec Chief expert | `rtl-agent-team:vcodec-chief-standard-expert` | Opus |
| Syntax/entropy expert | `rtl-agent-team:vcodec-syntax-entropy-expert` | Opus |
| Prediction expert | `rtl-agent-team:vcodec-prediction-expert` | Opus |
| Transform/quantization expert | `rtl-agent-team:vcodec-transform-quant-expert` | Opus |
| Filter/reconstruction expert | `rtl-agent-team:vcodec-filter-recon-expert` | Opus |
| Codec architecture expert | `rtl-agent-team:vcodec-architecture-expert` | Opus |
| Video processing expert | `rtl-agent-team:video-processing-expert` | Opus |

## Coding Conventions (Mandatory)

> **IMPORTANT — Language Standards (Project Defaults)**
>
> | Language | Standard | Notes |
> |------|------|------|
> | **SystemVerilog (RTL)** | **IEEE 1800-2009** | Baseline for synthesizable RTL code. Features added after 2012 are for verification only |
> | **SystemVerilog (Verification)** | **IEEE 1800-2012** | 2012 features allowed in SVA, UVM TB (checker, interface class, etc.) |
> | **C (Ref Model)** | **C11** (`-std=c11`) | DPI-C 연동 우선. Functional model (no clock/reset). 외부 메모리 접근 함수 추상화 필수 |
> | **C++ (BFM, SystemC)** | **C++17** (`-std=c++17`) | SystemC 3.0 TLM-2.0 BFM 전용. Ref Model에는 사용하지 않음 |
>
> - iverilog flag uses `-g2012` (basic SV syntax support)
> - **iverilog unsupported**: `interface`, unpacked `struct`/`union` — agents must not generate these
> - `typedef struct packed` / `typedef union packed` are supported (usable)
> - Do not modify if the user has added them directly or they exist in existing code
> - verilator/slang fully support 2009 features with default settings
> - No synthesis-related feature additions after 2012 (2017 is errata only, 2023 has early tool support)

> **IMPORTANT — Core Overrides (Always Applied)**
>
> 1. **Port prefix**: `i_`, `o_`, `io_` required (NOT suffix `_i`, `_o`). However, **clock and reset are exceptions** (no prefix needed)
> 2. **Clock**: `clk` (single) or `{domain}_clk` (multiple, e.g., `sys_clk`) — NOT `clk_i`. `i_` prefix not needed
> 3. **Reset**: `rst_n` (single) or `{domain}_rst_n` (multiple, e.g., `sys_rst_n`) — NOT `rst_ni`. Active-low asynchronous reset required. `i_` prefix not needed
> 4. **CamelCase completely prohibited**: Parameter → `ALL_CAPS` (`DATA_WIDTH`). Internal localparam → `L_` prefix (`L_ADDR_BITS`). Enum values → `ALL_CAPS` (`ST_IDLE`). All identifiers must use only `snake_case` or `ALL_CAPS`
> 5. **UVM exception**: `m_` prefix allowed for UVM class internal member handles (industry practice). `u_` is for RTL instances only

**Coding convention skills auto-applied by extension/Phase:**

| File Extension / Context | Design Phase | Applied Skill |
|----------------------|-----------|----------|
| `.sv`, `.svh`, `.v`, `.vh` (RTL) | Phase 4 (RTL) | `/rtl-agent-team:systemverilog` |
| `.sv` (SVA, assertion, bind) | Phase 5 (Formal) | `/rtl-agent-team:systemverilog-assertion` |
| `.sv` (UVM testbench) | Phase 5 (UVM) | `/rtl-agent-team:uvm` |
| `.cpp`, `.h` (SystemC/TLM) | Phase 2 (Ref Model), Phase 3 (BFM) | `/rtl-agent-team:systemc` |

- `systemverilog`: lowRISC + overrides, Power optimization, FPGA, Pipelining
- `systemverilog-assertion`: SVA patterns, bind files, SymbiYosys integration, assume/assert/cover
- `uvm`: UVM class hierarchy, factory, TLM ports, coverage, phase callback
- `systemc`: TLM-2.0 AT non-blocking, AMBA-PV (AXI/AHB/APB), Memory Manager, PEQ, cocotb integration

## EDA Tool Usage

The `eda-runner` agent directly executes EDA CLI tools via Bash:
- Simulation: `verilator`, `iverilog` (Icarus Verilog)
- Synthesis: `yosys`
- Formal verification: `sby` (SymbiYosys)
- Lint: `verilator --lint-only`, `verible-verilog-lint`, `slang`
- cocotb tests: `make SIM=icarus TOPLEVEL=<mod> MODULE=<test>`
- SystemC: `g++ -lsystemc` (local build)
- Waveform viewer: `gtkwave` (VCD/FST waveform analysis)

When tools are not installed, `eda-runner` provides installation guidance.
Environment checking and project initialization are available via the `/rtl-agent-team:rtl-setup` skill.

## Artifact Structure

Design artifacts are separated into two categories:
- **`docs/`** = Per-Phase design documents. Phase N's artifacts serve as guides/inputs for Phase N+1 in the pipeline
- **`reviews/`** = verdict documents that only verify compliance with upper specs/requirements

### docs/ — Design Artifacts (Phase Guide Pipeline)

```
docs/
├── phase-1-research/                    # → Input for Phase 2
│   ├── requirements.json                # Requirements list
│   ├── io_definition.json               # I/O port spec
│   ├── domain-analysis.md               # Domain analysis (algorithms, standards)
│   └── phase-1-summary.md              # Phase 1 compressed summary (auto-generated)
├── phase-2-architecture/                # → Input for Phase 3
│   ├── architecture.md                  # Block architecture (module hierarchy, datapath, timing)
│   └── phase-2-summary.md              # Phase 2 compressed summary (auto-generated)
├── phase-3-uarch/                       # → Input for Phase 4
│   ├── {module_name}.md                 # Per-module microarchitecture
│   └── phase-3-summary.md              # Phase 3 compressed summary (auto-generated)
├── phase-4-rtl/                         # → Input for Phase 5
│   ├── module-descriptions.md           # Per-module design summary (ports, functions, dependencies)
│   ├── unit-test-design.md              # Unit test design (test strategy, coverage targets)
│   ├── stream-b-sva-skeletons.md        # SVA property skeletons from uarch (Stream B, Phase 4)
│   ├── stream-b-cdc-preliminary.md      # Preliminary CDC topology report (Stream B, Phase 4)
│   ├── stream-b-tb-skeletons.md         # cocotb TB skeletons from uarch (Stream B, Phase 4)
│   └── phase-4-summary.md              # Phase 4 compressed summary (auto-generated)
├── phase-5-verify/                      # → Input for Phase 6
│   ├── unit-test-report.md              # Unit test results summary
│   ├── integration-report.md            # Integration test results
│   ├── ref-rtl-model-consistency.md         # RTL vs C golden model consistency comparison
│   ├── lint-report.md                   # Verilator lint results summary
│   ├── synthesis-estimate.md            # Yosys synthesis estimates (area, timing)
│   └── phase-5-summary.md              # Phase 5 compressed summary (auto-generated)
├── phase-6-design-note/                 # Final design documents
│   ├── design-note.md                   # Detailed design document (algorithms, HW implementation, trade-offs)
│   └── improvements.md                  # Improvement recommendations (must-fix, should-fix, nice-to-have)
├── decisions/                           # Architecture Decision Records (ADR)
│   └── ADR-{NNN}.md                    # Per-decision record (context, options, decision, consequences)
├── lessons-learned.md                   # Cross-phase lessons learned (appended per bug fix)
└── phase-7-exploration/                 # Free exploration (pipeline rules not applied)
    └── exploration-notes.md             # Improvement exploration, experimental ideas
```

### reviews/ — Verification verdict (Upper Spec Compliance Check)

```
reviews/
├── phase-1-research/
│   └── research-review.md               # Spec completeness + feasibility verdict
├── phase-2-architecture/
│   ├── architecture-review-r1.md        # Round 1 review (3-round iterative)
│   ├── architecture-review-r2.md        # Round 2 review
│   ├── architecture-review-r3.md        # Round 3 review (mandatory final pass)
│   ├── architecture-review.md           # Consolidated verdict on whether Arch complies with Spec
│   ├── feature-coverage.md              # Feature Coverage Checklist (100% REQ mapping)
│   └── architecture-diagram.md          # Mermaid block diagram
├── phase-3-uarch/
│   ├── uarch-review-r1.md              # Round 1 review (3-round iterative)
│   ├── uarch-review-r2.md              # Round 2 review
│   ├── uarch-review-r3.md              # Round 3 review (mandatory final pass)
│   ├── uarch-review.md                  # Consolidated verdict on whether μArch complies with Arch
│   ├── feature-preservation.md          # Feature Preservation Checklist (100% preserved)
│   └── pipeline-diagram.md             # Mermaid pipeline diagram
├── phase-4-rtl/
│   ├── functional-completeness.md       # Requirement → uarch → RTL traceability
│   ├── design-review.md                 # Verdict on whether RTL complies with μArch
│   └── lint-report.md                   # Verilator lint results
├── phase-5-verify/
│   ├── formal-review.md                 # SVA formal verification results
│   ├── cdc-report.md                    # Clock domain crossing analysis
│   ├── requirement-traceability.md      # Requirement → test → result mapping
│   ├── coverage-report.md               # Line/toggle/FSM coverage analysis
│   ├── final-compliance.md              # Final compliance verdict against original Spec
│   └── e2e-traceability.md             # Unified end-to-end: REQ→Arch→μArch→RTL→Test→Result
├── phase-6-review/
│   ├── code-review.md                   # Code quality verdict
│   ├── design-review.md                 # Design quality verdict
│   ├── design-note.md                   # Comprehensive design document
│   └── improvements.md                  # Prioritized improvement recommendations
└── phase-7-exploration/
    └── exploration-review.md            # Exploration results review verdict
```

### Code Artifacts

```
rtl/src/                                 # RTL source code (Phase 4)
tb/                                      # Testbenches (Phase 4-5)
├── unit/                                # Unit tests
└── formal/                              # SVA formal verification
ref_model/                               # C golden reference (Phase 2)
```

> **Principle**: Store data/metrics/design content in `docs/`, and only verdict (PASS/FAIL) in `reviews/`.
> Example: formal verification data goes in `docs/phase-5-verify/`, while spec compliance judgment goes in `reviews/phase-5-verify/final-compliance.md`.

### Review Markdown Format

All verdict reports (`reviews/`) follow this structure:
```markdown
# [Phase] Review: [Title]
- Date: YYYY-MM-DD
- Reviewer: [Agent Name]
- Upper Spec: [Referenced Upper Document]
- Verdict: PASS | FAIL

## Feature Coverage Checklist
| REQ ID | Requirement | Status | Implementation Location |
|--------|---------|------|----------|
| REQ-001 | ... | COVERED | module.sv:42 |
| REQ-002 | ... | MISSING | — |

## Findings
### [severity] Finding-1: ...

## Verdict
PASS | FAIL: [Reason]
```

## State Files

Design flow state is stored under `.rtl-agent-team/`:
- `.rtl-agent-team/state/rtl-autopilot-state.json` — Pipeline progress state (for resumption, schema v2.0)
- `.rtl-agent-team/rtl/{module}/phase-{n}-complete.json` — Phase completion gate
- `.rtl-agent-team/scratch/phase-{N}/` — Temporary working files for iterative review rounds (cleaned on phase completion)
- `.rtl-agent-team/context/` — Context manifests and phase summaries (auto-managed)

<!-- RTL-AGENT-TEAM:END -->
