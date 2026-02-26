# SystemVerilog Coding Style Guide — Detailed Reference

> 이 문서는 `systemverilog` 스킬의 상세 레퍼런스이다.
> 핵심 규칙은 `skills/systemverilog/SKILL.md`의 `<Steps>` 참조.

## 1. 명명 규칙 상세

### 1.1 식별자 규칙 종합표

| 대상 | 스타일 | Prefix/Suffix | 예시 | 금지 |
|------|--------|--------------|------|------|
| 모듈 | `snake_case` | — | `axi_lite_slave` | `AXI_Lite_Slave` |
| 인터페이스 | `snake_case` | `_if` suffix | `axi_if` | `AXI_IF` |
| 패키지 | `snake_case` | `_pkg` suffix | `cabac_pkg` | `CabacPkg` |
| Parameter (외부) | `ALL_CAPS` | — | `DATA_WIDTH` | `DataWidth` |
| Localparam (내부) | `ALL_CAPS` | `L_` prefix | `L_ADDR_BITS` | `AddrBits` |
| Typedef struct | `snake_case` | `_t` suffix | `bus_req_t` | `BusReq` |
| Typedef enum type | `snake_case` | `_e` suffix | `state_e` | `StateType` |
| Enum 값 | `ALL_CAPS` | — | `ST_IDLE` | `StIdle` |
| `define 매크로 | `ALL_CAPS` | — | `MAX_DEPTH` | `maxDepth` |
| 인스턴스 | `snake_case` | `u_` prefix | `u_fifo` | `fifo_inst` |
| Generate 블록 | `snake_case` | `gen_` prefix | `gen_pipeline` | `GEN_PIPE` |
| 내부 신호 | `snake_case` | — | `write_en` | `writeEn` |
| 입력 포트 | `snake_case` | `i_` prefix | `i_data` | `data_i` |
| 출력 포트 | `snake_case` | `o_` prefix | `o_valid` | `valid_o` |
| 양방향 포트 | `snake_case` | `io_` prefix | `io_sda` | `sda_io` |
| 클럭 | `snake_case` | — | `sys_clk`, `clk` | `clk_i` |
| 리셋 | `snake_case` | `_n` suffix | `sys_rst_n`, `rst_n` | `rst_ni` |

### 1.2 클럭/리셋 예외 규칙

클럭과 리셋 포트는 `i_` prefix를 사용하지 **않는다**:
```systemverilog
// CORRECT
input logic sys_clk,
input logic sys_rst_n,
input logic pixel_clk,
input logic pixel_rst_n,

// ALSO CORRECT (single domain)
input logic clk,
input logic rst_n,

// WRONG
input logic i_sys_clk,    // i_ prefix on clock
input logic i_sys_rst_n,  // i_ prefix on reset
input logic clk_i,        // suffix style
input logic rst_ni,       // suffix style
```

### 1.3 파이프라인 스테이지 신호

| 패턴 | 용도 | 예시 |
|------|------|------|
| `{name}_d` | combinational (next value) | `state_d`, `count_d` |
| `{name}_q` | registered (current value) | `state_q`, `count_q` |
| `stage{N}_{name}` | pipeline register | `stage1_data`, `stage2_valid` |

## 2. 타입 사용 규칙

### 2.1 필수 타입

```systemverilog
// 항상 logic 사용
logic [7:0] data;          // NOT: reg [7:0] data; wire [7:0] data;
logic       valid;

// signed 연산 시 명시적 signed
logic signed [15:0] coefficient;

// 비트폭이 있는 parameter는 int unsigned
parameter int unsigned DATA_WIDTH = 32;
parameter int unsigned DEPTH      = 16;
```

### 2.2 Struct/Enum 패턴

```systemverilog
// 패키지에 정의
package my_module_pkg;
  typedef struct packed {
    logic [31:0] addr;
    logic [31:0] data;
    logic        write;
  } bus_req_t;

  typedef enum logic [2:0] {
    ST_IDLE    = 3'b000,
    ST_SETUP   = 3'b001,
    ST_ACCESS  = 3'b010,
    ST_DONE    = 3'b011
  } state_e;
