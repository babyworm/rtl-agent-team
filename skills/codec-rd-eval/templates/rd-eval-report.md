# Rate-Distortion Evaluation Report

- **Date**: {{date}}
- **Anchor**: {{anchor_label}}
- **Test**: {{test_label}}
- **Methodology**: VCEG-M33 (Bjontegaard Delta)
- **QP Points**: {{qp_points}}
- **Quality Metrics**: {{quality_metrics}}

## Summary

<!-- JSON source: bd-metrics.json → aggregate (single comparison) or comparisons[0].aggregate -->

| Metric | Value | Interpretation |
|--------|-------|----------------|
| **Avg BD-rate (Y)** | {{aggregate.avg_bd_rate_y}}% | Negative = test uses fewer bits at same quality |
| **Avg BD-PSNR (Y)** | {{aggregate.avg_bd_psnr_y}} dB | Positive = test has better quality at same bitrate |
| **Avg BD-rate (YUV)** | {{aggregate.avg_bd_rate_yuv}}% | Combined luma+chroma metric |
| **Avg BD-PSNR (YUV)** | {{aggregate.avg_bd_psnr_yuv}} dB | Combined luma+chroma metric |

## Per-Sequence Results

### BD Metrics

<!-- JSON source: bd-metrics.json → sequences (dict keyed by sequence name) -->

