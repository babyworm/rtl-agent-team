---
name: rtl-model-consistency
description: This skill should be used when the user asks to "check model consistency", "3-way comparison", "verify ref model vs BFM vs RTL", "detect model drift", "cross-model comparison", or when bitexact consistency between the C reference model, SystemC BFM, and RTL simulation must be confirmed on shared test vectors.
user-invocable: true
argument-hint: "[--vectors path/to/test_vectors.bin | --generate N]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Run a 3-way bitexact comparison between the C reference model (`refc/`), SystemC BFM (`bfm/`), and RTL simulation on a shared test vector set. Outputs: `sim/consistency/consistency_report.md` with a per-vector comparison matrix and diagnosis identifying which model diverges.
</Purpose>

<Use_When>
- All three models exist (`refc/`, `bfm/`, `rtl/`) and need consistency validation.
- Checking for drift between models after independent updates.
- A pre-regression gate is needed to confirm baseline consistency.
- A discrepancy between two models requires the third to arbitrate.
</Use_When>

<Do_Not_Use_When>
- Only two models exist → use `rtl-p5s-func-verify` (RTL vs ref) or `rtl-p5s-perf-verify` (RTL vs BFM).
- Models are known to be out of sync — fix the diverging model first, then re-run.
- Only functional RTL verification is needed → use `rtl-p5s-func-verify`.
</Do_Not_Use_When>

<Why_This_Exists>
When ref model, BFM, and RTL are developed independently, silent divergence accumulates. 3-way comparison isolates which model is wrong: `ref == BFM != RTL` means RTL has a bug; `ref != BFM == RTL` means the ref model diverged; `ref == RTL != BFM` means BFM has an issue. Two-model comparisons cannot make this determination.
</Why_This_Exists>

## Prerequisites

- `refc/build/ref_model` built and executable.
- `bfm/build/bfm_smoke` built and executable.
- RTL files present under `rtl/` with simulation infrastructure (iverilog or cocotb).
- Test vectors at `sim/consistency/test_vectors.bin` (or will be generated — minimum 10 vectors).

If any model binary is missing: WARNING — run that model's build skill first; proceed with 2-way comparison and note the absent model in the report.

<Assets>
| Path | Role |
|------|------|
| `scripts/compare_3way.py` | Pairwise binary diff of ref/BFM/RTL outputs; emits per-vector PASS/FAIL matrix and first-divergence byte. |
| `templates/consistency-report.md` | Report scaffold with summary table, diagnosis section, and mismatch details table. |
| `references/model-consistency-conventions.md` | Comparison criteria, diagnosis logic table, vector-count guidance, anti-patterns. |
| `examples/.gitkeep` | (placeholder — deep-fill in follow-up PR) |
</Assets>

<Responsibility_Boundary>
- **Scripts** (`compare_3way.py`) handle deterministic pairwise binary comparison and first-divergence extraction.
- **LLM** handles diagnosis (which model is the likely source of error), report narrative, and escalation decisions.
- Contract surface: all three models must run on identical input vectors; bitexact is the default criterion unless tolerance is documented.
</Responsibility_Boundary>

<Execution>
1. Select shared test vector set: use `sim/consistency/test_vectors.bin` if present; otherwise generate a minimum 10-vector set.
2. Run all three models in parallel on identical input (see Tool_Usage):
   - `ref-model-dev`: `./refc/build/ref_model < sim/consistency/test_vectors.bin > sim/consistency/ref_output.bin`
   - `bfm-dev`: `./bfm/build/bfm_smoke < sim/consistency/test_vectors.bin > sim/consistency/bfm_output.bin`
   - `func-verifier`: simulate RTL with vectors (iverilog/cocotb), capture to `sim/consistency/rtl_output.bin`
3. Run `python3 skills/rtl-model-consistency/scripts/compare_3way.py sim/consistency/` — produces pairwise PASS/FAIL matrix and first-divergence bytes.
4. Write `sim/consistency/consistency_report.md` using `templates/consistency-report.md`: summary table, diagnosis (see conventions for logic), mismatch details with byte offset + expected/actual values.
5. Report overall consistency status to the user.

Apply steps 1-5 to every vector set requested — do not stop after the first run.
</Execution>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Run refc/build/ref_model on sim/consistency/test_vectors.bin via Bash CLI. "
            "Capture output to sim/consistency/ref_output.bin. Build first if needed: make -C refc/.")

Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="Run bfm/build/bfm_smoke on sim/consistency/test_vectors.bin via Bash CLI. "
            "Capture output to sim/consistency/bfm_output.bin. Build first if needed: make -C bfm/.")

Task(subagent_type="rtl-agent-team:func-verifier",
     prompt="Simulate RTL with sim/consistency/test_vectors.bin as input via Bash CLI (iverilog/cocotb). "
            "RTL ports use i_/o_ prefixes, clocks are {domain}_clk, resets are {domain}_rst_n. "
            "Capture output to sim/consistency/rtl_output.bin.")
```
</Tool_Usage>

<Examples>
<example index="1">
<scenario>All three models built; 50 shared vectors; post-BFM-update consistency gate.</scenario>
<expected_output>ref == BFM on 50/50; RTL diverges on vector 23; consistency_report.md diagnoses RTL as outlier; first divergence at byte 142; diagnosis: CABAC encoder rounding difference.</expected_output>
</example>

<example index="2">
<scenario>Ref model updated after spec change; BFM and RTL not yet updated.</scenario>
<expected_output>ref != BFM == RTL; consistency_report.md diagnoses ref model diverged; mismatch details list first-divergence byte per vector; user informed to update BFM and RTL.</expected_output>
</example>

<example index="3">
<scenario>BFM binary missing; only ref and RTL available.</scenario>
<expected_output>WARNING in report noting BFM absent; 2-way ref vs RTL comparison run; consistency_report.md documents reduced scope; user advised to run bfm-develop before full 3-way check.</expected_output>
</example>
</Examples>

<Escalation_And_Stop_Conditions>
- Three-way mismatch (`ref != BFM != RTL`) → report all divergences; cannot auto-diagnose; escalate to user.
- Any model binary not built → note in report; run 2-way comparison with available models.
- Test vector set missing → generate minimal 10-vector set before proceeding; note generation in report.
</Escalation_And_Stop_Conditions>

## Output

- `sim/consistency/consistency_report.md` — 3-way comparison matrix with per-vector PASS/FAIL, first-divergence details, and diagnosis.

<Final_Checklist>
- [ ] All three models run on identical input vectors.
- [ ] Pairwise comparison completed for all three pairs (ref/BFM, ref/RTL, BFM/RTL).
- [ ] `sim/consistency/consistency_report.md` written with summary table and diagnosis.
- [ ] Diverging model identified where possible.
- [ ] First-divergence byte offset and expected/actual values reported for each mismatch.
- [ ] Absent model binaries noted in report with recommendation to build.
</Final_Checklist>
