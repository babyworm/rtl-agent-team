# v2 execution and prompt audit

Status (2026-11-17): repository implementation complete for the prompt audit and
roadmap Phases 1b–5 on `try-2.0`, starting from `0db2ba5`. External site
qualification remains open as listed below. No commit, release, installed-plugin
update, or global tool installation was performed. Package version 0.14.6 still
identifies the last published release.

## Governing decisions

Prompts carry the goal, project constraints, required evidence, and completion
condition. Retain exact normative facts, artifact schemas, project conventions,
tool quirks and order-sensitive commands. Remove general lessons, motivational
background, invented design values, and compulsory exploration or review rounds.
Leave model effort at the session default.

Record confidence and observable reasons for judgment. Confidence is a model
self-report, not a calibrated probability. A material ambiguity changes behavior,
interfaces, constraints, or a verification expected result. Keep it open until an
authorized decision resolves it, even when the model confidently identifies the
problem or an averaged ambiguity score is low. Continue independent work while
waiting for that decision.

One evidence review is enough when its findings are settled. No successful check
is repeated solely to raise confidence. A concrete failure justifies repair and
its affected checks, bounded by the existing maximum of two failed feedback
cycles; there is no minimum iteration count or automatic strategy ladder.
Confidence never overrides a measured failure, missing functional evidence, or an
undefined verification oracle.

## Official guidance checked on 2026-11-17

