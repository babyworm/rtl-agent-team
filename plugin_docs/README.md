# Plugin Documentation Lifecycle

`plugin_docs/` contains current operational guides and dated design records. A
document's status header controls how it should be used:

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
