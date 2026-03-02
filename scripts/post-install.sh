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

  if eval "$cmd" > /dev/null 2>&1; then
    local version
    version=$(eval "$cmd" 2>&1 | head -1)
    if [ "$required" = "yes" ]; then
      REQUIRED_FOUND=$((REQUIRED_FOUND + 1))
    else
      OPTIONAL_FOUND=$((OPTIONAL_FOUND + 1))
    fi
    printf "  ${GREEN}[OK]${NC}  %-20s %s\n" "$name" "$version"
  else
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
check_tool "verible" "verible-verilog-lint --version" "yes" "Style Lint"
check_tool "yosys" "yosys -V" "yes" "Synthesis"
check_tool "cocotb" "python3 -c 'import cocotb; print(cocotb.__version__)'" "yes" "Functional verification"
check_tool "python3" "python3 --version" "yes" "cocotb runtime"
check_tool "gcc/g++" "g++ --version" "yes" "Ref model build"
check_tool "make" "make --version" "yes" "Build system"

echo ""
echo "Optional Tools:"
check_tool "iverilog" "iverilog -V" "no" "Alternative simulator"
check_tool "sby" "sby --help" "no" "Formal verification"
check_tool "slang" "slang --version" "no" "Advanced lint"
check_tool "slang-server" "slang-server --version" "no" "SV Language Server"
check_tool "gtkwave" "gtkwave --version" "no" "Waveform viewer"
check_tool "sv2v" "sv2v --version" "no" "SV to Verilog conversion"
check_tool "systemc" "pkg-config --modversion systemc" "no" "SystemC/TLM-2.0"

echo ""
echo "=========================================="
echo " Summary"
echo "=========================================="
echo "  Required: ${REQUIRED_FOUND}/${REQUIRED_TOTAL} installed"
echo "  Optional: ${OPTIONAL_FOUND}/${OPTIONAL_TOTAL} installed"

if [ ${#MISSING_REQUIRED[@]} -gt 0 ]; then
  echo ""
  printf "  ${RED}Missing required tools:${NC}\n"
  for tool in "${MISSING_REQUIRED[@]}"; do
    echo "    - $tool"
  done
  echo ""
  echo "  Install with:"
  echo "    sudo apt install verilator iverilog gtkwave build-essential python3-pip"
  echo "    pip3 install cocotb"
  echo "    # Yosys: https://github.com/YosysHQ/oss-cad-suite-build"
  echo "    # Verible: https://github.com/chipsalliance/verible/releases"
fi

# Python version check
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
  printf "\n  ${RED}WARNING:${NC} Python 3.9+ required (found $PYTHON_VERSION)\n"
fi

# Docker suggestion
if command -v docker > /dev/null 2>&1; then
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  PLUGIN_ROOT="$(dirname "$SCRIPT_DIR")"
  if [ -d "$PLUGIN_ROOT/docker" ]; then
    echo ""
    echo "  Docker detected. You can build an all-in-one EDA image:"
    echo "    docker build -t rtl-eda-tools $PLUGIN_ROOT/docker/"
  fi
fi

echo ""
echo "=========================================="
