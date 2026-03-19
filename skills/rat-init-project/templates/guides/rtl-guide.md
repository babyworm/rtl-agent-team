# RTL Source Code

## Directory Structure

```
rtl/
├── {module}/                # Per-module RTL (e.g., entropy/, itq/, intra_pred/)
│   ├── {module}_top.sv      #   Module top-level (instantiates sub-modules)
│   ├── {module}_aa.sv       #   Sub-module A
│   └── {module}_bb.sv       #   Sub-module B
├── common/                  # Shared utilities (ICG, synchronizer, CDC primitives)
├── include/                 # Common defines, packages
├── top/                     # Top-level module instantiation
├── filelist_{module}.f      # Per-module filelist (MUST exist)
└── filelist_top.f           # Top-level filelist (MUST exist)
```

## Filelist Convention

| Type | Location | Required | Description |
|------|----------|----------|-------------|
| Module-level | `rtl/filelist_{module}.f` | **MUST exist** | Module's RTL sources + dependencies |
| Top-level | `rtl/filelist_top.f` | **MUST exist** | Includes all module filelists, adds top.sv |
| TB/test | in `sim/` scope | Dynamic | Scripts add TB files at runtime |

## Verification Flow (Quick Reference)

Every RTL file modification requires this flow:
```
1. Modify RTL
2. Lint:  verilator --lint-only -Wall rtl/{module}/*.sv
3. TB:    Create/update sim/{module}/tb_{module}.sv
4. Sim:   Run cocotb/verilator → PASS
```

Detailed coding rules: `.claude/rules/rtl-coding-conventions.md`
Verification gate rules: `.claude/rules/rtl-verification-gate.md`

<!-- rat-version: 0.7.7 -->
