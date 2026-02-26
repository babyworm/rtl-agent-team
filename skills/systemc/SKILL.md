---
name: systemc
description: "SystemC/TLM-2.0 coding convention and design guideline skill. Enforces coding standards for BFM development (Phase 3) and Reference Model development (Phase 2). Covers TLM-2.0 AT/LT patterns, AMBA-PV extensions, naming conventions, and testbench integration."
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
- **AT (Approximately Timed) non-blocking이 BFM의 기본 모델링 스타일**
- `templates/tlm2-module-template.cpp`를 새 모듈의 시작점으로 사용
- `examples/bfm-at-pattern.cpp`로 AT BFM 구현 패턴 확인
</Execution_Policy>

<Steps>

## 1. 명명 규칙

### 1.1 파일명
| 유형 | 패턴 | 예시 |
|------|------|------|
| Reference Model | `ref_{module}.cpp / .h` | `ref_cabac.cpp` |
| BFM | `bfm_{module}.cpp / .h` | `bfm_axi_master.cpp` |
| TLM Adapter | `tlm_{module}_adapter.cpp` | `tlm_cabac_adapter.cpp` |
| Memory Manager | `memory_manager.h` | `memory_manager.h` |
| DPI-C Interface | `dpi_{module}.cpp / .h` | `dpi_interface.cpp` |
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
SystemC 포트는 RTL 포트와 동일한 이름을 사용:
```cpp
sc_in<sc_uint<8>>  i_data{"i_data"};
sc_out<bool>        o_valid{"o_valid"};
sc_in<bool>         sys_clk{"sys_clk"};       // clock: no i_/o_ prefix
sc_in<bool>         sys_rst_n{"sys_rst_n"};   // reset: no i_/o_ prefix
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
  static uint32_t encode_bin(uint16_t ctx_addr, bool bin_val,
                             const ctx_table_t& ctx_table);
  void process_block(const block_input_t& input, block_output_t& output);
  void reset();
private:
  ctx_table_t m_ctx_table;
};
```

### 2.3 고정소수점 규칙
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
- **AT non-blocking 기본**: `nb_transport_fw/bw()` 사용 (LT는 명시 요청 시만)
- **Pin-adapter 분리**: TLM 추상화와 핀 레벨 인터페이스를 분리
- **AXI 기본 프로토콜**: AHB/APB/ACE는 명시 요청 시만

### 3.2 Coding Styles
| Style | Interface | Use Case |
|-------|-----------|----------|
| **AT (Approximately Timed)** | `nb_transport_fw/bw()` | **DEFAULT**. Timing-accurate, pipelined, OoO |
| **LT (Loosely Timed)** | `b_transport()` | Fast simulation, simple register access only |

### 3.3 AT 4-Phase Protocol
```
Initiator                    Target
    |-------- BEGIN_REQ ------->|
    |<------- END_REQ ----------|
    |<------- BEGIN_RESP -------|
    |-------- END_RESP -------->|
```

### 3.4 필수 헤더
```cpp
#include <systemc>
#include <tlm>
#include <tlm_utils/simple_initiator_socket.h>
#include <tlm_utils/simple_target_socket.h>
#include <tlm_utils/peq_with_cb_and_phase.h>  // AT phase scheduling
// #include <amba_pv.h>  // AMBA protocol extensions (when needed)
```

### 3.5 BFM 아키텍처
```
┌────────────┐  AT nb_transport  ┌────────────┐
│ Testbench  │◄──── fw/bw ─────►│    BFM     │
│ (Initiator)│                   │(Cycle-acc.)│
└────────────┘                   └─────┬─────┘
                                       │ Pin Adapter
                                ┌──────▼──────┐
                                │ RTL Wrapper  │   (optional)
                                │ (sc_signal)  │──► DPI-C ──► SV TB
                                └─────────────┘
```

## 4. Memory Manager (Payload Pooling)

