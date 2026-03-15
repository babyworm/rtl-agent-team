# Block-Parallel Domain Expert Enhancement — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enhance video codec domain experts (3-way prediction split + knowledge deepening) and add worktree-based block-parallel Phase 4 RTL development with autonomous rat-ultraloop execution mode.

**Architecture:** Plugin enhancement adding 6 new agents, 4 new skills, 14 knowledge files, and updates to manifest/routing/completion-criteria. Follows existing plugin patterns: agent frontmatter conventions, Skill→Agent→Policy architecture, team-fallback contract, soft advisory prerequisites.

**Tech Stack:** Claude Code plugin (Markdown agents/skills, POSIX shell hooks, JSON config)

**Spec:** `plugin_docs/specs/2026-03-15-block-parallel-domain-expert-design.md`

---

## File Structure

### New Files (24 total)

**Agents (6):**
- `agents/vcodec-intra-pred-expert.md` — Intra prediction domain expert (split from prediction-expert)
- `agents/vcodec-me-expert.md` — Motion Estimation domain expert (split from prediction-expert)
- `agents/vcodec-mc-expert.md` — Motion Compensation domain expert (split from prediction-expert)
- `agents/p4-block-parallel-coordinator.md` — 6-block parallel coordination orchestrator
- `agents/p4-block-worker.md` — Per-block worktree execution worker
- `agents/ultraloop-reviewer.md` — Autonomous review with freeze verification

**Skills (4):**
- `skills/rtl-p4-block-parallel/SKILL.md` — Block-parallel Phase 4 entry point
- `skills/rtl-block-interface-policy/SKILL.md` — Interface design rules + timing contract
- `skills/rtl-block-contract-test-policy/SKILL.md` — Contract test criteria and procedures
- `skills/rat-ultraloop/SKILL.md` — Autonomous implement-review-improve loop

**Knowledge (14):**
- `domain-packages/video-codec/knowledge/intra-prediction-modes.md`
- `domain-packages/video-codec/knowledge/intra-reference-sample.md`
- `domain-packages/video-codec/knowledge/me-search-algorithms.md`
- `domain-packages/video-codec/knowledge/mv-prediction.md`
- `domain-packages/video-codec/knowledge/mc-interpolation-filters.md`
- `domain-packages/video-codec/knowledge/weighted-prediction.md`
- `domain-packages/video-codec/knowledge/cabac-context-tables.md`
- `domain-packages/video-codec/knowledge/cavlc-coding-tables.md`
- `domain-packages/video-codec/knowledge/nal-unit-types.md`
- `domain-packages/video-codec/knowledge/butterfly-operations.md`
- `domain-packages/video-codec/knowledge/quantization-matrices.md`
- `domain-packages/video-codec/knowledge/rdoq-algorithm.md`
- `domain-packages/video-codec/knowledge/deblocking-boundary-strength.md`
- `domain-packages/video-codec/knowledge/sao-classification.md`

### Modified Files (16)

- `domain-packages/video-codec/manifest.json` — Remove prediction-expert, add 3 new experts, register 14 knowledge files, update agent_coverage and agent_coordination
- `skills/rtl-orchestrate/SKILL.md` — Add new skills/agents to routing table + Action Skill→Orchestrator mapping table
- `skills/domain-consult/SKILL.md` — Split prediction routing → intra/ME/MC (Section 4.5 of spec)
- `hooks/rtl-orchestrator-inject.sh` — Auto-regenerated via `sync_orchestrator_inject.sh`
- `hooks/stop-gate.sh` — Add ultraloop state detection + 30-min auto-continue timestamp check
- `skill-completion-criteria.json` — Add `rtl-p4-block-parallel` and `rat-ultraloop` entries
- `CLAUDE.md` — Update agent/skill counts
- `agents/vcodec-chief-standard-expert.md` — Update cross-block review template + "4 sub-domain" → "6 sub-domain" prose
- `agents/p1-research-orchestrator.md` — Update prediction-expert reference
- `agents/p1-research-team-orchestrator.md` — Update task graph prediction references
- `scripts/inject-worker-protocol.sh` — Update agent list + case statement
- `tests/unit/test_expert_quality.py` — Update expert quality test lists
- `tests/unit/test_team_mode.py` — Update team mode test assertions
- `CONTRIBUTING.md` — Update expert listing
- `README.md` — Update domain experts table + agent count
- `README_kr.md` — Update domain experts table + agent count (Korean)
- `CHANGELOG.md` — Add [Unreleased] entry for this feature

### Deleted Files (1)

- `agents/vcodec-prediction-expert.md` — Replaced by 3-way split

---

## Chunk 1: Knowledge Base Expansion

### Task 1: Create Intra Prediction Knowledge Files

**Files:**
- Create: `domain-packages/video-codec/knowledge/intra-prediction-modes.md`
- Create: `domain-packages/video-codec/knowledge/intra-reference-sample.md`
- Reference: `domain-packages/video-codec/knowledge/h264-spec-summary.md`
- Reference: `domain-packages/video-codec/knowledge/h265-spec-summary.md`

