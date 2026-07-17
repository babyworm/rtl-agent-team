#!/bin/bash
# RTL Agent Team - Post-Install Environment Check
# Run once after plugin installation to verify EDA toolchain availability.
# Non-destructive: reports status only, does not install anything.

set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo " RTL Agent Team - Environment Check"
echo "=========================================="
echo ""

REQUIRED_FOUND=0
REQUIRED_TOTAL=0
OPTIONAL_FOUND=0
OPTIONAL_TOTAL=0
MISSING_REQUIRED=()
CHECK_TOOL_OK=0

check_tool() {
  local name="$1"
  local cmd="$2"
  local required="$3"
  local purpose="$4"

  if [ "$required" = "yes" ]; then
    REQUIRED_TOTAL=$((REQUIRED_TOTAL + 1))
  else
    OPTIONAL_TOTAL=$((OPTIONAL_TOTAL + 1))
  fi

  local output
  if output=$(eval "$cmd" 2>&1); then
    CHECK_TOOL_OK=1
    local version
    version=$(printf '%s\n' "$output" | sed -n '1p')
    if [ "$required" = "yes" ]; then
      REQUIRED_FOUND=$((REQUIRED_FOUND + 1))
    else
      OPTIONAL_FOUND=$((OPTIONAL_FOUND + 1))
    fi
    printf "  ${GREEN}[OK]${NC}  %-20s %s\n" "$name" "$version"
  else
    CHECK_TOOL_OK=0
    if [ "$required" = "yes" ]; then
      MISSING_REQUIRED+=("$name ($purpose)")
      printf "  ${RED}[MISSING]${NC} %-20s %s\n" "$name" "$purpose"
    else
      printf "  ${YELLOW}[--]${NC}  %-20s %s (optional)\n" "$name" "$purpose"
    fi
  fi
}

echo "Required Tools:"
check_tool "verilator" "verilator --version" "yes" "Simulation + Lint"
check_tool "cocotb" "python3 -c 'import cocotb; print(cocotb.__version__)'" "yes" "Functional verification"
check_tool "python3" "python3 --version" "yes" "cocotb runtime"
check_tool "gcc/g++" "g++ --version" "yes" "Ref model build"
check_tool "make" "make --version" "yes" "Build system"
_check_systemc() {
  pkg-config --modversion systemc 2>/dev/null && return 0
  if [ -n "${SYSTEMC_HOME:-}" ] && [ -d "${SYSTEMC_HOME:-}" ]; then
    echo "found via SYSTEMC_HOME"
    return 0
  fi
  return 1
}
check_tool "systemc" "_check_systemc" "yes" "SystemC/TLM-2.0 (ref model + BFM)"

echo ""
echo "Lint Tools (at least one required):"
check_tool "verible" "verible-verilog-lint --version" "no" "Style Lint"
VERIBLE_OK=$CHECK_TOOL_OK
check_tool "slang" "slang --version" "no" "Lint + parsing"
SLANG_OK=$CHECK_TOOL_OK
REQUIRED_TOTAL=$((REQUIRED_TOTAL + 1))
if [ "$VERIBLE_OK" -eq 1 ] || [ "$SLANG_OK" -eq 1 ]; then
  REQUIRED_FOUND=$((REQUIRED_FOUND + 1))
else
  printf '  %b[!!]%b  %-20s %s\n' "$RED" "$NC" "LINT GATE" "FAILED: install at least one of verible or slang"
  MISSING_REQUIRED+=("verible/slang (at least one lint tool)")
fi

echo ""
echo "CDC Tools (at least one required):"
check_tool "svlens" "svlens --version" "no" "Open-source CDC + structural analysis"
SVLENS_OK=$CHECK_TOOL_OK
check_tool "sg_shell" "command -v sg_shell" "no" "SpyGlass CDC"
SG_SHELL_OK=$CHECK_TOOL_OK
check_tool "vc_cdc" "command -v vc_cdc" "no" "VC CDC"
VC_CDC_OK=$CHECK_TOOL_OK
check_tool "questa_cdc" "command -v questa_cdc" "no" "Questa CDC"
QUESTA_CDC_OK=$CHECK_TOOL_OK
REQUIRED_TOTAL=$((REQUIRED_TOTAL + 1))
if [ "$SVLENS_OK" -eq 1 ] || [ "$SG_SHELL_OK" -eq 1 ] || \
   [ "$VC_CDC_OK" -eq 1 ] || [ "$QUESTA_CDC_OK" -eq 1 ]; then
  REQUIRED_FOUND=$((REQUIRED_FOUND + 1))
else
  printf '  %b[!!]%b  %-20s %s\n' "$RED" "$NC" "CDC GATE" "FAILED: install svlens or a supported commercial CDC tool"
  MISSING_REQUIRED+=("svlens/commercial CDC (at least one CDC tool)")
fi

echo ""
echo "Optional Tools:"
check_tool "yosys" "yosys -V" "no" "Synthesis (Phase 5B+)"
check_tool "iverilog" "iverilog -V" "no" "Alternative simulator"
check_tool "sby" "sby --help" "no" "Formal verification"
check_tool "slang-server" "slang-server --version" "no" "SV Language Server"
check_tool "gtkwave" "gtkwave --version" "no" "Waveform viewer"
check_tool "sv2v" "sv2v --version" "no" "SV to Verilog conversion"

echo ""
echo "=========================================="
echo " Summary"
echo "=========================================="
echo "  Required: ${REQUIRED_FOUND}/${REQUIRED_TOTAL} installed"
echo "  Optional: ${OPTIONAL_FOUND}/${OPTIONAL_TOTAL} installed"

if [ ${#MISSING_REQUIRED[@]} -gt 0 ]; then
  echo ""
  printf '  %bMissing required tools:%b\n' "$RED" "$NC"
  for tool in "${MISSING_REQUIRED[@]}"; do
    echo "    - $tool"
  done
  echo ""
  echo "  Install with:"
  echo "    sudo apt install verilator iverilog gtkwave build-essential python3-pip"
  echo "    python3 -m venv \"$HOME/.local/share/rtl-agent-team/venv\""
  echo "    \"$HOME/.local/share/rtl-agent-team/venv/bin/python\" -m pip install cocotb"
  echo "    # Yosys: https://github.com/YosysHQ/oss-cad-suite-build"
  echo "    # Verible: https://github.com/chipsalliance/verible/releases"
fi

# Python version check
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || { [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]; }; then
  printf '\n  %bWARNING:%b Python 3.9+ required (found %s)\n' "$RED" "$NC" "$PYTHON_VERSION"
fi

# Docker suggestion
if command -v docker > /dev/null 2>&1; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
  if [ -d "$PLUGIN_ROOT/docker" ]; then
    echo ""
    echo "  Docker detected. You can build an all-in-one EDA image:"
    printf '    docker build -t rtl-eda-tools "%s/docker/"\n' "$PLUGIN_ROOT"
  fi
fi

echo ""
echo "=========================================="
