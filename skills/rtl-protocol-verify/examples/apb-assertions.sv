// Example: APB3 Protocol Assertions (slave perspective)
// Convention: i_/o_ prefix, sys_clk, sys_rst_n

module apb3_slave_assertions (
  input logic sys_clk,
  input logic sys_rst_n,
  input logic i_psel,
  input logic i_penable,
  input logic i_pwrite,
  input logic [31:0] i_paddr,
  input logic [31:0] i_pwdata,
  input logic [31:0] o_prdata,
  input logic o_pready,
  input logic o_pslverr
);

  // APB FSM states
  typedef enum logic [1:0] {
    ST_IDLE   = 2'b00,
    ST_SETUP  = 2'b01,
    ST_ACCESS = 2'b10
  } apb_state_e;

  // APB-1: PSEL must assert one cycle before PENABLE (setup phase)
  setup_before_access: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (i_psel && !i_penable) |=> i_penable
  ) else $error("APB: PENABLE not asserted after PSEL setup phase");

  // APB-2: Address stable during entire transfer
  addr_stable: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (i_psel && i_penable && !o_pready) |=> $stable(i_paddr)
  ) else $error("APB: i_paddr changed during transfer");

  // APB-3: Write data stable during transfer
  wdata_stable: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (i_psel && i_penable && i_pwrite && !o_pready) |=> $stable(i_pwdata)
  ) else $error("APB: i_pwdata changed during write transfer");

  // APB-4: PWRITE stable during transfer
  pwrite_stable: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (i_psel && i_penable && !o_pready) |=> $stable(i_pwrite)
  ) else $error("APB: i_pwrite changed during transfer");

  // APB-5: PSEL must remain high during access phase
  psel_hold: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (i_psel && i_penable && !o_pready) |=> i_psel
  ) else $error("APB: i_psel dropped during access phase");

  // APB-6: No X on read data when valid read completes
  rdata_no_x: assert property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    (i_psel && i_penable && !i_pwrite && o_pready) |-> !$isunknown(o_prdata)
  ) else $error("APB: o_prdata contains X/Z on read completion");

  // Cover: successful write
  write_complete: cover property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    i_psel && i_penable && i_pwrite && o_pready
  );

  // Cover: successful read
  read_complete: cover property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    i_psel && i_penable && !i_pwrite && o_pready
  );

  // Cover: slave error response
  slave_error: cover property (
    @(posedge sys_clk) disable iff (!sys_rst_n)
    i_psel && i_penable && o_pready && o_pslverr
  );

endmodule
