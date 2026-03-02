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

# Only inject when RTL project is detected
if [ ! -d "rtl" ] && [ ! -d "docs" ] && [ ! -d ".rtl-agent-team" ]; then
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

## Skill Routing (key patterns → skill)
| Pattern | Skill |
|---|---|
| RTL design, chip design, full pipeline | `/rtl-agent-team:rtl-autopilot` (command) |
| setup, initialize, project start | `/rtl-agent-team:rtl-setup` |
| spec analysis, requirements, research | `/rtl-agent-team:p1-spec-research` (command) |
| codec, H.264, H.265, domain expert | `/rtl-agent-team:domain-consult` |
| architecture design (RTL context) | `/rtl-agent-team:p2-arch-design` (command) |
| architecture review | `/rtl-agent-team:arch-review` |
| reference model, C model | `/rtl-agent-team:ref-model` |
| BFM, bus functional model, SystemC | `/rtl-agent-team:bfm-develop` |
| microarchitecture, uarch | `/rtl-agent-team:rtl-p3-uarch-design` (command) |
| DSE, design space exploration | `/rtl-agent-team:rtl-dse` (command) |
| spec to uarch, Phase 1-3, design only | `/rtl-agent-team:rtl-spec-to-uarch` (command) |
| uarch to verify, Phase 4-5, RTL from uarch | `/rtl-agent-team:rtl-uarch-to-verify` (command) |
| bug fix, RTL fix, RTL bug | `/rtl-agent-team:rtl-p4s-bugfix` |
| RTL coding, module implementation | `/rtl-agent-team:rtl-p4-implement` (command) |
| refactoring (RTL context) | `/rtl-agent-team:rtl-p4s-refactor` |
| unit test (RTL context) | `/rtl-agent-team:rtl-p4s-unit-test` |
| lint, lint check | `/rtl-agent-team:rtl-lint-check` |
| synthesis, yosys, SDC | `/rtl-agent-team:rtl-synth-check` |
| Phase 5, verification pipeline | `/rtl-agent-team:rtl-p5-verify` (command) |
| simulation, testbench, cocotb | `/rtl-agent-team:rtl-p5s-func-verify` (command) |
| formal, SVA, assertion | `/rtl-agent-team:rtl-p5s-sva-check` |
| CDC, clock domain | `/rtl-agent-team:rtl-p5s-cdc-verify` |
| AXI, APB, AHB, protocol | `/rtl-agent-team:rtl-p5s-protocol-verify` |
| coverage | `/rtl-agent-team:rtl-p5s-coverage-analyze` |
| design review, Phase 6, design note | `/rtl-agent-team:rtl-p6-design-review` (command) |
Full routing table: `/rtl-agent-team:rtl-orchestrate`

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
- SV RTL: IEEE 1800-2009. SV Verification: IEEE 1800-2012. C ref model: C11
- Full rules: `.claude/rules/rtl-coding-conventions.md`

## Mandatory Verification After RTL Changes
RTL modify → lint (`verilator --lint-only -Wall`) → TB create/update → simulation PASS → done
Gate: `touch .rtl-agent-team/state/rtl-verify-done` (or `rtl-verify-waiver` for non-functional changes)

## 6+1 Phase Design Pipeline
P1: Research → P2: Arch/Ref → P3: μArch → P4: RTL+Unit → P5: Verify → P6: Design Note → P7: Exploration (optional)
Artifacts: `docs/phase-N-*/` (design guides), `reviews/phase-N-*/` (verdicts)
RULES_EOF
