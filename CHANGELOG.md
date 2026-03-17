# Changelog

All notable changes to `rtl-agent-team` are documented in this file.

The format is based on Keep a Changelog and follows the repository's released version history in git.
Versions `0.6.1` and `0.6.2` do not appear in the recorded release history, so the changelog covers the released versions that exist in the repository plus current unreleased work.

## [Unreleased]

### Added
- Test plan generation (Wave 0 Step 0b) before RTL implementation — TDD-style verification (GAP 1)
- New `test-plan-writer` agent for spec-driven test scenario derivation (ECP/BVA/STT/DT)
- P4→P5 coverage handoff — P5 CDTG uses Tier 2 baseline for incremental gap closure (GAP 2)
- Structured acceptance criteria (`ac_id`) in iron-requirements.json with criteria-level traceability (GAP 4)
- AC-level RTM, compliance-checker forward-trace, and coverage-analyst gap reporting
- Cross-phase requirement decomposition chain (`traces_to` field) — REQ-F→REQ-A→REQ-U completeness check (GAP 3)
- Automated structural verification in Wave 4 code review — FSM completeness, pipeline depth, port mapping (GAP 5)
- Mandatory error injection at Tier 2 — reset recovery, backpressure stress, boundary arithmetic (GAP 6)
- Backward traceability — test failure → requirement impact analysis with BLOCKING/WARNING/UNTRACEABLE (GAP 7)
- Backward-compatible fallback: projects without `acceptance_criteria` or `traces_to` use `req_ids` only

### Fixed
- Filesystem verification in 3 auxiliary orchestrators (autopilot, p4-rtl-sanity, uarch-to-verify)
- Requirements.json reference added to auxiliary orchestrator TB generation prompts

## [0.8.4] - 2026-03-17

### Verified
- Final comprehensive Codex cross-review R1+R2 consecutive LGTM (no code changes)

## [0.8.3] - 2026-03-17

### Fixed (final cross-review R1-R5)
- P4 policy line 19 Wave 6b summary includes covergroups + codec conformance
- Skill count 91→92 across all surfaces (README, README_kr, CLAUDE.md, marketplace)
- CLAUDE.md policy breakdown 30→31 policies
- codec_conformance schema PASS/FAIL/N/A (FAIL state representable)
- Step 5a explicitly writes codec_conformance into result JSON

## [0.8.2] - 2026-03-17

### Fixed (Codex cross-review R1-R11)
- Tier 2 PASS definition aligned across all surfaces (orchestrator, team, policy)
- codec_conformance field in result schema (PASS/FAIL/N/A), Step 5a writes it
- func_coverage + codec_conformance in completion criteria (3 skills x 2 files)
- P4 policy Wave 6b gate summary aligned with full contract
- gap_fill_round non-executed default clarified (before/after: null)
- Step order corrected: 5a(codec) → 5b(gap-fill) → 5c(gate)
- Step 5 requires ALL schema fields with explicit defaults
- Team gate matched non-team exactly (per-feature req_ids, explicit codec_conformance)
- Tier 2 checklist: func_coverage + codec_conformance items added

## [0.8.1] - 2026-03-17

### Added
- New `rtl-test-design-policy` skill — ECP, BVA, state transition, decision table testing
- testbench-dev Investigation Protocol steps 4a-4e (systematic test vector derivation)
- Error injection plan step in testbench-dev (protocol violations, reset, backpressure)
- Tier 2 functional coverage bins (FSM states, valid/ready cross-coverage)
- Tier 2 lightweight CDTG gap-fill round (Step 5b in unit-test orchestrator)
- Tier 4 integration result JSON with req_ids traceability
- SV TB template boundary value + FSM + interface testing guide
- `func_coverage` and `gap_fill_round` fields in Tier 2 result JSON schema

### Fixed (Codex R1-R4)
- Gate moved after codec conformance (Step 5a before 5c)
- "valid without ready" reclassified as backpressure stress (not protocol violation)
- "return to IDLE" replaced with "spec-defined reset state"
- Functional coverage policy split: gate-enforced vs recommended guidance

## [0.8.0] - 2026-03-17

