#!/usr/bin/env bash
# Claude runs this in a new workspace before the first turn.
set -eu
plugin_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
bash "$plugin_root/skills/rat-init-project/scripts/install_project_templates.sh" "$PWD" >/dev/null
mkdir -p rtl sim docs/phase-3-uarch .rat/state
cat >rat_config.json <<'EOF'
{"project":{"name":"incrementer","top_module":"incrementer"},"execution":{"backend":"local"},"preferences":{"simulator":"iverilog"},"verification":{"stop_gate":"block"}}
EOF
cat >docs/phase-3-uarch/incrementer.md <<'EOF'
REQ-U-001. The four-bit output is the four-bit input plus one, modulo sixteen.
For input four, the required output is five. The supplied unit bench checks this vector.
EOF
cat >rtl/incrementer.sv <<'EOF'
module incrementer(input logic [3:0] i_value, output logic [3:0] o_value);
  assign o_value = i_value + 4'd1;
endmodule
EOF
cat >sim/tb_incrementer.sv <<'EOF'
module tb_incrementer;
  logic [3:0] value;
  incrementer u_dut(.i_value(4'd4), .o_value(value));
  initial begin
    #5;
    $display("REQ-U-001 expected=5 actual=%0d", value);
    if (value !== 4'd5) $fatal(1, "RAT_SIM_FAIL incrementer mismatch");
    $display("RAT_SIM_PASS");
    $finish;
  end
endmodule

module smoke;
  initial begin
    #1;
    $display("RAT_SIM_PASS unrelated smoke");
    $finish;
  end
endmodule
EOF
printf '%s\n' rtl/incrementer.sv sim/tb_incrementer.sv > sources.f
