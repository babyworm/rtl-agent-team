# Yosys Command Reference and Latch Detection Guide

> 이 문서는 `synth-check` 스킬의 상세 레퍼런스이다.
> 핵심 규칙은 `skills/synth-check/SKILL.md`의 `<Steps>` 참조.

## 1. Yosys 기본 합성 플로우

```tcl
# === 1. Read Design ===
read_verilog -sv rtl/src/my_module_pkg.sv
read_verilog -sv rtl/src/my_module.sv

# === 2. Elaborate ===
hierarchy -top my_module -check

# === 3. Pre-Synthesis Checks ===
check -assert                    # Basic consistency check
proc                             # Process always blocks → muxes/FFs
flatten                          # Flatten hierarchy (optional)

# === 4. Synthesize ===
synth -top my_module             # Generic synthesis
# OR target-specific:
# synth_xilinx -top my_module   # Xilinx FPGA
# synth_ice40 -top my_module    # iCE40 FPGA

# === 5. Post-Synthesis Analysis ===
stat                             # Area/resource report
check -assert                    # Final consistency check

# === 6. Write Output ===
write_verilog -noattr synth/netlist.v
write_json synth/netlist.json
```

## 2. Latch Detection

### 2.1 Latch 확인 명령

```tcl
# proc 후 latch 확인
proc
# Yosys가 $_DLATCH_ 셀을 생성하면 latch 존재

# 방법 1: stat에서 latch 카운트
stat
# Output: "$_DLATCH_P_  2" ← latch가 2개

# 방법 2: select로 latch 셀 검색
select -module my_module t:$_DLATCH_*
stat                    # 선택된 latch 셀의 개수

# 방법 3: JSON 출력에서 검색
write_json -noattr /dev/stdout | grep -i dlatch
```

### 2.2 Latch 원인과 수정

| 원인 | 예시 | 수정 |
|------|------|------|
| `case` 불완전 | `case` without `default` | `default` branch 추가 |
| `if/else` 불완전 | `if` without `else` | `else` branch 추가 |
| `always_comb` 에서 일부 신호 미할당 | 특정 조건에서만 할당 | 모든 경로에서 할당 |
| 비동기 리셋 없는 feedback | `always @(*)` with state | `always_ff` + reset 사용 |

```systemverilog
// LATCH (WRONG):
always_comb begin
  if (sel) out = in_a;
  // else 없음 → latch!
end

// NO LATCH (CORRECT):
always_comb begin
  out = '0;            // default 값
  if (sel) out = in_a;
end
```

## 3. 주요 Yosys 명령 레퍼런스

### 3.1 Read & Elaborate

| 명령 | 용도 | 예시 |
|------|------|------|
| `read_verilog -sv` | SystemVerilog 읽기 | `read_verilog -sv file.sv` |
| `read_verilog -D MACRO=1` | define 설정 | `read_verilog -D SYNTH=1 file.sv` |
| `hierarchy -top` | top 모듈 지정 | `hierarchy -top my_top -check` |
| `hierarchy -check` | 미해결 참조 체크 | unresolved module 에러 검출 |

### 3.2 Synthesis Passes

| 명령 | 용도 | 비고 |
|------|------|------|
| `proc` | always → logic cells | FF, mux, latch 추론 |
| `opt` | 일반 최적화 | dead code 제거, const folding |
| `opt_clean` | 미사용 셀/와이어 제거 | |
| `flatten` | 계층 제거 | 면적 리포트 정확도 향상 |
| `memory` | 메모리 추론 | BRAM/distributed 판단 |
| `techmap` | 기술 매핑 | generic → target cells |
| `abc` | 로직 최적화 (ABC) | 면적/속도 최적화 |
| `dfflibmap` | FF 라이브러리 매핑 | target FF cell 매핑 |

### 3.3 Analysis & Reporting

| 명령 | 용도 | 출력 예 |
|------|------|--------|
| `stat` | 리소스 카운트 | cells, wires, FF count |
| `stat -tech` | 기술별 리소스 | LUT, FF, BRAM (FPGA) |
| `check` | 일관성 검사 | combinational loops, etc. |
| `tee -o file.log stat` | 파일로 출력 | 로그 파일 생성 |
| `show` | 회로 다이어그램 (dot) | GraphViz 시각화 |
| `write_json` | JSON netlist | 후처리용 |

### 3.4 Selection

```tcl
# 특정 모듈의 셀만 선택
select -module my_module

# FF 셀만 선택
select t:$dff t:$adff t:$sdff

# Latch 셀만 선택
select t:$dlatch t:$_DLATCH_*

# 선택 후 stat
select t:$dff; stat; select -clear
```

## 4. FPGA 타겟별 합성

### 4.1 Xilinx

```tcl
read_verilog -sv rtl/src/*.sv
synth_xilinx -top my_module -family xc7
stat
write_verilog -noattr synth/xilinx_netlist.v
```

### 4.2 iCE40

```tcl
read_verilog -sv rtl/src/*.sv
synth_ice40 -top my_module
stat
write_blif synth/ice40_netlist.blif
```

### 4.3 ECP5

```tcl
read_verilog -sv rtl/src/*.sv
synth_ecp5 -top my_module
stat
write_json synth/ecp5_netlist.json
```

## 5. 일반적인 Yosys 에러와 해결

| 에러 | 원인 | 해결 |
|------|------|------|
| `ERROR: Module not found` | top 모듈 이름 불일치 | `-top` 인자 확인 |
| `ERROR: Identifier not found` | import 누락 | `import pkg::*` 추가 |
| `Warning: Latch inferred` | combinational 불완전 | default 할당 추가 |
| `ERROR: syntax error` | SV 미지원 문법 | `-sv` 플래그 확인, Yosys SV 지원 범위 확인 |
| `Warning: Replacing memory` | 메모리 추론 실패 | 동기 read 패턴 확인 |

## 6. 합성 스크립트 템플릿

`skills/synth-check/templates/yosys-synth-script.ys` 참조.
