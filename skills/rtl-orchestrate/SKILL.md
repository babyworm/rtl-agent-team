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
| "RTL design", "verilog", "FPGA", "ASIC", "chip design", "rtl-autopilot" | `/rtl-agent-team:rtl-autopilot` | Action Skill |
| "setup", "initialize", "project start", "init", "docker image", "EDA docker" | `/rtl-agent-team:rtl-setup` | Action Skill |
| **--- Phase 1: Research ---** | | |
| "spec analysis", "requirements", "paper research", "research" | `/rtl-agent-team:p1-spec-research` | Action Skill |
| "codec consultation", "H.264", "H.265", "domain expert" | `/rtl-agent-team:domain-consult` | Action Skill |
| **--- Phase 2: Architecture ---** | | |
| "architecture design" (RTL context) | `/rtl-agent-team:p2-arch-design` | Action Skill |
| "architecture review", "arch review" | `/rtl-agent-team:arch-review` | Action Skill |
| "reference model", "ref model", "C model" | `/rtl-agent-team:ref-model` | Action Skill |
| "BFM", "bus functional model", "SystemC model" | `/rtl-agent-team:bfm-develop` | Action Skill |
| **--- Phase 3: μArch ---** | | |
| "microarchitecture", "μArch", "uarch", "pipeline design" | `/rtl-agent-team:rtl-p3-uarch-design` | Action Skill |
| **--- Pipeline Composition ---** | | |
| "DSE", "design space exploration", "algorithm study", "architecture comparison" | `/rtl-agent-team:rtl-dse` | Action Skill |
| "spec to uarch", "design only", "Phase 1-3", "design documents only" | `/rtl-agent-team:rtl-spec-to-uarch` | Action Skill |
| "uarch to verify", "implement and verify", "Phase 4-5", "RTL from uarch" | `/rtl-agent-team:rtl-uarch-to-verify` | Action Skill |
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
| "free exploration", "exploration", "Phase 7", "improvement exploration" | `/rtl-agent-team:rtl-p6-design-review` (exploration mode) | Action Skill |
| **--- Other Verification ---** | | |
| "LLM code review", "safe refactor", "review and refactor workflow" | `/rtl-agent-team:rtl-review-refactor` | Action Skill |
| "integration test", "cross-module test", "end-to-end test", "Tier 4" | `/rtl-agent-team:rtl-p5s-integration-test` | Action Skill |
| "regression", "multi-seed" | `/rtl-agent-team:rtl-p5s-func-verify` (Tier 3) | Action Skill |
| "RTL conformance", "RTL conformance test", "RTL golden comparison" | `/rtl-agent-team:rtl-conformance-test` | Action Skill |
| "bug reproduction", "bug repro", "waveform debug" | `/rtl-agent-team:rtl-bug-repro` | Action Skill |
| "model consistency", "RTL-model comparison" | `/rtl-agent-team:rtl-model-consistency` | Action Skill |
| "routing help", "which skill to use", "routing reference" | `rtl-orchestrate` (internal context only) | Internal Reference |

### Action Skill → Orchestrator Agent Mapping (internal)

Action Skills are user-facing. Each action delegates to one orchestrator agent, which loads one policy skill.