- [ ] **Step 1: Create intra-prediction-modes.md**

Content requirements:
- H.264 intra modes: 9 modes (4x4), 4 modes (16x16), 4 modes (chroma)
- H.265 intra modes: 35 modes (DC, Planar, 33 angular) with intraPredAngle table
- Mode-dependent reference sample filtering (H.265 §8.4.4.2.3)
- Strong intra smoothing conditions (32x32 blocks)
- Mode index tables with direction vectors
- All clause references to H.264 §8.3 and H.265 §8.4

- [ ] **Step 2: Create intra-reference-sample.md**

Content requirements:
- Reference sample availability rules (H.264 §8.3.1, H.265 §8.4.4.2.2)
- Substitution algorithm when neighbors unavailable
- Picture edge and slice boundary behavior
- Constrained intra prediction flag impact
- Reference sample construction for each block size

- [ ] **Step 3: Verify cross-references with existing spec summaries**

Run: `grep -l "intra" domain-packages/video-codec/knowledge/*.md`
Verify: new files complement (not duplicate) existing h264/h265-spec-summary.md content.

- [ ] **Step 4: Commit**

```bash
git add domain-packages/video-codec/knowledge/intra-prediction-modes.md \
       domain-packages/video-codec/knowledge/intra-reference-sample.md
git commit -m "knowledge: add intra prediction modes and reference sample docs"
```

### Task 2: Create Motion Estimation Knowledge Files

**Files:**
- Create: `domain-packages/video-codec/knowledge/me-search-algorithms.md`
- Create: `domain-packages/video-codec/knowledge/mv-prediction.md`

- [ ] **Step 1: Create me-search-algorithms.md**

Content requirements:
- Full search, diamond search, hexagonal search, TZ search algorithms
- Search range specification per profile/level
- Integer ME → Fractional ME (half-pel → quarter-pel) cascade
- Rate-distortion cost models: SAD, SATD, SSE with lambda weighting
- Multi-reference frame search strategy
- Encoder-side only (not decoder-mandated) — clearly labeled

- [ ] **Step 2: Create mv-prediction.md**

Content requirements:
- H.264 median MV prediction from spatial neighbors (A, B, C/D) — §8.4.1
- H.265 AMVP candidate derivation (§8.5.3.2): spatial (A0, A1, B0, B1, B2) + temporal
- H.265 Merge Mode (§8.5.3.1): up to 5 candidates, strict derivation order
- Candidate pruning rules (duplicate removal)
- Direct mode (B-slice): spatial and temporal direct (§8.4.1.2)
- All with exact neighbor position diagrams

- [ ] **Step 3: Commit**

```bash
git add domain-packages/video-codec/knowledge/me-search-algorithms.md \
       domain-packages/video-codec/knowledge/mv-prediction.md
git commit -m "knowledge: add ME search algorithms and MV prediction docs"
```

### Task 3: Create Motion Compensation Knowledge Files

**Files:**
- Create: `domain-packages/video-codec/knowledge/mc-interpolation-filters.md`
- Create: `domain-packages/video-codec/knowledge/weighted-prediction.md`

- [ ] **Step 1: Create mc-interpolation-filters.md**

Content requirements:
- H.264: 6-tap Wiener filter [1,-5,20,20,-5,1]/32 for half-pel luma (§8.4.2.2.1)
- H.264: bilinear for quarter-pel luma, bilinear for chroma (§8.4.2.2.2)
- H.265: 8-tap luma filter coefficients per position (Table 8-2)
- H.265: 4-tap chroma filter coefficients (Table 8-3)
- Intermediate precision: accumulator width, shift, rounding, clipping
- Diagonal position filtering order and intermediate precision caveat

- [ ] **Step 2: Create weighted-prediction.md**

Content requirements:
- Default weighted prediction: (predL0 + predL1 + 1) >> 1
- Explicit weighted prediction: per-slice weights and offsets (H.264 §8.4.2.3, H.265 §8.5.3.3.4)
- Log2 weight denominator, rounding behavior
- Uni-prediction vs bi-prediction weighting differences

- [ ] **Step 3: Commit**

```bash
git add domain-packages/video-codec/knowledge/mc-interpolation-filters.md \
       domain-packages/video-codec/knowledge/weighted-prediction.md
git commit -m "knowledge: add MC interpolation filters and weighted prediction docs"
```

### Task 4: Create Syntax/Entropy Knowledge Files

**Files:**
- Create: `domain-packages/video-codec/knowledge/cabac-context-tables.md`
- Create: `domain-packages/video-codec/knowledge/cavlc-coding-tables.md`
- Create: `domain-packages/video-codec/knowledge/nal-unit-types.md`

- [ ] **Step 1: Create cabac-context-tables.md**

Content requirements:
- Context initialization tables per slice_type and cabac_init_idc (H.264 §9.3.1)
- H.265 context initialization (§9.3.2): initType, initValue derivation
- Context model index mapping for each syntax element
- Renormalization tables and range/offset encoding tables
- State transition tables (pStateIdx, valMPS)

