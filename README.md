[한국어](README_kr.md)

# RTL Agent Team

Claude Code plugin for RTL design and verification. Its 91 specialized AI agents
and 55 skills cover specification, architecture, microarchitecture, RTL
implementation, verification, and design notes.

## Quick Start

In Claude Code, install the published plugin (v0.14.6):

```text
/plugin marketplace add babyworm/rtl-agent-team
/plugin install rtl-agent-team
```

From your RTL project directory, set up the tools, initialize the project, and
start with your specification:

```text
/rtl-agent-team:rat-setup
/rtl-agent-team:rat-init-project
/rtl-agent-team:rat-auto-design specs/design.md
```

For remote EDA, give `rat-setup` the SSH alias, target phase, and site setup
script if needed. Keep connection details and generated configuration outside
this plugin repository. [EDA setup, including Docker](plugin_docs/eda-setup-guide.md)

## Choose a workflow

| Goal | Skill |
| --- | --- |
| Run P1–P6 | `rat-auto-design` |
| Explore alternatives through microarchitecture and BFM | `rat-dse` |
| Review the design before writing RTL | `rat-p1p3-spec-uarch` |
| Implement and verify RTL from an approved microarchitecture | `rat-p4p5-impl-verify` |
| Close functional verification | `rtl-p5a-functional-closure` |
| Check synthesis, timing, and CDC after P5A passes | `rtl-p5b-silicon-validation` |

Use the `/rtl-agent-team:` prefix for each skill. Full automation uses team mode
when available and the bundled Phase 5 verification flow. Pass `--no-team` for
sequential execution. Rerun the same command to resume with valid evidence.

Codex cross-review is off by default. Ask for it in a run, including for a single
phase, or set `review.codex_cross_review` to `true` in the project's
`rat_config.json`. [Cross-review behavior](runtime/phase-dispatch.md)

## Local plugin development

From a `try-2.0` checkout, run `claude --plugin-dir .` to load the current working
tree. For a fresh checkout:

```bash
git clone --branch try-2.0 https://github.com/babyworm/rtl-agent-team.git
cd rtl-agent-team
claude --plugin-dir .
```

- [Contributing](CONTRIBUTING.md) · [Tests](tests/README.md)
- [Technical guides](plugin_docs/README.md) · [Model selection](runtime/model-selection.md)
- [Changelog](CHANGELOG.md) · [MIT License](LICENSE)
