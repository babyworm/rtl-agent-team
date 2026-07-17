# axi_stream_stub BFM — minimal SystemC TLM-2.0 build skeleton.
#
# PREREQUISITE: a local SystemC installation. This example is NOT built in
# CI (SystemC is not available there); run_bfm.py refuses to build it with
# a clear error unless SYSTEMC_HOME is exported:
#
#   export SYSTEMC_HOME=/path/to/systemc   # install root: include/ + lib*/
#
# run_bfm.py invokes `make` then `make run` with cwd set to this directory.

CXX      ?= g++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra
INCLUDES  = -I$(SYSTEMC_HOME)/include
LIBDIRS   = -L$(SYSTEMC_HOME)/lib -L$(SYSTEMC_HOME)/lib-linux64
LIBS      = -lsystemc

all: build/axi_stream_stub_bfm

build/axi_stream_stub_bfm: src/axi_stream_stub_bfm.cpp
	@mkdir -p build
	$(CXX) $(CXXFLAGS) $(INCLUDES) -o $@ src/axi_stream_stub_bfm.cpp $(LIBDIRS) $(LIBS)

run: all
	./build/axi_stream_stub_bfm > smoke_test_result.txt
	@cat smoke_test_result.txt

clean:
	rm -rf build smoke_test_result.txt

.PHONY: all run clean
