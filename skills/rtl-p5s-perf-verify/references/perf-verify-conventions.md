# Performance Verification Conventions

A quick reference for `rtl-p5s-perf-verify`. Stays under 150 lines so it can be consulted in one read.

## 1. Naming & output structure

| Element | Convention | Example |
|---------|-----------|---------|
| Raw metrics JSON | `sim/{module}/{module}_perf.json` | `sim/cabac_encoder/cabac_encoder_perf.json` |
| Performance report | `reviews/phase-5-verify/{module}-performance-report.md` | |
| BFM baseline | `bfm/perf_baseline.json` | |
| Measurement harness | Based on `templates/perf-monitor-template.sv` | |
| Deviation threshold | 10% — flag as FAIL if measured deviates > 10% from BFM baseline | |
| Port prefix | `i_/o_/io_` per project convention | see `.claude/rules/rtl-coding-conventions.md` |
| Clock naming | `{domain}_clk` | `sys_clk`, `pixel_clk` |

## 2. Output schema

### sim/{module}/{module}_perf.json

```json
{
  "module": "{module_name}",
  "run_timestamp": "ISO-8601",
  "metrics": {
    "throughput_mbps":  { "measured": 0.0, "expected": 0.0, "delta_pct": 0.0, "verdict": "PASS|FAIL" },
    "latency_cycles":   { "measured": 0,   "expected": 0,   "delta_pct": 0.0, "verdict": "PASS|FAIL" },
    "stall_cycles_pct": { "measured": 0.0, "expected": 0.0, "delta_pct": 0.0, "verdict": "PASS|FAIL" }
  },
  "overall_verdict": "PASS|FAIL",
  "notes": ""
}
```

All three metric categories must be present. If a metric cannot be measured (e.g., no
backpressure path exists), set `measured` and `expected` to `null` and `verdict` to `"N/A"`.

### reviews/phase-5-verify/{module}-performance-report.md structure

```markdown
# Performance Verification Report — {module}

## Summary
Overall verdict: PASS | FAIL

## Metrics vs BFM Baseline
| Metric | Measured | Expected (BFM) | Delta % | Verdict |
|--------|----------|----------------|---------|---------|
| Throughput (Mbps) | ... | ... | ... | ... |
| Latency (cycles) | ... | ... | ... | ... |
| Stall cycles (%) | ... | ... | ... | ... |

## Deviation Analysis
{Explain any FAIL metric: which pipeline stage contributes the stall/latency excess.}

## Recommendation
{PASS: proceed to rtl-p6-design-review. FAIL: list RTL locations to investigate.}
```

## 3. Length guidance

- Performance report: 30–60 lines. Deviation Analysis section: 3–8 lines per failing metric.
- Recommendation section: 2–5 lines.
- JSON: one entry per measured metric. Do not add extra commentary fields — use `notes` for
  any free-form text.

## 4. Anti-patterns

- Do not declare PASS if any metric exceeds the 10% deviation threshold.
- Do not fabricate BFM baseline values — read from `bfm/perf_baseline.json`; if the file
  is missing, emit WARNING and stop per prerequisites guidance.
- Do not run performance measurement before functional verification passes — performance
  numbers from a functionally incorrect RTL are meaningless.
- Do not include synthesis timing slack in this report — timing analysis belongs in
  `rtl-synth-check`. This skill measures RTL simulation throughput/latency only.
- Do not average over multiple runs without reporting the run count and variance.
- Surface known measurement limitations (e.g., simulation speed not matching post-synthesis
  behaviour) in the `notes` field rather than omitting them.
