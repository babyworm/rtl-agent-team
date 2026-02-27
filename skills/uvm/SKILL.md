---
name: uvm
description: "UVM (Universal Verification Methodology) coding convention and methodology guideline skill. Covers class hierarchy, factory patterns, sequence/sequencer, TLM ports, coverage integration, and naming conventions for UVM testbenches."
---

<Purpose>
UVM 코딩 표준 및 방법론 가이드라인.
UVM 기반 검증 환경을 구축하거나 수정하는 에이전트는 이 스킬의 규칙을 따라야 한다.
IEEE 1800.2-2020 UVM Standard를 기본으로 한다.
</Purpose>

<Use_When>
- UVM testbench, agent, sequence, scoreboard 작성 시
- uvm-verify 스킬 실행을 위한 UVM 환경 구축 시
- Phase 5 (Verification) — UVM 기반 검증 작업 시
- 에이전트: testbench-dev
</Use_When>

<Do_Not_Use_When>
- cocotb Python 기반 검증 시 → `func-verify` 스킬 사용
- SVA assertion만 작성 시 → `systemverilog-assertion` 스킬 사용
- RTL 합성 코드 작성 시 → `systemverilog` 스킬 사용
</Do_Not_Use_When>

<Why_This_Exists>
UVM은 산업 표준 검증 방법론이나, 자유도가 높아 일관되지 않은 코드가 만들어지기 쉽다.
일관된 명명 규칙, 클래스 구조, factory 사용 패턴을 따르면:
- 환경 재사용성 극대화 (agent를 여러 프로젝트에서 재사용)
- 디버깅 용이성 (예측 가능한 구조)
- Coverage 통합이 자연스러움
</Why_This_Exists>

<Execution_Policy>
- UVM 환경을 생성하는 모든 에이전트에 적용
- `templates/uvm-env-template.sv`를 새 환경의 시작점으로 사용
- `examples/uvm-smoke-test-example.sv`로 기본 smoke test 구조 확인
- 모든 UVM 컴포넌트는 factory에 등록 (`uvm_component_utils` / `uvm_object_utils`)
- Phase callback 순서를 정확히 따를 것
</Execution_Policy>

<Steps>

## 1. 명명 규칙

### 1.1 파일명
| 유형 | 패턴 | 예시 |
|------|------|------|
| Agent | `{proto}_agent.sv` | `axi_agent.sv` |
| Driver | `{proto}_driver.sv` | `axi_driver.sv` |
| Monitor | `{proto}_monitor.sv` | `axi_monitor.sv` |
| Sequencer | `{proto}_sequencer.sv` | `axi_sequencer.sv` |
| Sequence Item | `{proto}_seq_item.sv` | `axi_seq_item.sv` |
| Sequence | `{proto}_{name}_seq.sv` | `axi_write_seq.sv` |
| Scoreboard | `{module}_scoreboard.sv` | `cabac_scoreboard.sv` |
| Environment | `{module}_env.sv` | `cabac_env.sv` |
| Test | `{module}_{name}_test.sv` | `cabac_smoke_test.sv` |
| Package | `{module}_tb_pkg.sv` | `cabac_tb_pkg.sv` |
| Top | `tb_{module}_top.sv` | `tb_cabac_top.sv` |

### 1.2 클래스 명명
| 대상 | 패턴 | 예시 |
|------|------|------|
| Agent | `{proto}_agent` | `axi_agent` |
| Driver | `{proto}_driver` | `axi_driver` |
| Monitor | `{proto}_monitor` | `axi_monitor` |
| Sequencer | `{proto}_sequencer` | `axi_sequencer` |
| Sequence Item | `{proto}_seq_item` | `axi_seq_item` |
| Sequence (base) | `{proto}_base_seq` | `axi_base_seq` |
| Sequence (specific) | `{proto}_{name}_seq` | `axi_write_burst_seq` |
| Scoreboard | `{module}_scoreboard` | `cabac_scoreboard` |
| Environment | `{module}_env` | `cabac_env` |
| Test (base) | `{module}_base_test` | `cabac_base_test` |
| Coverage | `{module}_coverage` | `cabac_coverage` |

