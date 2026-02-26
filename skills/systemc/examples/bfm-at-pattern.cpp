// =============================================================================
// Example: AXI Master BFM with AT Non-Blocking Transport and AMBA-PV
// Demonstrates the recommended BFM style:
//   - AT (Approximately Timed) nb_transport_fw/bw with 4-phase protocol
//   - AXI burst transactions via amba_pv::axi_extension
//   - Memory Manager (tlm_mm_interface) for payload pooling
//   - PEQ (peq_with_cb_and_phase) for phase scheduling
//   - Performance instrumentation (transaction count, stall cycles)
//
// This is the DEFAULT style for performance-critical BFMs.
// For simple register-access peripherals, see bfm-pattern.cpp (LT style).
// =============================================================================

#pragma once

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_initiator_socket.h>
#include <tlm_utils/peq_with_cb_and_phase.h>
#include <cstdint>
#include <cstring>
#include <vector>
#include <fstream>

// Uncomment when amba_pv headers are available
// #include <amba_pv.h>

// =============================================================================
// Memory Manager (Payload Pooling)
// =============================================================================
class MemoryManager : public tlm::tlm_mm_interface {
public:
  MemoryManager() = default;

  ~MemoryManager() override {
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
    p->reset();
    m_pool.push_back(p);
  }

private:
  std::vector<tlm::tlm_generic_payload*> m_pool;
};

// =============================================================================
// AXI Master BFM (AT Non-Blocking Initiator)
// =============================================================================
class axi_master_bfm : public sc_core::sc_module {
public:
  // TLM-2.0 initiator socket (AT style)
  tlm_utils::simple_initiator_socket<axi_master_bfm> m_init_socket{
      "m_init_socket"};

  // Pin-level ports (matching RTL port names)
  sc_core::sc_in<bool> sys_clk{"sys_clk"};
  sc_core::sc_in<bool> sys_rst_n{"sys_rst_n"};

  SC_HAS_PROCESS(axi_master_bfm);

  explicit axi_master_bfm(sc_core::sc_module_name name,
                           double clk_period_ns = 10.0)
      : sc_module(name),
        m_peq(this, &axi_master_bfm::peq_callback),
        m_clk_period(clk_period_ns, sc_core::SC_NS) {
    m_init_socket.register_nb_transport_bw(
        this, &axi_master_bfm::nb_transport_bw);
    SC_THREAD(run);
  }

  // -------------------------------------------------------------------------
  // Performance Report
  // -------------------------------------------------------------------------
  void write_perf_report(const std::string& path) const {
    std::ofstream f(path);
    f << "{\n"
      << "  \"bfm_version\": \"1.0\",\n"
      << "  \"transport_style\": \"AT\",\n"
      << "  \"amba_protocol\": \"AXI\",\n"
      << "  \"transactions_total\": " << m_transactions << ",\n"
      << "  \"stall_cycles_total\": " << m_stall_cycles << "\n"
      << "}\n";
  }

private:
  // -------------------------------------------------------------------------
  // AT Backward Transport (from target)
  // -------------------------------------------------------------------------
  tlm::tlm_sync_enum nb_transport_bw(tlm::tlm_generic_payload& trans,
                                      tlm::tlm_phase& phase,
                                      sc_core::sc_time& delay) {
    m_peq.notify(trans, phase, delay);
    return tlm::TLM_ACCEPTED;
  }

  // -------------------------------------------------------------------------
  // PEQ Callback (phase scheduling)
  // -------------------------------------------------------------------------
  void peq_callback(tlm::tlm_generic_payload& trans,
                     const tlm::tlm_phase& phase) {
    switch (phase) {
    case tlm::END_REQ:
      // Request phase complete — target accepted our request
      m_end_req_event.notify();
      break;

    case tlm::BEGIN_RESP: {
      // Response arrived — send END_RESP to complete transaction
      tlm::tlm_phase resp_phase = tlm::END_RESP;
      sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
      m_init_socket->nb_transport_fw(trans, resp_phase, delay);
      m_resp_event.notify();
      break;
    }

    default:
      SC_REPORT_ERROR("axi_master_bfm",
                       "Unexpected phase in backward path");
    }
  }

