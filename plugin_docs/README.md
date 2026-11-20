# Plugin Documentation Lifecycle

`plugin_docs/` contains current operational guides and dated design records. Use these guides for current workflows:

- [Quick start and local checkout](../README.md#quick-start)
- [Contributing and deployment](../CONTRIBUTING.md)
- [EDA tool setup and private site profiles](eda-setup-guide.md)
- [Hook development and RTL Stop behavior](hook-development-guide.md)
- [Host-native model selection](../runtime/model-selection.md)
- [Phase-scoped Codex cross-review](../runtime/phase-dispatch.md)
- [Running tests](../tests/README.md) and [model evaluations](../evals/README.md)

A dated document's status header controls how it should be used:

- `Draft`: exploratory material that is not approved for implementation.
- `Approved`: accepted design with implementation still pending or in progress.
- `Implemented`: shipped design. Its historical body may retain original problem
  statements, commands, and unchecked steps when a historical boundary says so.
- `Historical`: execution record retained for context, not active work.
- `Superseded`: replaced by another named document or live contract.

For a dated plan with a companion `Implemented` specification, treat the plan as
historical unless its header explicitly reopens work. Current runtime behavior is
defined by the repository code, tests, root documentation, and active skill or agent
contracts. Do not execute historical worker instructions without checking those live
sources first.
