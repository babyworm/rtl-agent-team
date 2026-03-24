---
name: rat-setup
description: "This skill should be used when verifying EDA toolchain installation, installing missing tools, or building the Docker EDA image. Triggers on 'setup tools', 'install tools', 'EDA setup', 'docker image'."
user-invocable: true
---

<Purpose>
Interactive one-time environment setup wizard for the RTL Agent Team plugin.
Audits EDA tools, test infrastructure, and plugin configuration.
Guides the user through installation choices with categorized questions.
For per-project directory structure and rules deployment, use `rat-init-project` instead.
</Purpose>

<Use_When>
- First time installing the plugin on a new machine
- Verifying EDA toolchain is properly installed
- Installing missing required EDA tools
- User says "setup tools", "install tools", "EDA setup", "check tools"
- User says "docker image", "make docker", "EDA environment container"
- Recommended by `rat-init-project` when required tools are missing
</Use_When>

<Do_Not_Use_When>
- Initializing a new project workspace (use `rat-init-project`)
- Tools are already verified and working
- Only need to run a specific EDA tool (use the tool-specific skill)
</Do_Not_Use_When>

<Why_This_Exists>
The 6-Phase pipeline depends on EDA CLI tools (Verilator, verible/slang, cocotb, etc.).
Without proper tool installation, design and verification agents fail with tool-not-found errors.
This skill ensures the EDA environment is ready before any design work begins.
</Why_This_Exists>

<Execution_Policy>
- Interactive: ask the user before installing anything or changing configuration
- Report tool status honestly: installed version or "NOT FOUND"
- If any **required** tool is missing, mark setup as **NOT READY** and explicitly require installation
- Default to user-local installs under `~/.local/bin`, `~/.local`, or `~/tools` (LLM has no sudo access)
- For `global` mode, print sudo commands for the user to run manually
- Never overwrite existing user configuration without confirmation
</Execution_Policy>

<Steps>

## Phase 1: Discovery (silent scan — no questions yet)

Run all checks in parallel via Bash CLI, collect results.

### 1a. EDA Tool Audit

Categorize tools into three tiers and check each:

**Tier 1 — Required** (pipeline cannot function without these):

| Tool | Check Command | Purpose |
|------|--------------|---------|
| python3 | `python3 --version` | cocotb runtime, hook JSON parsing |
| gcc/g++ | `g++ --version` | Reference model build (C11/C++17) |
| make | `make --version` | Build system |
| verilator | `verilator --version` | Simulation + Lint |
| cocotb | `python3 -c "import cocotb; print(cocotb.__version__)"` | Functional verification |
| systemc | `pkg-config --modversion systemc` or `$SYSTEMC_HOME` | SystemC/TLM-2.0 (ref model, BFM) |
| lint tool | `verible-verilog-lint --version` AND/OR `slang --version` | At least ONE required |

**Tier 2 — Recommended** (significantly improves workflow):

| Tool | Check Command | Purpose |
|------|--------------|---------|
| jq | `jq --version` | Hook JSON parser (robust state gating) |
| slang-cdc | `slang-cdc --version` | AST-based CDC analysis (crosscheck with structural) |
| sv-renamer | `python3 -c "import sv_renamer"` or `sv_renamer.py --help` | SV identifier rename + semantic diff |
| sv_to_ipxact | `sv_to_ipxact --help` | SV → IP-XACT XML auto-generation |
| slang-server | `slang-server --version` | SV Language Server (LSP for Claude Code) |
| verible (if slang only) | `verible-verilog-lint --version` | Style lint + formatting |
| slang (if verible only) | `slang --version` | Deep semantic lint |

**Tier 3 — Optional** (needed for specific phases):

| Tool | Check Command | When Needed |
|------|--------------|-------------|
| iverilog | `iverilog -V` | Fallback simulator |
| yosys | `yosys --version` | Synthesis (Phase 5B+) |
| sby | `sby --help` | Formal verification (SymbiYosys) |
| gtkwave | `gtkwave --version` | Waveform viewer |
| docker | `docker --version` | EDA tool fallback container |
| sv2v | `sv2v --version` | SV→Verilog for formal tools |

### 1b. Test Infrastructure Audit

