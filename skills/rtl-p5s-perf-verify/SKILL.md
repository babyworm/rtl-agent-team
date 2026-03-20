---
name: rtl-p5s-perf-verify
description: "This skill should be used when measuring RTL throughput and latency against BFM baselines. Flags deviations exceeding 10%."
user-invocable: true
argument-hint: "[module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Measure RTL performance (throughput, latency, stall cycles) and compare against BFM predictions.
Outputs: sim/{module}/{module}_perf.json with measured vs expected metrics.
</Purpose>

<Use_When>
- RTL passes functional verification and performance validation is needed
- Use `skills/rtl-p5s-perf-verify/templates/perf-monitor-template.sv` as measurement harness scaffold
- BFM performance baseline exists in bfm/
- Performance regression after RTL change
</Use_When>

<Do_Not_Use_When>
- BFM does not exist (run bfm-develop first)
- Functional correctness not yet established (run rtl-p5s-func-verify first)
- Synthesis timing analysis needed (use rtl-synth-check instead)
</Do_Not_Use_When>

<Why_This_Exists>
RTL that is functionally correct may still fail performance targets due to unexpected stalls,
backpressure, or pipeline bubbles. BFM provides the performance baseline; RTL must match it.
</Why_This_Exists>

## Prerequisites

RTL modules and BFM baseline required:
- `rtl/**/*.sv` files must exist
- `bfm/perf_baseline.json` must exist

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:rtl-p5s-func-verify`
and `/rtl-agent-team:bfm-develop` first. Orchestrator will adapt scope with available artifacts.

## Execution

Task(subagent_type="rtl-agent-team:p5s-perf-orchestrator",
     prompt="Execute performance verification. User input: $ARGUMENTS")

Do not perform any work directly.
The orchestrator agent manages performance simulation, BFM baseline comparison,
throughput/latency/stall measurement, and deviation flagging.