AT 모델에서 payload 재사용을 위한 필수 컴포넌트:
```cpp
class MemoryManager : public tlm::tlm_mm_interface {
public:
    tlm::tlm_generic_payload* allocate() {
        if (m_pool.empty()) return new tlm::tlm_generic_payload(this);
        auto* p = m_pool.back(); m_pool.pop_back(); return p;
    }
    void free(tlm::tlm_generic_payload* p) override {
        p->reset(); m_pool.push_back(p);
    }
    ~MemoryManager() override { for (auto* p : m_pool) delete p; }
private:
    std::vector<tlm::tlm_generic_payload*> m_pool;
};
```
사용: `m_mm.allocate()` → `trans->acquire()` → ... → `trans->release()`

## 5. AMBA-PV 프로토콜 선택

| Protocol | When to Use |
|----------|-------------|
| **AXI** | DEFAULT. High-performance, burst, out-of-order |
| **AHB** | Legacy interconnect, in-order |
| **APB** | Low-bandwidth peripherals, register access |
| **ACE** | ONLY when cache coherency is explicitly required |

기본 AXI extension 설정:
```cpp
#include <amba_pv.h>

auto* ext = new amba_pv::axi_extension();
ext->set_id(0);
ext->set_burst(amba_pv::AXI_BURST_INCR);  // Incrementing (most common)
ext->set_length(burst_len);                // AxLEN (beats - 1)
ext->set_size(log2(beat_size));            // AxSIZE
ext->set_cache(0xF);                       // Write-back, allocate
ext->set_prot(0x0);                        // Unprivileged, secure, data
trans.set_extension(ext);
```
> AHB/APB/ACE 상세 및 AXI 속성 테이블은 `<Advanced>` 섹션 참조.

## 6. 빌드 규칙

```bash
# Reference Model (standalone, no SystemC)
g++ -std=c++17 -O2 -Wall -Wextra -shared -fPIC -o ref_cabac.so ref_cabac.cpp

# BFM (SystemC required)
g++ -std=c++17 -O2 -Wall -Wextra \
  -I${SYSTEMC_HOME}/include -L${SYSTEMC_HOME}/lib-linux64 -lsystemc \
  -o tb_cabac tb_cabac_top.cpp bfm_cabac.cpp

# cocotb integration (shared library)
g++ -std=c++17 -shared -fPIC -o ref_cabac.so ref_cabac.cpp
```

cocotb 연동:
```python
import ctypes
lib = ctypes.CDLL("./ref_cabac.so")
lib.encode_bin.restype = ctypes.c_uint32
lib.encode_bin.argtypes = [ctypes.c_uint16, ctypes.c_bool]
expected = lib.encode_bin(ctx_addr, bin_val)
```

## 7. 코딩 스타일

### 7.1 필수
- C++17 이상, 고정폭 정수 (`<cstdint>`), RAII, `const`, Header guard
- AT 모델: MemoryManager + PEQ 사용

### 7.2 금지
- `float`/`double` in bit-exact models
- `malloc`/`free`, platform-dependent `int`
- `using namespace std;` in headers
- LT `b_transport` in performance BFMs (AT 사용)

</Steps>

<Tool_Usage>
이 스킬은 직접 실행하지 않는다. SystemC 코드를 생성하는 에이전트가 참조한다:
```
Task(subagent_type="rtl-agent-team:bfm-dev",
     prompt="... Follow systemc skill conventions. Use AT non-blocking transport.")

Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="... Follow systemc skill conventions for bit-accurate reference model.")
```
</Tool_Usage>

