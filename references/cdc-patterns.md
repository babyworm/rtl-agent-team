# CDC (Clock Domain Crossing) Patterns and Constraints

> 이 문서는 `cdc-verify` 스킬의 상세 레퍼런스이다.
> 핵심 규칙은 `skills/cdc-verify/SKILL.md`의 `<Steps>` 참조.

## 1. Synchronizer Types

### 1.1 2-FF Synchronizer (Single Bit)

가장 기본적인 CDC 패턴. 단일 비트 신호 전용.

```systemverilog
module sync_2ff #(
  parameter int unsigned STAGES = 2
) (
  input  logic dst_clk,
  input  logic dst_rst_n,
  input  logic i_async,
  output logic o_sync
);
  logic [STAGES-1:0] sync_q;

  always_ff @(posedge dst_clk or negedge dst_rst_n) begin
    if (!dst_rst_n)
      sync_q <= '0;
    else
      sync_q <= {sync_q[STAGES-2:0], i_async};
  end

  assign o_sync = sync_q[STAGES-1];
endmodule
```

**적용**: 단일 비트 제어 신호 (enable, flag, interrupt)

### 1.2 Gray Code FIFO (Multi-bit Bus)

다중 비트 데이터는 gray code FIFO로 전달.

```systemverilog
// Gray code 변환
function automatic logic [W-1:0] bin2gray(input logic [W-1:0] bin);
  return bin ^ (bin >> 1);
endfunction

function automatic logic [W-1:0] gray2bin(input logic [W-1:0] gray);
  logic [W-1:0] bin;
  bin[W-1] = gray[W-1];
  for (int i = W-2; i >= 0; i--)
    bin[i] = bin[i+1] ^ gray[i];
  return bin;
endfunction
```

**구조**:
```
Writer (src_clk) → FIFO RAM → Reader (dst_clk)
  wr_ptr (binary) → bin2gray → 2-FF sync → gray2bin → wr_ptr_sync
  rd_ptr (binary) → bin2gray → 2-FF sync → gray2bin → rd_ptr_sync
```

**적용**: 다중 비트 데이터 스트림, 버퍼링 필요한 CDC

### 1.3 Pulse Synchronizer

소스 도메인의 1-cycle pulse를 목적지 도메인으로 전달.

```systemverilog
module sync_pulse (
  input  logic src_clk,
  input  logic src_rst_n,
  input  logic dst_clk,
  input  logic dst_rst_n,
  input  logic i_pulse,
  output logic o_pulse
);
  logic toggle_q;
  logic [1:0] sync_q;

  // Source: toggle on pulse
  always_ff @(posedge src_clk or negedge src_rst_n) begin
    if (!src_rst_n) toggle_q <= 1'b0;
    else if (i_pulse) toggle_q <= ~toggle_q;
  end

  // Destination: 2-FF sync + edge detect
  always_ff @(posedge dst_clk or negedge dst_rst_n) begin
    if (!dst_rst_n) sync_q <= 2'b0;
    else sync_q <= {sync_q[0], toggle_q};
  end

  assign o_pulse = sync_q[1] ^ sync_q[0];
endmodule
```

**적용**: 인터럽트, 이벤트 통지

### 1.4 Handshake Synchronizer

데이터 + valid를 안전하게 전달. 양방향 핸드셰이크.

```
src_clk domain:          dst_clk domain:
  req ─── 2-FF sync ───► req_sync
  ack ◄── 2-FF sync ──── ack
  data ─────────────────► data (stable while req high)
```

**적용**: 느린 제어 경로, 레지스터 설정값 전달

## 2. Common CDC Violations

| 위반 | 설명 | 심각도 | 수정 |
|------|------|--------|------|
| Multi-bit bus crossing | 여러 비트를 직접 sync | Critical | Gray code FIFO 사용 |
| Missing synchronizer | CDC 경로에 sync 없음 | Critical | 2-FF sync 추가 |
| Reconvergence | CDC 신호가 분기 후 재합류 | High | 단일 sync 후 분배 |
| Glitch on MUX select | CDC 신호로 MUX 제어 | High | Sync 후 MUX 선택 |
| Reset domain crossing | 비동기 리셋이 다른 도메인 | Medium | Reset sync 추가 |
| FIFO pointer sync | Binary pointer 직접 sync | Critical | Gray code 필수 |
| Pulse too narrow | src pulse < dst period | High | Pulse sync 사용 |

## 3. SDC Constraint Templates for CDC

### 3.1 비동기 클럭 그룹

```tcl
# 서로 관련 없는 클럭 도메인
set_clock_groups -asynchronous \
  -group [get_clocks sys_clk] \
  -group [get_clocks pixel_clk]
```

### 3.2 개별 False Path

```tcl
# 2-FF synchronizer 경로
set_false_path -from [get_clocks sys_clk] \
  -to [get_pins u_sync_*/sync_q_reg[0]/D]

# Gray code FIFO pointer 경로
set_false_path -from [get_clocks sys_clk] \
  -to [get_pins u_async_fifo/rd_ptr_gray_sync_reg[*][0]/D]
```

### 3.3 Max Delay (optional)

```tcl
# Synchronizer 경로에 max_delay 설정 (skew 제한)
set_max_delay -datapath_only \
  -from [get_clocks sys_clk] -to [get_pins u_sync_*/sync_q_reg[0]/D] \
  [expr {$dst_period * 0.8}]
```

## 4. CDC Verification Checklist

| 항목 | 검사 방법 | 도구 |
|------|----------|------|
| 모든 CDC 경로에 synchronizer | 구조 검사 | CDC tool / grep |
| Multi-bit bus에 gray code | 코드 리뷰 | Manual / CDC tool |
| Reconvergence 없음 | 경로 추적 | CDC tool |
| SDC false_path 설정 | SDC 리뷰 | 합성 도구 |
| Reset synchronizer 존재 | 코드 리뷰 | Manual |
| Pulse width ≥ dst period | 타이밍 분석 | Simulation |

## 5. CDC 검증 도구

| 도구 | 유형 | 사용법 |
|------|------|--------|
| Verilator | 구조 검사 (제한적) | `--lint-only -Wall` |
| Slang | 구조 검사 | `--lint-only` |
| CDC formal (상용) | 수학적 증명 | Cadence JasperGold CDC, Synopsys VC CDC |
| Simulation | 동적 검증 | 다중 클럭 testbench |

오픈소스 환경에서는 구조적 검사(grep + lint)와 시뮬레이션 기반 CDC 검증을 조합한다.
