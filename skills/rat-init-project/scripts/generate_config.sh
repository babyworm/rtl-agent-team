#!/usr/bin/env bash
# generate_config.sh — Generate rat_config.json with EDA tool auto-detection
#
# Usage: generate_config.sh [project_root] [project_name]
#
# Detects all known EDA tools, records path for each, extracts NAND2 area
# from liberty if specified. Tools not in PATH get empty fields that users
# can fill in with 'path' or 'env_source' to enable detection on re-run.
#
# If rat_config.json already exists, preserves user-edited fields while
# refreshing derived detection state, unusable tool paths, and NAND2 area.

set -euo pipefail

if (( BASH_VERSINFO[0] < 4 )); then
  echo "ERROR: generate_config.sh requires Bash 4 or newer." >&2
  exit 2
fi

PROJECT_ROOT="${1:-.}"
PROJECT_NAME="${2:-$(basename "$(cd "$PROJECT_ROOT" && pwd)")}"
CONFIG="$PROJECT_ROOT/rat_config.json"
CONFIG_MK="$PROJECT_ROOT/config.mk"
GENERATED_CONFIG=""
GENERATED_CONFIG_MK=""
EXISTING_CONFIG=""

cleanup() {
  [[ -z "$GENERATED_CONFIG" ]] || rm -f -- "$GENERATED_CONFIG"
  [[ -z "$GENERATED_CONFIG_MK" ]] || rm -f -- "$GENERATED_CONFIG_MK"
}
trap cleanup EXIT

validate_managed_destination() {
  local destination="$1"
  if [[ -L "$destination" || ( -e "$destination" && ! -f "$destination" ) ]]; then
    echo "ERROR: managed config destination is not a regular file: $destination" >&2
    return 1
  fi
}

validate_managed_destination "$CONFIG"
validate_managed_destination "$CONFIG_MK"

GENERATED_CONFIG=$(mktemp "$PROJECT_ROOT/.rat_config.generated.XXXXXX")
GENERATED_CONFIG_MK=$(mktemp "$PROJECT_ROOT/.config.mk.generated.XXXXXX")

if [[ -f "$CONFIG" ]]; then
  EXISTING_CONFIG="$CONFIG"
fi

# ─── Helpers ────────────────────────────────────────────────────────────────

json_get_path() {
  local file="$1"
  shift
  python3 - "$file" "$@" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as config_file:
    value = json.load(config_file)

for key in sys.argv[2:]:
    if not isinstance(value, dict) or key not in value:
        raise SystemExit(0)
    value = value[key]

if value is not None:
    print(json.dumps(value) if isinstance(value, (dict, list)) else value)
PY
}

json_quote() {
  python3 -c 'import json, sys; print(json.dumps(sys.argv[1]))' "$1"
}

