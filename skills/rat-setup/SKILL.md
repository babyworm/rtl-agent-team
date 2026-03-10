---
name: rat-setup
description: "This skill should be used when initializing a new RTL project, setting up directory structure, or verifying EDA toolchain installation. Triggers on 'setup', 'initialize', 'init project'."
user-invocable: true
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
- Designing architecture or writing RTL (use p2-arch-design or rtl-p4-implement)
</Do_Not_Use_When>

<Why_This_Exists>
The 6-Phase pipeline expects a standard directory layout (rtl/, refc/, bfm/, sim/, lint/, syn/, etc.)
and depends on EDA CLI tools (Verilator, verible/slang, cocotb, etc.) being available.
Without proper setup, agents fail with missing directory or tool-not-found errors.
This skill ensures everything is in place before design work begins.
</Why_This_Exists>

<Execution_Policy>
- Non-destructive: never overwrite existing files or directories
- Report tool status honestly: installed version or "NOT FOUND" with install instructions
- Create only the directories that don't already exist
- Generate a setup report at the end
- If any **required** tool is missing, mark setup as **NOT READY** and explicitly require installation before proceeding
- Default to user-local installs under `~/.local/bin`, `~/.local`, or `~/tools` (LLM has no sudo access)
- For `global` mode, print sudo commands for the user to run manually
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

2a. **Deploy rules** (if `.claude/rules/` does not exist or files are missing):
   ```bash
   mkdir -p .claude/rules
   # Copy only if target does not exist (non-destructive)
   [ ! -f .claude/rules/rtl-coding-conventions.md ] && cp skills/rat-setup/templates/rules/rtl-coding-conventions.md .claude/rules/
   [ ! -f .claude/rules/rtl-verification-gate.md ] && cp skills/rat-setup/templates/rules/rtl-verification-gate.md .claude/rules/
   [ ! -f .claude/rules/diagram-rules.md ] && cp skills/rat-setup/templates/rules/diagram-rules.md .claude/rules/
   ```

2b. **Deploy guides** (copy CLAUDE.md to each directory if not already present):
   ```bash
   # Copy guide files as CLAUDE.md into each artifact directory (non-destructive)
   [ ! -f rtl/CLAUDE.md ] && cp skills/rat-setup/templates/guides/rtl-guide.md rtl/CLAUDE.md
   [ ! -f sim/CLAUDE.md ] && cp skills/rat-setup/templates/guides/sim-guide.md sim/CLAUDE.md
   [ ! -f docs/CLAUDE.md ] && cp skills/rat-setup/templates/guides/docs-guide.md docs/CLAUDE.md
   [ ! -f reviews/CLAUDE.md ] && cp skills/rat-setup/templates/guides/reviews-guide.md reviews/CLAUDE.md
   [ ! -f refc/CLAUDE.md ] && cp skills/rat-setup/templates/guides/refc-guide.md refc/CLAUDE.md
   [ ! -f syn/CLAUDE.md ] && cp skills/rat-setup/templates/guides/syn-guide.md syn/CLAUDE.md
   ```

3. **Check EDA tool availability** (via `which` or `--version`):

   | Tool | Check Command | Purpose | Required |
   |------|--------------|---------|----------|
   | verilator | `verilator --version` | Simulation + Lint | Yes |
   | verible | `verible-verilog-lint --version` | Style Lint + Formatting | Yes (at least one of verible/slang) |
   | slang | `slang --version` | IEEE 1800 Semantic Lint | Yes (at least one of verible/slang; both recommended) |
   | slang-server | `slang-server --version` | SV Language Server (LSP) | Recommended |
   | cocotb | `python3 -c "import cocotb; print(cocotb.__version__)"` | Functional verification | Yes |
   | systemc | `pkg-config --modversion systemc` or check `$SYSTEMC_HOME` | SystemC/TLM-2.0 library (ref model, BFM) | Yes |
   | python3 | `python3 --version` | cocotb runtime | Yes |
   | gcc/g++ | `g++ --version` | Reference model build | Yes |
   | make | `make --version` | Build system | Yes |
   | iverilog | `iverilog -V` | Fallback simulator | Optional (nice-to-have if verilator is installed) |
   | yosys | `yosys --version` | Synthesis (Phase 5B+) | Optional |
   | sby | `sby --help` | Formal verification | Optional |
   | jq | `jq --version` | Hook JSON parser (robust state gating) | Recommended |
   | gtkwave | `gtkwave --version` | Waveform viewer | Optional |

   **Lint tool gate**: At least one of `verible` or `slang` MUST be installed.
   Both are recommended — verible for style/formatting, slang for deep semantic analysis.
   If only one is available, setup proceeds with a warning recommending the other.

