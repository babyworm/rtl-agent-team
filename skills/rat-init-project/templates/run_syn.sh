#!/usr/bin/env bash
# run_syn.sh — Synthesis runner for RTL modules
# Usage: syn/scripts/run_syn.sh [OPTIONS] [SV_FILES...]
#
# Directory structure (DC-standard, adapted for all tools):
#   syn/db/      — Binary databases (.ddc, .db)
#   syn/vnet/    — Gate-level netlists (.v)
#   syn/svf/     — Setup Verification Flow files (.svf)
#   syn/scr/     — Generated synthesis scripts (.tcl, .ys)
#   syn/rpt/     — Reports (area, timing, power, qor)
#   syn/log/     — Synthesis logs
#   syn/temp/    — Synthesis cache and temporary files
#   syn/work/    — Tool work directories (alib, elaboration)
#
# Supports: yosys (default), dc_shell/design_compiler, genus, vivado
#
# Examples:
#   syn/scripts/run_syn.sh --tool yosys --top top_module -f rtl/filelist_top.f
#   syn/scripts/run_syn.sh --tool dc_shell --top my_top -f rtl/filelist_top.f --liberty sky130.lib
#   syn/scripts/run_syn.sh --tool genus --top my_top -f rtl/filelist_top.f --liberty sky130.lib

set -euo pipefail

# Source Docker-aware tool runner (transparent fallback)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_LIB_RUNNER="$(cd "$SCRIPT_DIR/../../lib" 2>/dev/null && pwd)/tool-runner.sh" 2>/dev/null || true
if [[ -f "${_LIB_RUNNER:-}" ]]; then
  source "$_LIB_RUNNER"
else
  run_tool() { "$@"; }
fi

PROJECT_ROOT="$(pwd)"

# ─── Defaults ───────────────────────────────────────────────────────────────
TOOL="yosys"
TOP=""
FILELIST=""
SYN_ROOT="syn"
LIBERTY=""
SDC_FILE=""
SCRIPT_PATH=""
FILES=()
VERBOSE=0
FLATTEN=0
SKIP_IF_UNAVAILABLE=0

# ─── Usage ──────────────────────────────────────────────────────────────────
usage() {
  cat <<'USAGE'
Usage: syn/scripts/run_syn.sh [OPTIONS] [SV_FILES...]

Options:
  --tool <name>     yosys|dc_shell|design_compiler|genus|vivado (default: yosys)
  --top <module>    Top-level module name (required)
  -f <filelist>     Source filelist (.f file)
  --syn-root <dir>  Synthesis root directory (default: syn)
  --liberty <file>  Liberty (.lib) file for technology mapping
  --sdc <file>      SDC constraints file (default: syn/constraints/design.sdc)
  --script <file>   User-provided tool script/Tcl (skips auto-generation)
  --flatten         Flatten design before synthesis
  --skip-if-unavailable  Exit cleanly (exit 0) if tool not available/licensed
  -v, --verbose     Verbose output
  -h, --help        Show this help

Output directories (under --syn-root):
  db/               Binary databases (.ddc, .db)
  vnet/             Gate-level netlists (.v)
  svf/              Setup Verification Flow (.svf)
  scr/              Generated scripts (.tcl, .ys) + replay/
  rpt/              Reports (area, timing, power, qor)
  log/              Synthesis logs
  temp/             Cache and temporary files
  work/             Tool work directories
USAGE
  exit 0
}

# ─── Parse args ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool)      TOOL="$2"; shift 2 ;;
    --top)       TOP="$2"; shift 2 ;;
    -f)          FILELIST="$2"; shift 2 ;;
    --syn-root|--outdir) SYN_ROOT="$2"; shift 2 ;;
    --liberty)   LIBERTY="$2"; shift 2 ;;
    --sdc)       SDC_FILE="$2"; shift 2 ;;
    --script)    SCRIPT_PATH="$2"; shift 2 ;;
    --flatten)   FLATTEN=1; shift ;;
    --skip-if-unavailable) SKIP_IF_UNAVAILABLE=1; shift ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help)   usage ;;
    -*)          echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
    *)           FILES+=("$1"); shift ;;
  esac
done

if [[ "$TOOL" == "design_compiler" ]]; then
  TOOL="dc_shell"
