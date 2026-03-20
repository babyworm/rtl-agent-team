/**
 * {{MODULE_NAME}}_bfm.h — SystemC TLM-2.0 Bus Functional Model
 *
 * AT (Approximately-Timed) non-blocking transport for cycle-approximate simulation.
 * Implements timing-annotated behavior matching Phase 3 uArch specification.
 *
 * Build: g++ -std=c++17 -I${SYSTEMC_HOME}/include -L${SYSTEMC_HOME}/lib-linux64
 *        -lsystemc -ltlm -o bfm_{{MODULE_NAME}} bfm_{{MODULE_NAME}}.cpp
 */

#ifndef {{MODULE_NAME_UPPER}}_BFM_H
#define {{MODULE_NAME_UPPER}}_BFM_H

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_initiator_socket.h>
#include <tlm_utils/simple_target_socket.h>
#include <tlm_utils/peq_with_cb_and_phase.h>

/**
 * {{MODULE_NAME}}_bfm — TLM-2.0 AT model
 *
 * Ports:
 *   i_socket: target socket (receives transactions from upstream)
 *   o_socket: initiator socket (sends transactions downstream)
 *
 * Timing:
 *   Processing latency: {{LATENCY}} clock cycles (from uArch spec)
 *   Pipeline stages: {{STAGES}}
 */
SC_MODULE({{MODULE_NAME}}_bfm)
{
    // ─── TLM Sockets ────────────────────────────────────────────────────
    tlm_utils::simple_target_socket<{{MODULE_NAME}}_bfm>    i_socket;
    tlm_utils::simple_initiator_socket<{{MODULE_NAME}}_bfm> o_socket;

    // ─── Configuration ──────────────────────────────────────────────────
    sc_core::sc_time clk_period;
    int processing_latency;  // cycles

    // ─── PEQ for AT timing ──────────────────────────────────────────────
    tlm_utils::peq_with_cb_and_phase<{{MODULE_NAME}}_bfm> m_peq;

    SC_CTOR({{MODULE_NAME}}_bfm)
        : i_socket("i_socket")
        , o_socket("o_socket")
        , clk_period({{CLK_PERIOD_NS}}, sc_core::SC_NS)
        , processing_latency({{LATENCY}})
        , m_peq(this, &{{MODULE_NAME}}_bfm::peq_cb)
    {
        i_socket.register_nb_transport_fw(this, &{{MODULE_NAME}}_bfm::nb_transport_fw);
        o_socket.register_nb_transport_bw(this, &{{MODULE_NAME}}_bfm::nb_transport_bw);
    }

    // ─── AT Non-Blocking Forward Path ───────────────────────────────────
    tlm::tlm_sync_enum nb_transport_fw(
        tlm::tlm_generic_payload &trans,
        tlm::tlm_phase           &phase,
        sc_core::sc_time         &delay)
    {
        if (phase == tlm::BEGIN_REQ) {
            // Accept request, schedule processing
            delay += clk_period * processing_latency;
            m_peq.notify(trans, tlm::END_REQ, delay);
            return tlm::TLM_ACCEPTED;
        }
        return tlm::TLM_ACCEPTED;
    }

    // ─── AT Non-Blocking Backward Path ──────────────────────────────────
    tlm::tlm_sync_enum nb_transport_bw(
        tlm::tlm_generic_payload &trans,
        tlm::tlm_phase           &phase,
        sc_core::sc_time         &delay)
    {
        (void)trans; (void)phase; (void)delay;
        /* TODO: Handle downstream backpressure */
        return tlm::TLM_ACCEPTED;
    }

    // ─── PEQ Callback (timing engine) ───────────────────────────────────
    void peq_cb(tlm::tlm_generic_payload &trans, const tlm::tlm_phase &phase)
    {
        if (phase == tlm::END_REQ) {
            /* TODO: Process transaction data here
             *
             * 1. Read input data: trans.get_data_ptr(), trans.get_data_length()
             * 2. Apply algorithm (matching ref-model behavior)
             * 3. Write output data back to transaction
             * 4. Forward to downstream via o_socket
             */

            // Log per-block I/O for BFM-vs-refC validation
            // SC_REPORT_INFO("BFM", sc_core::sc_time_stamp().to_string() + ": processed");

            trans.set_response_status(tlm::TLM_OK_RESPONSE);
            tlm::tlm_phase resp_phase = tlm::BEGIN_RESP;
            sc_core::sc_time resp_delay = sc_core::SC_ZERO_TIME;
            i_socket->nb_transport_bw(trans, resp_phase, resp_delay);
        }
    }

    // ─── Performance Baseline Output ────────────────────────────────────
    /* TODO: At end_of_simulation(), write perf_baseline.json:
     * {
     *   "module": "{{MODULE_NAME}}",
     *   "latency_cycles": processing_latency,
     *   "throughput_txn_per_sec": measured_throughput,
     *   "total_transactions": txn_count
     * }
     */
};

#endif // {{MODULE_NAME_UPPER}}_BFM_H
