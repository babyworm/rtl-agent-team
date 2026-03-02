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

## Routing (key patterns → skill or orchestrator agent)
Orchestrators: spawn via Task(subagent_type="rtl-agent-team:XXX"). Skills: invoke via Skill().
| Pattern | Route To | Type |
|---|---|---|
| RTL design, chip design, full pipeline | `autopilot-orchestrator` | Orchestrator |
| setup, initialize, project start | `/rtl-agent-team:rtl-setup` | Skill |
| spec analysis, requirements, research | `p1-research-orchestrator` | Orchestrator |
| codec, H.264, H.265, domain expert | `/rtl-agent-team:domain-consult` | Skill |
| architecture design (RTL context) | `p2-arch-orchestrator` | Orchestrator |
| architecture review | `/rtl-agent-team:arch-review` | Skill |
| reference model, C model | `/rtl-agent-team:ref-model` | Skill |
| BFM, bus functional model, SystemC | `/rtl-agent-team:bfm-develop` | Skill |
| microarchitecture, uarch | `p3-uarch-orchestrator` | Orchestrator |
| DSE, design space exploration | `dse-orchestrator` | Orchestrator |
| spec to uarch, Phase 1-3, design only | `spec-to-uarch-orchestrator` | Orchestrator |
| uarch to verify, Phase 4-5, RTL from uarch | `uarch-to-verify-orchestrator` | Orchestrator |
| RD eval, BD-PSNR, codec quality | `/rtl-agent-team:codec-rd-eval` | Skill |
| decoder conformance, conformance stream | `/rtl-agent-team:codec-conformance-eval` | Skill |
| bug fix, RTL fix, RTL bug | `/rtl-agent-team:rtl-p4s-bugfix` | Skill |
| RTL coding, module implementation | `p4-implement-orchestrator` | Orchestrator |
| refactoring (RTL context) | `/rtl-agent-team:rtl-p4s-refactor` | Skill |
| unit test (RTL context) | `/rtl-agent-team:rtl-p4s-unit-test` | Skill |
| IP instance, IP integration | `/rtl-agent-team:rtl-ip-instantiate` | Skill |
| lint, lint check | `/rtl-agent-team:rtl-lint-check` | Skill |
| synthesis, yosys, SDC | `/rtl-agent-team:rtl-synth-check` | Skill |
| RTL documentation | `/rtl-agent-team:rtl-document` | Skill |
| IP-XACT, register map | `/rtl-agent-team:rtl-ipxact-gen` | Skill |
| Phase 5, verification pipeline | `p5-verify-orchestrator` | Orchestrator |
| simulation, testbench, cocotb | `p5s-func-verify-orchestrator` | Orchestrator |
| UVM verification, sequence, agent | `/rtl-agent-team:rtl-p5s-uvm-verify` | Skill |
| performance verification, throughput | `/rtl-agent-team:rtl-p5s-perf-verify` | Skill |
| formal, SVA, assertion | `/rtl-agent-team:rtl-p5s-sva-check` | Skill |
| CDC, clock domain | `/rtl-agent-team:rtl-p5s-cdc-verify` | Skill |
| AXI, APB, AHB, protocol | `/rtl-agent-team:rtl-p5s-protocol-verify` | Skill |
| coverage | `/rtl-agent-team:rtl-p5s-coverage-analyze` | Skill |
| integration test, cross-module, Tier 4 | `/rtl-agent-team:rtl-p5s-integration-test` | Skill |
| regression, multi-seed | `p5s-func-verify-orchestrator` (Tier 3) | Orchestrator |
| RTL conformance, golden comparison | `/rtl-agent-team:rtl-conformance-test` | Skill |
| bug reproduction, waveform debug | `/rtl-agent-team:rtl-bug-repro` | Skill |
| model consistency, RTL-model compare | `/rtl-agent-team:rtl-model-consistency` | Skill |
| design review, Phase 6, design note | `p6-review-orchestrator` | Orchestrator |
| exploration, Phase 7, free exploration | `p6-review-orchestrator` (exploration mode) | Orchestrator |
For complete agent delegation table and design rules, invoke the rtl-orchestrate skill.

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
RULES_EOF