<Examples>
<Good>
AT non-blocking BFM with AXI extension and memory manager:
```cpp
void axi_master_bfm::run() {
    tlm::tlm_generic_payload* trans = m_mm.allocate();
    trans->acquire();
    // ... setup payload + AXI extension ...
    tlm::tlm_phase phase = tlm::BEGIN_REQ;
    sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
    init_socket->nb_transport_fw(*trans, phase, delay);
    // ... handle END_REQ, BEGIN_RESP, END_RESP via PEQ ...
    trans->release();
}
```
</Good>
<Good>
Bit-exact ref model with fixed-width integers:
```cpp
int32_t cabac_ref_model::encode_bin(uint16_t ctx_addr, bool bin_val) {
  uint16_t range = m_ctx_table[ctx_addr].range;
  uint16_t lps   = static_cast<uint16_t>((range >> 6) & 0x03);
  // ... bit-exact operations
}
```
</Good>
<Bad>
Float, platform-dependent int, LT in performance BFM:
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
- AMBA-PV 헤더 미설치 → 사용자에게 ARM AMBA-PV 라이브러리 설치 안내
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] 파일명 규칙: `ref_` / `bfm_` / `tlm_` / `dpi_` prefix
- [ ] 고정폭 정수만 사용 (`int32_t` 등, no `int`/`float`)
- [ ] Reference Model: cycle-agnostic, deterministic
- [ ] BFM: AT non-blocking 기본, 4-phase 프로토콜
- [ ] BFM: Memory Manager + PEQ 사용
- [ ] AMBA extension 설정 (AXI burst/cache/prot)
- [ ] 포트명이 RTL 포트명과 일치 (`i_data`, `o_valid`, `sys_clk`)
- [ ] cocotb 연동용 shared library 빌드 가능
- [ ] `m_` prefix for member variables
- [ ] Header guard 존재
</Final_Checklist>

<Advanced>

## AMBA-PV Protocol Details

### AXI Burst Types
| Type | Value | Description |
|------|-------|-------------|
| `AXI_BURST_FIXED` | 0 | Fixed address (FIFO access) |
| `AXI_BURST_INCR` | 1 | Incrementing address (DEFAULT) |
| `AXI_BURST_WRAP` | 2 | Wrapping burst (cache line) |

### AXI Cache Attributes (AxCACHE)
- `0x0`: Non-cacheable, non-bufferable (device)
- `0x3`: Cacheable, bufferable, no allocate
- `0xF`: Write-back, read/write allocate (normal memory)

### AXI Response Codes
| Code | Description |
|------|-------------|
| `AXI_RESP_OKAY` | Success |
| `AXI_RESP_EXOKAY` | Exclusive access success |
| `AXI_RESP_SLVERR` | Slave error |
| `AXI_RESP_DECERR` | Decode error (no slave at address) |

### AHB Extension
```cpp
auto* ahb_ext = new amba_pv::ahb_extension();
ahb_ext->set_trans(amba_pv::AHB_TRANS_NONSEQ);
ahb_ext->set_burst(amba_pv::AHB_BURST_SINGLE);
ahb_ext->set_size(2);  // 4 bytes (2^2)
ahb_ext->set_prot(0x0);
ahb_ext->set_master(0);
trans.set_extension(ahb_ext);
```
Transfer types: `AHB_TRANS_IDLE` (0), `AHB_TRANS_BUSY` (1), `AHB_TRANS_NONSEQ` (2), `AHB_TRANS_SEQ` (3)
Burst types: `SINGLE`, `INCR`, `WRAP4`, `INCR4`, `WRAP8`, `INCR8`, `WRAP16`, `INCR16`

### APB Extension
```cpp
auto* apb_ext = new amba_pv::apb_extension();
apb_ext->set_prot(0x0);
trans.set_extension(apb_ext);
```
APB: Single 32-bit transfers only, in-order, 2-phase (SETUP + ACCESS).

