# =============================================================================
# RTL Build System
# =============================================================================
# Open-source tools by default. Commercial EDA via _tool suffix.
#
#   make sim TOP=my_module        Simulate (verilator)
#   make lint                     Lint (verilator + verible + slang)
#   make syn TOP=my_module        Synthesize (yosys)
#   make formal TOP=my_module     Formal verify (SymbiYosys)
#   make help                     Show all targets
#
# Commercial tool examples:
#   make sim_xrun TOP=my_module   Simulate (Cadence Xcelium)
#   make lint_spyglass TOP=m      Lint (Synopsys SpyGlass)
#   make syn_dc TOP=my_module     Synthesize (Synopsys DC)
# =============================================================================

.DEFAULT_GOAL := help

# ─── Configuration ──────────────────────────────────────────────────────────
TOP         ?=
FILELIST    ?= rtl/filelist_top.f
BUILD_DIR   ?= build
LIBERTY     ?=
SBY_FILE    ?= sim/formal/$(TOP).sby
TB          ?=

# Script locations (deployed by rat-init-project)
LINT_SCRIPT := lint/scripts/run_lint.sh
SYN_SCRIPT  := syn/scripts/run_syn.sh
CDC_SCRIPT  := sim/cdc/run_cdc.sh

# ─── Internal helpers ───────────────────────────────────────────────────────
define _require_top
$(if $(TOP),,$(error TOP is required. Usage: make $(MAKECMDGOALS) TOP=<module>))
endef

_top_flag     = $(if $(TOP),--top $(TOP))
_liberty_flag = $(if $(LIBERTY),--liberty $(LIBERTY))

# Parse filelist for tools that don't support -f (iverilog)
# Falls back to globbing rtl/ if filelist is missing
_src_files = $(or $(shell grep -v '^\s*//' $(FILELIST) 2>/dev/null \
               | grep -v '^\s*+' | grep -v '^\s*$$'), \
               $(shell find rtl -name '*.sv' -o -name '*.v' 2>/dev/null | sort))

# =============================================================================
# Simulation — default: verilator
# =============================================================================
.PHONY: sim sim_verilator sim_iverilog sim_xrun sim_vcs

sim: sim_verilator

sim_verilator:
	$(call _require_top)
	@mkdir -p $(BUILD_DIR)/verilator
	verilator --binary -Wall -Wpedantic -sv \
	  --top-module $(TOP) -f $(FILELIST) $(TB) \
	  --Mdir $(BUILD_DIR)/verilator -o V$(TOP)
	$(BUILD_DIR)/verilator/V$(TOP)

sim_iverilog:
	$(call _require_top)
	@mkdir -p $(BUILD_DIR)
	iverilog -g2012 -I rtl/include \
	  -o $(BUILD_DIR)/$(TOP).vvp \
	  $(_src_files) $(TB)
	vvp $(BUILD_DIR)/$(TOP).vvp

sim_xrun:
	$(call _require_top)
	xrun -sv -64bit -top $(TOP) \
	  -f $(FILELIST) $(TB) \
	  -xmlibdirpath $(BUILD_DIR)/xcelium

sim_vcs:
	$(call _require_top)
	@mkdir -p $(BUILD_DIR)
	vcs -full64 -sverilog -top $(TOP) \
	  -f $(FILELIST) $(TB) \
	  -o $(BUILD_DIR)/simv
	$(BUILD_DIR)/simv

# =============================================================================
# Lint — default: verilator + verible + slang (all open-source)
# =============================================================================
.PHONY: lint lint_spyglass lint_xmvlog

lint:
	@echo "=== Running all open-source linters ==="
	-$(LINT_SCRIPT) --tool verilator -f $(FILELIST) $(_top_flag)
	-$(LINT_SCRIPT) --tool verible   -f $(FILELIST)
	-$(LINT_SCRIPT) --tool slang     -f $(FILELIST) $(_top_flag)

lint_spyglass:
	$(call _require_top)
	$(LINT_SCRIPT) --tool spyglass --top $(TOP) -f $(FILELIST)

lint_xmvlog:
	xmvlog -sv -f $(FILELIST)

