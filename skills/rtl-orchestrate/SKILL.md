---
name: rtl-orchestrate
description: "Internal RTL routing reference. Defines the single source of truth for Action Skill routing, Action Skill→Orchestrator→Policy mapping, and SessionStart hook export content."
user-invocable: false
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

When RTL/HDL/FPGA/ASIC related tasks are detected, route to **Action Skills first**.
Orchestrator agents are internal execution units spawned only by Action Skills.

**Invocation types:**
- **Action Skill**: user-facing entry point via `Skill(skill="rtl-agent-team:XXX")`
- **Convention**: auto-applied by file extension/phase, not user-invocable
- **Internal Reference**: non-user-facing skill used for routing/context export only

| Pattern Detected | Route To | Type |
|-----------|------------|------|
| **--- Full Pipeline ---** | | |
| "RTL design", "verilog", "FPGA", "ASIC", "chip design", "rat-auto-design" | `/rtl-agent-team:rat-auto-design` | Action Skill |
| "setup tools", "install tools", "EDA setup", "check tools", "docker image", "EDA docker" | `/rtl-agent-team:rat-setup` | Action Skill |
| "init project", "initialize project", "new project", "project init" | `/rtl-agent-team:rat-init-project` | Action Skill |
| "debug", "diagnostics", "plugin status", "rat debug", "tool check" | `/rtl-agent-team:rat-plugin-debug` | Action Skill |
| "tutorial", "getting started", "how to use", "help me learn" | `/rtl-agent-team:rat-tutorial` | Action Skill |
| **--- Phase 1: Research ---** | | |
| "spec analysis", "requirements", "paper research", "research" | `/rtl-agent-team:p1-spec-research` | Action Skill |
| "codec consultation", "H.264", "H.265", "domain expert" | `/rtl-agent-team:domain-consult` | Action Skill |
| "intra prediction", "angular mode", "planar mode", "DC mode" | `/rtl-agent-team:domain-consult` → `vcodec-intra-pred-expert` | Action Skill |
| "motion estimation", "IME", "FME", "TZ search", "MV prediction", "AMVP" | `/rtl-agent-team:domain-consult` → `vcodec-me-expert` | Action Skill |
| "motion compensation", "sub-pel interpolation", "bi-prediction", "weighted prediction" | `/rtl-agent-team:domain-consult` → `vcodec-mc-expert` | Action Skill |
| **--- Phase 2: Architecture ---** | | |
| "architecture design" (RTL context) | `/rtl-agent-team:p2-arch-design` | Action Skill |
| "architecture review", "arch review" | `/rtl-agent-team:arch-review` | Action Skill |
| "reference model", "ref model", "C model" | `/rtl-agent-team:ref-model` | Action Skill |
| "BFM", "bus functional model", "SystemC model" | `/rtl-agent-team:bfm-develop` | Action Skill |
| **--- Phase 3: μArch ---** | | |
| "microarchitecture", "μArch", "uarch", "pipeline design" | `/rtl-agent-team:rtl-p3-uarch-design` | Action Skill |
| **--- Pipeline Composition ---** | | |
| "DSE", "design space exploration", "algorithm study", "architecture comparison", "iterative exploration" | `/rtl-agent-team:rat-dse` | Action Skill |
| "Phase 1 team", "research team", "parallel research" | `/rtl-agent-team:rtl-p1-research-team` | Action Skill |
| "Phase 2 team", "arch team", "parallel architecture" | `/rtl-agent-team:rtl-p2-arch-team` | Action Skill |
| "Phase 3 team", "uarch team", "parallel uarch" | `/rtl-agent-team:rtl-p3-uarch-team` | Action Skill |
| "spec to uarch team", "Phase 1-3 team", "parallel design pipeline" | `/rtl-agent-team:rat-p1p3-spec-uarch-team` | Action Skill |
| "spec to uarch", "design only", "Phase 1-3", "design documents only" | `/rtl-agent-team:rat-p1p3-spec-uarch` | Action Skill |
| "uarch to verify", "implement and verify", "Phase 4-5", "RTL from uarch" | `/rtl-agent-team:rat-p4p5-impl-verify` | Action Skill |
| "RD eval", "BD-PSNR", "BD-rate", "codec quality", "algorithm quality evaluation" | `/rtl-agent-team:codec-rd-eval` | Action Skill |
| "decoder conformance", "conformance stream", "conformance test", "decoder verify" | `/rtl-agent-team:codec-conformance-eval` | Action Skill |
| **--- Coding Conventions (auto-applied by extension/Phase) ---** | | |
| `.sv`, `.svh`, `.v`, `.vh` RTL code generation | `systemverilog` (auto-applied) | Convention |
| `.sv`, `.sva` (SVA, assertion, bind), formal assertion | `systemverilog-assertion` (auto-applied) | Convention |
| UVM testbench, agent, sequence generation | `uvm` (auto-applied) | Convention |
| `.cpp`, `.h` (SystemC/TLM), Phase 2/3 | `systemc` (auto-applied) | Convention |
| **--- Phase 4: RTL ---** | | |
| "rapid rtl", "P4 rapid", "sanity integration", "fast implementation loop" | `/rtl-agent-team:rtl-p4-rapid-impl` | Action Skill |
| "bug fix", "RTL fix", "RTL bug", "functional error" | `/rtl-agent-team:rtl-p4s-bugfix` | Action Skill |
| "RTL coding", "module implementation", "SV writing" | `/rtl-agent-team:rtl-p4-implement` | Action Skill |
| "Phase 4 team", "implement team", "parallel implement" | `/rtl-agent-team:rtl-p4-implement-team` | Action Skill |
| "block parallel", "worktree parallel", "6-block", "block-parallel Phase 4" | `/rtl-agent-team:rtl-p4-block-parallel` | Action Skill |
| "refactoring", "RTL refactoring", "code cleanup" (RTL context) | `/rtl-agent-team:rtl-p4s-refactor` | Action Skill |
| "SV unit test", "unit test" (RTL context) | `/rtl-agent-team:rtl-p4s-unit-test` | Action Skill |
| "IP instance", "IP integration", "submodule connection" | `/rtl-agent-team:rtl-ip-instantiate` | Action Skill |
| "lint", "lint check" (RTL context) | `/rtl-agent-team:rtl-lint-check` | Action Skill |
| "synthesis", "yosys", "SDC" | `/rtl-agent-team:rtl-synth-check` | Action Skill |
| "documentation", "RTL docs" | `/rtl-agent-team:rtl-document` | Action Skill |
| "IP-XACT", "ipxact", "register map generation" | `/rtl-agent-team:rtl-ipxact-gen` | Action Skill |
| **--- Phase 5: Verify ---** | | |
| "functional closure", "P5A", "deep functional verification", "hierarchical functional closure" | `/rtl-agent-team:rtl-p5a-functional-closure` | Action Skill |
| "silicon validation", "P5B", "signoff readiness", "timing signoff", "post-functional signoff" | `/rtl-agent-team:rtl-p5b-silicon-validation` | Action Skill |
| "Phase 5", "verification pipeline", "extensive verification" | `/rtl-agent-team:rtl-p5-verify` | Action Skill |
| "Phase 5 team", "verify team", "parallel verify" | `/rtl-agent-team:rtl-p5-verify-team` | Action Skill |
| "simulation", "functional verification", "testbench", "cocotb" | `/rtl-agent-team:rtl-p5s-func-verify` | Action Skill |
| "UVM", "UVM verification", "sequence", "agent" (UVM context) | `/rtl-agent-team:rtl-p5s-uvm-verify` | Action Skill |
| "performance verification", "throughput", "latency measurement" | `/rtl-agent-team:rtl-p5s-perf-verify` | Action Skill |
| "formal", "SVA", "assertion" | `/rtl-agent-team:rtl-p5s-sva-check` | Action Skill |
| "CDC", "clock domain" | `/rtl-agent-team:rtl-p5s-cdc-verify` | Action Skill |
| "AXI", "APB", "AHB", "protocol" (RTL context) | `/rtl-agent-team:rtl-p5s-protocol-verify` | Action Skill |
| "coverage" | `/rtl-agent-team:rtl-p5s-coverage-analyze` | Action Skill |
| **--- Phase 6: Design Note ---** | | |
| "design review", "Phase 6", "design note", "code review documentation" | `/rtl-agent-team:rtl-p6-design-review` | Action Skill |
| **--- Phase 7: Exploration (optional) ---** | | |
| "free exploration", "exploration", "Phase 7", "improvement exploration" | `/rtl-agent-team:rtl-p7-exploration` | Action Skill |
| **--- Autonomous Loops ---** | | |
| "ultraloop", "autonomous loop", "unattended", "퇴근 모드" | `/rtl-agent-team:rat-ultraloop` | Action Skill |
| **--- Other Verification ---** | | |
| "LLM code review", "safe refactor", "review and refactor workflow" | `/rtl-agent-team:rtl-review-refactor` | Action Skill |
| "integration test", "cross-module test", "end-to-end test", "Tier 4" | `/rtl-agent-team:rtl-p5s-integration-test` | Action Skill |
| "regression", "multi-seed" | `/rtl-agent-team:rtl-p5s-func-verify` (Tier 3) | Action Skill |
| "RTL conformance", "RTL conformance test", "RTL golden comparison" | `/rtl-agent-team:rtl-conformance-test` | Action Skill |
| "bug reproduction", "bug repro", "waveform debug" | `/rtl-agent-team:rtl-bug-repro` | Action Skill |
| "model consistency", "RTL-model comparison" | `/rtl-agent-team:rtl-model-consistency` | Action Skill |
| "cross-phase", "contract validation", "spec consistency", "phase boundary check" | `/rtl-agent-team:cross-phase-contract-validator` | Action Skill |
| "cross-review", "codex review", "2nd reviewer", "second opinion", "cross check" | `/rtl-agent-team:codex-cross-review` | Action Skill |
| "routing help", "which skill to use", "routing reference" | `rtl-orchestrate` (internal context only) | Internal Reference |