### ACE Extension (Cache Coherency)
ACE는 cache coherency가 명시적으로 필요한 경우에만 사용:
```cpp
auto* ace_ext = new amba_pv::ace_extension();
ace_ext->set_domain(amba_pv::ACE_DOMAIN_INNER_SHAREABLE);
ace_ext->set_snoop(amba_pv::ACE_SNOOP_READ_SHARED);
ace_ext->set_barrier(amba_pv::ACE_BARRIER_NORMAL);
ace_ext->set_burst(amba_pv::AXI_BURST_INCR);
ace_ext->set_cache(0xF);
trans.set_extension(ace_ext);
```
Domain types: `NON_SHAREABLE`, `INNER_SHAREABLE`, `OUTER_SHAREABLE`, `SYSTEM`

## DPI-C Co-simulation

SystemVerilog co-simulation이 필요한 경우에만 사용.

### DPI-C Interface Header
```cpp
// dpi_interface.h
#ifdef __cplusplus
extern "C" {
#endif

void dpi_sc_init();
void dpi_sc_run(uint64_t time_ps);
void dpi_sc_finish();
int  dpi_axi_write(uint64_t addr, const unsigned char* data, unsigned int len);
int  dpi_axi_read(uint64_t addr, unsigned char* data, unsigned int len);

extern void sv_notify_completion(int trans_id, int status);

#ifdef __cplusplus
}
#endif
```

### SystemVerilog DPI Import
```systemverilog
module tb_dpi_cosim;
    import "DPI-C" function void dpi_sc_init();
    import "DPI-C" function void dpi_sc_run(longint unsigned time_ps);
    import "DPI-C" function void dpi_sc_finish();
    import "DPI-C" function int dpi_axi_write(
        longint unsigned addr, input byte unsigned data[], int unsigned len);

    export "DPI-C" function sv_notify_completion;

    function void sv_notify_completion(int trans_id, int status);
        $display("Transaction %0d completed with status %0d", trans_id, status);
    endfunction

    initial begin
        dpi_sc_init();
        dpi_sc_run(100_000);  // 100ns
        // ... transactions ...
        dpi_sc_finish();
        $finish;
    end
endmodule
```

## LT (Loosely Timed) Pattern

LT는 단순 레지스터 접근 (APB/AXI-Lite) 또는 빠른 SW 시뮬레이션에만 사용:
```cpp
void my_bfm::b_transport(tlm::tlm_generic_payload& trans, sc_time& delay) {
  if (trans.get_command() == tlm::TLM_WRITE_COMMAND) {
    std::memcpy(&m_memory[addr], data, len);
    trans.set_response_status(tlm::TLM_OK_RESPONSE);
  } else if (trans.get_command() == tlm::TLM_READ_COMMAND) {
    std::memcpy(data, &m_memory[addr], len);
    trans.set_response_status(tlm::TLM_OK_RESPONSE);
  }
  delay += sc_time(m_latency_cycles * m_clk_period_ns, SC_NS);
}
```

## AMBA-PV Build

```bash
# BFM with AMBA-PV headers
g++ -std=c++17 -O2 -Wall -Wextra \
  -I${SYSTEMC_HOME}/include -I${AMBA_PV_HOME}/include \
  -L${SYSTEMC_HOME}/lib-linux64 -lsystemc \
  -o tb_axi tb_axi_top.cpp bfm_axi_master.cpp
```

## Anti-patterns

| Category | Forbidden | Correct |
|----------|-----------|---------|
| Protocol | LT when AT is specified | Use nb_transport_fw/bw |
| Protocol | ACE when simple AXI suffices | Use AXI by default |
| Timing | Magic numbers: `wait(2.0, SC_NS)` | Derive from timing_constraints.json |
| Memory | No memory manager for pooled payloads | Use tlm_mm_interface + acquire/release |
| Extensions | Leaking extension memory | Call p->reset() in MemoryManager::free() |
| Phases | Missing phase transitions in AT | Implement all 4 phases with PEQ |
| Verification | Model without testbench | Every model needs sc_main testbench |
| DPI | Blocking calls that deadlock | Queue to SC_THREAD for async handling |
| Response | Missing set_response_status() | Always set before returning |

</Advanced>
