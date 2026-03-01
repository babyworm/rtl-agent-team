# CDC SDC Constraints Template
# Convention: {domain}_clk naming per CLAUDE.md
# Generate from: cdc-checker analysis of rtl/*/*.sv

# ============================================================
# Clock Definitions
# ============================================================
create_clock -name sys_clk  -period {{SYS_PERIOD_NS}}  [get_ports sys_clk]
# create_clock -name axi_clk  -period {{AXI_PERIOD_NS}}  [get_ports axi_clk]
# create_clock -name pixel_clk -period {{PIX_PERIOD_NS}} [get_ports pixel_clk]

# ============================================================
# Clock Groups (asynchronous domains)
# ============================================================
# set_clock_groups -asynchronous \
#   -group [get_clocks sys_clk] \
#   -group [get_clocks axi_clk]

# ============================================================
# False Paths (synchronized crossings)
# ============================================================
# 2-FF synchronizer paths — timing tool should not analyze these
# set_false_path -from [get_clocks sys_clk] -to [get_pins u_sync_*/d_ff1/D]

# ============================================================
# Max Delay Constraints (for gray code / handshake crossings)
# ============================================================
# Gray code bus: constrain to less than 1 destination clock period
# set_max_delay -from [get_pins u_gray_encoder/o_gray_*] \
#               -to [get_pins u_gray_decoder/i_gray_*] \
#               -datapath_only {{DEST_PERIOD_NS}}

# ============================================================
# Reset Synchronizer Constraints
# ============================================================
# set_false_path -from [get_ports sys_rst_n]
