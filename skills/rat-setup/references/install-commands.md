# Install Commands (rat-setup reference)

Installation commands based on the user's choice of `local`, `global`, `docker`, or macOS
(Homebrew). Read this file only after Q1 collects a remediation choice for missing Tier 1
tools.

## Upstream version discovery (run first for fast-moving tools)

```bash
# Verilator official sources:
# - https://verilator.org/guide/latest/install.html
# - https://github.com/verilator/verilator
# Verible official sources:
# - https://chipsalliance.github.io/verible/README.html#installation
# - https://github.com/chipsalliance/verible/releases
# slang official sources:
# - https://sv-lang.com/user-manual.html#getting-the-binary
# - https://sv-lang.com/building.html
# SystemC official sources:
# - https://github.com/accellera-official/systemc
#
# Resolve concrete stable versions before proceeding:
set -euo pipefail
latest_stable_tag() {
  python3 -c 'import re, sys; tags = [tag.strip() for tag in sys.stdin if tag.strip() and not re.search(r"(?:alpha|beta|rc)", tag, re.I)]; key = lambda tag: tuple((1, int(part)) if part.isdigit() else (0, part.lower()) for part in re.split(r"(\d+)", tag)); tags or sys.exit("no stable tag found"); print(max(tags, key=key))'
}
VERILATOR_LATEST_TAG="$(git ls-remote --tags --refs https://github.com/verilator/verilator.git 'v*' | awk -F/ '{print $3}' | latest_stable_tag)"
VERIBLE_LATEST_TAG="$(git ls-remote --tags --refs https://github.com/chipsalliance/verible.git 'v*' | awk -F/ '{print $3}' | latest_stable_tag)"
SYSTEMC_LATEST_TAG="$(git ls-remote --tags --refs https://github.com/accellera-official/systemc.git | awk -F/ '{print $3}' | latest_stable_tag)"
SLANG_VERSION="v11.0"
SVLENS_VERSION="v0.3.6"
: "${VERILATOR_LATEST_TAG:?No Verilator release tag found}"
: "${VERIBLE_LATEST_TAG:?No Verible release tag found}"
: "${SYSTEMC_LATEST_TAG:?No SystemC release tag found}"
: "${SLANG_VERSION:?SLANG_VERSION must be pinned}"
: "${SVLENS_VERSION:?SVLENS_VERSION must be pinned}"
echo "Verilator latest stable candidate: ${VERILATOR_LATEST_TAG}"
echo "Verible latest stable candidate: ${VERIBLE_LATEST_TAG}"
echo "slang compatible pin: ${SLANG_VERSION}"
echo "svlens compatible pin: ${SVLENS_VERSION}"
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
      GXX_OUTPUT="$(g++ --version 2>&1)"
      GXX_RC=$?
      printf 'Activated gcc-toolset-%s: ' "$VER"
      printf '%s\n' "$GXX_OUTPUT" | sed -n '1p'
      [ "$GXX_RC" -eq 0 ] || exit "$GXX_RC"
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
#!/usr/bin/env bash
set -euo pipefail

CLAUDE_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || true)}"
SLANG_SERVER_INSTALLER="${CLAUDE_PLUGIN_ROOT}/scripts/install-slang-server.sh"
[[ -f "$SLANG_SERVER_INSTALLER" ]] || { echo "Cannot find rtl-agent-team slang-server installer" >&2; exit 1; }

latest_stable_tag() {
  python3 -c 'import re, sys; tags = [tag.strip() for tag in sys.stdin if tag.strip() and not re.search(r"(?:alpha|beta|rc)", tag, re.I)]; key = lambda tag: tuple((1, int(part)) if part.isdigit() else (0, part.lower()) for part in re.split(r"(\d+)", tag)); tags or sys.exit("no stable tag found"); print(max(tags, key=key))'
}
VERILATOR_LATEST_TAG="$(git ls-remote --tags --refs https://github.com/verilator/verilator.git 'v*' | awk -F/ '{print $3}' | latest_stable_tag)"
VERIBLE_LATEST_TAG="$(git ls-remote --tags --refs https://github.com/chipsalliance/verible.git 'v*' | awk -F/ '{print $3}' | latest_stable_tag)"
SYSTEMC_LATEST_TAG="$(git ls-remote --tags --refs https://github.com/accellera-official/systemc.git | awk -F/ '{print $3}' | latest_stable_tag)"
SLANG_VERSION="v11.0"
SVLENS_VERSION="v0.3.6"
: "${VERILATOR_LATEST_TAG:?No Verilator release tag found}"
: "${VERIBLE_LATEST_TAG:?No Verible release tag found}"
: "${SYSTEMC_LATEST_TAG:?No SystemC release tag found}"

# ===== PATH bootstrap =====
for tool in git curl python3 cmake; do
  command -v "$tool" >/dev/null 2>&1 || { echo "Missing prerequisite: $tool" >&2; exit 1; }
done
python3 -m venv --help >/dev/null 2>&1 || { echo "Missing prerequisite: python3-venv" >&2; exit 1; }
RAT_EDA_VENV="$HOME/.local/share/rtl-agent-team/venv"
mkdir -p "$HOME/.local/bin" "$HOME/.local/lib" "$HOME/tools" "$(dirname "$RAT_EDA_VENV")"
python3 -m venv "$RAT_EDA_VENV"
export PATH="$RAT_EDA_VENV/bin:$HOME/.local/bin:$PATH"
PROFILE_LINE='export PATH="$HOME/.local/share/rtl-agent-team/venv/bin:$HOME/.local/bin:$PATH"'
touch "$HOME/.profile"
grep -Fqx "$PROFILE_LINE" "$HOME/.profile" || printf '%s\n' "$PROFILE_LINE" >> "$HOME/.profile"

# ===== Verilator (source build → ~/.local) =====
git clone https://github.com/verilator/verilator.git "$HOME/tools/verilator-src"
cd "$HOME/tools/verilator-src"
git fetch --tags
git checkout "$VERILATOR_LATEST_TAG"
autoconf
./configure --prefix="$HOME/.local"
make -j"$(nproc)"
make install
verilator --version

# ===== Verible (prebuilt binary) =====
case "$(uname -m)" in
  x86_64) VERIBLE_ARCH="x86_64" ;;
  aarch64|arm64) VERIBLE_ARCH="arm64" ;;
  *) echo "Unsupported Verible architecture: $(uname -m)" >&2; exit 1 ;;
esac
VERIBLE_DIR="$HOME/tools/verible-${VERIBLE_LATEST_TAG}"
VERIBLE_ARCHIVE="$HOME/tools/verible-${VERIBLE_LATEST_TAG}-linux-static-${VERIBLE_ARCH}.tar.gz"
curl -fsSL "https://github.com/chipsalliance/verible/releases/download/${VERIBLE_LATEST_TAG}/verible-${VERIBLE_LATEST_TAG}-linux-static-${VERIBLE_ARCH}.tar.gz" -o "$VERIBLE_ARCHIVE"
mkdir -p "$VERIBLE_DIR"
tar xzf "$VERIBLE_ARCHIVE" -C "$VERIBLE_DIR" --strip-components=1
ln -sf "$VERIBLE_DIR/bin/verible-verilog-lint" "$HOME/.local/bin/verible-verilog-lint"
ln -sf "$VERIBLE_DIR/bin/verible-verilog-format" "$HOME/.local/bin/verible-verilog-format"

# ===== slang (official source build) =====
git clone --depth 1 --branch "$SLANG_VERSION" https://github.com/MikePopoloski/slang.git "$HOME/tools/slang-src"
cmake -S "$HOME/tools/slang-src" -B "$HOME/tools/slang-src/build" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$HOME/.local" \
  -DSLANG_INCLUDE_TESTS=OFF
cmake --build "$HOME/tools/slang-src/build" -j"$(nproc)"
cmake --install "$HOME/tools/slang-src/build"

# ===== svlens (structural analysis: CDC + connectivity + metrics) =====
git clone --depth 1 --branch "$SVLENS_VERSION" https://github.com/babyworm/svlens.git "$HOME/tools/svlens"
cmake -S "$HOME/tools/svlens" -B "$HOME/tools/svlens/build" -DCMAKE_PREFIX_PATH="$HOME/.local"
cmake --build "$HOME/tools/svlens/build" -j"$(nproc)"
cmake --install "$HOME/tools/svlens/build" --prefix "$HOME/.local"
# Binary installs to ~/.local/bin/svlens

# ===== slang-server (SystemVerilog LSP for Claude Code) =====
bash "$SLANG_SERVER_INSTALLER" install

# ===== cocotb (managed virtual environment) =====
"$RAT_EDA_VENV/bin/python" -m pip install cocotb

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
# Official installation guide: https://yosyshq.readthedocs.io/projects/sby/en/latest/install.html
case "$(uname -m)" in
  x86_64) OSS_CAD_ARCH="linux-x64" ;;
  aarch64|arm64) OSS_CAD_ARCH="linux-arm64" ;;
  *) echo "Unsupported OSS CAD Suite architecture: $(uname -m)" >&2; exit 1 ;;
esac
OSS_CAD_TAG="2025-02-01"
OSS_CAD_DATE="${OSS_CAD_TAG//-/}"
curl -fsSL "https://github.com/YosysHQ/oss-cad-suite-build/releases/download/${OSS_CAD_TAG}/oss-cad-suite-${OSS_CAD_ARCH}-${OSS_CAD_DATE}.tgz" -o "$HOME/tools/oss-cad-suite.tgz"
tar xzf "$HOME/tools/oss-cad-suite.tgz" -C "$HOME/tools"
rm -f "$HOME/tools/oss-cad-suite.tgz"
ln -sf "$HOME/tools/oss-cad-suite/bin/yosys" "$HOME/.local/bin/yosys"
ln -sf "$HOME/tools/oss-cad-suite/bin/sby" "$HOME/.local/bin/sby"
```

