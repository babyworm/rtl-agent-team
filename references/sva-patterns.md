# SVA Temporal Operator Reference and Pattern Library

> 이 문서는 `sva-check` 스킬의 상세 레퍼런스이다.
> 핵심 규칙은 `skills/sva-check/SKILL.md`의 `<Steps>` 참조.

## 1. Temporal Operators

### 1.1 Sequence Operators

| 연산자 | 의미 | 예시 |
|--------|------|------|
| `##N` | N 사이클 후 | `a ##1 b` — a 후 1사이클 뒤 b |
| `##[M:N]` | M~N 사이클 범위 | `a ##[1:3] b` — 1~3사이클 내 b |
| `##[0:$]` | 언젠가 (eventually) | `a ##[0:$] b` — a 이후 언젠가 b |
| `[*N]` | N 연속 반복 | `a[*3]` — a가 3사이클 연속 |
| `[*M:N]` | M~N 반복 | `a[*1:5]` — 1~5회 연속 |
| `[*0:$]` | 0회 이상 반복 | `a[*0:$]` — 0회 이상 연속 |
| `[=N]` | 비연속 N회 | `a[=3]` — (간격 허용) 총 3회 |
| `[->N]` | 비연속 goto N회 | `a[->3]` — 3번째 a까지 |

### 1.2 Property Operators

| 연산자 | 의미 | 예시 |
|--------|------|------|
| `\|->` | Overlapping implication | `a \|-> b` — a와 같은 사이클에 b 검사 |
| `\|=>` | Non-overlapping implication | `a \|=> b` — a 다음 사이클에 b 검사 |
| `not` | 부정 | `not (a ##1 b)` — 시퀀스 미발생 |
| `and` | 둘 다 성립 | `p1 and p2` |
| `or` | 하나 이상 성립 | `p1 or p2` |
| `if...else` | 조건부 | `if(cond) p1 else p2` |
| `until` | ~ 전까지 유지 | `a until b` — b 될 때까지 a 유지 |
| `s_until` | strong until | 반드시 b 발생 보장 |
| `eventually` | 언젠가 성립 | `s_eventually(a)` — 언젠가 a |

### 1.3 System Functions

| 함수 | 의미 | 주의사항 |
|------|------|---------|
| `$rose(sig)` | 0→1 전이 | |
| `$fell(sig)` | 1→0 전이 | |
| `$stable(sig)` | 값 변화 없음 | |
| `$changed(sig)` | 값 변화 있음 | |
| `$past(sig, N)` | N 사이클 전 값 | **past_valid guard 필수** |
| `$onehot(sig)` | exactly one bit high | |
| `$onehot0(sig)` | at most one bit high | |
| `$isunknown(sig)` | X 또는 Z 포함 | |
| `$countones(sig)` | 1인 비트 수 | |

## 2. Assertion Pattern Library

### 2.1 Valid/Ready Handshake

```systemverilog
// Valid holds until ready
a_valid_hold: assert property (
  i_valid && !o_ready |=> i_valid
) else $error("[%m] valid dropped before ready");

// Data stable while valid && !ready
a_data_stable: assert property (
  i_valid && !o_ready |=> $stable(i_data)
) else $error("[%m] data changed while waiting for ready");

// No X/Z on control signals
a_valid_no_x: assert property (
  !$isunknown(i_valid)
) else $error("[%m] valid is X/Z");

a_ready_no_x: assert property (
  !$isunknown(o_ready)
) else $error("[%m] ready is X/Z");
```

### 2.2 FIFO Safety

```systemverilog
// No push when full
a_no_overflow: assert property (
  i_push && !i_pop |-> !o_full
) else $error("[%m] FIFO overflow");

// No pop when empty
a_no_underflow: assert property (
  i_pop && !i_push |-> !o_empty
) else $error("[%m] FIFO underflow");

// Count consistency
a_count_range: assert property (
  o_count >= 0 && o_count <= DEPTH
) else $error("[%m] count out of range");

// Empty/Full vs count
a_empty_iff: assert property (
  o_empty == (o_count == 0)
) else $error("[%m] empty flag mismatch");

a_full_iff: assert property (
  o_full == (o_count == DEPTH)
) else $error("[%m] full flag mismatch");
```