### Action Skill → Orchestrator Agent Mapping (internal)

Action Skills are user-facing. Each action delegates to one orchestrator agent, which loads one policy skill.

| Action Skill | Orchestrator Agent | Policy Skill |
|--------------|--------------------|-------------|
| `rat-auto-design` | `autopilot-orchestrator` | `rat-auto-design-policy` |
| `p1-spec-research` | `p1-research-orchestrator` | `p1-spec-research-policy` |
| `p2-arch-design` | `p2-arch-orchestrator` | `p2-arch-design-policy` |
| `rtl-p3-uarch-design` | `p3-uarch-orchestrator` | `rtl-p3-uarch-policy` |
| `rtl-p4-implement` | `p4-implement-orchestrator` | `rtl-p4-implement-policy` |
| `rtl-p4-implement-team` | `p4-implement-team-orchestrator` | `rtl-p4-implement-policy` |
| `rtl-p4-rapid-impl` | `p4-rtl-sanity-orchestrator` | `rtl-p4-rapid-impl-policy` |
| `rtl-p4s-bugfix` | `p4s-bugfix-orchestrator` | `rtl-p4s-bugfix-policy` |
| `rtl-p4s-refactor` | `p4s-refactor-orchestrator` | `rtl-p4s-refactor-policy` |
| `rtl-p4s-unit-test` | `p4s-unit-test-orchestrator` | `rtl-p4s-unit-test-policy` |
| `rtl-p5-verify` | `p5-verify-orchestrator` | `rtl-p5-verify-policy` |
| `rtl-p5-verify-team` | `p5-verify-team-orchestrator` | `rtl-p5-verify-policy` |
| `rtl-p5a-functional-closure` | `p5a-functional-closure-orchestrator` | `rtl-p5a-functional-closure-policy` |
| `rtl-p5b-silicon-validation` | `p5b-silicon-validation-orchestrator` | `rtl-silicon-validation-policy` |
| `rtl-p5s-func-verify` | `p5s-func-verify-orchestrator` | `rtl-p5s-func-verify-policy` |
| `rtl-p5s-sva-check` | `p5s-sva-orchestrator` | `rtl-p5s-sva-policy` |
| `rtl-p5s-cdc-verify` | `p5s-cdc-orchestrator` | `rtl-p5s-cdc-policy` |
| `rtl-p5s-protocol-verify` | `p5s-protocol-orchestrator` | `rtl-p5s-protocol-policy` |
| `rtl-p5s-perf-verify` | `p5s-perf-orchestrator` | `rtl-p5s-perf-policy` |
| `rtl-p5s-coverage-analyze` | `p5s-coverage-orchestrator` | `rtl-p5s-coverage-policy` |
| `rtl-p5s-uvm-verify` | `p5s-uvm-orchestrator` | `rtl-p5s-uvm-policy` |
| `rtl-p5s-integration-test` | `p5s-integration-orchestrator` | `rtl-p5s-integration-test-policy` |
| `rtl-p6-design-review` | `p6-review-orchestrator` | `rtl-p6-design-review-policy` |
| `rtl-p7-exploration` | `p7-exploration-orchestrator` | `rtl-p7-exploration-policy` |
| `rtl-review-refactor` | `review-refactor-orchestrator` | `code-review-policy`, `refactor-classification-policy`, `verification-recheck-policy` |
| `codex-cross-review` | `codex-cross-reviewer` | — (self-contained) |
| `rat-dse` | `dse-orchestrator` | `rat-dse-policy` |
| `rtl-p1-research-team` | `p1-research-team-orchestrator` | `p1-spec-research-policy` |
| `rtl-p2-arch-team` | `p2-arch-team-orchestrator` | `p2-arch-design-policy` |
| `rtl-p3-uarch-team` | `p3-uarch-team-orchestrator` | `rtl-p3-uarch-policy` |
| `rat-p1p3-spec-uarch` | `spec-to-uarch-orchestrator` | `rat-p1p3-spec-uarch-policy` |
| `rat-p1p3-spec-uarch-team` | `spec-to-uarch-team-orchestrator` | `rat-p1p3-spec-uarch-policy` |
| `rat-p4p5-impl-verify` | `uarch-to-verify-orchestrator` | `rat-p4p5-impl-verify-policy` |
| `rtl-p4-block-parallel` | `p4-block-parallel-coordinator` | `rtl-block-interface-policy`, `rtl-block-contract-test-policy` |
| `rat-ultraloop` | — (skill-driven, dispatches `ultraloop-reviewer` for review cycles) | — |

