---
name: rtl-lint-check
description: "Run the configured RTL linter and report findings. Use for 'run lint', pre-commit checks, or phase verification. No automatic fixes."
user-invocable: true
---

Lint the requested RTL scope with `preferences.lint` from rat_config.json, unless
the user selects a tool. Use one suitable configured linter; an extra engine is
useful only for a concrete unresolved diagnostic or an explicit multi-tool request.
Do not install or require three engines to repeat a successful check.

Use the deployed wrapper, or its bundled source when the project has no copy:

```bash
lint/scripts/run_lint.sh --tool auto --top {top} -f {filelist} --outdir lint/{scope}
```

The wrapper consumes configured executable/environment/backend settings and handles
filelist includes/defines. SpyGlass requires a recognized goal result, not only a
zero exit. Tool absence, an unknown goal format, or a timeout is not PASS.

Report tool, checked scope, exit/verdict, log path, and findings with file/line/rule/
severity. Group shared root causes without hiding individual affected locations.
Distinguish a style/syntax scan from semantic elaboration. Use lint-checker when
cross-file diagnosis is needed. This action reports findings; fixing belongs to the
implementation or bugfix action and requires affected functional verification.

For a relevant Verilator diagnostic or waiver syntax, read
`references/verilator-warnings.md`. Preserve project naming rules and existing
explicit waivers; do not silence a failure merely to obtain PASS.
