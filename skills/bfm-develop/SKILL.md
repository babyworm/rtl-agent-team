---
name: bfm-develop
description: "This skill should be used when developing SystemC TLM Bus Functional Models with AT non-blocking transport and AMBA protocol support from architecture block specifications."
user-invocable: true
---

<Purpose>
Implement SystemC TLM 2.0 BFMs that model the RTL design at transaction level using LT (Loosely
Timed) blocking transport by default, with ARM AMBA protocol extensions (AXI/AHB/APB/ACE).
Switch to AT (Approximately Timed) non-blocking transport only when explicitly requested for
timing accuracy. Outputs: bfm/ directory with SystemC models, build scripts, and initial smoke test results.
Runs in parallel with rtl-p3-uarch-design during Phase 3.
</Purpose>

<Use_When>
- Phase 2 artifacts (architecture.md, refc/) are complete
- TLM models are needed for early performance estimation or protocol verification
- BFM needed as stimulus/checker in verification environment
- AMBA bus protocol modeling required (AXI/AHB/APB)
- DPI-C co-simulation interface needed for SystemVerilog testbenches
</Use_When>

<Do_Not_Use_When>
- Architecture is not yet stable (BFM will need full rewrite)
- Only simple unit tests needed (use rtl-p4s-unit-test directly)
- Pure software development without hardware interaction
</Do_Not_Use_When>

<Why_This_Exists>
TLM models run orders of magnitude faster than RTL simulation.
Early BFM catches protocol bugs and performance bottlenecks before RTL exists.
BFM also serves as the performance reference in rtl-p5s-perf-verify phase.
Use `skills/bfm-develop/templates/bfm_module_template.h` as SystemC TLM-2.0 AT scaffold.
AT non-blocking transport accurately models pipelined and out-of-order behavior
that LT blocking transport cannot capture.
</Why_This_Exists>

<Execution_Policy>
- bfm-dev implements SystemC TLM models using LT blocking transport by default
- Switch to AT non-blocking transport only when explicitly requested for timing accuracy
- AMBA protocol selection: AXI by default, AHB/APB/ACE per architecture spec
- Memory Manager (tlm_mm_interface) required for payload pooling
- PEQ (peq_with_cb_and_phase) required for AT phase scheduling
- video-processing-expert ensures datapath model accuracy
- Smoke test (compile + run one LT transaction) required before gate passes
- BFM per-block functional output must match Phase 2 C reference model (refc/) — bitexact or within documented tolerance. Both models must be fed the same test vectors for valid comparison (Cross-Phase Artifact Functional Consistency principle)
</Execution_Policy>