**Cross-cutting policy skills** (referenced by specialist agents, not tied to a single orchestrator):

| Policy Skill | Referenced By | Purpose |
|-------------|---------------|---------|
| `test-design-policy` | `testbench-dev`, `test-plan-writer` | Systematic test case design methodology (ECP, BVA, state transition, decision table) |

**Specialist agents (spawned by orchestrators, not user-invocable):**

| Agent | Purpose | Spawned By |
|-------|---------|-----------|
| `test-plan-writer` | Test plan generation from uarch spec (ECP/BVA/STT/DT) | Spawned by P4 orchestrators in Wave 0 Step 0b |

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
| DFT/scan chain/BIST/JTAG | `dft-designer` | Opus |
| Clock architecture/PLL review | `clock-architect` | Opus |

### Phase 6 Agents
| Task Type | Agent | Model |
|----------|-------|-------|
| Code quality review | `code-quality-reviewer` | Opus |
| Design quality review | `design-quality-reviewer` | Opus |
| Design document writing | `design-note-writer` | Opus |
| Improvement analysis | `improvement-analyst` | Opus |

### Orchestrator Agents (pipeline coordinators)
| Pipeline | Agent | Policy Skill |
|----------|-------|-------------|
| Full pipeline (P1→P6) | `autopilot-orchestrator` | `rat-auto-design-policy` |
| Phase 1: Research | `p1-research-orchestrator` | `p1-spec-research-policy` |
| Phase 2: Architecture | `p2-arch-orchestrator` | `p2-arch-design-policy` |
| Phase 3: μArch | `p3-uarch-orchestrator` | `rtl-p3-uarch-policy` |
| Phase 4: RTL Implementation | `p4-implement-orchestrator` | `rtl-p4-implement-policy` |
| Phase 1: Research (Team) | `p1-research-team-orchestrator` | `p1-spec-research-policy` |
| Phase 2: Architecture (Team) | `p2-arch-team-orchestrator` | `p2-arch-design-policy` |
| Phase 3: μArch (Team) | `p3-uarch-team-orchestrator` | `rtl-p3-uarch-policy` |
| Phase 4: RTL Implementation (Team) | `p4-implement-team-orchestrator` | `rtl-p4-implement-policy` |
| Phase 4: Rapid RTL + Sanity | `p4-rtl-sanity-orchestrator` | `rtl-p4-rapid-impl-policy` |
| Phase 4: Bug Fix | `p4s-bugfix-orchestrator` | `rtl-p4s-bugfix-policy` |
| Phase 4: Unit Test | `p4s-unit-test-orchestrator` | `rtl-p4s-unit-test-policy` |
| Phase 5: Verification | `p5-verify-orchestrator` | `rtl-p5-verify-policy` |
| Phase 5: Verification (Team) | `p5-verify-team-orchestrator` | `rtl-p5-verify-policy` |
| Phase 5A: Functional Closure | `p5a-functional-closure-orchestrator` | `rtl-p5a-functional-closure-policy` |
| Phase 5B: Silicon Validation | `p5b-silicon-validation-orchestrator` | `rtl-silicon-validation-policy` |
| Phase 5: Func Verify | `p5s-func-verify-orchestrator` | `rtl-p5s-func-verify-policy` |
| Phase 5: Integration | `p5s-integration-orchestrator` | `rtl-p5s-integration-test-policy` |
| Phase 5: SVA/Formal | `p5s-sva-orchestrator` | `rtl-p5s-sva-policy` |
| Phase 5: CDC | `p5s-cdc-orchestrator` | `rtl-p5s-cdc-policy` |
| Phase 5: Protocol | `p5s-protocol-orchestrator` | `rtl-p5s-protocol-policy` |
| Phase 5: Performance | `p5s-perf-orchestrator` | `rtl-p5s-perf-policy` |
| Phase 5: Coverage | `p5s-coverage-orchestrator` | `rtl-p5s-coverage-policy` |
| Phase 5: UVM | `p5s-uvm-orchestrator` | `rtl-p5s-uvm-policy` |
| Phase 6: Design Review | `p6-review-orchestrator` | `rtl-p6-design-review-policy` |
| LLM Review + Refactor | `review-refactor-orchestrator` | `code-review-policy` + `refactor-classification-policy` + `verification-recheck-policy` |
| DSE | `dse-orchestrator` | `rat-dse-policy` |
| Spec→μArch (P1-3) | `spec-to-uarch-orchestrator` | `rat-p1p3-spec-uarch-policy` |
| Spec→μArch (P1-3 Team) | `spec-to-uarch-team-orchestrator` | `rat-p1p3-spec-uarch-policy` |
| μArch→Verify (P4-5) | `uarch-to-verify-orchestrator` | `rat-p4p5-impl-verify-policy` |
| Phase 4: Block-Parallel | `p4-block-parallel-coordinator` | `rtl-block-interface-policy`, `rtl-block-contract-test-policy` |
| Phase 4: Block Worker | `p4-block-worker` | `rtl-p4-implement-policy` |
| Autonomous Review Loop | `ultraloop-reviewer` | — (READ-ONLY reviewer) |

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
| Intra prediction expert | `vcodec-intra-pred-expert` | Opus |
| Motion estimation expert | `vcodec-me-expert` | Opus |
| Motion compensation expert | `vcodec-mc-expert` | Opus |
| Transform/quantization expert | `vcodec-transform-quant-expert` | Opus |
| Filter/reconstruction expert | `vcodec-filter-recon-expert` | Opus |
| Codec architecture expert | `vcodec-architecture-expert` | Opus |
| Codec performance expert | `video-processing-expert` | Opus |
| Color format expert | `vproc-color-format-expert` | Opus |
| Denoise expert | `vproc-denoise-expert` | Opus |
| Image processing expert | `vproc-image-processing-expert` | Opus |

