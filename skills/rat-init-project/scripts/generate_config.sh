#!/usr/bin/env bash
# generate_config.sh — Generate rat_config.json with EDA tool auto-detection
#
# Usage: generate_config.sh [project_root] [project_name]
#
# Detects all known EDA tools, records path for each, extracts NAND2 area
# from liberty if specified. Tools not in PATH get empty fields that users
# can fill in with 'path' or 'env_source' to enable detection on re-run.
#
# If rat_config.json already exists, preserves user-edited fields (env_source,
# path overrides, technology, waivers, coverage). Only refreshes 'detected'.

set -euo pipefail

PROJECT_ROOT="${1:-.}"
PROJECT_NAME="${2:-$(basename "$(cd "$PROJECT_ROOT" && pwd)")}"
CONFIG="$PROJECT_ROOT/rat_config.json"

# ─── Helpers ────────────────────────────────────────────────────────────────

# Read a JSON string value by key (simple grep-based, no jq dependency)
json_get() {
  local file="$1" key="$2"
  sed -n "s/.*\"${key}\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p" "$file" | head -1
}

# Read env_source for a tool from existing config (nested under category)
json_get_tool_field() {
  local file="$1" tool="$2" field="$3"
  # Match: "tool": { ... "field": "value" ... } — simplified line-by-line
  awk -v tool="\"$tool\"" -v field="\"$field\"" '
    $0 ~ tool { found=1 }
    found && $0 ~ field {
      gsub(/.*: *"/, ""); gsub(/".*/, ""); print; exit
    }
    found && /\}/ { found=0 }
  ' "$file"
}

# Check if a tool is available, optionally sourcing env first or using explicit path
# Args: tool_name env_source_cmd explicit_path
tool_detect() {
  local tool="$1" env_cmd="${2:-}" explicit_path="${3:-}"

  # Try explicit path first
  if [[ -n "$explicit_path" && -x "$explicit_path" ]]; then
    echo "$explicit_path"
    return 0
  fi

  # Try with env_source
  if [[ -n "$env_cmd" ]]; then
    local found
    found=$(bash -c "$env_cmd 2>/dev/null && command -v $tool 2>/dev/null" 2>/dev/null) || true
    if [[ -n "$found" ]]; then
      echo "$found"
      return 0
    fi
  fi

  # Try PATH directly
  local path
  path=$(command -v "$tool" 2>/dev/null) || true
  if [[ -n "$path" ]]; then
    echo "$path"
    return 0
  fi

  return 1
}

# ─── All known tools (category:binary_name) ────────────────────────────────
# Format: CATEGORY TOOL_KEY BINARY_NAME
ALL_TOOLS=(
  "simulators  vcs        vcs"
  "simulators  xrun       xrun"
  "simulators  vsim       vsim"
  "simulators  verilator  verilator"
  "simulators  iverilog   iverilog"
  "synthesis   yosys      yosys"
  "synthesis   dc_shell   dc_shell"
  "synthesis   genus      genus"
  "lint        verilator  verilator"
  "lint        verible    verible-verilog-lint"
  "lint        slang      slang"
  "lint        sg_shell   sg_shell"
  "formal      sby        sby"
  "formal      jg         jg"
  "formal      vcf        vcf"
  "equivalence fm_shell   fm_shell"
  "equivalence lec        lec"
  "cdc         svlens     svlens"
  "cdc         sg_shell   sg_shell"
  "debug       verdi      verdi"
  "debug       simvision  simvision"
  "coverage    urg        urg"
  "coverage    imc        imc"
  "coverage    vcover     vcover"
)

# ─── Load existing user fields ─────────────────────────────────────────────
declare -A SAVED_ENV=()
declare -A SAVED_PATH=()

