# Install Commands (rat-setup reference)

Installation commands based on the user's choice of `local`, `global`, `docker`, or macOS
(Homebrew). Read this file only after Q1 collects a remediation choice for missing Tier 1
tools.

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
which may lack full C++20 support needed by tools like **slang**, **svlens**, and recent **Verilator**.

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

# ===== svlens (structural analysis: CDC + connectivity + metrics) =====
git clone https://github.com/babyworm/svlens.git "$HOME/tools/svlens"
cd "$HOME/tools/svlens"
./scripts/setup-deps.sh --prefix "$HOME/.local"
cmake -B build -DCMAKE_PREFIX_PATH="$HOME/.local"
cmake --build build -j$(nproc)
cmake --install build --prefix "$HOME/.local"
# Binary installs to ~/.local/bin/svlens

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