| Component | Check Command | Purpose |
|-----------|--------------|---------|
| pytest | `python3 -m pytest --version` | Plugin unit test runner |
| cocotb-bus | `python3 -c "import cocotb_bus; print(cocotb_bus.__version__)"` | Bus protocol models |
| numpy | `python3 -c "import numpy; print(numpy.__version__)"` | BD-rate calculations |
| hjson | `python3 -c "import hjson; print(hjson.__version__)"` | Config file parsing |

### 1c. Plugin Configuration State

```bash
# Check if global rules are deployed
test -d ~/.claude/rules && ls ~/.claude/rules/ 2>/dev/null
# Check Claude Code settings
test -f ~/.claude/settings.json && cat ~/.claude/settings.json
# Check if plugin is registered
test -f ~/.claude/plugins.json && cat ~/.claude/plugins.json
```

---

## Phase 2: Report (show categorized results)

Present results in a clear categorized table:

```
## EDA Environment Audit

### Tier 1 — Required Tools
| Tool | Status | Version | Action Needed |
|------|--------|---------|---------------|
| python3 | OK | 3.11.2 | — |
| verilator | MISSING | — | Install required |
| ... | | | |

### Tier 2 — Recommended Tools
| Tool | Status | Version | Benefit |
| ... |

### Tier 3 — Optional Tools
| Tool | Status | When Needed |
| ... |

### Test Infrastructure
| Component | Status |
| ... |

### Plugin Configuration
| Item | Status |
| Global rules (~/.claude/rules/) | Not deployed |
| ... |

Ready to start: Yes/No (**No** if any required tool is missing)
```

---

## Phase 3: Interactive Decisions (AskUserQuestion for each category)

Only ask questions for items that need action. Skip categories where everything is already satisfied.

### Q1: Required tool remediation (if any Tier 1 tool is missing)

If required tools are missing, installation is required before real design work can begin.

Before installing missing required tools, ask the user:

