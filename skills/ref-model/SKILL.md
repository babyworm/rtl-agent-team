---
name: ref-model
description: This skill should be used when the user asks to "build a reference model", "create C ref model", "write golden model", "implement functional reference", "bitexact reference for RTL verification", or when a Phase 2 C functional reference model is needed for algorithm validation or bandwidth analysis.
user-invocable: true
argument-hint: "[algorithm-name | --update]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Build a golden C functional reference model (Phase 2) that validates algorithm correctness and estimates external memory bandwidth. Outputs: `refc/*.c`, `refc/include/*.h`, `conformance_report.json`, `bandwidth_report.json`, and `reviews/phase-2-architecture/ref-model-feature-coverage.md`.
</Purpose>

<Use_When>
- Phase 1 artifacts are complete and a reference model does not yet exist.
- Reference model needs updating after a spec change.
- A conformance baseline is needed before RTL verification can begin.
- Bandwidth or datapath-width exploration is required.
- An independent quality gate is needed before declaring the model a verification oracle.
</Use_When>

<Do_Not_Use_When>
- Reference model already exists and `conformance_report.json` is current — avoid regenerating.
- Only a quick algorithm question is needed → use `domain-consult` instead.
</Do_Not_Use_When>

<Why_This_Exists>
Writing the reference model before RTL forces algorithm understanding and exposes spec ambiguities before silicon commitment. Bitexact match against JM/HM is the industry-standard acceptance criterion. The model doubles as a bandwidth analysis tool by routing all external memory traffic through `ext_mem_read`/`ext_mem_write`, enabling memory-bandwidth estimation without RTL.
</Why_This_Exists>

## Prerequisites

- `docs/phase-1-research/iron-requirements.json` present with `REQ-F-*` items.
- JM 19.0 (H.264) or HM 16.20 (H.265) installed and on `PATH`.

If missing: WARNING — proceed with available artifacts; feature coverage step will note absent requirements file.

<Assets>
| Path | Role |
|------|------|
| `templates/Makefile` | Build + test + bandwidth targets (`build`, `test`, `bandwidth`, `sanitize`). |
| `templates/ref_model_main.c` | Scaffold with `ext_mem_read/write` stubs and `PARALLEL_LANES` define. |
| `templates/ref_model_header.h` | Struct typedefs: `input_t`, `output_t`, `context_t`, `ext_mem_stats_t`. |
| `templates/dpi_wrapper.h` | DPI-C export declarations for SV testbench linkage. |
| `scripts/.gitkeep` | (placeholder — deep-fill in follow-up PR) |
| `references/ref-model-conventions.md` | C11/DPI-C rules, output schemas, anti-patterns. |
| `examples/.gitkeep` | (placeholder — deep-fill in follow-up PR) |
</Assets>

<Responsibility_Boundary>
- **Scripts** handle build, bitexact comparison, and bandwidth measurement via `Makefile` targets.
- **LLM** handles algorithm implementation, feature-coverage mapping, and spec-gap escalation.
- Contract surface: `ext_mem_read/write` abstraction layer + `REQ-F-*` coverage table.
</Responsibility_Boundary>

<Execution>
1. Spawn domain expert for algorithm pseudocode and edge-case table (see Tool_Usage).
2. Spawn `ref-model-dev` to implement `refc/*.c` — pure C11, no clock/reset, I/O as function args, internal state as arrays/struct members, external memory via `ext_mem_read/write`, `PARALLEL_LANES` parameterizable, no C++ features.
3. Build: `cd refc && make build` (must compile with `-Wall -Wextra -Werror`).
4. Test: `cd refc && make test` — bitexact comparison against JM/HM; fix mismatches and iterate.
5. Bandwidth: `cd refc && make bandwidth` — captures `ext_mem_stats_t`; write `bandwidth_report.json`.
6. Feature coverage: read `iron-requirements.json`, map every `REQ-F-*` to a real code path (structural check — not just bitexact coverage); save `reviews/phase-2-architecture/ref-model-feature-coverage.md`. Escalate any unmapped feature to the user before proceeding.
7. Spawn `ref-model-reviewer` for algorithm fidelity, numeric precision, and UB/memory-safety review.
8. Write `conformance_report.json` with JM/HM version and per-vector pass/fail.
9. Sanitize: `cd refc && make sanitize` (`-fsanitize=address,undefined`) — must pass clean.