3.5. **Check Docker EDA image** (informational, NOT required for setup):
   Docker is used as a **transparent tool proxy** — when a local tool is missing, `run_tool()` in
   `lib/tool-runner.sh` automatically falls back to `docker exec` on a persistent container.
   This is primarily useful for Phase 5 (verification/silicon validation) commercial tools.
   - Check if `docker` CLI is available: `docker --version`
   - If Docker is NOT available → note in report, skip (all open-source tools should be installed locally)
   - If Docker IS available, check if `rtl-eda-tools` image exists: `docker images -q rtl-eda-tools`
     - **Image exists** → note as available for tool fallback
     - **Image does NOT exist** → inform user they can build it later if needed:
       ```bash
       docker build -t rtl-eda-tools "${CLAUDE_PLUGIN_ROOT}/docker/"
       ```
   - Store the Docker status for the setup report in Step 8.
   - **Do NOT block setup** on Docker availability — it is optional infrastructure.

4. **Generate lessons-learned.md** (if docs/lessons-learned.md does not exist):
   Create `docs/lessons-learned.md` with initial header:
   ```markdown
   # Lessons Learned

   > Cross-phase knowledge base. Entries are appended after each bug fix (especially Phase 5→4 feedback).
   > Agents in Phase 4/5 should read this file to avoid repeating known issues.
   >
   > Entry format: LL-{NNN} with sections: Symptom, Root Cause, Fix Applied, Prevention, Related (REQ IDs, module, fix commit, ADR, Phase 5 Sub-phase)

   ---
   ```

5. **Generate filelist templates** (if rtl/ has no .f files):
   - Copy `skills/rat-setup/templates/filelist.f` to `rtl/filelist_top.f` as starting point.
   - Per-module filelists (`rtl/filelist_{module}.f`) are created during Phase 4 when modules are coded.
   - Filelists support all simulators via run_sim.sh (+incdir+ auto-converted for iverilog).
   - **Filelist convention (3 types):**
     | Type | Location | Required |
     |------|----------|----------|
     | Module-level | `rtl/filelist_{module}.f` | MUST exist per module |
     | Top-level | `rtl/filelist_top.f` | MUST exist (includes module filelists) |
     | TB/test | in sim/ scope | Dynamic (scripts add at runtime) |

5.5. **Install run_sim.sh** (if scripts/run_sim.sh does not exist):
   Copy `scripts/run_sim.sh` and make executable:
   ```bash
   chmod +x scripts/run_sim.sh
   ```
   This simulator-agnostic script supports iverilog, verilator, vcs, xrun, questa.
   All skill files reference this script instead of direct simulator invocations.

5.7. **Install EDA scripts** (if script folders are empty):
   Create lint, synthesis, CDC, and equivalence checking scripts plus the shared tool runner library.
   All scripts use `lib/tool-runner.sh` for transparent Docker fallback when local tools are missing.
   These scripts support replayable execution (`outdir/replay/run_*_latest.sh`) and both open-source and commercial tools:
   - **Tool runner**: `lib/tool-runner.sh` — `run_tool()` tries local binary first, falls back to persistent Docker container
   - **Lint**: `lint/scripts/run_lint.sh` — verilator/verible/slang + spyglass
   - **Synthesis**: `syn/scripts/run_syn.sh` — yosys + dc_shell (Synopsys) + genus (Cadence)
   - **Equivalence checking**: `syn/scripts/run_formality.sh` (Synopsys Formality) + `syn/scripts/run_conformal.sh` (Cadence Conformal LEC)
   - **CDC**: `sim/cdc/run_cdc.sh` — structural quick check + spyglass/vc_cdc/questa_cdc
   - Runtime hook integration: `hooks/rtl-skill-activation.sh` runs
     `skills/rat-setup/scripts/install_project_templates.sh` automatically when `rat-setup` starts.
     This ensures script deployment happens even if the agent omits copy commands.

6. **Generate cocotb Makefile template** (if sim/ has no Makefile):
   Copy `skills/rat-setup/templates/cocotb-makefile` to `sim/top/Makefile` as reference.
   Per-module cocotb Makefiles are created in `sim/{module}/Makefile` during Phase 4-5.
   Supports icarus, verilator, vcs, xcelium, questa with per-simulator compile args.

