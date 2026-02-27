---
name: systemc
description: "SystemC/TLM-2.0 coding convention and design guideline skill. Enforces coding standards for BFM development (Phase 3) and Reference Model development (Phase 2). Covers TLM-2.0 AT/LT patterns, AMBA-PV extensions, naming conventions, and testbench integration."
---

<Purpose>
SystemC/TLM-2.0 coding standards and design guidelines.
All agents generating or modifying .cpp, .h files in a SystemC/TLM context must follow the rules in this skill.
Applies to BFM (Bus Functional Model) and Reference Model development.

Target standard: **C++17** (`-std=c++17`).
- C++17 features: structured bindings, if constexpr, std::optional, std::string_view, fold expressions — all permitted
- C++20 features (concepts, ranges, coroutines, modules) — do NOT use (tool/platform compatibility concerns)
- All compile commands must include `-std=c++17`
</Purpose>

<Use_When>
- When writing .cpp, .h files in a SystemC/TLM-2.0 context
- During Phase 2 (Architecture) — Reference Model development
- During Phase 3 (uArch) — BFM development
- Agents: bfm-dev, ref-model-dev
</Use_When>

<Do_Not_Use_When>
- When writing SystemVerilog code → use `systemverilog` skill
- When writing pure C/C++ (non-SystemC) utilities
- When writing Python cocotb tests → refer to `func-verify` skill
</Do_Not_Use_When>

<Why_This_Exists>
BFMs and Reference Models are the golden reference for RTL verification.
Following consistent coding standards and TLM-2.0 patterns ensures:
- Easy integration with cocotb/UVM testbenches
- Clear interfaces for bit-accurate comparison
- Model reuse across phases (Ref Model → BFM → cocotb golden)
</Why_This_Exists>

<Execution_Policy>
- Applies to all agents generating BFMs and Reference Models
- Based on the TLM-2.0 standard (IEEE 1666-2011)
- **AT (Approximately Timed) non-blocking is the default modeling style for BFMs**
- Use `templates/tlm2-module-template.cpp` as the starting point for new modules
- Review `examples/bfm-at-pattern.cpp` for AT BFM implementation patterns
- Review `examples/bfm-pattern.cpp` for LT-style BFM implementation patterns (for simple register access)
</Execution_Policy>

<Steps>

## 1. Naming Conventions

### 1.1 Filenames
| Type | Pattern | Example |
|------|---------|---------|
| Reference Model | `ref_{module}.cpp / .h` | `ref_cabac.cpp` |
| BFM | `bfm_{module}.cpp / .h` | `bfm_axi_master.cpp` |
| TLM Adapter | `tlm_{module}_adapter.cpp` | `tlm_cabac_adapter.cpp` |
| Memory Manager | `memory_manager.h` | `memory_manager.h` |
| DPI-C Interface | `dpi_{module}.cpp / .h` | `dpi_interface.cpp` |
| Testbench Top | `tb_{module}_top.cpp` | `tb_cabac_top.cpp` |
| Package (shared types) | `{module}_types.h` | `cabac_types.h` |

### 1.2 Class/Module Naming
| Target | Rule | Example |
|--------|------|---------|
| SC_MODULE | `snake_case` | `cabac_encoder_bfm` |
| Reference Model class | `{module}_ref_model` | `cabac_ref_model` |
| BFM class | `{module}_bfm` | `axi_master_bfm` |
| TLM Socket | `{role}_{protocol}_socket` | `init_axi_socket`, `targ_mem_socket` |
| Member variables | `m_` prefix | `m_state`, `m_ctx_table` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_CTX_ENTRIES` |

### 1.3 Port Naming (RTL Matching)
SystemC ports use the same names as their RTL counterparts:
```cpp
sc_in<sc_uint<8>>  i_data{"i_data"};
sc_out<bool>        o_valid{"o_valid"};
sc_in<bool>         sys_clk{"sys_clk"};       // clock: no i_/o_ prefix
sc_in<bool>         sys_rst_n{"sys_rst_n"};   // reset: no i_/o_ prefix
```

## 2. Reference Model Rules

### 2.1 Core Principles
- **Bit-accurate**: Must guarantee identical bit-level results as the RTL
- **Cycle-agnostic**: Implements only the algorithm, with no timing concepts
- **Deterministic**: Same input → same output guaranteed (no random, no float)
- **Standalone**: Must be compilable as pure C/C++ without SystemC

### 2.2 Interface Patterns
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

### 2.3 Fixed-Point Rules
- Use fixed-width integers such as `int16_t`, `uint32_t` (no `int`, no `float`)
- Explicitly specify overflow behavior: saturate vs wrap
```cpp
// CORRECT: bit-exact fixed-point multiply
int32_t fixed_mul(int16_t a, int16_t b) {
  return static_cast<int32_t>(a) * static_cast<int32_t>(b);
}

