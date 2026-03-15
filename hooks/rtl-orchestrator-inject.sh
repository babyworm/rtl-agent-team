#!/bin/sh
# SessionStart hook: RTL project orchestration rules injection
# Fires when RTL project directories exist (rtl/ or docs/ or .rtl-agent-team/)
# Injects critical design rules, delegation guidance, and pipeline context.
#
# WHY THIS EXISTS:
# Plugin CLAUDE.md is NOT loaded in user projects — only skills, agents, hooks,
# and MCP servers are loaded from plugins. This hook replaces CLAUDE.md's function
# by auto-injecting the routing rules and absolute rules that Claude needs to
# correctly orchestrate RTL design tasks.
#
# NOTE: This hook outputs raw markdown text (not JSON) because the content is ~96
# lines of structured markdown that would be fragile to JSON-escape in POSIX sh
# without jq. Claude Code SessionStart hooks accept raw text as additional context.
# Other hooks in this project output JSON because their content is simpler.

# Consume stdin (hook protocol)
INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

# Only inject when RTL project is detected
if [ ! -d "$CWD/rtl" ] && [ ! -d "$CWD/docs" ] && [ ! -d "$CWD/.rtl-agent-team" ]; then
  exit 0
fi

cat << 'RULES_EOF'
# BEGIN GENERATED ROUTING BLOCK - sync via scripts/sync_orchestrator_inject.sh
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

## Iron Requirements Protocol
- Each phase produces iron-requirements.json (absolute rules) and open-requirements.json (homework for next phase)
- Iron requirements from upper phases MUST NOT be violated
- Authority hierarchy: P1(functional) > P2(architecture) > P3(micro-arch)
- Violation triggers graduated escalation; infeasibility triggers Upstream Challenge with quantitative PPA evidence
- Phase exit requires compliance-checker PASS against all upstream iron

## Routing (key patterns → Action Skill)
Always route user intent to Action Skills first. Orchestrators are internal and spawned by skills.
| Pattern | Route To | Type |
|---|---|---|
| RTL design, chip design, full pipeline | `/rtl-agent-team:rat-auto-design` | Action Skill |
| setup, initialize, project start | `/rtl-agent-team:rat-setup` | Action Skill |
| debug, diagnostics, plugin status | `/rtl-agent-team:rat-plugin-debug` | Action Skill |
| tutorial, getting started, how to use | `/rtl-agent-team:rat-tutorial` | Action Skill |
| spec analysis, requirements, research | `/rtl-agent-team:p1-spec-research` | Action Skill |
| codec, H.264, H.265, domain expert | `/rtl-agent-team:domain-consult` | Action Skill |
| architecture design (RTL context) | `/rtl-agent-team:p2-arch-design` | Action Skill |
| architecture review | `/rtl-agent-team:arch-review` | Action Skill |
| reference model, C model | `/rtl-agent-team:ref-model` | Action Skill |
| BFM, bus functional model, SystemC | `/rtl-agent-team:bfm-develop` | Action Skill |
| microarchitecture, uarch | `/rtl-agent-team:rtl-p3-uarch-design` | Action Skill |
| DSE, design space exploration | `/rtl-agent-team:rtl-dse` | Action Skill |
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
- **Asymmetric Phase Gate**: Exit gates enforce artifact existence (strict). Entry gates scan and warn but proceed with available artifacts (flexible). Feedback loops capped at 2 iterations before user escalation.

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
- Full rules: `.claude/rules/rtl-coding-conventions.md`. Verification gate: `.claude/rules/rtl-verification-gate.md`. Diagram rules: `.claude/rules/diagram-rules.md`

## Mandatory Verification After RTL Changes
RTL modify → lint (`verilator --lint-only -Wall`) → TB create/update → simulation PASS → done
Gate: `touch .rtl-agent-team/state/rtl-verify-done` (or `rtl-verify-waiver` for non-functional changes)

## 6+1 Phase Design Pipeline
P1: Research → P2: Arch/Ref → P3: μArch → P4: RTL+Unit → P5: Verify → P6: Design Note → P7: Exploration (optional)
Artifacts: `docs/phase-N-*/` (design guides), `reviews/phase-N-*/` (verdicts)
# END GENERATED ROUTING BLOCK
RULES_EOF