| Action Skill | Orchestrator Agent | Policy Skill |
|--------------|--------------------|-------------|
| `rtl-autopilot` | `autopilot-orchestrator` | `rtl-autopilot-policy` |
| `p1-spec-research` | `p1-research-orchestrator` | `p1-spec-research-policy` |
| `p2-arch-design` | `p2-arch-orchestrator` | `p2-arch-design-policy` |
| `rtl-p3-uarch-design` | `p3-uarch-orchestrator` | `rtl-p3-uarch-policy` |
| `rtl-p4-implement` | `p4-implement-orchestrator` | `rtl-p4-implement-policy` |
| `rtl-p4-rapid-impl` | `p4-rtl-sanity-orchestrator` | `rtl-design-policy` |
| `rtl-p4s-bugfix` | `p4s-bugfix-orchestrator` | `rtl-p4s-bugfix-policy` |
| `rtl-p4s-unit-test` | `p4s-unit-test-orchestrator` | `rtl-p4s-unit-test-policy` |
| `rtl-p5-verify` | `p5-verify-orchestrator` | `rtl-p5-verify-policy` |
| `rtl-p5a-functional-closure` | `p5a-functional-closure-orchestrator` | `rtl-functional-verify-policy` |
| `rtl-p5b-silicon-validation` | `p5b-silicon-validation-orchestrator` | `rtl-silicon-validation-policy` |
| `rtl-p5s-func-verify` | `p5s-func-verify-orchestrator` | `rtl-p5s-func-verify-policy` |
| `rtl-p5s-integration-test` | `p5s-integration-orchestrator` | `rtl-p5s-integration-test-policy` |
| `rtl-p6-design-review` | `p6-review-orchestrator` | `rtl-p6-design-review-policy` |
| `rtl-review-refactor` | `review-refactor-orchestrator` | `code-review-policy`, `refactor-policy`, `verification-recheck-policy` |
| `rtl-dse` | `dse-orchestrator` | `rtl-dse-policy` |
| `rtl-spec-to-uarch` | `spec-to-uarch-orchestrator` | `rtl-spec-to-uarch-policy` |
| `rtl-uarch-to-verify` | `uarch-to-verify-orchestrator` | `rtl-uarch-to-verify-policy` |

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
| Full pipeline (P1→P6) | `autopilot-orchestrator` | `rtl-autopilot-policy` |
| Phase 1: Research | `p1-research-orchestrator` | `p1-spec-research-policy` |
| Phase 2: Architecture | `p2-arch-orchestrator` | `p2-arch-design-policy` |
| Phase 3: μArch | `p3-uarch-orchestrator` | `rtl-p3-uarch-policy` |
| Phase 4: RTL Implementation | `p4-implement-orchestrator` | `rtl-p4-implement-policy` |
| Phase 4: Rapid RTL + Sanity | `p4-rtl-sanity-orchestrator` | `rtl-design-policy` |
| Phase 4: Bug Fix | `p4s-bugfix-orchestrator` | `rtl-p4s-bugfix-policy` |
| Phase 4: Unit Test | `p4s-unit-test-orchestrator` | `rtl-p4s-unit-test-policy` |
| Phase 5: Verification | `p5-verify-orchestrator` | `rtl-p5-verify-policy` |
| Phase 5A: Functional Closure | `p5a-functional-closure-orchestrator` | `rtl-functional-verify-policy` |
| Phase 5B: Silicon Validation | `p5b-silicon-validation-orchestrator` | `rtl-silicon-validation-policy` |
| Phase 5: Func Verify | `p5s-func-verify-orchestrator` | `rtl-p5s-func-verify-policy` |
| Phase 5: Integration | `p5s-integration-orchestrator` | `rtl-p5s-integration-test-policy` |
| Phase 6: Design Review | `p6-review-orchestrator` | `rtl-p6-design-review-policy` |
| LLM Review + Refactor | `review-refactor-orchestrator` | `code-review-policy` + `refactor-policy` + `verification-recheck-policy` |
| DSE | `dse-orchestrator` | `rtl-dse-policy` |
| Spec→μArch (P1-3) | `spec-to-uarch-orchestrator` | `rtl-spec-to-uarch-policy` |
| μArch→Verify (P4-5) | `uarch-to-verify-orchestrator` | `rtl-uarch-to-verify-policy` |

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
| `stop-gate.sh` | Stop | Autopilot escalation ladder enforcement + dynamic prompt injection |
| `rtl-verify-stop-gate.sh` | Stop | RTL verification gate |
| `rtl-p6-cascade-gate.sh` | Stop | Phase 6 cascade enforcement |
| `rtl-skill-completion-gate.sh` | Stop | Skill completion escalation ladder enforcement (`N→2N→last-chance→user escalation`) |

Stop hook order (current): `rtl-verify-stop-gate` → `rtl-p6-cascade-gate` → `rtl-skill-completion-gate` → `stop-gate`.

## State Files