---

## Pipeline Rules (policy + enforcement map)

These rules define the canonical pipeline order. Rule 5 is hook-enforced
(hard gate); rules 1-4 and 6-8 are policy declarations carried through
skill-entry warnings (asymmetric phase gate design — exit strict, entry
flexible). See `CLAUDE.md` "Pipeline Rules" section for the enforcement
column.

1. **No RTL without Spec** (policy): Do not start RTL coding without a specification (spec-analyst first)
2. **No TB without Ref Model** (policy): Do not write a Testbench without a Reference Model
3. **No Synthesis without RTL** (policy): Do not run synthesis without RTL code
4. **No Formal without Lint** (policy — skill warning): Do not run Formal verification without passing Lint
5. **Verification Required** (HARD — `rtl-verify-stop-gate.sh`): Do not declare completion after RTL modification without functional verification (lint alone is insufficient)
6. **Unit Tests for Phase Gate** (policy — skill warning): Do not proceed to Phase 5 without per-module unit tests upon Phase 4 completion + Stream B early verification artifacts (SVA skeletons, CDC preliminary, TB skeletons)
7. **Feedback Loop Limit** (policy — orchestrator counter): When Phase 5 FAILs, allow a maximum of 2 Phase 4 feedback loops; escalate to user if exceeded
8. **Phase 5 PASS Required** (policy — skill warning): Do not proceed to Phase 6 without Phase 5 PASS (final-compliance.md verdict=PASS required)
9. **Phase 7 Exempt**: Phase 7 is exempt from pipeline rules — free exploration allowed without pipeline Gate

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

