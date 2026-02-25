// =============================================================================
// Example: AXI-Lite Slave BFM with Cycle-Accurate Latency
// Demonstrates TLM-2.0 target socket, register map, and cocotb integration
// =============================================================================

#pragma once

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_target_socket.h>
#include <cstdint>
#include <cstring>
#include <array>
#include <iostream>

// =============================================================================
// Register Map (shared with RTL via _pkg.sv)
// =============================================================================
namespace axi_lite_regs {
  constexpr uint32_t CTRL_REG    = 0x00;  // [0]=enable, [1]=start
  constexpr uint32_t STATUS_REG  = 0x04;  // [0]=busy, [1]=done, [2]=error
  constexpr uint32_t DATA_IN_REG = 0x08;  // Input data register
  constexpr uint32_t DATA_OUT_REG = 0x0C; // Output data register
  constexpr uint32_t REG_COUNT   = 4;
  constexpr uint32_t REG_SIZE    = REG_COUNT * 4;  // 16 bytes
}

// =============================================================================
// AXI-Lite Slave BFM
// =============================================================================
class axi_lite_slave_bfm : public sc_core::sc_module {
public:
  // TLM-2.0 target socket
  tlm_utils::simple_target_socket<axi_lite_slave_bfm> m_targ_socket{"m_targ_socket"};

  // Pin-level ports (matching RTL port names)
  sc_core::sc_in<bool>  sys_clk{"sys_clk"};
  sc_core::sc_in<bool>  sys_rst_n{"sys_rst_n"};

  SC_HAS_PROCESS(axi_lite_slave_bfm);

  explicit axi_lite_slave_bfm(sc_core::sc_module_name name)
    : sc_module(name)
  {
    m_targ_socket.register_b_transport(this, &axi_lite_slave_bfm::b_transport);
    m_registers.fill(0);

    SC_METHOD(process);
    sensitive << sys_clk.pos();
    dont_initialize();
  }

  // -------------------------------------------------------------------------
  // Reset
  // -------------------------------------------------------------------------
  void reset() {
    m_registers.fill(0);
    m_processing = false;
    m_process_countdown = 0;
  }

  // -------------------------------------------------------------------------
  // Register Access (for testbench direct read)
  // -------------------------------------------------------------------------
  uint32_t read_reg(uint32_t addr) const {
    const uint32_t idx = addr >> 2;
    if (idx < axi_lite_regs::REG_COUNT) {
      return m_registers[idx];
    }
    return 0xDEADBEEF;
  }

private:
  // -------------------------------------------------------------------------
  // TLM-2.0 Blocking Transport
  // -------------------------------------------------------------------------
  void b_transport(tlm::tlm_generic_payload& trans, sc_core::sc_time& delay) {
    const uint64_t addr = trans.get_address();
    uint8_t* data = trans.get_data_ptr();
    const unsigned int len = trans.get_data_length();

    // Address range check
    if (addr + len > axi_lite_regs::REG_SIZE) {
      trans.set_response_status(tlm::TLM_ADDRESS_ERROR_RESPONSE);
      SC_REPORT_WARNING("BFM", "Address out of range");
      return;
    }

    // Alignment check (32-bit aligned access only)
    if (addr % 4 != 0 || len != 4) {
      trans.set_response_status(tlm::TLM_BURST_ERROR_RESPONSE);
      SC_REPORT_WARNING("BFM", "Unaligned or non-32bit access");
      return;
    }

    const uint32_t reg_idx = static_cast<uint32_t>(addr >> 2);

    if (trans.get_command() == tlm::TLM_WRITE_COMMAND) {
      uint32_t wdata;
      std::memcpy(&wdata, data, sizeof(wdata));
      m_registers[reg_idx] = wdata;

      // Side effect: writing CTRL_REG[1]=start triggers processing
      if (reg_idx == (axi_lite_regs::CTRL_REG >> 2) && (wdata & 0x2)) {
        m_processing = true;
        m_process_countdown = PROCESS_LATENCY;
        // Set STATUS.busy
        m_registers[axi_lite_regs::STATUS_REG >> 2] |= 0x1;
      }

      trans.set_response_status(tlm::TLM_OK_RESPONSE);
    } else if (trans.get_command() == tlm::TLM_READ_COMMAND) {
      uint32_t rdata = m_registers[reg_idx];
      std::memcpy(data, &rdata, sizeof(rdata));
      trans.set_response_status(tlm::TLM_OK_RESPONSE);
    }

    // 1 cycle access latency
    delay += sc_core::sc_time(CLK_PERIOD_NS, sc_core::SC_NS);
  }

