---
name: rtl-model-consistency
description: "This skill should be used when performing 3-way consistency checks between C reference model, BFM, and RTL simulation outputs."
user-invocable: true
---

<Purpose>
Verify that all three models of the design — reference C model, SystemC TLM BFM, and RTL —
produce bitexact identical outputs on a shared test vector set.
Outputs: sim/consistency/consistency_report.md with per-vector comparison matrix.
</Purpose>

<Use_When>
- All three models exist (refc/, bfm/, rtl/)
- Checking for drift between models after independent updates
- Pre-regression gate to ensure baseline consistency
- Debugging discrepancy between two models (need third to arbitrate)
</Use_When>

<Do_Not_Use_When>
- Only two models exist (use rtl-p5s-func-verify for RTL vs ref, or rtl-p5s-perf-verify for RTL vs BFM)
- Models are known to be out of sync (fix the diverging model first)
- Only functional verification of RTL needed (use rtl-p5s-func-verify)
</Do_Not_Use_When>

<Why_This_Exists>
When ref model, BFM, and RTL are developed independently, silent divergence accumulates.
3-way comparison isolates which model is wrong: if ref == BFM != RTL, RTL has a bug;
if ref != BFM == RTL, ref model diverged; if ref == RTL != BFM, BFM has an issue.
</Why_This_Exists>

<Execution_Policy>
- Use `skills/rtl-model-consistency/scripts/compare_3way.py` for automated pairwise comparison
- Use `skills/rtl-model-consistency/templates/consistency-report.md` as report scaffold
- ref-model-dev runs reference C model on shared test vectors
- bfm-dev runs BFM on same vectors
- func-verifier runs RTL on same vectors
- All three run in parallel, then outputs compared
- Report identifies which pairs match and which diverge
</Execution_Policy>

<Steps>
1. Select shared test vector set (use sim/consistency/test_vectors.bin or generate 50 vectors)
2. Run all three models in parallel on identical input via Bash CLI:
   a. ref-model-dev: `./refc/build/ref_model < sim/consistency/test_vectors.bin > sim/consistency/ref_output.bin`
   b. bfm-dev: `./bfm/build/bfm_smoke < sim/consistency/test_vectors.bin > sim/consistency/bfm_output.bin`
   c. func-verifier: simulate RTL with vectors using iverilog/cocotb, capture output to sim/consistency/rtl_output.bin
      - RTL ports use project convention: i_/o_ prefixes, {domain}_clk, {domain}_rst_n
3. Compare outputs pairwise via Bash CLI (diff, cmp, or Python script):
   ref==BFM? ref==RTL? BFM==RTL?
4. Write sim/consistency/consistency_report.md:
   - Per-vector comparison matrix (PASS/FAIL per pair)
   - First divergence for each mismatch (byte offset, value expected vs actual)
   - Diagnosis: which model is the likely source of error
5. Report overall consistency status to user
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Run refc/build/ref_model on sim/consistency/test_vectors.bin via Bash CLI. Capture output to sim/consistency/ref_output.bin. Build first if needed: make -C refc/.")

Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="Run bfm/build/bfm_smoke on sim/consistency/test_vectors.bin via Bash CLI. Capture output to sim/consistency/bfm_output.bin. Build first if needed: make -C bfm/.")

Task(subagent_type="rtl-agent-team:func-verifier",
     prompt="Simulate RTL with sim/consistency/test_vectors.bin as input via Bash CLI (iverilog/cocotb). RTL ports use i_/o_ prefixes, clocks are {domain}_clk, resets are {domain}_rst_n. Capture output to sim/consistency/rtl_output.bin.")
```
</Tool_Usage>

<Examples>
<Good>
All 3 models run on 50 vectors; ref==BFM on 50/50; RTL diverges on vector 23;
consistency report shows RTL is the outlier; first divergence at byte 142;
diagnosis: RTL CABAC encoder has rounding difference vs ref and BFM.
</Good>
<Bad>
Running only ref vs RTL and declaring consistency — misses BFM drift that would
cause rtl-p5s-perf-verify to produce wrong baseline comparisons.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- ref != BFM != RTL (three-way mismatch) → report all divergences, cannot auto-diagnose
- Any model binary not built → halt for that model, note in report, run 2-way comparison
- Vector set missing → generate minimal 10-vector set before proceeding
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All three models run on identical input vectors
- [ ] Pairwise comparison done for all three pairs
- [ ] sim/consistency/consistency_report.md written with comparison matrix
- [ ] Diverging model identified where possible
- [ ] First divergence byte offset reported for each mismatch
</Final_Checklist>
