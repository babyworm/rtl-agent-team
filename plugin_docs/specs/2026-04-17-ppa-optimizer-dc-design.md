# PPA Optimizer (DC-based) — Design Spec

- **Date**: 2026-04-17
- **Status**: Draft — pending user review
- **Target release**: v0.10.0 (minor bump)
- **Author**: Hyun-Gyu (Ethan) Kim

## 1. Summary

Introduce a Design Compiler–centric Power/Performance/Area (PPA) optimization loop
as a post-verification stage. The loop runs DC synthesis, parses multi-report output
into a single JSON, invokes an LLM RTL patcher against that report, verifies
equivalence + functional smoke regression, and iterates until convergence or
early-plateau escalation to the user.

This feature is targeted at industrial flows where DC or Genus is available and
the RTL has already passed Phase 5 verification. The design favors **timing-first**
optimization and **early user escalation** when EDA tools have already saturated
the optimization space.

## 2. Motivation & Scope

### 2.1 Motivation

- Current pipeline stops at Phase 5 (verification) and Phase 6 (design-note). No
  structured loop exists for iterative PPA refinement after functional closure.
- Industrial flows need a reproducible way to:
  - Run DC synthesis with a PPA-oriented compile strategy
  - Identify the specific RTL changes (not just tool flags) that close timing,
    raise clock gating efficiency, or reduce power hotspots
  - Guarantee functional preservation (equivalence + regression) across every
    patch applied by the LLM
  - Know when to stop — LLM-driven RTL patches rarely beat what `compile_ultra
    -retime -gate_clock -scan` already accomplishes beyond the first 1-2 rounds
    of feedback.

### 2.2 In scope

- DC (`dc_shell`) and Genus commercial synthesis only
- RTL-level patches within an `allowed_edit_scope` (module source), with
  `frozen_scope` for interfaces/packages/common library
- Per-iteration equivalence + smoke-regression enforcement
- Convergence policy with explicit early-plateau escalation
- JSON schema for DC `.rpt` consolidation (`ppa-report.json`)

### 2.3 Out of scope (for v0.10.0)

- Yosys estimation fallback (no commercial tool → hard fail)
- Multi-corner/multi-mode optimization (single PVT corner per run)
- Place-and-route awareness (synthesis PPA only)
- Scaffold deployment via `rat-init-project` (deferred; evaluate in v0.11)

## 3. Pipeline Integration

### 3.1 Position

```
P1 → P2 → P3 → P4 → P5 (verify PASS)
                      │
                      └─► [PPA-Opt Loop]  ◄── new post-verify stage (no phase number)
                              │
                              └─► P6 (design note) → P7 (exploration)
```

- No new phase number. Labeled "Post-Verify Optimization".
- Optional stage. Users without commercial synthesis tools skip entirely.

### 3.2 Entry conditions

- **Soft (advisory)**: `reviews/phase-5-verify/final-compliance.md` verdict=PASS
- **Hard (enforced)**: `dc_shell` OR `genus` available in PATH
- **Hard (enforced)**: `requirements.json["ppa_targets"]` present (else scaffold
  writeback + halt)
- **Hard (enforced)**: git working tree clean (no uncommitted / untracked in
  `allowed_edit_scope`) — enables rollback guarantee

### 3.3 Exit conditions

| Condition | Action |
|-----------|--------|
| Convergence met (3-streak × `|Δ|<2%` OR all targets met) | Full Phase 5 regression → finalize, emit `.rat/state/ppa-opt-done` |
| Early plateau (iter 1–2 `|Δ|<1%`) | User escalation via `reviews/ppa-opt/early-plateau-escalation.md`, halt |
| `max_cycles` reached | Best-so-far recorded, user escalation |
| Equivalence FAIL | Rollback patch + halt |
| Smoke FAIL | Rollback patch + halt |
| Scope violation | Rollback patch + halt |
| DC synthesis error | Halt, dump log paths |

