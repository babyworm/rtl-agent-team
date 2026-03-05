---
name: codec-conformance-eval
description: "Decoder conformance evaluation against JVET/JCTVC/3rd-party conformance bitstreams. Builds ref C model decoder, runs parallel decoding, and verifies bitexact output match against golden references. Supports profile/level filtering, MD5/bitexact/PSNR comparison, optional SSIM/VMAF, and AWS Batch opt-in."
user-invocable: true
---

<Purpose>
Build and evaluate ref_model C decoder binaries against official conformance bitstreams,
verifying bitexact output match with golden references to ensure decoder algorithmic correctness.

This skill automates the full decoder conformance evaluation pipeline:
1. Build decoder binary from refc/*.c (C11, gcc)
2. Run parallel decoding of conformance bitstreams (JVET, JCTVC, 3rd party)
3. Compare decoded output against golden references (MD5, bitexact, optional PSNR/SSIM/VMAF)
4. Generate conformance report with profile/level coverage matrix

**Scope: Decoder conformance evaluation at the algorithm/C model level.**
- This skill tests the **C reference model decoder** against official conformance streams
- For **RTL-level** conformance testing, use `/rtl-agent-team:rtl-conformance-test` (Phase 5)
- For **encoder RD evaluation**, use `/rtl-agent-team:codec-rd-eval`

**Phase-agnostic**: Commonly used during Phase 1-2 (Research/Architecture) to validate
decoder algorithm correctness before committing to hardware implementation. Can also be
used at any Phase where decoder conformance verification is needed.

| | rtl-conformance-test | codec-conformance-eval |
|---|---|---|
| Target | RTL implementation (.sv) | C ref model decoder |
| Phase | Phase 5 (Verify) | Phase 1-2 (Research/Architecture) |
| Comparison | JM/HM reference output | Official conformance golden output |
| Purpose | RTL-level bitexact verification | Algorithm-level conformance verification |

**Execution modes**:
- **local**: ProcessPoolExecutor-based parallel decoding on local CPU cores
- **aws-batch**: Optional AWS Batch spot instance submission for large stream sets

**Key features**:
- Profile/level filtering for targeted conformance testing
- Multiple conformance sources: JVET/JCTVC (mandatory per standard), 3rd party (optional)
- Configurable comparison: MD5 checksum, bitexact byte comparison, PSNR threshold
- SSIM/VMAF opt-in (only on explicit user request)
- Profile coverage matrix generation
</Purpose>

<Use_When>
- Validating decoder algorithm correctness against official conformance streams
- Verifying that a C ref model decoder passes JVET/JCTVC conformance requirements
- Testing decoder support for specific profiles/levels before hardware implementation
- Evaluating 3rd-party conformance streams for additional coverage
- The user explicitly says "decoder conformance", "conformance stream", "conformance test", "decoder verify", "bitexact decoder"
</Use_When>

<Do_Not_Use_When>
- No ref C model decoder exists yet (build ref model first via `/rtl-agent-team:ref-model`)
- Testing RTL decoder implementation (use `/rtl-agent-team:rtl-conformance-test`, Phase 5)
- Comparing encoder quality (use `/rtl-agent-team:codec-rd-eval`)
- Comparing RTL vs C model output (use `/rtl-agent-team:rtl-model-consistency`)
</Do_Not_Use_When>

<Why_This_Exists>
Decoder conformance is a hard requirement for any video codec implementation. A decoder
that fails official conformance streams has algorithmic bugs that will propagate to hardware.

Catching conformance failures at the C model level (Phase 1-2) is orders of magnitude
cheaper than discovering them after RTL implementation (Phase 5). Official conformance
streams from JVET and JCTVC exercise specific codec features and corner cases that
typical test sequences may not cover.

This skill automates the tedious process of running hundreds of conformance streams,
comparing outputs, and tracking which profile features are covered.
</Why_This_Exists>

<Execution_Policy>
- Requires refc/*.c with decoder functionality (or configured decoder_src)
- HJSON conformance configuration defines all test parameters
- Local execution is the default; AWS Batch is opt-in via configuration
- Conformance results are cached at .rtl-agent-team/scratch/conformance-eval/
- Report is generated at configured path (default: docs/phase-1-research/conformance-eval-report.md)
- On build failure: report error details and stop
- On decoding failure: mark stream as FAIL, continue with remaining streams
- Mandatory streams (JVET, JCTVC) must all PASS for overall conformance PASS
- Optional streams (3rd party) failures are reported but do not affect overall verdict
- SSIM/VMAF are computed ONLY when explicitly requested via quality_metrics config
- timeout_per_job is in seconds (default: 300s = 5 min per decoding job)
- Dependencies: gcc (C11), Python 3.9+, hjson, numpy (optional, for PSNR computation). Optional: ffmpeg (required for SSIM/VMAF computation when quality_metrics includes "ssim" or "vmaf"), boto3 (required only for aws-batch execution mode)
- Self-test: `python3 skills/codec-conformance-eval/scripts/compare_output.py --test` runs built-in unit tests
</Execution_Policy>

<Steps>
1. **Prerequisite validation**
   - Verify refc/*.c (or configured decoder_src) exists with decoder code
   - Verify conformance configuration file exists (HJSON format)
     - If not provided, generate from template at skills/codec-conformance-eval/templates/conformance-config.hjson
   - Verify conformance bitstream directories exist
   - Verify golden output references exist (MD5 checksums or reference YUV files)
   - Check Python dependencies: `python3 -c "import hjson; print('OK')"`
     - Optional: `python3 -c "import numpy; print('numpy OK')"` (needed for PSNR comparison mode)

2. **Decoder build** (build_decoder.sh)
   - `bash skills/codec-conformance-eval/scripts/build_decoder.sh <decoder_src> <decoder_binary> [extra_cflags...]`
   - Build flags: `gcc -std=c11 -O2 -Wall -Wextra -lm` (C11 standard per CLAUDE.md)
   - Optional extra_cflags: e.g., `-DDECODER_ONLY`, `-DMAX_DPB_SIZE=16`
   - On build failure: capture stderr, report to user, STOP

3. **Conformance test execution** (run_conformance.py)
   - Parse HJSON conformance configuration
   - Auto-discover conformance bitstreams from configured source paths
   - Filter by target profile/level (if specified)
   - Execute in configured mode:
     - **local**: `python3 skills/codec-conformance-eval/scripts/run_conformance.py <config.hjson> --mode local`
     - **aws-batch**: `python3 skills/codec-conformance-eval/scripts/run_conformance.py <config.hjson> --mode aws-batch`
   - Each job produces: decoded YUV (or MD5) + decode_time + status
   - Results saved to: `.rtl-agent-team/scratch/conformance-eval/results.json`

4. **Output comparison** (compare_output.py)
   - `python3 skills/codec-conformance-eval/scripts/compare_output.py <results.json> <config.hjson>`
   - Comparison modes:
     a) MD5 checksum (default, fastest)
     b) Bitexact byte comparison (reports first mismatch offset)
     c) PSNR threshold (for approximate matching, e.g., floating-point rounding)
   - Optional: SSIM/VMAF (only when quality_metrics includes them)
   - Profile coverage matrix: which profile features are tested
   - Output: `.rtl-agent-team/scratch/conformance-eval/conformance-metrics.json`

5. **Report generation**
   - Generate report from template at skills/codec-conformance-eval/templates/conformance-report.md
   - Output path: as configured (default: docs/phase-1-research/conformance-eval-report.md)
   - Report contains:
     - Overall conformance verdict (PASS/FAIL)
     - Per-stream PASS/FAIL table with decode time
     - Conformance source breakdown (JVET/JCTVC mandatory, 3rd party optional)
     - Profile/level coverage matrix
     - Failure details (byte offset, pixel divergence) for failed streams
     - SSIM/VMAF metrics (if opt-in enabled)
</Steps>

<Tool_Usage>
```
# ============================================================
# Step 1: Prerequisite validation
# ============================================================
Glob("refc/*.c")                       # Verify decoder source exists
Read("<conformance-config.hjson>")     # Read conformance configuration
Bash("python3 -c 'import hjson; print(\"OK\")'")  # Check dependencies
Bash("ls conformance/")               # Verify conformance bitstream dirs exist
Bash("ls conformance/golden-outputs/") # Verify golden output references exist

# ============================================================
# Step 2: Decoder build
# ============================================================
Bash("bash skills/codec-conformance-eval/scripts/build_decoder.sh refc .rtl-agent-team/scratch/conformance-eval/decoder")

# ============================================================
# Step 3: Conformance test execution (parallel)
# ============================================================
Bash("python3 skills/codec-conformance-eval/scripts/run_conformance.py <config.hjson> --mode local",
     timeout=600000)

# ============================================================
# Step 4: Output comparison
# ============================================================
Bash("python3 skills/codec-conformance-eval/scripts/compare_output.py .rtl-agent-team/scratch/conformance-eval/results.json <config.hjson> --output .rtl-agent-team/scratch/conformance-eval/conformance-metrics.json")

# ============================================================
# Step 5: Report generation
# ============================================================
Read(".rtl-agent-team/scratch/conformance-eval/conformance-metrics.json")
# Write report to configured output path
```
</Tool_Usage>

<Examples>
**Example 1: H.264 Baseline decoder conformance**
```
User: "Run H.264 Baseline profile decoder conformance test"
→ Invoke /rtl-agent-team:codec-conformance-eval
→ Step 1: Verify refc/ exists, generate conformance-config.hjson (target: h264/Baseline)
→ Step 2: Build decoder
→ Step 3: Filter Baseline profile from JVET + JCTVC conformance streams, parallel decoding
→ Step 4: Per-stream MD5 comparison → 42/45 PASS, 3 FAIL
→ Step 5: Generate docs/phase-1-research/conformance-eval-report.md
→ "42 of 45 conformance streams PASS. 3 failures: deblocking filter edge cases. Debugging required."
```

**Example 2: Full HEVC conformance with SSIM**
```
User: "Run H.265 Main profile conformance with SSIM"
→ quality_metrics: ["psnr", "ssim"] configured
→ Execute JVET + JCTVC + Allegro + Elecard conformance streams
→ Mandatory (JVET+JCTVC): 128/128 PASS
→ Optional (3rd party): 45/48 PASS
→ "All mandatory streams PASS. 3 third-party failures (optional). Overall verdict: PASS."
```

**Example 3: No decoder source**
```
User: "Run decoder conformance test"
→ Step 1: No decoder code found in refc/
→ "No ref C model decoder source found. Run /rtl-agent-team:ref-model first to generate the reference model."
```
</Examples>

<Escalation_And_Stop_Conditions>
- refc/ does not exist → suggest running ref-model skill first
- Decoder build fails → report gcc error details, check C11 compliance
- Conformance bitstreams not found → provide download guidance (JVET/JCTVC URLs)
- Golden outputs missing → suggest generating from reference decoder (JM/HM)
- Mandatory stream fails → report failure details, do NOT mark overall as PASS
- High failure rate (>20%) → suggest verifying decoder binary correctness first
- AWS Batch credentials not configured → fall back to local mode
- SSIM/VMAF requested but ffmpeg not available → warn and skip optional metrics
</Escalation_And_Stop_Conditions>

<Final_Checklist>
Before reporting completion, verify ALL of the following:
- [ ] Decoder binary built successfully (exit code 0)
- [ ] All conformance streams executed (success or explicit failure)
- [ ] MD5/bitexact comparison completed for each stream
- [ ] Profile/level coverage matrix generated
- [ ] Overall verdict determined (PASS only if all mandatory streams pass)
- [ ] Report generated at configured output path
- [ ] Raw data preserved at .rtl-agent-team/scratch/conformance-eval/
- [ ] If SSIM/VMAF requested: optional metrics included
- [ ] Failed streams have detailed failure info (byte offset or pixel divergence)

If ANY item is unchecked → DO NOT report completion. Fix the issue first.
</Final_Checklist>
