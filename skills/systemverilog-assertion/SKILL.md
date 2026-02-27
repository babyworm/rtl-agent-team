---
name: systemverilog-assertion
description: "SVA (SystemVerilog Assertion) coding convention and formal verification guideline skill. Covers assertion styles, property/sequence patterns, bind files, coverage properties, and SymbiYosys integration. Applied when writing .sva files or SVA blocks in .sv files."
---

<Purpose>
SystemVerilog Assertion (SVA) 코딩 표준 및 formal verification 가이드라인.
SVA를 작성하거나 수정하는 에이전트는 이 스킬의 규칙을 따라야 한다.
IEEE 1800-2017 Assertion 문법을 기본으로 한다.
</Purpose>

<Use_When>
- .sva 파일 또는 SVA bind 파일 작성 시
- sva-check 스킬 실행을 위한 assertion 준비 시
- Phase 5 (Verification) — formal verification 작업 시
- Protocol assertion 작성 시 (AXI, APB, AHB 등)
- 에이전트: sva-extractor, testbench-dev, protocol-checker
</Use_When>

<Do_Not_Use_When>
- RTL 합성 코드 작성 시 → `systemverilog` 스킬 사용
- cocotb Python 기반 검증 시 → `func-verify` 스킬 참조
- UVM 기반 검증 환경 구축 시 → `uvm` 스킬 사용
</Do_Not_Use_When>

<Why_This_Exists>
SVA는 RTL 설계의 의도(intent)를 수학적으로 표현하는 유일한 방법이다.
잘 작성된 assertion은:
- Formal tool (SymbiYosys)로 수학적 증명 가능
- 시뮬레이션에서 버그를 즉시 감지
- 설계 문서 역할 (executable specification)
일관된 SVA 패턴을 따르면 가독성, 재사용성, 도구 호환성이 향상된다.
</Why_This_Exists>

<Execution_Policy>
- SVA를 작성하는 모든 에이전트에 적용
- RTL 모듈 내부 assertion보다 bind 파일 방식 우선 권장
- 모든 assertion에는 failure message 필수
- `templates/sva-bind-template.sv`를 새 SVA 파일의 시작점으로 사용
- `examples/fifo-sva-example.sv`로 FIFO safety assertion 패턴 확인
</Execution_Policy>

<Steps>

## 1. Assertion 스타일 분류

| 스타일 | 용도 | 키워드 |
|--------|------|--------|
| Immediate | combinational 조건 체크 | `assert (expr)` |
| Concurrent | 시간 기반 property 검증 | `assert property (...)` |
| Deferred | delta-cycle 이후 체크 | `assert #0 (expr)` |
| Assume | formal tool에 입력 제약 전달 | `assume property (...)` |
| Cover | 도달 가능성 확인 | `cover property (...)` |
| Restrict | formal에만 적용되는 제약 | `restrict property (...)` |

### 사용 가이드
- **시뮬레이션 + formal 공용**: `assert property` 사용
- **Formal 전용 입력 제약**: `assume property` 사용
- **커버리지 목표**: `cover property` 사용
- Immediate assert는 combinational 체크에만 사용 (always_comb 내부)

## 2. 명명 규칙

| 대상 | 패턴 | 예시 |
|------|------|------|
| Assert 라벨 | `a_{signal}_{condition}` | `a_valid_hold`, `a_data_stable` |
| Assume 라벨 | `m_{signal}_{constraint}` | `m_valid_no_x`, `m_addr_aligned` |
| Cover 라벨 | `c_{scenario}` | `c_back_to_back`, `c_max_burst` |
| Sequence | `seq_{name}` | `seq_handshake`, `seq_burst_complete` |
| Property | `prop_{name}` | `prop_valid_hold`, `prop_fifo_no_overflow` |
| SVA 파일 | `sva_{module}.sv` | `sva_axi_slave.sv` |
| SVA bind 모듈 | `sva_{module}_checker` | `sva_axi_slave_checker` |

## 3. 클럭/리셋 패턴

### 3.1 기본 구조
```systemverilog
// 모든 concurrent assertion은 default clocking + disable iff 사용
default clocking cb @(posedge sys_clk); endclocking
default disable iff (!sys_rst_n);
```

### 3.2 Past-Valid Guard
리셋 직후 첫 사이클은 $past() 값이 무효하므로 guard 사용:
```systemverilog
logic past_valid;
always_ff @(posedge sys_clk or negedge sys_rst_n) begin
  if (!sys_rst_n) past_valid <= 1'b0;
  else            past_valid <= 1'b1;
end

// $past 사용 시 반드시 past_valid 체크
a_data_stable: assert property (
  past_valid && $rose(i_valid) |-> ##1 $stable(i_data)
) else $error("Data must be stable after valid rises");
```

## 4. 핵심 Assertion 패턴

### 4.1 Valid/Ready Handshake
```systemverilog
// Valid는 ready 올 때까지 유지
a_valid_hold: assert property (
  i_valid && !o_ready |=> i_valid
) else $error("valid must hold until ready");

// Valid 중 data 안정
a_data_stable: assert property (
  i_valid && !o_ready |=> $stable(i_data)
) else $error("data must be stable while valid && !ready");

// Unknown 금지
a_valid_no_x: assert property (
  !$isunknown(i_valid)
) else $error("valid must not be X/Z");
```