<Steps>
1. Read architecture.md, io_definition.json, and identify AMBA protocol requirements
2. bfm-dev implements bfm/src/*.cpp: one TLM module per architectural block
   - **LT blocking** (b_transport) as default transport style
   - **AT non-blocking** (nb_transport_fw/bw) only when explicitly requested for timing accuracy
   - **AXI protocol** with amba_pv::axi_extension as default (unless AHB/APB/ACE specified)
   - **Memory Manager** (tlm_mm_interface) for payload pooling
   - **PEQ** (peq_with_cb_and_phase) for AT phase scheduling
   - BFM interface names must match io_definition.json port names exactly
   - Port naming follows project conventions: `i_`/`o_`/`io_` prefix, `clk`/`{domain}_clk`, `rst_n`/`{domain}_rst_n`
3. video-processing-expert reviews datapath model for signal processing accuracy
4. Build BFM via Bash CLI: `mkdir -p bfm/build && cd bfm/build && cmake .. && make`
5. Run smoke test via Bash CLI: `cd bfm/build && ./smoke_test`
6. Fix compile errors and smoke test failures
7. **Feature coverage verification against iron-requirements.json** (MANDATORY):
   - Read `docs/phase-1-research/iron-requirements.json` — extract all REQ-F-* items
   - Read `reviews/phase-2-architecture/ref-model-feature-coverage.md` if available
   - For EACH REQ-F-*, verify the BFM has a corresponding transaction-level model
     that exercises the feature (module method, transaction handler, data path — not just a stub)
   - This is a **structural** check: bitexact comparison with refc/ verifies data correctness,
     but may miss features not exercised by the specific test vectors used
   - Save `reviews/phase-3-uarch/bfm-feature-coverage.md`:
     ```
     | REQ-F-* | Feature | BFM Module/Method | Ref Model Match | Status |
     |---------|---------|-------------------|-----------------|--------|
     | REQ-F-001 | Intra 4x4 | intra_pred_module::b_transport | intra_predict_4x4() | IMPLEMENTED |
     | REQ-F-002 | Intra 8x8 | — | intra_predict_8x8() | MISSING |
     ```
   - Coverage < 100%: escalate to user via AskUserQuestion —
     "BFM does not model REQ-F-NNN ({feature}). Approve omission or require implementation?"
   - User-approved omissions must have ADR with documented impact on downstream verification
8. Record smoke test result in bfm/smoke_test_result.txt
9. If DPI-C co-simulation required: implement bfm/dpi/ interface
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="Implement SystemC TLM 2.0 BFMs in C++ at bfm/src/*.cpp from architecture.md. CRITICAL: Output MUST be C++ (.cpp/.h) files using SystemC, NOT SystemVerilog (.sv). If SystemC is not installed, write a pure C timing model as fallback. Use LT blocking transport (b_transport) by default. Use AXI protocol with amba_pv extensions. Include Memory Manager (tlm_mm_interface). One module per block. Include CMakeLists.txt. Interface signal names must match io_definition.json exactly (i_/o_ prefix convention, {domain}_clk/{domain}_rst_n). Switch to AT non-blocking only if explicitly requested.")

Task(subagent_type="rtl-agent-team:video-processing-expert",
     prompt="Review bfm/src/ datapath models for signal processing accuracy vs requirements.json.")

# Build and smoke test via Bash CLI (NOT MCP)
Bash: cd bfm/build && cmake .. && make
Bash: cd bfm/build && ./smoke_test
```
</Tool_Usage>

<Examples>
<Good>
bfm-dev produces 5 LT TLM modules with AXI extensions and memory manager;
all modules use b_transport with proper latency annotation;
smoke test passes (1 AXI burst transaction end-to-end in LT mode);
bfm/smoke_test_result.txt records PASS with latency numbers.
</Good>
<Bad>
Using LT b_transport for performance BFM — cannot model pipeline bubbles or OoO completions.
No AMBA extensions — bus attributes (burst type, cache policy) not captured.
No Memory Manager — payload leaks accumulate during simulation.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- SystemC not available in build environment → halt, instruct user to install SystemC 3.0+
- AMBA-PV headers not available → instruct user to install ARM AMBA-PV library
- Smoke test fails after 2 fix iterations → report failure, provide compile/runtime log
- AT 4-phase protocol deadlock → check PEQ callbacks for missing phase transitions
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] bfm/src/*.cpp compiles without errors
- [ ] One TLM module per architectural block
- [ ] LT blocking transport used by default (b_transport)
- [ ] If AT requested: 4-phase handshake complete (BEGIN_REQ, END_REQ, BEGIN_RESP, END_RESP)
- [ ] AMBA protocol extensions set correctly (AXI burst/cache/prot)
- [ ] Memory Manager (tlm_mm_interface) used for payload pooling
- [ ] PEQ (peq_with_cb_and_phase) used for phase scheduling
- [ ] Smoke test passes (at least one LT transaction; AT only when explicitly requested)
- [ ] BFM per-block functional output matches refc/ output (shared test vectors, bitexact or documented tolerance)
- [ ] Feature coverage verified against iron-requirements.json (ALL REQ-F-* mapped to BFM modules)
- [ ] `reviews/phase-3-uarch/bfm-feature-coverage.md` saved
- [ ] Missing features escalated to user — omissions have ADR with impact estimate
- [ ] bfm/smoke_test_result.txt written
- [ ] DPI-C interface provided if SV co-simulation required
</Final_Checklist>

<Advanced>
Use TLM 2.0 LT blocking coding style by default for fast functional validation and I/O logging.
Use AT non-blocking coding style only when explicitly requested for timing-accurate performance modeling.
BFM interfaces must match io_definition.json port list exactly for rtl-p5s-perf-verify compatibility.
AMBA protocol extensions must match architecture spec for protocol-level verification.
</Advanced>