### Fixed (Codex cross-review R1-R13)
- Team P4 orchestrator Wave 6a/6b alignment (summary, task graph, W9 deps)
- Stream B content quality gate in orchestrator gate + policy checklist
- rtl-verify-stop-gate FILES double-escaping removed
- compliance-checker prompt uses upstream_iron/target_artifacts contract
- req_ids enforcement in non-team P4 gate, policy, and Tier 2 orchestrator
- P4 completion criteria updated for both implement + implement-team
- Wave 10 forward-trace: compliance-checker (not requirement-tracer)
- iron-requirements.json in defense-in-depth scan (both orchestrators)
- W9 depends on t_tier2 (prevents unit_results invalidation)
- Team t_tier2 created after loop with correct blockedBy (not prematurely runnable)
- compliance-checker Glob deferred to execution time
- W10 blockedBy flattened (no nested lists)
- Stale requirement-tracer paragraph removed
- phase-registry.json + skill-completion-criteria.json in package.json files
- rtl-p4s-unit-test iron_upstream populated for standalone support

## [0.7.9] - 2026-03-17

### Added
- P3-10: `phase-registry.json` single source of truth + `scripts/generate-phase-maps.sh`
- P3-11: `emit_stop_block()` / `emit_post_continue()` in hook-output-util.sh
- Wave 6b (Tier 2 unit test) mandatory in 10-Wave pipeline
- Wave 8 expanded with timing contract verification
- Wave 10 requirement-tracer forward-trace dispatch
- Tier 2 coverage targets (FSM>=50%, line>=60%) and `req_ids` tracing
- Stream B promoted to P5 required artifacts + content quality gate
- `sim/**/*_unit_results.json` in P5 required artifact map

### Changed
- 10 hooks migrated to shared output helpers (P3-11)
- 3 hook files use GENERATED PHASE_MAP markers (P3-10)
- Tier 2 completion criteria: `ref-mismatches-zero|coverage-met|req-ids-traced`

### Fixed
- Wave 6b scheduling: global after all 6a (not per-module)
- requirement-tracer scoped to iron-requirements.json (REQ-U-*)
- phase-registry.json aligned with artifact-map glob pattern
- \\n double-escaping in emit_stop_block messages

## [0.7.8] - 2026-03-17

### Added
- `TestMappingSyncParity` (5 tests) — cross-map drift detection for phase mapper, compliance bootstrap, agent mappings
- Python parser mode testing via `RTL_FORCE_PYTHON_PARSER` env var + 3-mode parametrization
- `scripts/bump-version.sh` — automated 6-file version bump with `--dry-run`
- `scripts/check-new-skill.sh` — 8-location skill registration validator
- `.github/workflows/ci.yml` — GitHub Actions CI (pytest + shellcheck)
- `TestHookIntegrationChain` — skill→bootstrap→spawn-context end-to-end test
- `TestFlockUtilStaleLock` — stale lock reclaim tests
- Audit session-id path traversal security tests (4 tests)
- 7 missing completion criteria for pipeline-critical skills
- `.shellcheckrc` — SC1090/SC1091 suppression for dynamic source paths
- `plugin_docs/hook-development-guide.md` — hook development documentation
- Template version markers (`rat-version: 0.7.8`) + `--update` flag for `install_project_templates.sh`
- P3-10 (phase registry) and P3-11 (hook output standardization) implementation plans

### Changed
- Extract compliance-gate logic to `hooks/lib/compliance-gate-util.sh` (behavior-preserving)
- Consolidate duplicate test setup (`datetime` import, `_setup_marker`)
- CI uses `tests/requirements-test.txt` for dependencies

### Fixed
- Compliance gate: upstream_challenge messaging in stop gate
- Compliance gate: clear stale overrides (strategy, budgets, authority, prompt) on PASS
- Compliance gate: clear stale state when compliance-report.json absent
- Compliance gate: clear upstream_challenge on fixable FAIL (downgrade from infeasible)
- Compliance gate: ignore zero-value budget overrides (> 0 check)
- Compliance gate: always run stale-state cleanup regardless of pending criteria
- Compliance gate: recheck completion after preprocessing clears last criterion
- `bump-version.sh`: fix sed BRE escaping for markdown bold
- `check-new-skill.sh`: fix false positives via `grep_case_exact()`, skip sub-phase skills
- `install_project_templates.sh`: use `sort -V` for newer-only version comparison

## [0.7.7] - 2026-03-16

### Fixed
- Add missing Step 0 Context Bootstrap to `review-refactor-orchestrator`
- Fix heading level consistency in `p4-rtl-sanity-orchestrator` (`###` → `##`)
- Add `rtl-p6-design-review` to compliance bootstrap case branch
- Correct CLAUDE.md Step 0 orchestrator count (29→30, only p5a/p5b excluded)