- [ ] **Step 2: Create cavlc-coding-tables.md**

Content requirements:
- Coeff_token VLC tables (H.264 Table 9-5 to 9-8)
- Level prefix/suffix encoding rules
- Total zeros and run_before tables
- nC derivation from neighbor availability

- [ ] **Step 3: Create nal-unit-types.md**

Content requirements:
- H.264 NAL unit types (Table 7-1): coded slice, IDR, SPS, PPS, SEI, etc.
- H.265 NAL unit types (Table 7-1): VPS, SPS, PPS, slice segment types
- Forbidden_zero_bit, nal_ref_idc, nal_unit_type field layouts
- Start code emulation prevention (§7.4.1)

- [ ] **Step 4: Commit**

```bash
git add domain-packages/video-codec/knowledge/cabac-context-tables.md \
       domain-packages/video-codec/knowledge/cavlc-coding-tables.md \
       domain-packages/video-codec/knowledge/nal-unit-types.md
git commit -m "knowledge: add CABAC/CAVLC tables and NAL unit types docs"
```

### Task 5: Create Transform/Quantization Knowledge Files

**Files:**
- Create: `domain-packages/video-codec/knowledge/butterfly-operations.md`
- Create: `domain-packages/video-codec/knowledge/quantization-matrices.md`
- Create: `domain-packages/video-codec/knowledge/rdoq-algorithm.md`

- [ ] **Step 1: Create butterfly-operations.md**

Content requirements:
- H.264 4x4 integer DCT butterfly (§8.5.12): core transform matrix
- H.265 DCT-II butterfly for 4x4, 8x8, 16x16, 32x32 (§8.6.4.2)
- H.265 DST-VII for 4x4 intra (§8.6.4.2)
- Per-stage accumulator width analysis (overflow prevention)
- Inverse transform: transposed butterfly with right-shift per stage

- [ ] **Step 2: Create quantization-matrices.md**

Content requirements:
- H.264 quantization: MF/V matrices per QP, QP%6 indexing (§8.5.12.1)
- H.265 scaling lists: default and custom (§8.6.3)
- QP range (0-51), per-QP scaling factor derivation
- Chroma QP mapping (QPC from QPY)
- Flat vs non-flat scaling matrices

- [ ] **Step 3: Create rdoq-algorithm.md**

Content requirements:
- Rate-Distortion Optimized Quantization concept (encoder-side)
- Cost function: J = D + λ·R
- Last significant coefficient position optimization
- Level decision: floor vs ceil quantization trade-off
- Encoder-side only — clearly labeled

- [ ] **Step 4: Commit**

```bash
git add domain-packages/video-codec/knowledge/butterfly-operations.md \
       domain-packages/video-codec/knowledge/quantization-matrices.md \
       domain-packages/video-codec/knowledge/rdoq-algorithm.md
git commit -m "knowledge: add butterfly, quantization matrices, and RDOQ docs"
```

### Task 6: Create Filter/Reconstruction Knowledge Files

**Files:**
- Create: `domain-packages/video-codec/knowledge/deblocking-boundary-strength.md`
- Create: `domain-packages/video-codec/knowledge/sao-classification.md`

- [ ] **Step 1: Create deblocking-boundary-strength.md**

Content requirements:
- H.264 boundary strength derivation (§8.7.2.1): Bs=0,1,2,3,4 conditions
- H.265 boundary strength derivation (§8.7.2.5.4): simplified Bs=0,1,2
- Filter decision thresholds: alpha, beta, tc (per QP)
- Strong filter vs normal filter conditions
- Edge filtering order (vertical then horizontal)

- [ ] **Step 2: Create sao-classification.md**

Content requirements:
- H.265 SAO modes: edge offset (4 classes) and band offset (32 bands) — §8.7.3
- Edge offset category derivation per class (horizontal, vertical, 135°, 45°)
- Band offset: band position from sample value MSBs
- SAO merge modes (left, up)
- Per-CTU SAO parameter signaling

- [ ] **Step 3: Commit**

```bash
git add domain-packages/video-codec/knowledge/deblocking-boundary-strength.md \
       domain-packages/video-codec/knowledge/sao-classification.md
git commit -m "knowledge: add deblocking boundary strength and SAO classification docs"
```

---

## Chunk 2: Domain Expert Restructuring

### Task 7: Create vcodec-intra-pred-expert Agent

**Files:**
- Create: `agents/vcodec-intra-pred-expert.md`
- Reference: `agents/vcodec-prediction-expert.md` (template structure)

- [ ] **Step 1: Create agent file**

Frontmatter:
```yaml
---
name: vcodec-intra-pred-expert
description: Video codec intra prediction expert (H.264/H.265). Interprets intra prediction modes, reference sample construction, mode-dependent filtering, and boundary conditions from normative standard text.
model: opus
color: blue
---
```