Hook-enforced (quality gates):
- `.rtl-agent-team/state/rtl-autopilot-state.json` — Full pipeline progress (stop-gate)
- `.rtl-agent-team/state/rtl-autopilot-state.json::orchestration_control` — Active gate counters/strategy (`N→2N→last-chance`) and dynamic prompt payload
- `.rtl-agent-team/state/rtl-verify-done` — RTL verification completion gate (rtl-verify-stop-gate)
- `.rtl-agent-team/state/rtl-verify-waiver` — Verification waiver (rtl-verify-stop-gate)
- `.rtl-agent-team/state/skill-active.json` — Skill completion loop state (rtl-skill-activation, rtl-skill-completion-gate)
- `.rtl-agent-team/state/phase6-stale` — Phase 6 cascade marker (rtl-edit-tracker, rtl-p6-cascade-gate)
- `.rtl-agent-team/state/phase6-cascade-done` — Phase 6 cascade completion (rtl-p6-cascade-gate)
- `.rtl-agent-team/state/rtl-modified-files.txt` — Modified RTL file tracking (rtl-edit-tracker, rtl-verify-stop-gate)

Agent-managed (orchestrator resumability):
- `.rtl-agent-team/state/rtl-spec-to-uarch-state.json` — Spec-to-μArch pipeline progress
- `.rtl-agent-team/state/rtl-uarch-to-verify-state.json` — μArch-to-Verify pipeline progress
- `.rtl-agent-team/state/rtl-dse-state.json` — DSE pipeline progress
- `.rtl-agent-team/state/feedback-loop-state.json` — Phase 5→4 feedback loop tracking
- `.rtl-agent-team/state/{module}-phase-3-complete.json` — Per-module Phase 3 completion marker

Templates:
- `${CLAUDE_PLUGIN_ROOT}/skills/rtl-autopilot/templates/autopilot-state.json` (or `skills/rtl-autopilot/templates/autopilot-state.json` in repo context) — v3.0 state schema with `orchestration_control`
- `${CLAUDE_PLUGIN_ROOT}/skills/rtl-autopilot/templates/escalation-prompts.json` (or `skills/rtl-autopilot/templates/escalation-prompts.json` in repo context) — fallback prompt templates for ladder transitions

---

## SessionStart Hook Export (SSOT)

This block is the single source for SessionStart routing injection.
`scripts/sync_orchestrator_inject.sh` copies it into `hooks/rtl-orchestrator-inject.sh`.

<!-- SESSIONSTART_HOOK_EXPORT_START -->
# RTL Agent Team — Active Project Rules

## Absolute Rules (Hard Gates)
1. No RTL coding without specification (run spec-analyst first)
2. No Testbench without Reference Model
3. No synthesis without RTL code
4. No Formal verification without passing Lint
5. No completion after RTL modification without functional verification (lint alone is insufficient)
6. No Phase 5 without per-module unit tests upon Phase 4 completion + Stream B early verification artifacts
7. Phase 5 FAIL → max 2 Phase 4 feedback loops; escalate to user if exceeded
8. No Phase 6 without Phase 5 PASS (final-compliance.md verdict=PASS required)
9. Phase 7 is exempt — free exploration allowed without pipeline Gate

## Routing (key patterns → Action Skill)
Always route user intent to Action Skills first. Orchestrators are internal and spawned by skills.
| Pattern | Route To | Type |
|---|---|---|
| RTL design, chip design, full pipeline | `/rtl-agent-team:rtl-autopilot` | Action Skill |
| setup, initialize, project start | `/rtl-agent-team:rtl-setup` | Action Skill |
| spec analysis, requirements, research | `/rtl-agent-team:p1-spec-research` | Action Skill |
| codec, H.264, H.265, domain expert | `/rtl-agent-team:domain-consult` | Action Skill |
| architecture design (RTL context) | `/rtl-agent-team:p2-arch-design` | Action Skill |
| architecture review | `/rtl-agent-team:arch-review` | Action Skill |
| reference model, C model | `/rtl-agent-team:ref-model` | Action Skill |
| BFM, bus functional model, SystemC | `/rtl-agent-team:bfm-develop` | Action Skill |
| microarchitecture, uarch | `/rtl-agent-team:rtl-p3-uarch-design` | Action Skill |
| DSE, design space exploration | `/rtl-agent-team:rtl-dse` | Action Skill |
| spec to uarch, Phase 1-3, design only | `/rtl-agent-team:rtl-spec-to-uarch` | Action Skill |
| uarch to verify, Phase 4-5, RTL from uarch | `/rtl-agent-team:rtl-uarch-to-verify` | Action Skill |
| RD eval, BD-PSNR, codec quality | `/rtl-agent-team:codec-rd-eval` | Action Skill |
| decoder conformance, conformance stream | `/rtl-agent-team:codec-conformance-eval` | Action Skill |
| rapid rtl, P4 rapid, sanity integration, fast implementation loop | `/rtl-agent-team:rtl-p4-rapid-impl` | Action Skill |
| bug fix, RTL fix, RTL bug | `/rtl-agent-team:rtl-p4s-bugfix` | Action Skill |
| RTL coding, module implementation | `/rtl-agent-team:rtl-p4-implement` | Action Skill |
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
| design review, Phase 6, design note | `/rtl-agent-team:rtl-p6-design-review` | Action Skill |
| exploration, Phase 7, free exploration | `/rtl-agent-team:rtl-p6-design-review` (exploration mode) | Action Skill |
| LLM code review, safe refactor, review and refactor workflow | `/rtl-agent-team:rtl-review-refactor` | Action Skill |
| `.sv/.svh/.v/.vh` files | `systemverilog` (auto-applied) | Convention |
| `.sv/.sva` assertion work | `systemverilog-assertion` (auto-applied) | Convention |
| UVM testbench generation | `uvm` (auto-applied) | Convention |
| `.cpp/.h` SystemC/TLM work | `systemc` (auto-applied) | Convention |
Internal routing reference skill (`rtl-orchestrate`) is non-user-invocable and loaded by agents when needed.

