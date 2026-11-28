# CDC constraint fragment. The project timing setup supplies clocks and units.
# Replace the example pins with registers resolved in the linked design.
# Cite the source for each physical bound and CDC exception.

# Vivado mixed crossing example: a bounded Gray pointer bus and a single-bit request
# share the same asynchronous clock pair. Keep the clock pair timed.
# set_max_delay -datapath_only {{GRAY_MAX_DELAY_NS}} \
#   -from [get_pins {u_fifo/wgray_reg*/C}] -to [get_pins {u_fifo/wgray_sync1_reg*/D}]
# set_false_path -from [get_pins u_req/req_reg/C] -to [get_pins u_req_sync/stage1_reg/D]

# Use set_clock_groups -asynchronous only for independently inventoried pairs
# where every crossing in both directions may be excluded. Keep the paths
# between synchronizer stages timed. Verify effective exceptions and individual
# bounded paths in the target STA tool with all project constraints loaded.
