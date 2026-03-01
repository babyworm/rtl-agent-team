---
name: rtl-regression-run
description: "DEPRECATED — Use rtl-p5s-func-verify (Tier 3) for module-level regression with multi-seed support."
---

> **DEPRECATED**: This skill's functionality has been absorbed into `rtl-p5s-func-verify` (Tier 3).
> Use `/rtl-agent-team:rtl-p5s-func-verify` for module-level regression with multi-seed support.
> The `scripts/run_regression.sh` script is still available and is invoked by rtl-p5s-func-verify.

<Purpose>
Run the full test suite with multiple random seeds to maximize functional coverage.
Outputs: sim/regression/results_{timestamp}.json (per-test pass/fail) + sim/coverage/coverage.xml.
</Purpose>

<Use_When>
- RTL passes directed tests and needs broad regression
- Pre-tapeout full regression gate
- Coverage closure requires multi-seed runs
- Overnight/background regression requested
</Use_When>

<Do_Not_Use_When>
- RTL still has known failing tests (fix first with rtl-bug-repro)
- Only a single specific test needs running (use rtl-p5s-func-verify)
- UVM-based regression required (use rtl-p5s-uvm-verify)
</Do_Not_Use_When>

<Why_This_Exists>
A single seed may miss corner cases that other seeds expose. Multi-seed regression
with coverage collection provides statistical confidence and drives coverage closure
in a single automated flow.
</Why_This_Exists>

<Execution_Policy>
- eda-runner executes the test suite with each seed in parallel (if resources allow)
- coverage-analyst aggregates coverage across seeds
- Failing seeds trigger waveform capture for later analysis
- Report: total vectors, pass rate, coverage %, failing seed list
</Execution_Policy>

<Steps>
1. Read sim/regression/seed_list.txt (or use default seeds: 1, 42, 123, 1337, 65536)
2. eda-runner runs full test suite per seed via Bash CLI.
   Use `skills/rtl-regression-run/scripts/run_regression.sh` for automated multi-seed execution:
   ```bash
   bash skills/rtl-regression-run/scripts/run_regression.sh --seeds "1 42 123 1337 65536" --sim icarus
   ```
   Or run individually:
   ```bash
   make -C sim/top SIM=icarus SEED={seed} COVERAGE=1
   ```
3. Capture per-seed results to sim/regression/seed_{seed}_results.json
4. On failure: capture .vcd waveform for failing test (signals use i_/o_ prefixes, {domain}_clk/{domain}_rst_n)
5. coverage-analyst merges coverage via `skills/rtl-regression-run/scripts/merge_coverage.sh`:
   ```bash
   bash skills/rtl-regression-run/scripts/merge_coverage.sh --format verilator --output sim/coverage/merged.info
   ```
6. Write sim/coverage/coverage.xml (merged) and sim/regression/results_{timestamp}.json
7. Report using `templates/regression-report.md` format: seeds run, pass rate, total failures, coverage percentage, failing seed list
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:eda-runner",
     prompt="Run full cocotb regression via Bash CLI with seeds [1, 42, 123, 1337, 65536]. For each seed: make -C sim/top SIM=icarus SEED={seed} COVERAGE=1. Capture .vcd on failure. Save results to sim/regression/seed_{seed}_results.json.")

Task(subagent_type="rtl-agent-team:coverage-analyst",
     prompt="Merge coverage data from sim/regression/seed_*_results.json via Bash CLI (lcov --add-tracefile or equivalent). Produce sim/coverage/coverage.xml with line, branch, and toggle coverage. Report overall coverage percentage.")
```
</Tool_Usage>

<Examples>
<Good>
5 seeds run (500 tests each); 2498/2500 pass; seed 1337 fails test_cabac_bypass;
waveform captured; coverage-analyst reports 91.2% line, 83.4% toggle; regression report written.
</Good>
<Bad>
Running all seeds sequentially when parallel execution is available — wastes wall-clock
time on a task that is embarrassingly parallel.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Failure rate >5% → halt, do not continue other seeds, report immediately
- Coverage below 80% after 5 seeds → invoke rtl-p5s-coverage-analyze skill
- Simulator crashes (not test failure) → report crash with seed and test name
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All requested seeds executed
- [ ] sim/regression/results_{timestamp}.json written with per-test status
- [ ] sim/coverage/coverage.xml merged from all seeds
- [ ] Failing tests identified with seed numbers
- [ ] Pass rate and coverage % reported to user
</Final_Checklist>

<Advanced>
Coverage collection with Verilator:
```bash
# Compile with coverage
make -C sim/top SIM=verilator EXTRA_ARGS="--coverage --trace-fst" TOPLEVEL=dut MODULE=test_dut

# Merge multi-seed coverage data
verilator_coverage --write-info merged.info seed_*/coverage.dat

# Generate HTML report
genhtml merged.info -o sim/coverage/html/ --title "Regression Coverage"
```

Multi-seed strategy: use at least 5 deterministic seeds (1, 42, 123, 1337, 65536) plus
5 random seeds per run. Stop early if failure rate exceeds 5%.

Coverage targets: ≥90% line, ≥80% toggle, ≥70% FSM state.
See `references/coverage-tools.md` for lcov integration, Verilator coverage flags,
multi-seed regression script, and Coverview dashboard setup.
</Advanced>
