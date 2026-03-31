#!/usr/bin/env bash
# generate_config.sh — Generate rat_config.json with EDA tool auto-detection
#
# Usage: generate_config.sh [project_root] [project_name]
#
# Detects available EDA tools (checking PATH and env_setup sourcing scripts),
# extracts NAND2 area from liberty file if specified, and writes rat_config.json.
#
# If rat_config.json already exists, only updates tool availability (preserves
# user-edited fields like liberty, waivers, env_setup, coverage targets).

set -euo pipefail

PROJECT_ROOT="${1:-.}"
PROJECT_NAME="${2:-$(basename "$(cd "$PROJECT_ROOT" && pwd)")}"
CONFIG="$PROJECT_ROOT/rat_config.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="$(cd "$SCRIPT_DIR/.." && pwd)/templates/rat_config.json"

# ─── Helpers ────────────────────────────────────────────────────────────────

# Check if a tool is available, optionally sourcing env_setup first
# Args: tool_name [env_setup_cmd]
tool_available() {
  local tool="$1"
  local env_cmd="${2:-}"

  if [[ -n "$env_cmd" ]]; then
    # Source in subshell and check
    (eval "$env_cmd" 2>/dev/null && command -v "$tool" >/dev/null 2>&1)
  else
    command -v "$tool" >/dev/null 2>&1
  fi
}

# Read a JSON string field using grep+sed (no jq dependency)
json_get() {
  local file="$1" key="$2"
  sed -n "s/.*\"${key}\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$file" | head -1
}

# ─── Load existing config (if any) for env_setup ───────────────────────────
declare -A ENV_SETUP=()
if [[ -f "$CONFIG" ]]; then
  for tool in vcs xrun vsim dc_shell genus sg_shell sby verilator slang; do
    val=$(json_get "$CONFIG" "$tool")
    [[ -n "$val" ]] && ENV_SETUP[$tool]="$val"
  done
fi

# ─── Detect tools ──────────────────────────────────────────────────────────
# Detect tools in a category, writing results to global vars
# Sets: _DET_TOOLS (array), _DET_PREF (string)
detect_category() {
  _DET_TOOLS=()
  _DET_PREF=""
  local tools=("$@")

  for tool in "${tools[@]}"; do
    if tool_available "$tool" "${ENV_SETUP[$tool]:-}"; then
      _DET_TOOLS+=("$tool")
      if [[ -z "$_DET_PREF" ]]; then _DET_PREF="$tool"; fi
    fi
  done
  return 0
}

echo "=== EDA Tool Detection ==="

detect_category vcs xrun vsim
SIM_TOOLS=("${_DET_TOOLS[@]}"); SIM_PREF="$_DET_PREF"
echo "Simulators: [${SIM_TOOLS[*]:-none}] (preferred: ${SIM_PREF:-none})"

detect_category yosys dc_shell genus
SYN_TOOLS=("${_DET_TOOLS[@]}"); SYN_PREF="$_DET_PREF"
echo "Synthesis:  [${SYN_TOOLS[*]:-none}] (preferred: ${SYN_PREF:-none})"

detect_category verilator verible-verilog-lint slang sg_shell
LINT_TOOLS=("${_DET_TOOLS[@]}"); LINT_PREF="$_DET_PREF"
# Normalize verible binary name
LINT_TOOLS=("${LINT_TOOLS[@]/verible-verilog-lint/verible}")
if [[ "$LINT_PREF" == "verible-verilog-lint" ]]; then LINT_PREF="verible"; fi
echo "Lint:       [${LINT_TOOLS[*]:-none}] (preferred: ${LINT_PREF:-none})"

detect_category sby
FORMAL_TOOLS=("${_DET_TOOLS[@]}"); FORMAL_PREF="$_DET_PREF"
echo "Formal:     [${FORMAL_TOOLS[*]:-none}] (preferred: ${FORMAL_PREF:-none})"

detect_category slang-cdc sg_shell
CDC_TOOLS=("structural" "${_DET_TOOLS[@]}"); CDC_PREF="${_DET_PREF:-structural}"
echo "CDC:        [${CDC_TOOLS[*]}] (preferred: $CDC_PREF)"