Agent structure (follow `vcodec-prediction-expert.md` pattern):
- `<Role>`: Intra prediction specialist. Knowledge files: `intra-prediction-modes.md`, `intra-reference-sample.md`, plus existing spec summaries.
- Phase participation: P1 Primary, P2 Primary, P3 Support, P4 Review, P5 Support
- `<Domain_Knowledge>`: Sections 1 (Intra Prediction) and 6 (Block Partitioning) extracted from prediction-expert, expanded with deeper mode-specific detail
- `<Success_Criteria>`: Intra-specific: mode availability rules, reference sample substitution, strong intra smoothing conditions
- `<Constraints>`: Intra-specific. Remove all inter/ME/MC constraints.
- `<Investigation_Protocol>`: Intra-focused 10-step protocol
- `<Quality_Contract>`: Same 5-item contract as prediction-expert
- `<Tool_Usage>`, `<Output_Format>`, `<Examples>`: Intra-specific
- Team Worker Protocol section (copied from prediction-expert)

- [ ] **Step 2: Validate agent structure**

Run: `head -6 agents/vcodec-intra-pred-expert.md` — verify frontmatter
Run: `grep -c "DOMAIN_UNCERTAINTY" agents/vcodec-intra-pred-expert.md` — verify uncertainty tagging exists

- [ ] **Step 3: Commit**

```bash
git add agents/vcodec-intra-pred-expert.md
git commit -m "agent: add vcodec-intra-pred-expert (split from prediction-expert)"
```

### Task 8: Create vcodec-me-expert Agent

**Files:**
- Create: `agents/vcodec-me-expert.md`

- [ ] **Step 1: Create agent file**

Frontmatter:
```yaml
---
name: vcodec-me-expert
description: Video codec motion estimation expert (H.264/H.265). Interprets ME search algorithms (IME/FME), MV prediction (AMVP/merge), reference frame management, and search range constraints.
model: opus
color: blue
---
```

Agent structure:
- `<Role>`: ME specialist. Knowledge files: `me-search-algorithms.md`, `mv-prediction.md`, plus spec summaries.
- Phase participation: P1 Primary, P2 Primary, P3 Primary (ME architecture is complex), P4 Review, P5 Support
- `<Domain_Knowledge>`: Sections 2 (Motion Estimation), 4 (MV Prediction) from prediction-expert, expanded
- `<Constraints>`: Must clearly distinguish encoder-side (ME search) from decoder-mandated (MV prediction). ME search algorithms are encoder freedom, not normative.
- Team Worker Protocol section

- [ ] **Step 2: Validate and commit**

```bash
git add agents/vcodec-me-expert.md
git commit -m "agent: add vcodec-me-expert (split from prediction-expert)"
```

### Task 9: Create vcodec-mc-expert Agent

**Files:**
- Create: `agents/vcodec-mc-expert.md`

- [ ] **Step 1: Create agent file**

Frontmatter:
```yaml
---
name: vcodec-mc-expert
description: Video codec motion compensation expert (H.264/H.265). Interprets sub-pixel interpolation filters, bi-prediction weighting, weighted prediction, and reference block fetching from normative standard text.
model: opus
color: blue
---
```

Agent structure:
- `<Role>`: MC specialist. Knowledge files: `mc-interpolation-filters.md`, `weighted-prediction.md`, plus spec summaries.
- Phase participation: P1 Primary, P2 Primary, P3 Support, P4 Review, P5 Support
- `<Domain_Knowledge>`: Sections 3 (MC Sub-Pixel Interpolation), 5 (Bi-Prediction) from prediction-expert, expanded
- `<Constraints>`: MC interpolation is decoder-mandated (normative). Filter coefficients must be exact.
- `<Success_Criteria>`: All filter coefficients cited from standard tables, intermediate precision specified
- Team Worker Protocol section

- [ ] **Step 2: Validate and commit**

```bash
git add agents/vcodec-mc-expert.md
git commit -m "agent: add vcodec-mc-expert (split from prediction-expert)"
```

### Task 10: Update manifest.json

**Files:**
- Modify: `domain-packages/video-codec/manifest.json`

- [ ] **Step 1: Remove vcodec-prediction-expert from agents array**

Remove the agent entry with `"id": "vcodec-prediction-expert"` (lines ~159-185 of current manifest).

- [ ] **Step 2: Add 3 new expert entries to agents array**

Add entries for `vcodec-intra-pred-expert`, `vcodec-me-expert`, `vcodec-mc-expert` following the existing entry pattern. Each entry needs: id, source ("plugin"), plugin_id, file, model, role, phase_intensity, output_tags, triggers.

Trigger keywords per spec Section 4.5:
- intra-pred: intra prediction, angular mode, planar mode, DC mode, intra reference sample, intra mode decision, neighboring sample, intra smoothing
- me: motion estimation, ME, search algorithm, IME, FME, TZ search, diamond search, MV prediction, AMVP, merge mode, search range, reference frame selection
- mc: motion compensation, MC, sub-pel interpolation, half-pel, quarter-pel, bi-prediction, weighted prediction, reference block fetch, interpolation filter