# =============================================================================
# Synthesis — default: yosys
# =============================================================================
.PHONY: syn syn_dc syn_genus

syn:
	$(call _require_top)
	$(SYN_SCRIPT) --tool yosys --top $(TOP) -f $(FILELIST) $(_liberty_flag)

syn_dc:
	$(call _require_top)
	$(SYN_SCRIPT) --tool dc_shell --top $(TOP) -f $(FILELIST) $(_liberty_flag)

syn_genus:
	$(call _require_top)
	$(SYN_SCRIPT) --tool genus --top $(TOP) -f $(FILELIST) $(_liberty_flag)

# =============================================================================
# Formal Verification — default: SymbiYosys
# =============================================================================
.PHONY: formal formal_jasper formal_vcf

formal:
	$(call _require_top)
	sby -f $(SBY_FILE)

formal_jasper:
	$(call _require_top)
	$(if $(JASPER_TCL),,$(error JASPER_TCL required. Usage: make formal_jasper TOP=<m> JASPER_TCL=<tcl>))
	jg -batch $(JASPER_TCL)

formal_vcf:
	$(call _require_top)
	$(if $(VCF_TCL),,$(error VCF_TCL required. Usage: make formal_vcf TOP=<m> VCF_TCL=<tcl>))
	vcf -f $(VCF_TCL) -batch

# =============================================================================
# UVM Verification — commercial simulators only
# =============================================================================
.PHONY: uvm_compile uvm_run uvm_regression uvm_coverage

UVM_TEST    ?= base_test
UVM_SEEDS   ?= 42 123 456 789 1337
UVM_SIM     ?= vcs
UVM_TB_DIR  ?= sim/uvm
UVM_REG_SCRIPT := sim/uvm/scripts/run_regression_uvm.sh

uvm_compile:
	$(call _require_top)
	@echo "=== UVM Compile ($(UVM_SIM)) ==="
