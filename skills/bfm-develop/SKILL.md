---
name: bfm-develop
description: "This skill should be used when developing SystemC TLM Bus Functional Models with AT non-blocking transport and AMBA protocol support from architecture block specifications."
---

<Purpose>
Implement SystemC TLM 2.0 BFMs that model the RTL design at transaction level using AT (Approximately
Timed) non-blocking transport with ARM AMBA protocol extensions (AXI/AHB/APB/ACE).
Outputs: bfm/ directory with SystemC models, build scripts, and initial smoke test results.
Runs in parallel with rtl-uarch-design during Phase 3.
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
- Only simple unit tests needed (use rtl-sv-unit-test directly)
- Pure software development without hardware interaction
</Do_Not_Use_When>

<Why_This_Exists>
TLM models run orders of magnitude faster than RTL simulation.
Early BFM catches protocol bugs and performance bottlenecks before RTL exists.
BFM also serves as the performance reference in rtl-perf-verify phase.
AT non-blocking transport accurately models pipelined and out-of-order behavior
that LT blocking transport cannot capture.
</Why_This_Exists>

<Execution_Policy>
- bfm-dev implements SystemC TLM models using AT non-blocking transport by default
- AMBA protocol selection: AXI by default, AHB/APB/ACE per architecture spec
- Memory Manager (tlm_mm_interface) required for payload pooling
- PEQ (peq_with_cb_and_phase) required for AT phase scheduling
- video-processing-expert ensures datapath model accuracy
- Smoke test (compile + run one AT transaction with 4-phase handshake) required before gate passes
</Execution_Policy>

<Steps>
1. Read architecture.md, io_definition.json, and identify AMBA protocol requirements
2. bfm-dev implements bfm/src/*.cpp: one TLM module per architectural block
   - **AT non-blocking** (nb_transport_fw/bw) as default transport style
   - **AXI protocol** with amba_pv::axi_extension as default (unless AHB/APB/ACE specified)
   - **Memory Manager** (tlm_mm_interface) for payload pooling
   - **PEQ** (peq_with_cb_and_phase) for AT phase scheduling
   - BFM interface names must match io_definition.json port names exactly
   - Port naming follows project conventions: `i_`/`o_`/`io_` prefix, `clk`/`{domain}_clk`, `rst_n`/`{domain}_rst_n`
3. video-processing-expert reviews datapath model for signal processing accuracy
4. Build BFM via Bash CLI: `mkdir -p bfm/build && cd bfm/build && cmake .. && make`
5. Run smoke test via Bash CLI: `cd bfm/build && ./smoke_test`
6. Fix compile errors and smoke test failures
7. Record smoke test result in bfm/smoke_test_result.txt
8. If DPI-C co-simulation required: implement bfm/dpi/ interface
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="Implement SystemC TLM 2.0 BFMs at bfm/src/ from architecture.md. Use AT non-blocking transport (nb_transport_fw/bw) with 4-phase protocol. Use AXI protocol with amba_pv extensions. Include Memory Manager (tlm_mm_interface) and PEQ (peq_with_cb_and_phase). One module per block. Include CMakeLists.txt. Interface signal names must match io_definition.json exactly (i_/o_ prefix convention, {domain}_clk/{domain}_rst_n).")

Task(subagent_type="rtl-agent-team:video-processing-expert",
     prompt="Review bfm/src/ datapath models for signal processing accuracy vs requirements.json.")

# Build and smoke test via Bash CLI (NOT MCP)
Bash: cd bfm/build && cmake .. && make
Bash: cd bfm/build && ./smoke_test
```
</Tool_Usage>

<Examples>
<Good>
bfm-dev produces 5 AT TLM modules with AXI extensions and memory manager;
all modules use nb_transport_fw/bw with 4-phase handshake;
smoke test passes (1 AXI burst transaction end-to-end in AT mode);
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
- [ ] AT non-blocking transport used by default (nb_transport_fw/bw)
- [ ] 4-phase handshake complete (BEGIN_REQ, END_REQ, BEGIN_RESP, END_RESP)
- [ ] AMBA protocol extensions set correctly (AXI burst/cache/prot)
- [ ] Memory Manager (tlm_mm_interface) used for payload pooling
- [ ] PEQ (peq_with_cb_and_phase) used for phase scheduling
- [ ] Smoke test passes (at least one AT transaction)
- [ ] bfm/smoke_test_result.txt written
- [ ] DPI-C interface provided if SV co-simulation required
</Final_Checklist>

<Advanced>
Use TLM 2.0 AT non-blocking coding style for timing-accurate performance modeling.
Use LT loosely-timed coding style only for fast SW development simulation.
BFM interfaces must match io_definition.json port list exactly for rtl-perf-verify compatibility.
AMBA protocol extensions must match architecture spec for protocol-level verification.
</Advanced>
