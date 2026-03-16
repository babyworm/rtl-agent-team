---
name: codec-rd-eval
description: "Rate-Distortion evaluation automation for codec algorithm comparison. Builds ref C model encoder, runs parallel encoding simulations across multiple sequences and QP points, computes BD-PSNR/BD-rate (VCEG-M33 methodology), and generates comparison reports. Supports N-candidate comparison, configurable encoder CLI, SSIM/VMAF opt-in metrics."
user-invocable: true
---

<Purpose>
Build and evaluate ref_model C encoder binaries across multiple encoding configurations,
computing BD-PSNR and BD-rate metrics (VCEG-M33 methodology) to quantitatively compare
codec algorithm candidates.

This skill automates the full Rate-Distortion evaluation pipeline:
1. Build encoder binaries from refc/*.c (C11, gcc)
2. Run parallel encoding simulations across (sequence, QP, config) combinations
3. Compute BD-PSNR/BD-rate using VCEG-M33 polynomial interpolation (3+ points)
4. Generate comparison reports with per-sequence and aggregate metrics

**Scope: Encoder RD evaluation only.**
This skill evaluates encoder quality metrics (BD-PSNR, BD-rate, optional SSIM/VMAF).
For decoder conformance testing against JVET/JCTVC bitstreams, use `/rtl-agent-team:codec-conformance-eval`.

**Phase-agnostic**: While commonly used during rat-dse Step 3b, this skill can be invoked
at any Phase where quantitative RD comparison of encoder configurations is needed —
Phase 1 (algorithm exploration), Phase 2 (architecture validation), Phase 4 (fixed-point
precision impact), or standalone evaluation outside the pipeline.

**Execution modes**:
- **local**: ProcessPoolExecutor-based parallel encoding on local CPU cores
- **aws-batch**: Optional AWS Batch spot instance submission for large-scale evaluation

**Key features**:
- **N-candidate comparison**: Compare 2+ configurations via candidates[] array (anchor + N tests)
- **Configurable encoder CLI**: encoder_cmd_template supports any encoder (HM, VTM, custom). Available variables: `{encoder}`, `{cfg}`, `{input}`, `{width}`, `{height}`, `{fps}`, `{frames}`, `{qp}`, `{bitstream}`, `{recon}`, `{bit_depth}`, `{chroma_format}`
- **Configurable output parsing**: Custom regex patterns for bitrate/PSNR extraction
- **SSIM/VMAF opt-in**: Additional quality metrics on explicit user request only
- **bit_depth/chroma_format aware**: YUV weighting adjusts per chroma format (420/422/444)
- **3+ QP point support**: Standard 4-point (exact fit), 5+ (least-squares), 3 (quadratic fallback)
</Purpose>

<Use_When>
- Comparing algorithm candidates with objective quality metrics (any Phase)
- Measuring BD-PSNR/BD-rate between anchor and modified encoder configurations
- Evaluating fixed-point precision impact on codec quality (e.g., 12-bit vs 16-bit paths)
- Validating that HW-friendly algorithm modifications preserve acceptable quality
- N-way comparison of multiple encoder configurations (candidates[] mode)
- The user explicitly says "RD eval", "BD-PSNR", "BD-rate", "codec quality", "algorithm quality evaluation"
</Use_When>

<Do_Not_Use_When>
- No ref C model encoder exists yet (build ref model first via ref-model skill)
- Comparing RTL vs C model output (use `/rtl-agent-team:rtl-model-consistency` instead)
- Running decoder conformance tests against standard bitstreams (use `/rtl-agent-team:codec-conformance-eval`)
- Running RTL-level conformance against reference decoder (use `/rtl-agent-team:rtl-conformance-test`)
- Non-codec designs where RD metrics don't apply
</Do_Not_Use_When>

<Why_This_Exists>
In codec design, algorithm selection has the highest impact on final quality and area.
Theoretical complexity analysis (operations/pixel, gate estimates) provides useful guidance
but cannot capture the full picture — actual RD performance on representative sequences
is the definitive metric.

BD-PSNR/BD-rate (VCEG-M33) is the universally accepted method in the video coding community
for comparing codec configurations. It normalizes across different operating points (QP values)
to produce a single, meaningful comparison metric.

Without this skill, teams either skip quantitative RD evaluation (risking suboptimal algorithm
selection) or manually set up evaluation infrastructure (time-consuming and error-prone).
</Why_This_Exists>

<Execution_Policy>
- Requires refc/*.c to exist (or user-specified encoder source path)
- HJSON test configuration defines all evaluation parameters
- Local execution is the default; AWS Batch is opt-in via configuration
- Simulation results are cached at .rtl-agent-team/scratch/rd-eval/ for re-analysis
- Report is generated at the path specified in test configuration (default: docs/phase-1-research/rd-eval-report.md)
- On build failure: report error details and stop (do not proceed with stale binaries)
- On simulation failure: report failed jobs, compute BD metrics from successful jobs with warnings
- On metric parsing failure (bitrate=0 or PSNR=0): mark job as failed with guidance to check output_parsing
- timeout_per_job is in seconds (default: 3600s = 1 hour per encoding job)
- SSIM/VMAF are computed ONLY when explicitly requested via quality_metrics config
- Dependencies: gcc (C11), Python 3.9+, numpy, hjson. Optional: ffmpeg (required for SSIM/VMAF computation when quality_metrics includes "ssim" or "vmaf"), boto3 (required only for aws-batch execution mode)
- Self-test: `python3 skills/codec-rd-eval/scripts/bd_rate.py --test` runs built-in unit tests
</Execution_Policy>

<Steps>
1. **Prerequisite validation**
   - Verify refc/*.c (or configured encoder_src) exists
   - Verify test configuration file exists (HJSON format)
     - If not provided, generate from template at skills/codec-rd-eval/templates/test-config.hjson
     - Ask user to fill in sequence paths and encoder configurations
   - Check anchor encoder binary existence (skip build if already built)
   - Verify Python dependencies: `python3 -c "import numpy; import hjson"`
     - If missing, report: `pip install numpy hjson`

2. **Encoder build** (build_encoder.sh)
   - For each unique encoder_src in configurations (anchor/test or candidates[]):
     `bash skills/codec-rd-eval/scripts/build_encoder.sh <src> <binary> [extra_cflags]`
   - Build flags: `gcc -std=c11 -O2 -Wall -Wextra -lm` (C11 standard per CLAUDE.md)
   - On build failure: capture stderr, report to user, STOP

3. **Simulation execution** (run_eval.py)
   - Parse HJSON test configuration
   - Generate job matrix: (sequence x QP x config) combinations
   - Execute in configured mode:
     - **local**: `python3 skills/codec-rd-eval/scripts/run_eval.py <config.hjson> --mode local`
     - **aws-batch**: `python3 skills/codec-rd-eval/scripts/run_eval.py <config.hjson> --mode aws-batch`
   - Each job produces: bitrate_kbps, psnr_y/u/v/yuv (dB), encode_time_s
   - Optional: SSIM, VMAF (when quality_metrics includes them)
   - Results saved to: `.rtl-agent-team/scratch/rd-eval/results.json`

4. **BD-PSNR/BD-rate calculation** (bd_rate.py)
   - `python3 skills/codec-rd-eval/scripts/bd_rate.py .rtl-agent-team/scratch/rd-eval/results.json --output .rtl-agent-team/scratch/rd-eval/bd-metrics.json`
   - VCEG-M33 algorithm with N-point support:
     1. Transform rates to log10 domain
     2. Fit polynomial (degree = min(3, N-1)) — exact interpolation for 4 points, least-squares fitting for 5+
     3. Integrate over common PSNR range
     4. BD-rate (%) and BD-PSNR (dB)
   - N-candidate mode: compute metrics for each test vs anchor
   - Per-sequence results + aggregate average + encoding time summary
   - Output: `.rtl-agent-team/scratch/rd-eval/bd-metrics.json`

5. **Report generation**
   - Generate report from template at skills/codec-rd-eval/templates/rd-eval-report.md
   - Output path: as configured in HJSON (default: docs/phase-1-research/rd-eval-report.md)
   - Report contains:
     - Evaluation summary (anchor label, test label, date)
     - Per-sequence RD data table (QP, bitrate, PSNR, encode time)
     - Per-sequence BD-PSNR and BD-rate
     - Aggregate BD-PSNR and BD-rate
     - Encoding time comparison table
     - SSIM/VMAF tables (if opt-in metrics enabled)
     - N-candidate comparison matrix (if candidates[] mode)
     - Interpretation guidance
   - If invoked from rat-dse: feed BD metrics back to algorithm comparison matrix
</Steps>

<Tool_Usage>
```
# ============================================================
# Step 1: Prerequisite validation
# ============================================================
Glob("refc/*.c")                       # Verify encoder source exists
Read("<test-config.hjson>")            # Read test configuration
Bash("python3 -c 'import numpy; import hjson; print(\"OK\")'")  # Check dependencies

# ============================================================
# Step 2: Encoder build (for each unique encoder_src)
# ============================================================
Bash("bash skills/codec-rd-eval/scripts/build_encoder.sh refc .rtl-agent-team/scratch/rd-eval/anchor_encoder")
Bash("bash skills/codec-rd-eval/scripts/build_encoder.sh refc .rtl-agent-team/scratch/rd-eval/test_encoder")

# ============================================================
# Step 3: Simulation execution (parallel)
# ============================================================
Bash("python3 skills/codec-rd-eval/scripts/run_eval.py <config.hjson> --mode local",
     timeout=600000)  # Up to 10 min for large evaluations

# ============================================================
# Step 4: BD metric calculation
# ============================================================
Bash("python3 skills/codec-rd-eval/scripts/bd_rate.py .rtl-agent-team/scratch/rd-eval/results.json --output .rtl-agent-team/scratch/rd-eval/bd-metrics.json")

# ============================================================
# Step 5: Report generation
# ============================================================
# Read bd-metrics.json and generate markdown report
Read(".rtl-agent-team/scratch/rd-eval/bd-metrics.json")
# Write report to configured output path
```
</Tool_Usage>

<Examples>
**Example 1: Algorithm comparison during DSE**
```
User: "Compare RD performance of 3 H.264 intra prediction algorithm candidates"
→ Invoke /rtl-agent-team:codec-rd-eval
→ Step 1: Verify refc/ exists, generate test-config.hjson (candidates[] mode)
→ Step 2: Build 3 encoders: SAD, Hadamard, SATD+RDOQ
→ Step 3: Simulate BasketballDrill, BQTerrace, RaceHorses × QP{22,27,32,37}
→ Step 4: vs SAD(anchor): Hadamard BD-rate=-3.2%, SATD+RDOQ BD-rate=-5.1%
→ Step 5: Generate docs/phase-1-research/rd-eval-report.md (with N-candidate matrix)
→ "SATD+RDOQ achieves best BD-rate -5.1% over SAD. Hadamard gives -3.2%."
```

**Example 2: Fixed-point precision evaluation with SSIM**
```
User: "Measure quality difference between 12-bit vs 16-bit internal paths including SSIM"
→ quality_metrics: ["psnr", "ssim"] configured
→ anchor: 16-bit internal path encoder
→ test: 12-bit internal path encoder
→ BD-PSNR = -0.02 dB, BD-rate = +0.5%, SSIM delta = -0.0001
→ "12-bit path shows BD-rate +0.5% vs 16-bit, negligible SSIM difference (-0.0001). Recommend 12-bit considering gate count savings."
```

**Example 3: No encoder source available**
```
User: "Run BD-rate comparison"
→ Step 1: refc/*.c not found
→ "No ref C model encoder source found. Run /rtl-agent-team:ref-model first to generate the reference model."
```
</Examples>

<Escalation_And_Stop_Conditions>
- refc/ does not exist → suggest running ref-model skill first
- Encoder build fails → report gcc error details, check C11 compliance
- Test sequences not found at configured paths → ask user for correct paths
- All simulations fail → check encoder binary, report common error pattern
- Metric parsing returns 0 → suggest configuring output_parsing patterns in HJSON
- BD-rate shows unexpected large degradation (>20%) → warn user, suggest verifying encoder correctness
- AWS Batch credentials not configured → fall back to local mode with warning
- numpy/hjson not installed → provide pip install command
- SSIM/VMAF requested but ffmpeg not available → warn and skip optional metrics
</Escalation_And_Stop_Conditions>

<Final_Checklist>
Before reporting completion, verify ALL of the following:
- [ ] Encoder binary built successfully (exit code 0)
- [ ] All (or majority of) simulation jobs completed successfully
- [ ] No parsing failures (bitrate=0 or PSNR=0 on successful encodes)
- [ ] BD-PSNR and BD-rate calculated for each sequence
- [ ] Aggregate BD metrics computed
- [ ] Encoding time comparison included in report
- [ ] Report generated at configured output path
- [ ] Raw data preserved at .rtl-agent-team/scratch/rd-eval/
- [ ] If N-candidate mode: comparison matrix generated
- [ ] If SSIM/VMAF requested: optional metrics included
- [ ] If invoked from rat-dse: BD metrics available for algorithm comparison matrix

If ANY item is unchecked → DO NOT report completion. Fix the issue first.
</Final_Checklist>