- [ ] **Step 3: Update standard_support_matrix.agent_coverage**

Change `"prediction"` to `"intra", "me", "mc"` in both H.264 and H.265 entries.

- [ ] **Step 4: Update agent_coordination workflow references**

Replace `vcodec-prediction-expert` with the appropriate split experts in:
- `phase_1_research.primary_domain_agents`: add all 3 new experts
- `phase_4_rtl.support_domain_agents`: add all 3 new experts
- `phase_5_verification.support_domain_agents`: add all 3 new experts

- [ ] **Step 5: Register 14 new knowledge files in knowledge_base.contents**

Add entries for all 14 new knowledge files following the existing entry pattern (file, description, standard_id, standard_version).

- [ ] **Step 6: Validate JSON**

Run: `python3 -c "import json; json.load(open('domain-packages/video-codec/manifest.json'))"`
Expected: no error

- [ ] **Step 7: Commit**

```bash
git add domain-packages/video-codec/manifest.json
git commit -m "manifest: 3-way prediction split + 14 knowledge files registration"
```

### Task 11: Delete vcodec-prediction-expert and Update References

**Files:**
- Delete: `agents/vcodec-prediction-expert.md`
- Modify: `agents/vcodec-chief-standard-expert.md` — update cross-block review template
- Modify: `skills/domain-consult/SKILL.md` — split routing table row

- [ ] **Step 1: Search for all references to vcodec-prediction-expert**

Run: `grep -r "vcodec-prediction-expert" --include="*.md" --include="*.json" --include="*.sh" --include="*.py"`
Fix each reference to point to the appropriate split expert(s).

- [ ] **Step 2: Update domain-consult routing table and prose**

Replace single prediction row with 3 rows per spec Section 4.5 keyword partition.
Also update `<Why_This_Exists>` section prose: "4 codec sub-domain specialists" → "6 codec sub-domain specialists".

- [ ] **Step 3: Update vcodec-chief-standard-expert cross-block template**

Replace `#### To vcodec-prediction-expert:` with three separate feedback sections:
- `#### To vcodec-intra-pred-expert:`
- `#### To vcodec-me-expert:`
- `#### To vcodec-mc-expert:`

- [ ] **Step 3b: Update chief expert prose references**

Run: `grep -n "4 sub-domain\|four sub-domain" agents/vcodec-chief-standard-expert.md`
Update all instances to "6 sub-domain experts" (description line, Role section, checklist).

- [ ] **Step 4: Delete prediction-expert agent**

```bash
git rm agents/vcodec-prediction-expert.md
```

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: all tests pass

- [ ] **Step 6: Commit**

```bash
git add agents/vcodec-chief-standard-expert.md \
       skills/domain-consult/SKILL.md \
       agents/p1-research-orchestrator.md \
       agents/p1-research-team-orchestrator.md \
       scripts/inject-worker-protocol.sh \
       tests/unit/test_expert_quality.py \
       tests/unit/test_team_mode.py \
       CONTRIBUTING.md README.md README_kr.md
git commit -m "refactor: delete prediction-expert, update all references to 3-way split"
```

---

## Chunk 3: Policy Skills

### Task 12: Create rtl-block-interface-policy Skill

**Files:**
- Create: `skills/rtl-block-interface-policy/SKILL.md`

- [ ] **Step 1: Create skill file**

Frontmatter:
```yaml
---
name: rtl-block-interface-policy
description: "Policy skill defining interface design rules, timing contract format, and Phase 2 interface freeze criteria for block-parallel RTL development."
user-invocable: false
---
```

Content requirements:
- Interface file naming convention: `rtl/intf/{src}_{dst}_if.sv`
- Package convention: `rtl/pkg/codec_if_pkg.sv`
- Timing contract comment format (from spec Section 6.2)
- Handshake protocols: valid/ready, backpressure rules
- Phase 2 freeze criteria: which files are frozen, hash verification method
- recon_filter_if.sv exclusion: filter-internal, not frozen (per spec fix)
- Interface list (8 cross-block interfaces from spec Section 6.1)

- [ ] **Step 2: Commit**

```bash
git add skills/rtl-block-interface-policy/SKILL.md
git commit -m "skill: add rtl-block-interface-policy (interface design rules)"
```

### Task 13: Create rtl-block-contract-test-policy Skill

**Files:**
- Create: `skills/rtl-block-contract-test-policy/SKILL.md`

- [ ] **Step 1: Create skill file**

Frontmatter:
```yaml
---
name: rtl-block-contract-test-policy
description: "Policy skill defining contract test structure, merge-time verification procedures, and stub generation rules for block-parallel development."
user-invocable: false
---
```

Content requirements:
- Contract test directory structure: `sim/{block}/contract/`
- Three test file types: `{block}_if_contract_tb.sv`, `{block}_timing_check.sv`, `{block}_stub.sv`
- Merge-time execution order (spec Section 6.3)
- Upstream-first merge sequence: entropy→TQ→ME→MC→intra→filter
- Cross-block integration test rules (test against already-merged blocks)
- PASS/FAIL criteria and retry semantics (max 3 attempts)