## [0.7.6] - 2026-03-16

### Fixed
- Hook execution order: compliance state bootstrap now runs before spawn context manifest
  write, fixing non-deterministic `upstream_iron` in `spawn-context.json`
- Add `rtl-p4-block-parallel` to compliance bootstrap, phase mapper, spawn-context agent
  mapping, and test coverage tables
- Add `rat-p4p5-impl-verify` to compliance bootstrap case branch
- `json-util.sh` python mode: use `json.dumps()` for list/dict types instead of `str()`
  (fixes malformed JSON on systems without jq)
- CLAUDE.md: add `step0-template.md` to agents/lib/ inventory

## [0.7.5] - 2026-03-16

### Changed
- Renamed `rtl-dse` skill to `rat-dse` (consistent with `rat-` prefix for top-level pipeline entry points).
- Renamed `rtl-dse-policy` skill to `rat-dse-policy`.
- Updated all routing tables, hook mappings, cross-references, and tests.

## [0.7.4] - 2026-03-15

### Added
- 3-way prediction expert split: `vcodec-intra-pred-expert`, `vcodec-me-expert`, `vcodec-mc-expert`
- 14 new knowledge files for deepened domain expertise (intra, ME, MC, entropy, TQ, filter)
- Block-parallel Phase 4 RTL development (`rtl-p4-block-parallel` skill)
- `rat-ultraloop` autonomous implement-review-improve loop with design freeze
- Interface policy and contract test policy skills
- `p4-block-parallel-coordinator` and `p4-block-worker` agents
- `ultraloop-reviewer` READ-ONLY autonomous review agent

### Changed
- `vcodec-chief-standard-expert`: updated for 6 sub-domain experts (was 4)
- `domain-consult`: 3-way prediction routing with keyword partition
- `stop-gate.sh`: ultraloop state detection + 30-min auto-continue
- `manifest.json`: updated agent_coverage, agent_coordination, 14 knowledge registrations

### Removed
- `vcodec-prediction-expert` (replaced by intra/ME/MC 3-way split)

## [0.7.3] - 2026-03-15

### Added
- Cross-review convergence improvements: agreement ledger, anti-oscillation rule, stability criterion
- Agreement ledger injected into follow-up prompts to prevent context-reset re-raises
- Anti-oscillation: settled items cannot be re-raised without new evidence
- Stability requires 2+ consecutive APPROVE rounds with no still_disagree and no oscillation
- pending_confirmations separated from agreement_ledger (no premature settlement)
- resolved_items now required in review schema

## [0.7.2] - 2026-03-15

### Fixed
- Clarified P3 gate iron vs zero-opens Glob comments (prevent LLM misread)
- Added explicit trial promotion commit step with worktree_branch capture
- Added critique closure verification (HIGH findings must be RESOLVED or JUSTIFIED)
- Specified explicit phase paths in self-critique artifact reading


## [0.7.1] - 2026-03-15

### Added
- Extended rtl-dse to Phase 1→3 with self-critique loop and trial iteration
- Phase 3 produces C/SystemC BFM (not RTL), with DPI bridge template
- Self-critique: agent reviews P1→P3 output, re-runs with findings
- User-controlled trial iteration via git worktrees with compliance-based comparison
- ADR invalidation recovery: re-generate candidates + re-ask user
- P1 ambiguity gate in DSE orchestrator

### Changed
- compliance-checker: supports custom output path via prompt
- P3 orchestrator: open-requirements.json intake fully conditional
- DSE policy: Phase 3 gate definition, trial comparison protocol, self-critique protocol


## [0.7.0] - 2026-03-15

### Added
- **Cascading Requirements with Iron/Open Taxonomy**: Phase-gated requirement lifecycle system
  - `iron-requirements.json` (settled rules) + `open-requirements.json` (research homework) per phase
  - Authority hierarchy: P1(functional) > P2(architecture) > P3(micro-architecture)
  - `compliance-checker` agent (Opus): independent upstream iron requirement verification
  - Upstream Challenge Protocol: infeasibility detection with quantitative PPA evidence
  - Authority-differentiated escalation budgets in skill-completion-gate
  - Iron Requirements Protocol injected via SessionStart hook