fi

if [[ -z "$TOP" ]]; then
  echo "ERROR: --top <module> is required" >&2
  exit 1
fi

# Default SDC path (always project-relative, not SYN_ROOT-relative)
if [[ -z "$SDC_FILE" ]]; then
  SDC_FILE="syn/constraints/design.sdc"
fi

# ─── Resolve paths to absolute (before cd to synthesis root) ──────────
case "$SYN_ROOT" in /*) ;; *) SYN_ROOT="$PROJECT_ROOT/$SYN_ROOT" ;; esac
[[ -n "$LIBERTY" && "$LIBERTY" != /* ]] && LIBERTY="$PROJECT_ROOT/$LIBERTY"
[[ -n "$SDC_FILE" && "$SDC_FILE" != /* ]] && SDC_FILE="$PROJECT_ROOT/$SDC_FILE"
[[ -n "$SCRIPT_PATH" && "$SCRIPT_PATH" != /* ]] && SCRIPT_PATH="$PROJECT_ROOT/$SCRIPT_PATH"
[[ -n "$FILELIST" && "$FILELIST" != /* ]] && FILELIST="$PROJECT_ROOT/$FILELIST"

# ─── Directory setup ──────────────────────────────────────────────────────
DIR_DB="${SYN_ROOT}/db"
DIR_VNET="${SYN_ROOT}/vnet"
DIR_SVF="${SYN_ROOT}/svf"
DIR_SCR="${SYN_ROOT}/scr"
DIR_RPT="${SYN_ROOT}/rpt"
DIR_LOG="${SYN_ROOT}/log"
DIR_TEMP="${SYN_ROOT}/temp"
DIR_WORK="${SYN_ROOT}/work"
DIR_REPLAY="${DIR_SCR}/replay"

mkdir -p "$DIR_DB" "$DIR_VNET" "$DIR_SVF" "$DIR_SCR" "$DIR_RPT" \
         "$DIR_LOG" "$DIR_TEMP" "$DIR_WORK" "$DIR_REPLAY"

# ─── Tool availability & license pre-check ─────────────────────────────────
_tool_bin=""
case "$TOOL" in
  yosys)    _tool_bin="yosys" ;;
  dc_shell) _tool_bin="dc_shell" ;;
  genus)    _tool_bin="genus" ;;
  *)        _tool_bin="$TOOL" ;;
esac

if ! command -v "$_tool_bin" >/dev/null 2>&1; then
  if [[ "$SKIP_IF_UNAVAILABLE" -eq 1 ]]; then
    echo "WARNING: Synthesis tool '$TOOL' not available — skipping synthesis." >&2
    echo '{"tool":"'"$TOOL"'","status":"SKIPPED","reason":"tool_not_available"}' > "${DIR_RPT}/syn_result.json" 2>/dev/null || true
    exit 0
  fi
  echo "ERROR: Synthesis tool '$_tool_bin' not found in PATH." >&2
  exit 127
fi

# License check for commercial tools
if type check_tool_licensed >/dev/null 2>&1; then
  case "$TOOL" in
    dc_shell|genus)
      if ! check_tool_licensed "$TOOL"; then
        if [[ "$SKIP_IF_UNAVAILABLE" -eq 1 ]]; then
          echo "WARNING: '$TOOL' license not available — skipping synthesis." >&2
          echo '{"tool":"'"$TOOL"'","status":"SKIPPED","reason":"license_unavailable"}' > "${DIR_RPT}/syn_result.json" 2>/dev/null || true
          exit 0
        fi
        echo "ERROR: '$TOOL' license check failed." >&2
        exit 1
      fi ;;
  esac
fi

# ─── Collect source files ──────────────────────────────────────────────────
SRC_FILES=()
if [[ -n "$FILELIST" ]]; then
  while IFS= read -r line; do
    line=$(echo "$line" | sed 's|//.*||' | xargs)
    [[ -z "$line" ]] && continue
    [[ "$line" == +* ]] && continue
    SRC_FILES+=("$line")
  done < "$FILELIST"
fi
[[ ${#FILES[@]} -gt 0 ]] && SRC_FILES+=("${FILES[@]}")

if [[ ${#SRC_FILES[@]} -eq 0 ]]; then
  echo "ERROR: No source files specified. Use -f <filelist> or pass .sv files directly." >&2
  exit 1
fi

# Resolve source files to absolute paths (before cd)
_abs_src=()
for f in "${SRC_FILES[@]}"; do
  case "$f" in /*) _abs_src+=("$f") ;; *) _abs_src+=("$PROJECT_ROOT/$f") ;; esac
done
SRC_FILES=("${_abs_src[@]}")

# ─── Relative $readmemh/$readmemb ROM guard ─────────────────────────────────
# Source/SDC/filelist paths are absolutized above, but $readmemh("rel/path.mem")
# strings INSIDE the RTL are not — the tool resolves them against CWD, and we cd
# into $SYN_ROOT below. A relative ROM path then silently loads NOTHING (empty
# ROM, wrong synthesis, no error). Warn loudly so it is caught here, not in silicon.
# A bare "..." starting with '/' is absolute (fine); a `define-built or {..}-concat
# path is parameterizable (fine) and won't match this literal-relative pattern.
_relmem=$(grep -hoE '\$readmem[hb][[:space:]]*\([[:space:]]*"[^"/][^"]*"' "${SRC_FILES[@]}" 2>/dev/null | sort -u || true)
if [[ -n "$_relmem" ]]; then
  echo "WARNING: RTL uses RELATIVE \$readmemh/\$readmemb ROM paths. Synthesis runs from" >&2
  echo "         '$SYN_ROOT' (cd below), so these may load EMPTY (silent wrong synthesis)." >&2
  echo "         Fix: use absolute paths, parameterize the dir (+define+MEM_DIR=...), or" >&2
  echo "         ensure the .mem files resolve relative to \$SYN_ROOT. Offending loads:" >&2
  echo "$_relmem" | sed 's/^/           /' >&2
fi

# ─── cd to synthesis root — all tool artifacts stay contained ─────────
cd "$SYN_ROOT"
echo "[run_syn] Working directory: $(pwd)"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_CWD="$(pwd)"

write_replay() {
  local cmd="$1"
  local replay_file="${DIR_REPLAY}/run_syn_${TOOL}_${TOP}_${TIMESTAMP}.sh"
  cat > "$replay_file" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$RUN_CWD"
$cmd
EOF
  chmod +x "$replay_file"
  cp "$replay_file" "${DIR_REPLAY}/run_syn_${TOOL}_latest.sh"
}

# ─── Tool-specific synthesis ───────────────────────────────────────────────
EXIT_CODE=0

case "$TOOL" in
  # =========================================================================
  # Yosys (open-source)
  # =========================================================================
  yosys)
    SCRIPT="${DIR_SCR}/synth_${TOP}_${TIMESTAMP}.ys"
    LOG="${DIR_LOG}/yosys_${TOP}_${TIMESTAMP}.log"
    NETLIST_JSON="${DIR_DB}/${TOP}.json"
    NETLIST_V="${DIR_VNET}/${TOP}.v"

    # sv2v conversion (SystemVerilog → Verilog for Yosys compatibility)
    SV2V_OUT="${DIR_TEMP}/${TOP}_sv2v.v"
    USE_SV2V=0
    if command -v sv2v >/dev/null 2>&1; then
      COMMON_FILES=()
      if [[ -d "$PROJECT_ROOT/rtl/common" ]]; then
        while IFS= read -r cf; do
          COMMON_FILES+=("$cf")
        done < <(find "$PROJECT_ROOT/rtl/common" -name '*.sv' -o -name '*.v' 2>/dev/null | sort)
      fi
      echo "=== sv2v Conversion ==="
      sv2v "${COMMON_FILES[@]}" "${SRC_FILES[@]}" -o "$SV2V_OUT"
      echo "Converted: $SV2V_OUT (${#SRC_FILES[@]} source + ${#COMMON_FILES[@]} common files)"
      USE_SV2V=1
    else
      echo "WARNING: sv2v not found — using read_verilog -sv (limited SV support in Yosys)"
    fi

    # Generate Yosys script
    {
      echo "# Yosys synthesis script for $TOP"
      echo "# Generated: $(date)"
      echo ""
      if [[ $USE_SV2V -eq 1 ]]; then
        echo "read_verilog $SV2V_OUT"
      else
        for f in "${SRC_FILES[@]}"; do
          echo "read_verilog -sv $f"
        done
        if [[ -d "$PROJECT_ROOT/rtl/common" ]]; then
          for f in "$PROJECT_ROOT"/rtl/common/*.sv "$PROJECT_ROOT"/rtl/common/*.v; do
            [[ -f "$f" ]] && echo "read_verilog -sv $f"
          done
        fi
      fi
      echo ""
      echo "hierarchy -check -top $TOP"
      echo "proc; opt; fsm; opt"
      [[ $FLATTEN -eq 1 ]] && echo "flatten"
      echo ""
      echo "# Memory handling"
      echo "memory; opt"
      echo ""
      if [[ -n "$LIBERTY" ]]; then
        echo "# Technology mapping"
        echo "techmap; opt"
        echo "dfflibmap -liberty $LIBERTY"
        echo "abc -liberty $LIBERTY"
        echo "clean"
        echo ""
        echo "stat -liberty $LIBERTY"
      else
        echo "# Generic synthesis (no technology mapping)"
        echo "techmap; opt"
        echo "stat -top $TOP"
      fi
      echo ""
      echo "# Post-synthesis checks"
      echo "scc -max_depth 10"
      echo "write_json $NETLIST_JSON"
      echo "write_verilog $NETLIST_V"
    } > "$SCRIPT"

    echo "=== Yosys Synthesis ==="
    echo "Script: $SCRIPT"
    echo "CMD: yosys -s $SCRIPT"
    write_replay "yosys -s \"$SCRIPT\""
    run_tool yosys -s "$SCRIPT" 2>&1 | tee "$LOG"
    EXIT_CODE=${PIPESTATUS[0]}

    # Extract stats to report
    if [[ -f "$LOG" ]]; then
      {
        echo "# Yosys Synthesis Report: $TOP"
        echo "# Date: $(date)"
        echo "# Liberty: ${LIBERTY:-none}"
        echo ""
        # Extract stats — try multiple markers for Yosys version compatibility
        grep -A 30 "Number of cells:\|Number of wires:\|=== $TOP ===\|Printing statistics" "$LOG" 2>/dev/null || true
      } > "${DIR_RPT}/${TOP}_stat.rpt"
    fi
    ;;

  # =========================================================================
  # Synopsys Design Compiler
  # =========================================================================
  dc_shell)
    LOG="${DIR_LOG}/dc_${TOP}_${TIMESTAMP}.log"
    SCRIPT="${SCRIPT_PATH:-${DIR_SCR}/dc_syn_${TOP}_${TIMESTAMP}.tcl}"

    NETLIST="${DIR_VNET}/${TOP}.v"
    DDC="${DIR_DB}/${TOP}.ddc"
    SVF="${DIR_SVF}/${TOP}.svf"
    AREA_RPT="${DIR_RPT}/${TOP}_area.rpt"
    TIMING_RPT="${DIR_RPT}/${TOP}_timing.rpt"
    POWER_RPT="${DIR_RPT}/${TOP}_power.rpt"
    QOR_RPT="${DIR_RPT}/${TOP}_qor.rpt"
    DC_WORK="${DIR_WORK}/dc"
    DC_TEMP="${DIR_TEMP}/dc"

    mkdir -p "$DC_WORK" "$DC_TEMP"

    # Generate .synopsys_dc.setup
    DC_SETUP="${DIR_SCR}/.synopsys_dc.setup"
    {
      echo "# Auto-generated .synopsys_dc.setup"
      echo "# Generated: $(date)"
      echo ""
      echo "set_app_var search_path [list . ${DIR_DB} ${DIR_WORK}/dc]"
      echo "set_app_var sh_command_log_file \"${DIR_LOG}/command.log\""
      if [[ -n "$LIBERTY" ]]; then
        echo "set_app_var target_library [list \"$LIBERTY\"]"
        echo "set_app_var link_library [list \"*\" \"$LIBERTY\"]"
      fi
      echo ""
      echo "# Work directories"
      echo "define_design_lib WORK -path \"${DC_WORK}\""
      echo "set_app_var alib_library_analysis_path \"${DC_TEMP}\""
      echo ""
      echo "# SVF for Formality verification"
      echo "set_svf \"${SVF}\""
    } > "$DC_SETUP"

    if [[ ! -f "$SCRIPT" || -z "$SCRIPT_PATH" ]]; then
      {
        echo "# Design Compiler synthesis script for $TOP"
        echo "# Generated: $(date)"
        echo ""
        echo "# --- Setup (sourced from .synopsys_dc.setup or inline) ---"
        echo "source \"${DC_SETUP}\""
        echo ""
        echo "# --- Read RTL ---"
        if [[ -d "$PROJECT_ROOT/rtl/common" ]]; then
          for f in "$PROJECT_ROOT"/rtl/common/*.sv "$PROJECT_ROOT"/rtl/common/*.v; do
            [[ -f "$f" ]] && echo "analyze -format sverilog \"$f\""
          done
        fi
        for f in "${SRC_FILES[@]}"; do
          echo "analyze -format sverilog \"$f\""
        done
        echo ""
        echo "elaborate $TOP"
        echo "link"
        echo "check_design"
        echo ""
        echo "# --- Constraints ---"
        echo "if {[file exists \"$SDC_FILE\"]} {"
        echo "  source \"$SDC_FILE\""
        echo "  puts \"INFO: SDC loaded from $SDC_FILE\""
        echo "} else {"
        echo "  puts \"WARNING: No SDC found at $SDC_FILE — timing estimates unreliable\""
        echo "}"
        echo ""
        echo "# --- SRAM wrapper handling ---"
        echo "# Uncomment for foundry macros:"
        echo "# set_dont_touch [get_designs sram_sp]"
        echo "# set_dont_touch [get_designs sram_tp]"
        echo "# set_dont_touch [get_designs sram_dp]"
        echo ""
        if [[ $FLATTEN -eq 1 ]]; then
          echo "ungroup -all -flatten"
        fi
        echo ""
        echo "# --- Compile ---"
        echo "compile_ultra -no_autoungroup"
        echo ""
        echo "# --- Reports ---"
        echo "report_area -hierarchy > \"$AREA_RPT\""
        echo "report_timing -max_paths 10 -significant_digits 3 > \"$TIMING_RPT\""
        echo "report_power > \"$POWER_RPT\""
        echo "report_qor > \"$QOR_RPT\""
        echo "report_constraint -all_violators"
        echo ""
        echo "# --- Save outputs ---"
        echo "change_names -rules verilog -hierarchy"
        echo "write -hierarchy -format ddc -output \"$DDC\""
        echo "write -hierarchy -format verilog -output \"$NETLIST\""
        echo ""
        echo "quit"
      } > "$SCRIPT"
    fi

    CMD="dc_shell -64bit -f \"$SCRIPT\""
    echo "=== Design Compiler Synthesis ==="
    echo "Script: $SCRIPT"
    echo "Setup:  $DC_SETUP"
    echo "CMD: $CMD"
    write_replay "$CMD"
    eval "run_tool $CMD" 2>&1 | tee "$LOG"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  # =========================================================================
  # Cadence Genus
  # =========================================================================
  genus)
    LOG="${DIR_LOG}/genus_${TOP}_${TIMESTAMP}.log"
    SCRIPT="${SCRIPT_PATH:-${DIR_SCR}/genus_syn_${TOP}_${TIMESTAMP}.tcl}"

    NETLIST="${DIR_VNET}/${TOP}.v"
    AREA_RPT="${DIR_RPT}/${TOP}_area.rpt"
    TIMING_RPT="${DIR_RPT}/${TOP}_timing.rpt"
    POWER_RPT="${DIR_RPT}/${TOP}_power.rpt"
    QOR_RPT="${DIR_RPT}/${TOP}_qor.rpt"
    GENUS_WORK="${DIR_WORK}/genus"
    GENUS_TEMP="${DIR_TEMP}/genus"

    mkdir -p "$GENUS_WORK" "$GENUS_TEMP"

    if [[ ! -f "$SCRIPT" || -z "$SCRIPT_PATH" ]]; then
      {
        echo "# Cadence Genus synthesis script for $TOP"
        echo "# Generated: $(date)"
        echo ""
        if [[ -n "$LIBERTY" ]]; then
          echo "set_db init_lib_search_path ."
          echo "set_db library [list \"$LIBERTY\"]"
        fi
        echo ""
        echo "# Work directory"
        echo "set_db hdl_work_directory \"${GENUS_WORK}\""
        echo "set_db log_directory \"${DIR_LOG}\""
        echo "set_db temp_directory \"${GENUS_TEMP}\""
        echo ""
        echo "# --- Read RTL ---"
        if [[ -d "$PROJECT_ROOT/rtl/common" ]]; then
          for f in "$PROJECT_ROOT"/rtl/common/*.sv "$PROJECT_ROOT"/rtl/common/*.v; do
            [[ -f "$f" ]] && echo "read_hdl -sv \"$f\""
          done
        fi
        for f in "${SRC_FILES[@]}"; do
          echo "read_hdl -sv \"$f\""
        done
        echo ""
        echo "elaborate $TOP"
        echo "check_design -unresolved"
        echo ""
        echo "# --- Constraints ---"
        echo "if {[file exists \"$SDC_FILE\"]} {"
        echo "  read_sdc \"$SDC_FILE\""
        echo "  puts \"INFO: SDC loaded from $SDC_FILE\""
        echo "} else {"
        echo "  puts \"WARNING: No SDC found at $SDC_FILE — timing estimates unreliable\""
        echo "}"
        echo ""
        echo "# --- SRAM wrapper handling ---"
        echo "# Uncomment for foundry macros:"
        echo "# set_db [get_db designs sram_sp] .dont_touch true"
        echo "# set_db [get_db designs sram_tp] .dont_touch true"
        echo "# set_db [get_db designs sram_dp] .dont_touch true"
        echo ""
        if [[ $FLATTEN -eq 1 ]]; then
          echo "ungroup -all -flatten"
        fi
        echo ""
        echo "# --- Synthesize ---"
        echo "syn_generic"
        echo "syn_map"
        echo "syn_opt"
        echo ""
        echo "# --- Reports ---"
        echo "report_area > \"$AREA_RPT\""
        echo "report_timing -nworst 10 > \"$TIMING_RPT\""
        echo "report_power > \"$POWER_RPT\""
        echo "report_qor > \"$QOR_RPT\""
        echo ""
        echo "# --- Save outputs ---"
        echo "write_hdl -mapped > \"$NETLIST\""
        echo "write_db -to_file \"${DIR_DB}/${TOP}.genus_db\""
        echo ""
        echo "exit"
      } > "$SCRIPT"
    fi

    CMD="genus -64 -files \"$SCRIPT\""
    echo "=== Cadence Genus Synthesis ==="
    echo "Script: $SCRIPT"
    echo "CMD: $CMD"
    write_replay "$CMD"
    eval "run_tool $CMD" 2>&1 | tee "$LOG"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  # =========================================================================
  # Vivado (requires user-provided script)
  # =========================================================================
  vivado)
    echo "ERROR: Vivado requires project-specific configuration." >&2
    echo "Provide --script <tcl> and execute your project flow command manually." >&2
    exit 1
    ;;

  *)
    echo "ERROR: Unknown synthesis tool: $TOOL" >&2
    echo "Supported: yosys, dc_shell, design_compiler, genus, vivado" >&2
    exit 1
    ;;
esac

# ─── Summary ───────────────────────────────────────────────────────────────
echo ""
echo "=== Synthesis Summary ==="
echo "Tool:     $TOOL"
echo "Top:      $TOP"
echo "Files:    ${#SRC_FILES[@]}"
echo "Liberty:  ${LIBERTY:-none}"
echo "SDC:      ${SDC_FILE}"
echo ""
echo "Outputs:"
echo "  Log:      ${DIR_LOG}/"
echo "  Netlist:  ${DIR_VNET}/"
[[ "$TOOL" == "dc_shell" ]] && echo "  DDC:      ${DIR_DB}/"
[[ "$TOOL" == "dc_shell" ]] && echo "  SVF:      ${DIR_SVF}/"
[[ "$TOOL" == "genus" ]]    && echo "  DB:       ${DIR_DB}/"
echo "  Reports:  ${DIR_RPT}/"
echo "  Scripts:  ${DIR_SCR}/"
echo "  Replay:   ${DIR_REPLAY}/run_syn_${TOOL}_latest.sh"
echo ""
echo "Exit:     $EXIT_CODE"
exit "$EXIT_CODE"

# rat-version: 0.8.19
