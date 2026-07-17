// axi_stream_stub_bfm.cpp — minimal SystemC TLM-2.0 LT BFM skeleton.
//
// Runnable shape for scripts/run_bfm.py. Requires a local SystemC install
// (SYSTEMC_HOME); NOT compiled in CI. Demonstrates the smallest useful BFM:
// one target SC_MODULE with an LT blocking transport handler, driven by a
// stub initiator that pushes a single write transaction end-to-end and
// prints a smoke_test_result.txt-shaped verdict (see bfm-conventions.md).
//
// A production BFM adds amba_pv AXI extensions, a Memory Manager
// (tlm_mm_interface), and per-block perf_baseline.json capture — see
// templates/bfm_module_template.h.

#include <cstdint>
#include <cstdio>

#include <systemc>
#include <tlm>
#include <tlm_utils/simple_initiator_socket.h>
#include <tlm_utils/simple_target_socket.h>

// LT target: accepts every transaction with a fixed 10 ns latency.
SC_MODULE(AxiStreamStubBfm) {
    tlm_utils::simple_target_socket<AxiStreamStubBfm> t_sock;

    SC_CTOR(AxiStreamStubBfm) : t_sock("t_sock") {
        t_sock.register_b_transport(this, &AxiStreamStubBfm::b_transport);
    }

    void b_transport(tlm::tlm_generic_payload &trans,
                     sc_core::sc_time &delay) {
        delay += sc_core::sc_time(10, sc_core::SC_NS);
        trans.set_response_status(tlm::TLM_OK_RESPONSE);
    }
};

// Stub initiator: one LT write, then verdict.
SC_MODULE(StubInitiator) {
    tlm_utils::simple_initiator_socket<StubInitiator> i_sock;

    SC_CTOR(StubInitiator) : i_sock("i_sock") {
        SC_THREAD(drive);
    }

    void drive() {
        uint8_t payload_data[4] = {0xDE, 0xAD, 0xBE, 0xEF};
        tlm::tlm_generic_payload trans;
        sc_core::sc_time delay = sc_core::SC_ZERO_TIME;

        trans.set_command(tlm::TLM_WRITE_COMMAND);
        trans.set_address(0x0);
        trans.set_data_ptr(payload_data);
        trans.set_data_length(4);
        trans.set_streaming_width(4);
        trans.set_response_status(tlm::TLM_INCOMPLETE_RESPONSE);

        i_sock->b_transport(trans, delay);

        const bool ok = trans.is_response_ok();
        std::printf("%s\n", ok ? "PASS" : "FAIL");
        std::printf("transport=LT\n");
        std::printf("latency=%.0fns\n", delay.to_seconds() * 1e9);
        std::printf("transactions=1\n");
        if (!ok) {
            sc_core::sc_stop();
        }
    }
};

int sc_main(int, char **) {
    AxiStreamStubBfm u_bfm("u_bfm");
    StubInitiator u_init("u_init");
    u_init.i_sock.bind(u_bfm.t_sock);

    sc_core::sc_start();
    return 0;
}
