---
name: systemc
description: "SystemC/TLM-2.0 coding convention and design guideline skill. Enforces coding standards for BFM development (Phase 3) and Reference Model development (Phase 2). Covers TLM-2.0 patterns, naming conventions, and testbench integration."
---

<Purpose>
SystemC/TLM-2.0 코딩 표준 및 설계 가이드라인.
모든 .cpp, .h 파일을 SystemC/TLM 컨텍스트에서 생성하거나 수정하는 에이전트는 이 스킬의 규칙을 따라야 한다.
BFM (Bus Functional Model)과 Reference Model 개발에 적용된다.
</Purpose>

<Use_When>
- .cpp, .h 파일을 SystemC/TLM-2.0 컨텍스트에서 작성할 때
- Phase 2 (Architecture) — Reference Model 개발 시
- Phase 3 (μArch) — BFM 개발 시
- 에이전트: bfm-dev, ref-model-dev
</Use_When>

<Do_Not_Use_When>
- SystemVerilog 코드 작성 시 → `systemverilog` 스킬 사용
- 순수 C/C++ (non-SystemC) 유틸리티 작성 시
- Python cocotb 테스트 작성 시 → `func-verify` 스킬 참조
</Do_Not_Use_When>

<Why_This_Exists>
BFM과 Reference Model은 RTL 검증의 기준점(golden reference)이다.
일관된 코딩 표준과 TLM-2.0 패턴을 따르면:
- cocotb/UVM 테스트벤치와의 통합이 용이
- bit-accurate comparison을 위한 인터페이스가 명확
- Phase 간 모델 재사용이 가능 (Ref Model → BFM → cocotb golden)
</Why_This_Exists>

<Execution_Policy>
- BFM, Reference Model을 생성하는 모든 에이전트에 적용
- TLM-2.0 표준(IEEE 1666-2011)을 기본으로 따른다
- `templates/tlm2-module-template.cpp`를 새 모듈의 시작점으로 사용
- `examples/bfm-pattern.cpp`로 BFM 구현 패턴 확인
</Execution_Policy>

<Steps>

## 1. 명명 규칙

### 1.1 파일명
| 유형 | 패턴 | 예시 |
|------|------|------|
| Reference Model | `ref_{module}.cpp / .h` | `ref_cabac.cpp` |
| BFM | `bfm_{module}.cpp / .h` | `bfm_axi_master.cpp` |
| TLM Adapter | `tlm_{module}_adapter.cpp` | `tlm_cabac_adapter.cpp` |
| Testbench Top | `tb_{module}_top.cpp` | `tb_cabac_top.cpp` |
| Package (shared types) | `{module}_types.h` | `cabac_types.h` |

### 1.2 클래스/모듈 명명
| 대상 | 규칙 | 예시 |
|------|------|------|
| SC_MODULE | `snake_case` | `cabac_encoder_bfm` |
| Reference Model 클래스 | `{module}_ref_model` | `cabac_ref_model` |
| BFM 클래스 | `{module}_bfm` | `axi_master_bfm` |
| TLM Socket | `{role}_{protocol}_socket` | `init_axi_socket`, `targ_mem_socket` |
| 멤버 변수 | `m_` prefix | `m_state`, `m_ctx_table` |
| 상수 | `UPPER_SNAKE_CASE` | `MAX_CTX_ENTRIES` |

### 1.3 포트 명명 (RTL 매칭)
SystemC 포트는 RTL 포트와 동일한 이름을 사용하여 cocotb 연동을 용이하게 한다:
```cpp
// RTL: input logic [7:0] i_data → SystemC:
sc_in<sc_uint<8>>  i_data{"i_data"};
sc_out<bool>        o_valid{"o_valid"};
sc_in<bool>         sys_clk{"sys_clk"};
sc_in<bool>         sys_rst_n{"sys_rst_n"};
```

## 2. Reference Model 규칙

### 2.1 기본 원칙
- **Bit-accurate**: RTL과 동일한 비트 연산 결과를 보장
- **Cycle-agnostic**: 타이밍 개념 없이 알고리즘만 구현
- **Deterministic**: 동일 입력 → 동일 출력 보장 (no random, no float)
- **Standalone**: SystemC 없이도 순수 C/C++로 컴파일 가능해야 함

### 2.2 인터페이스 패턴
```cpp
class cabac_ref_model {
public:
  // Pure function: input → output, no side effects on global state
  static uint32_t encode_bin(uint16_t ctx_addr, bool bin_val,
                             const ctx_table_t& ctx_table);

  // Stateful: maintains internal context table
  void process_block(const block_input_t& input, block_output_t& output);

  // Reset
  void reset();

private:
  ctx_table_t m_ctx_table;
};
```

### 2.3 고정소수점 규칙
- RTL과 동일한 비트폭, 반올림, 클리핑 적용
- `int16_t`, `uint32_t` 등 고정폭 정수 사용 (no `int`, no `float`)
- 오버플로우 동작 명시: saturate vs wrap
```cpp
// CORRECT: bit-exact fixed-point multiply
int32_t fixed_mul(int16_t a, int16_t b) {
  return static_cast<int32_t>(a) * static_cast<int32_t>(b);
}

// WRONG: implicit promotion may differ from RTL
int result = a * b;  // 'int' width is platform-dependent
```

## 3. BFM (Bus Functional Model) 규칙

### 3.1 기본 원칙
- **Cycle-accurate**: RTL과 동일한 사이클 수에 결과 생성
- **TLM-2.0 compliant**: `tlm_generic_payload` 기반 트랜잭션
- **Pin-adapter 분리**: TLM 추상화와 핀 레벨 인터페이스를 분리