| Sequence | BD-rate Y (%) | BD-PSNR Y (dB) | BD-rate YUV (%) | BD-PSNR YUV (dB) |
|----------|---------------|-----------------|-----------------|-------------------|
{{#each sequences}}
| {{@key}} | {{bd_rate_y}} | {{bd_psnr_y}} | {{bd_rate_yuv}} | {{bd_psnr_yuv}} |
{{/each}}
| **Average** | **{{aggregate.avg_bd_rate_y}}** | **{{aggregate.avg_bd_psnr_y}}** | **{{aggregate.avg_bd_rate_yuv}}** | **{{aggregate.avg_bd_psnr_yuv}}** |

### RD Data per Config

<!--
  JSON source: results.json (from run_eval.py)
  Fields per entry: sequence, qp, config_label, bitrate_kbps, psnr_y, psnr_yuv, encode_time_s, is_anchor, status

  Agent instructions:
  - Group results by config_label (field name in results.json)
  - Note: "label" is the HJSON config field name, "config_label" is the results.json field name.
    They refer to the same value. Template uses {{label}} when iterating over HJSON config entries,
    and config_label when referencing results.json data.
  - For 2-config mode: show Anchor table then Test table
  - For N-candidate mode: show one table per config_label
  - Filter to status="success" entries only
-->

{{#each config_labels}}
#### {{label}} {{#if is_anchor}}(Anchor){{/if}}

| Sequence | QP | Bitrate (kbps) | PSNR-Y (dB) | PSNR-YUV (dB) | Encode Time (s) |
|----------|----|----------------|-------------|----------------|-----------------|
{{#each results}}
| {{sequence}} | {{qp}} | {{bitrate_kbps}} | {{psnr_y}} | {{psnr_yuv}} | {{encode_time_s}} |
{{/each}}
{{/each}}

## Encoding Time Comparison

<!-- JSON source: bd-metrics.json → aggregate.avg_anchor_encode_time_s / avg_test_encode_time_s / computed_speedup
     Note: computed_speedup is only present when both anchor and test have non-zero encode times.
     For N-candidate mode: one row per test candidate. -->

| Config | Avg Encode Time (s) | Speedup vs Anchor |
|--------|---------------------|-------------------|
| {{anchor_label}} (Anchor) | {{aggregate.avg_anchor_encode_time_s}} | 1.00x |
<!-- comparisons_or_single: Agent-constructed variable (not from bd-metrics.json).
     For 2-config mode: single-element array wrapping the bd-metrics.json root object.
     For N-candidate mode: bd-metrics.json "comparisons" array (one entry per test candidate). -->
{{#each comparisons_or_single}}
| {{test_label}} | {{aggregate.avg_test_encode_time_s}} | {{#if aggregate.computed_speedup}}{{aggregate.computed_speedup}}x{{else}}N/A{{/if}} |
{{/each}}

{{#if ssim_enabled}}
<!-- Condition: ssim_enabled = "ssim" in quality_metrics (from HJSON config) -->
## SSIM Comparison (opt-in)

<!-- JSON source: bd-metrics.json → sequences[].anchor_avg_ssim / test_avg_ssim / ssim_delta -->

| Sequence | Anchor Avg SSIM | Test Avg SSIM | Delta |
|----------|-----------------|---------------|-------|
{{#each sequences}}
| {{@key}} | {{anchor_avg_ssim}} | {{test_avg_ssim}} | {{ssim_delta}} |
{{/each}}
{{/if}}

{{#if vmaf_enabled}}
<!-- Condition: vmaf_enabled = "vmaf" in quality_metrics (from HJSON config) -->
## VMAF Comparison (opt-in)

| Sequence | Anchor Avg VMAF | Test Avg VMAF | Delta |
|----------|-----------------|---------------|-------|
{{#each sequences}}
| {{@key}} | {{anchor_avg_vmaf}} | {{test_avg_vmaf}} | {{vmaf_delta}} |
{{/each}}
{{/if}}

{{#if n_candidate}}
<!-- Condition: n_candidate = "comparisons" key exists in bd-metrics.json (N-config mode with 3+ candidates) -->
## N-Candidate Comparison Matrix

<!-- JSON source: bd-metrics.json → comparisons[] array -->

BD-rate Y (%) vs Anchor ({{anchor_label}}):

| Candidate | Avg BD-rate Y (%) | Avg BD-PSNR Y (dB) | Avg Encode Time (s) |
|-----------|-------------------|---------------------|---------------------|
{{#each comparisons}}
| {{test_label}} | {{aggregate.avg_bd_rate_y}} | {{aggregate.avg_bd_psnr_y}} | {{aggregate.avg_test_encode_time_s}} |
{{/each}}
{{/if}}

## Interpretation Guide

- **BD-rate**: Measures the average bitrate difference (%) between two encoders at the same PSNR.
  - Negative BD-rate → test encoder is **more efficient** (fewer bits for same quality)
  - Positive BD-rate → test encoder is **less efficient** (more bits for same quality)
  - Industry significance: -1% to -3% is a meaningful improvement in mature codecs

- **BD-PSNR**: Measures the average PSNR difference (dB) between two encoders at the same bitrate.
  - Positive BD-PSNR → test encoder produces **better quality** at same bitrate
  - Negative BD-PSNR → test encoder produces **worse quality** at same bitrate

- **Methodology**: VCEG-M33 fits 3rd-order polynomials through RD points in the log-rate
  domain, then computes the integral difference over the common range.
  Standard uses 4 QP points. 3-point (quadratic fallback) and 5+ point (least-squares) are supported.

- **YUV Weighting**: 4:2:0 uses 6:1:1, 4:2:2 uses 4:1:1, 4:4:4 uses 1:1:1 (equal).

## Configuration

<!--
  JSON source: Agent reads HJSON config directly for this section.
  bd-metrics.json only has anchor_label/test_label — not full encoder_src/cfg.

  For 2-config mode: show anchor + test.
  For N-candidate mode: list all candidates with is_anchor flag.
-->

```
{{#each config_labels}}
{{label}}{{#if is_anchor}} (Anchor){{/if}}:
  Source: {{encoder_src}}
  Config: {{encoder_cfg}}
{{/each}}

Sequences: {{aggregate.num_sequences}}
QP points: {{qp_points}}
Execution: {{execution_mode}}
Quality metrics: {{quality_metrics}}
```

---
*Generated by codec-rd-eval skill (rtl-agent-team)*
