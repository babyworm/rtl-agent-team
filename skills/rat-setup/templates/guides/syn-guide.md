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
# 1. Generate SDC (constraint-writer agent)
# 2. sv2v conversion
sv2v rtl/{module}/*.sv -o rtl/{module}/{module}_v2v.v
# 3. Yosys synthesis estimation with NanGate45
yosys -p "read_verilog rtl/{module}/{module}_v2v.v; \
  synth -top {module}; \
  dfflibmap -liberty NangateOpenCellLibrary_typical.lib; \
  abc -liberty NangateOpenCellLibrary_typical.lib; \
  stat -liberty NangateOpenCellLibrary_typical.lib" \
  | tee syn/reports/{module}_synth.txt
# 4. Parse results → gate count (NAND2-FO2 equivalent)
python skills/rtl-synth-check/scripts/parse_yosys_stat.py syn/reports/{module}_synth.txt
```

## Directory Structure

```
syn/
├── scripts/          # Synthesis scripts (run_syn.sh)
├── constraints/      # SDC constraint files
│   ├── design.sdc
│   └── cdc_constraints.sdc
└── reports/          # Per-module results ({module}_synth.txt)
```
