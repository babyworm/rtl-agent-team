# AXI Protocol Rules and SVA Assertion Templates

> 이 문서는 `protocol-verify` 스킬의 상세 레퍼런스이다.
> 핵심 규칙은 `skills/protocol-verify/SKILL.md`의 `<Steps>` 참조.

## 1. AXI4 채널 개요

| 채널 | 방향 (Master→Slave) | 용도 |
|------|---------------------|------|
| AW (Write Address) | M → S | 쓰기 주소 + 버스트 정보 |
| W (Write Data) | M → S | 쓰기 데이터 + 스트로브 |
| B (Write Response) | S → M | 쓰기 응답 |
| AR (Read Address) | M → S | 읽기 주소 + 버스트 정보 |
| R (Read Data) | S → M | 읽기 데이터 + 응답 |

모든 채널은 **VALID/READY 핸드셰이크** 사용.

## 2. AXI4 Protocol Rules (AMBA Spec 기준)

### 2.1 Handshake Rules (모든 채널 공통)

| Rule ID | 규칙 | SVA 패턴 |
|---------|------|---------|
| A3.2.1 | VALID는 READY 없이도 assert 가능 | — (제약 아님) |
| A3.2.2 | VALID assert 후 READY 올 때까지 유지 | `valid && !ready \|=> valid` |
| A3.2.1 | READY는 VALID 없이도 assert 가능 | — (제약 아님) |
| — | VALID 중 payload stable | `valid && !ready \|=> $stable(payload)` |

### 2.2 Write Address Channel (AW)

| 신호 (프로젝트 규칙) | 방향 | 설명 |
|---------------------|------|------|
| `i_awaddr` | M→S | 쓰기 시작 주소 |
| `i_awlen` | M→S | 버스트 길이 (beats - 1) |
| `i_awsize` | M→S | 비트/바이트 크기 (log2) |
| `i_awburst` | M→S | 버스트 타입 (FIXED/INCR/WRAP) |
| `i_awvalid` | M→S | 주소 유효 |
| `o_awready` | S→M | 주소 수락 |

### 2.3 Write Data Channel (W)

| 신호 | 방향 | 설명 |
|------|------|------|
| `i_wdata` | M→S | 쓰기 데이터 |
| `i_wstrb` | M→S | 바이트 스트로브 |
| `i_wlast` | M→S | 마지막 beat |
| `i_wvalid` | M→S | 데이터 유효 |
| `o_wready` | S→M | 데이터 수락 |

### 2.4 Write Response Channel (B)

| 신호 | 방향 | 설명 |
|------|------|------|
| `o_bresp` | S→M | 응답 (OKAY/SLVERR/DECERR) |
| `o_bvalid` | S→M | 응답 유효 |
| `i_bready` | M→S | 응답 수락 |

### 2.5 Read Address Channel (AR)

| 신호 | 방향 | 설명 |
|------|------|------|
| `i_araddr` | M→S | 읽기 시작 주소 |
| `i_arlen` | M→S | 버스트 길이 |
| `i_arsize` | M→S | 비트/바이트 크기 |
| `i_arburst` | M→S | 버스트 타입 |
| `i_arvalid` | M→S | 주소 유효 |
| `o_arready` | S→M | 주소 수락 |

### 2.6 Read Data Channel (R)

| 신호 | 방향 | 설명 |
|------|------|------|
| `o_rdata` | S→M | 읽기 데이터 |
| `o_rresp` | S→M | 응답 |
| `o_rlast` | S→M | 마지막 beat |
| `o_rvalid` | S→M | 데이터 유효 |
| `i_rready` | M→S | 데이터 수락 |

## 3. SVA Assertion Templates per Channel

### 3.1 AW Channel

```systemverilog
// AWVALID holds until AWREADY
a_aw_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_awvalid && !o_awready |=> i_awvalid
) else $error("[%m] AWVALID dropped before AWREADY");

// AWADDR stable while waiting
a_aw_addr_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_awvalid && !o_awready |=> $stable(i_awaddr)
) else $error("[%m] AWADDR changed while AWVALID && !AWREADY");

// AWLEN stable
a_aw_len_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_awvalid && !o_awready |=> $stable(i_awlen)
) else $error("[%m] AWLEN changed");

// AWBURST valid (00=FIXED, 01=INCR, 10=WRAP, 11=reserved)
a_aw_burst_valid: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_awvalid |-> (i_awburst != 2'b11)
) else $error("[%m] AWBURST reserved value");
```

