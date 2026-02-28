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
- User says "setup", "initialize", "init project", "project init"
- User says "docker image", "make docker", "EDA environment container"
</Use_When>

<Do_Not_Use_When>
- Project directories already exist and tools are verified
- Only need to run a specific EDA tool (use the tool-specific skill)
- Designing architecture or writing RTL (use arch-design or rtl-code)
</Do_Not_Use_When>

<Why_This_Exists>
The 6-Phase pipeline expects a standard directory layout (rtl/, refc/, bfm/, sim/, lint/, syn/, etc.)
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
   refc/               # C reference model (DPI-C compatible)
     include/          # Common ref model headers
     build/            # Build output (.so for DPI-C)
   bfm/                # Bus Functional Models
     include/          # Common BFM headers
   rtl/                # Synthesizable SystemVerilog source
     common/           # Shared utility modules (ICG, synchronizer, CDC primitives)
     include/          # Common defines, packages
     top/              # Top-level module instantiation
   sim/                # Simulation & testbenches
     top/              # Tier 4: integration tests
     formal/           # SVA formal verification (.sby configs)
   lint/               # Lint flow
     scripts/          # Lint scripts (run_lint.sh)
     reports/          # Per-module lint results
   syn/                # Synthesis flow
     scripts/          # Synthesis scripts (run_syn.sh)
     reports/          # Per-module synthesis results
   docs/               # Design documentation
     phase-1-research/   # Phase 1 artifacts
     phase-2-architecture/ # Phase 2 artifacts
     phase-3-uarch/      # Phase 3 artifacts
     phase-4-rtl/        # Phase 4 artifacts
     phase-5-verify/     # Phase 5 artifacts
     decisions/          # Architecture Decision Records (ADR)
   reviews/            # Phase gate review reports (Markdown)
     phase-1-research/
     phase-2-architecture/
     phase-3-uarch/
     phase-4-rtl/
     phase-5-verify/
     phase-6-review/    # Phase 6 review deliverables
   .rtl-agent-team/
     state/            # Plugin state files (auto-managed)
   ```
   Note: Per-module subdirectories under `refc/`, `bfm/`, `rtl/`, `sim/` are created
   during Phase 2 (architecture) when module decomposition is decided.
   Example: `rtl/entropy/`, `rtl/itq/`, `sim/entropy/`, `sim/itq/`, etc.

3. **Check EDA tool availability** (via `which` or `--version`):

   | Tool | Check Command | Purpose | Required |
   |------|--------------|---------|----------|
   | verilator | `verilator --version` | Simulation + Lint | Yes |
   | verible | `verible-verilog-lint --version` | Style Lint + Formatting | Yes |
   | iverilog | `iverilog -V` | Alternative simulator | Optional |
   | yosys | `yosys --version` | Synthesis | Yes |
   | sby | `sby --help` | Formal verification | Optional |
   | cocotb | `python3 -c "import cocotb; print(cocotb.__version__)"` | Functional verification | Yes |
   | slang | `slang --version` | Advanced lint | Optional |
   | slang-server | `slang-server --version` | SV Language Server (LSP) | Optional |
   | gtkwave | `gtkwave --version` | Waveform viewer | Optional |
   | systemc | `pkg-config --modversion systemc` or check `$SYSTEMC_HOME` | SystemC/TLM-2.0 library (ref model, BFM) | Optional |
   | python3 | `python3 --version` | cocotb runtime | Yes |
   | gcc/g++ | `g++ --version` | Reference model build | Yes |
   | make | `make --version` | Build system | Yes |

4. **Generate lessons-learned.md** (if docs/lessons-learned.md does not exist):
   Create `docs/lessons-learned.md` with initial header:
   ```markdown
   # Lessons Learned

   > Cross-phase knowledge base. Entries are appended after each bug fix (especially Phase 5→4 feedback).
   > Agents in Phase 4/5 should read this file to avoid repeating known issues.
   >
   > Entry format: see `skills/rtl-autopilot/templates/lessons-learned-entry.md`

   ---
   ```

5. **Generate filelist templates** (if rtl/ has no .f files):
   - Copy `skills/rtl-setup/templates/filelist.f` to `rtl/filelist_top.f` as starting point.
   - Per-module filelists (`rtl/filelist_{module}.f`) are created during Phase 4 when modules are coded.
   - Filelists support all simulators via simulate.sh (+incdir+ auto-converted for iverilog).
   - **Filelist convention (3 types):**
     | Type | Location | Required |
     |------|----------|----------|
     | Module-level | `rtl/filelist_{module}.f` | MUST exist per module |
     | Top-level | `rtl/filelist_top.f` | MUST exist (includes module filelists) |
     | TB/test | in sim/ scope | Dynamic (scripts add at runtime) |

5.5. **Install simulate.sh** (if scripts/simulate.sh does not exist):
   Copy `scripts/simulate.sh` and make executable:
   ```bash
   chmod +x scripts/simulate.sh
   ```
   This simulator-agnostic script supports iverilog, verilator, vcs, xrun, questa.
   All skill files reference this script instead of direct simulator invocations.

5.7. **Install lint/syn scripts** (if lint/scripts/ or syn/scripts/ is empty):
   Create `lint/scripts/run_lint.sh` and `syn/scripts/run_syn.sh`.
   These scripts support both open-source (verilator, verible, yosys) and commercial tools (vcs, xrun, questa, dc_shell).

6. **Generate cocotb Makefile template** (if sim/ has no Makefile):
   Copy `skills/rtl-setup/templates/cocotb-makefile` to `sim/top/Makefile` as reference.
   Per-module cocotb Makefiles are created in `sim/{module}/Makefile` during Phase 4-5.
   Supports icarus, verilator, vcs, xcelium, questa with per-simulator compile args.

6.5. **Generate SV testbench template** (inform user):
   Reference `skills/rtl-sv-unit-test/templates/sv-testbench-template.sv` for Tier 2 unit tests.
   Replace `{{MODULE_NAME}}` and `{{DOMAIN}}` placeholders when creating per-module TBs.
   TB files go in `sim/{module}/tb_{module}.sv`.

7. **Generate module template** (if rtl/ has no .sv files):
   Create `rtl/include/template_module.sv` demonstrating project naming conventions:
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

8. **Report setup summary**:
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

9. **Docker EDA image build** (on user request):
   When the user requests "docker image", "EDA docker environment", etc., build the Docker image.
   See the `<Advanced>` section for detailed build/run commands and included tool list.

   ```bash
   docker build -t rtl-eda-tools docker/
   docker run -it --rm -v $(pwd):/workspace -w /workspace rtl-eda-tools
   ```
</Steps>

<Advanced>

## Docker EDA Image Details

The image includes all required and optional EDA tools so the entire team can share an identical environment.

### Build (versions are configurable)
```bash
docker build -t rtl-eda-tools \
  --build-arg VERILATOR_VERSION=5.024 \
  --build-arg SLANG_VERSION=v6.0 \
  --build-arg SYSTEMC_VERSION=3.0.2 \
  docker/