### 4.2 FIFO Safety
```systemverilog
a_no_overflow: assert property (
  i_push && !i_pop |-> o_count < DEPTH
) else $error("FIFO overflow: push when full");

a_no_underflow: assert property (
  i_pop && !i_push |-> o_count > 0
) else $error("FIFO underflow: pop when empty");
```

### 4.3 One-Hot / Mutex
```systemverilog
a_onehot_grant: assert property (
  $onehot0(o_grant)
) else $error("Grant must be one-hot or zero");

a_mutex_access: assert property (
  !(o_read_en && o_write_en)
) else $error("Simultaneous read and write forbidden");
```

### 4.4 Liveness (Eventually)
```systemverilog
// Request는 반드시 N 사이클 내에 응답
a_req_ack: assert property (
  i_req |-> ##[1:MAX_LATENCY] o_ack
) else $error("No ack within MAX_LATENCY cycles");
```

## 5. Bind 파일 패턴

RTL 모듈을 수정하지 않고 외부에서 assertion을 attach:
```systemverilog
// sva_my_module.sv
module sva_my_module_checker (
  input logic       sys_clk,
  input logic       sys_rst_n,
  input logic [7:0] i_data,
  input logic       i_valid,
  input logic       o_ready
);
  default clocking cb @(posedge sys_clk); endclocking
  default disable iff (!sys_rst_n);

  // Assertions here...
  a_valid_hold: assert property (
    i_valid && !o_ready |=> i_valid
  ) else $error("valid must hold until ready");
endmodule

// Bind statement (별도 파일 또는 같은 파일 하단)
bind my_module sva_my_module_checker u_sva_checker (.*);
```
See `templates/sva-bind-template.sv` for complete scaffold.

## 6. SymbiYosys 통합

### 6.1 Formal 검증 모드
| 모드 | 용도 | SBY 설정 |
|------|------|---------|
| BMC (Bounded Model Check) | 유한 깊이 반례 탐색 | `mode bmc`, `depth 20-50` |
| Induction (prove) | 무한 깊이 수학적 증명 | `mode prove` |
| Cover | 커버 포인트 도달성 확인 | `mode cover` |

### 6.2 assume vs assert
- `assume`: formal tool의 입력 제약 (시뮬에서는 assert처럼 동작)
- `assert`: 검증 대상 property
- formal에서는 assume 위반 시 해당 trace 무시 (over-constraint 주의!)

### 6.3 Liveness 주의
- BMC는 liveness property(eventually) 증명 불가 — prove 모드 사용
- Prove에서도 무한 대기 시 induction 실패 가능 → bound 추가

## 7. Anti-Patterns

| Anti-Pattern | 문제 | 수정 |
|-------------|------|------|
| `assert(signal)` in always_ff | 시뮬 only, formal 미지원 | `assert property` 사용 |
| missing `disable iff` | 리셋 중 false failure | `default disable iff (!rst_n)` |
| `$past` without past_valid | 리셋 직후 X값 비교 | past_valid guard 추가 |
| Over-constraining with assume | valid trace 없음 | assume 최소화, cover로 확인 |
| No failure message | 디버그 불가 | 모든 assert에 `else $error(...)` |
| `assert property` in `always_comb` | 문법 오류 | concurrent assert는 모듈 스코프에 배치 |

</Steps>

<Tool_Usage>
이 스킬은 직접 실행하지 않는다. SVA를 생성하는 에이전트가 참조한다:
```
Task(subagent_type="rtl-agent-team:sva-extractor",
     prompt="... Follow systemverilog-assertion skill conventions. Use bind file pattern.")

Task(subagent_type="rtl-agent-team:protocol-checker",
     prompt="... Follow systemverilog-assertion skill for AXI protocol assertions.")
```
</Tool_Usage>

<Examples>
<Good>
Bind 파일 사용, default clocking/disable, past_valid guard, failure message:
```systemverilog
default clocking cb @(posedge sys_clk); endclocking
default disable iff (!sys_rst_n);

a_valid_hold: assert property (
  i_valid && !o_ready |=> i_valid
) else $error("[%m] valid dropped before ready at %0t", $time);
```
</Good>
<Bad>
RTL 내부 직접 삽입, immediate assert, 메시지 없음:
```systemverilog
always_ff @(posedge clk) begin
  assert(valid);  // WRONG: immediate, no message, wrong clock name
end
```
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- SymbiYosys BMC/prove FAIL → sva-extractor에게 반례 분석, rtl-coder에게 RTL 수정 요청
- Over-constrained (cover FAIL) → assume 조건 검토
- 프로토콜 스펙 불명확 → spec-analyst에게 확인 요청
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Bind 파일 방식 사용 (RTL 내부 직접 삽입 최소화)
- [ ] `default clocking` / `default disable iff` 설정
- [ ] $past 사용 시 past_valid guard 존재
- [ ] 모든 assert에 `else $error(...)` failure message
- [ ] 라벨 명명: `a_` (assert), `m_` (assume), `c_` (cover)
- [ ] Unknown 체크: `$isunknown` 사용
- [ ] Cover property로 assertion 도달성 확인
- [ ] 포트명이 RTL과 일치 (i_/o_, sys_clk, sys_rst_n)
</Final_Checklist>
