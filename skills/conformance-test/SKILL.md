---
name: conformance-test
description: Standards conformance testing. RTL vs JM/HM bitexact comparison. Video codec specific.
---

<Purpose>
Verify that RTL-encoded bitstreams are bitexact matches against JM (H.264) or HM (H.265) reference decoder output.
This is the final standards compliance gate before tape-out sign-off.
</Purpose>

<Use_When>
- RTL passes functional verification and standards compliance must be confirmed
- Codec standard version has changed and re-conformance is required
- A specific compliance test suite (e.g., ITU-T JVT conformance) must be run
</Use_When>

<Do_Not_Use_When>
- Reference model conformance_report.json does not exist (run ref-model first)
- Non-codec RTL design (not applicable)
</Do_Not_Use_When>

<Why_This_Exists>
Standards compliance cannot be inferred from internal verification. JM/HM produce the normative
reference bitstreams. Bitexact match is the only accepted evidence of conformance for codec IP.
</Why_This_Exists>

<Coding_Convention_Requirements>
Conformance testbenches and simulation wrappers MUST follow project conventions (CLAUDE.md):
- Port connections: `i_` prefix for inputs, `o_` prefix for outputs (e.g., `i_pixel_data`, `o_bitstream`)
- Clock: `{domain}_clk` (e.g., `sys_clk`, `pixel_clk`) — NOT `clk`, `clk_i`
- Reset: `{domain}_rst_n` (e.g., `sys_rst_n`) — NOT `rst_ni`
- DUT instance: `u_dut` or `u_` prefix
- Use `logic` only (NOT `reg`/`wire`)
</Coding_Convention_Requirements>

<Execution_Policy>
- codec-standards-expert selects the applicable conformance test suite
- video-processing-expert validates test vector applicability
- eda-runner runs RTL simulation via Bash CLI and captures output bitstream
- Comparison done via Bash CLI: `cmp -l rtl_output.bin jm_output.bin`
- Any mismatch is a hard FAIL (no tolerance)
</Execution_Policy>

<Steps>
1. codec-standards-expert selects conformance test vectors (JVT suite or project-specific)
2. video-processing-expert validates vector coverage against requirements
3. eda-runner runs RTL simulation on each vector via Bash CLI, captures encoded bitstream
   - Simulation uses correct `i_`/`o_` port naming and `sys_clk`/`sys_rst_n`
4. Compare RTL bitstream vs JM/HM output via Bash CLI: `cmp -l rtl_output.bin jm_output.bin`
5. Record PASS/FAIL per vector in conformance/results.json
6. Any FAIL: capture divergence byte offset, attach to result entry
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:codec-standards-expert",
     prompt="Select H.264 conformance test vectors applicable to CABAC encoder. List vector files and JM version to use.")

Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run RTL conformance simulation via Bash CLI for each vector in conformance/vectors/*.yuv. Compile: iverilog -g2012 -o sim/conformance/cabac_sim rtl/src/cabac_encoder.sv tb/conformance/tb_cabac_conformance.sv. Compare output bitstreams with JM 19.0 reference: cmp -l sim/conformance/rtl_output.bin conformance/ref/jm_output.bin. Report PASS/FAIL per vector.")

Task(subagent_type="rtl-agent-team:func-verifier",
     prompt="Validate conformance/results.json: verify all vectors ran, all have status, any FAIL has byte offset and divergence details.")
```
</Tool_Usage>

<Examples>
<Good>
500 conformance vectors; RTL simulation uses `sys_clk` and `i_pixel_data`/`o_bitstream` correctly;
498 PASS; 2 FAIL at byte offset 1024 (CABAC flush sequence);
codec-standards-expert identifies spec section 9.3.4.6; RTL fix applied; re-run all 500 PASS.
</Good>
<Bad>
Accepting 99% bitexact match — codec standards require 100% bitexact; partial match means non-conformant.
Using `clk` or `data_i` in conformance testbench — violates project conventions and may cause binding errors.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- JM/HM not available → halt, instruct user to install (provide download URL)
- >10 vectors fail → likely systemic issue; escalate to ref-model for model review before RTL debug
- Single vector fails repeatedly after fix attempts → report to codec-standards-expert for spec interpretation
- Testbench naming convention violation → must fix before running conformance
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All conformance testbenches use correct naming (`i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n`)
- [ ] All ITU-T conformance vectors run
- [ ] 100% bitexact match achieved
- [ ] conformance/results.json written with per-vector status
- [ ] JM/HM version recorded in results
</Final_Checklist>

<Advanced>
Run both encoder conformance (RTL encodes, JM decodes) and decoder conformance (JM encodes, RTL decodes) if design includes both paths.
Conformance vectors can be parallelized: each vector runs in independent simulation via Bash CLI.
</Advanced>
