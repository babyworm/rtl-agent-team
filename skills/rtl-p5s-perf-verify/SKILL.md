---
name: rtl-p5s-perf-verify
description: "P5 performance verification: RTL throughput/latency/stalls vs BFM baseline. Triggers 'measure throughput', 'performance regression', 'latency vs BFM'."
user-invocable: true
argument-hint: "[module-name]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Measure RTL performance (throughput, latency, stall cycles) against BFM-predicted baselines and flag deviations exceeding 10%. Outputs: `sim/{module}/{module}_perf.json` (raw measured vs expected metrics) and `reviews/phase-5-verify/{module}-performance-report.md` (PASS/FAIL verdict with deviation analysis).
</Purpose>

<Use_When>
- RTL passes functional verification and performance validation is the next step.
- A BFM performance baseline exists in `bfm/perf_baseline.json`.
- A performance regression needs quantification after an RTL change.
</Use_When>

<Do_Not_Use_When>
- BFM does not exist yet — run `bfm-develop` first.
- Functional correctness is not yet established — run `rtl-p5s-func-verify` first.
- Synthesis timing analysis (setup/hold slack) is needed — use `rtl-synth-check` instead.
</Do_Not_Use_When>

<Why_This_Exists>
RTL that is functionally correct may still fail performance targets due to unexpected stalls, backpressure, or pipeline bubbles invisible to functional tests. BFM provides the performance baseline; RTL must match it. Separating performance measurement from functional verification keeps each pass focused and regressions attributable.
</Why_This_Exists>

## Prerequisites

- `rtl/**/*.sv` files must exist.
- `bfm/perf_baseline.json` must exist.

If prerequisites are missing: WARNING — recommend running `/rtl-agent-team:rtl-p5s-func-verify` and `/rtl-agent-team:bfm-develop` first. Orchestrator adapts scope with available artifacts.

<Assets>
| Path | Role |
|------|------|
| `templates/perf-monitor-template.sv` | SV measurement harness scaffold: cycle counter, throughput/latency monitors wired to DUT ports. |
| `scripts/parse_perf_report.py` | Deterministic comparator: parses the perf-monitor summary block from the sim run log, compares against `bfm/perf_baseline.json`, writes `{module}_perf.json` with per-metric delta_pct/verdict (10% threshold; exit 1 on FAIL). |
| `references/perf-verify-conventions.md` | Metric naming, JSON schema, 10% deviation threshold, report structure, anti-patterns. |
| `examples/` | Worked example: sample run log + baseline + generated `cabac_encoder_perf.json` + README with the exact command and metric arithmetic. |
</Assets>

<Responsibility_Boundary>
- **Scripts** handle deterministic measurement: cycle counters and throughput monitors in the SV harness produce raw numeric values written to the JSON output.
- **LLM** handles interpretive analysis: deviation root cause (which pipeline stage contributes stalls), recommendation text, and BFM vs RTL gap narrative.
- Contract surface: `{module}_perf.json` schema and report structure documented in `references/perf-verify-conventions.md`.
</Responsibility_Boundary>

<Execution>
1. Read `skills/rtl-p5s-perf-verify/references/perf-verify-conventions.md` for the JSON schema, 10% deviation threshold, and report structure.
2. Spawn `p5s-perf-orchestrator` (see Tool_Usage) to execute performance simulation using `templates/perf-monitor-template.sv` as the measurement harness scaffold.
3. The orchestrator reads `bfm/perf_baseline.json`, runs the simulation, and writes `sim/{module}/{module}_perf.json` with measured vs expected values and per-metric PASS/FAIL verdicts. For deterministic comparison it can run `python3 {plugin_root}/skills/rtl-p5s-perf-verify/scripts/parse_perf_report.py --log sim/{module}/{module}_perf_run.log --baseline bfm/perf_baseline.json -o sim/{module}/{module}_perf.json` (`{plugin_root}` = plugin root resolved from `.rat/state/spawn-context.json`; see `examples/README.md` for flags).
4. The orchestrator writes `reviews/phase-5-verify/{module}-performance-report.md` with the metrics table, deviation analysis for any failing metric, and a recommendation.
5. Report the overall PASS/FAIL verdict and the report path to the user.

Apply steps 1-5 to every requested module — do not stop after the first.
</Execution>

<Tool_Usage>
Performance orchestration:
```
Task(subagent_type="rtl-agent-team:p5s-perf-orchestrator",
     prompt="Execute performance verification. User input: $ARGUMENTS")
```

Do not perform simulation work directly — the orchestrator manages performance simulation, BFM baseline comparison, throughput/latency/stall measurement, and deviation flagging.
</Tool_Usage>

<Examples>
<example index="1">
<scenario>Video encoder module after a pipeline rebalancing change; throughput must match BFM baseline within 10%.</scenario>
<reference>skills/rtl-p5s-perf-verify/examples/</reference>
<expected_output>JSON reports throughput 480 Mbps measured vs 500 Mbps expected (4% delta → PASS); latency 12 cycles vs 12 expected (0% → PASS); overall PASS. Report recommends proceeding to `rtl-p6-design-review`.</expected_output>
</example>

<example index="2">
<scenario>RTL change introduced a pipeline bubble; stall cycles exceed baseline by 15%.</scenario>
<reference>skills/rtl-p5s-perf-verify/examples/</reference>
<expected_output>JSON reports stall_cycles_pct 23% measured vs 8% expected (188% delta → FAIL); overall FAIL. Report identifies the added pipeline register at the output FIFO as the contributor; recommends inspecting `rtl/encoder/output_buffer.sv`.</expected_output>
</example>

<example index="3">
<scenario>`bfm/perf_baseline.json` is absent before BFM development is complete.</scenario>
<reference>skills/rtl-p5s-perf-verify/examples/</reference>
<expected_output>WARNING emitted: `bfm/perf_baseline.json` not found — recommend running `/rtl-agent-team:bfm-develop` first. Skill does not proceed to simulation.</expected_output>
</example>
</Examples>

<Escalation_And_Stop_Conditions>
- `bfm/perf_baseline.json` absent → emit WARNING; do not fabricate baseline values; stop.
- Simulation fails to compile or run → report the error; do not report performance metrics.
- Deviation exceeds 10% → report FAIL with deviation analysis; do not auto-accept.
- Performance bottleneck requires RTL-level investigation → flag the suspected module and signal path; do not modify RTL.
</Escalation_And_Stop_Conditions>

## Output

- `sim/{module}/{module}_perf.json` — raw measured vs expected metric values with per-metric PASS/FAIL.
- `reviews/phase-5-verify/{module}-performance-report.md` — throughput and latency table vs BFM baseline, deviation analysis, PASS/FAIL verdict.

<Final_Checklist>
- [ ] `bfm/perf_baseline.json` read as baseline source — no fabricated values.
- [ ] `sim/{module}/{module}_perf.json` written with all three metric categories.
- [ ] Metrics exceeding 10% deviation flagged as FAIL.
- [ ] `reviews/phase-5-verify/{module}-performance-report.md` written with deviation analysis.
- [ ] RTL source not modified.
- [ ] Overall verdict and report path reported to the user.
</Final_Checklist>
