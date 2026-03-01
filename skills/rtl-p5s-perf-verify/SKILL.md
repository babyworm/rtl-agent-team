---
name: rtl-p5s-perf-verify
description: "This skill should be used when measuring RTL throughput and latency against BFM baselines. Flags deviations exceeding 10%."
---

<Purpose>
Measure RTL performance (throughput, latency, stall cycles) and compare against BFM predictions.
Outputs: sim/{module}/{module}_perf.json with measured vs expected metrics.
</Purpose>

<Use_When>
- RTL passes functional verification and performance validation is needed
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

<Coding_Convention_Requirements>
Performance monitor instrumentation and testbenches MUST follow project conventions (CLAUDE.md):
- Signal references: `i_` prefix for inputs, `o_` prefix for outputs (e.g., `i_valid`, `o_stall`)
- Clock: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
- Reset: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
- Performance counter instances: `u_` prefix (e.g., `u_perf_counter`)
- Use `logic` for all signal declarations (NOT `reg`/`wire`)
</Coding_Convention_Requirements>

<Execution_Policy>
- perf-verifier runs RTL simulation with performance monitors enabled via Bash CLI
- waveform-analyzer extracts cycle counts and stall statistics
- Compare against BFM metrics; flag any metric exceeding 10% deviation
</Execution_Policy>

<Steps>
1. perf-verifier sets up RTL simulation with performance counter instrumentation
   - Counters track `o_valid`/`i_ready` handshake cycles, stall cycles, latency
2. eda-runner runs simulation on standard performance test vectors via Bash CLI (deterministic, not random)
3. waveform-analyzer extracts: throughput (bits/cycle), latency (cycles), stall rate (%)
4. Read BFM performance baseline from bfm/perf_baseline.json
5. Compare RTL vs BFM per metric; flag deviations >10%
6. Write sim/{module}/{module}_perf.json: {metric, rtl_value, bfm_value, delta_pct, status}
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:perf-verifier",
     prompt="Run RTL performance simulation for rtl/cabac_encoder/cabac_encoder.sv with perf monitors. Use sys_clk, i_/o_ signal names. Measure throughput (o_valid/i_ready cycles), latency, stall rate on refc/vectors/perf/.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Compile and run performance simulation via Bash CLI: scripts/run_sim.sh --sim verilator --top tb_cabac_encoder_perf --outdir sim/cabac_encoder --trace rtl/cabac_encoder/cabac_encoder.sv sim/cabac_encoder/tb_cabac_encoder_perf.sv.")

Task(subagent_type="rtl-agent-team:waveform-analyzer",
     prompt="Analyze sim/cabac_encoder/cabac_encoder_perf.vcd. Extract throughput (bits/cycle on o_data), average latency (sys_clk cycles from i_valid to o_valid), stall cycles per 1000 cycles on i_ready.")
```
</Tool_Usage>

<Examples>
<Good>
RTL throughput 98 bits/cycle vs BFM 100 bits/cycle (2% delta, PASS);
RTL stall rate 3.2% vs BFM 2.8% (14% delta, FAIL — investigate backpressure on `i_ready`).
Performance counters use `sys_clk` and track `o_valid`/`i_ready` handshakes.
</Good>
<Bad>
Using random test vectors for performance measurement — non-deterministic results make
regression comparison meaningless.
Using `clk_i` or `data_i` in performance counters instead of `clk`/`{domain}_clk` or `i_data` -- breaks consistency with RTL conventions.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Performance deficit >20% vs BFM → escalate to rtl-architect for pipeline analysis
- BFM baseline file missing → run bfm-develop first, halt rtl-p5s-perf-verify
- Performance monitor uses wrong signal names → perf-verifier must fix before re-run
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Performance monitors use correct signal names (`i_`/`o_` prefix, `sys_clk`)
- [ ] Deterministic performance vectors used
- [ ] sim/{module}/*_perf.json written for all modules
- [ ] RTL vs BFM comparison done per metric
- [ ] All deviations >10% flagged with root cause analysis
</Final_Checklist>

<Advanced>
Performance vectors should stress maximum throughput (back-to-back `i_valid` high, no gaps).
Also run a stall-stress vector (frequent `o_ready` deassertion) to expose stall handling bugs.
Use `$time` with `sys_clk` edges for cycle-accurate measurement in SV testbenches.
</Advanced>
