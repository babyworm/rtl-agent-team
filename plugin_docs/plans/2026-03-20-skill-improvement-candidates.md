# Skill Improvement Candidates

> Identified 2026-03-20. Criteria: action skills with no assets (templates/scripts/references/examples)
> that would benefit from concrete scaffolding to improve agent output quality.

## Priority 1: Utility Skills (asset-free, domain-specific logic)

| Skill | Lines | Current Focus | Most Valuable Asset | Effort |
|-------|-------|---------------|---------------------|--------|
| `ref-model` | 173 | C ref model (no clock/reset, DPI-C, bitexact) | C skeleton: Makefile + DPI-C header + main.c template | M |
| `bfm-develop` | 120 | SystemC TLM-2.0 AT BFM (AMBA, perf_baseline) | sc_module skeleton + TLM AT socket + functional parity assertion | M |
| `rtl-ipxact-gen` | 88 | IP-XACT XML from RTL ports/params | XML template + integration example | M |
| `rtl-ip-instantiate` | 101 | Wrapper for 3rd-party IP with port convention mapping | Wrapper module template + vendor port mapping guide | M |
| `rtl-bug-repro` | 95 | Minimal repro TB from failing sim | Repro TB template + VCD diff script | M |
| `rtl-document` | 105 | Port table + design summary from RTL/synth | Markdown doc template (port table, param table, hierarchy) | S |
| `rtl-model-consistency` | 93 | 3-way compare (refC vs BFM vs RTL) | Test vector alignment script + comparison report template | M |
| `rtl-conformance-test` | 105 | Bitexact match vs JM/HM golden | Comparison script + golden metadata format | M |

## Priority 2: Phase 5 Sub-Skills (verification quality)

| Skill | Lines | Current Focus | Most Valuable Asset | Effort |
|-------|-------|---------------|---------------------|--------|
| `rtl-p5s-perf-verify` | 47 | Latency/throughput vs BFM baseline | Perf monitor TB template (cycle counter, throughput measure) | M |
| `rtl-p5s-coverage-analyze` | 48 | Coverage gap analysis + risk ranking | Coverage report template + gap-to-test tracer format | M |
| `rtl-p5s-integration-test` | 62 | Tier 4 cross-module verification | Integration TB skeleton + module boundary protocol template | M |

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
