// =============================================================================
// TLM-2.0 Module Template
// Module: {{MODULE_NAME}}_bfm
// Description: {{BRIEF_DESCRIPTION}}
// Author: bfm-dev (generated)
// =============================================================================

#pragma once

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_initiator_socket.h>
#include <tlm_utils/simple_target_socket.h>
#include <cstdint>
#include <cstring>
#include <vector>

// =============================================================================
// Shared Types (import from {module}_types.h)
// =============================================================================
// #include "{{MODULE_NAME}}_types.h"

struct {{MODULE_NAME}}_config_t {
  uint32_t base_addr;
  uint32_t data_width;
  uint32_t latency_cycles;
};

// =============================================================================
// BFM Module
// =============================================================================
class {{MODULE_NAME}}_bfm : public sc_core::sc_module {
public:
  // -------------------------------------------------------------------------
  // TLM-2.0 Sockets
  // -------------------------------------------------------------------------
  tlm_utils::simple_target_socket<{{MODULE_NAME}}_bfm> m_targ_socket{"m_targ_socket"};
  // tlm_utils::simple_initiator_socket<{{MODULE_NAME}}_bfm> m_init_socket{"m_init_socket"};

  // -------------------------------------------------------------------------
  // Pin-Level Ports (for RTL co-simulation)
  // -------------------------------------------------------------------------
  sc_core::sc_in<bool>            sys_clk{"sys_clk"};
  sc_core::sc_in<bool>            sys_rst_n{"sys_rst_n"};
  // sc_core::sc_in<sc_dt::sc_uint<8>>   i_data{"i_data"};
  // sc_core::sc_out<bool>                o_valid{"o_valid"};

  // -------------------------------------------------------------------------
  // Constructor
  // -------------------------------------------------------------------------
  SC_HAS_PROCESS({{MODULE_NAME}}_bfm);

  explicit {{MODULE_NAME}}_bfm(sc_core::sc_module_name name,
                                const {{MODULE_NAME}}_config_t& config)
    : sc_module(name)
    , m_config(config)
    , m_memory(config.data_width, 0)
  {
    // Register TLM target callback
    m_targ_socket.register_b_transport(this, &{{MODULE_NAME}}_bfm::b_transport);

    // Register clock-edge process (for cycle-accurate behavior)
    SC_METHOD(clock_edge_process);
    sensitive << sys_clk.pos();
    dont_initialize();
  }

  // -------------------------------------------------------------------------
  // Reset
  // -------------------------------------------------------------------------
  void reset() {
    std::fill(m_memory.begin(), m_memory.end(), 0);
    m_cycle_count = 0;
  }

private:
  // -------------------------------------------------------------------------
  // TLM-2.0 Blocking Transport
  // -------------------------------------------------------------------------
  void b_transport(tlm::tlm_generic_payload& trans, sc_core::sc_time& delay) {
    const uint64_t addr   = trans.get_address();
    uint8_t*       data   = trans.get_data_ptr();
    const unsigned int len = trans.get_data_length();
    const uint64_t local_addr = addr - m_config.base_addr;

    if (local_addr + len > m_memory.size()) {
      trans.set_response_status(tlm::TLM_ADDRESS_ERROR_RESPONSE);
      return;
    }

    if (trans.get_command() == tlm::TLM_WRITE_COMMAND) {
      std::memcpy(&m_memory[local_addr], data, len);
      trans.set_response_status(tlm::TLM_OK_RESPONSE);
    } else if (trans.get_command() == tlm::TLM_READ_COMMAND) {
      std::memcpy(data, &m_memory[local_addr], len);
      trans.set_response_status(tlm::TLM_OK_RESPONSE);
    } else {
      trans.set_response_status(tlm::TLM_COMMAND_ERROR_RESPONSE);
    }

    // Cycle-accurate delay model
    delay += sc_core::sc_time(
      m_config.latency_cycles * CLK_PERIOD_NS, sc_core::SC_NS
    );
  }

  // -------------------------------------------------------------------------
  // Clock Edge Process (cycle-accurate behavior)
  // -------------------------------------------------------------------------
  void clock_edge_process() {
    if (!sys_rst_n.read()) {
      reset();
      return;
    }
    m_cycle_count++;
    // TODO: Implement cycle-accurate pipeline behavior
  }

  // -------------------------------------------------------------------------
  // Internal State
  // -------------------------------------------------------------------------
  static constexpr double CLK_PERIOD_NS = 10.0;  // Match RTL clock

  {{MODULE_NAME}}_config_t    m_config;
  std::vector<uint8_t>        m_memory;
  uint64_t                    m_cycle_count{0};
};