- [ ] **Step 2: Commit**

```bash
git add skills/rtl-block-contract-test-policy/SKILL.md
git commit -m "skill: add rtl-block-contract-test-policy (contract test procedures)"
```

---

## Chunk 4: Block-Parallel Agents

### Task 14: Create p4-block-parallel-coordinator Agent

**Files:**
- Create: `agents/p4-block-parallel-coordinator.md`
- Reference: `agents/p4-implement-team-orchestrator.md` (pattern template)

- [ ] **Step 1: Create agent file**

Frontmatter:
```yaml
---
name: p4-block-parallel-coordinator
model: opus
description: "Phase 4 block-parallel coordination teammate. Manages 6 worktree-based block workers, upstream-first merge sequence, contract test orchestration, and design freeze verification via TaskCreate/TaskList/TaskUpdate/SendMessage."
skills: [rtl-block-interface-policy, rtl-block-contract-test-policy]
---
```

Agent structure (follow `p4-implement-team-orchestrator.md` pattern):
- Step 0: Context Bootstrap — copy lines 53-89 from `agents/p4-implement-team-orchestrator.md` (from `Read(".rtl-agent-team/state/spawn-context.json")` through upstream artifact scan). This is the standard ~12-line block duplicated across all orchestrators per CLAUDE.md intentional design decision #2.
- Coordination Teammate Role: FORBIDDEN (TeamCreate, TeamDelete), ALLOWED (TaskCreate, TaskList, TaskUpdate, SendMessage, Read, Bash, etc.)
- 6-Block Pipeline (not 10-wave): entropy→TQ→ME→MC→intra→filter
- Task graph: 6 parallel implement tasks, then sequential merge tasks with dependencies
- Merge protocol: per-block merge → contract test → PASS/FAIL handling
- Design freeze verification: hash check at each merge
- Worker communication: SendMessage for progress, issues, merge readiness
- Report to leader: progress summaries, completion status
- Fallback: if any infrastructure issue → SendMessage to leader suggesting sequential fallback

- [ ] **Step 2: Validate and commit**

```bash
git add agents/p4-block-parallel-coordinator.md
git commit -m "agent: add p4-block-parallel-coordinator (6-block coordination)"
```

### Task 15: Create p4-block-worker Agent

**Files:**
- Create: `agents/p4-block-worker.md`

- [ ] **Step 1: Create agent file**

Frontmatter:
```yaml
---
name: p4-block-worker
model: opus
description: "Per-block worktree execution worker for Phase 4 block-parallel development. Reads μArch spec, spawns domain expert for knowledge injection, delegates to rtl-coder for implementation, runs lint and unit tests."
---
```

Agent structure:
- Step 0: Context Bootstrap — copy the standard ~12-line block from `agents/p4-implement-team-orchestrator.md` lines 53-89 (same pattern as coordinator)
- Worker lifecycle: read μArch → spawn domain expert → spawn rtl-coder → lint → unit test → report
- Domain expert mapping: block name → expert agent ID (6 mappings)
- Interface freeze awareness: `rtl/pkg/` and `rtl/intf/` are read-only in worktree
- Output: SendMessage to coordinator with completion/issue status
- Team Worker Protocol: follow `agents/lib/team-worker-preamble.md`

- [ ] **Step 2: Validate and commit**

```bash
git add agents/p4-block-worker.md
git commit -m "agent: add p4-block-worker (per-block worktree executor)"
```

---

## Chunk 5: Block-Parallel Skill

### Task 16: Create rtl-p4-block-parallel Skill

**Files:**
- Create: `skills/rtl-p4-block-parallel/SKILL.md`
- Reference: `skills/rtl-p4-implement-team/SKILL.md` (pattern template)

- [ ] **Step 1: Create skill file**

Frontmatter:
```yaml
---
name: rtl-p4-block-parallel
description: "Phase 4 block-parallel RTL implementation using 6 worktrees with Team coordination and upstream-first merge. Requires Phase 2 interfaces and Phase 3 μArch."
user-invocable: true
argument-hint: "[--all or specific block names]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob, TeamCreate, TeamDelete, Agent, SendMessage, TaskCreate, TaskList, TaskUpdate, AskUserQuestion
---
```

Content structure (follow existing P4 team skill pattern):
1. **Prerequisites check** (soft advisory):
   - Check `rtl/pkg/codec_if_pkg.sv` exists (Phase 2)
   - Check `docs/phase-3-uarch/` completeness (Phase 3)
   - WARNING + fallback to `rtl-p4-implement-team` if missing
