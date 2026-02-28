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

### RD Data — Anchor ({{anchor_label}})

<!-- JSON source: results.json (from run_eval.py). Agent must split by is_anchor=true → anchor_results[], is_anchor=false → test_results[]. Each entry has: sequence, qp, bitrate_kbps, psnr_y, psnr_yuv, encode_time_s -->

| Sequence | QP | Bitrate (kbps) | PSNR-Y (dB) | PSNR-YUV (dB) | Encode Time (s) |
|----------|----|----------------|-------------|----------------|-----------------|
{{#each anchor_results}}
| {{sequence}} | {{qp}} | {{bitrate_kbps}} | {{psnr_y}} | {{psnr_yuv}} | {{encode_time_s}} |
{{/each}}

### RD Data — Test ({{test_label}})

| Sequence | QP | Bitrate (kbps) | PSNR-Y (dB) | PSNR-YUV (dB) | Encode Time (s) |
|----------|----|----------------|-------------|----------------|-----------------|
{{#each test_results}}
| {{sequence}} | {{qp}} | {{bitrate_kbps}} | {{psnr_y}} | {{psnr_yuv}} | {{encode_time_s}} |
{{/each}}

## Encoding Time Comparison

<!-- JSON source: bd-metrics.json → aggregate.avg_anchor_encode_time_s / avg_test_encode_time_s -->

| Config | Avg Encode Time (s) | Speedup vs Anchor |
|--------|---------------------|-------------------|
| {{anchor_label}} (Anchor) | {{aggregate.avg_anchor_encode_time_s}} | 1.00x |
| {{test_label}} (Test) | {{aggregate.avg_test_encode_time_s}} | {{aggregate.computed_speedup}}x |

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

<!-- JSON source: Original HJSON config (anchor/test/candidates blocks). Agent must read the HJSON config directly — bd-metrics.json does not include config passthrough. -->

```
Anchor: {{anchor_label}}
  Source: {{anchor.encoder_src}}
  Config: {{anchor.encoder_cfg}}

Test: {{test_label}}
  Source: {{test.encoder_src}}
  Config: {{test.encoder_cfg}}

Sequences: {{aggregate.num_sequences}}
QP points: {{qp_points}}
Execution: {{execution.mode}}
Quality metrics: {{quality_metrics}}
```

---
*Generated by codec-rd-eval skill (rtl-agent-team)*