6.6. **Deploy Phase 6 PDF Makefile** (if reviews/phase-6-review/ has no Makefile):
   Copy `skills/rat-setup/templates/phase6-pdf-makefile` to `reviews/phase-6-review/Makefile`.
   Enables `make pdf` for design note PDF generation with pandoc + xelatex.
   Optional D2/Mermaid diagram pre-rendering when tools are available.

6.5. **Generate SV testbench template** (inform user):
   Reference `skills/rtl-p4s-unit-test/templates/sv-testbench-template.sv` for Tier 2 unit tests.
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
   - Missing required: [list with local install commands (LLM default); sudo commands for manual global install]
   - Coding conventions: lowRISC SV Style + project overrides
     - Port prefix: i_/o_/io_ (NOT suffix _i/_o)
     - Clock: {domain}_clk (e.g., sys_clk)
     - Reset: {domain}_rst_n (e.g., sys_rst_n)
   - Ready to start: Yes/No (**No** if any required tool is missing)
   - Docker EDA image: [Built / Not built / Docker not available] (optional, for tool fallback)
   ```
   If required tools are missing AND Docker is available:
   - Image NOT built → append: "EDA scripts use transparent Docker fallback via `lib/tool-runner.sh`. Build image when needed: `docker build -t rtl-eda-tools \"${CLAUDE_PLUGIN_ROOT}/docker/\"`"
   - Image already built → append: "Docker tool fallback is active. Missing local tools will automatically execute inside a persistent container."

8.5. **Required tool remediation**:
   If one or more **required** tools are missing:
   - Stop after setup/reporting and tell the user installation is required before real design work
   - Ask the user **before attempting installation** whether they want:
     - `local` — user-local install under `~/.local/bin` (LLM executes directly, **default**)
     - `global` — system-wide install (provide `sudo apt install ...` commands for user to run manually; LLM cannot use sudo)
     - `skip` — do not install now; report that the project is not ready
   - Use a concise plain-text question if interactive choice UI is unavailable
   - **Default is `local`** — the LLM has no sudo access, so local install is the only option it can execute autonomously
   - **`global` mode**: Print the exact `sudo` commands and instruct the user to run them manually, then re-run `/rat-setup` to verify
   - **Actively look up the latest stable version** from official upstream sources before giving install commands for fast-moving tools such as Verilator and SystemC
   - Prefer official documentation / release announcements / upstream tags over distro package versions
   - In the setup report, include the **exact version chosen** and the **official source URL** used to justify it
   - Provide **exact commands** for each missing tool
   - For `local` installs: ensure executables resolve from `~/.local/bin`, remind user to add to `PATH` for persistence
   - If Docker fallback can cover a missing tool, mention it as a fallback rather than the primary recommendation
   - If the user chooses `skip`, clearly list the blocked required tools and end with `Ready to start: No`

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
| yosys | OSS CAD Suite | Synthesis |
| iverilog | apt latest | Alternative simulator |
| slang | v6.0 (configurable) | IEEE 1800 Semantic Lint |
| sby (SymbiYosys) | OSS CAD Suite + boolector, z3, yices2 | Formal verification |
| gtkwave | apt latest | Waveform viewer |
| SystemC/TLM-2.0 | 3.0.2 (configurable) | Reference model + BFM |
| cocotb + extensions | pip latest | Functional verification |
| gcc/g++ | apt latest | Reference model build |

</Advanced>

