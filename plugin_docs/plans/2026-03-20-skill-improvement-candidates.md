# Skill Improvement Candidates

> Identified 2026-03-20. Criteria: action skills with no assets (templates/scripts/references/examples)
> that would benefit from concrete scaffolding to improve agent output quality.

## Priority 1: Utility Skills (asset-free, domain-specific logic)

| Skill | Lines | Current Focus | Most Valuable Asset | Effort |
|-------|-------|---------------|---------------------|--------|
| `ref-model` | 173 | C ref model (no clock/reset, DPI-C, bitexact) | C skeleton: Makefile + DPI-C header + main.c template | ✅ done |
| `bfm-develop` | 120 | SystemC TLM-2.0 AT BFM (AMBA, perf_baseline) | sc_module skeleton + TLM AT socket + functional parity assertion | ✅ done |
| `rtl-ipxact-gen` | 88 | IP-XACT XML from RTL ports/params | XML template + integration example | ✅ done |
| `rtl-ip-instantiate` | 101 | Wrapper for 3rd-party IP with port convention mapping | Wrapper module template + vendor port mapping guide | ✅ done |
| `rtl-bug-repro` | 95 | Minimal repro TB from failing sim | Repro TB template + VCD diff script | ✅ done |
| `rtl-document` | 105 | Port table + design summary from RTL/synth | Markdown doc template (port table, param table, hierarchy) | ✅ done (2026-05-12) |
| `rtl-model-consistency` | 93 | 3-way compare (refC vs BFM vs RTL) | Test vector alignment script + comparison report template | ✅ done |
| `rtl-conformance-test` | 105 | Bitexact match vs JM/HM golden | Comparison script + golden metadata format | ✅ done |

## Priority 2: Phase 5 Sub-Skills (verification quality)

| Skill | Lines | Current Focus | Most Valuable Asset | Effort |
|-------|-------|---------------|---------------------|--------|
| `rtl-p5s-perf-verify` | 47 | Latency/throughput vs BFM baseline | Perf monitor TB template (cycle counter, throughput measure) | ✅ done |
| `rtl-p5s-coverage-analyze` | 48 | Coverage gap analysis + risk ranking | Coverage report template + gap-to-test tracer format | ✅ done |
| `rtl-p5s-integration-test` | 62 | Tier 4 cross-module verification | Integration TB skeleton + module boundary protocol template | ✅ done |

## Implementation Order (by impact × effort)

1. `rtl-document` — S effort, immediate value (most frequently used utility)
2. `rtl-bug-repro` — M effort, debugging accelerator
3. `rtl-ipxact-gen` — M effort, integration enabler
4. `rtl-p5s-perf-verify` — M effort, Phase 5 gap
5. `rtl-p5s-coverage-analyze` — M effort, Phase 5 gap
6. `rtl-p5s-integration-test` — M effort, Phase 5 gap
7. `ref-model` — M effort, Phase 2 quality
8. `bfm-develop` — M effort, Phase 3 quality
9. `rtl-ip-instantiate` — M effort, integration utility
10. `rtl-model-consistency` — M effort, cross-phase consistency
11. `rtl-conformance-test` — M effort, codec-specific

## Asset Types

- **T (Template)**: Skeleton files the agent copies and fills in
- **S (Script)**: Executable scripts for automation (build, compare, run)
- **R (Reference)**: Documentation/guides the agent reads for context
- **E (Example)**: Complete worked examples for few-shot guidance

## Well-Equipped Skills (reference models)

| Skill | Assets | What makes them effective |
|-------|--------|--------------------------|
| `rtl-p5s-func-verify` | T,S,R,E (7) | cocotb TB, regression runner, ecosystem guide, examples |
| `rtl-lint-check` | T,S,R,E (5) | lint scripts, tool reference, output examples |
| `rtl-synth-check` | T,S,R (7) | synthesis scripts, SDC templates |
| `rat-auto-design` | T,R (14) | state templates, phase guides |
| `systemverilog` | T,R,E (4) | module template, reference doc, examples |

## Reference Pattern

`rtl-document` (completed 2026-05-12) is the reference implementation of the
"asset bundle pattern". Spec: `plugin_docs/specs/2026-05-12-rtl-document-asset-bundle-design.md`.
Plan: `plugin_docs/plans/2026-05-12-rtl-document-asset-bundle-plan.md`.

Subsequent skill upgrades in this list follow that pattern: deterministic
parser script with a JSON schema, snippet-composing renderer with
`<!-- LLM_FILL: ... -->` markers, ≤200-line references guide, three worked
examples covering the complexity spectrum, and a lean SKILL.md (~90-125 lines,
~900 words) applying the Anthropic prompting + plugin-dev skill-development
guidelines documented in §5.3 of the spec.

## Update — v0.11.0 + clone pack PR (2026-05-13)

All 11 candidates migrated. The reference pattern (asset-bundle layout: `templates/`, `scripts/`, `references/{name}-conventions.md`, `examples/`) is now in place across every utility skill in this list. Deep script/example fills are tracked per-skill in follow-up PRs.