// WRONG: implicit promotion may differ from RTL
int result = a * b;  // 'int' width is platform-dependent
```

## 3. BFM (Bus Functional Model) Rules

### 3.1 Core Principles
- **Cycle-accurate**: Produce results in the same number of cycles as RTL
- **AT non-blocking by default**: Use `nb_transport_fw/bw()` (LT only when explicitly requested)
- **Separate pin-adapter**: Separate TLM abstraction from pin-level interface
- **AXI as default protocol**: AHB/APB/ACE only when explicitly requested

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

### 3.4 Required Headers
```cpp
#include <systemc>
#include <tlm>
#include <tlm_utils/simple_initiator_socket.h>
#include <tlm_utils/simple_target_socket.h>
#include <tlm_utils/peq_with_cb_and_phase.h>  // AT phase scheduling
// #include <amba_pv.h>  // AMBA protocol extensions (when needed)
```

### 3.5 BFM Architecture
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

Required component for payload reuse in AT models:
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
Usage: `m_mm.allocate()` → `trans->acquire()` → ... → `trans->release()`

## 5. AMBA-PV Protocol Selection

| Protocol | When to Use |
|----------|-------------|
| **AXI** | DEFAULT. High-performance, burst, out-of-order |
| **AHB** | Legacy interconnect, in-order |
| **APB** | Low-bandwidth peripherals, register access |
| **ACE** | ONLY when cache coherency is explicitly required |

Default AXI extension setup:
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
> See the `<Advanced>` section for AHB/APB/ACE details and AXI attribute tables.

## 6. Build Rules

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

cocotb integration:
```python
import ctypes
lib = ctypes.CDLL("./ref_cabac.so")
lib.encode_bin.restype = ctypes.c_uint32
lib.encode_bin.argtypes = [ctypes.c_uint16, ctypes.c_bool]
expected = lib.encode_bin(ctx_addr, bin_val)
```

## 7. Coding Style

### 7.1 Mandatory
- C++17 or later, fixed-width integers (`<cstdint>`), RAII, `const`, Header guard
- AT models: use MemoryManager + PEQ

### 7.2 Prohibited
- `float`/`double` in bit-exact models
- `malloc`/`free`, platform-dependent `int`
- `using namespace std;` in headers
- LT `b_transport` in performance BFMs (use AT)

</Steps>

<Tool_Usage>
This skill is not executed directly. It is referenced by agents that generate SystemC code:
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
- Bit mismatch between Ref Model and RTL → report discrepancy to func-verifier
- TLM-2.0 socket connection error → request review from bfm-dev
- Fixed-point overflow behavior unclear → request spec clarification from spec-analyst
- AMBA-PV headers not installed → guide user to install the ARM AMBA-PV library
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] Filename convention: `ref_` / `bfm_` / `tlm_` / `dpi_` prefix
- [ ] Use fixed-width integers only (`int32_t` etc., no `int`/`float`)
- [ ] Reference Model: cycle-agnostic, deterministic
- [ ] BFM: AT non-blocking by default, 4-phase protocol
- [ ] BFM: use Memory Manager + PEQ
- [ ] AMBA extension configured (AXI burst/cache/prot)
- [ ] Port names match RTL port names (`i_data`, `o_valid`, `sys_clk`)
- [ ] Shared library buildable for cocotb integration
- [ ] `m_` prefix for member variables
- [ ] Header guard present
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
Use ACE only when cache coherency is explicitly required:
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

Use only when SystemVerilog co-simulation is needed.

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

Use LT only for simple register access (APB/AXI-Lite) or fast SW simulation:
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
