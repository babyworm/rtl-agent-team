---
name: rtl-conformance-test
description: "Final codec standards compliance gate: bitexact RTL bitstream check against JM/HM reference. Triggers: 'conformance test', 'H.264/H.265 conformance'."
user-invocable: true
argument-hint: "[--standard H.264|H.265] [--vectors path/to/vectors/]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Verify that RTL-encoded or decoded bitstreams match JM (H.264) or HM (H.265) reference output with 100% bitexact accuracy. This is the final standards compliance gate before tape-out sign-off. Outputs: `sim/conformance/results.json` with per-vector PASS/FAIL and divergence details.
</Purpose>

<Use_When>
- RTL passes functional verification and standards compliance must be confirmed.
- Codec standard version has changed and re-conformance is required.
- A specific ITU-T JVT conformance suite must be run against the RTL.
</Use_When>

<Do_Not_Use_When>
- `conformance_report.json` from `ref-model` does not exist — run `ref-model` first.
- Non-codec RTL design — this skill is specific to video codec standards compliance.
</Do_Not_Use_When>

<Why_This_Exists>
Standards compliance cannot be inferred from internal functional verification. JM/HM produce the normative reference bitstreams, and bitexact match is the only accepted evidence of conformance for codec IP submitted to standards bodies or licensees.
</Why_This_Exists>

## Prerequisites

- `conformance_report.json` (from `ref-model`) present — ref model gate must pass first.
- JM 19.0 (H.264) or HM 16.20 (H.265) installed and on `PATH`.
- RTL passes `rtl-p5s-func-verify` (functional verification complete).
- Conformance test vectors present at `sim/conformance/vectors/`.

If missing: WARNING — halt and instruct user to resolve the missing prerequisite before proceeding.

<Assets>
| Path | Role |
|------|------|
| `scripts/conformance_compare.py` | Bitexact binary comparison; emits per-vector PASS/FAIL with divergence byte offset, expected/actual hex. |
| `templates/golden-metadata.json` | Stream metadata schema: standard, profile, level, JM/HM version, width, height, frame count. |
| `references/conformance-test-conventions.md` | Naming rules, results.json schema, bitexact criteria, block-level decoder guidance, anti-patterns. |
| `examples/.gitkeep` | (placeholder — deep-fill in follow-up PR) |
</Assets>

<Responsibility_Boundary>
- **Scripts** (`conformance_compare.py`) handle deterministic byte-level bitstream comparison.
- **LLM** handles test vector selection, simulation orchestration, failure diagnosis, and spec-section attribution.
- Contract surface: 100% bitexact match required; any divergence is a hard FAIL with byte offset + hex values recorded.
</Responsibility_Boundary>

<Execution>
1. Spawn `vcodec-syntax-entropy-expert` to select the applicable conformance test vectors (JVT suite or project-specific) for the target standard and profile/level.
2. Spawn `video-processing-expert` to validate vector coverage against requirements.
3. Spawn `eda-runner` to simulate each vector via Bash CLI; capture RTL output bitstream per vector. Testbench must use `i_`/`o_` port prefixes and `{domain}_clk`/`{domain}_rst_n` naming.
4. For each vector, run `python3 {plugin_root}/skills/rtl-conformance-test/scripts/conformance_compare.py rtl_output.bin ref_output.bin` (`{plugin_root}` = plugin root resolved from `.rat/state/spawn-context.json`) (or `cmp -l`); record PASS/FAIL with divergence byte, expected/actual hex on FAIL.
5. Spawn `func-verifier` to validate `sim/conformance/results.json` completeness — all vectors present, all have status, FAILs have byte offsets.
6. Write `sim/conformance/results.json` with JM/HM version, standard, profile/level, and per-vector entries.
7. For decoder designs, also run block-level conformance at each pipeline stage (CABAC, inverse TQ, prediction, reconstruction, deblocking, SAO) using C reference model output as oracle.

Apply steps 1-7 to every requested vector suite — do not stop after the first.
</Execution>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:vcodec-syntax-entropy-expert",
     prompt="Select H.264 conformance test vectors applicable to CABAC encoder. "
            "List vector files and JM version to use.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run RTL conformance simulation via Bash CLI for each vector in "
            "sim/conformance/vectors/. Compile and run: "
            "scripts/run_sim.sh --sim iverilog --top tb_cabac_conformance "
            "--outdir sim/conformance --trace rtl/cabac_encoder/cabac_encoder.sv "
            "sim/top/tb_cabac_conformance.sv. "
            "Compare output with JM 19.0: "
            "cmp -l sim/conformance/rtl_output.bin sim/conformance/ref/jm_output.bin. "
            "Report PASS/FAIL per vector with divergence byte offset.")

Task(subagent_type="rtl-agent-team:func-verifier",
     prompt="Validate sim/conformance/results.json: verify all vectors ran, all have status, "
            "every FAIL has divergence_byte and expected_hex/actual_hex fields.")
```
</Tool_Usage>

<Examples>
<example index="1">
<scenario>500 ITU-T H.264 vectors; CABAC encoder RTL; JM 19.0 reference.</scenario>
<expected_output>498 PASS; 2 FAIL at byte offset 1024 (spec §9.3.4.6); vcodec-syntax-entropy-expert identifies CABAC flush bug; RTL fix applied; re-run: all 500 PASS; results.json updated.</expected_output>
</example>

<example index="2">
<scenario>H.265 codec with both encoder and decoder paths; HM 16.20 available.</scenario>
<expected_output>Encoder conformance (RTL→JM decode) and decoder conformance (HM encode→RTL) both run; results.json records HM 16.20 version; 100% bitexact achieved on both paths.</expected_output>
</example>

<example index="3">
<scenario>12 of 500 vectors fail — likely systemic issue.</scenario>
<expected_output>Escalation to ref-model review triggered (>10 failures threshold); root cause traced to ref model feature gap rather than isolated RTL bug; ref-model updated; conformance re-run after ref-model gate passes.</expected_output>
</example>
</Examples>

<Escalation_And_Stop_Conditions>
- JM/HM not available → halt; instruct user to install before proceeding.
- `>10 vectors fail` → likely systemic issue; escalate to `ref-model` for model review before RTL debug.
- Single vector fails repeatedly after fix attempts → escalate to the relevant sub-domain expert (vcodec-syntax-entropy, vcodec-prediction, vcodec-transform-quant, or vcodec-filter-recon) for spec interpretation.
- Testbench uses suffix naming convention (`data_i`, `clk_i`) → fix naming before running conformance.
</Escalation_And_Stop_Conditions>

## Output

- `sim/conformance/results.json` — per-vector PASS/FAIL with JM/HM version, profile/level, and divergence details on failures.

<Final_Checklist>
- [ ] `conformance_report.json` from `ref-model` confirmed present before starting.
- [ ] All conformance testbenches use correct naming (`i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n`).
- [ ] All ITU-T conformance vectors run.
- [ ] 100% bitexact match achieved.
- [ ] `sim/conformance/results.json` written with per-vector status, JM/HM version, and profile/level.
- [ ] Every FAIL entry records `divergence_byte`, `expected_hex`, `actual_hex`.
- [ ] Decoder block-level conformance run if design includes a decoder path.
</Final_Checklist>
