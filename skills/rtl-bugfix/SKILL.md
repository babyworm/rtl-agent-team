---
name: rtl-bugfix
description: "RTL bug fix workflow enforcing the full cycle: analyze → fix → lint → TB create/update → functional verification. Prevents RTL changes from being considered complete with lint-only validation."
---

<Purpose>
A workflow skill that enforces the design-to-verification flow when fixing RTL bugs.
A fix is only considered complete after TB generation and functional simulation pass — not just lint.

**Core principle: lint is only a syntax check, not evidence of functional correctness.**

This skill integrates with the PostToolUse:Edit hook tracking system.
Modified .sv files are automatically tracked, and session termination is blocked without functional verification.
</Purpose>

<Use_When>
- Fixing RTL bugs found during Phase 4 review
- Fixing functional errors in RTL modules
- Adding or modifying functionality in existing RTL
- Verifying no functional regression after refactoring
- Fixing integration bugs spanning multiple modules
- **Phase 5→4 Feedback Loop**: Automatic fix path invoked when Phase 5 verification FAILs
</Use_When>

<Do_Not_Use_When>
- Coding convention changes only (e.g., port renaming with no functional change) → use rtl-refactor
- Writing a new module from scratch → use rtl-code
- Simple lint error fixes (e.g., removing unused signals) → use rtl-lint-check
</Do_Not_Use_When>

<Why_This_Exists>
Born from a previous session where 9 RTL bugs were fixed with only lint runs, skipping TB/simulation entirely.
Passing lint is merely "compilation success" — simulation is required to prove the fix is functionally correct.

**Anti-pattern example:**
- 312 lines of RTL modified across 5 Waves → only verilator --lint-only executed → 0 TBs, 0 simulations
- Result: declared "complete" with zero functional correctness verification
</Why_This_Exists>

<Execution_Policy>
- Mandatory 4-step sequence per module: analyze → fix+lint → TB → functional verification
- Each step can only proceed after the previous step is complete
- **Parallel UNIT_FIX**: When multiple independent modules fail, fix them in parallel
  - UNIT_FIX (different modules): parallel rtl-bugfix tasks, one per module
  - UNIT_FIX (same module): sequential within single task
  - INTEGRATION_FIX: always sequential (cross-module dependencies)
- If TB already exists: update existing TB (add new test cases)
- If no TB exists: creating at least a smoke test TB is mandatory
- Verification-done marker is only created after ALL parallel fixes pass functional verification
- The Stop hook checks the verification-done marker to allow session termination
</Execution_Policy>

<Steps>
1. **Analysis step**: Understand the bug and assess impact scope
   - Use rtl-explorer to search related modules/signals
   - Identify the bug's root cause
   - Compile a list of affected modules
   - Formulate a fix plan (which files, what changes)

1.5. **Classify and Batch Parallel Fixes**:
   When multiple Phase 5 sub-phases report FAIL simultaneously:
   - Classify each FAIL as: **UNIT_FIX** (single module) or **INTEGRATION_FIX** (multi-module)
   - Group UNIT_FIX failures by module
   - **If failures are in DIFFERENT modules** (independent):
     → Launch parallel rtl-bugfix tasks, one per module
     → Each follows the full cycle: analyze → fix → lint → TB → sim
     → All run concurrently (use `run_in_background: true`)
     → Collect results: all must PASS before returning to Phase 5
   - **If failures are in the SAME module** (dependent):
     → Sequential fix within a single rtl-bugfix task (fix all issues together)
   - **INTEGRATION_FIX**: Always sequential (may affect shared interfaces across multiple modules)
   - After all parallel fixes complete, re-run ONLY the affected Phase 5 sub-phases in parallel

2. **Fix+lint step**: Modify RTL code and verify syntax
   - rtl-coder implements the bug fix
   - lint-checker runs lint on modified files: `verilator --lint-only -Wall`
   - Iterate on lint errors (max 3 rounds)
   - **This step is a necessary condition, not a sufficient one**

3. **TB creation/update step**: Write tests to verify the fix
   - Check for existing TBs: `ls sim/*/test_*.py sim/*/tb_*.sv 2>/dev/null`
   - **If no TB exists**: testbench-dev creates at least a smoke test TB
     - At least 1 test file per modified module
     - Include the bug reproduction scenario as a test case
   - **If TB exists**: testbench-dev adds bug-related test cases
     - Test vectors that reproduce the bug trigger condition
     - Assertions that confirm correct behavior after the fix
   - TB signal naming convention: `dut.sys_clk`, `dut.i_*`, `dut.o_*`

