# Flow-Test Design — Dog-fooding the RTL-Agent-Team Pipeline on a Canonical Huffman VLD

Date: 2026-07-15 · Author: flow-test session · Type: plugin-dev meta (validation run)

## 1. Objective

Validate the **plugin runtime pipeline end-to-end** by building a small, complete
variable-length decoder (`huffman_vld`) through Phases 1→6. Success = **pipeline
integrity** (all phases run, gates behave, real EDA tools execute, final RTL is
lint-clean and bitexact vs a C golden), NOT production silicon quality.

## 2. Runtime context reproduction

- Test project: `~/work/rat-vld-test` (separate git repo — clean plugin-runtime CWD,
  no pollution of the plugin source repo).
- Initialized by reproducing `rat-init-project` (its own scripts run: `inject_claude_md`,
  `generate_config`, `install_project_templates`) → full dir tree, `.claude/rules/`,
  guides, `rat_config.json`, Makefile, EDA scripts.

## 3. Orchestration: "orchestrator-as-workflow" (leaf-specialist mapping)

Confirmed empirically (CWD probe): subagents default to the **plugin repo** CWD, and
bare relative paths leak there; only absolute paths under `PROJECT_ROOT` are safe.
Implication — the pipeline is driven by the **Workflow** tool acting as the orchestrator,
calling the plugin's **leaf specialist agents** directly (not the multi-level orchestrator
agents), so that a loud `PROJECT_ROOT` absolute-path contract is injected into every
single-level agent prompt and cannot be dropped by un-instructed nested spawns.

Benefits: deterministic phase/gate control flow (JS), native parallel fan-out per phase,
resumable (`resumeFromRunId`), observable (`/workflows`). This doubles as a prototype of a
possible future plugin architecture (agents parameterized by explicit project root).

Deviation from as-shipped: the plugin's **Stop-hook hard gates** (Rule 5) are replaced by
JS gate control flow inside the workflow. To retain coverage of the headline feature, a
**separate Rule-5 hook sanity check** is run in the main session (verify
`rtl-verify-stop-gate.sh` blocks without `.rat/state/rtl-verify-done` and passes with it).

## 4. Phase → leaf-agent map + gates

| Phase | Leaf agent(s) | Gate (agent-executed, JS-branched) |
|-------|---------------|-------------------------------------|
| P1 Research | spec-analyst → rtl-critic (1 review round) | requirements + spec analysis exist under `docs/phase-1-research/` |
| P2 Arch+RefC | arch-designer ∥ ref-model-dev | **G2 functional**: `gcc` builds `refc/`, self-test decodes all 16 symbols + 256 windows == Appendix A |
| P3 uArch | uarch-designer | uarch spec (pipeline/regmap/FSM) exists + consistent with P2 |
| P4 RTL+Unit | rtl-coder → lint-checker → func-verifier(unit) | **G4**: verilator lint-clean + cocotb unit test PASS vs refC |
| P5 Verify | func-verifier(regression) ∥ sva-extractor ∥ coverage-analyst | **G5 (Rule-5 equiv)**: bitexact over 256 windows + randomized regression PASS + formal `o_error` safety proven |
| P6 DesignNote | design-note-writer | `reviews/phase-6-review/design-note.md` exists |

P5→P4 feedback: JS `while (attempt<=2)` loop calling `p4s-bugfix`-style fix agent on gate FAIL (Rule 7 bound).

## 5. Intentional deviations (simple design → lighter pipeline)

- P1 uses 1 review round (not the mandated 3) — flow test, not quality gate.
- No BFM (P3), no CDC (single clock), no protocol bus — out of scope by design.
- `o_error` is a formal safety target (complete code has no invalid codeword).

## 6. Success criteria

1. All 6 phases execute; each gate PASS or produces an actionable FAIL that the loop resolves.
2. Real tools run: gcc (refC), verilator (lint), cocotb (sim), sby (formal), yosys (synth smoke).
3. Final RTL bitexact vs C golden over 256 windows + randomized regression.
4. Rule-5 hook sanity confirms native Stop-gate behavior.
5. Artifacts land entirely under `~/work/rat-vld-test` (no plugin-repo pollution).
6. A flow-test report enumerates per-phase gate outcomes and any friction found.