# Check if a tool is available, optionally sourcing env first or using explicit path
# Args: tool_name env_source_cmd explicit_path
tool_detect() {
  local tool="$1" env_cmd="${2:-}" explicit_path="${3:-}"

  # Try explicit path first
  if [[ -n "$explicit_path" && -f "$explicit_path" && -x "$explicit_path" ]]; then
    echo "$explicit_path"
    return 0
  fi

  # Try with env_source
  if [[ -n "$env_cmd" ]]; then
    local found
    found=$(bash -c 'eval "$1" >/dev/null 2>&1 && command -v -- "$2"' \
      _ "$env_cmd" "$tool" 2>/dev/null) || true
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
  "cdc         vc_cdc     vc_cdc"
  "cdc         questa_cdc questa_cdc"
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
    read -r cat key _bin <<< "$entry"
    index="$cat/$key"
    env_val=$(json_get_path "$CONFIG" tools "$cat" "$key" env_source)
    path_val=$(json_get_path "$CONFIG" tools "$cat" "$key" path)
    [[ -z "$env_val" ]] || SAVED_ENV[$index]="$env_val"
    [[ -z "$path_val" || "$path_val" == "(built-in)" ]] || SAVED_PATH[$index]="$path_val"
  done
  echo "Loaded existing config (preserving user fields)"
fi

# Preserve other user-edited sections
if [[ -f "$CONFIG" ]]; then
  TOP_MODULE=$(json_get_path "$CONFIG" project top_module)
  FILELIST=$(json_get_path "$CONFIG" project filelist)
  LIBERTY=$(json_get_path "$CONFIG" technology liberty)
  SRAM_LIB=$(json_get_path "$CONFIG" technology sram_lib)
  TARGET=$(json_get_path "$CONFIG" technology target)
  NAND2_PATTERN=$(json_get_path "$CONFIG" technology nand2_cell_pattern)
  SEEDS=$(json_get_path "$CONFIG" coverage seeds)
  W_VERILATOR=$(json_get_path "$CONFIG" waivers verilator)
  W_VERIBLE=$(json_get_path "$CONFIG" waivers verible)
  W_SG_LINT=$(json_get_path "$CONFIG" waivers spyglass_lint)
  W_SG_CDC=$(json_get_path "$CONFIG" waivers spyglass_cdc)
  W_CDC=$(json_get_path "$CONFIG" waivers cdc)
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
  env_src="${SAVED_ENV[$cat/$key]:-}"
  exp_path="${SAVED_PATH[$cat/$key]:-}"

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
PREF_CDC=$(pick_pref cdc sg_shell vc_cdc questa_cdc svlens)
if [[ -z "$PREF_CDC" ]]; then PREF_CDC="structural"; fi
PREF_EQUIV=$(pick_pref equivalence fm_shell lec)

# ─── Normalize keys to Makefile target suffixes ──────────────────────────
# generate_config.sh uses internal keys (dc_shell, jg, vsim, sg_shell)
# but Makefile targets use normalized names (dc, jasper, questa, spyglass)
normalize_for_make() {
  case "$1" in
    dc_shell) echo "dc" ;;
    jg)       echo "jasper" ;;
    vcf)      echo "vcf" ;;
    vsim)     echo "questa" ;;
    sg_shell) echo "spyglass" ;;
    *)        echo "$1" ;;
  esac
}

# Commercial formal tools (jg, vcf) require project-specific TCL scripts.
# Fall back to sby if detected (including env_source paths); otherwise keep
# normalized commercial name (user gets clear "JASPER_TCL required" error).
safe_formal_pref() {
  case "$1" in
    jg|vcf)
      if [[ "${DET_STATUS[formal/sby]:-false}" == "true" ]]; then echo "sby"
      else normalize_for_make "$1"
      fi ;;
    *) echo "$1" ;;
  esac
}

