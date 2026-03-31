#!/usr/bin/env bash
# run_syn.sh — Synthesis runner for RTL modules
# Usage: syn/scripts/run_syn.sh [OPTIONS]
#
# Supports: yosys (default)
# Commercial: dc_shell/design_compiler, genus, vivado (via --tool flag)
#
# Examples:
#   syn/scripts/run_syn.sh --tool yosys --top top_module -f rtl/filelist_top.f
#   syn/scripts/run_syn.sh --tool yosys --top entropy_coder -f rtl/filelist_entropy.f --liberty sky130.lib

set -euo pipefail

# Source Docker-aware tool runner (transparent fallback)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_LIB_RUNNER="$(cd "$SCRIPT_DIR/../../lib" 2>/dev/null && pwd)/tool-runner.sh" 2>/dev/null || true
if [[ -f "${_LIB_RUNNER:-}" ]]; then
  source "$_LIB_RUNNER"
else
  run_tool() { "$@"; }
fi

# ─── Defaults ───────────────────────────────────────────────────────────────
TOOL="yosys"
TOP=""
FILELIST=""
OUTDIR="syn/reports"
LIBERTY=""
SCRIPT_PATH=""
FILES=()
VERBOSE=0
FLATTEN=0

# ─── Usage ──────────────────────────────────────────────────────────────────
usage() {
  cat <<'USAGE'
Usage: syn/scripts/run_syn.sh [OPTIONS] [SV_FILES...]

Options:
  --tool <name>     yosys|dc_shell|design_compiler|genus|vivado (default: yosys)
  --top <module>    Top-level module name (required)
  -f <filelist>     Source filelist (.f file)
  --outdir <dir>    Report output directory (default: syn/reports)
  --liberty <file>  Liberty (.lib) file for technology mapping
  --script <file>   Tool script/Tcl file (dc_shell/genus/vivado)
  --flatten         Flatten design before synthesis
  -v, --verbose     Verbose output
  -h, --help        Show this help
USAGE
  exit 0
}

# ─── Parse args ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool)    TOOL="$2"; shift 2 ;;
    --top)     TOP="$2"; shift 2 ;;
    -f)        FILELIST="$2"; shift 2 ;;
    --outdir)  OUTDIR="$2"; shift 2 ;;
    --liberty) LIBERTY="$2"; shift 2 ;;
    --script)  SCRIPT_PATH="$2"; shift 2 ;;
    --flatten) FLATTEN=1; shift ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help) usage ;;
    -*)        echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
    *)         FILES+=("$1"); shift ;;
  esac
done

if [[ "$TOOL" == "design_compiler" ]]; then
  TOOL="dc_shell"
fi

if [[ -z "$TOP" ]]; then
  echo "ERROR: --top <module> is required" >&2
  exit 1
fi

mkdir -p "$OUTDIR"

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

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_CWD="$(pwd)"
REPLAY_DIR="$OUTDIR/replay"
REPLAY_SCRIPT="$REPLAY_DIR/run_syn_${TOOL}_${TOP}_${TIMESTAMP}.sh"
mkdir -p "$REPLAY_DIR"

write_replay() {
  local cmd="$1"
  cat > "$REPLAY_SCRIPT" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$RUN_CWD"
$cmd
EOF
  chmod +x "$REPLAY_SCRIPT"
  cp "$REPLAY_SCRIPT" "$REPLAY_DIR/run_syn_${TOOL}_latest.sh"
}

