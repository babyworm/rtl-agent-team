// Yosys-compatible formal harness template for {{MODULE}}.
// Adapt the parameter and port list to match the DUT before running SBY.
//
// This OSS harness intentionally uses procedural immediate assert/assume/cover
// statements. Keep full concurrent SVA syntax, temporal operators, and bind
// files in `{{MODULE}}_props.sv` for commercial formal tools; do not send those
// assets through sv2v because formal semantics can be dropped.

module {{MODULE}}_formal_harness;
  parameter int unsigned DATA_WIDTH = 8;

  logic {{DOMAIN}}_clk;
  logic {{DOMAIN}}_rst_n;
  logic i_valid;
  logic o_ready;
  logic [DATA_WIDTH-1:0] i_data;
  logic [DATA_WIDTH-1:0] o_data;

  {{MODULE}} #(
    .DATA_WIDTH(DATA_WIDTH)
  ) dut (
    .{{DOMAIN}}_clk({{DOMAIN}}_clk),
    .{{DOMAIN}}_rst_n({{DOMAIN}}_rst_n),
    .i_valid(i_valid),
    .o_ready(o_ready),
    .i_data(i_data),
    .o_data(o_data)
  );

  initial {{DOMAIN}}_clk = 1'b0;
  always #1 {{DOMAIN}}_clk = !{{DOMAIN}}_clk;

  // Replace this marker with DUT-specific immediate assume/assert/cover
  // statements derived from requirements. Do not leave tautological checks in
  // place: the SBY template requires at least one real $check cell and stops
  // before solver execution when this harness has not been completed.
  // {{FORMAL_CHECKS}}
endmodule
