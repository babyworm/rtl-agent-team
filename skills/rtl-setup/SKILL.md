---
name: rtl-setup
description: "This skill should be used when initializing a new RTL project, setting up directory structure, or verifying EDA toolchain installation. Triggers on 'setup', 'initialize', 'init project'."
---

<Purpose>
Set up a new RTL design project with the standard directory structure required by this plugin,
and verify that required EDA tools are installed and accessible.
</Purpose>

<Use_When>
- Starting a new RTL/FPGA/ASIC design project
- First time using this plugin in a workspace
- Verifying EDA toolchain is properly installed
- User says "setup", "initialize", "init project", "프로젝트 초기화"
</Use_When>

<Do_Not_Use_When>
- Project directories already exist and tools are verified
- Only need to run a specific EDA tool (use the tool-specific skill)
- Designing architecture or writing RTL (use arch-design or rtl-code)
</Do_Not_Use_When>

<Why_This_Exists>
The 5-Phase pipeline expects a standard directory layout (specs/, rtl/src/, tb/, ref_model/, etc.)
and depends on EDA CLI tools (Verilator, Yosys, cocotb, etc.) being available.
Without proper setup, agents fail with missing directory or tool-not-found errors.
This skill ensures everything is in place before design work begins.
</Why_This_Exists>

<Execution_Policy>
- Non-destructive: never overwrite existing files or directories
- Report tool status honestly: installed version or "NOT FOUND" with install instructions
- Create only the directories that don't already exist
- Generate a setup report at the end
</Execution_Policy>

<Steps>
1. **Check project root**: Verify current directory is suitable (has .git or is empty).

2. **Create directory structure** (skip existing):
   ```
   specs/              # Input specifications and datasheets
   rtl/
     src/              # Synthesizable SystemVerilog source
     include/          # Shared headers and packages
   tb/
     unit/             # SV unit tests
     cocotb/           # cocotb Python testbenches
   ref_model/
     src/              # C/C++ reference model source
     build/            # Reference model build output
   uarch/              # Micro-architecture documents
   bfm/                # Bus Functional Models
   formal/             # SymbiYosys .sby configurations
   synth/              # Synthesis scripts and reports
   docs/               # Design documentation
   reviews/            # Phase gate 리뷰 리포트 (Markdown)
     phase-1-research/
     phase-2-architecture/
     phase-3-uarch/
     phase-4-rtl/
     phase-5-verify/
   .rtl-agent-team/
     state/            # Plugin state files (auto-managed)
   ```

3. **Check EDA tool availability** (via `which` or `--version`):

   | Tool | Check Command | Purpose | Required |
   |------|--------------|---------|----------|
   | verilator | `verilator --version` | Simulation + Lint | Yes |
   | iverilog | `iverilog -V` | Alternative simulator | Optional |
   | yosys | `yosys --version` | Synthesis | Yes |
   | sby | `sby --help` | Formal verification | Optional |
   | cocotb | `python3 -c "import cocotb; print(cocotb.__version__)"` | Functional verification | Yes |
   | slang | `slang --version` | Advanced lint | Optional |
   | gtkwave | `gtkwave --version` | Waveform viewer | Optional |
   | python3 | `python3 --version` | cocotb runtime | Yes |
   | gcc/g++ | `g++ --version` | Reference model build | Yes |
   | make | `make --version` | Build system | Yes |

4. **Generate filelist template** (if rtl/src/ is empty):
   Create `rtl/filelist.f` with comment explaining format.

5. **Generate cocotb Makefile template** (if tb/cocotb/ is empty):
   Create `tb/cocotb/Makefile` with standard cocotb make targets.