### 3.4 Phase 6 cascade

On normal convergence, the loop emits `.rat/state/ppa-opt-done`. The existing
`rtl-p6-cascade-gate.sh` detects this marker and flags P6 for re-review if the
design-note was written prior to PPA optimization.

## 4. Pipeline Rules (additions)

| # | Rule | Enforcement |
|---|------|-------------|
| 10 | Do not start DC-based PPA optimization without Phase 5 PASS | Policy — skill entry warning |
| 11 | Every PPA-Opt iteration must pass equivalence + smoke before accepting patch | Policy — orchestrator/skill internal guard (fail → rollback; not hook-enforced) |

Rule 5 (RTL modification requires functional verification) is satisfied because
every iteration runs equivalence + smoke. On normal convergence, the wrapper
emits `.rat/state/rtl-verify-done` so the existing Stop-gate does not block.

## 5. Architecture Overview

```
[Action Skill]  rtl-ppa-optimize-dc         (one-shot single iteration)
                rat-ultraloop-ppa            (auto-loop wrapper; wraps above)
                       │
                       ▼ Task(subagent_type="...")
[Orchestrator] ppa-optimizer-dc-orchestrator (opus)
                       │
      ┌────────────────┼────────────────┬───────────────┐
      ▼                ▼                ▼               ▼
[Specialist]  ppa-optimizer-dc    dc-report-parser  equivalence-checker
              (opus, patcher)     (sonnet, JSON)    (existing, reused)
                       │
                       │ skills: [ppa-optimizer-dc-policy]
                       ▼
[Policy Skill] ppa-optimizer-dc-policy
               (weights, convergence, Tcl snippets, heuristic)
```

### 5.1 Component inventory

| Component | New/Existing | Role |
|-----------|--------------|------|
| `rtl-ppa-optimize-dc` (action skill) | **New** | User entry point, 1 iteration |
| `rat-ultraloop-ppa` (action skill) | **New** | Convergence-driven auto-loop wrapper |
| `ppa-optimizer-dc-orchestrator` (agent) | **New** | Iteration coordinator |
| `ppa-optimizer-dc` (agent) | **New** | RTL patcher using user-supplied prompt template base |
| `dc-report-parser` (agent) | **New** | Wraps `parse_dc_reports.py`, emits `ppa-report.json` |
| `ppa-optimizer-dc-policy` (skill) | **New** | Heuristic / weights / convergence / Tcl fragment reference |
| `equivalence-checker` (agent) | Existing | Reused per-iteration (Formality > Conformal > Yosys) |
| `synthesis-reporter` (agent) | Existing | Final human-readable summary |
| `power-analyzer`, `timing-advisor` (agent) | Existing | Optional read-only advisor lanes |

## 6. Data Flow (per iteration)

```
 (1) Read requirements.json → ppa_targets + weights + convergence
 (2) Read rtl/{module}/**/*.sv (allowed_edit_scope)
 (3) run_syn.sh --tool dc_shell --top {top} -f filelist.f --liberty ${LIB}
       └─► syn/rpt/{top}_{area,timing,power,qor,clock_gating,vt}.rpt
 (4) parse_dc_reports.py syn/rpt/ > syn/ppa-report.json             ◄── new
 (5) Task(subagent_type="ppa-optimizer-dc",
          inputs=[RTL, ppa-report.json, requirements.json, prev rationale])
       └─► outputs: patch.diff + rationale.md + dc-tcl-snippet.tcl
 (6) Snapshot pre-patch RTL (for rollback reference)
 (7) Apply patch.diff (git apply)
 (8) Scope validation: diff must touch only allowed_edit_scope
       └─► violation → git checkout . → halt
 (9) Task(equivalence-checker) — reference = iter-{N-1} snapshot (or pre-patch)
       └─► FAIL → git checkout . → halt
 (10) Run smoke regression (sim/{module} make smoke)
       └─► FAIL → git checkout . → halt
 (11) Re-run run_syn.sh → new ppa-report.json
 (12) Compute Δ vs. iter-{N-1}
       └─► Timing regression guard: Δ_wns ≥ -0.02 ns required, else rollback
 (13) Update .rat/state/ppa-loop-state.json (history, streak, verdict)
 (14) Check convergence / early-plateau / max_cycles
       └─► terminate or continue N+1
```

