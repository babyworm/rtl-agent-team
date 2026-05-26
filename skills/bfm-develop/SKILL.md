---
name: bfm-develop
description: This skill should be used when the user asks to "develop BFM", "create SystemC TLM model", "build bus functional model", "implement TLM-2.0 BFM", "model AMBA protocol in SystemC", or when Phase 3 transaction-level models are needed for performance estimation or protocol verification.
user-invocable: true
argument-hint: "[block-name | --all-blocks]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Implement SystemC TLM-2.0 Bus Functional Models for each architectural block using LT (Loosely Timed) blocking transport by default, with ARM AMBA protocol extensions (AXI/AHB/APB/ACE). Outputs: `bfm/src/*.cpp`, `bfm/build/`, `bfm/smoke_test_result.txt`, `bfm/perf_baseline.json`, and `reviews/phase-3-uarch/bfm-feature-coverage.md`.
</Purpose>

<Use_When>
- Phase 2 artifacts (`docs/phase-2-architecture/architecture.md`, `refc/`) are complete.
- TLM models are needed for early performance estimation or protocol verification.
- BFM is needed as stimulus/checker in a verification environment.
- AMBA bus protocol modeling (AXI/AHB/APB) is required.
- DPI-C co-simulation interface is needed for SystemVerilog testbenches.
</Use_When>

<Do_Not_Use_When>
- Architecture is not yet stable — a BFM built on a changing arch spec requires full rewrite.
- Only simple unit tests are needed → use `rtl-p4s-unit-test` directly.
- Pure software development without hardware interaction.
</Do_Not_Use_When>

<Why_This_Exists>
TLM models run orders of magnitude faster than RTL simulation, enabling early detection of protocol bugs and performance bottlenecks before RTL exists. The BFM also serves as the performance reference in `rtl-p5s-perf-verify`. LT transport is the default because it gives fast functional validation; AT non-blocking is reserved for timing-accurate pipelined modeling.
</Why_This_Exists>

## Prerequisites

- `docs/phase-2-architecture/architecture.md` and `io_definition.json` present.
- `refc/` reference model built (needed for cross-phase functional consistency check).
- SystemC 3.0+ and ARM AMBA-PV headers installed.

If missing: WARNING — proceed with available artifacts; note absent dependencies in smoke test result.

<Assets>
| Path | Role |
|------|------|
| `templates/bfm_module_template.h` | SystemC TLM-2.0 scaffold with LT/AT transport, Memory Manager, PEQ, and AXI extension stubs. |
| `scripts/.gitkeep` | (placeholder — deep-fill in follow-up PR) |
| `references/bfm-conventions.md` | Transport-style rules, AMBA protocol guidance, perf_baseline.json schema, anti-patterns. |
| `examples/.gitkeep` | (placeholder — deep-fill in follow-up PR) |
</Assets>

<Responsibility_Boundary>
- **Scripts** handle build (`cmake`/`make`) and smoke-test execution via Bash CLI.
- **LLM** handles TLM module design, protocol binding, and feature-coverage mapping.
- Contract surface: port names must match `io_definition.json` exactly; functional output must match `refc/` on shared test vectors.
</Responsibility_Boundary>

<Execution>
1. Read `architecture.md` and `io_definition.json`; identify AMBA protocol requirements per block.
2. Spawn `bfm-dev` to implement `bfm/src/*.cpp` — one `SC_MODULE` per architectural block, LT by default, AXI with `amba_pv::axi_extension`, Memory Manager, PEQ; AT only if explicitly requested (see Tool_Usage).
3. Build: `mkdir -p bfm/build && cd bfm/build && cmake .. && make` — fix all compile errors.
4. Smoke test: `cd bfm/build && ./smoke_test` — at least one LT transaction end-to-end; write result to `bfm/smoke_test_result.txt`.
5. Functional consistency: run BFM and `refc/` on the same test vectors; verify per-block output matches (bitexact or within documented tolerance); record in `bfm/perf_baseline.json`.
6. Feature coverage: map every `REQ-F-*` from `iron-requirements.json` to a BFM module/method (structural check); save `reviews/phase-3-uarch/bfm-feature-coverage.md`. Escalate unmapped features to the user.
7. If DPI-C co-simulation is required: implement `bfm/dpi/` interface.

