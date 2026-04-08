## RTL Project (managed by rtl-agent-team plugin)

### Directory Map

```
specs/          Input specifications and datasheets
refc/           C reference model (DPI-C compatible, C11)
bfm/            Bus Functional Models (C++17 SystemC TLM-2.0)
rtl/            Synthesizable SystemVerilog (IEEE 1800-2009)
  common/       Shared utilities (ICG, synchronizer, CDC primitives)
  include/      Packages, defines
  top/          Top-level integration
sim/            Simulation & testbenches
  formal/       SVA formal verification (.sby configs)
  cdc/          CDC analysis
lint/           Lint flow (scripts/ + reports/)
syn/            Synthesis flow (scripts/ + reports/)
docs/           Design documentation (phase-1 ~ phase-7)
reviews/        Phase gate review verdicts
```

### Build System

```
make sim TOP=<module>        Simulate (verilator)
make lint                    Lint (verilator + verible + slang)
make syn TOP=<module>        Synthesize (yosys)
make formal TOP=<module>     Formal verify (SymbiYosys)
make help                    All targets + commercial EDA options (_xrun, _vcs, _dc, ...)
```

### Phase Pipeline → Directory Mapping

| Phase | Primary Artifacts | Reviews |
|-------|-------------------|---------|
| P1 Research | `docs/phase-1-research/` | `reviews/phase-1-research/` |
| P2 Architecture | `docs/phase-2-architecture/` + `refc/` | `reviews/phase-2-architecture/` |
| P3 μArch/BFM | `docs/phase-3-uarch/` + `bfm/` | `reviews/phase-3-uarch/` |
| P4 RTL+Unit | `rtl/` + `sim/` + `docs/phase-4-rtl/` | `reviews/phase-4-rtl/` |
| P5 Verify | `formal/` + `docs/phase-5-verify/` | `reviews/phase-5-verify/` |
| P6 Design Note | — | `reviews/phase-6-review/` |
| P7 Exploration | `docs/phase-7-exploration/` (optional) | — |

### Rules & Conventions

- Coding conventions: `.claude/rules/rtl-coding-conventions.md`
- Verification gate: `.claude/rules/rtl-verification-gate.md`
- Per-directory details: see `CLAUDE.md` in each subdirectory
