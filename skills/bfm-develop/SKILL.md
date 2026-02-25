---
name: bfm-develop
description: Phase 3b skill. Builds SystemC TLM Bus Functional Models for performance verification.
---

<Purpose>
Implement SystemC TLM 2.0 BFMs that model the RTL design at transaction level.
Outputs: bfm/ directory with SystemC models, build scripts, and initial smoke test results.
Runs in parallel with uarch-design during Phase 3.
</Purpose>

<Use_When>
- Phase 2 artifacts (architecture.md, ref_model/) are complete
- TLM models are needed for early performance estimation or protocol verification
- BFM needed as stimulus/checker in verification environment
</Use_When>

<Do_Not_Use_When>
- Architecture is not yet stable (BFM will need full rewrite)
- Only simple unit tests needed (use sv-unit-test directly)
</Do_Not_Use_When>

<Why_This_Exists>
TLM models run orders of magnitude faster than RTL simulation.
Early BFM catches protocol bugs and performance bottlenecks before RTL exists.
BFM also serves as the performance reference in perf-verify phase.
</Why_This_Exists>

<Execution_Policy>
- bfm-dev implements SystemC TLM models
- video-processing-expert ensures datapath model accuracy
- Smoke test (compile + run one transaction) required before gate passes
</Execution_Policy>

<Steps>
1. Read architecture.md and io_definition.json
2. bfm-dev implements bfm/src/*.cpp: one TLM module per architectural block
   - BFM interface names must match io_definition.json port names exactly
   - Port naming follows project conventions: `i_`/`o_`/`io_` prefix, `{domain}_clk`/`{domain}_rst_n`
   - Use the same signal names in SystemC as in io_definition.json for perf-verify compatibility
3. video-processing-expert reviews datapath model for signal processing accuracy
4. Build BFM via Bash CLI: `mkdir -p bfm/build && cd bfm/build && cmake .. && make`
5. Run smoke test via Bash CLI: `cd bfm/build && ./smoke_test`
6. Fix compile errors and smoke test failures
7. Record smoke test result in bfm/smoke_test_result.txt
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="Implement SystemC TLM 2.0 BFMs at bfm/src/ from architecture.md. One module per block. Include CMakeLists.txt. Interface signal names must match io_definition.json exactly (i_/o_ prefix convention, {domain}_clk/{domain}_rst_n).")

Task(subagent_type="rtl-agent-team:video-processing-expert",
     prompt="Review bfm/src/ datapath models for signal processing accuracy vs requirements.json.")

# Build and smoke test via Bash CLI (NOT MCP)
Bash: cd bfm/build && cmake .. && make
Bash: cd bfm/build && ./smoke_test
```
</Tool_Usage>

<Examples>
<Good>
bfm-dev produces 5 TLM modules; smoke test passes (1 frame encoded end-to-end in TLM);
bfm/smoke_test_result.txt records PASS with latency numbers.
</Good>
<Bad>
Using RTL-abstracted cycle-accurate models instead of TLM — defeats the purpose of fast simulation
and couples BFM too tightly to implementation details.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- SystemC not available in build environment → halt, instruct user to install SystemC 2.3.4+
- Smoke test fails after 2 fix iterations → report failure, provide compile/runtime log
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] bfm/src/*.cpp compiles without errors
- [ ] One TLM module per architectural block
- [ ] Smoke test passes (at least one transaction)
- [ ] bfm/smoke_test_result.txt written
</Final_Checklist>

<Advanced>
Use TLM 2.0 loosely-timed coding style for maximum simulation speed.
BFM interfaces must match io_definition.json port list exactly for perf-verify compatibility.
</Advanced>