```

### Run
```bash
# Basic run
docker run -it --rm -v $(pwd):/workspace -w /workspace rtl-eda-tools

# GUI (gtkwave) support
docker run -it --rm \
  -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v $(pwd):/workspace -w /workspace rtl-eda-tools
```

### Included Tools
| Tool | Version | Purpose |
|------|---------|---------|
| verilator | 5.024 (configurable) | Simulation + Lint |
| verible | latest release | Style Lint + Formatting |
| yosys | apt latest | Synthesis |
| iverilog | apt latest | Alternative simulator |
| slang | v6.0 (configurable) | IEEE 1800 Semantic Lint |
| sby (SymbiYosys) | latest + boolector, z3 | Formal verification |
| gtkwave | apt latest | Waveform viewer |
| SystemC/TLM-2.0 | 3.0.2 (configurable) | Reference model + BFM |
| cocotb + extensions | pip latest | Functional verification |
| gcc/g++ | apt latest | Reference model build |

</Advanced>

<Tool_Usage>
```
# Directory creation (Bash CLI)
Bash: mkdir -p specs refc/include refc/build bfm/include rtl/common rtl/include rtl/top sim/top sim/formal lint/scripts lint/reports syn/scripts syn/reports docs/phase-{1-research,2-architecture,3-uarch,4-rtl,5-verify,7-exploration} docs/decisions reviews/phase-{1-research,2-architecture,3-uarch,4-rtl,5-verify,6-review,7-exploration} .rtl-agent-team/state .rtl-agent-team/scratch