## 7. JSON Schemas

### 7.1 `syn/ppa-report.json`

```json
{
  "schema_version": "1.1",
  "tool": "dc_shell",
  "design": "vc_transform_8x8",
  "iteration": 3,
  "timestamp": "2026-04-17T14:22:13Z",
  "liberty": ".../tcbn07_tt_1p0v_25c.lib",
  "sdc": "syn/constraints/design.sdc",

  "area": {
    "total_um2": 45230.5,
    "combinational_um2": 28150.2,
    "sequential_um2": 17080.3,
    "buf_inv_um2": 2341.7,
    "macro_um2": 0.0,
    "per_module": [
      {"hier": "top/u_core", "um2": 12345.6, "pct": 27.3, "cells": 4521}
    ]
  },

  "timing": {
    "clock": "sys_clk",
    "period_ns": 1.25,
    "wns_ns": -0.083,
    "tns_ns": -2.41,
    "num_violating_paths": 17,
    "critical_paths": [
      {
        "rank": 1,
        "from": "u_core/u_s1/pix_reg[7]/CP",
        "to":   "u_core/u_s2/sum_reg[15]/D",
        "slack_ns": -0.083,
        "data_delay_ns": 1.201,
        "logic_levels": 17,
        "top_cells": ["MUX4_X1:3", "XOR2_X1:4", "FA_X1:2"]
      }
    ]
  },

  "power": {
    "analysis_effort": "high",
    "total_mw": 124.37,
    "dynamic_mw": 98.21,
    "leakage_mw": 26.16,
    "clock_mw": 42.10,
    "clock_pct": 42.8,
    "net_mw": 38.44,
    "internal_mw": 14.92,
    "register_mw": 14.92,
    // register_mw is a legacy alias for internal_mw (schema 1.0 compatibility).
    "combinational_mw": 2.75,
    "per_module": [
      {"hier": "top/u_core", "total_mw": 71.2, "pct": 57.3}
    ]
  },

  "clock_gating": {
    "total_registers": 3421,
    "gated_registers": 2871,
    "gating_efficiency_pct": 83.9,
    "ungated_banks": [
      {"hier": "top/u_io_ctrl/cfg_reg", "registers": 32}
    ]
  },

  "vt_group": {
    "LVT_pct": 4.2,
    "SVT_pct": 61.8,
    "HVT_pct": 34.0
  },

  "qor": {
    "design_wns_ns": -0.083,
    "design_tns_ns": -2.41,
    "worst_hold_slack_ns": 0.023,
    "status": "TIMING_VIOLATION"
  },

  "warnings": [
    {"category": "unmapped_cell", "detail": "GTECH_MUX4 at u_core/u_s1"},
    {"category": "inferred_latch", "detail": "latch at ctrl_fsm.sv:45"}
  ]
}
```

### 7.2 `.rat/state/ppa-loop-state.json`