<Tool_Usage>
```
# Directory creation (Bash CLI)
Bash: mkdir -p specs refc/include refc/build bfm/include rtl/common rtl/include rtl/top sim/top sim/formal sim/cdc sim/cdc/reports lint/scripts lint/reports syn/scripts syn/reports syn/constraints docs/phase-{1-research,2-architecture,3-uarch,4-rtl,5-verify,7-exploration} docs/decisions reviews/phase-{1-research,2-architecture,3-uarch,4-rtl,5-verify,6-review,7-exploration} .rtl-agent-team/state .rtl-agent-team/scratch

# Rules deployment (non-destructive)
Bash: mkdir -p .claude/rules
Bash: [ ! -f .claude/rules/rtl-coding-conventions.md ] && cp skills/rat-setup/templates/rules/rtl-coding-conventions.md .claude/rules/ || true
Bash: [ ! -f .claude/rules/rtl-verification-gate.md ] && cp skills/rat-setup/templates/rules/rtl-verification-gate.md .claude/rules/ || true
Bash: [ ! -f .claude/rules/diagram-rules.md ] && cp skills/rat-setup/templates/rules/diagram-rules.md .claude/rules/ || true

# Guide deployment (non-destructive, copy as CLAUDE.md)
Bash: [ ! -f rtl/CLAUDE.md ] && cp skills/rat-setup/templates/guides/rtl-guide.md rtl/CLAUDE.md || true
Bash: [ ! -f sim/CLAUDE.md ] && cp skills/rat-setup/templates/guides/sim-guide.md sim/CLAUDE.md || true
Bash: [ ! -f docs/CLAUDE.md ] && cp skills/rat-setup/templates/guides/docs-guide.md docs/CLAUDE.md || true
Bash: [ ! -f reviews/CLAUDE.md ] && cp skills/rat-setup/templates/guides/reviews-guide.md reviews/CLAUDE.md || true
Bash: [ ! -f refc/CLAUDE.md ] && cp skills/rat-setup/templates/guides/refc-guide.md refc/CLAUDE.md || true
Bash: [ ! -f syn/CLAUDE.md ] && cp skills/rat-setup/templates/guides/syn-guide.md syn/CLAUDE.md || true

# Tool checks via Bash CLI (run in parallel, NOT MCP)
# --- Required tools ---
Bash: verilator --version 2>&1 || echo "NOT_FOUND"
Bash: python3 --version 2>&1 || echo "NOT_FOUND"
Bash: python3 -c "import cocotb; print(cocotb.__version__)" 2>&1 || echo "NOT_FOUND"
Bash: g++ --version 2>&1 || echo "NOT_FOUND"
Bash: make --version 2>&1 || echo "NOT_FOUND"
Bash: pkg-config --modversion systemc 2>/dev/null || (test -n "$SYSTEMC_HOME" && test -f "$SYSTEMC_HOME/lib-linux64/libsystemc.a" && echo "$SYSTEMC_HOME (found via SYSTEMC_HOME)") || echo "NOT_FOUND"
# --- Lint tools (at least one required) ---
Bash: verible-verilog-lint --version 2>&1 || echo "NOT_FOUND"
Bash: slang --version 2>&1 || echo "NOT_FOUND"
# --- Recommended ---
Bash: slang-server --version 2>&1 || echo "NOT_FOUND"
Bash: jq --version 2>&1 || echo "NOT_FOUND"
# --- Optional ---
Bash: iverilog -V 2>&1 || echo "NOT_FOUND"
Bash: yosys --version 2>&1 || echo "NOT_FOUND"

# Docker EDA image check (run only if required tools are missing)
Bash: docker --version 2>&1 || echo "NOT_FOUND"
Bash: docker images -q rtl-eda-tools 2>/dev/null | head -1 || echo "NO_IMAGE"

# Lessons learned initial file (if not exists)
# Write: docs/lessons-learned.md — initial header (see Step 4)

# Template generation (copy from plugin templates)
Bash: cp skills/rat-setup/templates/filelist.f rtl/filelist_top.f
Bash: cp skills/rat-setup/templates/cocotb-makefile sim/top/Makefile
Bash: mkdir -p lib && cp skills/rat-setup/templates/lib/tool-runner.sh lib/tool-runner.sh
Bash: cp skills/rat-setup/templates/run_lint.sh lint/scripts/run_lint.sh
Bash: cp skills/rat-setup/templates/run_syn.sh syn/scripts/run_syn.sh
Bash: cp skills/rat-setup/templates/run_cdc.sh sim/cdc/run_cdc.sh
Bash: cp skills/rat-setup/templates/run_formality.sh syn/scripts/run_formality.sh
Bash: cp skills/rat-setup/templates/run_conformal.sh syn/scripts/run_conformal.sh
Bash: mkdir -p reviews/phase-6-review && cp -n skills/rat-setup/templates/phase6-pdf-makefile reviews/phase-6-review/Makefile
Bash: chmod +x lib/tool-runner.sh lint/scripts/run_lint.sh syn/scripts/run_syn.sh sim/cdc/run_cdc.sh syn/scripts/run_formality.sh syn/scripts/run_conformal.sh
Bash: chmod +x scripts/run_sim.sh
# Hook-safe bootstrap (non-destructive, idempotent)
Bash: bash skills/rat-setup/scripts/install_project_templates.sh "$PWD"
Write: rtl/include/template_module.sv — convention reference template (i_/o_ prefix, sys_clk/sys_rst_n)
```

**All EDA tools are executed via Bash CLI directly. No MCP tool servers for EDA.**
</Tool_Usage>