### 1.3 인스턴스 명명 (create)
```systemverilog
// 인스턴스명은 변수명과 동일하게
m_driver  = axi_driver::type_id::create("m_driver", this);
m_monitor = axi_monitor::type_id::create("m_monitor", this);
m_seqr    = axi_sequencer::type_id::create("m_seqr", this);
```

## 2. UVM 클래스 계층

```
uvm_test
 └── cabac_base_test
      └── cabac_smoke_test
           └── cabac_random_test

uvm_env
 └── cabac_env
      ├── axi_agent (m_axi_agt)
      │    ├── axi_driver (m_driver)
      │    ├── axi_monitor (m_monitor)
      │    └── axi_sequencer (m_seqr)
      ├── cabac_scoreboard (m_scoreboard)
      └── cabac_coverage (m_coverage)
```

## 3. Factory 등록 (필수)

모든 UVM 컴포넌트/오브젝트는 반드시 factory에 등록:
```systemverilog
class axi_driver extends uvm_driver #(axi_seq_item);
  `uvm_component_utils(axi_driver)

  function new(string name = "axi_driver", uvm_component parent = null);
    super.new(name, parent);
  endfunction
  // ...
endclass

class axi_seq_item extends uvm_sequence_item;
  `uvm_object_utils(axi_seq_item)

  function new(string name = "axi_seq_item");
    super.new(name);
  endfunction
  // ...
endclass
```

## 4. Phase Callback 순서

| Phase | 용도 | 주의사항 |
|-------|------|---------|
| `build_phase` | 컴포넌트 create, config_db get | create는 여기서만 |
| `connect_phase` | TLM 포트 연결 | build 완료 후 |
| `end_of_elaboration_phase` | 최종 구조 확인 | 선택적 |
| `run_phase` | 시뮬레이션 실행 | raise/drop objection 필수 |
| `extract_phase` | 결과 수집 | 선택적 |
| `check_phase` | pass/fail 판정 | 선택적 |
| `report_phase` | 결과 리포트 | scoreboard 요약 |

### Objection 규칙
```systemverilog
task cabac_base_test::run_phase(uvm_phase phase);
  phase.raise_objection(this, "Test started");
  // ... test body (start sequences)
  phase.drop_objection(this, "Test completed");
endtask
```
- **Only test raises/drops objection** — sequence나 driver에서 금지
- objection 없으면 시뮬레이션 즉시 종료

## 5. TLM 포트 사용

| 포트 유형 | 방향 | 용도 |
|----------|------|------|
| `uvm_analysis_port` | Monitor → Scoreboard/Coverage | 브로드캐스트 (1:N) |
| `uvm_seq_item_pull_port` | Driver ↔ Sequencer | 자동 연결 |
| `uvm_analysis_imp` | Scoreboard 수신부 | write() 구현 필수 |

```systemverilog
// Monitor: analysis port 선언 및 사용
class axi_monitor extends uvm_monitor;
  uvm_analysis_port #(axi_seq_item) m_ap;

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_ap = new("m_ap", this);
  endfunction

  task run_phase(uvm_phase phase);
    // ... capture transaction
    m_ap.write(txn);  // broadcast to all subscribers
  endtask
endclass

// Scoreboard: analysis imp 선언
class cabac_scoreboard extends uvm_scoreboard;
  `uvm_analysis_imp_decl(_input)
  `uvm_analysis_imp_decl(_output)

  uvm_analysis_imp_input  #(axi_seq_item, cabac_scoreboard) m_input_imp;
  uvm_analysis_imp_output #(axi_seq_item, cabac_scoreboard) m_output_imp;

  function void write_input(axi_seq_item txn);
    // enqueue expected
  endfunction

  function void write_output(axi_seq_item txn);
    // compare with expected
  endfunction
endclass
```

## 6. config_db 사용