## Mode: `global` (print commands for user to run manually — requires sudo)

```bash
#!/bin/bash
# RTL Agent Team — Global Install Script
# Run this manually with sudo access, then re-run /rtl-agent-team:rat-setup to verify.

set -euo pipefail

sudo apt update
sudo apt install -y git curl help2man perl python3 python3-pip python3-venv make autoconf \
  g++ flex bison ccache libfl2 libfl-dev zlib1g zlib1g-dev cmake

sudo apt install -y iverilog gtkwave jq

latest_stable_tag() {
  python3 -c 'import re, sys; tags = [tag.strip() for tag in sys.stdin if tag.strip() and not re.search(r"(?:alpha|beta|rc)", tag, re.I)]; key = lambda tag: tuple((1, int(part)) if part.isdigit() else (0, part.lower()) for part in re.split(r"(\d+)", tag)); tags or sys.exit("no stable tag found"); print(max(tags, key=key))'
}
VERILATOR_LATEST_TAG="$(git ls-remote --tags --refs https://github.com/verilator/verilator.git 'v*' | awk -F/ '{print $3}' | latest_stable_tag)"
VERIBLE_LATEST_TAG="$(git ls-remote --tags --refs https://github.com/chipsalliance/verible.git 'v*' | awk -F/ '{print $3}' | latest_stable_tag)"
SYSTEMC_LATEST_TAG="$(git ls-remote --tags --refs https://github.com/accellera-official/systemc.git | awk -F/ '{print $3}' | latest_stable_tag)"
SLANG_VERSION="v11.0"
SVLENS_VERSION="v0.3.6"
: "${VERILATOR_LATEST_TAG:?No Verilator release tag found}"
: "${VERIBLE_LATEST_TAG:?No Verible release tag found}"
: "${SYSTEMC_LATEST_TAG:?No SystemC release tag found}"

# Verilator (source build — distro packages are often outdated)
VERILATOR_TAG="${1:-$VERILATOR_LATEST_TAG}"
: "${VERILATOR_TAG:?VERILATOR_TAG must not be empty}"
git clone https://github.com/verilator/verilator.git /tmp/verilator-src
cd /tmp/verilator-src && git checkout "$VERILATOR_TAG"
autoconf && ./configure && make -j"$(nproc)" && sudo make install

# Verible (official prebuilt release)
VERIBLE_TAG="${3:-${VERIBLE_LATEST_TAG:?Run version discovery first}}"
: "${VERIBLE_TAG:?VERIBLE_TAG must not be empty}"
case "$(uname -m)" in
  x86_64) VERIBLE_ARCH="x86_64" ;;
  aarch64|arm64) VERIBLE_ARCH="arm64" ;;
  *) echo "Unsupported Verible architecture: $(uname -m)" >&2; exit 1 ;;
esac
mkdir -p /tmp/verible-bin
curl -fsSL "https://github.com/chipsalliance/verible/releases/download/${VERIBLE_TAG}/verible-${VERIBLE_TAG}-linux-static-${VERIBLE_ARCH}.tar.gz" -o /tmp/verible.tar.gz
tar xzf /tmp/verible.tar.gz -C /tmp/verible-bin --strip-components=1
sudo install /tmp/verible-bin/bin/verible-verilog-lint /tmp/verible-bin/bin/verible-verilog-format /usr/local/bin/

# slang (official source build)
SLANG_TAG="${4:-${SLANG_VERSION:-v11.0}}"
: "${SLANG_TAG:?SLANG_TAG must not be empty}"
git clone --depth 1 --branch "$SLANG_TAG" https://github.com/MikePopoloski/slang.git /tmp/slang-src
cmake -S /tmp/slang-src -B /tmp/slang-src/build -DCMAKE_BUILD_TYPE=Release -DSLANG_INCLUDE_TESTS=OFF
cmake --build /tmp/slang-src/build -j"$(nproc)"
sudo cmake --install /tmp/slang-src/build

# svlens (required open-source CDC fallback)
: "${SVLENS_VERSION:=v0.3.6}"
: "${SVLENS_VERSION:?SVLENS_VERSION must not be empty}"
git clone --depth 1 --branch "$SVLENS_VERSION" https://github.com/babyworm/svlens.git /tmp/svlens
cmake -S /tmp/svlens -B /tmp/svlens/build -DCMAKE_PREFIX_PATH=/usr/local
cmake --build /tmp/svlens/build -j"$(nproc)"
sudo cmake --install /tmp/svlens/build

# cocotb (managed virtual environment)
RAT_EDA_VENV="/opt/rtl-agent-team-venv"
sudo python3 -m venv "$RAT_EDA_VENV"
sudo "$RAT_EDA_VENV/bin/python" -m pip install cocotb
export PATH="$RAT_EDA_VENV/bin:$PATH"
printf '%s\n' 'export PATH="/opt/rtl-agent-team-venv/bin:$PATH"' | sudo tee /etc/profile.d/rtl-agent-team-venv.sh >/dev/null

# SystemC/TLM-2.0
SYSTEMC_TAG="${2:-${SYSTEMC_LATEST_TAG:?Run version discovery first}}"
: "${SYSTEMC_TAG:?SYSTEMC_TAG must not be empty}"
git clone --depth 1 --branch "$SYSTEMC_TAG" https://github.com/accellera-official/systemc.git /tmp/systemc-src
cd /tmp/systemc-src
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j"$(nproc)" && sudo cmake --install build

echo "Done. Re-run /rtl-agent-team:rat-setup to verify installation."
```

