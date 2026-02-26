# SDC (Synopsys Design Constraints) Best Practices

> 이 문서는 `synth-check` 스킬의 상세 레퍼런스이다.
> 핵심 규칙은 `skills/synth-check/SKILL.md`의 `<Steps>` 참조.
> SDC 템플릿: `skills/synth-check/templates/design-constraints.sdc`

## 1. SDC 기본 규칙

### 1.1 클럭 정의

```tcl
# 단일 클럭
create_clock -period 10.0 -name sys_clk [get_ports sys_clk]

# 다중 클럭 도메인
create_clock -period 10.0 -name sys_clk   [get_ports sys_clk]
create_clock -period  6.6 -name pixel_clk [get_ports pixel_clk]

# 생성 클럭 (PLL/MMCM 출력)
create_generated_clock -name pll_clk_2x \
  -source [get_ports sys_clk] \
  -multiply_by 2 \
  [get_pins u_pll/clk_out]
```

### 1.2 포트명 규칙 (프로젝트 컨벤션 준수)

```tcl
# 포트명은 RTL과 정확히 일치해야 함
# 프로젝트 규칙: {domain}_clk, {domain}_rst_n, i_/o_ prefix

# CORRECT
set_input_delay -clock sys_clk -max 3.0 [get_ports i_data*]
set_output_delay -clock sys_clk -max 2.0 [get_ports o_result*]

# WRONG (suffix convention)
# set_input_delay -clock clk_i -max 3.0 [get_ports data_i*]
```

## 2. Input/Output Delay

### 2.1 Input Delay

```tcl
# 외부 FF → 현재 설계 입력까지의 지연
# max: setup 분석용, min: hold 분석용
set_input_delay -clock sys_clk -max 3.0 [get_ports i_data*]
set_input_delay -clock sys_clk -min 0.5 [get_ports i_data*]
set_input_delay -clock sys_clk -max 3.0 [get_ports i_valid]
set_input_delay -clock sys_clk -min 0.5 [get_ports i_valid]

# DDR 입력 (양 에지)
set_input_delay -clock sys_clk -max 2.0 [get_ports i_ddr_data*]
set_input_delay -clock sys_clk -max 2.0 -clock_fall -add_delay [get_ports i_ddr_data*]
```

### 2.2 Output Delay

```tcl
# 현재 설계 출력 → 외부 FF 셋업까지 필요 시간
set_output_delay -clock sys_clk -max 2.0 [get_ports o_result*]
set_output_delay -clock sys_clk -min 0.3 [get_ports o_result*]
```

### 2.3 계산 공식

```
Input delay max  = Tclk_to_q(외부) + Tboard_delay
Input delay min  = Tclk_to_q_min(외부)
Output delay max = Tsetup(외부) + Tboard_delay
Output delay min = -Thold(외부)
```

## 3. Clock Uncertainty & Transition

```tcl
# Setup uncertainty (jitter + skew)
set_clock_uncertainty -setup 0.3 [get_clocks sys_clk]
# Hold uncertainty
set_clock_uncertainty -hold  0.1 [get_clocks sys_clk]

# Clock transition (slew rate)
set_clock_transition 0.15 [get_clocks sys_clk]
```

## 4. False Path & Multicycle

### 4.1 False Path

```tcl
# 비동기 리셋 → false path
set_false_path -from [get_ports sys_rst_n]

# CDC 경로 (2-FF synchronizer가 처리)
set_false_path -from [get_clocks sys_clk] -to [get_clocks pixel_clk]
set_false_path -from [get_clocks pixel_clk] -to [get_clocks sys_clk]

# 설정 레지스터 (rarely changes)
set_false_path -from [get_cells u_config/cfg_reg*]
```

### 4.2 Multicycle Path

```tcl
# 2 사이클 연산 (예: 곱셈기)
set_multicycle_path 2 -setup -from [get_cells u_mul/stage1_q*] -to [get_cells u_mul/result_q*]
set_multicycle_path 1 -hold  -from [get_cells u_mul/stage1_q*] -to [get_cells u_mul/result_q*]
```

### 4.3 주의사항

| 항목 | 설명 |
|------|------|
| False path 남용 금지 | 실제 동작 경로를 false path로 지정하면 타이밍 위반 미감지 |
| CDC는 false path | 단, synchronizer가 반드시 존재해야 함 |
| Multicycle hold | `-hold` 값은 보통 `-setup` 값 - 1 |

## 5. Clock Groups

```tcl
# 비동기 클럭 그룹 (서로 false path)
set_clock_groups -asynchronous \
  -group [get_clocks sys_clk] \
  -group [get_clocks pixel_clk]

# Exclusive 클럭 (MUX 선택, 동시 활성화 불가)
set_clock_groups -physically_exclusive \
  -group [get_clocks pll_clk_fast] \
  -group [get_clocks pll_clk_slow]
```

## 6. 도구별 차이

| 기능 | Synopsys DC | Cadence Genus | Yosys |
|------|------------|---------------|-------|
| SDC 지원 | 완전 | 완전 | 부분적 |
| `create_clock` | O | O | O |
| `set_input_delay` | O | O | O (제한적) |
| `set_false_path` | O | O | X (주석 처리) |
| `set_multicycle_path` | O | O | X |
| `set_clock_groups` | O | O | X |

Yosys는 `create_clock`, `set_input_delay`, `set_output_delay`만 부분 지원.
False path, multicycle은 주석으로 문서화하고, 실제 적용은 P&R 도구에서 수행.

## 7. SDC 검증 체크리스트

- [ ] 모든 클럭 포트에 `create_clock` 정의
- [ ] 생성 클럭(PLL/MMCM)에 `create_generated_clock`
- [ ] 모든 입력 포트에 `set_input_delay` (max + min)
- [ ] 모든 출력 포트에 `set_output_delay` (max + min)
- [ ] 비동기 리셋에 `set_false_path`
- [ ] CDC 경로에 `set_false_path` 또는 `set_clock_groups`
- [ ] Clock uncertainty 설정
- [ ] 포트명이 RTL과 일치 (i_/o_ prefix, sys_clk 등)
