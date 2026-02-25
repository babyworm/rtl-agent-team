---
name: rtl-autopilot
description: Master orchestrator for full RTL design pipeline from specification to verified silicon-ready implementation.
---

<Purpose>
Drive the complete RTL design pipeline through five sequential phases with enforced phase gates.
Each phase must produce required artifacts before the next phase begins.
State is persisted at .rtl-agent-team/state/rtl-autopilot-state.json for resumability.
</Purpose>

<Use_When>
- Starting a new RTL design project from specification
- Resuming an interrupted pipeline run
- Full end-to-end automation is required with no manual phase handoff
</Use_When>

<Do_Not_Use_When>
- Only a single phase needs to run (use the phase-specific skill instead)
- Design already has completed artifacts for early phases
- Quick prototype or exploratory work only
</Do_Not_Use_When>

<Why_This_Exists>
RTL design spans domains (algorithm, architecture, RTL, verification) that require different specialists.
Manual handoff between phases loses context and misses interface contracts.
This skill automates sequencing, gate checking, and recovery.
</Why_This_Exists>

<Execution_Policy>
- State file (.rtl-agent-team/state/rtl-autopilot-state.json) tracks progress for resumability
- Independent sub-tasks within a phase run in parallel via concurrent Task() calls
- Phase gates are hard stops: missing artifacts block progression
- On failure: retry the failed phase once, then escalate to user
- On interruption: state file is preserved; re-invoking this skill resumes from last phase
</Execution_Policy>

<Steps>
1. Initialize state: write .rtl-agent-team/state/rtl-autopilot-state.json with phase=1
2. Phase 1 - Research: invoke research-analyze skill; gate: requirements.json + io_definition.json + domain-analysis.md
   - io_definition.json must use project naming conventions: `i_`/`o_`/`io_` port prefixes, `{domain}_clk`, `{domain}_rst_n`
3. Phase 2 - Arch+Ref (parallel): invoke arch-design and ref-model skills concurrently; gate: architecture.md + block_diagram + ref_model/src/*.cpp
   - architecture.md interface tables must use `i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n` naming
4. Phase 3 - uArch+BFM (parallel): invoke uarch-design and bfm-develop skills concurrently; gate: uarch/*.md + bfm/ directory
   - uarch/*.md register/signal names must follow: `i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n`, `u_` instances, `gen_` generates
5. Phase 4 - RTL: invoke rtl-code skill; gate: rtl/src/*.sv all lint-clean
   - Enforce: `logic` only (no `reg`/`wire`), `always_ff`/`always_comb`, ANSI port style
6. Phase 5 - Verify: invoke sv-unit-test, sva-check, func-verify, perf-verify, conformance-test sequentially; gate: all pass
7. On completion: remove state file, report summary

**Coding Convention Enforcement (all phases):**
- Port naming: inputs `i_`, outputs `o_`, bidirectional `io_` (NOT suffix `_i`/`_o`)
- Clock: `{domain}_clk` (e.g., `sys_clk`, `pixel_clk`) — NOT `clk_i`, `clk`, `clk_sys`
- Reset: `{domain}_rst_n` (e.g., `sys_rst_n`) — NOT `rst_ni`, `rst_n`
- Instances: `u_` prefix; generates: `gen_` prefix
- Use `logic` everywhere (`reg`/`wire` forbidden)
- Base style: lowRISC SystemVerilog Coding Style Guide with above overrides
</Steps>

<Tool_Usage>
```
# Phase 1: Research
Task(subagent_type="rtl-agent-team:spec-analyst",
     prompt="Analyze spec at specs/ and produce requirements.json, io_definition.json, domain-analysis.md. Port names in io_definition.json must use i_/o_/io_ prefix convention, clocks as {domain}_clk, resets as {domain}_rst_n.")

# Phase 2: Arch + Ref Model (parallel)
Task(subagent_type="rtl-agent-team:arch-designer",
     prompt="Design architecture from requirements.json and io_definition.json. All interface signals must use i_/o_ prefix, {domain}_clk/{domain}_rst_n naming. Produce architecture.md and block_diagram.")
Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Implement C++ ref model at ref_model/src/ from requirements.json. Must be bitexact vs JM/HM.")

# Phase 3: uArch + BFM (parallel)
Task(subagent_type="rtl-agent-team:uarch-designer",
     prompt="Produce uarch/*.md from architecture.md. All signal names must use i_/o_ prefix, {domain}_clk/{domain}_rst_n, u_ instances, gen_ generates.")
Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="Implement SystemC TLM BFMs at bfm/src/ from architecture.md. Interface names must match io_definition.json.")

# Phase 4: RTL (parallel per module)
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Implement rtl/src/{module}.sv from uarch/{module}.md. Use logic only (no reg/wire), i_/o_ port prefix, {domain}_clk/{domain}_rst_n, u_ instances, gen_ generates. Run lint after writing.")

# Phase 5: Verify (sequential)
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Write SV unit tests for rtl/src/{module}.sv at tb/unit/.")
Task(subagent_type="rtl-agent-team:func-verifier",
     prompt="Run cocotb functional tests on rtl/src/*.sv against ref_model.")
```
</Tool_Usage>

<Examples>
<Good>
User: "autopilot: implement H.264 CABAC encoder from spec"
→ Writes state file, runs all 5 phases sequentially with gates, resumes on interruption.
</Good>
<Bad>
User: "quickly sketch a block diagram"
→ Do NOT invoke rtl-autopilot. Use arch-design or domain-consult directly.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Gate check fails twice → pause and report missing artifacts to user
- Verification phase fails after 2 retries → invoke bug-repro skill, report findings
- User says "cancelomc" → invoke cancel skill, preserve state file for resume
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] State file written before starting
- [ ] Each phase gate validated before proceeding
- [ ] Naming conventions enforced at every phase gate:
  - io_definition.json: `i_`/`o_`/`io_` prefix, `{domain}_clk`/`{domain}_rst_n`
  - architecture.md: interface signal names, clock/reset naming
  - uarch/*.md: all signal names, FSM states, instance prefixes
  - rtl/src/*.sv: lint-clean, naming compliant
- [ ] All 5 phases completed
- [ ] State file removed on clean completion
- [ ] Summary report generated
</Final_Checklist>

<Advanced>
Resume: read existing state file, skip completed phases, continue from current phase.
Parallel phases (2 and 3) use separate state sub-keys to track each sub-task independently.
</Advanced>