```systemverilog
// Test → Agent: virtual interface 전달 (build_phase)
uvm_config_db #(virtual axi_if)::set(this, "m_env.m_axi_agt*", "vif", m_vif);

// Agent: virtual interface 가져오기 (build_phase)
if (!uvm_config_db #(virtual axi_if)::get(this, "", "vif", m_vif))
  `uvm_fatal("NO_VIF", "Virtual interface not set for agent")
```
- set/get 경로는 hierarchy 기반 (wildcard `*` 사용 가능)
- 가져오기 실패 시 `uvm_fatal` 필수

## 7. Coverage 통합

```systemverilog
class cabac_coverage extends uvm_subscriber #(axi_seq_item);
  `uvm_component_utils(cabac_coverage)

  covergroup cg_transaction;
    cp_cmd:    coverpoint m_txn.cmd    { bins read = {0}; bins write = {1}; }
    cp_size:   coverpoint m_txn.size   { bins sizes[] = {1, 2, 4, 8}; }
    cross cp_cmd, cp_size;
  endgroup

  function new(string name, uvm_component parent);
    super.new(name, parent);
    cg_transaction = new();
  endfunction

  function void write(axi_seq_item t);
    m_txn = t;
    cg_transaction.sample();
  endfunction
endclass
```

## 8. Anti-Patterns

| Anti-Pattern | 문제 | 수정 |
|-------------|------|------|
| Factory 미등록 | override/재사용 불가 | 모든 클래스에 `uvm_*_utils` |
| Driver에서 objection | phase 제어 혼란 | test에서만 raise/drop |
| config_db get 실패 무시 | null pointer crash | `uvm_fatal` 처리 |
| Sequence에서 DUT 직접 접근 | 재사용성 파괴 | sequencer→driver 경로만 사용 |
| Hard-coded hierarchy path | 이식성 파괴 | config_db wildcard 사용 |
| run_phase에서 `#delay` | 이식성 파괴 | `@(posedge vif.sys_clk)` 사용 |

</Steps>

<Tool_Usage>
이 스킬은 직접 실행하지 않는다. UVM 환경을 생성하는 에이전트가 참조한다:
```
Task(subagent_type="rtl-agent-team:testbench-dev",
     prompt="... Follow uvm skill conventions. Use factory registration for all components.")
```
</Tool_Usage>

<Examples>
<Good>
Factory 등록, 올바른 명명, config_db 사용, analysis port:
```systemverilog
class axi_agent extends uvm_agent;
  `uvm_component_utils(axi_agent)
  axi_driver    m_driver;
  axi_monitor   m_monitor;
  axi_sequencer m_seqr;

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_driver  = axi_driver::type_id::create("m_driver", this);
    m_monitor = axi_monitor::type_id::create("m_monitor", this);
    m_seqr    = axi_sequencer::type_id::create("m_seqr", this);
  endfunction
endclass
```
</Good>
<Bad>
Factory 미사용, 하드코딩, 직접 new:
```systemverilog
class my_agent extends uvm_agent;
  // WRONG: no uvm_component_utils
  my_driver drv;
  function void build_phase(uvm_phase phase);
    drv = new("drv", this);  // WRONG: bypasses factory
  endfunction
endclass
```
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- UVM 환경 컴파일 에러 → testbench-dev에게 수정 요청
- Coverage 목표 미달 → 추가 sequence 작성 또는 coverage-analyst에게 분석 요청
- Scoreboard mismatch → func-verifier에게 RTL vs Ref Model 비교 요청
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] 모든 UVM 클래스에 factory 등록 (`uvm_component_utils` / `uvm_object_utils`)
- [ ] Objection은 test에서만 raise/drop
- [ ] config_db get 실패 시 `uvm_fatal` 처리
- [ ] TLM analysis port로 monitor→scoreboard 연결
- [ ] Virtual interface를 config_db로 전달
- [ ] 명명 규칙: `{proto}_agent`, `{proto}_driver`, `m_` prefix 인스턴스
- [ ] Coverage collector가 analysis port에 subscribe
- [ ] 포트명이 RTL과 일치 (sys_clk, sys_rst_n, i_/o_)
</Final_Checklist>