  // -------------------------------------------------------------------------
  // Cycle-Accurate Processing
  // -------------------------------------------------------------------------
  void process() {
    if (!sys_rst_n.read()) {
      reset();
      return;
    }

    if (m_processing && m_process_countdown > 0) {
      m_process_countdown--;
      if (m_process_countdown == 0) {
        // Processing complete: compute result from DATA_IN
        uint32_t input = m_registers[axi_lite_regs::DATA_IN_REG >> 2];
        uint32_t result = compute(input);
        m_registers[axi_lite_regs::DATA_OUT_REG >> 2] = result;

        // Update STATUS: clear busy, set done
        m_registers[axi_lite_regs::STATUS_REG >> 2] =
          (m_registers[axi_lite_regs::STATUS_REG >> 2] & ~0x1u) | 0x2u;

        m_processing = false;
      }
    }
  }

  // -------------------------------------------------------------------------
  // Computation (replace with actual algorithm)
  // -------------------------------------------------------------------------
  static uint32_t compute(uint32_t input) {
    // Example: bit-exact transformation (no float!)
    uint16_t lo = static_cast<uint16_t>(input & 0xFFFF);
    uint16_t hi = static_cast<uint16_t>((input >> 16) & 0xFFFF);
    int32_t product = static_cast<int32_t>(static_cast<int16_t>(lo))
                    * static_cast<int32_t>(static_cast<int16_t>(hi));
    return static_cast<uint32_t>(product);
  }

  // -------------------------------------------------------------------------
  // Internal State
  // -------------------------------------------------------------------------
  static constexpr double   CLK_PERIOD_NS    = 10.0;
  static constexpr uint32_t PROCESS_LATENCY  = 5;  // cycles

  std::array<uint32_t, axi_lite_regs::REG_COUNT> m_registers;
  bool     m_processing{false};
  uint32_t m_process_countdown{0};
};


// =============================================================================
// Example: Reference Model (standalone, no SystemC dependency)
// Compile: g++ -std=c++17 -shared -fPIC -o ref_compute.so ref_compute.cpp
// =============================================================================

// --- ref_compute.h ---
// #pragma once
// #include <cstdint>
//
// extern "C" {
//   uint32_t ref_compute(uint32_t input);
//   void     ref_reset(void);
// }

// --- ref_compute.cpp ---
// #include "ref_compute.h"
//
// extern "C" {
//   uint32_t ref_compute(uint32_t input) {
//     uint16_t lo = static_cast<uint16_t>(input & 0xFFFF);
//     uint16_t hi = static_cast<uint16_t>((input >> 16) & 0xFFFF);
//     int32_t product = static_cast<int32_t>(static_cast<int16_t>(lo))
//                     * static_cast<int32_t>(static_cast<int16_t>(hi));
//     return static_cast<uint32_t>(product);
//   }
//   void ref_reset(void) { /* nothing for stateless model */ }
// }
//
// --- cocotb usage ---
// import ctypes
// lib = ctypes.CDLL("./ref_compute.so")
// lib.ref_compute.restype = ctypes.c_uint32
// lib.ref_compute.argtypes = [ctypes.c_uint32]
// expected = lib.ref_compute(0xFFFF0002)  # -1 * 2 = -2 → 0xFFFFFFFE