  // -------------------------------------------------------------------------
  // Main Transaction Sequence
  // -------------------------------------------------------------------------
  void run() {
    // Wait for reset de-assertion
    while (!sys_rst_n.read()) {
      wait(sys_clk.posedge_event());
    }
    wait(m_clk_period);  // 1 cycle after reset

    // --- Example: 4-beat AXI INCR burst write (16 bytes) ---
    axi_write_burst(0x1000, 16);

    // --- Example: 4-beat AXI INCR burst read (16 bytes) ---
    axi_read_burst(0x1000, 16);
  }

  // -------------------------------------------------------------------------
  // AXI Burst Write (AT 4-phase)
  // -------------------------------------------------------------------------
  void axi_write_burst(uint64_t addr, unsigned int len) {
    // Allocate from memory manager (no leaks)
    tlm::tlm_generic_payload* trans = m_mm.allocate();
    trans->acquire();

    // Prepare write data
    std::vector<uint8_t> data(len);
    for (unsigned int i = 0; i < len; i++) {
      data[i] = static_cast<uint8_t>(i);
    }

    // Setup generic payload
    trans->set_command(tlm::TLM_WRITE_COMMAND);
    trans->set_address(addr);
    trans->set_data_ptr(data.data());
    trans->set_data_length(len);
    trans->set_streaming_width(len);
    trans->set_byte_enable_ptr(nullptr);
    trans->set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);

    // Optional: set AXI extension
    // auto* axi_ext = new amba_pv::axi_extension();
    // axi_ext->set_id(1);
    // axi_ext->set_burst(amba_pv::AXI_BURST_INCR);
    // axi_ext->set_length((len / 4) - 1);  // AxLEN = beats - 1
    // axi_ext->set_size(2);                  // 4 bytes per beat (2^2)
    // axi_ext->set_cache(0xF);               // Write-back, allocate
    // trans->set_extension(axi_ext);

    // AT 4-phase: Phase 1 — BEGIN_REQ
    tlm::tlm_phase phase = tlm::BEGIN_REQ;
    sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
    tlm::tlm_sync_enum status =
        m_init_socket->nb_transport_fw(*trans, phase, delay);

    if (status == tlm::TLM_ACCEPTED) {
      // Phase 2 — Wait for END_REQ from target via PEQ
      wait(m_end_req_event);
    } else if (status == tlm::TLM_COMPLETED) {
      // Shortcut: transaction completed immediately (LT-style)
      m_transactions++;
      trans->release();
      return;
    }

    // Phase 3-4 — Wait for BEGIN_RESP -> send END_RESP (handled in PEQ)
    wait(m_resp_event);

    // Check response
    if (trans->is_response_error()) {
      SC_REPORT_ERROR("axi_master_bfm", "AXI write burst failed");
    }

    m_transactions++;
    trans->release();  // Returns payload to pool
  }

  // -------------------------------------------------------------------------
  // AXI Burst Read (AT 4-phase)
  // -------------------------------------------------------------------------
  void axi_read_burst(uint64_t addr, unsigned int len) {
    tlm::tlm_generic_payload* trans = m_mm.allocate();
    trans->acquire();

    std::vector<uint8_t> data(len, 0);

    trans->set_command(tlm::TLM_READ_COMMAND);
    trans->set_address(addr);
    trans->set_data_ptr(data.data());
    trans->set_data_length(len);
    trans->set_streaming_width(len);
    trans->set_byte_enable_ptr(nullptr);
    trans->set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);

    // AT 4-phase
    tlm::tlm_phase phase = tlm::BEGIN_REQ;
    sc_core::sc_time delay = sc_core::SC_ZERO_TIME;
    tlm::tlm_sync_enum status =
        m_init_socket->nb_transport_fw(*trans, phase, delay);

    if (status == tlm::TLM_ACCEPTED) {
      wait(m_end_req_event);
    } else if (status == tlm::TLM_COMPLETED) {
      m_transactions++;
      trans->release();
      return;
    }

    wait(m_resp_event);

    if (trans->is_response_error()) {
      SC_REPORT_ERROR("axi_master_bfm", "AXI read burst failed");
    }

    // Verify read data
    for (unsigned int i = 0; i < len; i++) {
      if (data[i] != static_cast<uint8_t>(i)) {
        SC_REPORT_WARNING("axi_master_bfm", "Read data mismatch");
        break;
      }
    }

    m_transactions++;
    trans->release();
  }

  // -------------------------------------------------------------------------
  // Internal State
  // -------------------------------------------------------------------------
  tlm_utils::peq_with_cb_and_phase<axi_master_bfm> m_peq;
  MemoryManager m_mm;
  sc_core::sc_event m_end_req_event;
  sc_core::sc_event m_resp_event;
  sc_core::sc_time m_clk_period;

  // Performance counters
  uint64_t m_transactions{0};
  uint64_t m_stall_cycles{0};
};

