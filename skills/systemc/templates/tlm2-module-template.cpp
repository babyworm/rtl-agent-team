// =============================================================================
// TLM-2.0 AT Module Template (Non-Blocking, AMBA-PV)
// Module: {{MODULE_NAME}}_bfm
// Description: {{BRIEF_DESCRIPTION}}
// Author: bfm-dev (generated)
//
// Transport style: AT (Approximately Timed) — non-blocking nb_transport_fw/bw
// Protocol: AXI (default) via amba_pv::axi_extension
// Payload pooling: MemoryManager (tlm_mm_interface)
// Phase scheduling: PEQ (peq_with_cb_and_phase)
// =============================================================================

#pragma once

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_initiator_socket.h>
#include <tlm_utils/simple_target_socket.h>
#include <tlm_utils/peq_with_cb_and_phase.h>
#include <cstdint>
#include <cstring>
#include <vector>

// Uncomment when using AMBA-PV protocol extensions
// #include <amba_pv.h>

// =============================================================================
// Shared Types (import from {module}_types.h)
// =============================================================================
// #include "{{MODULE_NAME}}_types.h"

struct {{MODULE_NAME}}_config_t {
  uint32_t base_addr;
  uint32_t data_width;
  uint32_t latency_cycles;
  double   clk_period_ns;  // Derived from timing_constraints.json
};

// =============================================================================
// Memory Manager (Payload Pooling — required for AT models)
// =============================================================================
class {{MODULE_NAME}}_mm : public tlm::tlm_mm_interface {
public:
  {{MODULE_NAME}}_mm() = default;

  ~{{MODULE_NAME}}_mm() override {
    for (auto* p : m_pool) { delete p; }
  }

  tlm::tlm_generic_payload* allocate() {
    if (m_pool.empty()) {
      return new tlm::tlm_generic_payload(this);
    }
    auto* p = m_pool.back();
    m_pool.pop_back();
    return p;
  }

  void free(tlm::tlm_generic_payload* p) override {
    p->reset();  // Clears extensions, data pointer, etc.
    m_pool.push_back(p);
  }

private:
  std::vector<tlm::tlm_generic_payload*> m_pool;
};

// =============================================================================
// BFM Target Module (AT Non-Blocking)
// =============================================================================
class {{MODULE_NAME}}_bfm : public sc_core::sc_module {
public:
  // -------------------------------------------------------------------------
  // TLM-2.0 Sockets (AT style)
  // -------------------------------------------------------------------------
  tlm_utils::simple_target_socket<{{MODULE_NAME}}_bfm> m_targ_socket{"m_targ_socket"};
  // tlm_utils::simple_initiator_socket<{{MODULE_NAME}}_bfm> m_init_socket{"m_init_socket"};

  // -------------------------------------------------------------------------
  // Pin-Level Ports (for RTL co-simulation, matching io_definition.json)
  // -------------------------------------------------------------------------
  // Clock/reset: no i_/o_ prefix
  sc_core::sc_in<bool>            sys_clk{"sys_clk"};
  sc_core::sc_in<bool>            sys_rst_n{"sys_rst_n"};
  // Data ports: i_/o_ prefix convention
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
    , m_peq(this, &{{MODULE_NAME}}_bfm::peq_callback)
    , m_memory(config.data_width, 0)
    , m_latency(config.latency_cycles * config.clk_period_ns, sc_core::SC_NS)
  {
    // Register AT non-blocking transport
    m_targ_socket.register_nb_transport_fw(
      this, &{{MODULE_NAME}}_bfm::nb_transport_fw);

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
  // AT Non-Blocking Forward Transport (4-phase protocol)
  // -------------------------------------------------------------------------
  tlm::tlm_sync_enum nb_transport_fw(
    tlm::tlm_generic_payload& trans,
    tlm::tlm_phase& phase,
    sc_core::sc_time& delay
  ) {
    if (phase == tlm::BEGIN_REQ) {
      // Accept request, schedule END_REQ immediately
      m_peq.notify(trans, tlm::END_REQ, delay);

      // Schedule BEGIN_RESP after latency
      m_peq.notify(trans, tlm::BEGIN_RESP, delay + m_latency);

      return tlm::TLM_ACCEPTED;
    }
    else if (phase == tlm::END_RESP) {
      // Transaction complete — initiator acknowledged response
      return tlm::TLM_COMPLETED;
    }

    SC_REPORT_ERROR("BFM", "Unexpected phase in forward path");
    return tlm::TLM_ACCEPTED;
  }

  // -------------------------------------------------------------------------
  // PEQ Callback (phase scheduling)
  // -------------------------------------------------------------------------
  void peq_callback(tlm::tlm_generic_payload& trans,
                     const tlm::tlm_phase& phase)
  {
    tlm::tlm_phase new_phase = phase;
    sc_core::sc_time delay = sc_core::SC_ZERO_TIME;

    if (phase == tlm::END_REQ) {
      // Send END_REQ back to initiator
      m_targ_socket->nb_transport_bw(trans, new_phase, delay);
    }
    else if (phase == tlm::BEGIN_RESP) {
      // Execute the actual transaction
      execute_transaction(trans);
      // Send BEGIN_RESP to initiator
      m_targ_socket->nb_transport_bw(trans, new_phase, delay);
    }
  }

  // -------------------------------------------------------------------------
  // Transaction Execution
  // -------------------------------------------------------------------------
  void execute_transaction(tlm::tlm_generic_payload& trans) {
    const uint64_t addr   = trans.get_address();
    uint8_t*       data   = trans.get_data_ptr();
    const unsigned int len = trans.get_data_length();
    const uint64_t local_addr = addr - m_config.base_addr;

    if (local_addr + len > m_memory.size()) {
      trans.set_response_status(tlm::TLM_ADDRESS_ERROR_RESPONSE);
      return;
    }

    // Optional: read AXI extension attributes
    // auto* axi_ext = trans.get_extension<amba_pv::axi_extension>();
    // if (axi_ext) {
    //   unsigned int beats = axi_ext->get_length() + 1;
    //   // ... adjust behavior based on burst type, cache, etc.
    // }

    if (trans.get_command() == tlm::TLM_WRITE_COMMAND) {
      std::memcpy(&m_memory[local_addr], data, len);
      trans.set_response_status(tlm::TLM_OK_RESPONSE);
    } else if (trans.get_command() == tlm::TLM_READ_COMMAND) {
      std::memcpy(data, &m_memory[local_addr], len);
      trans.set_response_status(tlm::TLM_OK_RESPONSE);
    } else {
      trans.set_response_status(tlm::TLM_COMMAND_ERROR_RESPONSE);
    }
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
  {{MODULE_NAME}}_config_t                               m_config;
  tlm_utils::peq_with_cb_and_phase<{{MODULE_NAME}}_bfm> m_peq;
  std::vector<uint8_t>                                   m_memory;
  sc_core::sc_time                                       m_latency;
  uint64_t                                               m_cycle_count{0};
};