### 2.3 FSM Safety

```systemverilog
// One-hot state encoding
a_state_onehot: assert property (
  $onehot(state_q)
) else $error("[%m] state not one-hot");

// No deadlock (always eventually leaves non-idle state)
a_no_deadlock: assert property (
  (state_q != ST_IDLE) |-> s_eventually(state_q == ST_IDLE)
) else $error("[%m] FSM deadlock");

// Known state (no X)
a_state_known: assert property (
  !$isunknown(state_q)
) else $error("[%m] state is X/Z");
```

### 2.4 Pipeline Valid Propagation

```systemverilog
// Stage valid propagation (with stall)
a_pipe_valid: assert property (
  stage1_valid && !i_stall |=> stage2_valid
) else $error("[%m] pipeline valid not propagated");

// Data follows valid through pipeline
a_pipe_data: assert property (
  stage1_valid && !i_stall |=> (stage2_data == $past(stage1_data))
) else $error("[%m] pipeline data corruption");
```

### 2.5 AXI Protocol (기본)

```systemverilog
// AW channel: AWVALID holds until AWREADY
a_aw_valid_hold: assert property (
  i_awvalid && !o_awready |=> i_awvalid
) else $error("[%m] AWVALID dropped");

// W channel: WVALID holds until WREADY
a_w_valid_hold: assert property (
  i_wvalid && !o_wready |=> i_wvalid
) else $error("[%m] WVALID dropped");

// B channel: BVALID holds until BREADY
a_b_valid_hold: assert property (
  o_bvalid && !i_bready |=> o_bvalid
) else $error("[%m] BVALID dropped");

// Write response only after write
a_b_after_w: assert property (
  $rose(o_bvalid) |-> ##[0:$] $past(i_wvalid && o_wready && i_wlast)
) else $error("[%m] BRESP without prior write");
```

### 2.6 Reset Behavior

```systemverilog
// After reset, outputs are known values
a_reset_output: assert property (
  !sys_rst_n |=> (o_valid == 1'b0) && (o_data == '0)
) else $error("[%m] output not reset");

// No activity during reset
a_reset_inactive: assert property (
  !sys_rst_n |-> !o_valid
) else $error("[%m] output active during reset");
```

### 2.7 Liveness (Bounded Response)

```systemverilog
// Request gets response within MAX_LATENCY cycles
a_bounded_resp: assert property (
  i_req |-> ##[1:MAX_LATENCY] o_ack
) else $error("[%m] no response within %0d cycles", MAX_LATENCY);
```

## 3. Formal Verification 모드별 적합한 패턴

| 패턴 | BMC | Prove | Cover |
|------|-----|-------|-------|
| Handshake valid/ready | O | O | — |
| FIFO overflow/underflow | O | O | — |
| FSM one-hot | O | O | — |
| No deadlock (s_eventually) | X | O | — |
| Bounded response | O (depth ≥ MAX_LATENCY) | O | — |
| Reachability | — | — | O |
| Back-to-back transfer | — | — | O |
| Max burst length | — | — | O |

## 4. assume vs assert 가이드

| 상황 | 사용 | 예시 |
|------|------|------|
| DUT 내부 property | `assert` | `a_fifo_no_overflow` |
| 입력 제약 (formal) | `assume` | `m_valid_no_x` |
| 입력 프로토콜 (formal) | `assume` | `m_valid_stable` |
| 커버리지 목표 | `cover` | `c_back_to_back` |
| formal 전용 제약 | `restrict` | `restrict property (i_mode == 2'b01)` |

**Over-constraint 방지**: 모든 `assume`에 대응하는 `cover`를 작성하여 assume이 valid trace를 남기는지 확인.