2. **Design freeze snapshot**: hash `rtl/pkg/` + `rtl/intf/` + `docs/phase-3-uarch/`
3. **TeamCreate**: `TeamCreate(team_name="p4-block-parallel", description="...")`
4. **Spawn coordinator**: `Agent(team_name="p4-block-parallel", subagent_type="rtl-agent-team:p4-block-parallel-coordinator")`
5. **Spawn 6 workers**: `Agent(team_name="p4-block-parallel")` × 6 with block assignment
6. **Initial task graph**: 6 parallel implement tasks via TaskCreate
7. **Leader monitoring loop**: TaskList polling, progress tracking
8. **Merge phase**: upstream-first, coordinator drives via SendMessage
9. **Contract test at each merge**: coordinator runs tests, reports to leader
10. **TeamDelete + cleanup**
11. **State persistence**: `block-parallel-state.json` (full metadata per spec Section 8.4)
12. **Fallback**: TeamCreate failure → fall back entirely to `rtl-p4-implement-team`

- [ ] **Step 2: Validate skill structure**

Run: `head -6 skills/rtl-p4-block-parallel/SKILL.md` — verify frontmatter
Run: `grep -c "TeamCreate\|SendMessage\|worktree" skills/rtl-p4-block-parallel/SKILL.md` — verify key patterns present

- [ ] **Step 3: Commit**

```bash
git add skills/rtl-p4-block-parallel/SKILL.md
git commit -m "skill: add rtl-p4-block-parallel (6-worktree block-parallel Phase 4)"
```

---

## Chunk 6: rat-ultraloop

### Task 17: Create ultraloop-reviewer Agent

**Files:**
- Create: `agents/ultraloop-reviewer.md`

- [ ] **Step 1: Create agent file**

Frontmatter:
```yaml
---
name: ultraloop-reviewer
model: opus
description: "Autonomous review agent for rat-ultraloop. Reviews RTL implementation, runs contract tests, verifies design freeze integrity, and produces improvement recommendations without modifying frozen artifacts."
---
```

Agent structure:
- Role: automated code reviewer within ultraloop cycles
- Inputs: block implementation files, contract test results, frozen hash
- Review scope: RTL quality, lint compliance, unit test coverage, interface conformance
- Design freeze check: verify hash of frozen paths, report violations (do NOT revert)
- Output: structured review with actionable improvements + freeze status
- Constraints: Strictly READ-ONLY (disallowedTools: Write, Edit). Reviewer produces improvement recommendations; the skill itself or a separate executor applies changes. This maintains separation of review and execution roles per plugin convention.

- [ ] **Step 2: Commit**

```bash
git add agents/ultraloop-reviewer.md
git commit -m "agent: add ultraloop-reviewer (autonomous review with freeze check)"
```

### Task 18: Create rat-ultraloop Skill

**Files:**
- Create: `skills/rat-ultraloop/SKILL.md`

- [ ] **Step 1: Create skill file**

Frontmatter:
```yaml
---
name: rat-ultraloop
description: "Autonomous implement-review-improve loop with 30-min auto-continue and design freeze enforcement. Wraps target skills for unattended execution."
user-invocable: true
---
```

Content structure:
1. **Invocation**: `/rat-ultraloop [target-skill]` (e.g., `/rat-ultraloop rtl-p4-block-parallel`)
2. **Design freeze snapshot**: hash frozen paths → `design-freeze.json`
3. **Autonomous loop** (max 10 cycles):
   a. Execute/continue target skill
   b. Dispatch `ultraloop-reviewer` for automated review
   c. Apply improvements from review
   d. Run contract tests
   e. Freeze verification (hash compare) — FAIL → stash + halt (fail-closed)
   f. Output cycle summary
   g. 30-min auto-continue via stop-gate escalation pattern
4. **Auto-termination**: all done / clean review / max cycles / token exhaustion
5. **State persistence**: `ultraloop-state.json` with cycle count, frozen_hash, last_cycle_timestamp
6. **User return**: `ultraloop-report.md` summary

- [ ] **Step 2: Commit**

```bash
git add skills/rat-ultraloop/SKILL.md
git commit -m "skill: add rat-ultraloop (autonomous implement-review-improve loop)"
```

---

## Chunk 7: Integration and Finalization

### Task 19: Update Routing Table

**Files:**
- Modify: `skills/rtl-orchestrate/SKILL.md`

- [ ] **Step 1: Add new skills to pattern→skill routing table**

Add entries for:
- `rtl-p4-block-parallel` — triggers: "block parallel", "worktree parallel", "6-block", "block-parallel Phase 4"
- `rat-ultraloop` — triggers: "ultraloop", "autonomous loop", "unattended", "퇴근 모드"

Add entries for new agents:
- `vcodec-intra-pred-expert`, `vcodec-me-expert`, `vcodec-mc-expert`
- `p4-block-parallel-coordinator`, `p4-block-worker`
- `ultraloop-reviewer`

- [ ] **Step 2: Add to Action Skill → Orchestrator Agent mapping table**

Add rows to the mapping table (lines ~99-138 of `rtl-orchestrate/SKILL.md`):
- `rtl-p4-block-parallel | p4-block-parallel-coordinator | rtl-block-interface-policy, rtl-block-contract-test-policy`
- `rat-ultraloop` — **omit from Orchestrator mapping table**. This skill is self-orchestrated (the skill itself drives the autonomous loop; `ultraloop-reviewer` is a READ-ONLY subagent, not an orchestrator). Add a note in the routing table: "rat-ultraloop: skill-driven, dispatches ultraloop-reviewer for review cycles."