```json
{
  "mode": "ppa-loop",
  "cycle": 3,
  "max_cycles": 4,
  "weights": {"timing": 0.7, "power": 0.2, "area": 0.1},
  "convergence": {
    "delta_pct": 2.0,
    "streak_required": 3,
    "current_streak": 2,
    "early_plateau_pct": 1.0,
    "early_plateau_checked": true,
    "targets_met": {"timing": false, "power": true, "area": true},
    "history": [
      {"iter": 1, "power_mw": 135.2, "wns_ns": -0.12, "area_um2": 48200, "weighted_delta_pct": null},
      {"iter": 2, "power_mw": 127.4, "wns_ns": -0.08, "area_um2": 46100, "weighted_delta_pct": -3.2},
      {"iter": 3, "power_mw": 124.3, "wns_ns": -0.083, "area_um2": 45230, "weighted_delta_pct": -1.1}
    ]
  },
  "allowed_edit_scope": ["rtl/{target_module}/**/*.sv"],
  "frozen_scope": ["rtl/common/**", "rtl/pkg/**", "rtl/intf/**"],
  "last_cycle_timestamp": 1744897333,
  "auto_continue_minutes": 30
}
```

### 7.3 `requirements.json["ppa_targets"]` extension

```json
{
  "clock_hz": 800000000,
  "ppa_targets": {
    "power_mw": 100,
    "timing_slack_ns": 0.10,
    "area_um2": 45000,
    "weights": {"timing": 0.7, "power": 0.2, "area": 0.1},
    "max_fanout": 32,
    "max_transition_ns": 0.30,
    "convergence": {
      "delta_pct": 2.0,
      "streak": 3,
      "early_plateau_pct": 1.0,
      "max_cycles": 4
    }
  }
}
```

All fields have defaults if missing. `weights` normalization enforced at load
time (sum must equal 1.0 within ±0.01).

## 8. Convergence & Escalation Policy

### 8.1 Three-tier termination

| Tier | Condition | Action |
|------|-----------|--------|
| **Early plateau** (new) | At iter 1 or 2, weighted `|Δ|<1%` | Halt immediately, write `reviews/ppa-opt/early-plateau-escalation.md`, report to user |
| Normal convergence | Streak of 3 iterations with weighted `|Δ|<2%` OR all targets met | Run full Phase 5 regression, finalize, emit `ppa-opt-done` |
| Max cycles | `max_cycles` reached (default 4) | Record best-so-far iter, escalate to user |

### 8.2 Weighted delta formula

```
weighted_Δ = w_timing × Δ_timing_norm
          + w_power  × Δ_power_norm
          + w_area   × Δ_area_norm

where Δ_timing_norm = (wns_current − wns_prev) / target_period_ns
      Δ_power_norm  = (power_prev − power_current) / target_power_mw
      Δ_area_norm   = (area_prev − area_current)  / target_area_um2
```

Positive `weighted_Δ` = improvement. Early-plateau triggers when absolute value
is under 1% for two consecutive iterations (or iter 1 alone if iter 2 has not
yet run and the user invokes one-shot).

### 8.3 Timing regression guard

```
If Δ_wns < -0.02 ns (i.e., timing gets more than 20 ps worse):
    rollback patch (git checkout .)
    halt loop
    write reviews/ppa-opt/timing-regression-iter-{N}.md
```

Applied even if the patch improves power/area. Timing is never traded in the
default weights configuration.

### 8.4 Early-plateau escalation report

```
reviews/ppa-opt/early-plateau-escalation.md

## Verdict: EARLY_PLATEAU
EDA tool auto-optimization appears saturated; RTL-level patches yielded
< 1% weighted improvement over 2 iterations.

## Iteration history
| iter | power_mw | wns_ns | area_um2 | weighted_Δ |

## Current bottleneck
- Critical path: ... (logic levels / top cells)
- Power hotspot: ... (clock %, module hier)
- Clock gating efficiency: ...%

## Why further iteration is unlikely to help
- [analysis]

## Recommended user actions
1. Review μArch (pipeline depth, algorithm variant)
2. Relax spec targets (clock / power budget)
3. Evaluate technology change (stdcell library, Vt mix)
4. Force continuation via requirements.json["ppa_targets"]["convergence"]["max_cycles"] = N (N > 4)
```

## 9. Optimization Heuristic (timing-first)

Defined authoritatively in `skills/ppa-optimizer-dc-policy/SKILL.md`. Summary:

```
Rule 1 (HIGHEST · aggressive): Timing closure
   - WNS < 0 → critical-path analysis, pipelining, retiming hints, logic restructuring
   - Logic levels > 12 at 100MHz → register rebalancing
   - REJECT any patch that worsens WNS beyond the 20 ps guard

Rule 2 (MAIN · safe): Clock gating coverage
   - Ungated register banks (always_ff without enable) → introduce enable
   - DC auto-gating missed signals → expose the missed enable condition
   - Target: raise gating_efficiency_pct 80% → 90%+

Rule 3 (SECONDARY · timing-neutral only): Operand isolation
   - Multiplier/divider with idle cycles > 50%
   - Accepted only if timing unchanged

Rule 4 (SECONDARY · timing-neutral only): Resource sharing
   - Duplicate operator instances
   - Accepted only if timing unchanged

REJECT set:
   - Any patch worsening WNS beyond 20 ps
   - Any patch creating inferred latches
   - Any patch touching frozen_scope
```

## 10. Error Handling Matrix

| Condition | Action |
|-----------|--------|
| `dc_shell` / `genus` not detected | Skill entry hard FAIL |
| `requirements.json["ppa_targets"]` missing | Scaffold writeback + halt (user edit required) |
| Git working tree dirty in `allowed_edit_scope` | Skill entry hard FAIL |
| DC synthesis error | Halt, log syn/log paths to user |
| `parse_dc_reports.py` failure | Halt, dump raw `.rpt` paths |
| Patch touches `frozen_scope` | Rollback + halt (scope violation) |
| Equivalence FAIL | Rollback + halt, `reviews/ppa-opt/equiv-fail-iter-{N}.md` |
| Smoke FAIL | Rollback + halt, `reviews/ppa-opt/smoke-fail-iter-{N}.md` |
| Timing regression > 20 ps | Rollback + halt, `reviews/ppa-opt/timing-regression-iter-{N}.md` |
| Streak of 3 met | Normal convergence → full P5 regression |
| `max_cycles` reached | Best-so-far recorded, escalate |
| Early plateau detected (iter 1–2) | Halt, escalate |
| Auto-continue 30-min path | Existing `stop-gate.sh` + `ppa-loop-state.json` pattern reused |

## 11. Artifacts Layout

```
docs/ppa-opt/                         ◄── user-project artifact
├── iter-01/
│   ├── ppa-report.json
│   ├── dc-reports/
│   │   ├── area.rpt
│   │   ├── timing.rpt
│   │   ├── power.rpt
│   │   ├── qor.rpt
│   │   ├── clock_gating.rpt
│   │   └── vt.rpt
│   ├── patch.diff
│   ├── rationale.md
│   ├── dc-tcl-snippet.tcl
│   ├── equiv-report.md
│   └── smoke-report.md
├── iter-02/
│   └── ...
├── convergence.csv           (iter, power_mw, wns_ns, tns_ns, area_um2, Δ_weighted)
└── final-report.md

.rat/state/
├── ppa-loop-state.json       (cycle, history, scope, convergence)
└── ppa-opt-done              (marker for P6 cascade)

reviews/ppa-opt/
├── convergence-review.md
├── early-plateau-escalation.md   (if applicable)
├── equiv-fail-iter-{N}.md        (if applicable)
├── smoke-fail-iter-{N}.md        (if applicable)
└── timing-regression-iter-{N}.md (if applicable)
```

## 12. Hook Integration (no new hooks)

Only minimal modifications to existing hooks:

| Hook | Modification |
|------|--------------|
| `rtl-edit-tracker.sh` | If `.rat/state/ppa-loop-state.json` exists, skip staleness counting for edits inside `allowed_edit_scope` |
| `stop-gate.sh` | Recognize `mode: "ppa-loop"` and apply auto-continue logic identical to existing ultraloop branch |
| `rtl-p6-cascade-gate.sh` | If `.rat/state/ppa-opt-done` mtime > P6 artifact mtime, flag P6 re-review required |
| `rtl-verify-stop-gate.sh` | No changes; `rat-ultraloop-ppa` writes `.rat/state/rtl-verify-done` on normal convergence |
| `rtl-skill-activation.sh` | New skill names registered via `skill-completion-criteria.json` update |

## 13. Testing Strategy

### 13.1 Unit tests (`tests/unit/`)

| Test | Coverage |
|------|----------|
| `test_parse_dc_reports.py` | Fixture `.rpt` → expected JSON, all 6 report types |
| `test_compute_delta.py` | Weighted-Δ formula, convergence boundary, early-plateau trigger |
| `test_ppa_loop_state.py` | State file schema validity and update protocol |
| `test_ppa_scope_guard.py` | Patch diff parsing, scope violation detection |

### 13.2 Fixtures (`tests/fixtures/dc-reports/`)

Redacted real DC outputs:
- `area.rpt`, `timing.rpt`, `power.rpt`, `qor.rpt`, `clock_gating.rpt`, `vt.rpt`
- `expected-ppa-report.json`

All tests must run on CI with Python stdlib only (no numpy/hjson/scipy). DC binary
is not required — tests use fixtures.

### 13.3 Integration test (`tests/integration/`)

`test_ppa_loop_integration.py`:
- Mock `run_syn.sh` that returns fixture `.rpt` files
- Stub out `equivalence-checker` and smoke regression with success results
- Verify end-to-end state transitions, file artifacts, and convergence path

### 13.4 CI impact

- `pytest tests/unit/` continues as today. No new dependencies.
- shellcheck applies to any new shell scripts (none expected — `run_syn.sh`
  already covered).
- `scripts/sync_orchestrator_inject.sh` run in CI as a drift check after the
  routing SSOT update.

## 14. Versioning & Release Plan

**Target**: v0.9.3 → v0.10.0 (minor bump; new feature, no breaking changes)

### 14.1 Required updates (per CLAUDE.md §14 checklist)

- `package.json` version
- `.claude-plugin/plugin.json` version
- `.claude-plugin/marketplace.json` (`metadata.version` + `plugins[0].version`)
- `README.md` + `README_kr.md` (marketplace table + skill/agent counts)
- `CHANGELOG.md` — new `## [0.10.0] - 2026-04-17` section

### 14.2 Component-count updates

- Skills: 94 → **97** (+ `rtl-ppa-optimize-dc`, `rat-ultraloop-ppa`, `ppa-optimizer-dc-policy`)
- Agents: 94 → **97** (+ `ppa-optimizer-dc-orchestrator`, `ppa-optimizer-dc`, `dc-report-parser`)
- Hooks: 14 (unchanged)

### 14.3 Routing SSOT

- Update `skills/rtl-orchestrate/SKILL.md` routing table:
  - "PPA optimize, DC PPA, power/timing/area optimize" → `rtl-ppa-optimize-dc`
  - "PPA auto-loop, ultraloop PPA" → `rat-ultraloop-ppa`
- Run `sh scripts/sync_orchestrator_inject.sh`

### 14.4 `phase-registry.json` update

- New phase ID: `ppa-opt` (no numeric index; after P5, before P6)
- Skill → phase: `rtl-ppa-optimize-dc → ppa-opt`, `rat-ultraloop-ppa → ppa-opt`
- Agent → skill: `ppa-optimizer-dc-orchestrator → rtl-ppa-optimize-dc`,
  `ppa-optimizer-dc → rtl-ppa-optimize-dc`, `dc-report-parser → rtl-ppa-optimize-dc`

### 14.5 Pre-push CI verification

Per CLAUDE.md §12 (CRITICAL):
```
python3 -m pytest tests/unit/ --ignore=tests/unit/test_bd_rate.py -x -q
shellcheck hooks/*.sh hooks/lib/*.sh scripts/*.sh
```

