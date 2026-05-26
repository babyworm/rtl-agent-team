# dc-compile-ppa.tcl — Design Compiler PPA-oriented compile fragment
# Applied by run_syn.sh --tool dc_shell when PPA-Opt loop is active.
# Intent: timing-first optimization with aggressive clock gating + leakage minimization.

# Report dir as a VARIABLE (not a hardcoded relative path) so the report paths
# never drift from the actual run dir / CWD. run_syn.sh `cd`s into $SYN_ROOT, so a
# hardcoded "syn/rpt/..." here would resolve to "<syn>/syn/rpt". The harness sets
# `rpt_dir` (absolute or run-dir-relative); default preserves the repo-root layout.
if {![info exists rpt_dir]} { set rpt_dir "syn/rpt" }

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
report_clock_gating -verbose > $rpt_dir/clock_gating.rpt
# Emit BOTH flat summary AND hierarchical breakdown in the same report
# (the parser extracts both sections).
report_power -analysis_effort high > $rpt_dir/power.rpt
report_power -hier -hier_level 2 >> $rpt_dir/power.rpt
report_threshold_voltage_group > $rpt_dir/vt.rpt
report_timing -max_paths 10 -delay_type max > $rpt_dir/timing.rpt
report_area -hier > $rpt_dir/area.rpt
report_qor > $rpt_dir/qor.rpt
