# Verilator Warning Categories and Waiver Format

> 이 문서는 `lint-check` 스킬의 상세 레퍼런스이다.
> 핵심 규칙은 `skills/lint-check/SKILL.md`의 `<Steps>` 참조.

## 1. Severity 분류

| Severity | 의미 | 기본 동작 |
|----------|------|----------|
| Error | 합성 불가 코드 | 중단, 수정 필수 |
| Warning | 잠재적 문제 | 표시, 선택적 수정 |
| Info | 참고 사항 | 비활성화 가능 |

## 2. 주요 Warning 카테고리

### 2.1 Critical (반드시 수정)

| Warning | 의미 | 수정 방법 |
|---------|------|----------|
| `LATCH` | Latch 추론됨 | `always_comb`에 `default` 추가, 모든 경로에서 신호 할당 |
| `COMBDLY` | Combinational 블록에 `<=` 사용 | `=` (blocking) 사용 |
| `BLKSEQ` | Sequential 블록에 `=` 사용 | `<=` (non-blocking) 사용 |
| `MULTIDRIVEN` | 신호에 다중 드라이버 | 단일 드라이버로 구조 변경 |
| `UNDRIVEN` | 출력 포트 미연결 | 드라이버 연결 또는 의도적이면 `= '0` |
| `UNUSED` | 입력 신호 미사용 | 사용하거나 waiver 추가 |
| `WIDTH` | 비트폭 불일치 | 명시적 캐스팅 또는 비트폭 조정 |
| `CASEINCOMPLETE` | case 문 불완전 | `default` 추가 |

### 2.2 Important (가능하면 수정)

| Warning | 의미 | 수정 방법 |
|---------|------|----------|
| `WIDTHEXPAND` | 자동 확장됨 | 명시적 확장: `{N{1'b0}, sig}` |
| `WIDTHTRUNC` | 자동 절삭됨 | 명시적 절삭: `sig[W-1:0]` |
| `UNSIGNED` | unsigned 비교 주의 | `int unsigned` 또는 `$signed()` 명시 |
| `SELRANGE` | 선택 범위 초과 가능 | 범위 체크 추가 또는 parameter 조정 |
| `IMPLICIT` | 암묵적 wire 선언 | `logic` 명시 선언 |
| `PINMISSING` | 인스턴스 포트 미연결 | 포트 연결 또는 `.port()` 빈 연결 명시 |
| `PINNOCONNECT` | 출력 포트 미연결 | 의도적이면 waiver, 아니면 연결 |
| `LITENDIAN` | Big/Little endian 혼용 | `[MSB:0]` little-endian 통일 |

### 2.3 Style (컨벤션)

| Warning | 의미 | 수정 방법 |
|---------|------|----------|
| `DECLFILENAME` | 파일명 ≠ 모듈명 | 파일명을 모듈명과 일치시킴 |
| `VARHIDDEN` | 변수가 상위 스코프 변수 가림 | 이름 변경 |
| `IMPORTSTAR` | `import pkg::*` | 명시적 import 또는 유지 (허용) |

## 3. 프로젝트 컨벤션 체크 (커스텀)

Verilator가 잡지 못하는 프로젝트 규칙은 `lint-checker` 에이전트가 grep으로 검사:

| 규칙 | 검사 패턴 | 위반 예 |
|------|----------|--------|
| CamelCase 금지 | `parameter\s+int\s+[A-Z][a-z]` | `parameter int DataWidth` |
| suffix 금지 | `\w+_(i|o)\b` in port list | `input logic data_i` |
| reg/wire 금지 | `\breg\b|\bwire\b` | `reg [7:0] data` |
| always @(*) 금지 | `always\s+@\s*\(\s*\*\s*\)` | `always @(*)` |
| clk_i/rst_ni 금지 | `clk_i|rst_ni` | `input logic clk_i` |

## 4. Waiver 파일 형식 (.verilator.vlt)

```
// Verilator waiver file
// Format: lint_off -rule WARNING -file "path" [-match "pattern"]

// 의도적으로 미사용된 신호
lint_off -rule UNUSED -file "rtl/src/my_module.sv" -match "Signal is not used: 'i_debug_*'"

// 의도적 비트폭 절삭 (알고리즘 요구)
lint_off -rule WIDTHTRUNC -file "rtl/src/dsp_core.sv" -match "*truncat*"

// 서드파티 IP (수정 불가)
lint_off -rule WIDTH -file "rtl/ip/*"

// 전역: 특정 경고 비활성화 (주의: 최소화할 것)
// lint_off -rule IMPORTSTAR
```

### Waiver 작성 규칙

1. **파일 단위 waiver 우선** — 전역 waiver 최소화
2. **`-match` 패턴 사용** — 가능한 한 좁은 범위
3. **주석으로 사유 기록** — 왜 waiver가 필요한지
4. **주기적 검토** — 불필요해진 waiver 제거

## 5. Verilator Lint 실행 명령

```bash
# 기본 lint-only (시뮬레이션 없이)
verilator --lint-only -Wall --top-module my_module rtl/src/my_module.sv

# 패키지 포함
verilator --lint-only -Wall --top-module my_module \
  -y rtl/include/ rtl/src/my_module_pkg.sv rtl/src/my_module.sv

# Waiver 적용
verilator --lint-only -Wall --top-module my_module \
  .verilator.vlt rtl/src/my_module.sv

# filelist 사용
verilator --lint-only -Wall --top-module top_module -f rtl/filelist.f

# 특정 경고만 활성화
verilator --lint-only -Wno-fatal -Wwarn-LATCH -Wwarn-WIDTH rtl/src/*.sv
```

## 6. Verilator + Verible 조합

```bash
# 1단계: Verilator (semantic lint)
verilator --lint-only -Wall -f rtl/filelist.f 2>&1 | tee lint_verilator.log

# 2단계: Verible (style lint)
verible-verilog-lint --rules_config .verible.rules rtl/src/*.sv 2>&1 | tee lint_verible.log

# 3단계: slang (IEEE 1800 semantic, optional)
slang --lint-only rtl/src/*.sv 2>&1 | tee lint_slang.log
```
