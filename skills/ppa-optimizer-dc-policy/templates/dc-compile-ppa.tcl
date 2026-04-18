# dc-compile-ppa.tcl — Design Compiler PPA-oriented compile fragment
# Applied by run_syn.sh --tool dc_shell when PPA-Opt loop is active.
# Intent: timing-first optimization with aggressive clock gating + leakage minimization.

# Clock gating strategy — latch-based ICG with fanout cap
set_clock_gating_style \
    -sequential_cell latch \
    -minimum_bitwidth 3 \
    -max_fanout 32 \
    -positive_edge_logic {integrated} \
    -control_point before \
    -control_signal scan_enable

# Compile strategy — ultra with retiming + scan-aware + clock gate insertion
compile_ultra \
    -timing \
    -gate_clock \
    -scan \
    -retime \
    -no_seq_output_inversion

# Leakage power optimization (post-compile incremental)
set_power_opt -leakage

# Additional reports to enable PPA analysis
report_clock_gating -verbose > syn/rpt/clock_gating.rpt
# Emit BOTH flat summary AND hierarchical breakdown in the same report
# (the parser extracts both sections).
report_power -analysis_effort high > syn/rpt/power.rpt
report_power -hier -hier_level 2 >> syn/rpt/power.rpt
report_threshold_voltage_group > syn/rpt/vt.rpt
report_timing -max_paths 10 -delay_type max > syn/rpt/timing.rpt
report_area -hier > syn/rpt/area.rpt
report_qor > syn/rpt/qor.rpt
