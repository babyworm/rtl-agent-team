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
| "spec analysis", "requirements", "paper research", "research" | `/rtl-agent-team:p1-spec-research` |
| "codec consultation", "H.264", "H.265", "domain expert" | `/rtl-agent-team:domain-consult` |
| **--- Phase 2: Architecture ---** | |
| "architecture design" (RTL context) | `/rtl-agent-team:p2-arch-design` |
| "architecture review", "arch review" | `/rtl-agent-team:arch-review` |
| "reference model", "ref model", "C model" | `/rtl-agent-team:ref-model` |
| "BFM", "bus functional model", "SystemC model" | `/rtl-agent-team:bfm-develop` |
| **--- Phase 3: μArch ---** | |
| "microarchitecture", "μArch", "uarch", "pipeline design" | `/rtl-agent-team:rtl-p3-uarch-design` |
| **--- Pipeline Composition ---** | |
| "DSE", "design space exploration", "algorithm study", "architecture comparison" | `/rtl-agent-team:rtl-dse` |
| "spec to uarch", "design only", "Phase 1-3", "design documents only" | `/rtl-agent-team:rtl-spec-to-uarch` |
| "uarch to verify", "implement and verify", "Phase 4-5", "RTL from uarch" | `/rtl-agent-team:rtl-uarch-to-verify` |
| "RD eval", "BD-PSNR", "BD-rate", "codec quality", "algorithm quality evaluation" | `/rtl-agent-team:codec-rd-eval` |
| "decoder conformance", "conformance stream", "conformance test", "decoder verify", "bitexact decoder" | `/rtl-agent-team:codec-conformance-eval` |
| **--- Coding Conventions (auto-applied by extension/Phase) ---** | |
| `.sv`, `.svh`, `.v`, `.vh` RTL code generation | `/rtl-agent-team:systemverilog` |
| `.sv`, `.sva` (SVA, assertion, bind), formal assertion | `/rtl-agent-team:systemverilog-assertion` |
| UVM testbench, agent, sequence generation | `/rtl-agent-team:uvm` |
| `.cpp`, `.h` (SystemC/TLM), Phase 2/3 | `/rtl-agent-team:systemc` |
| **--- Phase 4: RTL ---** | |
| "bug fix", "RTL fix", "RTL bug", "functional error" | `/rtl-agent-team:rtl-p4s-bugfix` |
| "RTL coding", "module implementation", "SV writing" | `/rtl-agent-team:rtl-p4-implement` |
| "refactoring", "RTL refactoring", "code cleanup" (RTL context) | `/rtl-agent-team:rtl-p4s-refactor` |
| "SV unit test", "unit test" (RTL context) | `/rtl-agent-team:rtl-p4s-unit-test` |
| "IP instance", "IP integration", "submodule connection" | `/rtl-agent-team:rtl-ip-instantiate` |
| "lint", "lint check" (RTL context) | `/rtl-agent-team:rtl-lint-check` |
| "synthesis", "yosys", "SDC" | `/rtl-agent-team:rtl-synth-check` |
| "documentation", "RTL docs" | `/rtl-agent-team:rtl-document` |
| "IP-XACT", "ipxact", "register map generation" | `/rtl-agent-team:rtl-ipxact-gen` |
| **--- Phase 5: Verify ---** | |
| "Phase 5", "verification pipeline", "extensive verification" | `/rtl-agent-team:rtl-p5-verify` |
| "simulation", "functional verification", "testbench", "cocotb" | `/rtl-agent-team:rtl-p5s-func-verify` |
| "UVM", "UVM verification", "sequence", "agent" (UVM context) | `/rtl-agent-team:rtl-p5s-uvm-verify` |
| "performance verification", "throughput", "latency measurement" | `/rtl-agent-team:rtl-p5s-perf-verify` |
| "formal", "SVA", "assertion" | `/rtl-agent-team:rtl-p5s-sva-check` |
| "CDC", "clock domain" | `/rtl-agent-team:rtl-p5s-cdc-verify` |
| "AXI", "APB", "AHB", "protocol" (RTL context) | `/rtl-agent-team:rtl-p5s-protocol-verify` |
| "coverage" | `/rtl-agent-team:rtl-p5s-coverage-analyze` |
| **--- Expert Reviews ---** | |
| "CDC review", "CDC design review", "synchronization strategy review" | Delegate directly to `cdc-reviewer` agent |
| "protocol review", "AXI design review", "interface review" | Delegate directly to `protocol-reviewer` agent |
| "formal review", "SVA review", "assertion quality" | Delegate directly to `formal-reviewer` agent |
| "power analysis", "power review", "power estimation" | Delegate directly to `power-analyzer` agent |
| "synthesis review", "area/timing review" | Delegate directly to `synthesis-reviewer` agent |
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
| "design review", "Phase 6", "design note", "code review documentation" | `/rtl-agent-team:rtl-p6-design-review` |
| **--- Phase 7: Exploration (optional) ---** | |
| "free exploration", "exploration", "Phase 7", "improvement exploration", "experimental improvement" | `/rtl-agent-team:rtl-p6-design-review` (exploration mode) |
| **--- Other Verification ---** | |
| "integration test", "cross-module test", "end-to-end test", "Tier 4" | `/rtl-agent-team:rtl-p5s-integration-test` |
| "regression", "multi-seed" | `/rtl-agent-team:rtl-p5s-func-verify` (Tier 3, absorbs rtl-regression-run) |
| "RTL conformance", "RTL conformance test", "RTL golden comparison" | `/rtl-agent-team:rtl-conformance-test` |
| "bug reproduction", "bug repro", "waveform debug" | `/rtl-agent-team:rtl-bug-repro` |
| "model consistency", "RTL-model comparison" | `/rtl-agent-team:rtl-model-consistency` |

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

## 6-Phase Design Pipeline

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

**Hierarchical Spec Compliance**: Lower stages must never violate upper stage specs. Spec → Arch → μArch → RTL → Verify. Details in `docs/CLAUDE.md`.

**Cascading Quality**: Higher abstraction = more review iterations. Phase 1-3: min 3 rounds each. Fix at the top, not the bottom. Details in `docs/CLAUDE.md`.

**Document-as-Memory**: Design artifacts are persistent memory. Each phase reads upstream docs, writes downstream. Enables resumability. Details in `docs/CLAUDE.md`.

## Coding Conventions (Core Overrides)

1. **Port prefix**: `i_`, `o_`, `io_` (NOT suffix). Clock/reset exempt
2. **Clock**: `{domain}_clk` (e.g., `sys_clk`). **Reset**: `{domain}_rst_n`. Active-low async
3. **No CamelCase**: `snake_case` or `ALL_CAPS` only. Parameters `ALL_CAPS`, localparam `L_` prefix
4. SV RTL: IEEE 1800-2009. SV Verification: IEEE 1800-2012. C ref model: C11
5. Convention skills auto-applied by file extension (see Skill Invocation Rules)

Full rules: `.claude/rules/rtl-coding-conventions.md`. Verification gate: `.claude/rules/rtl-verification-gate.md`.

## Hook-Based Enforcement

**Skill Completion Loop**: Skills with completion criteria are enforced by Stop hook. Set `all_complete: true` in `.rtl-agent-team/state/skill-active.json` when done.

**Phase 6 Cascade**: RTL changes after Phase 6 trigger mandatory lint + code review + design note update. Signal with `touch .rtl-agent-team/state/phase6-cascade-done`.

**State files**: Stored under `.rtl-agent-team/state/`. Pipeline state, verification gates, skill completion tracking.

<!-- RTL-AGENT-TEAM:END -->
