# selfcheck_fake_build — SystemC-free fixture for scripts/run_bfm.py.
#
# Exercises the wrapper's orchestration (build system detection, `make` +
# `make run` sequencing, artifact capture, JSON report) with plain-sh
# recipes only. Intentionally does NOT reference SYSTEMC_HOME so it runs
# anywhere make exists — this is how CI validates run_bfm.py without a
# SystemC installation. See ../axi_stream_stub/ for the real-BFM shape.

all:
	@mkdir -p build
	@printf '#!/bin/sh\necho "BFM smoke: PASS"\necho "transport=LT"\n' > build/fake_bfm
	@chmod +x build/fake_bfm

run: all
	@./build/fake_bfm > smoke_test_result.txt
	@cat smoke_test_result.txt

clean:
	rm -rf build smoke_test_result.txt

.PHONY: all run clean
