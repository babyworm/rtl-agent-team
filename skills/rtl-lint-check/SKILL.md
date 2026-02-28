---
name: rtl-lint-check
description: "This skill should be used when checking RTL files for lint violations using Verilator, Verible, and slang. Quick utility for pre-commit or phase gate verification."
---

<Purpose>
Run three complementary lint tools on target RTL files via Bash CLI:
- **Verilator** (synthesizability + semantic): catches LATCH, BLKANDNBLK, WIDTH, MULTIDRIVEN
- **Verible** (style/syntax): catches formatting, naming, structure issues
- **slang** (semantic/IEEE 1800 compliance): catches type errors, port mismatches

Report all violations with file, line, rule, and severity.
See `references/verilator-warnings.md` for detailed Verilator warning categories and waiver format.
</Purpose>

<Use_When>
- Verifying lint status of any RTL file before commit or phase gate
- Quick sanity check during development
- Generating lint report for review
</Use_When>

<Do_Not_Use_When>
- Lint fixing is also needed (use rtl-code or rtl-refactor which include fix cycles)
- Full verification suite needed (use rtl-func-verify or rtl-sv-unit-test)
</Do_Not_Use_When>

<Why_This_Exists>
Three complementary lint tools catch different issue classes:
- **Verilator** is the most widely-used open-source linter; it catches synthesizability issues (latches, blocking/non-blocking mix, width mismatches) that style linters miss entirely.
- **Verible** catches style and formatting issues; **slang** catches IEEE 1800 semantic issues.
Running all three gives comprehensive coverage: synthesizability + style + semantics.
</Why_This_Exists>

<Coding_Convention_Requirements>
Lint checks MUST enforce the project coding conventions (CLAUDE.md):
- Port prefix: `i_` (input), `o_` (output), `io_` (bidirectional) — NOT suffix `_i`, `_o`
- Clock: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
- Reset: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
- `logic` only — `reg`/`wire` usage flagged as violation
- Instance prefix: `u_` — missing prefix flagged
- Generate prefix: `gen_` — missing prefix flagged
Note: Verible and slang may not catch all convention violations natively.
lint-checker MUST perform a supplementary grep-based check for naming conventions.
</Coding_Convention_Requirements>

<Execution_Policy>
- lint-checker runs both tools in parallel on the target file(s) via Bash CLI
- Additionally checks naming conventions not caught by standard tools
- Results merged and de-duplicated
- Zero-error gate: skill reports PASS or FAIL with full violation list
</Execution_Policy>

<Steps>
1. Identify target files (single file, directory, or glob)
2. Run **Verilator** via Bash CLI (synthesizability lint):
   ```bash
   verilator --lint-only -Wall -Wpedantic -sv {files}
   ```
   - Critical warnings (MUST fix): BLKANDNBLK, LATCH, CASEINCOMPLETE, MULTIDRIVEN
   - Major warnings: WIDTH, UNDRIVEN, SYNCASYNCNET, UNSIGNED, CMPCONST
   - See `references/verilator-warnings.md` for full category list
3. Run **Verible** via Bash CLI (style lint):
   ```bash
   verible-verilog-lint --rules_config .verible_lint.cfg {files}
   ```
4. Run **slang** via Bash CLI (semantic lint):
   ```bash
   slang --lint-only {files}
   ```
5. Run supplementary convention checks via Bash CLI:
   - Use `skills/rtl-lint-check/scripts/check_conventions.sh {files}` for automated convention checking
   - Or manually grep for: `reg`/`wire` declarations, port suffixes `_i`/`_o`, `clk_i`/`rst_ni`, missing `u_`/`gen_` prefixes
6. Merge all results; report violations grouped by file then by severity
7. Return PASS (zero violations) or FAIL (violation count + list)
   - Use `templates/lint-report.md` as the report format template
   - If waiver file `.verilator.vlt` exists, apply waivers before final verdict (see `templates/verilator-waiver.vlt` for waiver format)
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Run Verilator, Verible, and slang lint on rtl/ via Bash CLI. Verilator: --lint-only -Wall -Wpedantic -sv. Verible: --rules_config .verible_lint.cfg. slang: --lint-only. Also check naming conventions: i_/o_ port prefixes, {domain}_clk/{domain}_rst_n, logic not reg/wire, u_ instance prefix. Report all violations grouped by file and severity (Critical/Major/Minor). Return PASS or FAIL summary.")
```
</Tool_Usage>

<Examples>
<Good>
lint-checker runs both tools via Bash CLI, finds 3 Verible style violations, 1 slang unused-variable warning,
and 2 convention violations (port `data_i` should be `i_data`, `clk` should be `sys_clk` in multi-domain context);
returns FAIL with exact line numbers and rule names.
</Good>
<Bad>
Running only one lint tool and claiming "lint clean" — misses semantic issues caught only by slang.
Not checking naming conventions — allows `clk_i`, `data_o` to pass lint despite project rules.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Verible not installed → report to user with install command (`apt install verible` or from GitHub releases)
- slang not installed → report to user with install command (`pip install slang` or from source)
- Lint rules config file missing → use default rules, note this in report
- Convention violations found → report alongside tool violations, same severity
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All three lint tools ran: Verilator, Verible, and slang via Bash CLI
- [ ] Verilator critical warnings (LATCH, BLKANDNBLK) treated as hard errors
- [ ] Naming convention checks ran (port prefix, clock, reset, logic, instance prefix)
- [ ] Results merged, de-duplicated, and reported by severity
- [ ] PASS/FAIL clearly stated
- [ ] Violation list includes file:line:rule:tool for each issue
</Final_Checklist>

<Advanced>
Project lint config: .verible_lint.cfg in repo root. Override rules only with user approval.
slang --lint-only treats warnings as errors in CI mode.
Convention check script: `skills/rtl-lint-check/scripts/check_conventions.sh` — ready for CI integration.
See `examples/lint-output-example.txt` for sample merged lint output across all tools.

Verilator waiver file (`.verilator.vlt`) for intentional suppressions:
```
`verilator_config
lint_off -rule UNUSED -file "rtl/reserved/reserved.sv" -lines 10-15
lint_off -rule WIDTH -file "rtl/datapath/datapath.sv" -match "Operator *"
```
Generate waiver template: `verilator --lint-only -Wall --waiver-output verilator.vlt rtl/*/*.sv`
See `references/verilator-warnings.md` for complete warning reference.
</Advanced>