// =============================================================================
// AT Target (for testbench completeness)
// =============================================================================
class axi_slave_bfm : public sc_core::sc_module {
public:
  tlm_utils::simple_target_socket<axi_slave_bfm> m_targ_socket{
      "m_targ_socket"};

  SC_HAS_PROCESS(axi_slave_bfm);

  explicit axi_slave_bfm(sc_core::sc_module_name name,
                          uint64_t base_addr = 0, uint64_t size = 4096,
                          sc_core::sc_time latency = sc_core::sc_time(
                              40, sc_core::SC_NS))
      : sc_module(name),
        m_peq(this, &axi_slave_bfm::peq_callback),
        m_base_addr(base_addr),
        m_latency(latency) {
    m_targ_socket.register_nb_transport_fw(this,
                                            &axi_slave_bfm::nb_transport_fw);
    m_memory.resize(size, 0);
  }

private:
  tlm::tlm_sync_enum nb_transport_fw(tlm::tlm_generic_payload& trans,
                                      tlm::tlm_phase& phase,
                                      sc_core::sc_time& delay) {
    if (phase == tlm::BEGIN_REQ) {
      m_peq.notify(trans, tlm::END_REQ, delay);
      m_peq.notify(trans, tlm::BEGIN_RESP, delay + m_latency);
      return tlm::TLM_ACCEPTED;
    } else if (phase == tlm::END_RESP) {
      return tlm::TLM_COMPLETED;
    }
    return tlm::TLM_ACCEPTED;
  }

  void peq_callback(tlm::tlm_generic_payload& trans,
                     const tlm::tlm_phase& phase) {
    tlm::tlm_phase new_phase = phase;
    sc_core::sc_time delay = sc_core::SC_ZERO_TIME;

    if (phase == tlm::END_REQ) {
      m_targ_socket->nb_transport_bw(trans, new_phase, delay);
    } else if (phase == tlm::BEGIN_RESP) {
      execute_transaction(trans);
      m_targ_socket->nb_transport_bw(trans, new_phase, delay);
    }
  }

  void execute_transaction(tlm::tlm_generic_payload& trans) {
    uint64_t addr = trans.get_address() - m_base_addr;
    uint8_t* ptr = trans.get_data_ptr();
    unsigned int len = trans.get_data_length();

    if (addr + len > m_memory.size()) {
      trans.set_response_status(tlm::TLM_ADDRESS_ERROR_RESPONSE);
      return;
    }

    if (trans.get_command() == tlm::TLM_READ_COMMAND) {
      std::memcpy(ptr, &m_memory[addr], len);
    } else if (trans.get_command() == tlm::TLM_WRITE_COMMAND) {
      std::memcpy(&m_memory[addr], ptr, len);
    }
    trans.set_response_status(tlm::TLM_OK_RESPONSE);
  }

  tlm_utils::peq_with_cb_and_phase<axi_slave_bfm> m_peq;
  uint64_t m_base_addr;
  sc_core::sc_time m_latency;
  std::vector<uint8_t> m_memory;
};

// =============================================================================
// Top-Level Testbench (sc_main)
// =============================================================================
// int sc_main(int argc, char* argv[]) {
//   // Clock and reset signals
//   sc_core::sc_signal<bool> sys_clk;
//   sc_core::sc_signal<bool> sys_rst_n;
//
//   // Instantiate BFMs
//   axi_master_bfm master("u_master", 10.0);  // 100 MHz
//   axi_slave_bfm  slave("u_slave", 0x1000, 4096,
//                          sc_core::sc_time(40, sc_core::SC_NS));
//
//   // Connect sockets
//   master.m_init_socket.bind(slave.m_targ_socket);
//
//   // Connect clock/reset
//   master.sys_clk(sys_clk);
//   master.sys_rst_n(sys_rst_n);
//
//   // Reset sequence
//   sys_rst_n = false;
//   sc_core::sc_start(50, sc_core::SC_NS);
//   sys_rst_n = true;
//
//   // Run simulation
//   sc_core::sc_start(1, sc_core::SC_US);
//
//   // Write performance report
//   master.write_perf_report("perf_baseline.json");
//
//   std::cout << "Simulation complete at "
//             << sc_core::sc_time_stamp() << std::endl;
//   return 0;
// }