## Expert Review → Agent Delegation (spawn directly or through skills)
| Request Pattern | Delegate to Agent |
|---|---|
| CDC review, synchronization strategy | `cdc-reviewer` |
| Protocol/AXI design review | `protocol-reviewer` |
| Formal/SVA quality review | `formal-reviewer` |
| Power analysis/estimation | `power-analyzer` |
| Synthesis area/timing review | `synthesis-reviewer` |
| UVM testbench quality | `uvm-reviewer` |
| Requirement tracing, feature coverage | `requirement-tracer` |
| cocotb testbench review | `cocotb-reviewer` |
| Ref model review | `ref-model-reviewer` |
| Regression/flaky test analysis | `regression-analyzer` |
| Equivalence checking | `equivalence-checker` |
| Integration/top-level verification | `integration-verifier` |
| Hardware security | `security-reviewer` |
| DFT/scan chain/BIST/JTAG | `dft-designer` |
| Clock architecture/PLL | `clock-architect` |

## Core Design Principles
- **Hierarchical Spec Compliance**: Lower stages must never violate upper stage specs. Spec → Arch → μArch → RTL → Verify. Changes require returning upstream.
- **Cascading Quality**: Higher abstraction = more review iterations. Phase 1-3: min 3 rounds each. Fix defects at the top, not the bottom.
- **Document-as-Memory**: Design artifacts serve as persistent memory across phases. Each phase reads upstream docs, writes downstream. Enables resumability.

## Coding Conventions (Core Overrides — .sv/.svh/.v/.vh)
- Port prefix: `i_`, `o_`, `io_` (NOT suffix). Clock/reset exempt
- Clock: `clk` (single) or `{domain}_clk` (multiple), Reset: `rst_n` (single) or `{domain}_rst_n` (multiple) (active-low async)
- No CamelCase: `snake_case` or `ALL_CAPS` only. Params `ALL_CAPS`, localparam `L_` prefix
- SV RTL: IEEE 1800-2009. SV Verification: IEEE 1800-2012. C ref model: C11. C++ BFM: C++17
- Full rules: `.claude/rules/rtl-coding-conventions.md`. Verification gate: `.claude/rules/rtl-verification-gate.md`. Diagram rules: `.claude/rules/diagram-rules.md`

## Mandatory Verification After RTL Changes
RTL modify → lint (`verilator --lint-only -Wall`) → TB create/update → simulation PASS → done
Gate: `touch .rtl-agent-team/state/rtl-verify-done` (or `rtl-verify-waiver` for non-functional changes)

## 6+1 Phase Design Pipeline
P1: Research → P2: Arch/Ref → P3: μArch → P4: RTL+Unit → P5: Verify → P6: Design Note → P7: Exploration (optional)
Artifacts: `docs/phase-N-*/` (design guides), `reviews/phase-N-*/` (verdicts)
<!-- SESSIONSTART_HOOK_EXPORT_END -->