### 3.2 W Channel

```systemverilog
// WVALID holds
a_w_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_wvalid && !o_wready |=> i_wvalid
) else $error("[%m] WVALID dropped");

// WDATA stable
a_w_data_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_wvalid && !o_wready |=> $stable(i_wdata)
) else $error("[%m] WDATA changed");

// WSTRB stable
a_w_strb_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_wvalid && !o_wready |=> $stable(i_wstrb)
) else $error("[%m] WSTRB changed");

// WLAST stable
a_w_last_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_wvalid && !o_wready |=> $stable(i_wlast)
) else $error("[%m] WLAST changed");
```

### 3.3 B Channel

```systemverilog
// BVALID holds
a_b_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  o_bvalid && !i_bready |=> o_bvalid
) else $error("[%m] BVALID dropped");

// BRESP stable
a_b_resp_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  o_bvalid && !i_bready |=> $stable(o_bresp)
) else $error("[%m] BRESP changed");

// BRESP valid (00=OKAY, 01=EXOKAY, 10=SLVERR, 11=DECERR)
a_b_resp_valid: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  o_bvalid |-> (o_bresp inside {2'b00, 2'b01, 2'b10, 2'b11})
) else $error("[%m] BRESP invalid");
```

### 3.4 AR Channel

```systemverilog
a_ar_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_arvalid && !o_arready |=> i_arvalid
) else $error("[%m] ARVALID dropped");

a_ar_addr_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  i_arvalid && !o_arready |=> $stable(i_araddr)
) else $error("[%m] ARADDR changed");
```

### 3.5 R Channel

```systemverilog
a_r_valid_hold: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  o_rvalid && !i_rready |=> o_rvalid
) else $error("[%m] RVALID dropped");

a_r_data_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  o_rvalid && !i_rready |=> $stable(o_rdata)
) else $error("[%m] RDATA changed");

a_r_last_stable: assert property (
  @(posedge sys_clk) disable iff (!sys_rst_n)
  o_rvalid && !i_rready |=> $stable(o_rlast)
) else $error("[%m] RLAST changed");
```

## 4. AXI4-Lite 차이점

AXI4-Lite는 AXI4의 간소화 버전:

| 항목 | AXI4 | AXI4-Lite |
|------|------|-----------|
| 버스트 | AWLEN/ARLEN 지원 | 단일 전송만 (len=0) |
| 데이터 폭 | 설정 가능 | 32 또는 64 bit |
| WSTRB | 전체 지원 | 전체 지원 |
| WLAST | 필요 | 불필요 (항상 1) |
| ID | 지원 | 미지원 |
| SIZE | 지원 | 데이터 폭 고정 |

## 5. Burst Type Rules

| Type | AxBURST | 동작 | 제약 |
|------|---------|------|------|
| FIXED | 2'b00 | 같은 주소 반복 | len ≤ 15 |
| INCR | 2'b01 | 주소 증가 | len ≤ 255 |
| WRAP | 2'b10 | 주소 감싸기 | len ∈ {1,3,7,15}, aligned |

## 6. Response Codes

| Code | RESP | 의미 |
|------|------|------|
| OKAY | 2'b00 | 정상 완료 |
| EXOKAY | 2'b01 | 독점 접근 성공 |
| SLVERR | 2'b10 | Slave 에러 |
| DECERR | 2'b11 | Decode 에러 (주소 범위 초과) |

## 7. APB Protocol Rules

APB(Advanced Peripheral Bus)는 간단한 레지스터 접근용:

| 신호 | 방향 | 설명 |
|------|------|------|
| `i_psel` | M→S | Slave 선택 |
| `i_penable` | M→S | Transfer enable |
| `i_pwrite` | M→S | 쓰기(1)/읽기(0) |
| `i_paddr` | M→S | 주소 |
| `i_pwdata` | M→S | 쓰기 데이터 |
| `o_prdata` | S→M | 읽기 데이터 |
| `o_pready` | S→M | Transfer 완료 |
| `o_pslverr` | S→M | 에러 응답 |

APB 프로토콜 2-phase: SETUP (psel=1, penable=0) → ACCESS (psel=1, penable=1, wait pready).
