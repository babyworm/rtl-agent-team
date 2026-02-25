// Example: UVM Scoreboard with Reference Model Comparison
// Convention: u_ instance prefix

class example_scoreboard extends uvm_scoreboard;
  `uvm_component_utils(example_scoreboard)

  uvm_analysis_imp #(example_seq_item, example_scoreboard) analysis_export;

  // Internal reference model state
  int unsigned expected_queue[$];
  int pass_count;
  int fail_count;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    analysis_export = new("analysis_export", this);
    pass_count = 0;
    fail_count = 0;
  endfunction

  // Called by monitor when DUT produces output
  function void write(example_seq_item item);
    int unsigned expected;

    if (expected_queue.size() == 0) begin
      `uvm_error("SCB", $sformatf("Unexpected output: %0h", item.data))
      fail_count++;
      return;
    end

    expected = expected_queue.pop_front();

    if (item.data !== expected) begin
      `uvm_error("SCB", $sformatf(
        "Mismatch: got=%0h, expected=%0h", item.data, expected))
      fail_count++;
    end else begin
      `uvm_info("SCB", $sformatf("Match: %0h", item.data), UVM_HIGH)
      pass_count++;
    end
  endfunction

  // Add expected values (called by input monitor or reference model)
  function void add_expected(int unsigned value);
    expected_queue.push_back(value);
  endfunction

  function void report_phase(uvm_phase phase);
    `uvm_info("SCB", $sformatf(
      "Scoreboard: %0d passed, %0d failed, %0d remaining in queue",
      pass_count, fail_count, expected_queue.size()), UVM_LOW)

    if (fail_count > 0 || expected_queue.size() > 0)
      `uvm_error("SCB", "Scoreboard check FAILED")
    else
      `uvm_info("SCB", "Scoreboard check PASSED", UVM_LOW)
  endfunction
endclass
