# Coverage Tools Reference

> 이 문서는 `regression-run` 스킬의 상세 레퍼런스이다.
> 핵심 규칙은 `skills/regression-run/SKILL.md`의 `<Steps>` 참조.

## 1. Verilator Coverage

### 1.1 활성화 플래그

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

### 1.2 Coverage 데이터 수집

```bash
# 시뮬레이션 실행 후 coverage.dat 생성
./obj_dir/Vtop_module +verilator+coverage+file+cov_seed1.dat

# 여러 시드 실행
for seed in 1 2 3 4 5; do
  ./obj_dir/Vtop_module +verilator+seed+$seed \
    +verilator+coverage+file+cov_seed${seed}.dat
done
```

### 1.3 Coverage 리포트

```bash
# 텍스트 리포트
verilator_coverage --annotate coverage_report cov_seed*.dat

# Annotated source (소스 코드에 커버리지 표시)
verilator_coverage --annotate-all --annotate coverage_annotated cov_seed*.dat

# 특정 모듈만
verilator_coverage --annotate coverage_report --annotate-min 1 cov_seed*.dat
```

## 2. Coverage Merge

### 2.1 Verilator 내장 merge

```bash
# 다중 .dat 파일 merge
verilator_coverage --write merged.dat cov_seed*.dat

# Merge 후 리포트
verilator_coverage --annotate merged_report merged.dat
```

### 2.2 lcov Integration

```bash
# Verilator coverage → lcov 형식 변환
verilator_coverage --write-info coverage.info cov_seed*.dat

# lcov로 리포트 생성
genhtml coverage.info --output-directory coverage_html

# 브라우저에서 확인
# open coverage_html/index.html
```

### 2.3 lcov 필터링

```bash
# 특정 디렉토리만 포함
lcov --extract coverage.info '*/rtl/src/*' -o rtl_coverage.info

# 테스트벤치 제외
lcov --remove coverage.info '*/tb/*' '*/test/*' -o rtl_only.info

# HTML 리포트
genhtml rtl_only.info -o coverage_html
```

## 3. cocotb-coverage (Functional Coverage)

### 3.1 기본 사용

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

# 테스트에서 호출
sample(cmd=dut.i_cmd.value.integer, addr=dut.i_addr.value.integer)

# 리포트
coverage_db.report_coverage(cocotb.log.info, bins=True)
coverage_db.export_to_xml("functional_coverage.xml")
```

### 3.2 Coverage Goal 확인

```python
def check_coverage_goals(min_pct=90.0):
    """모든 커버 포인트가 목표 달성했는지 확인"""
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

### 4.1 표준 플로우

```bash
#!/bin/bash
# run_regression.sh

SEEDS="1 42 100 255 1000 9999 12345 54321 99999 777"
PASS=0
FAIL=0
COV_FILES=""

for seed in $SEEDS; do
  echo "=== Running seed $seed ==="

  # cocotb 실행
  RANDOM_SEED=$seed make -C tb/cocotb SIM=icarus 2>&1 | tee run_${seed}.log

  if [ $? -eq 0 ]; then
    PASS=$((PASS + 1))
  else
    FAIL=$((FAIL + 1))
  fi

  # Verilator coverage 수집 (Verilator SIM 사용 시)
  # COV_FILES="$COV_FILES cov_seed${seed}.dat"
done

echo "=== Regression Summary ==="
echo "Total: $((PASS + FAIL)), PASS: $PASS, FAIL: $FAIL"
echo "Pass rate: $(echo "scale=1; $PASS * 100 / ($PASS + $FAIL)" | bc)%"

# Coverage merge (Verilator)
# verilator_coverage --write merged.dat $COV_FILES
# verilator_coverage --annotate coverage_report merged.dat
```

### 4.2 cocotb 다중 시드

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

## 5. Coverage Types 비교

| 타입 | 측정 대상 | 도구 | 목표 |
|------|----------|------|------|
| Line coverage | 코드 라인 실행 여부 | Verilator | ≥ 95% |
| Toggle coverage | 신호 0↔1 전이 | Verilator | ≥ 85% |
| Branch coverage | if/case 분기 | Verilator | ≥ 90% |
| FSM coverage | 상태/전이 커버 | Verilator/UVM | 100% states |
| Functional coverage | 시나리오 커버 | cocotb-coverage/UVM | ≥ 90% |
| Assertion coverage | SVA cover hits | SymbiYosys cover | All reachable |

## 6. Coverage 리포트 형식

`skills/regression-run/templates/regression-report.md` 참조.

### 주요 지표

| 지표 | 설명 | 목표 |
|------|------|------|
| Pass Rate | pass / total seeds | 100% |
| Line Coverage | Verilator line | ≥ 95% |
| Functional Coverage | cocotb-coverage | ≥ 90% |
| Unique Failures | 고유 실패 시나리오 수 | 0 |
| Regression Time | 전체 실행 시간 | — |
