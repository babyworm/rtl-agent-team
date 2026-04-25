# Changelog

All notable changes to `rtl-agent-team` are documented in this file.

The format is based on Keep a Changelog and follows the repository's released version history in git.
Versions `0.6.1` and `0.6.2` do not appear in the recorded release history, so the changelog covers the released versions that exist in the repository plus current unreleased work.

## [Unreleased]

## [0.10.6] - 2026-04-25

### Fixed
- **`marketplace.json` systemverilog-lsp sha now points to the commit,
  not the annotated tag-object.** v0.10.5 pinned `062ea908...`, which
  `git cat-file -t` resolves to `tag` (the annotated tag header
  object), not `commit`. The historical v1.1.3 pin used the commit
  sha (`b1a6c83...`), so v0.10.5 silently broke the project's pin
  convention. Switched to `a874d3248d08606b50b71376c64ed8af99396c97`
  (the commit referenced by v1.1.4).

  Background: `git rev-parse <tag>` returns the tag-object sha for
  annotated tags; the commit sha requires `^{commit}`. They are equal
  only for lightweight tags. The mistake came from running
  `git rev-parse v1.1.4` during v0.10.5 release prep without the
  `^{commit}` suffix.

### Changed
- **CLAUDE.md "Version bump checklist" (item 14)** now includes an
  explicit step for sub-plugin sha pins covering annotated vs lightweight
  tags and the `git cat-file -t` verification — preventing the v0.10.5
  drift from recurring.

### Notes — Claude Code v2.1.x JSON schema migration (v0.10.3 → v0.10.6)
This series addresses the SessionStart hook output schema enforcement
that Claude Code v2.1.x introduced (`hookSpecificOutput.hookEventName`
mandatory, must match the event name; raw-text stdout silently dropped):

- **v0.10.3** — `rtl-orchestrator-inject.sh` rewritten to emit a JSON
  envelope. Markdown JSON-encoded at sync time via
  `scripts/sync_orchestrator_inject.sh`; runtime hook keeps zero
  jq/python dependency. New CI `validate-plugin` job locks the contract.
- **v0.10.4** — `rtl-edit-tracker.sh::_rat_in_ppa_scope` mode read
  switched to `jsonu_get_file_path_string` graceful tier (jq → python →
  sed), reducing direct python3 calls in hook runtime.
- **v0.10.5** — pinned `systemverilog-lsp` v1.1.4 (its
  `slang-server-check.sh` was emitting JSON without `hookEventName`).
- **v0.10.6** (this release) — corrected the v0.10.5 sha pin format
  (commit sha, not tag-object sha) and documented the sub-plugin pinning
  convention so future bumps don't repeat the mistake.

User-facing effect after v0.10.6: a fresh Claude Code session in any
project pulls a coherent, schema-compliant plugin set on next reload.
No more `Hook JSON output validation failed — hookSpecificOutput is
missing required field "hookEventName"` from any rtl-agent-team-managed
hook.

## [0.10.5] - 2026-04-25

### Changed
- **`systemverilog-lsp` sub-plugin pinned to v1.1.4.**
  `.claude-plugin/marketplace.json` updates the `systemverilog-lsp`
  source `ref` from `v1.1.3` to `v1.1.4` and refreshes the pinned
  `sha` accordingly. v1.1.4 fixes the SessionStart hook
  (`hooks/slang-server-check.sh`) JSON envelope — the previous
  release emitted `{"hookSpecificOutput":{"additionalContext":"..."}}`
  without the required `hookEventName` field, which Claude Code v2.1.x's
  hook validator rejected with
  `Hook JSON output validation failed — hookSpecificOutput is missing
  required field "hookEventName"`. The error fired on every session
  startup whenever `slang-server` was missing or off-PATH (the exact
  case the advisory hook is designed to handle), masking the real
  install instructions.

  Net effect for users on the canonical marketplace install: a new
  Claude Code session in any project will pull v1.1.4 on next plugin
  reload and the schema error stops appearing. Cached v1.1.3 installs
  are evicted by the `ref`/`sha` change.

### Internal
- Marketplace versioning is independent from the systemverilog-lsp
  sub-plugin's own SemVer; the README "Marketplace" table is updated
  in lockstep with both bumps so user-visible documentation stays
  consistent.

## [0.10.4] - 2026-04-25

### Changed
- **`hooks/rtl-edit-tracker.sh::_rat_in_ppa_scope` runtime dependency
  reduced.** The mode key read in `.rat/state/ppa-loop-state.json` now
  uses `jsonu_get_file_path_string` (jq → python3 → python → sed
  tiered fallback in `hooks/lib/json-util.sh`) instead of a direct
  `python3 -c "..."` call. The recursive `**` glob match against
  `allowed_edit_scope` still uses a python step (fnmatch + custom
  regex is non-trivial to reproduce correctly in POSIX sh or jq),
  but when neither python3 nor python is available the function now
  returns 1 (out-of-scope) so the RTL verify gate stays active —
  safer to over-track than to silently skip a real RTL change.

  Net effect: hook runtime no longer issues a direct `python3` call
  outside the graceful fallback chain in `hooks/lib/json-util.sh`.
  User-facing behavior is unchanged in the canonical setup
  (jq + python3 both present); environments missing one of them now
  degrade more predictably.

## [0.10.3] - 2026-04-25

### Fixed
- **SessionStart hook JSON schema — marker-present path.** v0.10.2 fixed
  the marker-*absent* branch (minimal envelope) but the marker-*present*
  branch was still emitting ~10 KB of raw markdown via `cat << 'RULES_EOF'`,
  which Claude Code rejected with the same
  `hookSpecificOutput is missing required field "hookEventName"`
  validation error reported by users running in active RAT projects.
  `hooks/rtl-orchestrator-inject.sh` now emits a single JSON envelope
  `{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"<markdown>"}}`
  in both branches. Routing markdown is JSON-encoded once at sync time
  (build step) and embedded inside a single-quoted heredoc, so the
  runtime hook keeps zero jq/python dependency.

### Changed
- **`scripts/sync_orchestrator_inject.sh` now produces a JSON envelope.**
  The build script extracts the routing markdown from
  `skills/rtl-orchestrate/SKILL.md`, runs it through
  `python3 json.dumps(ensure_ascii=False)`, self-validates the encoded
  string, then splices the resulting `cat << 'JSON_EOF' …` heredoc
  between the BEGIN/END markers in the hook. Re-run after editing the
  SSOT block in `skills/rtl-orchestrate/SKILL.md` (no behavior change
  for skill authors; just re-run the existing sync command).
