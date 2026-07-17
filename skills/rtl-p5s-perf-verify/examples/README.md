# parse_perf_report.py Worked Example

Demonstrates the deterministic half of the perf-verify contract: raw
simulation counters (from `templates/perf-monitor-template.sv`
`print_summary()`) compared against the BFM baseline into the
`{module}_perf.json` schema of `references/perf-verify-conventions.md`.

| File | Role |
|------|------|
| `cabac_encoder_perf_run.log` | Input: simulation run log containing the perf-monitor summary block. |
| `perf_baseline.json` | Input: BFM baseline (schema per `skills/bfm-develop/references/bfm-conventions.md`). |
| `cabac_encoder_perf.json` | Output: per-metric measured/expected/delta/verdict JSON produced by the command below. |

## Command

Run from this directory:

```sh
python3 ../scripts/parse_perf_report.py \
    --log cabac_encoder_perf_run.log \
    --baseline perf_baseline.json \
    --clock-mhz 200 --bits-per-txn 8 \
    -o cabac_encoder_perf.json
```

Expected report: `Wrote cabac_encoder_perf.json: overall_verdict=PASS`
(exit code 0; a FAIL verdict exits 1, usage/parse errors exit 2).

## Metric arithmetic in this example

- `throughput_mbps`: 3000/10000 output-handshake cycles at 200 MHz with
  8 bits/txn = 480.0 Mbps vs 500.0 expected → delta −4.0% → PASS.
- `latency_cycles`: measured avg 12.0 vs baseline `clock_cycles` 12 →
  0.0% → PASS.
- `stall_cycles_pct`: 840/10000 = 8.4% vs 8.0% expected → +5.0% → PASS.
- Any |delta| > 10% flips the metric (and the overall verdict) to FAIL.

`run_timestamp` differs run-to-run; every other field is deterministic.
The LLM half of the contract (deviation root-cause narrative in
`reviews/phase-5-verify/{module}-performance-report.md`) builds on this JSON.