- New compliance-state.json bootstrap in `rtl-phase-state-bootstrap.sh`
- Upstream iron paths propagated through spawn-context manifests
- 5 new completion criteria: `iron-open-classified`, `ambiguity-pass`, `open-resolved`, `zero-remaining-opens`, `compliance-pass`
- Schema validation tests for iron/open/compliance JSON structures

### Changed
- `spec-analyst` produces `iron-requirements.json` + `open-requirements.json` (replaces flat `requirements.json`)
- P1/P2/P3 orchestrators: open resolution steps, compliance check steps, ambiguity gate references
- P1/P2/P3 policies: iron/open schema definitions, classification verification rules
- `arch-designer` and `uarch-designer` updated to reference `iron-requirements.json`
- P2 `open-requirements.json` made optional throughout (Glob-first conditional Read)
- `skill-completion-criteria.json`: new criteria for P1-P3 base skills
- `rtl-orchestrate/SKILL.md`: Iron Requirements Protocol added to routing source of truth
- 10 action skills (P1-P5 base + team) updated with iron/open and compliance references

## [0.6.15] - 2026-03-13

### Changed
- Removed deprecated `rtl-regression-run` skill; migrated scripts to `rtl-p5s-func-verify/scripts/`.
- Removed `(EXPERIMENTAL)` tags from stable hooks (`rtl-spawn-context`, `rtl-audit-subagent`).
- Consolidated 3 PostToolUse hook entries into single `Edit|Write|Bash` regex matcher.
- Extracted 3 shared helpers in `rtl-edit-tracker.sh` (211→199 lines, zero output change).
- Created `sync_step0.sh` + `step0-template.md` for Step 0 bootstrap management.

## [0.6.14] - 2026-03-13

### Fixed
- Fixed remaining `"name"` key in `scripts/install-slang-server.sh` LSP template.
- Completed 0.6.12 CHANGELOG entries for `f0bb002` (hook robustness, rat-tutorial rename, syn script fix, 13 new tests).

### Changed
- Relaxed version bump checklist wording from "single commit" to "single release-prep batch".
- Scoped version bump grep to active release files only (excludes CHANGELOG and artifacts).

## [0.6.13] - 2026-03-13

### Fixed
- Fixed LSP config: removed unrecognized `"name"` key from `.lsp.json` files (including `scripts/install-slang-server.sh` template) that caused plugin load errors in Claude Code.

