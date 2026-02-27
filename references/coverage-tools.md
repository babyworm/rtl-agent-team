# Coverage Tools Reference

> This document is the detailed reference for the `rtl-regression-run` skill.
> For core rules, see `<Steps>` in `skills/rtl-regression-run/SKILL.md`.

## 1. Verilator Coverage

### 1.1 Activation Flags

```bash
# Line coverage
verilator --cc --coverage-line -f filelist.f

# Toggle coverage (signal toggling)
verilator --cc --coverage-toggle -f filelist.f

# User-inserted coverage points
verilator --cc --coverage-user -f filelist.f

# All coverage types
verilator --cc --coverage -f filelist.f
```

### 1.2 Coverage Data Collection

```bash
# Generate coverage.dat after simulation run
./obj_dir/Vtop_module +verilator+coverage+file+cov_seed1.dat

# Run with multiple seeds
for seed in 1 2 3 4 5; do
  ./obj_dir/Vtop_module +verilator+seed+$seed \
    +verilator+coverage+file+cov_seed${seed}.dat
done
```

### 1.3 Coverage Report

```bash
# Text report
verilator_coverage --annotate coverage_report cov_seed*.dat

# Annotated source (coverage annotated on source code)
verilator_coverage --annotate-all --annotate coverage_annotated cov_seed*.dat

# Specific module only
verilator_coverage --annotate coverage_report --annotate-min 1 cov_seed*.dat
```

## 2. Coverage Merge

### 2.1 Verilator Built-in Merge

```bash
# Merge multiple .dat files
verilator_coverage --write merged.dat cov_seed*.dat

# Report after merge
verilator_coverage --annotate merged_report merged.dat
```

### 2.2 lcov Integration

```bash
# Convert Verilator coverage to lcov format
verilator_coverage --write-info coverage.info cov_seed*.dat

# Generate report with lcov
genhtml coverage.info --output-directory coverage_html

# View in browser
# open coverage_html/index.html
```

### 2.3 lcov Filtering

```bash
# Include only specific directories
lcov --extract coverage.info '*/rtl/src/*' -o rtl_coverage.info

# Exclude testbench
lcov --remove coverage.info '*/tb/*' '*/test/*' -o rtl_only.info

# HTML report
genhtml rtl_only.info -o coverage_html
```

## 3. cocotb-coverage (Functional Coverage)

### 3.1 Basic Usage

```python
from cocotb_coverage.coverage import CoverPoint, CoverCross, coverage_db

@CoverPoint("top.cmd",
            xf=lambda cmd: cmd,
            bins=[("READ", 0), ("WRITE", 1)])
@CoverPoint("top.addr",
            xf=lambda addr: addr,
            bins=list(range(0, 0x100, 0x10)))
@CoverCross("top.cmd_x_addr",
            items=["top.cmd", "top.addr"])
def sample(cmd, addr):
    pass

# Call in test
sample(cmd=dut.i_cmd.value.integer, addr=dut.i_addr.value.integer)

# Report
coverage_db.report_coverage(cocotb.log.info, bins=True)
coverage_db.export_to_xml("functional_coverage.xml")
```

### 3.2 Coverage Goal Check

```python
def check_coverage_goals(min_pct=90.0):
    """Check whether all cover points have met the target"""
    all_met = True
    for name, cp in coverage_db.items():
        pct = cp.cover_percentage
        status = "PASS" if pct >= min_pct else "FAIL"
        cocotb.log.info(f"  {status}: {name} = {pct:.1f}%")
        if pct < min_pct:
            all_met = False
    return all_met
```

## 4. Regression Coverage Workflow

### 4.1 Standard Flow

```bash
#!/bin/bash
# run_regression.sh

SEEDS="1 42 100 255 1000 9999 12345 54321 99999 777"
PASS=0
FAIL=0
COV_FILES=""

for seed in $SEEDS; do
  echo "=== Running seed $seed ==="

  # Run cocotb
  RANDOM_SEED=$seed make -C tb/cocotb SIM=icarus 2>&1 | tee run_${seed}.log

  if [ $? -eq 0 ]; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
  fi

  # Collect Verilator coverage (when using Verilator SIM)
  # COV_FILES="$COV_FILES cov_seed${seed}.dat"
done

echo "=== Regression Summary ==="
echo "Total: $((PASS + FAIL)), PASS: $PASS, FAIL: $FAIL"
echo "Pass rate: $(echo "scale=1; $PASS * 100 / ($PASS + $FAIL)" | bc)%"

# Coverage merge (Verilator)
# verilator_coverage --write merged.dat $COV_FILES
# verilator_coverage --annotate coverage_report merged.dat
```

### 4.2 cocotb Multiple Seeds

```python
import cocotb
import random

@cocotb.test()
async def test_random(dut):
    seed = int(cocotb.plusargs.get("RANDOM_SEED", "0"))
    random.seed(seed)
    cocotb.log.info(f"Using seed: {seed}")

    # ... random stimulus ...
```

## 5. Coverage Types Comparison

| Type | Measurement Target | Tool | Goal |
|------|--------------------|------|------|
| Line coverage | Code line execution | Verilator | >= 95% |
| Toggle coverage | Signal 0<->1 transitions | Verilator | >= 85% |
| Branch coverage | if/case branches | Verilator | >= 90% |
| FSM coverage | State/transition coverage | Verilator/UVM | 100% states |
| Functional coverage | Scenario coverage | cocotb-coverage/UVM | >= 90% |
| Assertion coverage | SVA cover hits | SymbiYosys cover | All reachable |

## 6. Coverage Report Format

See `skills/rtl-regression-run/templates/regression-report.md`.

### Key Metrics

| Metric | Description | Goal |
|--------|-------------|------|
| Pass Rate | pass / total seeds | 100% |
| Line Coverage | Verilator line | >= 95% |
| Functional Coverage | cocotb-coverage | >= 90% |
| Unique Failures | Number of unique failure scenarios | 0 |
| Regression Time | Total execution time | — |