### Asymmetric Phase Gate Design
Exit gates are strict, entry gates are flexible.

- **Exit gates** enforce artifact existence (e.g., Stream B files for P4→P5, iron-requirements.json for P1→P2). Missing artifacts → FAIL with specific file list.
- **Entry gates** scan upstream artifacts and emit WARNING for missing items, but proceed with adaptive scope reduction. Only `rat-init-project` is a hard entry block. Note: orchestrator "Context Preload" checks (verifying physical existence of input files a phase MUST read) use STOP, not WARNING — phases cannot function without their input data. This is distinct from entry gates which assess quality/completeness.
- **Feedback loops** are capped (max 2 iterations for P5→P4), then escalate to user via AskUserQuestion.

This ensures downstream phases never receive incomplete inputs, while allowing upstream-incomplete work to proceed with reduced scope.

### Document-as-Memory
Design artifacts serve as persistent memory across phases and agents.

```
iron-requirements.json + open-requirements.json → arch-designer → architecture.md → uarch-designer → docs/phase-3-uarch/*.md → rtl-coder
reviews/phase-N/ → Quality Gate → next phase proceeds or fails
```

- Each phase reads upstream documents as input context and writes downstream documents as output
- No agent needs to "remember" another agent's output — it reads the document
- Enables resumability: any phase can restart by re-reading its input documents
- Each phase generates `phase-N-summary.md` on completion for downstream context efficiency

### Cross-Phase Artifact Functional Consistency
Verification artifacts MUST be functionally validated against their upstream reference —
not merely checked for existence and compilation. Phase 1 (Research) and Phase 6 (Design Note)
are excluded as they produce no executable verification artifacts.

```
Phase 2 refC ──compare──→ external golden C model (if provided, e.g., vendor_ref/) OR Phase 1 requirements
Phase 3 BFM  ──compare──→ Phase 2 refC (shared test vectors, per-block output match) [enforced: G4b gate]
Phase 4 unit ──compare──→ Phase 2 refC golden output [enforced: DPI-C/file; gap: BFM I/O logs]
Phase 5 TB   ──compare──→ Phase 1 requirements via Phase 2 refC as oracle [enforced]
```

- **Validation gates must verify functional correctness** (output comparison), not just
  structural correctness (file exists + compiles)
- If external golden C model is provided (e.g., JM/HM, vendor model): Phase 2 refC AND Phase 3 BFM must both match it
- If no external golden: each phase builds on Phase 1 requirements with progressively more detail
- A verification artifact that compiles but produces wrong output is worse than no artifact —
  it provides false confidence and propagates errors downstream
- BFM validation gate (P3 G4b) must run both models with shared test vectors, compare per-block
  outputs against refC, and FAIL on mismatch before proceeding to review
- P3 G4b is the most explicit gate; P4/P5 enforce refC comparison via existing policies; gap: P4 does not yet consume BFM I/O logs

## Phase-Aware Invocation Cues (Dynamic Spawn Basis)

Use these cues to justify dynamic spawning of the four high-value specialists:

| Agent | Primary Phases | Invoke When |
|---|---|---|
| `rtl-planner` | P3 (μArch), P3→P4 handoff | Task dependency is unclear, repeated rework loops appear, or critical-path ordering blocks convergence |
| `clock-architect` | P3 (μArch), P4 (CDC fix loop), P5 (CDC/top signoff) | Multi-clock/generated-clock/PLL/MMCM/mux/gating strategy needs design review or CDC root cause points to clock architecture |
| `ref-model-reviewer` | P2 (ref model build/review) | C reference model is newly created/updated and must be validated for algorithm fidelity, numerical precision, and UB safety before oracle use. P5 oracle confidence is inherited from P2 validation — no separate P5 trigger unless ref model is modified during P5 |
| `equivalence-checker` | P4 (refactor), review-refactor workflow, P5B (silicon validation) | Change is declared behavior-preserving, or synthesis/ECO/refactor introduces semantic drift risk requiring RTL-vs-RTL or RTL-vs-netlist proof |

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
- Verification done: `touch .rat/state/rtl-verify-done`
- Waiver (non-functional changes): `touch .rat/state/rtl-verify-waiver`

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
Phase 5: Verify      → formal/ + docs/phase-5-verify/
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
| 4 | Integration | `rtl-p5s-integration-test` | Tier 3 pass or PARTIAL_PASS |

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
Diagram rules: `<markdown_diagram_rule>` in CLAUDE.md (or `.claude/rules/diagram-rules.md` fallback)

---

## Domain Packages

Domain packages provide pre-built knowledge bases. Active packages:

| Package | Path | Manifest | Status |
|---------|------|----------|--------|
| video-codec | `domain-packages/video-codec/` | `domain-packages/video-codec/manifest.json` | stable |
| video-processing | `domain-packages/video-processing/` | `domain-packages/video-processing/manifest.json` | active |

Domain expert agents MUST read relevant knowledge files from `domain-packages/{domain}/knowledge/` BEFORE producing analysis.
Each agent's prompt lists the specific files to read in its "Before analysis, read domain knowledge files:" section.

---

## Hook-Based Enforcement

| Hook | Event | Purpose |
|------|-------|---------|
| `rtl-orchestrator-inject.sh` | SessionStart | Inject routing rules and pipeline rules |
| `rtl-project-init-advisor.sh` | SessionStart | Advise rat-init-project if project not initialized |
| `rtl-edit-tracker.sh` | PostToolUse:Edit/Write/Bash | Track RTL file modifications |
| `rtl-skill-activation.sh` | PreToolUse:Skill | Activate skill completion loop + same-skill re-invocation counter reset |
| `stop-gate.sh` | Stop | Autopilot escalation ladder enforcement + dynamic prompt injection |
| `rtl-verify-stop-gate.sh` | Stop | RTL verification gate |
| `rtl-p6-cascade-gate.sh` | Stop | Phase 6 cascade enforcement + document mtime verification |
| `rtl-skill-completion-gate.sh` | Stop | Skill completion escalation ladder enforcement (`N→2N→last-chance→user escalation`) |

Stop hook order (current): `rtl-verify-stop-gate` → `rtl-p6-cascade-gate` → `rtl-skill-completion-gate` → `stop-gate`.

## State Files

Hook-enforced (quality gates):
- `.rat/state/rat-auto-design-state.json` — Full pipeline progress (stop-gate)
- `.rat/state/rat-auto-design-state.json::orchestration_control` — Active gate counters/strategy (`N→2N→last-chance`) and dynamic prompt payload
- `.rat/state/rtl-verify-done` — RTL verification completion gate (rtl-verify-stop-gate)
- `.rat/state/rtl-verify-waiver` — Verification waiver (rtl-verify-stop-gate)
- `.rat/state/skill-active.json` — Skill completion loop state (rtl-skill-activation, rtl-skill-completion-gate)
- `.rat/state/phase6-stale` — Phase 6 cascade marker (rtl-edit-tracker, rtl-p6-cascade-gate)
- `.rat/state/phase6-cascade-done` — Phase 6 cascade completion (rtl-p6-cascade-gate)
- `.rat/state/rtl-modified-files.txt` — Modified RTL file tracking (rtl-edit-tracker, rtl-verify-stop-gate)

Agent-managed (orchestrator resumability):
- `.rat/state/rat-p1p3-spec-uarch-state.json` — Spec-to-μArch pipeline progress
- `.rat/state/rat-p4p5-impl-verify-state.json` — μArch-to-Verify pipeline progress
- `.rat/state/rat-dse-state.json` — DSE pipeline progress
- `.rat/state/feedback-loop-state.json` — Phase 5→4 feedback loop tracking
- `.rat/state/{module}-phase-3-complete.json` — Per-module Phase 3 completion marker

Templates:
- `${CLAUDE_PLUGIN_ROOT}/skills/rat-auto-design/templates/autopilot-state.json` (or `skills/rat-auto-design/templates/autopilot-state.json` in repo context) — v3.0 state schema with `orchestration_control`
- `${CLAUDE_PLUGIN_ROOT}/skills/rat-auto-design/templates/escalation-prompts.json` (or `skills/rat-auto-design/templates/escalation-prompts.json` in repo context) — fallback prompt templates for ladder transitions

---

## SessionStart Hook Export (SSOT)

This block is the single source for SessionStart routing injection.
`scripts/sync_orchestrator_inject.sh` copies it into `hooks/rtl-orchestrator-inject.sh`.

<!-- SESSIONSTART_HOOK_EXPORT_START -->
# RTL Agent Team — Active Project Rules

## Pipeline Rules (Rule 5 hard-enforced; others advisory)
1. No RTL coding without specification (run spec-analyst first) — policy
2. No Testbench without Reference Model — policy
3. No synthesis without RTL code — policy
4. No Formal verification without passing Lint — policy (skill warning)
5. **No completion after RTL modification without functional verification** (lint alone is insufficient) — HARD (rtl-verify-stop-gate.sh)
6. No Phase 5 without per-module unit tests upon Phase 4 completion + Stream B early verification artifacts — policy (skill warning)
7. Phase 5 FAIL → max 2 Phase 4 feedback loops; escalate to user if exceeded — policy (orchestrator counter)
8. No Phase 6 without Phase 5 PASS (final-compliance.md verdict=PASS required) — policy (skill warning)
9. Phase 7 is exempt — free exploration allowed without pipeline Gate

## Iron Requirements Protocol
- Each phase produces iron-requirements.json (binding constraints for downstream) and open-requirements.json (homework for next phase)
- Iron requirements from upper phases MUST NOT be violated
- Authority hierarchy: P1(functional) > P2(architecture) > P3(micro-arch)
- Violation triggers graduated escalation; infeasibility triggers Upstream Challenge with quantitative PPA evidence
- Phase exit requires compliance-checker PASS against all upstream iron

