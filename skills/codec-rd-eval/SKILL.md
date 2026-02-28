---
name: codec-rd-eval
description: "Rate-Distortion evaluation automation for codec algorithm comparison. Builds ref C model encoder, runs parallel encoding simulations across multiple sequences and QP points, computes BD-PSNR/BD-rate (VCEG-M33 methodology), and generates comparison reports. Integrates with rtl-dse Step 3b for quantitative algorithm evaluation."
---

<Purpose>
Build and evaluate ref_model C encoder binaries across multiple encoding configurations,
computing BD-PSNR and BD-rate metrics (VCEG-M33 methodology) to quantitatively compare
codec algorithm candidates.

This skill automates the full Rate-Distortion evaluation pipeline:
1. Build encoder binaries from ref_model/src/*.c (C11, gcc)
2. Run parallel encoding simulations across (sequence, QP, config) combinations
3. Compute BD-PSNR/BD-rate using VCEG-M33 4-point cubic polynomial interpolation
4. Generate comparison reports with per-sequence and aggregate metrics

**Primary use case**: Quantitative algorithm comparison during rtl-dse Step 3b.
Instead of relying solely on theoretical complexity analysis, this skill provides
objective quality metrics (BD-PSNR, BD-rate) measured on standard test sequences.

**Execution modes**:
- **local**: ProcessPoolExecutor-based parallel encoding on local CPU cores
- **aws-batch**: Optional AWS Batch spot instance submission for large-scale evaluation

**Integration with rtl-dse**:
When invoked from rtl-dse Step 3b, results feed directly into the algorithm comparison
matrix, adding measured RD performance alongside theoretical gate count and complexity estimates.
</Purpose>

<Use_When>
- Comparing algorithm candidates during DSE (rtl-dse Step 3b) with objective quality metrics
- Measuring BD-PSNR/BD-rate between anchor and modified encoder configurations
- Evaluating fixed-point precision impact on codec quality (e.g., 12-bit vs 16-bit paths)
- Validating that HW-friendly algorithm modifications preserve acceptable quality
- The user explicitly says "RD eval", "BD-PSNR", "BD-rate", "codec quality evaluation"
</Use_When>

<Do_Not_Use_When>
- No ref C model encoder exists yet (build ref model first via ref-model skill)
- Comparing RTL vs C model output (use model-consistency skill instead)
- Running conformance tests against standard bitstreams (use conformance-test skill)
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
- Requires ref_model/src/*.c to exist (or user-specified encoder source path)
- HJSON test configuration defines all evaluation parameters
- Local execution is the default; AWS Batch is opt-in via configuration
- Simulation results are cached at .rtl-agent-team/scratch/rd-eval/ for re-analysis
- Report is generated at the path specified in test configuration (default: docs/phase-1-research/rd-eval-report.md)
- On build failure: report error details and stop (do not proceed with stale binaries)
- On simulation failure: report failed jobs, compute BD metrics from successful jobs with warnings
- Dependencies: gcc (C11), Python 3.8+, numpy, hjson
</Execution_Policy>

<Steps>
1. **Prerequisite validation**
   - Verify ref_model/src/*.c (or configured encoder_src) exists
   - Verify test configuration file exists (HJSON format)
     - If not provided, generate from template at skills/codec-rd-eval/templates/test-config.hjson
     - Ask user to fill in sequence paths and encoder configurations
   - Check anchor encoder binary existence (skip build if already built)
   - Verify Python dependencies: `python3 -c "import numpy; import hjson"`
     - If missing, report: `pip install numpy hjson`

2. **Encoder build** (build_encoder.sh)
   - Build anchor encoder: `bash skills/codec-rd-eval/scripts/build_encoder.sh <anchor_src> <anchor_binary>`
   - Build test encoder: `bash skills/codec-rd-eval/scripts/build_encoder.sh <test_src> <test_binary>`
     - If anchor and test use the same source with different configs, build once
   - Build flags: `gcc -std=c11 -O2 -Wall -lm` (C11 standard per CLAUDE.md)
   - On build failure: capture stderr, report to user, STOP

3. **Simulation execution** (run_eval.py)
   - Parse HJSON test configuration
   - Generate job matrix: (sequence × QP × config) combinations
   - Execute in configured mode:
     - **local**: `python3 skills/codec-rd-eval/scripts/run_eval.py <config.hjson> --mode local`
     - **aws-batch**: `python3 skills/codec-rd-eval/scripts/run_eval.py <config.hjson> --mode aws-batch`
   - Each job produces: bitrate (kbps), PSNR-Y (dB), PSNR-U (dB), PSNR-V (dB), PSNR-YUV (dB)
   - Results saved to: `.rtl-agent-team/scratch/rd-eval/results.json`
   - Progress reporting: log completed/total jobs

4. **BD-PSNR/BD-rate calculation** (bd_rate.py)
   - `python3 skills/codec-rd-eval/scripts/bd_rate.py .rtl-agent-team/scratch/rd-eval/results.json`
   - VCEG-M33 algorithm:
     1. Transform rates to log10 domain
     2. Fit 3rd-order polynomials (PSNR as function of log-rate) for anchor and test
     3. Integrate over common PSNR range
     4. BD-rate (%) = (10^(area_diff / psnr_range) - 1) × 100
     5. BD-PSNR (dB) = area_diff_reverse / rate_range
   - Per-sequence results + weighted average (optional resolution-based weighting)
   - Output: `.rtl-agent-team/scratch/rd-eval/bd-metrics.json`

5. **Report generation**
   - Generate report from template at skills/codec-rd-eval/templates/rd-eval-report.md
   - Output path: as configured in HJSON (default: docs/phase-1-research/rd-eval-report.md)
   - Report contains:
     - Evaluation summary (anchor label, test label, date)
     - Per-sequence RD data table (QP, bitrate, PSNR)
     - Per-sequence BD-PSNR and BD-rate
     - Aggregate BD-PSNR and BD-rate (average and weighted)
     - Interpretation guidance (negative BD-rate = improvement)
   - If invoked from rtl-dse: feed BD metrics back to algorithm comparison matrix
</Steps>

<Tool_Usage>
```
# ============================================================
# Step 1: Prerequisite validation
# ============================================================
Glob("ref_model/src/*.c")              # Verify encoder source exists
Read("<test-config.hjson>")            # Read test configuration
Bash("python3 -c 'import numpy; import hjson; print(\"OK\")'")  # Check dependencies

# ============================================================
# Step 2: Encoder build
# ============================================================
Bash("bash skills/codec-rd-eval/scripts/build_encoder.sh ref_model/src .rtl-agent-team/scratch/rd-eval/anchor_encoder")
Bash("bash skills/codec-rd-eval/scripts/build_encoder.sh ref_model/src .rtl-agent-team/scratch/rd-eval/test_encoder")

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
User: "H.264 인트라 예측 알고리즘 후보 3개의 실제 RD 성능을 비교해줘"
→ Invoke /rtl-agent-team:codec-rd-eval
→ Step 1: ref_model/src/ 존재 확인, test-config.hjson 생성
→ Step 2: anchor (SAD-based) + test (Hadamard-based) 인코더 빌드
→ Step 3: BasketballDrill, BQTerrace, RaceHorses × QP{22,27,32,37} 시뮬레이션
→ Step 4: BD-PSNR = +0.15 dB, BD-rate = -3.2% (Hadamard가 개선)
→ Step 5: docs/phase-1-research/rd-eval-report.md 생성
→ "Hadamard 기반 모드 결정이 SAD 대비 BD-rate -3.2% 개선 (동일 품질에서 3.2% 비트레이트 절감)"
```

**Example 2: Fixed-point precision evaluation**
```
User: "12비트 vs 16비트 내부 경로의 품질 차이를 측정해줘"
→ anchor: 16-bit internal path encoder
→ test: 12-bit internal path encoder
→ BD-PSNR = -0.02 dB, BD-rate = +0.5%
→ "12비트 경로는 16비트 대비 BD-rate +0.5% (미미한 열화). 게이트 절감 효과 고려 시 12비트 채택 권장."
```

**Example 3: No encoder source available**
```
User: "BD-rate 비교 해줘"
→ Step 1: ref_model/src/*.c 미존재
→ "ref C model 인코더 소스가 없습니다. 먼저 /rtl-agent-team:ref-model로 레퍼런스 모델을 생성하세요."
```
</Examples>

<Escalation>
- ref_model/src/ does not exist → suggest running ref-model skill first
- Encoder build fails → report gcc error details, check C11 compliance
- Test sequences not found at configured paths → ask user for correct paths
- All simulations fail → check encoder binary, report common error pattern
- BD-rate shows unexpected large degradation (>20%) → warn user, suggest verifying encoder correctness
- AWS Batch credentials not configured → fall back to local mode with warning
- numpy/hjson not installed → provide pip install command
</Escalation>

<Final_Checklist>
Before reporting completion, verify ALL of the following:
- [ ] Encoder binary built successfully (exit code 0)
- [ ] All (or majority of) simulation jobs completed successfully
- [ ] BD-PSNR and BD-rate calculated for each sequence
- [ ] Aggregate BD metrics computed
- [ ] Report generated at configured output path
- [ ] Raw data preserved at .rtl-agent-team/scratch/rd-eval/
- [ ] If invoked from rtl-dse: BD metrics available for algorithm comparison matrix

If ANY item is unchecked → DO NOT report completion. Fix the issue first.
</Final_Checklist>