> **Required tools missing: [list]**
> How would you like to install them?
> 1. `local` — install under ~/.local/bin (I'll execute directly, **recommended**)
> 2. `global` — print sudo commands for user to run manually
> 3. `docker` — use Docker EDA image as fallback (requires docker)
> 4. `skip` — skip for now (pipeline will NOT be fully functional)

### Q2: Optional/Recommended Tools (if any Tier 2-3 tools are missing)

> **Optional tools available for installation: [list with purpose]**
> Which would you like to install? (comma-separated numbers, 'all', or 'none')
> 1. jq — robust JSON parsing in hooks
> 2. yosys + sby — synthesis + formal verification
> 3. slang-server — SV LSP integration for Claude Code
> 4. iverilog — fallback simulator
> 5. gtkwave — waveform viewer
> 6. slang-cdc — AST-based CDC analysis (crosscheck with structural)

### Q3: Plugin Global Configuration

> **Plugin conventions can be deployed globally for access in ALL projects.**
> This makes RTL conventions available even without running `rat-init-project` per project.
> Deploy global configuration? (yes/no)
>
> What will be deployed:
> - `~/.claude/rules/rtl-coding-conventions.md` — port naming (i_/o_), clock/reset conventions
> - `~/.claude/rules/rtl-verification-gate.md` — mandatory lint→TB→sim after RTL changes
> - `~/.claude/CLAUDE.md` — diagram convention block (if not already present)

#### Diagram Rule Injection

Check if `~/.claude/CLAUDE.md` already contains `<markdown_diagram_rule>` tag.
- If tag found → skip (already deployed)
- If tag NOT found → append the following block:

```markdown
<markdown_diagram_rule>
## Diagram Policy

| Diagram Type | Tool | Use For |
|-------------|------|---------|
| **Block diagram** | **D2** | Architecture, module hierarchy, HW block decomposition |
| **Flow / Interaction** | **Mermaid** | Pipeline stages, FSM, data/control flow, sequence diagrams |
| **ASCII flow diagram** | **Prohibited** | Do NOT use ASCII art — use D2 or Mermaid |

D2: architecture diagrams (`.d2` code blocks), per-module internal structure.
Mermaid: FSM (`stateDiagram-v2`), data flow (`flowchart`), sequences (`sequenceDiagram`).
</markdown_diagram_rule>
```

Implementation:
```bash
if ! grep -q '<markdown_diagram_rule>' ~/.claude/CLAUDE.md 2>/dev/null; then
  # Append diagram rule block to ~/.claude/CLAUDE.md
  # Use Read tool to get current content, then Edit/Write to append
fi
```

### Q4: Test Infrastructure (if pytest/cocotb deps missing)

> **Test dependencies missing: [list]**
> Install via pip? (yes/no)
> ```
> python3 -m pip install --user pytest cocotb cocotb-bus numpy hjson
> ```

---

**IMPORTANT: After receiving all Q1-Q4 answers, immediately proceed to Phase 4 execution
in the same response. Do NOT pause or wait for user confirmation between Phase 3 and Phase 4.
The user has already made their decisions — execute them without an extra turn boundary.**

## Phase 4: Execute (based on user answers)

### 4a. Tool Installation

Execute installation commands based on Q1/Q2 answers.
- `local` mode: LLM executes directly (no sudo)
- `global` mode: print sudo commands for user to run manually
- `docker` mode: build Docker image if not present

**Actively look up the latest stable version** from official upstream sources
before giving install commands for fast-moving tools such as Verilator and SystemC.

### 4b. Plugin Config Deployment (if Q3 = yes)

**RTL rules → `~/.claude/rules/`** (path-scoped, RTL files only):
```bash
mkdir -p ~/.claude/rules
# Non-destructive: only copy if target does not exist
[ ! -f ~/.claude/rules/rtl-coding-conventions.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/rules/rtl-coding-conventions.md" ~/.claude/rules/
[ ! -f ~/.claude/rules/rtl-verification-gate.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/rules/rtl-verification-gate.md" ~/.claude/rules/
```

**Diagram rule → `~/.claude/CLAUDE.md`** (tagged block, all projects):
```bash
# Only inject if tag not already present
if ! grep -q '<markdown_diagram_rule>' ~/.claude/CLAUDE.md 2>/dev/null; then
  # Read current ~/.claude/CLAUDE.md, append <markdown_diagram_rule> block via Edit/Write
fi
```
See Q3 section for the exact block content.

### 4c. Test Infra Installation (if Q4 = yes)

```bash
python3 -m pip install --user pytest cocotb cocotb-bus numpy hjson
```

---

## Phase 5: Verify & Final Report

Re-check installed tools and present final status:

```
## RTL Agent Team — Setup Complete

### Tool Status (after installation)
| Tier | Installed | Total | Status |
|------|-----------|-------|--------|
| Required | 7 | 7 | PASS |
| Recommended | 3 | 4 | PARTIAL |
| Optional | 2 | 6 | — |

### Plugin Configuration
| Item | Status |
|------|--------|
| Global rules | Deployed to ~/.claude/rules/ |
| Test infra | pytest, cocotb, numpy installed |

### Setup Marker (advisory)
Write setup completion marker for `rat-init-project` to detect (soft gate, not enforced by hooks).
The actual enforcement gate remains `.claude/rules/rtl-coding-conventions.md` (project-level).
```bash
# Primary: CLAUDE_PLUGIN_DATA (set by Claude Code plugin runtime)
# Fallback: ~/.config/rtl-agent-team/ (reliable when env var is unset)
MARKER_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.config/rtl-agent-team}"
mkdir -p "$MARKER_DIR"
date -u '+%Y-%m-%dT%H:%M:%SZ' > "$MARKER_DIR/.setup-complete"
```

### Next Steps
- Run `/rtl-agent-team:rat-init-project` in your project directory to initialize project structure
- Run `/rtl-agent-team:rat-tutorial` for a guided walkthrough of the pipeline
```

</Steps>