## macOS (Homebrew)

```bash
#!/usr/bin/env bash
set -euo pipefail

brew tap chipsalliance/verible
brew install bash python curl git verilator verible icarus-verilog gtkwave jq cmake
MODERN_BASH="$(brew --prefix)/bin/bash"
"$MODERN_BASH" -c '(( BASH_VERSINFO[0] >= 4 ))' || { echo "Bash 4 or newer is required" >&2; exit 1; }
BREW_BIN="$(brew --prefix)/bin"
RAT_EDA_VENV="$HOME/.local/share/rtl-agent-team/venv"
mkdir -p "$HOME/.local/bin" "$HOME/tools" "$(dirname "$RAT_EDA_VENV")"
"$BREW_BIN/python3" -m venv "$RAT_EDA_VENV"
export PATH="$RAT_EDA_VENV/bin:$HOME/.local/bin:$BREW_BIN:$PATH"
PATH_LINE="export PATH=\"$RAT_EDA_VENV/bin:$HOME/.local/bin:$BREW_BIN:\$PATH\""
touch "$HOME/.zprofile"
grep -Fqx "$PATH_LINE" "$HOME/.zprofile" || printf '%s\n' "$PATH_LINE" >> "$HOME/.zprofile"
"$RAT_EDA_VENV/bin/python" -m pip install cocotb
JOBS="$(sysctl -n hw.ncpu)"
latest_stable_tag() {
  "$BREW_BIN/python3" -c 'import re, sys; tags = [tag.strip() for tag in sys.stdin if tag.strip() and not re.search(r"(?:alpha|beta|rc)", tag, re.I)]; key = lambda tag: tuple((1, int(part)) if part.isdigit() else (0, part.lower()) for part in re.split(r"(\d+)", tag)); tags or sys.exit("no stable tag found"); print(max(tags, key=key))'
}
SYSTEMC_LATEST_TAG="$(git ls-remote --tags --refs https://github.com/accellera-official/systemc.git | awk -F/ '{print $3}' | latest_stable_tag)"
: "${SYSTEMC_LATEST_TAG:?No SystemC release tag found}"
: "${SLANG_VERSION:=v11.0}"
: "${SLANG_VERSION:?SLANG_VERSION must not be empty}"
: "${SVLENS_VERSION:=v0.3.6}"
: "${SVLENS_VERSION:?SVLENS_VERSION must not be empty}"

# slang (official source build)
git clone --depth 1 --branch "$SLANG_VERSION" https://github.com/MikePopoloski/slang.git "$HOME/tools/slang-src"
cmake -S "$HOME/tools/slang-src" -B "$HOME/tools/slang-src/build" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$HOME/.local" \
  -DSLANG_INCLUDE_TESTS=OFF
cmake --build "$HOME/tools/slang-src/build" -j"$JOBS"
cmake --install "$HOME/tools/slang-src/build"

# svlens (required open-source CDC fallback)
git clone --depth 1 --branch "$SVLENS_VERSION" https://github.com/babyworm/svlens.git "$HOME/tools/svlens"
cmake -S "$HOME/tools/svlens" -B "$HOME/tools/svlens/build" -DCMAKE_PREFIX_PATH="$HOME/.local"
cmake --build "$HOME/tools/svlens/build" -j"$JOBS"
cmake --install "$HOME/tools/svlens/build" --prefix "$HOME/.local"

# SystemC/TLM-2.0 (resolved source release)
git clone --depth 1 --branch "$SYSTEMC_LATEST_TAG" https://github.com/accellera-official/systemc.git "$HOME/tools/systemc-src"
cmake -S "$HOME/tools/systemc-src" -B "$HOME/tools/systemc-src/build" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$HOME/.local"
cmake --build "$HOME/tools/systemc-src/build" -j"$JOBS"
cmake --install "$HOME/tools/systemc-src/build"
export SYSTEMC_HOME="$HOME/.local"
```

## Docker fallback

```bash
docker build -t rtl-eda-tools "${CLAUDE_PLUGIN_ROOT}/docker/"
```