Add `p4-block-parallel-coordinator` and `p4-block-worker` to the Orchestrator/Agent delegation tables.

- [ ] **Step 3: Regenerate hook routing block**

Run: `sh scripts/sync_orchestrator_inject.sh`
Verify: `hooks/rtl-orchestrator-inject.sh` updated

- [ ] **Step 4: Commit**

```bash
git add skills/rtl-orchestrate/SKILL.md hooks/rtl-orchestrator-inject.sh
git commit -m "routing: add block-parallel and ultraloop to orchestrate + hook"
```

### Task 20: Update skill-completion-criteria.json

**Files:**
- Modify: `skill-completion-criteria.json`

- [ ] **Step 1: Add entries for both new action skills**

```json
"rtl-p4-block-parallel": "rtl-written|lint-pass|unit-test-pass|contract-test-pass|all-blocks-merged",
"rat-ultraloop": "target-skill-executed|design-freeze-intact|cycle-summary-written"
```

- [ ] **Step 2: Validate JSON**

Run: `python3 -c "import json; json.load(open('skill-completion-criteria.json'))"`

- [ ] **Step 3: Commit**

```bash
git add skill-completion-criteria.json
git commit -m "config: add rtl-p4-block-parallel and rat-ultraloop completion criteria"
```

### Task 21: Modify stop-gate.sh for Ultraloop Auto-Continue

**Files:**
- Modify: `hooks/stop-gate.sh`
- Reference: `hooks/lib/posix-util.sh` (may need timestamp helper)

- [ ] **Step 1: Read current stop-gate.sh**

Understand existing autopilot state detection pattern (currently checks `rat-auto-design-state.json`).

- [ ] **Step 2: Add ultraloop state detection**

Add check for `.rtl-agent-team/state/ultraloop-state.json`:
- If file exists and `mode == "ultraloop"`, apply ultraloop escalation
- Compare `last_cycle_timestamp` with current time
- If elapsed > 30 minutes (configurable), allow auto-continuation
- POSIX shell only — use `[ ]` not `[[ ]]`, no bash-isms (CLAUDE.md rule 7)

- [ ] **Step 3: Add portable timestamp helper if needed**

If `hooks/lib/posix-util.sh` lacks timestamp comparison, add a `posix_elapsed_minutes()` function.

- [ ] **Step 4: Validate POSIX compatibility**

Run: `sh -n hooks/stop-gate.sh`
Expected: no syntax errors

- [ ] **Step 5: Commit**

```bash
git add hooks/stop-gate.sh hooks/lib/posix-util.sh
git commit -m "hook: add ultraloop state detection + 30-min auto-continue to stop-gate"
```

### Task 22: Update CLAUDE.md Counts

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Count actual agents and skills**

Run: `ls agents/*.md | wc -l` — use actual count (do NOT hardcode expected values)
Run: `find skills -name "SKILL.md" | wc -l` — use actual count

- [ ] **Step 2: Update counts in CLAUDE.md**

Update the line "it provides N specialized agents, M skills, 14 hooks" with actual counts from Step 1.
Update File Architecture comment counts if needed.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update agent/skill counts in CLAUDE.md"
```

### Task 23: Update CHANGELOG.md

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add [Unreleased] entry**

Add under `[Unreleased]` section:

```markdown
### Added
- 3-way prediction expert split: `vcodec-intra-pred-expert`, `vcodec-me-expert`, `vcodec-mc-expert`
- 14 new knowledge files for deepened domain expertise
- Block-parallel Phase 4 RTL development (`rtl-p4-block-parallel` skill)
- `rat-ultraloop` autonomous implement-review-improve loop
- Interface policy and contract test policy skills
- `p4-block-parallel-coordinator` and `p4-block-worker` agents

### Changed
- `vcodec-chief-standard-expert`: updated for 6 sub-domain experts
- `domain-consult`: 3-way prediction routing
- `stop-gate.sh`: ultraloop state detection

### Removed
- `vcodec-prediction-expert` (replaced by 3-way split)
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "changelog: add block-parallel domain expert feature"
```

### Task 24: Run Full Test Suite

**Files:**
- Reference: `tests/`

- [ ] **Step 1: Run all tests**

Run: `python3 -m pytest tests/ -v --tb=short`
Expected: all tests pass

- [ ] **Step 2: Verify hook scripts are valid POSIX shell**

Run: `sh -n hooks/rtl-orchestrator-inject.sh`
Expected: no syntax errors

- [ ] **Step 3: Verify all JSON files parse**

Run: `python3 -c "import json, glob; [json.load(open(f)) for f in glob.glob('**/*.json', recursive=True)]"`
Expected: no errors

- [ ] **Step 4: Final commit if any fixes needed**

```bash
git status  # review changed files — only stage files related to fixes
git add <specific files>
git commit -m "fix: address test/validation issues from integration"
```
