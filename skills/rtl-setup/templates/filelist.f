// RTL Source Filelist
// Usage: -f rtl/filelist.f (verilator/vcs/xrun/questa) or parsed by run_sim.sh (iverilog)
// Convention: packages first, then modules in dependency order
//
// run_sim.sh handles simulator differences automatically:
//   - iverilog: +incdir+ converted to -I, files read inline
//   - verilator/vcs/xrun/questa: passed as -f directly

+incdir+rtl/include

// --- Packages ---
// rtl/include/project_pkg.sv

// --- Common utility modules (ICG, synchronizer, CDC primitives) ---
// rtl/common/icg.sv
// rtl/common/sync_2ff.sv

// --- Leaf modules (no dependencies) ---
// rtl/module_a/module_a_sub1.sv
// rtl/module_a/module_a_sub2.sv
// rtl/module_a/module_a_top.sv
// rtl/module_b/module_b_top.sv

// --- Mid-level modules ---
// rtl/module_c/module_c_top.sv

// --- Top-level ---
// rtl/top/top_module.sv
