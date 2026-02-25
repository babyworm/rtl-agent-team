---
name: lint-check
description: Dual lint check using Verible and slang via Bash CLI. Quick utility skill.
---

<Purpose>
Run Verible (style/syntax) and slang (semantic) lint on target RTL files via Bash CLI.
Report all violations with file, line, rule, and severity.
</Purpose>

<Use_When>
- Verifying lint status of any RTL file before commit or phase gate
- Quick sanity check during development
- Generating lint report for review
</Use_When>

<Do_Not_Use_When>
- Lint fixing is also needed (use rtl-code or rtl-refactor which include fix cycles)
- Full verification suite needed (use func-verify or sv-unit-test)
</Do_Not_Use_When>

<Why_This_Exists>
Two complementary lint tools catch different issue classes.
Verible catches style and formatting; slang catches semantic issues that Verible misses.
Running both gives comprehensive coverage without false confidence from a single tool.
</Why_This_Exists>

<Coding_Convention_Enforcement>
Lint checks MUST enforce the project coding conventions (CLAUDE.md):
- Port prefix: `i_` (input), `o_` (output), `io_` (bidirectional) — NOT suffix `_i`, `_o`
- Clock: `{domain}_clk` (e.g., `sys_clk`) — NOT `clk_i`, `clk`
- Reset: `{domain}_rst_n` (e.g., `sys_rst_n`) — NOT `rst_ni`
- `logic` only — `reg`/`wire` usage flagged as violation
- Instance prefix: `u_` — missing prefix flagged
- Generate prefix: `gen_` — missing prefix flagged
Note: Verible and slang may not catch all convention violations natively.
lint-checker MUST perform a supplementary grep-based check for naming conventions.
</Coding_Convention_Enforcement>

<Execution_Policy>
- lint-checker runs both tools in parallel on the target file(s) via Bash CLI
- Additionally checks naming conventions not caught by standard tools
- Results merged and de-duplicated
- Zero-error gate: skill reports PASS or FAIL with full violation list
</Execution_Policy>

<Steps>
1. Identify target files (single file, directory, or glob)
2. Run Verible via Bash CLI: `verible-verilog-lint --rules_config .verible_lint.cfg {files}`
3. Run slang via Bash CLI: `slang --lint-only {files}`
4. Run supplementary convention checks via Bash CLI:
   - Grep for `reg ` or `wire ` declarations (should be `logic`)
   - Grep for port suffixes `_i,`, `_i)`, `_o,`, `_o)` (should use `i_`/`o_` prefix)
   - Grep for `clk_i`, `clk)`, `rst_ni` (should use `{domain}_clk`, `{domain}_rst_n`)
   - Grep for instances without `u_` prefix, generates without `gen_` prefix
5. Merge all results; report violations grouped by file then by severity
6. Return PASS (zero violations) or FAIL (violation count + list)
</Steps>

<Tool_Usage>
```
Task(subagent_type="rtl-agent-team:lint-checker",
     prompt="Run Verible and slang lint on rtl/src/ via Bash CLI. Also check naming conventions: i_/o_ port prefixes, {domain}_clk/{domain}_rst_n, logic not reg/wire, u_ instance prefix. Report all violations grouped by file. Return PASS or FAIL summary.")
```
</Tool_Usage>

<Examples>
<Good>
lint-checker runs both tools via Bash CLI, finds 3 Verible style violations, 1 slang unused-variable warning,
and 2 convention violations (port `data_i` should be `i_data`, `clk` should be `sys_clk`);
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
- [ ] Both Verible and slang ran on all target files via Bash CLI
- [ ] Naming convention checks ran (port prefix, clock, reset, logic, instance prefix)
- [ ] Results merged and reported
- [ ] PASS/FAIL clearly stated
- [ ] Violation list includes file:line:rule for each issue
</Final_Checklist>

<Advanced>
Project lint config: .verible_lint.cfg in repo root. Override rules only with user approval.
slang --lint-only treats warnings as errors in CI mode.
Convention check script can be added at scripts/check_conventions.sh for CI integration.
</Advanced>