if [[ -f "$CONFIG" ]]; then
  for entry in "${ALL_TOOLS[@]}"; do
    read -r _cat key _bin <<< "$entry"
    env_val=$(json_get_tool_field "$CONFIG" "$key" "env_source")
    path_val=$(json_get_tool_field "$CONFIG" "$key" "path")
    [[ -n "$env_val" ]] && SAVED_ENV[$key]="$env_val"
    # Only preserve user-set paths (not auto-detected ones)
    if [[ -n "$path_val" && "$path_val" != "/"* && "$path_val" != "(built-in)" ]]; then
      SAVED_PATH[$key]="$path_val"
    elif [[ -n "$path_val" && -n "${SAVED_ENV[$key]:-}" ]]; then
      # User set env_source, preserve their path too
      SAVED_PATH[$key]="$path_val"
    fi
  done
  echo "Loaded existing config (preserving user fields)"
fi

# Preserve other user-edited sections
if [[ -f "$CONFIG" ]]; then
  TOP_MODULE=$(json_get "$CONFIG" "top_module")
  FILELIST=$(json_get "$CONFIG" "filelist")
  LIBERTY=$(json_get "$CONFIG" "liberty")
  SRAM_LIB=$(json_get "$CONFIG" "sram_lib")
  TARGET=$(json_get "$CONFIG" "target")
  NAND2_PATTERN=$(json_get "$CONFIG" "nand2_cell_pattern")
  SEEDS=$(json_get "$CONFIG" "seeds")
  W_VERILATOR=$(json_get_tool_field "$CONFIG" "verilator" "verilator" 2>/dev/null || echo "")
  W_VERIBLE=$(json_get_tool_field "$CONFIG" "verible" "verible" 2>/dev/null || echo "")
  W_SG_LINT=$(json_get_tool_field "$CONFIG" "spyglass_lint" "spyglass_lint" 2>/dev/null || echo "")
  W_SG_CDC=$(json_get_tool_field "$CONFIG" "spyglass_cdc" "spyglass_cdc" 2>/dev/null || echo "")
  W_CDC=$(json_get_tool_field "$CONFIG" "cdc" "cdc" 2>/dev/null || echo "")
else
  TOP_MODULE=""
  FILELIST="rtl/filelist_top.f"
  LIBERTY=""
  SRAM_LIB=""
  TARGET=""
  NAND2_PATTERN="NAND2X1"
  SEEDS="42 123 456 789 1337"
  W_VERILATOR=""
  W_VERIBLE=""
  W_SG_LINT=""
  W_SG_CDC=""
  W_CDC=""
fi

# ─── Detect all tools ──────────────────────────────────────────────────────
echo "=== EDA Tool Detection ==="

declare -A DET_STATUS=()
declare -A DET_PATH=()

for entry in "${ALL_TOOLS[@]}"; do
  read -r cat key bin <<< "$entry"
  env_src="${SAVED_ENV[$key]:-}"
  exp_path="${SAVED_PATH[$key]:-}"

  found_path=""
  if found_path=$(tool_detect "$bin" "$env_src" "$exp_path"); then
    DET_STATUS[$cat/$key]=true
    DET_PATH[$cat/$key]="$found_path"
  else
    DET_STATUS[$cat/$key]=false
    DET_PATH[$cat/$key]=""
  fi
done

# structural CDC is always available
DET_STATUS["cdc/structural"]=true
DET_PATH["cdc/structural"]="(built-in)"

# Print summary
PREV_CAT=""
for entry in "${ALL_TOOLS[@]}"; do
  read -r cat key bin <<< "$entry"
  if [[ "$cat" != "$PREV_CAT" ]]; then
    [[ -n "$PREV_CAT" ]] && echo ""
    printf "  %-12s" "$cat:"
    PREV_CAT="$cat"
  fi
  if [[ "${DET_STATUS[$cat/$key]}" == "true" ]]; then
    printf " %s(OK)" "$key"
  else
    printf " %s(-)" "$key"
  fi
done
echo ""
echo ""

# ─── Determine preferences ────────────────────────────────────────────────
# Priority: commercial first within each category
pick_pref() {
  local cat="$1"; shift
  local candidates=("$@")
  for key in "${candidates[@]}"; do
    if [[ "${DET_STATUS[$cat/$key]:-false}" == "true" ]]; then
      echo "$key"
      return
    fi
  done
  echo ""
}

