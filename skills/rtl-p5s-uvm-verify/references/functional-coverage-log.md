# Functional bin logs

Export hit counts for the test plan's required bins. In a UVM coverage subscriber,
increment the counters where `write()` samples the corresponding covergroup. Export
the counts once in `report_phase`. For example, for a command coverpoint with `read`
and `write` bins and `at_least=2` for both:

```systemverilog
longint unsigned m_read_hits = 0, m_write_hits = 0;

// Use the same command and sampling condition as the coverpoint.
function void sample_request(logic cmd);
  if (cmd === 1'b0) m_read_hits++;
  if (cmd === 1'b1) m_write_hits++;
endfunction

function void report_phase(uvm_phase phase);
  super.report_phase(phase);
  $display("RAT_COV_BIN tb.req.cmd.read %0d 2", m_read_hits);
  $display("RAT_COV_BIN tb.req.cmd.write %0d 2", m_write_hits);
  $display("RAT_COV_END 2");
endfunction
```

The runner captures these lines in each seed's `sim.log`. Each seed emits the same
bin IDs and minimum hits, including zero-hit bins. Use unique IDs across instances
and cross bins. Emit one end record with the total number of bin records after all
collectors have exported. Merge uses summed hits and reports the percentage of
exported bins meeting their minimum. The report link and seed log paths are relative
to the project root when stored inside the project. Vendor weighting, exclusions, and code metrics
are outside this measurement. Covergroup totals from `get_coverage()` and existing
logs without bin hit counts provide insufficient data to merge.

For an already-passing regression, the merger can also read the seed logs directly:

```bash
python3 lib/merge_coverpoint_logs.py --output sim/uvm/coverage/functional.json \
  sim/uvm/regression/run_TIMESTAMP/seed_{42,43}/sim.log
```