### 3.2 TLM-2.0 소켓 사용
```cpp
// Initiator (master)
tlm_utils::simple_initiator_socket<axi_master_bfm> m_init_socket{"m_init_socket"};

// Target (slave)
tlm_utils::simple_target_socket<memory_bfm> m_targ_socket{"m_targ_socket"};
```

### 3.3 BFM 아키텍처
```
┌─────────────┐      TLM-2.0       ┌─────────────┐
│  Testbench  │◄──── b_transport ──►│    BFM       │
│  (Initiator)│                     │ (Cycle-acc.) │
└─────────────┘                     └──────┬──────┘
                                           │ Pin Adapter
                                    ┌──────▼──────┐
                                    │ RTL Wrapper  │
                                    │ (sc_signal)  │
                                    └─────────────┘
```

### 3.4 b_transport 구현
```cpp
void my_bfm::b_transport(tlm::tlm_generic_payload& trans, sc_time& delay) {
  uint64_t addr = trans.get_address();
  uint8_t* data = trans.get_data_ptr();
  unsigned int len = trans.get_data_length();

  if (trans.get_command() == tlm::TLM_WRITE_COMMAND) {
    // Write operation
    std::memcpy(&m_memory[addr], data, len);
    trans.set_response_status(tlm::TLM_OK_RESPONSE);
  } else if (trans.get_command() == tlm::TLM_READ_COMMAND) {
    // Read operation
    std::memcpy(data, &m_memory[addr], len);
    trans.set_response_status(tlm::TLM_OK_RESPONSE);
  }

  // Cycle-accurate delay
  delay += sc_time(m_latency_cycles * m_clk_period_ns, SC_NS);
}
```

## 4. 빌드 규칙

### 4.1 컴파일
```bash
# Reference Model (standalone, no SystemC)
g++ -std=c++17 -O2 -Wall -Wextra -shared -fPIC \
  -o ref_cabac.so ref_cabac.cpp

# BFM (SystemC required)
g++ -std=c++17 -O2 -Wall -Wextra \
  -I${SYSTEMC_HOME}/include \
  -L${SYSTEMC_HOME}/lib-linux64 -lsystemc \
  -o tb_cabac tb_cabac_top.cpp bfm_cabac.cpp

# cocotb integration (shared library)
g++ -std=c++17 -shared -fPIC -o ref_cabac.so ref_cabac.cpp
# Python: ctypes.CDLL("ref_cabac.so")
```

### 4.2 cocotb 연동
Reference Model을 cocotb에서 호출하는 패턴:
```python
import ctypes

lib = ctypes.CDLL("./ref_cabac.so")
lib.encode_bin.restype = ctypes.c_uint32
lib.encode_bin.argtypes = [ctypes.c_uint16, ctypes.c_bool]

# Call in cocotb test
expected = lib.encode_bin(ctx_addr, bin_val)
assert int(dut.o_result.value) == expected
```

## 5. 코딩 스타일

### 5.1 필수
- C++17 이상 (`std::optional`, `std::variant`, structured bindings)
- 고정폭 정수: `<cstdint>` 타입 사용 (`int32_t`, `uint8_t`)
- RAII: 리소스 관리에 스마트 포인터 사용
- `const` 적극 사용 (입력 파라미터, 멤버 함수)
- Header guard: `#pragma once` 또는 `#ifndef` 매크로

### 5.2 금지
- `float`/`double` in bit-exact models (고정소수점 대신 사용 금지)
- `malloc`/`free` (C++ `new`/`delete` 또는 smart pointer 사용)
- Platform-dependent `int` width (항상 `int32_t` 등 명시적 폭 사용)
- `using namespace std;` in headers

</Steps>

<Tool_Usage>
이 스킬은 직접 실행하지 않는다. SystemC 코드를 생성하는 에이전트가 참조한다:
```
Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="... Follow systemc skill conventions. Use templates/tlm2-module-template.cpp as scaffold.")

Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="... Follow systemc skill conventions for bit-accurate reference model.")
```
</Tool_Usage>

<Examples>
<Good>
TLM-2.0 compliant BFM, bit-exact ref model with fixed-width integers:
```cpp
int32_t cabac_ref_model::encode_bin(uint16_t ctx_addr, bool bin_val) {
  uint16_t range = m_ctx_table[ctx_addr].range;
  uint16_t lps   = static_cast<uint16_t>((range >> 6) & 0x03);
  // ... bit-exact operations
}
```
</Good>
<Bad>
Float 사용, platform-dependent int, TLM 미준수:
```cpp
float encode_result = ctx_range * 0.5f;  // WRONG: float in bit-exact model
int lps = range >> 6;                     // WRONG: 'int' is platform-dependent
```
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Ref Model과 RTL 간 bit mismatch → func-verifier에게 불일치 리포트
- TLM-2.0 소켓 연결 오류 → bfm-dev에게 재검토 요청
- 고정소수점 오버플로우 동작 불명확 → spec-analyst에게 스펙 확인 요청
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] 파일명 규칙: `ref_` / `bfm_` / `tlm_` prefix
- [ ] 고정폭 정수만 사용 (`int32_t` 등, no `int`/`float`)
- [ ] Reference Model: cycle-agnostic, deterministic
- [ ] BFM: cycle-accurate, TLM-2.0 `b_transport` 구현
- [ ] 포트명이 RTL 포트명과 일치 (`i_data`, `o_valid`, `sys_clk`)
- [ ] cocotb 연동용 shared library 빌드 가능
- [ ] `m_` prefix for member variables
- [ ] Header guard 존재
</Final_Checklist>