<Tool_Usage>
```
# Tool checks via Bash CLI (run ALL in parallel, NOT MCP)
# --- Tier 1: Required ---
Bash: python3 --version 2>&1 || echo "NOT_FOUND"
Bash: g++ --version 2>&1 | head -1 || echo "NOT_FOUND"
Bash: make --version 2>&1 | head -1 || echo "NOT_FOUND"
Bash: verilator --version 2>&1 || echo "NOT_FOUND"
Bash: python3 -c "import cocotb; print(cocotb.__version__)" 2>&1 || echo "NOT_FOUND"
Bash: pkg-config --modversion systemc 2>/dev/null || (test -n "$SYSTEMC_HOME" && test -f "$SYSTEMC_HOME/lib-linux64/libsystemc.a" && echo "$SYSTEMC_HOME (found via SYSTEMC_HOME)") || echo "NOT_FOUND"
Bash: verible-verilog-lint --version 2>&1 || echo "NOT_FOUND"
Bash: slang --version 2>&1 || echo "NOT_FOUND"

# --- Tier 2: Recommended ---
Bash: jq --version 2>&1 || echo "NOT_FOUND"
Bash: slang-cdc --version 2>&1 || echo "NOT_FOUND"
Bash: slang-server --version 2>&1 || echo "NOT_FOUND"

# --- Tier 3: Optional ---
Bash: iverilog -V 2>&1 | head -1 || echo "NOT_FOUND"
Bash: yosys --version 2>&1 || echo "NOT_FOUND"
Bash: sby --help 2>&1 | head -1 || echo "NOT_FOUND"
Bash: gtkwave --version 2>&1 || echo "NOT_FOUND"
Bash: docker --version 2>&1 || echo "NOT_FOUND"
Bash: sv2v --version 2>&1 || echo "NOT_FOUND"

# --- Test Infrastructure ---
Bash: python3 -m pytest --version 2>&1 || echo "NOT_FOUND"
Bash: python3 -c "import cocotb_bus; print(cocotb_bus.__version__)" 2>&1 || echo "NOT_FOUND"
Bash: python3 -c "import numpy; print(numpy.__version__)" 2>&1 || echo "NOT_FOUND"
Bash: python3 -c "import hjson; print(hjson.__version__)" 2>&1 || echo "NOT_FOUND"

# --- Plugin Config State ---
Bash: ls ~/.claude/rules/ 2>/dev/null || echo "NO_RULES"
Bash: docker images -q rtl-eda-tools 2>/dev/null | head -1 || echo "NO_IMAGE"

# --- Interactive questions via AskUserQuestion ---
# Use AskUserQuestion for Q1-Q4 decisions
```

**All EDA tools are executed via Bash CLI directly. No MCP tool servers for EDA.**
</Tool_Usage>

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

## RHEL/CentOS GCC Toolset (source builds requiring C++17/C++20)

RHEL, CentOS, Rocky, Alma and other EL-based distros ship older GCC by default (often GCC 8-11),
which may lack full C++20 support needed by tools like **slang**, **slang-cdc**, and recent **Verilator**.

Before source-building these tools, detect the distro and activate a newer GCC toolset:

```bash
# Detect RHEL-family and activate gcc-toolset if available
if [ -f /etc/redhat-release ]; then
  # Try gcc-toolset-14, fall back to 13, 12
  for VER in 14 13 12; do
    if [ -f "/opt/rh/gcc-toolset-${VER}/enable" ]; then
      source "/opt/rh/gcc-toolset-${VER}/enable"
      echo "Activated gcc-toolset-${VER}: $(g++ --version | head -1)"
      break
    fi
  done
fi
```

If no toolset is installed, print instructions for the user:
```bash
# RHEL/Rocky/Alma:
sudo dnf install -y gcc-toolset-14
source /opt/rh/gcc-toolset-14/enable
# CentOS Stream:
sudo dnf install -y gcc-toolset-14
scl enable gcc-toolset-14 bash
```

## Mode: `local` (default — LLM executes directly, no sudo)