## Routing (key patterns → Action Skill)
Always route user intent to Action Skills first. Orchestrators are internal and spawned by skills.
| Pattern | Route To | Type |
|---|---|---|
| RTL design, chip design, full pipeline | `/rtl-agent-team:rat-auto-design` | Action Skill |
| setup tools, EDA setup, install tools | `/rtl-agent-team:rat-setup` | Action Skill |
| init project, initialize project, new project | `/rtl-agent-team:rat-init-project` | Action Skill |
| debug, diagnostics, plugin status | `/rtl-agent-team:rat-plugin-debug` | Action Skill |
| tutorial, getting started, how to use | `/rtl-agent-team:rat-tutorial` | Action Skill |
| spec analysis, requirements, research | `/rtl-agent-team:p1-spec-research` | Action Skill |
| codec, H.264, H.265, domain expert | `/rtl-agent-team:domain-consult` | Action Skill |
| architecture design (RTL context) | `/rtl-agent-team:p2-arch-design` | Action Skill |
| architecture review | `/rtl-agent-team:arch-review` | Action Skill |
| reference model, C model | `/rtl-agent-team:ref-model` | Action Skill |
| BFM, bus functional model, SystemC | `/rtl-agent-team:bfm-develop` | Action Skill |
| microarchitecture, uarch | `/rtl-agent-team:rtl-p3-uarch-design` | Action Skill |
| DSE, design space exploration | `/rtl-agent-team:rat-dse` | Action Skill |
| Phase 1 team, research team, parallel research | `/rtl-agent-team:rtl-p1-research-team` | Action Skill |
| Phase 2 team, arch team, parallel architecture | `/rtl-agent-team:rtl-p2-arch-team` | Action Skill |
| Phase 3 team, uarch team, parallel uarch | `/rtl-agent-team:rtl-p3-uarch-team` | Action Skill |
| spec to uarch team, Phase 1-3 team | `/rtl-agent-team:rat-p1p3-spec-uarch-team` | Action Skill |
| spec to uarch, Phase 1-3, design only | `/rtl-agent-team:rat-p1p3-spec-uarch` | Action Skill |
| uarch to verify, Phase 4-5, RTL from uarch | `/rtl-agent-team:rat-p4p5-impl-verify` | Action Skill |
| RD eval, BD-PSNR, codec quality | `/rtl-agent-team:codec-rd-eval` | Action Skill |
| decoder conformance, conformance stream | `/rtl-agent-team:codec-conformance-eval` | Action Skill |
| rapid rtl, P4 rapid, sanity integration, fast implementation loop | `/rtl-agent-team:rtl-p4-rapid-impl` | Action Skill |
| bug fix, RTL fix, RTL bug | `/rtl-agent-team:rtl-p4s-bugfix` | Action Skill |
| RTL coding, module implementation | `/rtl-agent-team:rtl-p4-implement` | Action Skill |
| Phase 4 team, implement team, parallel implement | `/rtl-agent-team:rtl-p4-implement-team` | Action Skill |
| block parallel, worktree parallel, 6-block | `/rtl-agent-team:rtl-p4-block-parallel` | Action Skill |
| refactoring (RTL context) | `/rtl-agent-team:rtl-p4s-refactor` | Action Skill |
| unit test (RTL context) | `/rtl-agent-team:rtl-p4s-unit-test` | Action Skill |
| IP instance, IP integration | `/rtl-agent-team:rtl-ip-instantiate` | Action Skill |
| lint, lint check | `/rtl-agent-team:rtl-lint-check` | Action Skill |
| synthesis, yosys, SDC | `/rtl-agent-team:rtl-synth-check` | Action Skill |
| RTL documentation | `/rtl-agent-team:rtl-document` | Action Skill |
| IP-XACT, register map | `/rtl-agent-team:rtl-ipxact-gen` | Action Skill |
| functional closure, P5A, deep functional verification, hierarchical functional closure | `/rtl-agent-team:rtl-p5a-functional-closure` | Action Skill |
| silicon validation, P5B, signoff readiness, timing signoff, post-functional signoff | `/rtl-agent-team:rtl-p5b-silicon-validation` | Action Skill |
| Phase 5, verification pipeline | `/rtl-agent-team:rtl-p5-verify` | Action Skill |
| Phase 5 team, verify team, parallel verify | `/rtl-agent-team:rtl-p5-verify-team` | Action Skill |
| simulation, testbench, cocotb | `/rtl-agent-team:rtl-p5s-func-verify` | Action Skill |
| UVM verification, sequence, agent | `/rtl-agent-team:rtl-p5s-uvm-verify` | Action Skill |
| performance verification, throughput | `/rtl-agent-team:rtl-p5s-perf-verify` | Action Skill |
| formal, SVA, assertion | `/rtl-agent-team:rtl-p5s-sva-check` | Action Skill |
| CDC, clock domain | `/rtl-agent-team:rtl-p5s-cdc-verify` | Action Skill |
| AXI, APB, AHB, protocol | `/rtl-agent-team:rtl-p5s-protocol-verify` | Action Skill |
| coverage | `/rtl-agent-team:rtl-p5s-coverage-analyze` | Action Skill |
| integration test, cross-module, Tier 4 | `/rtl-agent-team:rtl-p5s-integration-test` | Action Skill |
| regression, multi-seed | `/rtl-agent-team:rtl-p5s-func-verify` (Tier 3) | Action Skill |
| RTL conformance, golden comparison | `/rtl-agent-team:rtl-conformance-test` | Action Skill |
| bug reproduction, waveform debug | `/rtl-agent-team:rtl-bug-repro` | Action Skill |
| model consistency, RTL-model compare | `/rtl-agent-team:rtl-model-consistency` | Action Skill |
| cross-phase contract, spec consistency | `/rtl-agent-team:cross-phase-contract-validator` | Action Skill |
| design review, Phase 6, design note | `/rtl-agent-team:rtl-p6-design-review` | Action Skill |
| exploration, Phase 7, free exploration | `/rtl-agent-team:rtl-p7-exploration` | Action Skill |
| ultraloop, autonomous loop, unattended | `/rtl-agent-team:rat-ultraloop` | Action Skill |
| LLM code review, safe refactor, review and refactor workflow | `/rtl-agent-team:rtl-review-refactor` | Action Skill |
| cross-review, codex review, 2nd reviewer, second opinion | `/rtl-agent-team:codex-cross-review` | Action Skill |
| `.sv/.svh/.v/.vh` files | `systemverilog` (auto-applied) | Convention |
| `.sv/.sva` assertion work | `systemverilog-assertion` (auto-applied) | Convention |
| UVM testbench generation | `uvm` (auto-applied) | Convention |
| `.cpp/.h` SystemC/TLM work | `systemc` (auto-applied) | Convention |
Internal routing reference skill (`rtl-orchestrate`) is non-user-invocable and loaded by agents when needed.