PREF_SIM=$(pick_pref simulators vcs xrun vsim verilator iverilog)
PREF_SYN=$(pick_pref synthesis dc_shell genus yosys)
PREF_LINT=$(pick_pref lint sg_shell slang verilator verible)
PREF_FORMAL=$(pick_pref formal jg vcf sby)
PREF_CDC=$(pick_pref cdc sg_shell svlens)
if [[ -z "$PREF_CDC" ]]; then PREF_CDC="structural"; fi
PREF_EQUIV=$(pick_pref equivalence fm_shell lec)

echo "Preferences: sim=$PREF_SIM syn=$PREF_SYN lint=$PREF_LINT formal=$PREF_FORMAL cdc=$PREF_CDC equiv=${PREF_EQUIV:-(yosys)}"

# ─── NAND2 area extraction ────────────────────────────────────────────────
NAND2_AREA="null"
if [[ -n "$LIBERTY" && -f "$LIBERTY" ]]; then
  NAND2_PAT="${NAND2_PATTERN:-NAND2X1}"
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
    echo "NAND2 area: ${EXTRACTED} um2 (from liberty: $NAND2_PAT)"
  else
    echo "WARNING: $NAND2_PAT not found in $LIBERTY — nand2_area_um2 left as null"
  fi
fi

# ─── Generate tool JSON block ─────────────────────────────────────────────
tool_json() {
  local cat="$1" key="$2"
  local det="${DET_STATUS[$cat/$key]:-false}"
  local path="${DET_PATH[$cat/$key]:-}"
  local env="${SAVED_ENV[$key]:-}"
  printf '      "%s": { "detected": %s, "path": "%s", "env_source": "%s" }' \
    "$key" "$det" "$path" "$env"
}

category_json() {
  local cat="$1"; shift
  local keys=("$@")
  echo "    \"$cat\": {"
  for i in "${!keys[@]}"; do
    tool_json "$cat" "${keys[$i]}"
    if [[ $i -lt $((${#keys[@]} - 1)) ]]; then echo ","; else echo ""; fi
  done
  echo "    }"
}

# ─── Write config ──────────────────────────────────────────────────────────
cat > "$CONFIG" << OUTER_EOF
{
  "project": {
    "name": "$PROJECT_NAME",
    "top_module": "$TOP_MODULE",
    "filelist": "$FILELIST"
  },
  "tools": {
    "_comment": "All known EDA tools. 'detected' is auto-filled. Edit 'path' or 'env_source' for tools needing setup, then re-run generate_config.sh.",
$(category_json simulators vcs xrun vsim verilator iverilog),
$(category_json synthesis yosys dc_shell genus),
$(category_json lint verilator verible slang sg_shell),
$(category_json formal sby jg vcf),
    "cdc": {
      "structural": { "detected": true, "path": "(built-in)", "env_source": "" },
$(tool_json cdc svlens),
$(tool_json cdc sg_shell)
    },
$(category_json equivalence fm_shell lec),
$(category_json debug verdi simvision),
$(category_json coverage urg imc vcover)
  },
  "preferences": {
    "_comment": "Preferred tool per category. Auto-set to first detected (commercial priority). User-overridable.",
    "simulator": "$PREF_SIM",
    "synthesis": "$PREF_SYN",
    "lint": "$PREF_LINT",
    "formal": "$PREF_FORMAL",
    "cdc": "$PREF_CDC",
    "equivalence": "${PREF_EQUIV:-}"
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
OUTER_EOF

echo ""
echo "Config written: $CONFIG"
echo ""
echo "Next steps:"
echo "  1. Edit 'env_source' for tools needing setup (e.g., \"source /tools/synopsys/vcs/setup.sh\")"
echo "  2. Edit 'path' for tools in non-standard locations"
echo "  3. Set technology.liberty for accurate NAND2 gate count"
echo "  4. Set waivers paths for lint/CDC waiver files"
echo "  5. Re-run to refresh detection: bash generate_config.sh"