4. **Functional verification step**: Run simulation and check results
   - eda-runner executes simulation:
     ```bash
     # cocotb (Python TB)
     make -C sim/{module} SIM=icarus TOPLEVEL={module} MODULE=test_{module}
     # Or SV TB via run_sim.sh
     scripts/run_sim.sh --sim iverilog --top tb_{module} --outdir sim/{module} --trace \
       rtl/{module}/{module}.sv sim/{module}/tb_{module}.sv
     ```
   - On failure: debug waveforms with waveform-analyzer
   - Confirm **all tests PASS**
   - Create the verification-done marker:
     ```bash
     touch .rtl-agent-team/state/rtl-verify-done
     ```
   - This marker must exist for the Stop hook to allow session termination

5. **(Phase 5→4 Feedback Mode)**: Return to Phase 5 sub-phase
   - When `feedback_origin` is specified (e.g., "5a-formal", "5b-cdc", "5c-integration")
   - After fix is complete, create verification-done marker: `touch .rtl-agent-team/state/rtl-verify-done`
   - Signal return to rtl-autopilot: request re-execution of the corresponding Phase 5 sub-phase
   - If feedback_origin is not set, skip this step (normal bug fix mode)
   - **Handling by FAIL type:**
     - UNIT_FIX: single module fix → lint → unit TB → unit sim → return after PASS
     - INTEGRATION_FIX: multi-module fix → lint → unit TB + integration TB → sim → return after PASS

6. **Append lesson learned** (recommended; mandatory in Phase 5→4 feedback mode)
   - Append a lesson entry to `docs/lessons-learned.md` using `templates/lessons-learned-entry.md` format
   - Record: symptom, root cause, fix applied, prevention strategy
   - In Phase 5→4 feedback mode (`feedback_origin` is set): this step is **mandatory**
   - In normal bugfix mode: this step is **recommended** for non-trivial bugs
   - For complex bugs, additionally save a fix report to the `reviews/` directory
</Steps>

<Tool_Usage>
```
# ============================================================
# Step 1: Analysis
# ============================================================
Task(subagent_type="rtl-agent-team:rtl-explorer",
     prompt="Analyze bug: [bug description]. Identify affected modules, root cause, and impact scope in rtl/. List all files that need modification.")

# ============================================================
# Step 2: Fix + lint
# ============================================================
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Fix bug in rtl/{module}/{module}.sv: [fix description]. Follow coding conventions: i_/o_ port prefix, sys_clk/sys_rst_n, logic only, always_ff/always_comb. After fix, run: verilator --lint-only -Wall rtl/{module}/{module}.sv")

# ============================================================
# Step 3: TB creation/update
# ============================================================
# Check for existing TBs
Bash("ls sim/*/test_*.py sim/*/tb_*.sv 2>/dev/null || echo 'NO_TB_EXISTS'")

# If no TB exists: create new
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Create cocotb smoke test for rtl/{module}/{module}.sv at sim/{module}/test_{module}.py. Include: (1) basic reset sequence, (2) bug reproduction scenario: [describe], (3) normal operation check. Signal naming: dut.sys_clk, dut.sys_rst_n, dut.i_*/dut.o_*.")

# If TB exists: add test cases
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Add test case to sim/{module}/test_{module}.py for bug fix verification: [describe bug and fix]. Add assertion checking correct behavior after fix. Signal naming: dut.sys_clk, dut.sys_rst_n, dut.i_*/dut.o_*.")

# ============================================================
# Step 4: Run functional verification
# ============================================================
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb test via Bash CLI: make -C sim/{module} SIM=icarus TOPLEVEL={module} MODULE=test_{module}. Report pass/fail. On failure, capture waveform for debug.")

# Create verification-done marker when all tests PASS
Bash("touch .rtl-agent-team/state/rtl-verify-done")

# ============================================================
# Step 5: Phase 5→4 Feedback Mode (when feedback_origin is specified)
# ============================================================
# When rtl-bugfix is invoked after a FAIL in a Phase 5 sub-phase:
# If feedback_origin is specified, return to the corresponding Phase 5 sub-phase after fix
#
# Example: Phase 5a formal verification FAIL
# → rtl-bugfix invoked (feedback_origin=5a-formal)
# → Steps 1-4 executed (analyze → fix → lint → TB → sim)
# → Step 5: create verify-done marker + request Phase 5a re-execution
#
# If feedback_origin is not set, Step 5 is skipped (normal bug fix mode)
Bash("touch .rtl-agent-team/state/rtl-verify-done")
# rtl-autopilot reads feedback_origin and re-executes the corresponding Phase 5 sub-phase

# ============================================================
# Step 1.5: Parallel UNIT_FIX (when multiple independent modules fail)
# ============================================================
# Example: Phase 5a SVA counterexample in module_a, Phase 5c cocotb failure in module_b
# These are independent UNIT_FIX failures → fix in parallel

# Module A fix (background)
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Fix SVA counterexample in rtl/module_a.sv: [details]. Follow coding conventions. After fix, run: verilator --lint-only -Wall rtl/module_a.sv",
     run_in_background=true)

# Module B fix (background, parallel with Module A)
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="Fix cocotb test failure in rtl/module_b.sv: [details]. Follow coding conventions. After fix, run: verilator --lint-only -Wall rtl/module_b.sv",
     run_in_background=true)

# After both fixes complete: parallel TB update + sim
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Update TB for module_a with fix verification test case.",
     run_in_background=true)
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="Update TB for module_b with fix verification test case.",
     run_in_background=true)

# Parallel re-verification
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb test for module_a: make -C sim/module_a SIM=icarus TOPLEVEL=module_a MODULE=test_module_a",
     run_in_background=true)
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run cocotb test for module_b: make -C sim/module_b SIM=icarus TOPLEVEL=module_b MODULE=test_module_b",
     run_in_background=true)

# After all pass: create verification-done marker
Bash("touch .rtl-agent-team/state/rtl-verify-done")

# Return to Phase 5: re-run ONLY affected sub-phases in parallel
# Phase 5a (formal) + Phase 5c (integration) re-run simultaneously
```
</Tool_Usage>