<Examples>
<Good>
User: "I want to start a new FPGA project"
→ Run rat-setup. Create directories, check tools, report what's missing.

User: "setup" or "rat-setup"
→ Same as above.
</Good>
<Bad>
User: "Create an AXI slave module"
→ Do NOT run rat-setup. Use rtl-p4-implement skill directly.
</Bad>
</Examples>

<Install_Instructions>
When tools are missing, provide installation commands based on user's choice of `local` or `global`.

## Upstream version discovery (run first for fast-moving tools)

```bash
# Verilator official sources:
# - https://verilator.org/guide/latest/install.html
# - https://github.com/verilator/verilator
# SystemC official sources:
# - https://github.com/accellera-official/systemc
#
# Resolve concrete stable versions before proceeding:
VERILATOR_LATEST_TAG="$(git ls-remote --tags --refs https://github.com/verilator/verilator.git 'v*' | awk -F/ '{print $3}' | sort -V | tail -1)"
SYSTEMC_LATEST_TAG="$(git ls-remote --tags --refs https://github.com/accellera-official/systemc.git | awk -F/ '{print $3}' | sort -V | tail -1)"
echo "Verilator latest stable candidate: ${VERILATOR_LATEST_TAG}"
echo "SystemC latest stable candidate: ${SYSTEMC_LATEST_TAG}"
```

## Mode: `local` (default — LLM executes directly, no sudo)

The LLM runs these commands autonomously. All binaries install under `~/.local/bin`.

```bash
# ===== PATH bootstrap =====
mkdir -p "$HOME/.local/bin" "$HOME/.local/lib" "$HOME/tools"
export PATH="$HOME/.local/bin:$PATH"
# Remind user to add to ~/.bashrc or ~/.zshrc for persistence

# ===== Verilator (source build → ~/.local) =====
# Build dependencies must be pre-installed (see global mode if missing)
git clone https://github.com/verilator/verilator.git "$HOME/tools/verilator-src"
cd "$HOME/tools/verilator-src"
git fetch --tags
git checkout "${VERILATOR_LATEST_TAG:-stable}"
autoconf
./configure --prefix="$HOME/.local"
make -j"$(nproc)"
make install
verilator --version

# ===== Verible (prebuilt binary) =====
# See: https://github.com/chipsalliance/verible/releases
mkdir -p "$HOME/tools/verible"
# Download appropriate release tarball, then:
tar xzf verible-*.tar.gz -C "$HOME/tools/verible" --strip-components=1
ln -sf "$HOME/tools/verible/bin/verible-verilog-lint" "$HOME/.local/bin/verible-verilog-lint"
ln -sf "$HOME/tools/verible/bin/verible-verilog-format" "$HOME/.local/bin/verible-verilog-format"

# ===== slang (prebuilt binary or source) =====
# See: https://sv-lang.com / https://github.com/MikePopoloski/slang/releases

# ===== slang-server (SystemVerilog LSP for Claude Code) =====
# Automated install (builds from source + registers Claude Code plugin):
bash scripts/install-slang-server.sh install
# Or manually: https://github.com/hudson-trading/slang-server

# ===== cocotb (pip user install) =====
python3 -m pip install --user cocotb
export PATH="$HOME/.local/bin:$PATH"

# ===== SystemC/TLM-2.0 (source build → ~/.local) =====
git clone https://github.com/accellera-official/systemc.git "$HOME/tools/systemc-src"
cd "$HOME/tools/systemc-src"
git fetch --tags
git checkout "${SYSTEMC_LATEST_TAG}"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$HOME/.local"
cmake --build build -j"$(nproc)"
cmake --install build
export SYSTEMC_HOME="$HOME/.local"
export PKG_CONFIG_PATH="$HOME/.local/lib/pkgconfig:$PKG_CONFIG_PATH"
pkg-config --modversion systemc || true

# ===== Optional: OSS CAD Suite (Yosys + SymbiYosys + solvers) =====
# https://github.com/YosysHQ/oss-cad-suite-build
curl -fsSL "https://github.com/YosysHQ/oss-cad-suite-build/releases/download/2025-02-01/oss-cad-suite-linux-x64-20250201.tgz" -o oss-cad-suite.tgz
tar xzf oss-cad-suite.tgz -C ~/tools
ln -sf "$HOME/tools/oss-cad-suite/bin/yosys" "$HOME/.local/bin/yosys"
ln -sf "$HOME/tools/oss-cad-suite/bin/sby" "$HOME/.local/bin/sby"
```