Apply steps 1-7 to every requested block — do not stop after the first.
</Execution>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="Implement SystemC TLM-2.0 BFMs in C++ at bfm/src/*.cpp from architecture.md. "
            "Output MUST be C++ (.cpp/.h), NOT SystemVerilog. "
            "LT blocking transport (b_transport) by default. AXI with amba_pv extensions. "
            "Memory Manager (tlm_mm_interface) required. One SC_MODULE per block. "
            "Include CMakeLists.txt. Port names must match io_definition.json exactly "
            "(i_/o_ prefix, {domain}_clk, {domain}_rst_n). AT only if explicitly requested.")

Task(subagent_type="rtl-agent-team:video-processing-expert",
     prompt="Review bfm/src/ datapath models for signal processing accuracy vs requirements.json.")
```
</Tool_Usage>

<Examples>
<example index="1">
<scenario>Five-block AXI pipeline; Phase 2 complete; LT transport requested.</scenario>
<expected_output>Five SC_MODULEs with b_transport and amba_pv::axi_extension; Memory Manager present; smoke test PASS; bfm/perf_baseline.json records per-block latency; all REQ-F-* mapped.</expected_output>
</example>

<example index="2">
<scenario>Out-of-order memory controller; AT timing accuracy explicitly requested.</scenario>
<expected_output>nb_transport_fw/bw with full 4-phase handshake (BEGIN_REQ→END_REQ→BEGIN_RESP→END_RESP); PEQ scheduling correct; smoke test PASS in AT mode.</expected_output>
</example>

<example index="3">
<scenario>BFM functional output diverges from refc/ on vector 23 during consistency check.</scenario>
<expected_output>Divergence recorded in perf_baseline.json with byte offset; bfm-dev fixes rounding in b_transport handler; re-run confirms bitexact match; bfm-feature-coverage.md updated.</expected_output>
</example>
</Examples>

<Escalation_And_Stop_Conditions>
- SystemC not available → halt; instruct user to install SystemC 3.0+ before proceeding.
- AMBA-PV headers not available → halt; instruct user to install ARM AMBA-PV library.
- Smoke test fails after 2 fix iterations → report failure with compile/runtime log; do not declare gate pass.
- AT 4-phase protocol deadlock → check PEQ callbacks for missing phase transitions.
- Feature coverage < 100% and user declines → record ADR with downstream verification impact; proceed only with explicit approval.
</Escalation_And_Stop_Conditions>

## Output

- `bfm/src/*.cpp` — SystemC TLM-2.0 BFM modules (C++17).
- `bfm/smoke_test_result.txt` — smoke test verdict with transport mode and latency.
- `bfm/perf_baseline.json` — per-block throughput and latency baseline.
- `reviews/phase-3-uarch/bfm-feature-coverage.md` — REQ-F-* mapping table.

<Final_Checklist>
- [ ] `bfm/src/*.cpp` compiles without errors (C++17).
- [ ] One `SC_MODULE` per architectural block.
- [ ] LT blocking transport (`b_transport`) used by default.
- [ ] If AT requested: all 4 phases present (BEGIN_REQ, END_REQ, BEGIN_RESP, END_RESP).
- [ ] AMBA protocol extensions set correctly (AXI burst/cache/prot).
- [ ] Memory Manager (`tlm_mm_interface`) used for payload pooling.
- [ ] PEQ (`peq_with_cb_and_phase`) used for phase scheduling.
- [ ] Smoke test passes; `bfm/smoke_test_result.txt` written.
- [ ] BFM per-block output matches `refc/` on shared test vectors (bitexact or documented tolerance).
- [ ] All `REQ-F-*` items mapped; `bfm-feature-coverage.md` saved.
- [ ] Missing features escalated; user-approved omissions have ADR.
- [ ] DPI-C interface provided if SV co-simulation required.
</Final_Checklist>