```bash
# ===== PATH bootstrap =====
mkdir -p "$HOME/.local/bin" "$HOME/.local/lib" "$HOME/tools"
export PATH="$HOME/.local/bin:$PATH"

# ===== Verilator (source build → ~/.local) =====
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
mkdir -p "$HOME/tools/verible"
tar xzf verible-*.tar.gz -C "$HOME/tools/verible" --strip-components=1
ln -sf "$HOME/tools/verible/bin/verible-verilog-lint" "$HOME/.local/bin/verible-verilog-lint"
ln -sf "$HOME/tools/verible/bin/verible-verilog-format" "$HOME/.local/bin/verible-verilog-format"

# ===== slang (prebuilt binary or source) =====
# See: https://sv-lang.com / https://github.com/MikePopoloski/slang/releases

# ===== slang-cdc (AST-based CDC analysis) =====
git clone https://github.com/babyworm/slang-cdc.git "$HOME/tools/slang-cdc"
cd "$HOME/tools/slang-cdc"
make build
make install
# Binary installs to ~/.local/bin/slang-cdc

# ===== slang-server (SystemVerilog LSP for Claude Code) =====
bash scripts/install-slang-server.sh install

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

# ===== Optional: OSS CAD Suite (Yosys + SymbiYosys + solvers) =====
curl -fsSL "https://github.com/YosysHQ/oss-cad-suite-build/releases/download/2025-02-01/oss-cad-suite-linux-x64-20250201.tgz" -o oss-cad-suite.tgz
tar xzf oss-cad-suite.tgz -C ~/tools
ln -sf "$HOME/tools/oss-cad-suite/bin/yosys" "$HOME/.local/bin/yosys"
ln -sf "$HOME/tools/oss-cad-suite/bin/sby" "$HOME/.local/bin/sby"
```

## Mode: `global` (print commands for user to run manually — requires sudo)

```bash
#!/bin/bash
# RTL Agent Team — Global Install Script
# Run this manually with sudo access, then re-run /rat-setup to verify.

set -euo pipefail

sudo apt update
sudo apt install -y git help2man perl python3 python3-pip make autoconf \
  g++ flex bison ccache libfl2 libfl-dev zlib1g zlib1g-dev cmake

sudo apt install -y iverilog gtkwave jq

# Verilator (source build — distro packages are often outdated)
VERILATOR_TAG="${1:-stable}"
git clone https://github.com/verilator/verilator.git /tmp/verilator-src
cd /tmp/verilator-src && git checkout "$VERILATOR_TAG"
autoconf && ./configure && make -j"$(nproc)" && sudo make install

# cocotb
pip3 install cocotb

# SystemC/TLM-2.0
SYSTEMC_TAG="${2:-}"
git clone https://github.com/accellera-official/systemc.git /tmp/systemc-src
cd /tmp/systemc-src
[ -n "$SYSTEMC_TAG" ] && git checkout "$SYSTEMC_TAG"
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)" && sudo cmake --install build

echo "Done. Re-run /rat-setup to verify installation."
```

## macOS (Homebrew)

```bash
brew install verilator icarus-verilog gtkwave jq
pip3 install cocotb
# Verible/slang: download from GitHub Releases
# SystemC: build from source (see local mode)
```

## Docker fallback

```bash
docker build -t rtl-eda-tools docker/
```
</Install_Instructions>

<Advanced>

## Docker EDA Image Details

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

<Escalation_And_Stop_Conditions>
- Required tool not found → report with install commands, require installation
- Neither verible nor slang found → report as REQUIRED
- Only one of verible/slang → proceed with WARNING recommending the other
- Before installing → ask user: local (default) / global / docker / skip
- Before installing fast-moving tools → verify latest stable version from upstream
- Before deploying global rules → confirm with user (never overwrite existing)
- `jq` not found → report as recommended (hooks fall back to python/sed)
- Python version < 3.9 → report incompatibility
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All EDA tools checked via Bash CLI (parallel) and categorized by tier
- [ ] Test infrastructure (pytest, cocotb-bus, numpy, hjson) checked
- [ ] Plugin config state (~/.claude/rules/) checked
- [ ] Categorized audit report displayed before asking questions
- [ ] Missing required tools trigger interactive Q1 (local/global/docker/skip)
- [ ] Optional tools offered selectively via Q2
- [ ] Global rule deployment offered via Q3 (non-destructive)
- [ ] Test infra installation offered via Q4
- [ ] Lint tool gate: at least one of verible/slang installed
- [ ] Fast-moving tools version-pinned from official upstream
- [ ] Docker EDA image status checked
- [ ] Final verification re-check after installation
- [ ] Next steps shown (rat-init-project, rat-tutorial)
</Final_Checklist>
