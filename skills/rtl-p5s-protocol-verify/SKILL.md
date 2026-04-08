---
name: rtl-p5s-protocol-verify
description: "This skill should be used when verifying bus protocol compliance (AXI/AHB/APB) using SVA handshake and ordering rules."
user-invocable: true
argument-hint: "[module-name --protocol=AXI|AHB|APB]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Verify that RTL bus interfaces comply with AXI, AHB, or APB protocol specifications
using formal SVA assertions and simulation-based protocol checking.
Outputs: reviews/phase-5-verify/protocol-report.md + formal/{bus}_assertions.sv.
</Purpose>

<Use_When>
- RTL module has AXI, AHB, or APB interface
- Protocol compliance needed before SoC integration
- Checking a specific protocol violation reported in simulation
- Adding protocol assertions to an existing design
</Use_When>

<Do_Not_Use_When>
- Custom/proprietary protocol (use rtl-p5s-sva-check for general SVA)
- Only functional behavior matters, not protocol compliance
- Protocol is already verified and RTL has not changed
</Do_Not_Use_When>

<Why_This_Exists>
Protocol violations cause SoC-level integration failures that are hard to debug.
Formal SVA assertions catch violations exhaustively; simulation-based checking
catches violations on real traffic patterns. Both are needed for confidence.
</Why_This_Exists>

## Prerequisites

RTL modules with bus interfaces required:
- `rtl/**/*.sv` files must exist with AXI/AHB/APB interface signals

If prerequisite is missing: WARNING — recommend running `/rtl-agent-team:rtl-p4-implement`.
Proceed with available artifacts — orchestrator will adapt scope.

## Execution

Task(subagent_type="rtl-agent-team:p5s-protocol-orchestrator",
     prompt="Execute protocol compliance verification. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages bus interface identification, SVA protocol assertion
generation, simulation-based checking, and violation reporting.
