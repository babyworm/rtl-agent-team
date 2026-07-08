---
name: systemc
description: "systemc project conventions (loaded by writer agents; do not invoke)."
user-invocable: false
---

<Purpose>
SystemC/TLM-2.0 project conventions for Reference Model (Phase 2) and BFM (Phase 3) code.
This skill covers project-specific rules only — TLM-2.0 mechanics (IEEE 1666-2011) are assumed known.

Language standard pins:
- Reference Model: **C11** (`-std=c11`), pure C, standalone — compilable without SystemC
- BFM/SystemC: **C++17** (`-std=c++17`); C++20 features (concepts, ranges, coroutines, modules) forbidden
</Purpose>

<Use_When>
- Writing .cpp/.h in a SystemC/TLM-2.0 context (Phase 2 Reference Model, Phase 3 BFM)
- Agents: bfm-dev, ref-model-dev
</Use_When>

<Do_Not_Use_When>
- SystemVerilog code → `systemverilog` skill; Python cocotb → `rtl-p5s-func-verify` skill; non-SystemC C/C++ utilities
</Do_Not_Use_When>

<Execution_Policy>
- **AT (Approximately Timed) non-blocking is the default BFM style**: `nb_transport_fw/bw()` with
  PEQ (`peq_with_cb_and_phase`) and payload pooling (`tlm_mm_interface` + `acquire()`/`release()`).
  LT (`b_transport()`) only for simple register access (APB/AXI-Lite) or when explicitly requested
- **AXI is the default protocol** (amba_pv extensions); AHB/APB only for legacy/low-bandwidth
  targets; ACE ONLY when cache coherency is explicitly required
- New module scaffold: `templates/tlm2-module-template.cpp`
- AT pattern incl. MemoryManager + PEQ + 4-phase handling: `examples/bfm-at-pattern.cpp`
- LT pattern (simple register access): `examples/bfm-pattern.cpp`
</Execution_Policy>

<Steps>

## 1. Naming Conventions

### 1.1 Filenames
| Type | Pattern | Example |
|------|---------|---------|
| Reference Model | `ref_{module}.c / .h` | `ref_cabac.c` |
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

## 2. Bit-Exactness Rules (Reference Model)

Core principles:
- **Bit-accurate**: must guarantee identical bit-level results as the RTL
- **Cycle-agnostic**: implements only the algorithm, no timing concepts
- **Deterministic**: same input → same output (no random, no float)
- **Standalone**: compilable as pure C without SystemC

Fixed-point rules:
- Fixed-width integers only (`int16_t`, `uint32_t`); no `int` (platform-dependent width), no `float`/`double`
- Explicitly specify overflow behavior: saturate vs wrap
```cpp
// CORRECT: bit-exact fixed-point multiply
int32_t fixed_mul(int16_t a, int16_t b) {
  return static_cast<int32_t>(a) * static_cast<int32_t>(b);
}
// WRONG: 'int result = a * b;' — implicit promotion may differ from RTL
```

## 3. BFM Rules

- **Cycle-accurate**: produce results in the same number of cycles as RTL
- **AT non-blocking by default**; LT only when explicitly requested (see Execution_Policy)
- **Separate pin-adapter**: keep TLM abstraction separate from the pin-level interface (sc_signal
  RTL wrapper + optional DPI-C bridge to SV TB)
- Timing values derive from `timing_constraints.json` — no magic `wait(2.0, SC_NS)` numbers
- Every model needs an `sc_main` testbench; always call `set_response_status()` before returning

## 4. Build Rules

```bash
# Reference Model (standalone C, no SystemC)
gcc -std=c11 -O2 -Wall -Wextra -Werror -shared -fPIC -o ref_cabac.so ref_cabac.c

# BFM (SystemC required)
g++ -std=c++17 -O2 -Wall -Wextra \
  -I${SYSTEMC_HOME}/include -L${SYSTEMC_HOME}/lib-linux64 -lsystemc \
  -o tb_cabac tb_cabac_top.cpp bfm_cabac.cpp

# cocotb integration (shared library, C ref model)
gcc -std=c11 -shared -fPIC -o ref_cabac.so ref_cabac.c
```

cocotb integration:
```python
import ctypes
lib = ctypes.CDLL("./ref_cabac.so")
lib.encode_bin.restype = ctypes.c_uint32
lib.encode_bin.argtypes = [ctypes.c_uint16, ctypes.c_bool]
expected = lib.encode_bin(ctx_addr, bin_val)
```

## 5. Coding Style

Mandatory:
- C++17 (not C++20), fixed-width integers (`<cstdint>`), RAII, `const`, header guard
- AT models: MemoryManager (payload pooling via `tlm_mm_interface`, `p->reset()` in `free()`) + PEQ

Prohibited:
- `float`/`double` in bit-exact models; platform-dependent `int`
- `malloc`/`free` (use RAII); `using namespace std;` in headers
- LT `b_transport` in performance BFMs (use AT); missing AT phase transitions (implement all 4 phases with PEQ)
- Blocking DPI calls that deadlock (queue to SC_THREAD for async handling)

</Steps>

<Tool_Usage>
This skill is not executed directly. It is referenced by agents that generate SystemC code
(e.g., bfm-dev, ref-model-dev). Agents should follow the conventions defined here.
</Tool_Usage>

<Examples>
AT non-blocking BFM (MemoryManager, PEQ, AXI extension, 4-phase): `examples/bfm-at-pattern.cpp`.
LT register-access BFM: `examples/bfm-pattern.cpp`.
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
