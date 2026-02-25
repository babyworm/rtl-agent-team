---
name: ref-model
description: "This skill should be used when building C++ reference models with bitexact verification against standard reference implementations."
---

<Purpose>
Build a golden reference model in C++ that exactly matches the target codec standard.
Outputs: ref_model/src/*.cpp, conformance_report.json.
Must achieve bitexact match against JM (H.264) or HM (H.265) reference software.
Runs in parallel with arch-design during Phase 2.
</Purpose>

<Use_When>
- Phase 1 artifacts are complete and reference model does not exist
- Reference model needs update after spec change
- Conformance baseline is needed for RTL verification
</Use_When>

<Do_Not_Use_When>
- Reference model already exists and conformance_report.json is current
- Only a quick algorithm question (use domain-consult instead)
</Do_Not_Use_When>

<Why_This_Exists>
RTL verification requires a golden reference. Writing the reference model before RTL
forces algorithm understanding and exposes spec ambiguities before silicon commitment.
Bitexact match against JM/HM is the industry standard acceptance criterion.
</Why_This_Exists>

<Execution_Policy>
- codec-standards-expert provides algorithm specification details
- ref-model-dev implements C++ model
- Run JM/HM bitexact comparison as automated gate
- Gate fails if any test vector mismatches
</Execution_Policy>

<Steps>
1. codec-standards-expert provides algorithm pseudocode and edge case table
2. ref-model-dev implements ref_model/src/*.cpp with clean C++ (no RTL bias)
   - C++ function/variable names for I/O interfaces should align with io_definition.json port names
     (e.g., use `i_data`, `o_result` naming in API to match RTL port conventions)
   - This ensures BFM and cocotb testbenches can reuse the same signal names
3. Build ref model via Bash CLI: `cd ref_model/build && cmake .. && make`
4. Run bitexact comparison via Bash CLI: `cd ref_model/build && ./run_conformance --vectors=test_vectors/`
5. Fix any mismatches (iterate until all vectors pass)
6. Write conformance_report.json with pass/fail per vector and JM/HM version
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:codec-standards-expert",
     prompt="Provide algorithm pseudocode and edge case table for CABAC entropy coding per H.264 spec section 9.3.")

Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Implement C++ reference model at ref_model/src/ based on algorithm pseudocode. Must be bitexact vs JM. Use io_definition.json port naming in C++ API (i_/o_ prefix convention) for testbench compatibility.")

# Build and test via Bash CLI (NOT MCP)
Bash: cd ref_model/build && cmake .. && make
Bash: cd ref_model/build && ./run_conformance --vectors=test_vectors/ 2>&1
Bash: cd ref_model/build && ./ref_model --sanitize  # run with -fsanitize=address,undefined
```
</Tool_Usage>

<Examples>
<Good>
ref-model-dev implements CABAC coder; bitexact test runs 500 vectors against JM 19.0; all pass; conformance_report.json written.
</Good>
<Bad>
Implementing ref model with RTL-style fixed-point arithmetic — introduces numerical bias
that breaks bitexact match and corrupts the verification baseline.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Bitexact mismatch persists after 3 fix iterations → report failing vectors to user with diff
- JM/HM not available in environment → halt and instruct user to install
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] ref_model/src/*.cpp compiles cleanly
- [ ] All test vectors pass bitexact comparison vs JM/HM
- [ ] conformance_report.json written with JM/HM version and vector results
</Final_Checklist>

<Advanced>
Use JM 19.0 for H.264, HM 16.20 for H.265. Test vector set: ITU-T conformance streams.
Reference model must be free of undefined behavior (run with -fsanitize=address,undefined).
</Advanced>