6. **Generate module template** (if rtl/src/ is empty):
   Create `rtl/src/template_module.sv` demonstrating project naming conventions:
   ```systemverilog
   // template_module.sv — Template demonstrating project coding conventions
   // Style: lowRISC SV Style Guide + project overrides (i_/o_ prefix, {domain}_clk/rst_n)
   module template_module
     import template_module_pkg::*;
   #(
     parameter int DATA_WIDTH = 32
   ) (
     input  logic                  sys_clk,       // Clock: {domain}_clk format
     input  logic                  sys_rst_n,     // Reset: {domain}_rst_n format
     input  logic [DATA_WIDTH-1:0] i_data,        // Input: i_ prefix
     input  logic                  i_valid,       // Input: i_ prefix
     output logic [DATA_WIDTH-1:0] o_result,      // Output: o_ prefix
     output logic                  o_ready        // Output: o_ prefix
   );
     // Use logic only (no reg/wire), typedef enum for FSM, u_ instance prefix, gen_ generate prefix
   endmodule
   ```

7. **Report setup summary**:
   ```
   ## RTL Project Setup Report
   - Directory structure: [N] directories created, [M] already existed
   - Required tools: [X/Y] installed
   - Optional tools: [A/B] installed
   - Missing required: [list with install commands]
   - Coding conventions: lowRISC SV Style + project overrides
     - Port prefix: i_/o_/io_ (NOT suffix _i/_o)
     - Clock: {domain}_clk (e.g., sys_clk)
     - Reset: {domain}_rst_n (e.g., sys_rst_n)
   - Ready to start: Yes/No
   ```
</Steps>

<Tool_Usage>
```
# Directory creation (Bash CLI)
Bash: mkdir -p specs rtl/src rtl/include tb/unit tb/cocotb ref_model/src ref_model/build uarch bfm formal synth docs reviews/phase-{1-research,2-architecture,3-uarch,4-rtl,5-verify} .rtl-agent-team/state

# Tool checks via Bash CLI (run in parallel, NOT MCP)
Bash: verilator --version 2>&1 || echo "NOT_FOUND"
Bash: yosys --version 2>&1 || echo "NOT_FOUND"
Bash: python3 -c "import cocotb; print(cocotb.__version__)" 2>&1 || echo "NOT_FOUND"
Bash: slang --version 2>&1 || echo "NOT_FOUND"
Bash: g++ --version 2>&1 || echo "NOT_FOUND"

# Template generation
Write: rtl/filelist.f          — filelist with format comment
Write: tb/cocotb/Makefile      — standard cocotb targets
Write: rtl/src/template_module.sv — convention reference template (i_/o_ prefix, sys_clk/sys_rst_n)
```

**All EDA tools are executed via Bash CLI directly. No MCP tool servers for EDA.**
</Tool_Usage>

<Examples>
<Good>
User: "새 FPGA 프로젝트를 시작하려고 해"
→ Run rtl-setup. Create directories, check tools, report what's missing.

User: "setup" or "rtl-setup"
→ Same as above.
</Good>
<Bad>
User: "AXI slave 모듈을 만들어줘"
→ Do NOT run rtl-setup. Use rtl-code skill directly.
</Bad>
</Examples>

<Install_Instructions>
When tools are missing, provide these installation commands:

```bash
# Ubuntu/Debian
sudo apt install verilator yosys iverilog gtkwave build-essential python3-pip
pip3 install cocotb

# macOS (Homebrew)
brew install verilator yosys icarus-verilog gtkwave
pip3 install cocotb

# SymbiYosys (from source)
# See: https://symbiyosys.readthedocs.io/en/latest/install.html

# slang (from source or package)
# See: https://sv-lang.com
```
</Install_Instructions>

<Final_Checklist>
- [ ] All required directories exist
- [ ] Tool availability checked via Bash CLI and reported
- [ ] Missing tools listed with install instructions
- [ ] Template files created for empty directories
- [ ] Module template (rtl/src/template_module.sv) demonstrates naming conventions
- [ ] Setup report includes coding convention summary (i_/o_ prefix, {domain}_clk/{domain}_rst_n)
- [ ] Setup report displayed to user
</Final_Checklist>