# Tool checks via Bash CLI (run in parallel, NOT MCP)
Bash: verilator --version 2>&1 || echo "NOT_FOUND"
Bash: verible-verilog-lint --version 2>&1 || echo "NOT_FOUND"
Bash: yosys --version 2>&1 || echo "NOT_FOUND"
Bash: python3 -c "import cocotb; print(cocotb.__version__)" 2>&1 || echo "NOT_FOUND"
Bash: slang --version 2>&1 || echo "NOT_FOUND"
Bash: slang-server --version 2>&1 || echo "NOT_FOUND"
Bash: pkg-config --modversion systemc 2>/dev/null || (test -n "$SYSTEMC_HOME" && test -f "$SYSTEMC_HOME/lib-linux64/libsystemc.a" && echo "$SYSTEMC_HOME (found via SYSTEMC_HOME)") || echo "NOT_FOUND"
Bash: g++ --version 2>&1 || echo "NOT_FOUND"

# Lessons learned initial file (if not exists)
# Write: docs/lessons-learned.md — initial header (see Step 4)

# Template generation (copy from plugin templates)
Bash: cp skills/rtl-setup/templates/filelist.f rtl/filelist_top.f
Bash: cp skills/rtl-setup/templates/cocotb-makefile sim/top/Makefile
Bash: chmod +x scripts/simulate.sh
Write: rtl/include/template_module.sv — convention reference template (i_/o_ prefix, sys_clk/sys_rst_n)
```

**All EDA tools are executed via Bash CLI directly. No MCP tool servers for EDA.**
</Tool_Usage>

<Examples>
<Good>
User: "I want to start a new FPGA project"
→ Run rtl-setup. Create directories, check tools, report what's missing.

User: "setup" or "rtl-setup"
→ Same as above.
</Good>
<Bad>
User: "Create an AXI slave module"
→ Do NOT run rtl-setup. Use rtl-code skill directly.
</Bad>
</Examples>

<Install_Instructions>
When tools are missing, provide these installation commands:

```bash
# Ubuntu/Debian
sudo apt install verilator yosys iverilog gtkwave build-essential python3-pip
pip3 install cocotb

# Verible (GitHub Releases)
# See: https://github.com/chipsalliance/verible/releases
# Download prebuilt binary for your platform and add to PATH

# macOS (Homebrew)
brew install verilator yosys icarus-verilog gtkwave
pip3 install cocotb
# brew install verible  # or download from GitHub releases

# SymbiYosys (from source)
# See: https://symbiyosys.readthedocs.io/en/latest/install.html

# slang (from source or package)
# See: https://sv-lang.com

# slang-server (SystemVerilog LSP for Claude Code)
# Automated install (builds from source + registers Claude Code plugin):
bash scripts/install-slang-server.sh install
# Or manually: https://github.com/hudson-trading/slang-server

# SystemC/TLM-2.0 (for reference models and BFMs)
# Option 1: apt (Ubuntu 22.04+)
sudo apt install libsystemc-dev

# Option 2: from source (recommended for specific version)
wget https://github.com/accellera-official/systemc/archive/refs/tags/3.0.2.tar.gz
tar xzf 3.0.2.tar.gz && cd systemc-3.0.2
mkdir build && cd build
cmake .. -DCMAKE_INSTALL_PREFIX=/usr/local
make -j$(nproc) && sudo make install

# Option 3: Docker EDA image (includes SystemC 3.0.2)
docker build -t rtl-eda-tools docker/
```
</Install_Instructions>

<Escalation_And_Stop_Conditions>
- Required tool not found (verilator, verible, yosys, cocotb, gcc, make) → report with install commands, do NOT proceed to design
- Directory creation permission denied → report error, suggest user fix permissions
- Existing project detected (rtl/ has .sv files in subdirectories) → warn user, ask whether to skip template generation
- Python version < 3.8 → cocotb 2.0 requires Python 3.8+; report incompatibility
- No write access to project directory → halt, cannot create structure
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All required directories exist
- [ ] Tool availability checked via Bash CLI and reported
- [ ] Missing tools listed with install instructions
- [ ] Template files created for empty directories
- [ ] Module template (rtl/include/template_module.sv) demonstrates naming conventions
- [ ] Setup report includes coding convention summary (i_/o_ prefix, {domain}_clk/{domain}_rst_n)
- [ ] Setup report displayed to user
</Final_Checklist>
