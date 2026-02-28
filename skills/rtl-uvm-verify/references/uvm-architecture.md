# UVM Testbench Architecture Reference

## Standard UVM Component Hierarchy

```
uvm_test (top-level test)
  └── uvm_env (environment container)
        ├── uvm_agent (protocol agent - one per interface)
        │     ├── uvm_sequencer (stimulus routing)
        │     ├── uvm_driver (drives DUT signals)
        │     └── uvm_monitor (observes DUT signals)
        ├── uvm_scoreboard (reference model comparison)
        ├── uvm_coverage (functional coverage collector)
        └── uvm_agent (additional agents for other interfaces)
```

## Key UVM Base Classes

| Class | Purpose | Key Methods |
|-------|---------|-------------|
| `uvm_test` | Top-level test container | `build_phase()`, `run_phase()` |
| `uvm_env` | Environment container | `build_phase()`, `connect_phase()` |
| `uvm_agent` | Protocol agent (driver+monitor+sequencer) | `build_phase()`, `connect_phase()` |
| `uvm_driver` | Drives DUT signals | `run_phase()`, `get_next_item()`, `item_done()` |
| `uvm_monitor` | Observes DUT signals (passive) | `run_phase()`, analysis port writes |
| `uvm_sequencer` | Routes sequence items to driver | Automatic with `uvm_sequencer#(REQ)` |
| `uvm_sequence` | Generates stimulus transactions | `body()` task |
| `uvm_scoreboard` | Compares expected vs actual | Analysis port callbacks |

## UVM Phase Order

```
build_phase      → Create components (top-down)
connect_phase    → Connect ports/exports (bottom-up)
end_of_elaboration_phase
start_of_simulation_phase
run_phase        → Main simulation (parallel with below)
  ├── reset_phase
  ├── configure_phase
  ├── main_phase
  └── shutdown_phase
extract_phase
check_phase      → Auto-check scoreboard
report_phase     → Print coverage/results
```

## UVM Agent Template (Project Conventions)

```systemverilog
class my_agent extends uvm_agent;
  `uvm_component_utils(my_agent)

  my_driver    m_driver;     // m_ prefix per project convention (UVM class members)
  my_monitor   m_monitor;
  my_sequencer m_seqr;

  function new(string name, uvm_component parent);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    m_monitor = my_monitor::type_id::create("m_monitor", this);
    if (get_is_active() == UVM_ACTIVE) begin
      m_driver    = my_driver::type_id::create("m_driver", this);
      m_seqr = my_sequencer::type_id::create("m_seqr", this);
    end
  endfunction

  function void connect_phase(uvm_phase phase);
    if (get_is_active() == UVM_ACTIVE)
      m_driver.seq_item_port.connect(m_seqr.seq_item_export);
  endfunction
endclass
```

## Simulator Compile Commands

### Synopsys VCS
```bash
# Compile
vcs -full64 -sverilog -ntb_opts uvm-1.2 \
  +incdir+uvm/ rtl/*/*.sv uvm/*.sv \
  -timescale=1ns/1ps -o simv

# Run
./simv +UVM_TESTNAME=base_test +ntb_random_seed=42 \
  +UVM_VERBOSITY=UVM_MEDIUM -l run.log
```

### Siemens Questa
```bash
# Compile
vlog -sv +incdir+uvm rtl/*/*.sv uvm/*.sv
vopt +acc top_tb -o opt_tb

# Run
vsim -c opt_tb +UVM_TESTNAME=base_test +UVM_VERBOSITY=UVM_MEDIUM \
  -do "run -all; quit" -l run.log
```

### Cadence Xcelium
```bash
# Compile and run
xrun -sv -uvm -access +rwc \
  +incdir+uvm rtl/*/*.sv uvm/*.sv \
  +UVM_TESTNAME=base_test -seed 42 -l run.log
```

## UVM Coverage Best Practices

| Practice | Description |
|----------|-------------|
| Functional coverage in monitor | Sample covergroups in monitor's `write()` method |
| Cross coverage | Define crosses between protocol state and data values |
| Coverage callbacks | Use `uvm_subscriber` for analysis port coverage |
| Explicit bins | Define meaningful bins — avoid `auto_bin_max` |
| Coverage target | 95% functional, 90% code coverage before signoff |
| Per-test coverage | Merge coverage from all tests with different seeds |

## Common UVM Mistakes

1. **Not using factory creation**: Use `type_id::create()`, never `new()` directly
2. **Missing phase callbacks**: Forgetting `super.build_phase()` call
3. **Blocking in monitor**: Monitor should be passive — never drive signals
4. **Missing analysis ports**: Scoreboard/coverage not connected to monitor
5. **Hard-coded test names**: Use `+UVM_TESTNAME` for test selection
