---
name: systemverilog
description: "SystemVerilog coding convention and design guideline skill. Enforces lowRISC style + project overrides for all .sv/.v file generation. Covers naming, module structure, power optimization, FPGA considerations, and pipelining for timing closure."
---

<Purpose>
SystemVerilog 코딩 표준 및 설계 가이드라인.
모든 .sv, .v 파일을 생성하거나 수정하는 에이전트는 이 스킬의 규칙을 따라야 한다.
기본: lowRISC SystemVerilog Coding Style Guide (https://github.com/lowRISC/style-guides/blob/master/VerilogCodingStyle.md)
프로젝트 오버라이드가 lowRISC 기본 규칙보다 우선한다.
</Purpose>

<Use_When>
- .sv, .svh, .v, .vh 파일을 작성하거나 수정할 때
- Phase 4 (RTL 구현) 작업 시
- Phase 5 (Verification) 에서 SVA, SV 테스트벤치 작성 시
- lint-check, synth-check 스킬 실행 전 코드 준비 시
- 에이전트: rtl-coder, sva-extractor, testbench-dev, lint-checker
</Use_When>

<Do_Not_Use_When>
- SystemC/C++ 코드 작성 시 → `systemc` 스킬 사용
- Python cocotb 테스트 작성 시 → `func-verify` 스킬의 cocotb 규칙 참조
- 문서 작성만 할 때
</Do_Not_Use_When>

<Why_This_Exists>
일관된 코딩 표준은 린트 통과율, 합성 품질, 팀 가독성을 동시에 보장한다.
lowRISC 기반이지만 포트 네이밍, 클럭/리셋 규칙 등 프로젝트 고유 오버라이드가 있으므로
별도 스킬로 관리하여 모든 SV 생성 에이전트가 동일한 규칙을 참조한다.
</Why_This_Exists>

<Execution_Policy>
- 이 스킬의 규칙은 SV 코드를 생성하는 모든 에이전트에 적용된다
- 위반 시 lint-check 스킬이 FAIL 판정을 내린다
- `templates/module-template.sv`를 새 모듈의 시작점으로 사용할 것
- `examples/good-vs-bad.sv`로 올바른/잘못된 패턴을 확인할 것
</Execution_Policy>

<Steps>

## 1. 프로젝트 오버라이드 (lowRISC보다 우선)

> **IMPORTANT — 아래 3가지는 lowRISC 가이드와 다르며, 반드시 이 규칙을 적용한다.**

### 1.1 포트 방향 prefix (필수)
- 입력: `i_`, 출력: `o_`, 양방향: `io_` — **항상 사용**
- 예: `i_data`, `o_valid`, `io_sda` (NOT `data_i`, `valid_o`)
- suffix(`_i`, `_o`, `_io`) 사용은 **금지**
- lowRISC는 suffix를 사용하지만, 이 프로젝트는 **prefix 필수**

### 1.2 클럭 명명
- 단일 클럭: `clk` (기본) 또는 `{domain}_clk` (다중 클럭)
- 다중 클럭 도메인: `sys_clk`, `pixel_clk`, `axi_clk`
- NOT `clk_i`, NOT suffix

### 1.3 리셋 명명
- 단일 리셋: `rst_n` (기본) 또는 `{domain}_rst_n` (다중 도메인)
- active-low 비동기 리셋 필수
- 예: `rst_n`, `sys_rst_n`, `pixel_rst_n` (NOT `rst_ni`)

### 1.4 CamelCase 금지 (추가 오버라이드)
- lowRISC는 Parameter에 `UpperCamelCase`, Enum 값에 `UpperCamelCase` 사용
- **이 프로젝트는 CamelCase 전면 금지**
- Parameter: `ALL_CAPS` (`DATA_WIDTH`, NOT `DataWidth`)
- Localparam (내부): `L_` prefix + `ALL_CAPS` (`L_ADDR_BITS`, NOT `AddrBits`)
- Enum 값: `ALL_CAPS` (`ST_IDLE`, NOT `StIdle`)

## 2. 명명 규칙

> **IMPORTANT — CamelCase 전면 금지. 모든 식별자는 `snake_case` 또는 `ALL_CAPS` 만 사용한다.**
> 상세 규칙: `references/coding-style-guide.md` 참조.

| 대상 | 규칙 | 예시 |
|------|------|------|
| 모듈 | `snake_case` | `axi_lite_slave` |
| 파라미터 (외부 설정 가능) | `ALL_CAPS` | `DATA_WIDTH`, `DEPTH` |
| 로컬 파라미터 (내부 전용) | `L_` prefix + `ALL_CAPS` | `L_ADDR_BITS`, `L_CNT_MAX` |
| 타입 (typedef) | `snake_case_t` suffix | `state_t`, `bus_req_t` |
| 열거형 타입 (typedef enum) | `snake_case_e` suffix | `state_e`, `cmd_type_e` |
| 열거형 값 | `ALL_CAPS` | `ST_IDLE`, `WAIT_RESP` |
| `define 매크로 | `ALL_CAPS` | `MAX_DEPTH`, `ASSERT_ON` |
| 인스턴스 | `u_` prefix | `u_fifo`, `u_arbiter` |
| generate 블록 | `gen_` prefix | `gen_pipeline_stage` |
| 신호(내부) | `snake_case` | `write_enable`, `addr_valid` |

### CamelCase 금지 예시

| 금지 (CamelCase) | 올바른 표현 |
|-----------------|-----------|
| `parameter int Width = 8` | `parameter int unsigned WIDTH = 8` |
| `localparam AddrBits = $clog2(Depth)` | `localparam L_ADDR_BITS = $clog2(DEPTH)` |
| `StIdle`, `StProcess` | `ST_IDLE`, `ST_PROCESS` |
| `UpperCamelCase` 어떤 것이든 | `ALL_CAPS` 또는 `snake_case` |

## 3. 파일명 규칙

| 유형 | 패턴 | 예시 |
|------|------|------|
| 모듈 | `module_name.sv` | `axi_lite_slave.sv` |
| 패키지 | `module_name_pkg.sv` | `cabac_pkg.sv` |
| 인터페이스 | `module_name_if.sv` | `axi_if.sv` |
| 테스트벤치 | `tb_module_name.sv` | `tb_axi_lite_slave.sv` |
| SVA bind | `sva_module_name.sv` | `sva_axi_lite_slave.sv` |

**One module per file, filename matches module name.**

## 4. SystemVerilog 코딩 규칙

### 4.1 필수 사용
- `logic` 사용 (`reg`/`wire` 사용 금지)
- `always_ff` for sequential (non-blocking `<=`)
- `always_comb` for combinational (blocking `=`)
- `typedef enum` / `typedef struct packed` 적극 사용
- 패키지(`_pkg.sv`)로 공유 타입 정의
- 포트: `input logic` / `output logic` (ANSI style)
- 매직 넘버 금지 — `parameter` 또는 `localparam` 사용

### 4.2 금지 사항
- `reg`, `wire` 키워드 사용 금지
- `always_latch` 사용 금지 (명시적 래치 제외, 일반적으로 금지)
- synthesizable 코드에서 `initial` 블록 금지
- 래치 유발: 모든 `case`에 `default` 필수
- combinational loop 금지
- `#delay` in synthesizable code 금지

### 4.3 모듈 구조
```
module_name_pkg.sv    ← 공유 타입/상수 정의
module_name.sv        ← 모듈 구현
  - parameter 선언
  - 포트 선언 (ANSI style)
  - 내부 신호 선언
  - 서브모듈 인스턴스 (u_ prefix)
  - combinational logic (always_comb)
  - sequential logic (always_ff)
  - assertions (SVA)
```
See `templates/module-template.sv` for complete scaffold.

## 5. Power Optimization

### 5.1 클럭 게이팅
- 활동이 없는 블록의 클럭을 게이팅하여 dynamic power 절감
- ICG(Integrated Clock Gating) 셀 사용 권장
```systemverilog
// Clock gating pattern
logic clk_enable;
logic gated_clk;

// Use dedicated ICG cell (synthesis tool maps to library cell)
assign gated_clk = sys_clk & clk_enable;  // For simulation only
// Synthesis: replace with ICG instantiation or let tool infer
```

### 5.2 Power-Aware 코딩 패턴
- 불필요한 toggling 최소화: mux 출력 전에 enable 체크
- Memory read enable: 필요할 때만 SRAM 읽기
- Operand isolation: 연산기 입력을 0으로 마스킹
```systemverilog
// Operand isolation — prevent unnecessary switching in multiplier
logic [15:0] mul_a_gated, mul_b_gated;
assign mul_a_gated = i_mul_valid ? i_mul_a : '0;
assign mul_b_gated = i_mul_valid ? i_mul_b : '0;
assign mul_result  = mul_a_gated * mul_b_gated;
```

### 5.3 Power Domain 고려사항
- 멀티 전압 도메인 시 level shifter 위치 명시
- Retention register 필요 시 주석으로 표시

## 6. FPGA 고려사항

### 6.1 리소스 추론 가이드
| 리소스 | 추론 패턴 | 주의사항 |
|--------|----------|---------|
| BRAM | `logic [W-1:0] mem [0:D-1]` + sync read | 비동기 읽기는 distributed RAM |
| DSP | `a * b + c` 패턴 | pipeline register 추가 시 더 잘 추론 |
| SRL | shift register (`always_ff` chain) | 자동 추론, 명시적 제어 불필요 |

### 6.2 XDC 제약조건 (Xilinx)
- SDC와 유사하나 Xilinx 고유 명령 포함
- `create_clock`, `set_input_delay`, `set_output_delay` 동일
- FPGA 고유: `set_property IOSTANDARD`, `set_property LOC`

### 6.3 ILA 디버깅
- 디버그 대상 신호에 `(* mark_debug = "true" *)` 어트리뷰트
- 합성 후 ILA core 삽입하여 실시간 파형 확인

### 6.4 IP Core 활용
- Xilinx: AXI Interconnect, MIG (DDR controller), AXI DMA
- Intel: Platform Designer (Qsys) IP
- IP 인스턴스도 `u_` prefix 규칙 적용

## 7. Pipelining for Timing Closure

### 7.1 파이프라인 삽입 기준
- 타이밍 리포트에서 critical path 위반 시
- Combinational depth > target frequency의 허용 범위 초과 시
- `synth-check` 스킬에서 logic depth 경고 발생 시

### 7.2 파이프라인 패턴
```systemverilog
// Before: long combinational path
assign o_result = func_a(func_b(func_c(i_data)));

// After: 2-stage pipeline
logic [W-1:0] stage1_q;
always_ff @(posedge sys_clk or negedge sys_rst_n) begin
  if (!sys_rst_n) stage1_q <= '0;
  else            stage1_q <= func_c(i_data);
end
assign o_result = func_a(func_b(stage1_q));
```

### 7.3 Register Retiming
- 합성 도구의 retiming 옵션 활용 (DC: `compile_ultra -retime`, Genus: `syn_opt -retiming`)
- Retiming 대상 레지스터에 `dont_touch` 금지

### 7.4 Valid/Ready 파이프라인
- 파이프라인 삽입 시 handshake 신호도 함께 파이프라인
- Backpressure 전파: `o_ready`는 다음 스테이지의 `i_ready`에서 역방향으로 전파

</Steps>

<Tool_Usage>
이 스킬은 직접 실행하지 않는다. SV 코드를 생성하는 에이전트가 참조한다:
```
Task(subagent_type="rtl-agent-team:rtl-coder",
     prompt="... Follow systemverilog skill conventions. Use templates/module-template.sv as scaffold.")

Task(subagent_type="rtl-agent-team:sva-extractor",
     prompt="... Follow systemverilog skill naming conventions for SVA bind files.")
```
</Tool_Usage>

<Examples>
<Good>
프로젝트 규칙 준수: ALL_CAPS parameter, L_ prefix localparam, snake_case, no CamelCase.
```systemverilog
module cabac_encoder #(
  parameter int unsigned CTX_ADDR_W = 9
) (
  input  logic                   clk,
  input  logic                   rst_n,
  input  logic [CTX_ADDR_W-1:0]  ctx_addr,
  output logic                   bin_valid
);
  localparam int unsigned L_CTX_DEPTH = 2 ** CTX_ADDR_W;

  typedef enum logic [1:0] {
    ST_IDLE,
    ST_ENCODE,
    ST_DONE
  } state_e;
```
</Good>
<Bad>
CamelCase, suffix, reg/wire, 매직 넘버:
```systemverilog
module cabac_encoder #(
  parameter int CtxAddrWidth = 9   // WRONG: CamelCase
) (
  input  wire        clk_i,        // WRONG: suffix, wire
  input  reg         rst_ni,       // WRONG: reg, suffix
  input  [8:0]       ctx_addr_i,   // WRONG: suffix, magic width
  output             bin_valid_o   // WRONG: no type, suffix
);
  localparam AddrBits = 4;         // WRONG: CamelCase, no L_ prefix
  typedef enum logic [1:0] {
    StIdle, StEncode, StDone       // WRONG: CamelCase enum values
  } state_e;
```
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- lint-check 실행 시 컨벤션 위반 발견 → rtl-coder에게 수정 요청
- 파워 최적화 패턴이 기능에 영향 → rtl-architect에게 검토 요청
- FPGA vs ASIC 타겟에 따라 다른 패턴 필요 → 사용자에게 타겟 확인
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] 포트 naming: `i_`/`o_`/`io_` prefix 필수
- [ ] 클럭: `clk` (단일) 또는 `{domain}_clk` (다중), 리셋: `rst_n` 또는 `{domain}_rst_n`
- [ ] CamelCase 없음: Parameter `ALL_CAPS`, localparam `L_` prefix, enum 값 `ALL_CAPS`
- [ ] `logic` 만 사용 (no `reg`/`wire`)
- [ ] `always_ff` (sequential), `always_comb` (combinational)
- [ ] 모든 `case`에 `default` 존재
- [ ] 인스턴스 `u_` prefix, generate `gen_` prefix
- [ ] 매직 넘버 없음 (parameter/localparam 사용)
- [ ] 파일명 = 모듈명
- [ ] One module per file
</Final_Checklist>
