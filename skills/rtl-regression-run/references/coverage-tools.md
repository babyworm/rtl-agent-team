> **DEPRECATED**: This file is under the deprecated `rtl-regression-run` skill.
> Use `rtl-p5s-func-verify` (Tier 3) for module-level regression with coverage.
> See also `references/coverage-tools.md` for the canonical coverage reference.

# RTL Coverage Tools Reference

## Verilator Coverage

### Enable Coverage Collection
```bash
# Compile with coverage enabled
verilator --cc --exe --build -j 0 \
  --coverage          # Enable all coverage types
  --coverage-line     # Line coverage only
  --coverage-toggle   # Toggle coverage only
  --trace-fst         # Also enable waveform traces
  rtl/*/*.sv sim/sim_main.cpp

# Or via cocotb Makefile
make -C sim/ SIM=verilator EXTRA_ARGS="--coverage --trace-fst" \
  TOPLEVEL=dut MODULE=test_dut
```

### Process Coverage Data
```bash
# Convert Verilator coverage to lcov format
verilator_coverage --write-info coverage.info coverage.dat

# Generate HTML report
genhtml coverage.info --output-directory coverage_html

# Merge multiple coverage runs (multi-seed)
verilator_coverage --write-info merged.info \
  seed_1/coverage.dat seed_42/coverage.dat seed_1337/coverage.dat

# Text summary
verilator_coverage --annotate coverage_annotated/ coverage.dat
```

### Coverage Types in Verilator

| Type | What It Measures | Flag |
|------|-----------------|------|
| Line | Each executable line executed | `--coverage-line` |
| Toggle | Each bit toggled 0→1 and 1→0 | `--coverage-toggle` |
| Branch | Each if/case branch taken | implicit in `--coverage` |
| User | `/*verilator coverage_on/off*/` regions | annotation-based |

## Icarus Verilog Coverage

Icarus Verilog does not have built-in coverage. Use cocotb-coverage for functional coverage:

```python
from cocotb_coverage.coverage import CoverPoint, CoverCross, coverage_db

@CoverPoint("top.data_range",
    xf=lambda data: data,
    bins=[range(0, 64), range(64, 128), range(128, 192), range(192, 256)])
def sample(data):
    pass

# At end: generate report
coverage_db.report_coverage(cocotb.log.info, bins=True)
coverage_db.export_to_xml("sim/coverage/functional_coverage.xml")
```

## lcov Integration

```bash
# Merge coverage files from multiple seeds
lcov --add-tracefile seed_1.info --add-tracefile seed_42.info \
  --output-file merged.info

# Remove unwanted files from coverage (testbench files)
lcov --remove merged.info '*/sim/*' '*/test_*' --output-file filtered.info

# Generate HTML report
genhtml filtered.info --output-directory coverage_report/ \
  --title "RTL Regression Coverage" --legend

# Summary (text)
lcov --summary filtered.info
```

## Coverage Targets

| Type | Target | Signoff |
|------|--------|---------|
| Line coverage | ≥90% | Required |
| Toggle coverage | ≥80% | Required |
| Branch coverage | — | Informational |
| FSM state coverage | ≥70% | Required |
| Functional coverage | — | Informational |
| Cross coverage | — | Informational |

## Multi-Seed Regression Strategy

```bash
#!/bin/bash
# run_regression.sh — Multi-seed regression with coverage merge
SEEDS=(1 42 123 1337 65536)
PASS=0; FAIL=0

for SEED in "${SEEDS[@]}"; do
  echo "=== Running seed $SEED ==="
  make -C sim/ SIM=verilator RANDOM_SEED=$SEED \
    EXTRA_ARGS="--coverage" TOPLEVEL=dut MODULE=test_dut 2>&1 \
    | tee sim/regression/seed_${SEED}.log

  if [ $? -eq 0 ]; then
    ((PASS++))
  else
    ((FAIL++))
    # Stop early if failure rate > 5%
    TOTAL=$((PASS + FAIL))
    RATE=$((FAIL * 100 / TOTAL))
    if [ $RATE -gt 5 ]; then
      echo "HALT: Failure rate ${RATE}% exceeds 5% threshold"
      break
    fi
  fi
done

# Merge coverage
verilator_coverage --write-info merged.info sim/regression/*/coverage.dat
genhtml merged.info -o sim/coverage/html/

echo "=== REGRESSION SUMMARY ==="
echo "Seeds: ${#SEEDS[@]}, Pass: $PASS, Fail: $FAIL"
```

## Coverview (Interactive Coverage Dashboards)

For visual coverage analysis, use Antmicro's Coverview tool:
```bash
pip install coverview
coverview --input coverage.info --output dashboard/
# Opens interactive HTML dashboard with drill-down coverage exploration
```