ifeq ($(UVM_SIM),vcs)
	vcs -full64 -sverilog -ntb_opts uvm-1.2 -cm line+cond+fsm+tgl+branch \
	  -timescale=1ns/1ps -f $(FILELIST) $(UVM_TB_DIR)/*.sv -o build/simv
else ifeq ($(UVM_SIM),xrun)
	xrun -sv -uvm -compile -coverage all -timescale 1ns/1ps \
	  -f $(FILELIST) $(UVM_TB_DIR)/*.sv -xmlibdirpath build/xcelium
else ifeq ($(UVM_SIM),questa)
	vlib build/work 2>/dev/null || true
	vlog -sv -work build/work +incdir+$(UVM_TB_DIR) -f $(FILELIST) $(UVM_TB_DIR)/*.sv
endif

uvm_run: uvm_compile
	$(call _require_top)
	@echo "=== UVM Run: $(UVM_TEST) ==="
ifeq ($(UVM_SIM),vcs)
	build/simv +UVM_TESTNAME=$(UVM_TEST) +ntb_random_seed=42 \
	  -cm line+cond+fsm+tgl+branch -cm_dir sim/uvm/coverage/seed_42.vdb
else ifeq ($(UVM_SIM),xrun)
	xrun -sv -uvm -R +UVM_TESTNAME=$(UVM_TEST) -seed 42 -coverage all \
	  -xmlibdirpath build/xcelium
else ifeq ($(UVM_SIM),questa)
	vsim -c -work build/work -coverage +UVM_TESTNAME=$(UVM_TEST) -sv_seed 42 \
	  -do "coverage save -onexit sim/uvm/coverage/seed_42.ucdb; run -all; quit -f" tb_top
endif

uvm_regression:
	$(call _require_top)
	$(UVM_REG_SCRIPT) --sim $(UVM_SIM) --seeds "$(UVM_SEEDS)" \
	  --test $(UVM_TEST) --module $(TOP) --filelist $(FILELIST)

uvm_coverage:
	@echo "=== UVM Coverage Report ==="
ifeq ($(UVM_SIM),vcs)
	urg -dir sim/uvm/coverage/*.vdb -report sim/uvm/coverage/report -format text
else ifeq ($(UVM_SIM),questa)
	vcover merge sim/uvm/coverage/merged.ucdb sim/uvm/coverage/seed_*.ucdb
	vcover report -details sim/uvm/coverage/merged.ucdb
endif

# =============================================================================
# CDC Analysis — default: structural + slang-cdc
# =============================================================================
.PHONY: cdc cdc_spyglass

cdc:
	$(call _require_top)
	$(CDC_SCRIPT) --tool structural --top $(TOP) -f $(FILELIST)

cdc_spyglass:
	$(call _require_top)
	$(CDC_SCRIPT) --tool spyglass --top $(TOP) -f $(FILELIST)

# =============================================================================
# Utility
# =============================================================================
.PHONY: help clean

help:
	@echo ""
	@echo "RTL Build System"
	@echo "════════════════"
	@echo ""
	@echo "  Simulation (default: verilator)"
	@echo "    sim               Verilator"
	@echo "    sim_iverilog      Icarus Verilog"
	@echo "    sim_xrun          Cadence Xcelium"
	@echo "    sim_vcs           Synopsys VCS"
	@echo ""
	@echo "  Lint (default: all open-source)"
	@echo "    lint              Verilator + Verible + slang"
	@echo "    lint_spyglass     Synopsys SpyGlass"
	@echo "    lint_xmvlog       Cadence xmvlog (compile-check)"
	@echo ""
	@echo "  Synthesis (default: yosys)"
	@echo "    syn               Yosys"
	@echo "    syn_dc            Synopsys Design Compiler"
	@echo "    syn_genus         Cadence Genus"
	@echo ""
	@echo "  Formal Verification (default: SymbiYosys)"
	@echo "    formal            SymbiYosys"
	@echo "    formal_jasper     Cadence JasperGold"
	@echo "    formal_vcf        Synopsys VC Formal"
	@echo ""
	@echo "  UVM Verification (commercial simulators)"
	@echo "    uvm_compile       Compile UVM environment"
	@echo "    uvm_run           Single test run (UVM_TEST=name)"
	@echo "    uvm_regression    Multi-seed regression (UVM_SEEDS=\"...\")"
	@echo "    uvm_coverage      Merge and report coverage"
	@echo ""
	@echo "  CDC Analysis"
	@echo "    cdc               structural + slang-cdc"
	@echo "    cdc_spyglass      Synopsys SpyGlass CDC"
	@echo ""
	@echo "  Utility"
	@echo "    help              Show this help"
	@echo "    clean             Remove build artifacts"
	@echo ""
	@echo "  Variables:"
	@echo "    TOP=<module>      Top-level module (required for sim/syn/formal)"
	@echo "    FILELIST=<.f>     Source filelist (default: rtl/filelist_top.f)"
	@echo "    TB=<file>         Testbench file"
	@echo "    LIBERTY=<.lib>    Liberty file for technology mapping"
	@echo "    SBY_FILE=<.sby>   SymbiYosys config (default: sim/formal/\$$TOP.sby)"
	@echo "    JASPER_TCL=<tcl>  JasperGold script"
	@echo "    VCF_TCL=<tcl>     VC Formal script"
	@echo "    UVM_SIM=<sim>     UVM simulator: vcs|xrun|questa (default: vcs)"
	@echo "    UVM_TEST=<name>   UVM test name (default: base_test)"
	@echo "    UVM_SEEDS=\"...\"   Seed list for regression (default: 42 123 456 789 1337)"
	@echo ""
	@echo "  Examples:"
	@echo "    make sim TOP=entropy_coder"
	@echo "    make sim TOP=entropy_coder TB=sim/entropy_coder/tb_entropy_coder.sv"
	@echo "    make lint"
	@echo "    make lint TOP=entropy_coder"
	@echo "    make syn TOP=entropy_coder LIBERTY=lib/sky130_fd_sc_hd.lib"
	@echo "    make sim_xrun TOP=entropy_coder"
	@echo ""

clean:
	rm -rf $(BUILD_DIR) lint/reports syn/reports
	@echo "Cleaned: $(BUILD_DIR)/ lint/reports/ syn/reports/"