Apply steps 1-9 to every algorithm unit requested — do not stop after the first.
</Execution>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:vcodec-syntax-entropy-expert",
     prompt="Provide algorithm pseudocode and edge case table for CABAC entropy coding per H.264 spec §9.3.")

Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Implement C functional reference model at refc/. Must be bitexact vs JM. "
            "No clock/reset — pure functional. I/O as function args. Internal memory as arrays/struct. "
            "External memory via ext_mem_read/write. PARALLEL_LANES parameterizable. "
            "C11, DPI-C compatible (no C++ features). Use templates/ scaffolding.")

Task(subagent_type="rtl-agent-team:ref-model-reviewer",
     prompt="Review refc/ model quality. Check algorithm fidelity, fixed-point/bit-width correctness, "
            "build warnings, UB risks, and I/O format compatibility. "
            "Save report to reviews/phase-2-architecture/ref-model-review.md with PASS/FAIL verdict.")
```
</Tool_Usage>

<Examples>
<example index="1">
<scenario>New CABAC entropy coder; Phase 1 complete; JM 19.0 available.</scenario>
<expected_output>refc/cabac_encoder.c compiled clean; 500 ITU-T vectors pass bitexact vs JM 19.0; bandwidth_report.json shows 2.3 MB/frame reads; all REQ-F-* mapped; ref-model-reviewer issues PASS.</expected_output>
</example>

<example index="2">
<scenario>Spec change adds intra 8×8 prediction; existing ref model misses REQ-F-042.</scenario>
<expected_output>ref-model-dev adds intra_predict_8x8(); feature-coverage.md updated; re-run confirms bitexact match; conformance_report.json refreshed.</expected_output>
</example>

<example index="3">
<scenario>Datapath width exploration: choose between PARALLEL_LANES=4 and PARALLEL_LANES=8.</scenario>
<expected_output>bandwidth_report.json generated for both configs; estimated_read_cycles compared; architect selects PARALLEL_LANES=4 based on memory bandwidth budget.</expected_output>
</example>
</Examples>

<Escalation_And_Stop_Conditions>
- Bitexact mismatch persists after 3 fix iterations → report failing vectors with diff to user.
- JM/HM not available → halt; instruct user to install before proceeding.
- Feature coverage < 100% and user declines to implement missing feature → record ADR with impact estimate; proceed only with explicit approval.
- External memory bandwidth exceeds technology limits → escalate to arch-designer for block restructuring.
</Escalation_And_Stop_Conditions>

## Output

- `refc/*.c`, `refc/include/*.h` — C11 functional reference model.
- `conformance_report.json` — per-vector bitexact results with JM/HM version.
- `bandwidth_report.json` — external memory access statistics per block.
- `reviews/phase-2-architecture/ref-model-feature-coverage.md` — REQ-F-* mapping table.
- `reviews/phase-2-architecture/ref-model-review.md` — reviewer verdict.

<Final_Checklist>
- [ ] `refc/*.c` compiles with `gcc -std=c11 -Wall -Wextra -Werror`.
- [ ] No C++ features — DPI-C compatible pure C.
- [ ] No clock/reset — pure functional model.
- [ ] External memory uses `ext_mem_read`/`ext_mem_write` abstraction.
- [ ] `PARALLEL_LANES` parameterizable.
- [ ] All test vectors pass bitexact comparison vs JM/HM.
- [ ] `make sanitize` passes clean (`-fsanitize=address,undefined`).
- [ ] All `REQ-F-*` items mapped to code paths; `ref-model-feature-coverage.md` saved.
- [ ] Missing features escalated; user-approved omissions have ADR.
- [ ] `ref-model-reviewer` report saved with PASS verdict.
- [ ] `conformance_report.json` and `bandwidth_report.json` written.
</Final_Checklist>