endpackage
```

### 2.3 금지 패턴

```systemverilog
// FORBIDDEN
reg  [7:0] data;           // reg keyword
wire [7:0] result;         // wire keyword
integer    count;          // use int unsigned
real       delay_val;      // no real in synth code
```

## 3. 모듈 구조 표준 순서

```systemverilog
module my_module
  import my_module_pkg::*;
#(
  // 1. Parameters (ALL_CAPS)
  parameter int unsigned DATA_WIDTH = 32,
  parameter int unsigned DEPTH      = 16
) (
  // 2. Clock/Reset (no i_ prefix)
  input  logic                    sys_clk,
  input  logic                    sys_rst_n,

  // 3. Input ports (i_ prefix, grouped by interface)
  input  logic [DATA_WIDTH-1:0]  i_data,
  input  logic                    i_valid,

  // 4. Output ports (o_ prefix)
  output logic [DATA_WIDTH-1:0]  o_result,
  output logic                    o_ready
);

  // 5. Localparams (L_ prefix)
  localparam int unsigned L_ADDR_BITS = $clog2(DEPTH);

  // 6. Type definitions (if not in _pkg)
  typedef enum logic [1:0] { ST_IDLE, ST_RUN, ST_DONE } state_e;

  // 7. Internal signals
  state_e state_q, state_d;
  logic [DATA_WIDTH-1:0] data_q;

  // 8. Submodule instances (u_ prefix)
  my_sub_module u_sub (
    .sys_clk   (sys_clk),
    .sys_rst_n (sys_rst_n),
    .i_data    (data_q),
    .o_result  (o_result)
  );

  // 9. Combinational logic (always_comb)
  always_comb begin
    state_d = state_q;
    // ...
  end

  // 10. Sequential logic (always_ff)
  always_ff @(posedge sys_clk or negedge sys_rst_n) begin
    if (!sys_rst_n) begin
      state_q <= ST_IDLE;
      data_q  <= '0;
    end else begin
      state_q <= state_d;
      data_q  <= i_data;
    end
  end

  // 11. Assertions (inline or reference bind file)
  // See sva_{module}.sv for formal assertions

endmodule
```

## 4. always 블록 규칙

| 블록 | 용도 | 할당 | sensitivity |
|------|------|------|-------------|
| `always_ff` | Sequential | `<=` (non-blocking) | `@(posedge clk or negedge rst_n)` |
| `always_comb` | Combinational | `=` (blocking) | 자동 |
| `always_latch` | **금지** | — | — |
| `always @(*)` | **금지** | — | `always_comb` 사용 |

## 5. case 문 규칙

```systemverilog
// REQUIRED: 모든 case에 default
always_comb begin
  unique case (state_q)
    ST_IDLE:  state_d = i_valid ? ST_RUN : ST_IDLE;
    ST_RUN:   state_d = done   ? ST_DONE : ST_RUN;
    ST_DONE:  state_d = ST_IDLE;
    default:  state_d = ST_IDLE;  // REQUIRED
  endcase
end
```

- `unique case`: 모든 값이 커버됨을 보장 (합성 최적화 힌트)
- `priority case`: 우선순위 인코딩이 필요한 경우
- plain `case`: 특별한 의미 없을 때 (default 필수는 동일)

## 6. 포트 선언 스타일

```systemverilog
// ANSI style (REQUIRED)
module my_module #(
  parameter int unsigned WIDTH = 8
) (
  input  logic              sys_clk,
  input  logic              sys_rst_n,
  input  logic [WIDTH-1:0]  i_data,
  output logic [WIDTH-1:0]  o_data
);

// NON-ANSI style (FORBIDDEN)
module my_module(sys_clk, sys_rst_n, i_data, o_data);
  input sys_clk;     // WRONG
  input [7:0] i_data; // WRONG
```