## Mode: `global` (print commands for user to run manually — requires sudo)

The LLM CANNOT execute these. Print as a script block and instruct the user to:
1. Run the commands manually
2. Re-run `/rat-setup` to verify

```bash
#!/bin/bash
# RTL Agent Team — Global Install Script
# Run this manually with sudo access, then re-run /rat-setup to verify.

set -euo pipefail

# ===== Build dependencies (required for Verilator source build) =====
sudo apt update
sudo apt install -y git help2man perl python3 python3-pip make autoconf \
  g++ flex bison ccache libfl2 libfl-dev zlib1g zlib1g-dev cmake

# ===== Optional system packages =====
sudo apt install -y iverilog gtkwave jq

# ===== Verilator (source build — distro packages are often outdated) =====
# Check latest version: https://github.com/verilator/verilator
VERILATOR_TAG="${1:-stable}"  # pass tag as arg, or use stable branch
git clone https://github.com/verilator/verilator.git /tmp/verilator-src
cd /tmp/verilator-src
git checkout "$VERILATOR_TAG"
autoconf
./configure
make -j"$(nproc)"
sudo make install
verilator --version

# ===== Verible =====
# Download from: https://github.com/chipsalliance/verible/releases
# Extract and copy binaries to /usr/local/bin/

# ===== slang =====
# Download from: https://github.com/MikePopoloski/slang/releases
# Extract and copy binary to /usr/local/bin/

# ===== cocotb =====
pip3 install cocotb

# ===== SystemC/TLM-2.0 (source build — distro packages are often outdated) =====
# Check latest version: https://github.com/accellera-official/systemc
SYSTEMC_TAG="${2:-}"  # pass tag as second arg
git clone https://github.com/accellera-official/systemc.git /tmp/systemc-src
cd /tmp/systemc-src
[ -n "$SYSTEMC_TAG" ] && git checkout "$SYSTEMC_TAG"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)"
sudo cmake --install build
pkg-config --modversion systemc

echo "Done. Re-run /rat-setup to verify installation."
```

## macOS (Homebrew)

```bash
brew install verilator icarus-verilog gtkwave jq
pip3 install cocotb
# Verible: download from GitHub Releases
# slang: download from GitHub Releases or brew
# SystemC: build from source (see local mode)
# Yosys + SymbiYosys: use OSS CAD Suite or brew install yosys
```

## Docker fallback

```bash
# Optional: Docker EDA image (includes all tools via OSS CAD Suite)
docker build -t rtl-eda-tools docker/
```
</Install_Instructions>

<Escalation_And_Stop_Conditions>
- Required tool not found (verilator, cocotb, systemc, gcc, make, python3) → report with install commands, require installation, do NOT proceed to design
- Neither verible nor slang found → report as REQUIRED (at least one lint tool needed), do NOT proceed to design
- Only one of verible/slang found → proceed with WARNING recommending the missing tool
- Before installing missing required tools → ask user whether to use `local` (default, LLM executes), `global` (provide sudo commands for user to run manually), or `skip`
- Before installing fast-moving required tools (especially Verilator, SystemC) → verify the latest stable version from official sources and cite the source used
- `jq` not found → report as recommended install (hooks fall back to python/sed, but robust JSON gating prefers jq)
- Directory creation permission denied → report error, suggest user fix permissions
- Existing project detected (rtl/ has .sv files in subdirectories) → warn user, ask whether to skip template generation
- Python version < 3.9 → Project requires Python 3.9+ (hashlib usedforsecurity); report incompatibility
- No write access to project directory → halt, cannot create structure
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All required directories exist
- [ ] Tool availability checked via Bash CLI and reported
- [ ] Missing tools listed with install instructions
- [ ] Missing required tools trigger a user choice: local (default, LLM executes) / global (sudo commands for user) / skip
- [ ] Lint tool gate: at least one of verible/slang is installed (both recommended)
- [ ] Fast-moving tools (Verilator, SystemC) are version-pinned from an official latest-stable source when installation guidance is given
- [ ] Template files created for empty directories
- [ ] Module template (rtl/include/template_module.sv) demonstrates naming conventions
- [ ] Setup report includes coding convention summary (i_/o_ prefix, {domain}_clk/{domain}_rst_n)
- [ ] Setup report marks Ready to start = No when required tools are missing
- [ ] Docker EDA image status checked when required tools are missing
- [ ] Setup report displayed to user
</Final_Checklist>