<Examples>
<Good>
5-Wave bug fix plan:
  Wave 1-5: 6 files, 312 lines of RTL modified
  → Each Wave: lint run (syntax verification)
  → After all fixes complete: smoke test TB created (test_h264_tq_top.py)
  → cocotb functional simulation run (10 test vectors)
  → RTL output vs C reference model comparison
  → All tests PASS → touch rtl-verify-done
  → Session terminates normally
</Good>
<Good>
Parallel UNIT_FIX:
  Phase 5a formal FAIL: SVA counterexample in cabac_encoder.sv (UNIT_FIX)
  Phase 5c cocotb FAIL: assertion error in transform.sv (UNIT_FIX)
  Different modules → parallel fix:
    → rtl-coder fixes cabac_encoder.sv (background)
    → rtl-coder fixes transform.sv (background, parallel)
    → Both lint-clean → parallel TB update → parallel sim
    → Both PASS → touch rtl-verify-done
    → Return to Phase 5: re-run 5a + 5c in parallel
  Total time: ~1x single fix (not 2x sequential)
</Good>
<Bad>
5-Wave bug fix plan:
  Wave 1-5: 6 files, 312 lines of RTL modified
  → Each Wave: verilator --lint-only -Wall (lint only)
  → Declared "lint passed, bug fix complete"
  → 0 TBs, 0 simulations
  → Declared complete with zero functional correctness verification ← this is the anti-pattern this skill prevents
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- lint fails 3 times → escalate to rtl-architect for design review
- Cannot write TB (no ref model) → write a minimal self-checking TB, then report ref model requirement to user
- Simulation fails after 2 fix iterations → escalate to waveform-analyzer + rtl-bug-repro skill
- Simulator not installed → eda-runner provides installation instructions (`pip install cocotb`, `apt install iverilog`)
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Bug root cause identified
- [ ] RTL fix complete
- [ ] lint passed (verilator --lint-only -Wall, 0 errors)
- [ ] TB created or updated (at least 1 test per modified module)
- [ ] Bug reproduction scenario included as a test case
- [ ] **Functional simulation executed (cocotb or verilator sim)**
- [ ] **All tests PASS**
- [ ] **Verification-done marker created (.rtl-agent-team/state/rtl-verify-done)**
- [ ] TB signal naming convention followed (dut.sys_clk, dut.i_*, dut.o_*)
- [ ] Multi-module failures classified (UNIT_FIX vs INTEGRATION_FIX)
- [ ] Independent UNIT_FIX modules fixed in parallel (not sequentially)
- [ ] All parallel fixes passed functional verification before verify-done marker
</Final_Checklist>

<Advanced>
**For integration bugs spanning multiple modules:**
- Both per-module unit TBs and top-level integration TB are needed
- Unit TBs: verify individual module I/O
- Integration TB: verify data flow between modules

**When an existing regression suite is available:**
- Recommended to re-run the full regression after bug fix
- Use the rtl-regression-run skill: `/rtl-agent-team:rtl-regression-run`

**For compound mode bugs like MODE_RECON:**
- Test individual modes first (MODE_FWD_TQ, MODE_INV_TQ)
- Add compound mode tests separately
- Include mode transition scenarios

**Parallel UNIT_FIX decision tree:**
- Multiple FAILs in DIFFERENT modules → parallel fix (each module independent)
- Multiple FAILs in SAME module → sequential fix (single task handles all)
- Any INTEGRATION_FIX → sequential (shared interfaces require coordinated changes)
- Mixed UNIT_FIX + INTEGRATION_FIX → INTEGRATION_FIX first (sequential), then remaining UNIT_FIX in parallel
</Advanced>