### Changed
- Added version bump checklist (item #12) to Plugin Development Best Practices in CLAUDE.md.
- Synced README.md and README_kr.md Marketplace table versions to 0.6.13.

## [0.6.12] - 2026-03-13

### Fixed
- Fixed codex cross-reviewer: mkdir safety, shell-safe tmux expansion via `$PROMPT_FILE`, merge-base diff range, and session resume logic.
- Reverted codex session resume (CLI flags incompatible); improved merge-base fallback chain (local → origin → root commit).
- Fixed codex cross-reviewer consistency: N/R variable scoping, round-loop context, Step 3 repetition wording, Mode A tmux requirement.
- Fixed DRY hook violations, pipe-subshell bug, and race condition found in quality review.
- Fixed `rat-tutuorial` typo → renamed to `rat-tutorial` with routing entry update.
- Fixed hook robustness: `jsonu_escape` tab/newline handling, `rtl-team-progress.sh` JSON output on all exit paths, `rtl-edit-tracker.sh` Phase 6 stale detection deduplication.
- Fixed unbound variable `$_DFF_` in `run_syn.sh` grep patterns.
- Fixed 8 Claude-Codex consensus review findings.
- Fixed 21 Claude-Codex cross-review findings across 10 rounds.
- Fixed 10 Claude-Codex Phase 2 cross-review findings across 7 rounds.

### Added
- Added `test_json_util.py` (50 tests): direct unit tests for all `json-util.sh` parser functions across default and sed-fallback modes.
- Added behavioral tests for `rtl-project-init-advisor.sh`.
- Added 13 tests: team-progress hook behavioral (4), ADR template structural (3), domain-expert agent (3), tutorial rename (3).
- Integrated Ouroboros evolutionary patterns into Phase 1-3 pipeline.

### Changed
- Increased Codex cross-review execution timeout from 300s to 1200s, with the tmux poll ceiling raised to 1230s.
- Deduplicated codex cross-reviewer Step 4b: replaced duplicated execution block with explicit reference to Step 2b procedure.
- Removed dead current-phase fallback from codex cross-reviewer agent.
- Wired 4 tool-profile skills to matching specialist agents.
- Updated CLAUDE.md: added 3 audit hooks to enforcement table, clarified POSIX sh scope, documented intentional design decisions.
- Improved codex-cross-reviewer: file-first data exchange pattern.
- Renamed `_BOOL_VAL` to `JSONU_BOOL_VAL` for naming convention consistency.

## [0.6.11] - 2026-03-11

### Added
- Added Codex CLI cross-review as mandatory 2nd reviewer for all phase orchestrators (P1-P6), with `codex-cross-reviewer` agent and `codex-cross-review` skill.
- Added ADR (Architecture Decision Record) generation to all orchestrator paths and synced policy checklists.

### Changed
- Renamed `rtl-spec-to-uarch` to `rat-p1p3-spec-uarch` and `rtl-uarch-to-verify` to `rat-p4p5-impl-verify` for consistent `rat-*` prefix naming.
- Added legacy state file migration for `rat-*` renames to ensure backward compatibility.
- Updated agent/skill counts across documentation (87 agents, 88 skills, 14 hook scripts).
- Bumped `rtl-agent-team` to `0.6.11`.

### Fixed
- Fixed Round 2+ Codex CLI execution to match Step 2b timeout and fallback behavior.
- Fixed tmux timeout handling, completion marker substitution, and related test coverage.
- Fixed cross-review findings: auto-detect ordering, artifact names, re-validation flow, and tests.

## [0.6.10] - 2026-03-10

### Added
- Added `rat-plugin-debug` skill for plugin diagnostics (version, EDA tool status, state files, hook health).

### Changed
- Reclassified EDA tool requirements: yosys moved to Optional (Phase 5B+), slang promoted to Required (at least one of verible/slang needed).
- Separated local/global install modes in `rat-setup` — LLM executes local installs directly; global mode prints sudo script for user.
- Renamed `rtl-autopilot` to `rat-auto-design` to avoid OMC keyword collision.
- Fixed autopilot state schema: added top-level `status` field for stop-gate.sh compatibility.
- Bumped `rtl-agent-team` to `0.6.10`.

## [0.6.9] - 2026-03-09

### Added
- Added a `SessionStart` readiness hook for the optional `systemverilog-lsp` plugin to detect missing `slang-server` and guide `local` / `global` / `skip` installation choices.
- Added a dedicated `plugins/systemverilog-lsp/scripts/install-slang-server.sh` helper and execution-based runtime contract tests for the new readiness flow.

### Changed
- Bumped `rtl-agent-team` to `0.6.9` and `systemverilog-lsp` to `1.1.1` across plugin manifests, marketplace metadata, and installer metadata.
- Updated `README.md` and `README_kr.md` to reflect the current plugin versions and the `systemverilog-lsp` readiness/install guidance.

## [0.6.8] - 2026-03-07

### Added
- Added `rat-tutuorial`, a user-invocable interactive tutorial skill for the RTL Agent Team workflow.
- Added dynamic domain expert discovery infrastructure for `domain-packages/*/manifest.json` and project-local `.claude/domain-experts/*.md`.
- Added `agents/domain-expert.md` and `agents/lib/domain-expert-discovery-protocol.md` to support manifest-driven local expert execution.
- Added `domain-packages/expert-template.md` as the canonical template for local domain expert definitions.

### Changed
- Integrated domain expert discovery into Phase 1 through Phase 5 orchestrators.
- Updated `README.md`, `README_kr.md`, `CLAUDE.md`, `CONTRIBUTING.md`, and marketplace metadata for current agent/skill counts and naming consistency.
- Aligned the tutorial project structure with the actual directories and helper scripts created by `rat-setup`.

### Fixed
- Fixed tutorial command examples to use the plugin namespace consistently: `/rtl-agent-team:<skill>`.
- Fixed stale agent/skill count references across developer-facing documentation.

## [0.6.7] - 2026-03-07

### Added
- Added decoder block-level conformance guidance in `domain-packages/video-codec/knowledge/block-level-conformance.md`.
- Added throughput invariant guidance for codec decoder pipeline decisions.

### Changed
- Integrated block-level conformance methodology into Phase 2 through Phase 5 flows, including reference model, BFM, unit-test, and conformance workflows.
- Updated codec architecture and Phase 3 policy prompts to check throughput feasibility earlier.

## [0.6.6] - 2026-03-07

### Changed
- Enforced SystemC C++ output for Phase 3 BFM generation and tightened prompts to prevent SystemVerilog fallback.
- Promoted SystemC from optional tooling to a required dependency in `rat-setup`.
- Added a pure-C timing-model fallback path when SystemC is unavailable.

## [0.6.5] - 2026-03-07

### Added
- Added `lib/tool-runner.sh` for transparent local-first, Docker-fallback EDA tool execution.
- Added `run_formality.sh` and `run_conformal.sh` template scripts for equivalence checking.
- Added Genus support to the synthesis wrapper flow.

### Changed
- Updated `run_lint.sh`, `run_syn.sh`, and `run_cdc.sh` to use the shared tool-runner abstraction.
- Updated `install_project_templates.sh` and `rat-setup` to deploy the new helper scripts and Docker-aware workflow.
- Added Docker cleanup handling to Phase 5 verification exits.

## [0.6.4] - 2026-03-07

### Fixed
- Added `hookEventName` to hook JSON outputs for schema-compliant non-Stop hook responses.

## [0.6.3] - 2026-03-07

### Changed
- Hardened the native team-mode hook flow and supporting tests after the `Orchestrator as Teammate` refactor.
- Expanded documentation and artifact mapping around team execution and Phase 6/P5 interactions.

### Fixed
- Fixed multiple hook and test defects affecting P1 through P3 team execution and schema handling.

## [0.6.0] - 2026-03-07

### Added
- Added audit logging and decision-visualization support around pipeline execution.
- Refactored native team mode so orchestrators run as teammates instead of the older execution pattern.

### Changed
- Reworked team coordination semantics for P1 through P5 native teams.
- Strengthened Stop-hook schema handling for the new orchestration model.

## [0.5.0] - 2026-03-06

### Added
- Added standardized state schema v3.0 for pipeline progress tracking.
- Added Phase 7 exploration mode to the design flow.
- Added spawn-context manifest/bootstrap support and additional sub-phase orchestrators/policies.

### Changed
- Improved resume behavior and routing/policy synchronization across orchestrators and hooks.
- Updated documentation to reflect the expanded orchestrator set and phase model.

## [0.4.0] - 2026-03-05

### Added
- Added native team-mode orchestrators for Phase 1 through Phase 3.
- Added session-scoped state isolation and team-worker protocol support for multi-agent team execution.
- Added video-processing domain experts and V4L2-oriented knowledge base content.

### Changed
- Hardened team-aware hooks, lock handling, and resume behavior for native team mode.
- Expanded documentation and branding around team execution and marketplace presentation.

## [0.3.0] - 2026-03-05

### Added
- Added Claude Code native team integration for parallel Phase 4 and Phase 5 execution.
- Added `rtl-p4-rapid-impl`, split Phase 5A/5B flows, review-refactor workflow, tool-profile skills, and phase-state bootstrap support.

### Changed
- Expanded verification and implementation workflows for larger parallel RTL projects.
- Improved hook safety, retry behavior, and platform compatibility around team execution.

## [0.2.0] - 2026-03-03

### Added
- Added escalation ladders for `rat-auto-design` and skill completion gates.
- Added plugin runtime contract tests for hooks, manifests, and routing.
- Added replayable EDA wrapper workflows, commercial tool support, and hook-driven project template bootstrap.

### Changed
- Unified command discovery under `skills/` and standardized Action Skill first routing.
- Standardized agent frontmatter and routing SSOT synchronization through `rtl-orchestrate`.
- Hardened stop-gate parsing and simplified skill completion behavior to ladder-based retries.

## [0.1.0] - 2026-02-25

### Added
- Initial Claude Code plugin structure for RTL design and verification automation.
- Initial agent, skill, and marketplace packaging for the 6-Phase RTL pipeline.
- Early Docker-based EDA environment support, SystemC/TLM guidance, and simulator/lint/synthesis references.
- Initial domain expert support for codec and video-processing workflows.
- Initial README, Korean README, CONTRIBUTING guide, and declarative plugin packaging.
- Initial test infrastructure, hook system, review artifacts, and progressive-disclosure reference materials.

### Changed
- Evolved the project from a simpler skill set into orchestrator/policy-based workflows with stronger routing and phase gating.
- Split design documents from review verdict artifacts and formalized the 6-Phase pipeline structure.
- Standardized naming conventions, coding rules, and English-only LLM-facing documentation.

### Fixed
- Fixed early marketplace metadata, hook wiring, script paths, version references, and cross-file consistency issues during initial stabilization.