# ─── NAND2 area extraction ────────────────────────────────────────────────
NAND2_AREA="null"
LIBERTY_FILE="$LIBERTY"
if [[ -n "$LIBERTY_FILE" && "$LIBERTY_FILE" != /* ]]; then
  LIBERTY_FILE="$PROJECT_ROOT/$LIBERTY_FILE"
fi
if [[ -n "$LIBERTY_FILE" && -f "$LIBERTY_FILE" ]]; then
  NAND2_PAT="${NAND2_PATTERN:-NAND2X1}"
  EXTRACTED=$(awk -v pat="$NAND2_PAT" '
    $0 ~ "cell[[:space:]]*\\("pat"\\)" { found=1 }
    found && /area[[:space:]]*:/ {
      gsub(/[^0-9.]/, "", $NF)
      print $NF
      exit
    }
    found && /^\s*\}/ { found=0 }
  ' "$LIBERTY_FILE")

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
  local env="${SAVED_ENV[$cat/$key]:-}"
  printf '      "%s": { "detected": %s, "path": %s, "env_source": %s }' \
    "$key" "$det" "$(json_quote "$path")" "$(json_quote "$env")"
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
cat > "$GENERATED_CONFIG" << OUTER_EOF
{
  "project": {
    "name": $(json_quote "$PROJECT_NAME"),
    "top_module": $(json_quote "$TOP_MODULE"),
    "filelist": $(json_quote "$FILELIST")
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
$(tool_json cdc sg_shell),
$(tool_json cdc vc_cdc),
$(tool_json cdc questa_cdc)
    },
$(category_json equivalence fm_shell lec),
$(category_json debug verdi simvision),
$(category_json coverage urg imc vcover)
  },
  "preferences": {
    "_comment": "Preferred tool per category. Auto-set to first detected (commercial priority). User-overridable.",
    "simulator": $(json_quote "$PREF_SIM"),
    "synthesis": $(json_quote "$PREF_SYN"),
    "lint": $(json_quote "$PREF_LINT"),
    "formal": $(json_quote "$PREF_FORMAL"),
    "cdc": $(json_quote "$PREF_CDC"),
    "equivalence": $(json_quote "${PREF_EQUIV:-}")
  },
  "technology": {
    "target": $(json_quote "$TARGET"),
    "liberty": $(json_quote "$LIBERTY"),
    "sram_lib": $(json_quote "$SRAM_LIB"),
    "nand2_cell_pattern": $(json_quote "${NAND2_PATTERN:-NAND2X1}"),
    "nand2_area_um2": $NAND2_AREA
  },
  "coverage": {
    "targets": { "line": 90, "toggle": 80, "fsm": 70, "branch": 80, "functional": 95 },
    "seeds": $(json_quote "$SEEDS"),
    "max_fail_rate": 5
  },
  "waivers": {
    "verilator": $(json_quote "$W_VERILATOR"),
    "verible": $(json_quote "$W_VERIBLE"),
    "spyglass_lint": $(json_quote "$W_SG_LINT"),
    "spyglass_cdc": $(json_quote "$W_SG_CDC"),
    "cdc": $(json_quote "$W_CDC")
  }
}
OUTER_EOF

python3 - "$GENERATED_CONFIG" "$EXISTING_CONFIG" <<'PY'
import json
import sys
from pathlib import Path


def preserve_user_fields(generated, existing, path=()):
    for key, existing_value in existing.items():
        if path and path[0] == "tools" and key in {"detected", "path"}:
            continue
        if path == ("technology",) and key == "nand2_area_um2":
            continue
        generated_value = generated.get(key)
        if isinstance(generated_value, dict) and isinstance(existing_value, dict):
            preserve_user_fields(generated_value, existing_value, (*path, key))
        else:
            generated[key] = existing_value


generated_path = Path(sys.argv[1])
with generated_path.open(encoding="utf-8") as generated_file:
    config = json.load(generated_file)

if sys.argv[2]:
    with Path(sys.argv[2]).open(encoding="utf-8") as existing_file:
        preserve_user_fields(config, json.load(existing_file))

generated_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
PY

PREF_SIM=$(json_get_path "$GENERATED_CONFIG" preferences simulator)
PREF_SYN=$(json_get_path "$GENERATED_CONFIG" preferences synthesis)
PREF_LINT=$(json_get_path "$GENERATED_CONFIG" preferences lint)
PREF_FORMAL=$(json_get_path "$GENERATED_CONFIG" preferences formal)
PREF_CDC=$(json_get_path "$GENERATED_CONFIG" preferences cdc)
PREF_EQUIV=$(json_get_path "$GENERATED_CONFIG" preferences equivalence)
LIBERTY=$(json_get_path "$GENERATED_CONFIG" technology liberty)
SEEDS=$(json_get_path "$GENERATED_CONFIG" coverage seeds)

MK_SIM=$(normalize_for_make "$PREF_SIM")
MK_SYN=$(normalize_for_make "$PREF_SYN")
MK_LINT=$(normalize_for_make "$PREF_LINT")
MK_FORMAL=$(normalize_for_make "$(safe_formal_pref "$PREF_FORMAL")")
MK_CDC=$(normalize_for_make "$PREF_CDC")
MK_EQUIV=$(normalize_for_make "$PREF_EQUIV")

validate_make_token() {
  local label="$1" value="$2"
  if [[ -n "$value" && ! "$value" =~ ^[[:alnum:]_][[:alnum:]_.+-]*$ ]]; then
    echo "ERROR: $label contains characters unsafe for Make." >&2
    return 1
  fi
}

normalize_seeds() {
  python3 - "$1" <<'PY'
import re
import sys

seeds = sys.argv[1].split()
if any(re.fullmatch(r"[0-9]+", seed) is None for seed in seeds):
    print("ERROR: coverage.seeds must contain only decimal integers.", file=sys.stderr)
    raise SystemExit(1)

print(" ".join(seed.lstrip("0") or "0" for seed in seeds))
PY
}

escape_make_path() {
  local label="$1" value="$2"
  if [[ ! "$value" =~ ^[[:alnum:]_./:+,@%\ -]*$ ]]; then
    echo "ERROR: $label contains characters unsafe for Make or the shell." >&2
    return 1
  fi
  printf '%s' "${value// /\\ }"
}

validate_make_token "preferences.simulator" "$MK_SIM"
validate_make_token "preferences.synthesis" "$MK_SYN"
validate_make_token "preferences.lint" "$MK_LINT"
validate_make_token "preferences.formal" "$MK_FORMAL"
validate_make_token "preferences.cdc" "$MK_CDC"
validate_make_token "preferences.equivalence" "$MK_EQUIV"
SEEDS_MK=$(normalize_seeds "$SEEDS")
LIBERTY_MK=$(escape_make_path "technology.liberty" "$LIBERTY")
SDC_FILE_MK=$(escape_make_path "SDC_FILE" "${SDC_FILE:-syn/constraints/design.sdc}")

echo "Preferences: sim=$PREF_SIM syn=$PREF_SYN lint=$PREF_LINT formal=$PREF_FORMAL cdc=$PREF_CDC equiv=${PREF_EQUIV:-(yosys)}"
echo "Make targets: sim=$MK_SIM syn=$MK_SYN lint=$MK_LINT formal=$MK_FORMAL cdc=$MK_CDC"

# ─── Generate config.mk (Makefile-includable preferences) ────────────────
{
  echo "# Auto-generated by generate_config.sh — do not edit manually."
  echo "# Re-generate: bash generate_config.sh"
  echo "# Included by Makefile via: -include config.mk"
  echo ""
  echo "# Preferred tool per category (normalized to Makefile target suffixes)"
  echo "# Only non-empty preferences are written; empty = let Makefile default apply"
  [[ -n "$MK_SIM" ]]    && echo "PREF_SIM     ?= ${MK_SIM}"
  [[ -n "$MK_SYN" ]]    && echo "PREF_SYN     ?= ${MK_SYN}"
  [[ -n "$MK_LINT" ]]   && echo "PREF_LINT    ?= ${MK_LINT}"
  [[ -n "$MK_FORMAL" ]] && echo "PREF_FORMAL  ?= ${MK_FORMAL}"
  [[ -n "$MK_CDC" ]]    && echo "PREF_CDC     ?= ${MK_CDC}"
  [[ -n "$MK_EQUIV" ]]  && echo "PREF_EQUIV   ?= ${MK_EQUIV}"
  echo ""
  echo "# Technology"
  [[ -n "$LIBERTY_MK" ]] && echo "LIBERTY      ?= ${LIBERTY_MK}"
  echo "SDC_FILE     ?= ${SDC_FILE_MK}"
  echo ""
  echo "# Regression"
  [[ -n "$SEEDS_MK" ]] && echo "SEEDS        ?= ${SEEDS_MK}"
} > "$GENERATED_CONFIG_MK"

preserve_mode() {
  python3 - "$1" "$2" <<'PY'
import os
import stat
import sys

source, destination = sys.argv[1:]
mode = stat.S_IMODE(os.stat(source).st_mode) if os.path.isfile(source) else 0o644
os.chmod(destination, mode)
PY
}

preserve_mode "$CONFIG" "$GENERATED_CONFIG"
preserve_mode "$CONFIG_MK" "$GENERATED_CONFIG_MK"
mv -f -- "$GENERATED_CONFIG" "$CONFIG"
mv -f -- "$GENERATED_CONFIG_MK" "$CONFIG_MK"

echo ""
echo "Config written: $CONFIG"
echo "Config.mk written: $CONFIG_MK"
echo ""
echo "Next steps:"
echo "  1. Edit 'env_source' for tools needing setup (e.g., \"source /tools/synopsys/vcs/setup.sh\")"
echo "  2. Edit 'path' for tools in non-standard locations"
echo "  3. Set technology.liberty for accurate NAND2 gate count"
echo "  4. Set waivers paths for lint/CDC waiver files"
echo "  5. Re-run to refresh detection: bash generate_config.sh"
