# Synthesis Flow

## Synthesis Estimation Policy (ASIC TSMC 28nm)

Synthesis is **estimation mode** by default. Target: ASIC TSMC 28nm, approximated with NanGate45 (FreePDK45).

| Item | Policy |
|------|--------|
| **Target** | ASIC TSMC 28nm (NOT FPGA) |
| **Liberty file** | NanGate45 (`NangateOpenCellLibrary_typical.lib`) as 28nm proxy |
| **Area metric** | Gate count (NAND2-FO2 equivalent). NAND2X1 ≈ 0.798 μm² |
| **Gate count** | `gate_count = total_area_um2 / 0.798` |
| **SDC** | Constraints MUST be created BEFORE synthesis estimation |

## sv2v Conversion Policy

| Tool | Input | Why sv2v |
|------|-------|---------|
| Yosys (synthesis) | sv2v-converted `.v` | Yosys SV support incomplete |
| SymbiYosys (formal) | sv2v-converted `.v` | Uses Yosys frontend internally |
| verilator/slang | `.sv` directly | Full SV support, no conversion needed |

## Standard ASIC Estimation Flow

```bash
# Use the synthesis wrapper (handles sv2v, tool selection, directory layout)
syn/scripts/run_syn.sh --tool yosys --top {module} -f rtl/filelist_{module}.f \
  --liberty NangateOpenCellLibrary_typical.lib

# Or via Makefile:
make syn TOP={module} LIBERTY=NangateOpenCellLibrary_typical.lib

# Parse results → gate count (NAND2-FO2 equivalent)
python skills/rtl-synth-check/scripts/parse_yosys_stat.py syn/log/yosys_{module}_*.log
```

## Directory Structure (DC-standard)

```
syn/
├── db/               # Binary databases (.ddc, .db, .genus_db)
├── vnet/             # Gate-level netlists (.v, .json)
├── svf/              # Setup Verification Flow (.svf, DC only)
├── scr/              # Generated scripts (.tcl, .ys) + replay/
├── rpt/              # Reports (area, timing, power, qor)
├── log/              # Synthesis logs
├── temp/             # Cache and temporary files
├── work/             # Tool work directories
├── scripts/          # Runner scripts (run_syn.sh, run_formality.sh, etc.)
└── constraints/      # SDC constraint files
    └── design.sdc
```

<!-- rat-version: 0.8.20 -->