# ─── Format JSON arrays ───────────────────────────────────────────────────
json_array() {
  local arr=("$@")
  if [[ ${#arr[@]} -eq 0 ]]; then
    echo "[]"
    return
  fi
  local out="["
  for i in "${!arr[@]}"; do
    [[ $i -gt 0 ]] && out+=", "
    out+="\"${arr[$i]}\""
  done
  out+="]"
  echo "$out"
}

SIM_ARR=$(json_array "${SIM_TOOLS[@]}")
SYN_ARR=$(json_array "${SYN_TOOLS[@]}")
LINT_ARR=$(json_array "${LINT_TOOLS[@]}")
FORMAL_ARR=$(json_array "${FORMAL_TOOLS[@]}")
CDC_ARR=$(json_array "${CDC_TOOLS[@]}")

# ─── Preserve user fields from existing config ─────────────────────────────
if [[ -f "$CONFIG" ]]; then
  # Preserve user-edited fields
  LIBERTY=$(json_get "$CONFIG" "liberty")
  SRAM_LIB=$(json_get "$CONFIG" "sram_lib")
  TARGET=$(json_get "$CONFIG" "target")
  NAND2_PATTERN=$(json_get "$CONFIG" "nand2_cell_pattern")
  TOP_MODULE=$(json_get "$CONFIG" "top_module")
  FILELIST=$(json_get "$CONFIG" "filelist")
  SEEDS=$(json_get "$CONFIG" "seeds")
  # Preserve waivers
  W_VERILATOR=$(json_get "$CONFIG" "verilator")  # under waivers context
  W_VERIBLE=$(json_get "$CONFIG" "verible")
  W_SG_LINT=$(json_get "$CONFIG" "spyglass_lint")
  W_SG_CDC=$(json_get "$CONFIG" "spyglass_cdc")
  W_CDC=$(json_get "$CONFIG" "cdc")
  echo "Preserving user-edited fields from existing config"
else
  LIBERTY=""
  SRAM_LIB=""
  TARGET=""
  NAND2_PATTERN="NAND2X1"
  TOP_MODULE=""
  FILELIST="rtl/filelist_top.f"
  SEEDS="42 123 456 789 1337"
  W_VERILATOR=""
  W_VERIBLE=""
  W_SG_LINT=""
  W_SG_CDC=""
  W_CDC=""
fi

# ─── NAND2 area extraction from liberty ────────────────────────────────────
NAND2_AREA="null"
NAND2_NOTE=""
if [[ -n "$LIBERTY" && -f "$LIBERTY" ]]; then
  NAND2_PAT="${NAND2_PATTERN:-NAND2X1}"
  # Parse liberty: find cell(<pattern>) { ... area : <value>; ... }
  EXTRACTED=$(awk -v pat="$NAND2_PAT" '
    $0 ~ "cell[[:space:]]*\\("pat"\\)" { found=1 }
    found && /area[[:space:]]*:/ {
      gsub(/[^0-9.]/, "", $NF)
      print $NF
      exit
    }
    found && /^\s*\}/ { found=0 }
  ' "$LIBERTY")

  if [[ -n "$EXTRACTED" ]]; then
    NAND2_AREA="$EXTRACTED"
    NAND2_NOTE=" (extracted from liberty: $NAND2_PAT)"
    echo "NAND2 area: ${EXTRACTED} um2${NAND2_NOTE}"
  else
    echo "WARNING: $NAND2_PAT not found in $LIBERTY — using null (will default to 0.798 NanGate45)"
  fi
else
  if [[ -n "$LIBERTY" ]]; then
    echo "WARNING: Liberty file not found: $LIBERTY"
  fi
fi

# ─── Preserve env_setup from existing config ───────────────────────────────
ES_VCS="${ENV_SETUP[vcs]:-}"
ES_XRUN="${ENV_SETUP[xrun]:-}"
ES_VSIM="${ENV_SETUP[vsim]:-}"
ES_DC="${ENV_SETUP[dc_shell]:-}"
ES_GENUS="${ENV_SETUP[genus]:-}"
ES_SG="${ENV_SETUP[sg_shell]:-}"
ES_SBY="${ENV_SETUP[sby]:-}"
ES_VERILATOR="${ENV_SETUP[verilator]:-}"
ES_SLANG="${ENV_SETUP[slang]:-}"

# ─── Write config ──────────────────────────────────────────────────────────
cat > "$CONFIG" << CONFIG_EOF
{
  "project": {
    "name": "$PROJECT_NAME",
    "top_module": "$TOP_MODULE",
    "filelist": "$FILELIST"
  },
  "env_setup": {
    "_comment": "Shell commands to source before running each tool. Leave empty if tool is already in PATH.",
    "vcs": "$ES_VCS",
    "xrun": "$ES_XRUN",
    "vsim": "$ES_VSIM",
    "dc_shell": "$ES_DC",
    "genus": "$ES_GENUS",
    "sg_shell": "$ES_SG",
    "sby": "$ES_SBY",
    "verilator": "$ES_VERILATOR",
    "slang": "$ES_SLANG"
  },
  "tools": {
    "simulator":  { "preferred": "${SIM_PREF:-}", "available": $SIM_ARR },
    "synthesis":  { "preferred": "${SYN_PREF:-}", "available": $SYN_ARR },
    "lint":       { "preferred": "${LINT_PREF:-}", "available": $LINT_ARR },
    "formal":     { "preferred": "${FORMAL_PREF:-}", "available": $FORMAL_ARR },
    "cdc":        { "preferred": "$CDC_PREF", "available": $CDC_ARR }
  },
  "technology": {
    "target": "$TARGET",
    "liberty": "$LIBERTY",
    "sram_lib": "$SRAM_LIB",
    "nand2_cell_pattern": "${NAND2_PATTERN:-NAND2X1}",
    "nand2_area_um2": $NAND2_AREA
  },
  "coverage": {
    "targets": { "line": 90, "toggle": 80, "fsm": 70, "branch": 80, "functional": 95 },
    "seeds": "$SEEDS",
    "max_fail_rate": 5
  },
  "waivers": {
    "verilator": "$W_VERILATOR",
    "verible": "$W_VERIBLE",
    "spyglass_lint": "$W_SG_LINT",
    "spyglass_cdc": "$W_SG_CDC",
    "cdc": "$W_CDC"
  }
}
CONFIG_EOF

echo ""
echo "Config written: $CONFIG"
echo "  Edit env_setup to add tool sourcing scripts (e.g., \"source /tools/synopsys/vcs/setup.sh\")"
echo "  Edit technology.liberty to set target library path"
echo "  Re-run to refresh tool detection (user fields preserved)"