- [Fable 5.2 prompting](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5-2)
- [Opus 5.5 prompting](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5)
- [Skill authoring](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [Latest OpenAI models](https://developers.openai.com/api/docs/guides/latest-model)
- [Reasoning guidance](https://developers.openai.com/api/docs/guides/reasoning-best-practices)
- [Claude Code hooks](https://code.claude.com/docs/en/hooks)
- [Verilator language behavior](https://verilator.org/guide/latest/languages.html)

The OpenAI family guide describes observations on Astra and asks users to evaluate
its advice on their chosen model. It is not Sol-specific proof of a quality gain.
The changes here apply those principles to this plugin and were checked with the
available model and runtime fixtures below.

## Completed implementation

- [x] Prompt audit and confidence/ambiguity contracts.
- [x] Phase 1b: direct slash commands, accepted-call state timing, and remaining
  enforcement-integrity fixes.
- [x] Phase 1c: explicit installation and safe template updates.
- [x] Phase 1d: runner-written verification evidence bound to current inputs.
- [x] Phase 2: truthful verdicts, timeout/failure handling, and library prerequisites.
- [x] Phase 3: shared execution contract with local, Docker, SSH, and LSF backends.
- [x] Phase 4: capability-based setup and consumed tool/site configuration.
- [x] Phase 5: prompt/policy/roster consolidation, executable gates and model evals.
- [x] Final unit suite, actual Verilator runs, and generated-artifact checks.

### Prompt audit

All 99 original agent audit preambles stopped asking for internal `THOUGHT`
annotations. They now request decisions, concise evidence/source references, and
uncertainty. Removed 54 generic `Why_This_Matters` sections, the generic RTL coding
tutorial, fixed P1 candidate counts, automatic literature/survey fan-out, repeated
SVA/coverage rounds, and the automatic cross-review/fallback ladder.

The spec analyst no longer forces an 18-step procedure, staged approval rounds,
or sample timing requirements. Unknown timing fields remain null. P1–P5 shared
workflows express contracts and dependencies; team mode adds ownership and
coordination only when requested. Active lint/synthesis prompts consume configured
tools instead of requiring every linter or assuming Yosys/NanGate45/a process node.
The explicit cross-review action remains available.

Policy source lives in `plugin_docs/agent-lib/policies/`, with a manifest and
`scripts/sync_agent_policies.py`. It inlines 32 policies and four tool profiles into
their consumers, removing 36 policy/profile entries from skill discovery while
preserving referenced assets. Six sequential/team orchestrator pairs share agent
identities and packaged `runtime/workflows/`. Synthesis reporting uses deterministic
scripts instead of two wrapper agents.

Current inventory: 91 agents, 55 discovered skills (50 actions, four conventions,
one internal routing reference), and 17 hook scripts. The branch's existing model
role map remains 36 Fable, 53 Opus and two Sonnet; no effort overrides were added.

### Phase 1b: hook integrity

`skill-event-util.sh` and `rtl-skill-expansion.sh` handle qualified direct commands
and Skill calls consistently, reject foreign/poisoned events, and run P5B preflight
before state changes. PreToolUse performs preflight only; accepted PostToolUse
writes phase/completion state. Event-specific hook output matches the API schema.

Stop budgets are session-scoped. User decisions and infeasibility take precedence
over auto-continue. Missing work gets a bounded reminder, without a review ladder.
Background activity refreshes loop activity; stale pending work produces a notice.
Fresh live runner evidence yields the verification gate, and new tracked content
re-arms it inside persistent loops. Unchanged work remains bounded.

Team ownership comes from the main-thread hook event and a config fingerprint,
not a model-authored leader ID. Unknown ownership enforces gates conservatively.
State/audit writes reject symlink trees. Audit starts cover every RAT agent;
completed spawn counts come from completion events. JSON helpers support a selected
Python >=3.9, cache state reads, and warn when no reliable parser is available.

The edit tracker normalizes project-relative paths, `..` and assignment prefixes,
deduplicates paths, ignores read-only commands and discarded worktree scope, and
marks Phase 6 stale for PPA edits too.

### Phase 1c: template lifecycle

Hooks no longer install files. The explicit installer has a no-write dry run and
hash-based ownership in `.rat/template-hashes.tsv`. It updates unchanged managed
copies; user-edited or unknown legacy files are preserved with proposed updates
under `.rat/template-updates`. Symlink, hardlink and escape checks protect targets.

`template-catalog.json` covers 22 scripts/helpers/rules/guides, including the added site setup helper. The catalog rejects
changed content without a version bump. Existing projects can request an explicit
`--update`; this session did not overwrite an external user project.

### Phases 1d–2: measured verdicts

`scripts/verify_evidence.py` snapshots source, filelist and include dependencies,
options, build artifacts, and logs. Run-only rejects changed build/input content.
Separate runtime completion prevents compiler output from supplying a false PASS.
Nonzero exits, explicit failures and timeout/stall/hang evidence take precedence;
compile-only is COMPILED, and missing completion is INCONCLUSIVE. Gates validate
current hashes and ignore a bare verify-done marker.

Unit/integration templates require at least one actual check, honor `+timeout`,
emit explicit PASS, and use `$fatal` for failure/timeout. Regression runners bind
expanded inputs and require all seeds and coverage merges. Atomic seed-result
publication prevents a missing result from shrinking the denominator into PASS.
Coverage exclusions use a structured/content-bound approval, not a permanent
marker.

SpyGlass uses SV12/type-verilog setup, include/define mapping, Tcl error handling,
and recognized goal summaries. An unknown report format is INCONCLUSIVE. DC/Genus
require the appropriate declared library unless the user explicitly selects an
unmapped exploratory run. DC PPA optimization requires a real `.db`; an unmapped
result is not signoff. Phase 6 staleness and user-decision gate ordering are fixed.

### Phase 3: execution

`scripts/eda_runner.py` and matching tool-runner shims consume executable overrides,
site environments (bash/csh/tcsh), explicit license-wait arguments, process-group
wall/stall limits, and process exit status. Make/cocotb uses temporary tool shims.
Bundled, installed and remote wrappers each use matching runtime helpers.

Docker preserves absolute mounts, working directory and uid/gid, with a writable
HOME and read-only external helper mounts. Nested commands stay inside the current
container. SSH/LSF synchronize one whole wrapper invocation, stage a private helper
bundle, fetch declared outputs, use explicit shell invocation, and preserve actual
job status. LSF submission success or transport completion is not functional PASS.
Timeout cancels only the submitted job. No rsync deletion is used.

The missing historical companion spec is replaced by the
[execution contract](../specs/2026-11-17-eda-runner-contract.md), also packaged under
`runtime/`. License flags are site configuration, not guessed vendor defaults.
TB cycle budgets plus process wall/stall limits replace a separate generic watchdog
module; a silent licensed tool need not enable the optional stall limit.

### Phase 4: setup

Configuration generation seeds trusted machine settings, consumes tool paths and
per-tool environments, preserves remote paths and user NAND2 area, refreshes
automatically chosen preferences, and supports `technology.db`, Liberty and SAIF.
Correct CDC binary probes and STA/power categories are included.

Readiness is scoped to the requested phase and verification framework, including
BFM, multiclock and signoff needs. Remote tools without an actual probe are not
reported ready. The setup skill and post-install check no longer require all OSS
tools for every task. No architecture-model toggle or effort setting was added;
the branch's role map supersedes the historical roadmap proposal.

### Phase 5: executable gates and evaluation

`scripts/gates/phase_gate.py` checks artifacts, JSON contracts and recorded judgment.
P1–P3/P5 handoffs require resolved material ambiguity; verification items identify
the requirement/acceptance criterion and expected result. A structural handoff PASS
is not a replacement for measured functional or silicon evidence.

`evals/` and `scripts/eval_prompts.py` provide fixed judgment and English/Korean
routing cases, comparison to `0db2ba5`, sanitized results and provider-unavailable
circuit breaking. They use native read-only Claude/Codex clients, without response
retries or effort overrides. Package files include workflows, runtime contracts
and the template catalog; generation consistency is checked automatically.

## Final validation

- `pytest tests/unit -q -o addopts=--tb=short`: **2292 passed, 16 skipped** in
  170.55 seconds after the SSH setup follow-up. Skips are not claimed as passing checks.
- Real Verilator 5.032, extracted under `/tmp` without a global install:
  **8/8 expected verdicts**, unit and integration templates each covering PASS
  (exit 0), mismatch FAIL (134), zero-check FAIL (134), and cycle TIMEOUT (134).
  [Saved results](../../evals/results/2026-11-17-verilator.json) and
  [reproduction harness](../../evals/runtime/check_verilator_templates.py).
- GPT-6.1 Sol: baseline and current each pass **4/4 judgment + 4/4 routing** cases.
  The four judgment payloads total **140035 -> 73084 UTF-8 bytes, 47.8% less**.
  This measures the selected prompt payloads, not billed tokens, full session
  context, latency improvement, general design quality, or confidence calibration.
  [Saved model results](../../evals/results/2026-11-17-sol.json).
- Qualified plugin routes and bare names are equivalent. Confidence in identifying
  ambiguity does not settle the design; a rerun conditional on clarification is
  not an immediate extra review. Grader corrections applied equally to saved
  baseline and current responses. The later spec-analyst revision received one
  fresh affected-case evaluation; intermediate revisions remain in local logs.
- Fable/Opus requests returned API 429 weekly usage limits before any completion.
  Remaining requests were skipped. There is no model behavior result for them.
- `git diff --check`, template catalog, policy sync check, generated phase maps,
  Step 0 dry run and SessionStart export consistency pass. Packaging contracts
  pass in the unit suite. After the final SessionStart prose cleanup, the three
  affected structure/runtime/output test modules passed **251/251** checks.

## Qualification still required outside this repository

At the initial closure, Docker, SSH/LSF and licensed tools had only controlled
fixture coverage. The follow-up below supports private site qualification. Docker, LSF,
other licensed capabilities, foundry libraries and site report formats still need
qualification; the SSH smoke is not a full site campaign. Verilator checks validate template/runner
classification on a tiny DUT, not codec conformance or silicon signoff.

Interactive tmux/iTerm team membership, in-process idle behavior, persistent-loop
host behavior and observer identity remain native-session qualification items.
The plugin does not declare observer agents; hook-owned identity does not invent
information absent from host events.

The source resolver supports common recursive filelists and conservative include
closure, including configured roots and UVM paths in the selected tool environment.
It is not a full SystemVerilog/vendor preprocessor. Unsupported or unresolved syntax
fails with a diagnostic rather than creating unverifiable evidence.

Next deployment action is site qualification with configured tools and the saved
fixtures. Release/versioning and installed-plugin updates remain separate actions.


## Follow-up: LLM-assisted SSH installation (2026-11-17)

Setup accepts an execution-site request, discovers host facts, prepares a reusable
named JSON profile, and applies project configuration without asking the user to
transcribe paths. `scripts/eda_setup.py` provides discover/probe/configure, no-write
previews, a private per-project workspace and preserved user overrides. Profiles
are per user/site; no user's host becomes a plugin-wide default.

Remote readiness explicitly probes paths/frameworks with `--probe-remote`, honoring
chosen tools without claiming license or design PASS. Supported Python discovery,
tcsh-compatible SSH commands and zero-exit loader-failure detection are implemented.
Matching failed probes prevent automatic selection; a changed configuration
invalidates the old probe fingerprint. Details load on demand, without mandatory
all-tool interviews or repeated successful checks.

Real site profiles, SSH aliases, usernames, installation/library paths and raw
probe/qualification reports belong in the user's private data directory outside
this repository. They must not appear in plugin docs, examples, tests or evals.
Repository fixtures use synthetic `.invalid` hostnames and invented paths. The
setup helper refuses private JSON destinations inside the plugin repository;
packaging excludes private state/profile/report directories.

Validation before the privacy cleanup: the complete unit suite passed **2292 tests**, with **16 skips**, in 170.55 seconds. Site-specific qualification records
are kept privately and are not published as repository evaluation artifacts.
All changes remain uncommitted on `try-2.0`; installed plugin code was not updated.

Privacy follow-up: real site records were moved to private user storage, outside
the repository. Setup destination guards and package exclusion checks pass;
public source and package content checks find no private site identifiers.
The original user-specific records were never committed.

## Follow-up: executable contracts (2026-11-19)

P5B now requires the exact nested P5A verdict and a JSON parser. P6 runs the
handoff CLI before starting reviewers. It rejects incidental or conflicting
PASS text. The CLI also rejects malformed ambiguity and verification entries
with a structured failure. A recorded handoff does not replace measured evidence.

CI regenerates policy blocks and hook maps in its checkout and attaches a patch
when they drift. Template revisions retain a separate integrity check. On PRs,
tag pushes and manual runs, the runtime job exercises 6,000 seeded log cases and
eight real Verilator runs. It retains synthetic simulation logs for reproduction.
The [contribution guide](../../CONTRIBUTING.md#where-to-enforce-a-rule) describes
where code, static checks, verification, prompts and human decisions belong.

Local verification passed the 6,000 generated cases, all eight Verilator checks,
and ShellCheck on the changed hook. A clean generator checkout passed, and a
stale generated file produced a patch and nonzero status. The full unit run had
2,323 passes, 16 skips, and one obsolete P6 prompt wording assertion. After
replacing it with behavior coverage, all 175 affected tests passed. GitHub Actions
execution remains unmeasured locally.