# ─── Tool-specific synthesis ───────────────────────────────────────────────
case "$TOOL" in
  yosys)
    SCRIPT="$OUTDIR/synth_${TOP}_${TIMESTAMP}.ys"
    REPORT="$OUTDIR/synth_${TOP}_${TIMESTAMP}.log"
    NETLIST="$OUTDIR/${TOP}_netlist.json"

    # sv2v conversion (SystemVerilog → Verilog for Yosys compatibility)
    SV2V_OUT="$OUTDIR/${TOP}_v2v.v"
    if command -v sv2v >/dev/null 2>&1; then
      # Auto-include rtl/common/ (SRAM wrappers, shared utilities)
      COMMON_FILES=()
      if [[ -d rtl/common ]]; then
        while IFS= read -r cf; do
          COMMON_FILES+=("$cf")
        done < <(find rtl/common -name '*.sv' -o -name '*.v' 2>/dev/null | sort)
      fi
      echo "=== sv2v Conversion ==="
      sv2v "${COMMON_FILES[@]}" "${SRC_FILES[@]}" -o "$SV2V_OUT"
      echo "Converted: $SV2V_OUT (${#SRC_FILES[@]} source + ${#COMMON_FILES[@]} common files)"
      USE_SV2V=1
    else
      echo "WARNING: sv2v not found — using read_verilog -sv (limited SV support in Yosys)"
      USE_SV2V=0
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
        # Auto-include rtl/common/ for SRAM wrappers
        if [[ -d rtl/common ]]; then
          for f in rtl/common/*.sv rtl/common/*.v; do
            [[ -f "$f" ]] && echo "read_verilog -sv $f"
          done
        fi
      fi
      echo ""
      echo "hierarchy -check -top $TOP"
      echo "proc; opt; fsm; opt"
      [[ $FLATTEN -eq 1 ]] && echo "flatten"
      echo ""
      echo "# Memory handling (SRAM wrappers → inferred memory blocks)"
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
        echo "# Generic synthesis (no technology mapping — area estimates less accurate)"
        echo "techmap; opt"
        echo "stat -top $TOP"
      fi
      echo ""
      echo "# Post-synthesis checks"
      echo "scc -max_depth 10"
      echo "write_json $NETLIST"
    } > "$SCRIPT"

    echo "=== Yosys Synthesis ==="
    echo "Script: $SCRIPT"
    echo "CMD: yosys -s $SCRIPT"
    write_replay "yosys -s \"$SCRIPT\""
    run_tool yosys -s "$SCRIPT" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  dc_shell)
    REPORT="$OUTDIR/synth_${TOP}_${TIMESTAMP}.log"
    NETLIST="$OUTDIR/${TOP}_netlist.v"
    AREA_RPT="$OUTDIR/${TOP}_area_${TIMESTAMP}.rpt"
    TIMING_RPT="$OUTDIR/${TOP}_timing_${TIMESTAMP}.rpt"
    SCRIPT="$SCRIPT_PATH"
    if [[ -z "$SCRIPT" ]]; then
      SCRIPT="${DC_SYN_TCL:-$OUTDIR/dc_syn_${TOP}_${TIMESTAMP}.tcl}"
    fi

    if [[ ! -f "$SCRIPT" ]]; then
      SDC_FILE="syn/constraints/design.sdc"
      POWER_RPT="$OUTDIR/${TOP}_power_${TIMESTAMP}.rpt"
      QOR_RPT="$OUTDIR/${TOP}_qor_${TIMESTAMP}.rpt"
      {
        echo "# Auto-generated Design Compiler script"
        echo "# Generated: $(date)"
        echo ""
        echo "set_app_var search_path [list .]"
        if [[ -n "$LIBERTY" ]]; then
          echo "set_app_var target_library [list \"$LIBERTY\"]"
          echo "set_app_var link_library [list \"*\" \"$LIBERTY\"]"
        fi
        echo ""
        echo "# --- Read RTL ---"
        # Auto-include rtl/common/ for SRAM wrappers
        if [[ -d rtl/common ]]; then
          for f in rtl/common/*.sv rtl/common/*.v; do
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
        echo "# Preserve SRAM wrappers as black boxes if foundry macros are intended"
        echo "# Uncomment and adjust for your target library:"
        echo "# set_dont_touch [get_designs sram_sp]"
        echo "# set_dont_touch [get_designs sram_dp]"
        echo "# set_dont_touch [get_designs sram_tdp]"
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
        echo "# --- Netlist ---"
        echo "change_names -rules verilog -hierarchy"
        echo "write -hierarchy -format verilog -output \"$NETLIST\""
        echo ""
        echo "quit"
      } > "$SCRIPT"
    fi

    CMD="dc_shell -64bit -f \"$SCRIPT\""
    echo "=== Design Compiler Synthesis ==="
    echo "Script: $SCRIPT"
    echo "CMD: $CMD"
    write_replay "$CMD"
    eval "run_tool $CMD" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  genus)
    REPORT="$OUTDIR/synth_${TOP}_${TIMESTAMP}.log"
    NETLIST="$OUTDIR/${TOP}_netlist.v"
    AREA_RPT="$OUTDIR/${TOP}_area_${TIMESTAMP}.rpt"
    TIMING_RPT="$OUTDIR/${TOP}_timing_${TIMESTAMP}.rpt"
    SCRIPT="$SCRIPT_PATH"
    if [[ -z "$SCRIPT" ]]; then
      SCRIPT="${GENUS_SYN_TCL:-$OUTDIR/genus_syn_${TOP}_${TIMESTAMP}.tcl}"
    fi

    if [[ ! -f "$SCRIPT" ]]; then
      SDC_FILE="syn/constraints/design.sdc"
      POWER_RPT="$OUTDIR/${TOP}_power_${TIMESTAMP}.rpt"
      QOR_RPT="$OUTDIR/${TOP}_qor_${TIMESTAMP}.rpt"
      {
        echo "# Auto-generated Cadence Genus synthesis script"
        echo "# Generated: $(date)"
        echo ""
        if [[ -n "$LIBERTY" ]]; then
          echo "set_db init_lib_search_path ."
          echo "set_db library [list \"$LIBERTY\"]"
        fi
        echo ""
        echo "# --- Read RTL ---"
        # Auto-include rtl/common/ for SRAM wrappers
        if [[ -d rtl/common ]]; then
          for f in rtl/common/*.sv rtl/common/*.v; do
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
        echo "# Preserve SRAM wrappers as black boxes if foundry macros are intended"
        echo "# Uncomment and adjust for your target library:"
        echo "# set_db [get_db designs sram_sp] .dont_touch true"
        echo "# set_db [get_db designs sram_dp] .dont_touch true"
        echo "# set_db [get_db designs sram_tdp] .dont_touch true"
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
        echo "# --- Netlist ---"
        echo "write_hdl -mapped > \"$NETLIST\""
        echo ""
        echo "exit"
      } > "$SCRIPT"
    fi

    CMD="genus -64 -files \"$SCRIPT\""
    echo "=== Cadence Genus Synthesis ==="
    echo "Script: $SCRIPT"
    echo "CMD: $CMD"
    write_replay "$CMD"
    eval "run_tool $CMD" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

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
echo "Report:   $REPORT"
echo "Replay:   $REPLAY_SCRIPT"

if [[ "$TOOL" == "yosys" && -f "$REPORT" ]]; then
  echo ""
  echo "--- Cell Statistics ---"
  grep -A 30 "Number of cells:" "$REPORT" 2>/dev/null || echo "(no cell stats found)"
  echo ""
  echo "--- Flip-flops ---"
  grep -i 'flip-flop\|DFF\|\$_DFF_' "$REPORT" 2>/dev/null || echo "(no FF stats found)"
  echo ""
  # Check for unmapped cells
  UNMAPPED=$(grep -c 'UNMAP\|\$_.*_\$' "$REPORT" 2>/dev/null || echo 0)
  echo "Unmapped cells: $UNMAPPED"
  echo "Netlist: $NETLIST"
fi

echo "Exit:     $EXIT_CODE"
exit "$EXIT_CODE"

# rat-version: 0.8.14