## 15. Implementation Order

Each step is verifiable in isolation. Steps 1-5 can run on CI without DC installed.

1. `parse_dc_reports.py` + unit tests + fixtures
2. `compute_delta.py` + convergence unit tests
3. `skills/ppa-optimizer-dc-policy/SKILL.md` (body) + `templates/dc-compile-ppa.tcl`
4. `agents/ppa-optimizer-dc.md` (patcher, derived from user-supplied template)
5. `agents/dc-report-parser.md` (thin wrapper around parse_dc_reports.py)
6. `agents/ppa-optimizer-dc-orchestrator.md` (loop coordination)
7. `skills/rtl-ppa-optimize-dc/SKILL.md` (action skill, one-shot)
8. `skills/rat-ultraloop-ppa/SKILL.md` (auto-loop wrapper)
9. Hook modifications: `rtl-edit-tracker.sh`, `stop-gate.sh`, `rtl-p6-cascade-gate.sh`
10. `skill-completion-criteria.json` + `phase-registry.json` updates
11. Routing SSOT update + `sync_orchestrator_inject.sh` run
12. `README.md` + `README_kr.md` + `CHANGELOG.md` + version bump batch
13. Integration test + full `pytest` + shellcheck
14. Commit strategy: atomic commits per implementation step, final release commit

## 16. Non-Goals / Future Work

- **v0.11 candidate**: Scaffold deployment via `rat-init-project`
- **v0.11 candidate**: Multi-corner (TT/FF/SS) awareness
- **v0.12 candidate**: Yosys estimation-mode fallback (for open-source flows)
- **Future**: Integrate `power-analyzer` and `timing-advisor` as parallel read-only
  advisors inside the orchestrator (currently listed as optional but not wired)
- **Future**: `--force-cycles=N` CLI override for `rat-ultraloop-ppa` when user
  intentionally wants to exceed `max_cycles=4`

## 17. Risks & Open Questions

| # | Risk / question | Mitigation |
|---|-----------------|------------|
| R1 | DC report format varies by version | Parser handles vN.M as they surface; fixtures pinned to a DC version |
| R2 | LLM patch exceeds `allowed_edit_scope` | Per-iter diff validation; rollback on violation |
| R3 | Equivalence tool absent in user environment | Document requirement; fall back to Yosys equiv_* with WARNING |
| R4 | smoke regression harness not standardized across projects | Use `sim/{module}/Makefile make smoke` convention; require user to provide if absent |
| R5 | EDA tool absent at CI | All unit tests run on fixtures only; integration test stubs DC |
| R6 | Token budget for large designs | Report summarization in agent prompt; top-N critical paths only |

## 18. Appendix: User-supplied prompt template mapping

| Template section | Destination |
|------------------|-------------|
| §1 Design Objectives | `agents/ppa-optimizer-dc.md` `<Role>`, runtime-injected values from `requirements.json["ppa_targets"]` |
| §2 Current Synthesis Report Analysis | `agents/ppa-optimizer-dc.md` `<Investigation_Protocol>` |
| §3 Optimization Strategy Selection | `skills/ppa-optimizer-dc-policy/SKILL.md` |
| §4 DC Tcl Script requirements | `skills/ppa-optimizer-dc-policy/SKILL.md` + `templates/dc-compile-ppa.tcl` |
| §5 RTL Patch generation rules | `agents/ppa-optimizer-dc.md` `<Constraints>`, `<Output_Format>` |
| §6 Iteration & Convergence | `skills/ppa-optimizer-dc-policy/SKILL.md` |
| §7 Output format | `agents/ppa-optimizer-dc.md` `<Output_Format>` |

Domain considerations (video codec / image processing) are injected via existing
`domain-packages/` path (referenced in agent prompt `<References>`), not hardcoded.