- **CLAUDE.md** documents the new SessionStart output schema in the
  "Plugin Architecture: Dynamic Prompt Injection" section and adds a
  best-practice item ("Hook stdout must be valid JSON when non-empty",
  #15) so future contributors don't reintroduce raw-markdown output.

### Tests
- `tests/unit/test_agent_skill_structure.py::test_rtl_orchestrate_hook_export_is_synced`
  now decodes the JSON envelope and compares `additionalContext`
  against the SKILL export, rather than expecting raw-markdown
  equality.
- `tests/unit/test_plugin_runtime_contract.py::TestSessionStartRoutingBlockContract::generated_block`
  fixture decodes the envelope so existing section-split assertions
  continue to operate on the routing markdown unchanged.
- `tests/unit/test_hooks.py` (`test_rat_marker_triggers_injection`,
  `test_legacy_marker_triggers_injection`,
  `test_orchestrator_inject_fires_with_legacy_dir`) read substrings
  from `hookSpecificOutput.additionalContext` instead of
  `raw_stdout`, matching the new envelope shape.

## [0.10.2] - 2026-04-25

### Fixed
- **SessionStart hook JSON validation error.** `hooks/rtl-audit-init.sh`
  emitted a bare `{}`, which Claude Code now rejects with
  `Hook JSON output validation failed — hookSpecificOutput is missing
  required field "hookEventName"`. Both `rtl-audit-init.sh` and
  `rtl-orchestrator-inject.sh` now emit a minimal valid SessionStart
  payload (`{"hookSpecificOutput":{"hookEventName":"SessionStart"}}`)
  whenever no RAT marker is present, satisfying the schema and exiting
  silently as intended.

### Changed
- **SessionStart marker check simplified.**
  `hooks/rtl-orchestrator-inject.sh` no longer treats generic
  directories like `rtl/` or `docs/` as RTL-project markers
  (false-positive prone — these names are common in non-RAT
  repositories). Only `.rat/` (current) and `.rtl-agent-team/` (legacy
  v0.8.11-) are recognized, matching the contract in
  `hooks/lib/rat-dir-util.sh:rat_is_project()`. When no marker is
  present the hook returns minimal valid JSON instead of injecting the
  ~96-line routing block; per-skill init advisory is handled by
  `hooks/rtl-skill-activation.sh` on demand.
- `hooks/rtl-audit-init.sh` switched its directory check from a hand-
  rolled four-way `[ -d ]` chain to `rat_is_project "$CWD"` for the
  same reason — the old check fired audit-session bookkeeping for any
  repository that happened to contain a `rtl/` or `docs/` directory.

## [0.10.1] - 2026-04-18

### Fixed
- **Python 3.14 compatibility.** CPython 3.14 changed `fnmatch.translate()`
  to emit the `\z` end anchor instead of `\Z`, which broke the
  wrapper-stripping logic in both `validate_patch_scope.py` and the
  embedded matcher in `hooks/rtl-edit-tracker.sh` (unbalanced parenthesis
  when building the `**` regex). Both now strip `\Z` *and* `\z` so
  glob-to-regex translation works across all supported Python 3.x
  versions.
- **macOS BSD `sed -i` incompatibility.** Three GNU-only `sed -i 'EXPR'
  file` call sites were replaced with portable alternatives so the plugin
  works on macOS without `brew install gnu-sed`:
  - `scripts/bump-version.sh` (2 sites) — `mktemp` + `sed > tmp && mv` for
    atomic in-place edits.
  - `scripts/add-rat-protocol.sh` (3 sites) — new awk-based
    `insert_protocol_after_line` helper (BSD's `sed -i "Na\..."` multi-line
    append differs from GNU's and cannot be unified trivially).
  - `skills/rat-auto-design/SKILL.md:75` — one-line `python3 -c` edit of
    `.rat/state/rat-auto-design-state.json` (LLM-visible example that
    previously instructed `sed -i` on a JSON state file).

### Changed
- `agents/lib/step0-template.md` and
  `agents/lib/domain-expert-discovery-protocol.md` now carry the
  audit-output-protocol reference line. These lib files were previously
  skipped silently by `add-rat-protocol.sh` under BSD `sed` and were
  picked up once the script became portable.
- **systemverilog-lsp marketplace pin bumped to `v1.1.3`** (sha
  `b1a6c83627d05b36418e5679be38f4a0a6d26e12`). The standalone repo's
  `v1.1.3` release ships proper docs (`README.md`, `CHANGELOG.md`,
  `.gitignore`) and corrects the `plugin.json` `repository` field
  (was still pointing at this monorepo as a leftover from the split
  point). See <https://github.com/babyworm/systemverilog-lsp/blob/main/CHANGELOG.md#113---2026-04-17>
  for the standalone repo's release notes.
- **systemverilog-lsp split into standalone repository.** The
  `systemverilog-lsp` plugin (formerly bundled at
  `plugins/systemverilog-lsp/`) was extracted to its own repo at
  https://github.com/babyworm/systemverilog-lsp using `git filter-repo
  --subdirectory-filter`, preserving full commit history. The
  marketplace entry now uses a `github` source pinned to `v1.1.2`
  (sha `515d95550e9b0ff6f4056b93bf0e1c65af22aea3`), giving the plugin
  its own independent tag namespace and release cadence so future
  systemverilog-lsp patches don't pollute rtl-agent-team git history
  (this v1.1.2 commit was exactly the case that triggered the split).
  The `version` field was dropped from the marketplace entry per
  Claude Code docs (for non-relative-path sources, `plugin.json` is
  authoritative). The inline `lspServers` definition and `strict:
  false` were also removed since they duplicate the standalone repo's
  `plugin.json` + `.lsp.json`. **No user action required** —
  `/reload-plugins` re-fetches from the new source automatically and
  the cached v1.1.2 install transparently switches to the
  GitHub-sourced copy.

## [0.10.0] - 2026-04-17

### Added
- DC-based PPA optimization loop (Post-Verify stage between P5 and P6)
  - `rtl-ppa-optimize-dc` action skill (one-shot iteration)
  - `rat-ultraloop-ppa` auto-loop wrapper with 30-min auto-continue
  - `ppa-optimizer-dc-policy` reference skill (timing-first heuristic,
    default weights 0.7/0.2/0.1, convergence: streak 3 × |Δ|<2%,
    early-plateau at iter 1–2 × |Δ|<1%, default max_cycles=4)
  - New agents: `ppa-optimizer-dc-orchestrator`, `ppa-optimizer-dc`, `dc-report-parser`
  - `parse_dc_reports.py` — DC `.rpt` → `ppa-report.json` consolidation
  - `compute_delta.py` — weighted Δ + convergence verdict
  - `validate_patch_scope.py` — allowed/frozen scope enforcement for RTL patches
- Pipeline Rules 10 & 11 (policy; Rule 11 enforced inside wrapper)

### Changed
- `hooks/rtl-edit-tracker.sh` skips staleness during active PPA-opt loop
- `hooks/stop-gate.sh` recognizes `mode: "ppa-loop"` for auto-continue
- `hooks/rtl-p6-cascade-gate.sh` flags P6 re-review after `.rat/state/ppa-opt-done`
- `skills/rtl-orchestrate/SKILL.md` routing table extended with two entries
- Component counts: skills 94 → 97, agents 94 → 97

### Requirements
- Commercial synthesis required at runtime: `dc_shell` or `genus` in PATH
- `requirements.json["ppa_targets"]` section needed (scaffold auto-written on first run)

### Fixed
- **systemverilog-lsp bumped to `1.1.2`** (cache-invalidation release; manifest
  version only). The `.lsp.json` fix from `a2c7687` ("remove unrecognized `name`
  key from .lsp.json files that caused plugin load errors in Claude Code") was
  already present in `v1.1.1` source, but users who installed `v1.1.1` *before*
  the marketplace propagated the corrected file received a stale cache that
  Claude Code did not invalidate (the manifest version had not changed). The
  symptom was a noisy `unrecognized_keys` Zod error on every `/reload-plugins`:
  `Invalid LSP server config for ".lsp.json": Unrecognized key: "name"`.
  Bumping to `v1.1.2` forces cache eviction so all stale `v1.1.1` installs
  get the corrected `.lsp.json` on next plugin reload. No file contents
  changed in this release — only `plugins/systemverilog-lsp/.claude-plugin/plugin.json`
  and the `systemverilog-lsp` entry in `.claude-plugin/marketplace.json`.

## [0.9.3] - 2026-04-17

### Fixed
- **Stage B ecosystem gap for commercial CDC tools**: `rat-init-project`'s
  `rat_config.json` template and `generate_config.sh` previously only knew
  `svlens` and `sg_shell` in the CDC category, so `vc_cdc` (Synopsys) and
  `questa_cdc` (Siemens) detected in Stage A by `rat-setup` were not persisted
  into per-project config. Now:
  - `rat_config.json` template lists all four CDC tools (`svlens`, `sg_shell`,
    `vc_cdc`, `questa_cdc`) so user `env_source` / `path` edits survive.
  - `generate_config.sh` `ALL_TOOLS` array scans all four CDC tools, and
    `pick_pref cdc` uses commercial-first priority (`sg_shell → vc_cdc →
    questa_cdc → svlens`) so the preferred CDC tool is auto-selected.
  - `run_cdc.sh` already accepted `--tool vc_cdc/questa_cdc`; this commit
    closes the Stage A → Stage B handoff.

### Docs
- **README Stage A wording corrected** (both `README.md` and `README_kr.md`):
  - "Installs the plugin and all EDA tools. Deploys global coding conventions"
    was misleading — `rat-setup` is fully interactive (Q1 required-tool
    remediation is the only install prompt; Q2 recommended tools are opt-in;
    Q2b commercial tools are scanned, not installed; Q3 rule deployment is a
    yes/no prompt). Stage A now explicitly lists what each Q step does.
- **README Stage B/C enforcement wording softened** — "must run inside" was
  too strong. `rat-init-project` and `rat-auto-design` use CWD-relative paths
  but are not hook-enforced. Rewritten as "should run from inside ... (artifacts
  are created relative to CWD)".
- **"empty project directory" claim dropped** — `rat-init-project` is
  non-destructive, so existing projects are safe. The phrase falsely implied
  a stricter precondition.
- **README EDA Wrapper Scripts table**: `run_cdc.sh` Supports column now lists
  `svlens` explicitly (the script already supported it; only the docs were stale).
- **Stage A Q1/Q2/Q3 prose precision** (README.md + README_kr.md): the first
  follow-up rewrite had minor inaccuracies caught by a second Codex review.
  Corrections:
  - Q1 required set now lists `python3`, `g++`, `make` (previously omitted —
    they are in `skills/rat-setup/SKILL.md` Tier 1 table).
  - Q1 CDC requirement now shows the full "at-least-one" alternatives
    (`svlens OR sg_shell OR vc_cdc OR questa_cdc`).
  - Q2 menu now matches the SKILL.md numbered list exactly: `jq`, `yosys + sby`
    (bundled), `slang-server`, `iverilog`, `gtkwave`. Previously missed
    `slang-server` and split `yosys + sby`.
  - Q3 deployment scope now explicitly lists the three files that get
    deployed (`rtl-coding-conventions.md`, `rtl-verification-gate.md`, and
    the `<markdown_diagram_rule>` block injected into `~/.claude/CLAUDE.md`).
- **Team-mode Phase 1→2 artifact contract migrated to iron/open-requirements**
  (caught by fifth Codex review — HIGH severity): the team-mode orchestrators
  and pipeline skills were still producing, verifying, and consuming the legacy
  `docs/phase-1-research/requirements.json` single-file contract, while
  `skills/rtl-p1-research-team/SKILL.md` and `skills/rtl-p2-arch-team/SKILL.md`
  declared `iron-requirements.json` + `open-requirements.json` as the SSOT
  (per the v0.8.6 Cross-Phase Artifact Functional Consistency principle).
  This made the default `rat-auto-design` team path silently violate the
  declared contract. Fixed in:
  - `agents/p1-research-team-orchestrator.md`: T6f now produces both
    `iron-requirements.json` (settled `REQ-F-*`/`REQ-P-*` with
    `acceptance_criteria`) and `open-requirements.json` (deferred `OPEN-1-*`
    with `research_needed`). T12 verification counts spec features against
    `iron ∪ open`. Phase 1 Gate verifies iron-requirements (required) and
    treats open-requirements as optional.
  - `agents/p2-arch-team-orchestrator.md`: Upstream Artifact Scan and Step 1
    Read both use `iron-requirements.json` (required) + `open-requirements.json`
    (optional).
  - `agents/spec-to-uarch-team-orchestrator.md`: All `requirements.json`
    references (task prompts, gate glob, review prompts, trace reads)
    migrated to `iron-requirements.json` with open-requirements side-context.
  - `skills/rat-p1p3-spec-uarch-team/SKILL.md`: Phase 1→2 artifact gate
    now checks `iron-requirements.json`.
  - `skills/rat-auto-design/SKILL.md`: Team-mode Phase 1 task prompt and
    artifact completeness gate use iron/open contract.

  **Round 6 follow-up**: Round 5 migration was incomplete. The sixth Codex
  review found 7 residual team-path references that the Round 5 commit
  missed — most critically, `agents/p5-verify-team-orchestrator.md` (the
  Phase 5 team coordinator) was not touched by Round 5 at all, so its
  upstream scan, requirement traceability task, final compliance review,
  and cross-review prompt were all still expecting
  `docs/phase-1-research/requirements.json` — a file the migrated team
  Phase 1 no longer produces. Round 6 closes the remaining team-path gap:
  - `agents/p1-research-team-orchestrator.md`: task graph summary (T6f
    description in the "Task Graph" section) and Step 5 output artifacts
    summary now both list `iron-requirements.json` + `open-requirements.json`.
  - `agents/p2-arch-team-orchestrator.md`: Step 5 Codex cross-review input
    artifacts migrated.
  - `agents/p5-verify-team-orchestrator.md`: upstream artifact scan,
    S3.1 requirement traceability task, S3.4 final compliance review, and
    Step 6 Codex cross-review input all migrated to read Phase 1
    `iron-requirements.json` + `open-requirements.json` (and continue to
    read Phase 3 `iron-requirements.json` for REQ-U).

  **Known technical debt (still out of scope)**: the sequential
  (non-team) orchestrators (`p1-research-orchestrator`, `autopilot-orchestrator`,
  `uarch-to-verify-orchestrator`, etc.) and several P4/P5 sub-orchestrators
  still reference `requirements.json`. Codex Round 5/6 intentionally limited
  scope to the team path (`rat-auto-design` default). A follow-up patch will
  migrate the sequential path to match.

- **`skills/rat-auto-design/SKILL.md` Output section Phase 6 path corrected**
  (Codex Round 5 MEDIUM): the Output section described Phase 6 artifacts as
  `docs/phase-6-review/`, but the skill's own execution body, `README.md`, and
  `CLAUDE.md` all correctly place Phase 6 outputs under `reviews/phase-6-review/`
  (Phase 6 is the design review + documentation phase, whose outputs live under
  `reviews/`). The Output section has been rewritten to explicitly split
  `docs/phase-1-research/` through `docs/phase-5-verify/` for design artifacts
  and `reviews/phase-6-review/` for the Phase 6 design note.

- **3 vcodec expert agents had `disallowedTools` vs body Tool Usage
  conflict** (caught by fifteenth Codex review, MEDIUM severity):
  `vcodec-intra-pred-expert.md`, `vcodec-me-expert.md`, and
  `vcodec-mc-expert.md` declared `disallowedTools: Write, Edit` in
  frontmatter, but their `<Tool_Usage>` sections explicitly instructed
  "Use Write/Edit to produce algorithm definition documents". A strict
  Claude Code allow/deny enforcement would block the documented
  workflow. Removed `disallowedTools` from all three frontmatters since
  the body clearly intends them as document-producing experts.
  `vcodec-architecture-expert.md` retains `disallowedTools` because it
  is explicitly declared READ-ONLY in its body and never references
  Write/Edit (so the constraint is consistent). The other 4 vcodec
  experts (`chief-standard`, `filter-recon`, `syntax-entropy`,
  `transform-quant`) had no `disallowedTools` declaration to begin
  with, so no change needed.

- **Test dependency completeness + README marketplace.json path R14
  knock-on** (caught by fourteenth Codex review):
  - `tests/requirements-test.txt` was missing `pytest-cov` and
    `pytest-timeout` even though `tests/Makefile`'s `test-coverage`
    target uses `--cov` and `test-docker` target uses `--timeout=3600`.
    On a clean environment `install-deps` → `test-coverage` /
    `test-docker` would fail before running any tests. Both
    dependencies added with comments pointing to the consuming
    Makefile targets.
  - `README.md:423` and `README_kr.md:422` Marketplace-add instructions
    still referenced the root-level `marketplace.json` short name
    (same category as R13-1, but in README rather than CONTRIBUTING).
    Both qualified to `.claude-plugin/marketplace.json`.

- **`CONTRIBUTING.md` marketplace.json path + `bump-version.sh` stale
  check grep pattern** (caught by thirteenth Codex review, LOW severity):
  - `CONTRIBUTING.md` referenced `marketplace.json` by short name in 5
    places (checklists + plugin-add walkthrough), but the actual file
    is `.claude-plugin/marketplace.json`. Contributors following the
    literal paths would have searched for a non-existent repo-root file.
    All 5 references now use the fully-qualified path.
  - `scripts/bump-version.sh` stale-version validator previously
    grep'd for `"$OLD_VER"` (quoted form only), which catches JSON
    version fields but misses the plain-text `0.9.1` format used in
    the Marketplace table rows of `README.md` and `README_kr.md`.
    The checklist in `CLAUDE.md` rule 14 explicitly lists README
    version rows, so the validator was silently failing to enforce
    what the docs promised. Rewrote the check to use an extended
    regex with word boundaries (`'(^|[^0-9.])'"$OLD_VER"'([^0-9]|$)'`)
    so both quoted and raw forms are caught without false-matching
    `0.9.10`/`10.9.1` substrings.

- **`plugin_docs/eda-setup-guide.md` phantom `generate_config.sh` path**
  (caught by twelfth Codex review, LOW severity): the "After editing
  `rat_config.json`" and troubleshooting sections instructed users to
  run `bash generate_config.sh`, but that script is **not installed into
  the project workspace** — `install_project_templates.sh` only copies
  `run_lint.sh`, `run_syn.sh`, `run_cdc.sh`, `run_formality.sh`,
  `run_conformal.sh`, `run_sim.sh`, and `tool-runner.sh` into the
  workspace. The generator lives at
  `${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/scripts/generate_config.sh`
  and is only invoked by the plugin itself. Following the guide's
  original instruction would have produced "command not found".
  Rewrote the "After editing" section to present two explicit paths:
  Option A — re-run `/rtl-agent-team:rat-init-project` (recommended,
  idempotent, preserves user-edited fields), Option B — invoke the
  plugin path directly with `${CLAUDE_PLUGIN_ROOT}`. All four
  troubleshooting references also updated to point to the correct
  invocation paths.

- **`scripts/add-rat-protocol.sh` orphan → documented in CONTRIBUTING.md**
  (caught by eleventh Codex review, LOW severity): the script is an
  idempotent bootstrap tool that inserts the audit-output-protocol
  reference into agent markdown frontmatter (skips files that already
  have it). Codex flagged it as orphaned because no other file in the
  repo referenced it, suggesting it was dead maintenance surface.
  **Disposition: refute + link**. The script is intentionally kept as a
  contributor utility for adding new agents — it's not dead code, it's
  an under-documented tool. Added a reference to the "에이전트 추가"
  checklist in `CONTRIBUTING.md` so contributors know to run it when
  adding a new agent file. Also flagged `bash scripts/sync_step0.sh`
  for orchestrator-class agents. This resolves the orphan state
  without deleting a useful utility.

- **"absolute rules" lowercase phrasing propagation** (caught by tenth
  Codex review): Round 9 renamed the CLAUDE.md section heading and
  cleaned the exact "Absolute Rules" title from the SSOT, but 11 residual
  lowercase "absolute rules" phrasings were still emitted or asserted
  across CLAUDE.md, SSOT, hook comments, Phase 7 docs, and iron-requirements
  descriptions. Round 10 disambiguates two distinct intents:
  - **Pipeline Rules meaning** (section references): `CLAUDE.md:288`,
    `hooks/rtl-orchestrator-inject.sh:9`, `skills/rtl-orchestrate/SKILL.md:504`,
    `agents/p7-exploration-orchestrator.md:4, 40`,
    `skills/rtl-p7-exploration/SKILL.md:3, 29`,
    `skills/rtl-p7-exploration-policy/SKILL.md:20` — all migrated to
    "pipeline rules" or "pipeline rules (Rule 9)" for Phase 7 exemption
    references.
  - **Iron requirements binding meaning** (downstream authority):
    `agents/spec-analyst.md:17`, `agents/dse-orchestrator.md:390`,
    `skills/rat-dse/SKILL.md:147`, `skills/p1-spec-research-policy/SKILL.md:123`,
    Iron Requirements Protocol in `skills/rtl-orchestrate/SKILL.md:560`
    (regenerated into hook:44) — all migrated to "binding constraints
    for downstream phases" to disambiguate from the Pipeline Rules
    section while preserving the authority=1 semantics.
  - `skills/p1-spec-research-policy/SKILL.md:120` heading "iron-requirements.json
    — Settled Rules (Authority = 1)" renamed to "Settled Requirements
    (Authority = 1)".

  Historical plan/spec documents under `plugin_docs/plans/` and
  `plugin_docs/specs/` intentionally retain the original "absolute rules"
  phrasing as period-accurate artifacts.

- **Pipeline Rules rename propagation + metadata/allowed-tools drift**
  (caught by ninth Codex review): the Round 8 rename of CLAUDE.md's
  "Absolute Rules" section to "Pipeline Rules (policy + enforcement
  map)" was not propagated across the rest of the tree. Round 9 closes
  the gap:
  - `skills/rtl-orchestrate/SKILL.md` (routing SSOT): both the internal
    body section (line 287) and the SessionStart hook export block
    (line 544) renamed to "Pipeline Rules" with per-rule "policy" vs.
    "HARD" enforcement annotations. Rule 5 tagged as hook-enforced via
    `rtl-verify-stop-gate.sh`, others tagged as policy/advisory.
  - `hooks/rtl-orchestrator-inject.sh` regenerated via
    `scripts/sync_orchestrator_inject.sh`.
  - `CLAUDE.md` progressive disclosure table description updated to
    "SessionStart hook → Pipeline Rules + Routing Table".
  - `tests/unit/test_hooks.py` (`test_docs_dir_triggers_injection` +
    `test_orchestrator_inject_fires_with_legacy_dir`): assertion strings
    migrated from "Absolute Rules (Hard Gates)" to "Pipeline Rules".
  - `skills/rat-ultraloop/SKILL.md`: added `allowed-tools` frontmatter
    declaring `Skill` (skill delegates to target via `Skill(...)` but
    was missing the declaration — same class of issue as R8-2
    `rtl-p4-block-parallel`).
  - `.claude-plugin/plugin.json`: `description` and `keywords` migrated
    to match `.claude-plugin/marketplace.json` exactly (`description`
    now the marketplace's full pipeline summary; `keywords` reordered
    and extended with `uvm` + `cocotb` to match `tags`).

- **Plugin author / allowed-tools / Docker README / Absolute Rules**
  (caught by eighth Codex review across 4 new angles):
  - `.claude-plugin/plugin.json` author was `RTL Agent Team contributors`,
    but `.claude-plugin/marketplace.json` used `babyworm`. Harmonized to
    `babyworm` to match the marketplace publishing identity.
  - `skills/rtl-p4-block-parallel/SKILL.md` frontmatter `allowed-tools`
    was missing `Skill`, but the body delegates to `rtl-p4-implement` via
    `Skill(...)` in the fallback path. A strict allowlist enforcement
    would have blocked the documented fallback. Added `Skill` to the list.
  - `README.md` and `README_kr.md` Docker "Included tools" list omitted
    `svlens` (CDC + structural analysis) and `slang-server` (SV LSP),
    even though `docker/Dockerfile` builds both. Added both to the list.
  - `CLAUDE.md` section "Absolute Rules" was misleading: Rule 5 is the only
    hook-enforced hard gate (via `rtl-verify-stop-gate.sh`); rules 1-4 and
    6-8 are policy declarations enforced via skill entry warnings, per the
    "Asymmetric Phase Gate Design" principle. Renamed the section to
    "Pipeline Rules (policy + enforcement map)" and added an explicit
    enforcement column so the table honestly reflects what is hard-blocked
    vs. advisory.

- **Skill and hook counts corrected** (caught by third Codex review):
  - `README.md`, `README_kr.md`, and `.claude-plugin/marketplace.json` previously
    said "93 skills". Actual count is **94** (CLAUDE.md file-tree header:
    "54 action entry-points + 31 policies + 4 tool profiles + 4 conventions
    + 1 internal = 94"). The README Skill categories table has been restructured
    to the 5-category CLAUDE.md taxonomy so the sum visibly equals 94 (the
    previous table summed to 91, a self-inconsistency).
  - `README.md`, `README_kr.md`, `CLAUDE.md`, and `plugin_docs/hook-development-guide.md`
    previously said "14 hook scripts". Actual count is **15** (verified via
    `find hooks -maxdepth 1 -name '*.sh'`). README's "17 registrations" was
    also wrong; actual registration count in `hooks/hooks.json` is **16**.

## [0.9.2] - 2026-04-09

### Changed
- **svlens promoted to Tier 1 Required** in `/rat-setup` — CDC/structural analysis
  is now a Tier 1 requirement alongside lint. svlens is the open-source default;
  the requirement is also satisfied by any commercial CDC tool (`sg_shell`,
  `vc_cdc`, `questa_cdc`). `svlens conn` additionally supplements lint (width,
  type, dangling checks) when verible/slang are missing, but does not replace
  style/semantic lint.
- **Phase 1d Commercial Tool Scan extended**: `vc_cdc` (Synopsys) and `questa_cdc`
  (Siemens) added to the commercial CDC detection table.
- **Phase 2 Report example** now explicitly lists svlens row so users do not miss
  the detection status.
- **Q1 remediation logic rewritten**: CDC tool requirement is checked against
  both Phase 1a (svlens) and Phase 1d (commercial CDC) results; svlens install
  is skipped automatically when any commercial CDC tool is detected.

### Docs
- **README restructured into 3-stage workflow**: "A. Machine Setup" (one-time per
  machine), "B. Project Initialization" (one-time per project), "C. Design Work"
  (recurring, inside project). Removed duplicate "Project initialization" section
  from Usage — now consolidated under Stage B. Stage scope/frequency table added
  at the top of Quick Start.
- `README.md` and `README_kr.md` EDA Tools table: added `svlens` (Tier 1 Required)
  and explicit "satisfies CDC requirement" note for commercial CDC tools.
  `README_kr.md` table previously missed `python3`/`g++`/`make`/`systemc`/`slang-server`
  rows — now synced with English version.
- `plugin_docs/eda-setup-guide.md`: new "Tier 1 at-least-one requirements" section
  explains the lint/CDC alternative patterns. `svlens` added to Auto-install path
  and `vc_cdc`/`questa_cdc` added to Commercial path in the integration table.

## [0.9.1] - 2026-04-08

### Changed
- **EDA tool working directory isolation**: each tool category now runs from its
  own dedicated directory instead of project root, preventing intermediate file
  pollution (`csrc/`, `work/`, `command.log`, etc.)
  - Synthesis (DC/Genus/Yosys): `cd syn/`
  - Simulation (VCS/Xrun/Questa): `cd $OUTDIR` (default `sim/build`)
  - Syntax lint: `cd lint/lint/`
  - CDC analysis: `cd lint/cdc/`
  - Formal verification: `cd formal/`
  - VCS in Makefile: `cd build/vcs/`
- Runner scripts (`run_syn.sh`, `run_sim.sh`, `run_lint.sh`, `run_cdc.sh`,
  `run_regression_uvm.sh`) resolve all input paths to absolute before `cd`
- Makefile formal targets use `cd formal && ...` with `$(abspath)` for inputs
- CDC script deployment path: `sim/cdc/run_cdc.sh` → `lint/scripts/run_cdc.sh`
- SBY_FILE default: `sim/formal/$(TOP).sby` → `formal/$(TOP).sby`
- Makefile clean target updated for new directory layout

### Fixed
- VCS `csrc/` directory polluting project root in Makefile `sim_vcs` and `uvm_compile`
- Questa missing `vlib`/`-work` in `run_sim.sh` (would fail or create `work/` in root)
- DC `command.log` now redirected to `syn/log/` via `sh_command_log_file`
- CDC script file collection ordering bug (resolve ran before files were collected)

## [0.9.0] - 2026-04-08

### Added
- `plugin_docs/eda-setup-guide.md`: comprehensive EDA tool setup guide covering
  env_source patterns, vendor-specific examples (Synopsys/Cadence/Siemens),
  rat_config.json field reference, and technology configuration
- `rat-setup` Phase 1d: commercial tool PATH scan (vcs, xrun, vsim, dc_shell,
  genus, sg_shell, fm_shell, lec, verdi, simvision)
- `rat-setup` Q2b: interactive commercial tool confirmation (detected tools) and
  env_source entry (undetected tools) with subshell verification
- `rat-setup` Q2c: synthesis target Liberty library path collection with
  NAND2 area auto-extraction
- README/README_kr: EDA Setup Guide link in EDA Tools section

## [0.8.21] - 2026-04-07

### Fixed
- Codex cross-review findings (10 rounds):
  - config.mk: skip empty PREF_*/SEEDS to prevent broken Make dispatch
  - generate_config.sh: normalize tool names for Makefile targets (dc_shell→dc, jg→jasper, vsim→questa, sg_shell→spyglass)
  - generate_config.sh: safe_formal_pref uses DET_STATUS for env_source-aware sby detection
  - run_syn.sh: SDC default always project-relative, not SYN_ROOT-relative
  - run_syn.sh: timestamp in auto-generated script filenames (parallel safety)
  - run_syn.sh: Yosys JSON netlist → syn/db/ (vnet/ for .v only)
  - run_syn.sh: Yosys stat extraction with multi-marker version compatibility
  - run_cdc.sh: svlens availability check includes run_tool Docker fallback
  - Makefile: sim_regression passes SIM + TOPLEVEL to cocotb sub-make
  - Makefile: svlens targets route through _run_tool wrapper
  - Makefile: add sim_questa target
  - Makefile: POSIX-portable regression (no bash-only PIPESTATUS)
  - Complete syn/reports → syn/{rpt,log,vnet,svf,scr}/ path migration across
    all consumers (equivalence-checker, formality, conformal, synth-check,
    syn-guide, syn-tool-profiles, module-doc-template, yosys-commands)
  - equivalence-checker: SVF path syn/output/ → syn/svf/
  - rat-setup: clarify env-config.json not yet consumed

## [0.8.20] - 2026-04-07

### Added
- EDA build infrastructure: DC-standard synthesis directory layout
  (`syn/{db,vnet,svf,scr,rpt,log,temp,work}/`)
- `config.mk` auto-generation from `rat_config.json` (Makefile-includable tool preferences)
- `make sim-regression` target for cocotb multi-seed regression
- Dynamic tool selection via `config.mk`: `make sim/syn/formal/cdc` auto-dispatch to preferred tool
- `${CLAUDE_PLUGIN_DATA}/env-config.json` for machine-wide EDA environment persistence
- `run_syn.sh`: `.synopsys_dc.setup` auto-generation, SVF output, proper DC/Genus work dirs
- Dockerfile: svlens build step (CDC + connectivity + metrics)
- P2/P3 orchestrator gate checks for `ref-model-feature-coverage.md` and `bfm-feature-coverage.md`
- `reviews-guide.md`: new feature coverage artifacts listed

### Changed
- `run_syn.sh` rewritten: `--outdir` flat output → structured `syn/{db,vnet,svf,...}/` layout
- Makefile: `-include config.mk`, expanded `clean` (all EDA outputs), dynamic help text
- `rat-setup`: detection command `svlens --version` (was `svlens help`)
- `bfm-develop`: smoke test default corrected to LT (was incorrectly AT)

### Fixed
- `.gitignore`: add `.remember/`, `config.mk`
- Test: updated replay path expectation for new syn directory structure

## [0.8.19] - 2026-04-07

### Changed
- slang-cdc → svlens migration: unified structural analysis (CDC + connectivity + metrics)
  - `run_cdc.sh`: `slang-cdc` CLI replaced with `svlens cdc` subcommand
  - `rat-setup`: Tier 2 detection/install updated to svlens (cmake-based build)
  - `cdc-tool-profiles`: rewritten for svlens 3-mode architecture + quantitative/qualitative gate philosophy
  - `generate_config.sh` / `rat_config.json`: tool key `slang_cdc` → `svlens`
  - `cdc-patterns.md`: tool recommendation updated to svlens
- Makefile: added `conn`, `metrics`, `svlens_all` targets for structural analysis
- rat-tutorial: auto-detect user language from conversation context (remove forced English default)

### Added
- Feature coverage gate in ref-model skill (Phase 2): structural verification of ALL REQ-F-* against C model implementation
- Feature coverage gate in bfm-develop skill (Phase 3): structural verification of ALL REQ-F-* against SystemC BFM
- Quantitative + qualitative gate philosophy documented in cdc-tool-profiles (svlens provides numbers, LLM provides judgment, both required)

## [0.8.18] - 2026-04-03

### Added
- Completion criteria for 20 missing action skills (100% coverage: 54/54)
- Output sections for 14 action skills lacking output specification
- Coverage exclusion approval gate (Stop hook, 15th hook)
- Spec change cascade detection (PostToolUse hook in edit-tracker)
- Phase entry prerequisite checks in skill-activation (P4→P3, P5→P4, P6→P5)
- Testbench Python file change tracking in edit-tracker (sim/*.py)

### Changed
- 5 oversized agents trimmed by 658 lines total (policy references instead of inline rules)
- Context budget reduced from 133 to 125 lines (expert delegation table compressed)
- Hook export regenerated via sync_orchestrator_inject.sh

## [0.8.17] - 2026-04-03

### Added
- New skill: cross-phase-contract-validator — validates P3→P4→P5 spec consistency
  (port widths, memory classification, pipeline depth, bus parameterization, REQ traceability)
- rtl-critic static analysis: bus width derivation check (f3), memory pattern detection (f4),
  unreachable code detection (f5)
- P5 verify policy: UARCH_FIX feedback path (P5→P3), feedback loop decision recording
- Tool abstraction layer: 3-tier model (commercial/oss/none) with sv2v internalized in Layer 2
- lib/tool-runner.sh: check_tool_available, check_tool_licensed, get_synthesis_tier, get_formal_tier
- run_syn.sh: --skip-if-unavailable flag with license pre-check and clean exit
- syn-tool-profiles: tool availability tiers + sv2v Layer 2 policy

### Changed
- V8/T8 synthesis estimation delegated to run_syn.sh --skip-if-unavailable (no explicit sv2v)
- Stream B smoke test delegated to wrapper with skip support
- SVA/formal: sv2v references changed to "scripts handle internally (Layer 2)"
- 8 explicit sv2v invocations removed from agent/orchestrator prompts

## [0.8.16] - 2026-04-03

### Added
- Coverage Exclusion Protocol: convergence detection, bin classification (STIMULUS_GAP/STRUCTURAL_DEAD/INFRA_CODE), tool-neutral exclusion manifest, module-namespaced documentation, auto/user approval workflow
- Combinational Chain Depth Heuristic: >4 sequential-dependency iterations flagged as timing risk with escalation path and technology exceptions (FPGA carry chains, balanced adder trees, low-frequency domains)
- Bus Width Parameterization Rule (P3): FIFO/bus widths must derive from design parameters, hardcoded constants prohibited
- Toggle Coverage Interpretation: per-signal analysis distinguishing STIMULUS vs PARAMETERIZATION vs STRUCTURAL root causes
- UVM Stimulus-to-DUT Connectivity Verification: randomization check, DUT connectivity check, effectiveness gate (coverage delta < 0.1% → halt and debug)
- UVM orchestrator restructure: Step 2.5 (test-plan-writer ECP/BVA), Step 3b (uvm-reviewer quality gate), structured 3-round CDV loop with test-plan-writer integration and exclusion protocol
- UVM directory hierarchy: hierarchical layout (agents/, env/, seq/, tb/, tests/, coverage/, results/) matching real project patterns
- Coverage policy: benign vs critical gap assessment framework, per-metric convergence tracking, config-to-code-path mapping
- test-plan-writer integration in coverage CDTG loop (both cocotb and UVM flows)
- Cross-module metadata propagation check in integration-verifier (FIFO sideband verification, unit mismatch detection)
- hier.cfg generation step in UVM orchestrator for TB infrastructure exclusion
- Coverage targets evaluated on post-exclusion numbers across all policies (V6/T6 gates updated)
- System-level coverage exclusion path in p5-verify-orchestrator T6

### Fixed
- UVM policy compile flags: paths updated from flat sim/uvm/*.sv to hierarchical subdirectories
- UVM orchestrator results path: sim/uvm/regression/ → sim/uvm/results/ (matching real project)
- 20 cross-file consistency issues resolved via Codex gpt-5.4 cross-review (11 rounds)
- Coverage exclusion record path standardized to {module}-coverage-exclusions.md across all files

## [0.8.15] - 2026-03-31

### Added
- SRAM wrapper taxonomy correction: SP (single-port) / TP (two-port, single clock) / DP (dual-port, dual clock wclk/rclk)
  - TP template: separate R+W ports, single clock — replaces old incorrectly-named sram_dp
  - DP template: separate R+W ports, dual clock (wclk/rclk) — new, for CDC boundaries
  - TDP (true dual-port, 2 R/W) removed — not recommended in modern processes
- P2 architecture: Memory Architecture Classification section (capacity, port count, clock domain)
- P5 CDC: sram_dp as CDC boundary in synchronizer table, Dual-Port SRAM Synchronizer pattern
  with verification checklist and SDC constraint templates in cdc-patterns.md
- CDC checker/reviewer: sram_dp domain verification in checklists
- rtl-architect/synthesis-reviewer: SP/TP/DP wrapper names with CDC annotation

### Fixed
- 12 consistency issues from initial review + 4 self-review + 2 Codex R1 + 3 Codex R3 + 3 Codex R4 + 2 Codex R5
- sram_tdp multi-driver (merged to single always_ff), then removed entirely (taxonomy correction)
- SpyGlass CDC orchestrator: `which spyglass` → `which sg_shell`
- UVM regression: functional≥95% in JSON output + help text, script bootstrap in install_project_templates.sh
- Template versioning: run_formality.sh, run_conformal.sh, run_syn.sh bumped to 0.8.14
- lint-checker agent: slang -Weverything for RTL, --allow-dup-initial-drivers for TB
- rat_config.json: env_source documentation alignment, equivalence category added

## [0.8.14] - 2026-03-31

### Added
- `rat_config.json` project configuration with EDA tool auto-detection
  - `env_setup`: sourcing scripts for tools not in PATH
  - `tools`: auto-detected by category (simulator, synthesis, lint, formal, cdc)
  - `technology`: liberty path, SRAM lib, NAND2 area auto-extraction from liberty
  - `coverage`: targets, seeds, max fail rate as single source of truth
  - `waivers`: custom paths for lint/CDC waiver files
  - `generate_config.sh`: preserves user fields on re-run
- Simulator-specific coverage collection documentation in UVM policy and sim-tool-profiles

### Fixed
- Questa coverage: add `+cover=bcestf` at `vlog` compile (was missing)
- Xcelium coverage: fix `imc` merge path (TCL script-based), add `-covscope`
- VCS coverage: `urg -format both` (text + XML for coverage-analyst)
- `generate_config.sh`: fix `set -e` + `&&` silent exit, fix subshell nameref array loss

## [0.8.13] - 2026-03-30

### Added
- Storage selection criteria (register vs SRAM wrapper) across Phase 3/4 pipeline
  - P3 uarch-policy: size/port threshold table (≤256b→register, 257-4096b→SRAM recommended, >4096b→SRAM mandatory)
  - SRAM wrapper interface spec (SP/DP/TDP, DEPTH/WIDTH params, standard port naming)
  - P4 implement-policy: Memory Wrapper Rules (rtl/common/ placement, foundry macro replacement)
  - systemverilog skill: SP/DP wrapper templates with behavioral code
  - rtl-coding-conventions: storage selection table deployed to user projects
- UVM coverage-driven regression infrastructure
  - `run_regression_uvm.sh`: multi-seed parallel regression for VCS/Xcelium/Questa with failure halt, per-seed JSON, coverage merge
  - Makefile targets: `uvm_compile`, `uvm_run`, `uvm_regression`, `uvm_coverage`
  - UVM policy: coverage targets (line≥90%, toggle≥80%, FSM≥70%, branch≥80%, functional≥95%)
  - CDV feedback loop: coverage-analyst → CDTG table → testbench-dev (max 3 rounds)
  - UVM orchestrator: mandatory coverage collector, regression script integration
- slang `-Weverything` for RTL lint (catches VCS ICPD errors: always_ff multi-driver)
  - Auto-detect RTL vs TB paths in run_lint.sh; TB uses `--allow-dup-initial-drivers`
- VCS `always_ff` + `initial` ICPD caveat documented in systemverilog skill §4.3

### Fixed
- SpyGlass batch mode: `spyglass -shell` → `sg_shell` with proper `new_project -projectwdir` lifecycle
- SpyGlass TCL: `read_file -type systemverilog` for .sv files (was `verilog`)
- Synthesis templates: Yosys split pass chain (memory pass for SRAM), sv2v auto rtl/common/ inclusion
- DC/Genus flows: SDC auto-loading, SRAM dont_touch, report_power/report_qor added
- Test environment isolation: 4 tests fixed for global `~/.claude/rules/` interference

## [0.8.12] - 2026-03-24

### Fixed
- rat-setup Phase 3→4 turn boundary: added directive to proceed immediately after Q1-Q4 answers without extra user prompt
- rat-setup RHEL/CentOS GCC toolset guidance for C++20 source builds (slang, slang-cdc, Verilator)

## [0.8.11] - 2026-03-24

### Added
- IEEE 1800 §12.5 forward reference enforcement across agents, skills, and coding conventions
- `check_conventions.sh` Rule 7 (DECL_ORDER): heuristic detection of declarations after logic blocks
- Unified project Makefile template (17 targets: sim/lint/syn/formal/cdc with open-source defaults, commercial EDA via `_tool` suffix)
- RAT-tagged project CLAUDE.md injection (`inject_claude_md.sh`): idempotent create/append/update with `<!-- RAT:START -->` / `<!-- RAT:END -->` delimiters
- CI-before-push rule (#12 CRITICAL) in Plugin Development Best Practices

### Fixed
- BUG-001: `((VIOLATIONS++))` → `VIOLATIONS=$((VIOLATIONS + 1))` for `set -e` safety
- DECL_ORDER grep pipeline `|| true` guard for `set -eo pipefail` on no-match files
- lint-checker.md step numbering (removed duplicate step 6, renumbered 6–13)
- Best Practices numbering (duplicate #12 → #12, #13, #14)

## [0.8.10] - 2026-03-20

### Added
- slang-cdc integration into CDC verification pipeline
  - `run_cdc.sh` structural mode: automatic slang-cdc crosscheck when installed
  - `run_cdc.sh` standalone `--tool slang-cdc` mode
  - `rat-setup` Tier 2: slang-cdc check, Q2 install option, Install_Instructions
  - `cdc-tool-profiles`: slang-cdc profile (8 sync patterns, quality checks)
  - `cdc-patterns.md`: slang-cdc as recommended open-source CDC tool

## [0.8.9] - 2026-03-20

### Added
- Interpretation Stability Framework (MVP Phase 1):
  - `scripts/stability_check.py` — content-based requirement alignment (41 TDD tests)
  - Adversarial reinterpretation Steps 7.6-7.9 in P1 orchestrator
  - Adversarial gate policy with dual gate arbitration (6-row table)
  - `challenge-report-schema.json` + `stability-report.md` template
- Phase 6 reviewers redesigned: objective metrics replace subjective 1-10 scoring
  - `code-quality-reviewer`: measurable thresholds (module size, nesting, conventions)
  - `design-quality-reviewer`: hierarchical traceability metrics (REQ coverage, drift)

## [0.8.8] - 2026-03-20

### Added
- New `rat-init-project` skill — per-project initialization (directories, rules, guides, templates)
- FSDB/SHM/VCD waveform dump `ifdef` guards in all SV testbench templates
- Templates and scripts for 11 previously asset-free skills:
  rtl-document, rtl-bug-repro, rtl-ipxact-gen, rtl-p5s-perf-verify,
  rtl-p5s-coverage-analyze, rtl-p5s-integration-test, ref-model,
  bfm-develop, rtl-ip-instantiate, rtl-model-consistency, rtl-conformance-test
- CDC edge case guidelines in `cdc-patterns.md` (non-2^N FIFO, reconvergence,
  combinational before sync, fan-out, reset crossing, clock gating, quasi-static)
- Categorized skill table in README/README_kr (93 skills across 10 categories)
- `${CLAUDE_PLUGIN_DATA}` advisory setup marker with `~/.config` fallback
- Global rules check in hooks (local || `~/.claude/rules/` fallback)
- `TestRatInitProjectRuntimeContract` and `TestRuleTemplateCount` tests

### Changed
- `rat-setup` redesigned as interactive 5-Phase EDA wizard (per-machine, not per-project)
- `diagram-rules.md` template removed — content injected via `<markdown_diagram_rule>` tag
- Agent Step 0 now calls `rat-init-project` (not `rat-setup`) for project initialization

### Renamed
- `refactor-policy` → `refactor-classification-policy`
- `rtl-design-policy` → `rtl-p4-rapid-impl-policy`
- `rtl-functional-verify-policy` → `rtl-p5a-functional-closure-policy`
- `rtl-test-design-policy` → `test-design-policy`

## [0.8.7] - 2026-03-19

### Fixed
- `local-ci-check.sh`: platform detection for CI parity (Linux bash 5+ runs all tests, macOS/older bash conservatively deselects)
- `local-ci-check.sh`: usage comment corrected from `sh` to `bash` (script uses bash arrays)
- `local-ci-check.sh`: skip reason comments now honestly describe conservative deselection, not fabricated hard dependencies
- `local-ci-check.sh`: numpy absence now warns visibly with install hint (was silent)
- `local-ci-check.sh`: final summary distinguishes "ALL PASSED" from "PASSED (skipped: ...)" to prevent false CI parity claims
- `local-ci-check.sh`: shellcheck install hint made platform-neutral (apt-get or brew)

## [0.8.6] - 2026-03-18

### Added
- Cross-Phase Artifact Functional Consistency principle — verification artifacts must be functionally validated against upstream references, not just checked for existence + compilation
- P3 BFM Validation Gate rewritten with G4a/G4b/G4c sub-gates: compilation → functional correctness (shared test vectors, per-block output comparison vs refC) → I/O log completeness
- bfm-dev agent Success Criteria and Final Checklist now require refC output match
- bfm-develop skill updated with functional validation requirement

### Fixed
- P3 team orchestrator referenced `requirements.json` instead of `iron-requirements.json` in upstream artifact scan
- P3 BFM gate failure handling now includes ref-model-dev in iteration loop (was missing)
- P4/P5 enforcement labels corrected: refC comparison is already enforced (not just "design intent")

## [0.8.5] - 2026-03-18

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

### Fixed (Codex cross-review R1-R10 + internal review R1)
- Non-team P5 Stage 3 aligned with team (AC audit, traces_to, iron-requirements)
- P4/P5 policy checklists gain test-plan + ac_ids items
- PARTIAL_PASS 2-tier model: Stage 1 WARNING, Stage 3 FAIL — enforced across all surfaces
  (p5-verify-orchestrator, p5-verify-team, requirement-tracer, p5a-closure, func-verify-policy,
  integration-test-policy, RTM template, routing SSOT, sim-guide)
- RTM template columns aligned with policy (5-col AC, 4-col REQ)
- Block-parallel: ac-coverage-advisory + Task() syntax for test-plan-writer
- Tier 3→4 handoff accepts PARTIAL_PASS (integration-test-policy, skill, routing)
- Module graduation gate accepts PARTIAL_PASS for V5 AC checks
- P5A internal vs exit gate PARTIAL distinction clarified

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
- New `test-design-policy` skill (renamed from `rtl-test-design-policy`) — ECP, BVA, state transition, decision table testing
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