## Expert Review → Agent Delegation (spawn directly or through skills)
| Request Pattern | Delegate to Agent |
|---|---|
| CDC, synchronization, clock architecture, PLL | `cdc-reviewer`, `clock-architect` |
| Protocol/AXI design, formal/SVA quality | `protocol-reviewer`, `formal-reviewer` |
| Power analysis, synthesis area/timing | `power-analyzer`, `synthesis-reviewer` |
| UVM/cocotb testbench quality, regression analysis | `uvm-reviewer`, `cocotb-reviewer`, `regression-analyzer` |
| Requirement tracing, ref model review | `requirement-tracer`, `ref-model-reviewer` |
| Equivalence checking, integration verification | `equivalence-checker`, `integration-verifier` |
| Hardware security, DFT/scan/BIST/JTAG | `security-reviewer`, `dft-designer` |

## Core Design Principles
- **Hierarchical Spec Compliance**: Lower stages must never violate upper stage specs. Spec → Arch → μArch → RTL → Verify. Changes require returning upstream.
- **Cascading Quality**: Higher abstraction = more review iterations. Phase 1-3: min 3 rounds each. Fix defects at the top, not the bottom.
- **Document-as-Memory**: Design artifacts serve as persistent memory across phases. Each phase reads upstream docs, writes downstream. Enables resumability.
- **Asymmetric Phase Gate**: Exit gates enforce artifact existence (strict). Entry gates scan and warn but proceed with available artifacts (flexible). Feedback loops capped at 2 iterations before user escalation.
- **Cross-Phase Artifact Functional Consistency**: Verification artifacts (P2 refC, P3 BFM, P4 unit tests, P5 TBs) must be functionally validated against upstream references via output comparison — not just file existence + compilation. BFM that compiles but produces wrong output → FAIL.

## Phase-Aware Invocation Cues (Dynamic Spawn Basis)
- rtl-planner: P3 or P3→P4 handoff when dependency graph and critical path are unclear or rework loops do not converge.
- clock-architect: P3/P4/P5 when multi-clock/generated-clock/PLL/gating/mux choices are risky or CDC root cause points to clock architecture.
- ref-model-reviewer: P2 (and later oracle audits) when ref C model is newly built/updated and must be validated before use as golden oracle.
- equivalence-checker: P4/refactor/P5B when behavior-preserving intent or synthesis/ECO changes require formal semantic equivalence proof.

## Coding Conventions (Core Overrides — .sv/.svh/.v/.vh)
- Port prefix: `i_`, `o_`, `io_` (NOT suffix). Clock/reset exempt
- Clock: `clk` (single) or `{domain}_clk` (multiple), Reset: `rst_n` (single) or `{domain}_rst_n` (multiple) (active-low async)
- No CamelCase: `snake_case` or `ALL_CAPS` only. Params `ALL_CAPS`, localparam `L_` prefix
- SV RTL: IEEE 1800-2009. SV Verification: IEEE 1800-2012. C ref model: C11. C++ BFM: C++17
- Full rules: `.claude/rules/rtl-coding-conventions.md`. Verification gate: `.claude/rules/rtl-verification-gate.md`. Diagram rules: `<markdown_diagram_rule>` in CLAUDE.md (or `.claude/rules/diagram-rules.md` fallback)

## Mandatory Verification After RTL Changes
RTL modify → lint (`verilator --lint-only -Wall`) → TB create/update → simulation PASS → done
Gate: `touch .rat/state/rtl-verify-done` (or `rtl-verify-waiver` for non-functional changes)

## 6+1 Phase Design Pipeline
P1: Research → P2: Arch/Ref → P3: μArch → P4: RTL+Unit → P5: Verify → P6: Design Note → P7: Exploration (optional)
Artifacts: `docs/phase-N-*/` (design guides), `reviews/phase-N-*/` (verdicts)
<!-- SESSIONSTART_HOOK_EXPORT_END -->
