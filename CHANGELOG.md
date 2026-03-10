# Changelog

All notable changes to `rtl-agent-team` are documented in this file.

The format is based on Keep a Changelog and follows the repository's released version history in git.
Versions `0.6.1` and `0.6.2` do not appear in the recorded release history, so the changelog covers the released versions that exist in the repository plus current unreleased work.

## [Unreleased]

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
