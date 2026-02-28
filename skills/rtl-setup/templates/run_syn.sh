#!/usr/bin/env bash
# run_syn.sh — Synthesis runner for RTL modules
# Usage: syn/scripts/run_syn.sh [OPTIONS]
#
# Supports: yosys (default)
# Commercial: dc_shell, genus, vivado (via --tool flag)
#
# Examples:
#   syn/scripts/run_syn.sh --tool yosys --top top_module -f rtl/filelist_top.f
#   syn/scripts/run_syn.sh --tool yosys --top entropy_coder -f rtl/filelist_entropy.f --liberty sky130.lib

set -euo pipefail

# ─── Defaults ───────────────────────────────────────────────────────────────
TOOL="yosys"
TOP=""
FILELIST=""
OUTDIR="syn/reports"
LIBERTY=""
FILES=()
VERBOSE=0
FLATTEN=0

# ─── Usage ──────────────────────────────────────────────────────────────────
usage() {
  cat <<'USAGE'
Usage: syn/scripts/run_syn.sh [OPTIONS] [SV_FILES...]

Options:
  --tool <name>     yosys|dc_shell|genus|vivado (default: yosys)
  --top <module>    Top-level module name (required)
  -f <filelist>     Source filelist (.f file)
  --outdir <dir>    Report output directory (default: syn/reports)
  --liberty <file>  Liberty (.lib) file for technology mapping
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
    --flatten) FLATTEN=1; shift ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help) usage ;;
    -*)        echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
    *)         FILES+=("$1"); shift ;;
  esac
done

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
SRC_FILES+=("${FILES[@]}")

if [[ ${#SRC_FILES[@]} -eq 0 ]]; then
  echo "ERROR: No source files specified. Use -f <filelist> or pass .sv files directly." >&2
  exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# ─── Tool-specific synthesis ───────────────────────────────────────────────
case "$TOOL" in
  yosys)
    SCRIPT="$OUTDIR/synth_${TOP}_${TIMESTAMP}.ys"
    REPORT="$OUTDIR/synth_${TOP}_${TIMESTAMP}.log"
    NETLIST="$OUTDIR/${TOP}_netlist.json"

    # Generate Yosys script
    {
      echo "# Yosys synthesis script for $TOP"
      echo "# Generated: $(date)"
      echo ""
      for f in "${SRC_FILES[@]}"; do
        echo "read_verilog -sv $f"
      done
      echo ""
      echo "hierarchy -check -top $TOP"
      echo "proc"
      echo "opt"
      [[ $FLATTEN -eq 1 ]] && echo "flatten"
      echo ""
      if [[ -n "$LIBERTY" ]]; then
        echo "# Technology mapping"
        echo "dfflibmap -liberty $LIBERTY"
        echo "abc -liberty $LIBERTY"
      else
        echo "# Generic synthesis (no technology mapping)"
        echo "synth -top $TOP"
      fi
      echo ""
      echo "# Reports"
      echo "stat -top $TOP"
      echo "write_json $NETLIST"
    } > "$SCRIPT"

    echo "=== Yosys Synthesis ==="
    echo "Script: $SCRIPT"
    echo "CMD: yosys -s $SCRIPT"
    yosys -s "$SCRIPT" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  dc_shell|genus|vivado)
    echo "ERROR: Commercial tool '$TOOL' requires project-specific configuration." >&2
    echo "Please create syn/scripts/${TOOL}_syn.tcl with your license and library setup." >&2
    exit 1
    ;;

  *)
    echo "ERROR: Unknown synthesis tool: $TOOL" >&2
    echo "Supported: yosys, dc_shell, genus, vivado" >&2
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

if [[ "$TOOL" == "yosys" && -f "$REPORT" ]]; then
  echo ""
  echo "--- Cell Statistics ---"
  grep -A 30 "Number of cells:" "$REPORT" 2>/dev/null || echo "(no cell stats found)"
  echo ""
  echo "--- Flip-flops ---"
  grep -i "flip-flop\|DFF\|\\$_DFF_" "$REPORT" 2>/dev/null || echo "(no FF stats found)"
  echo ""
  # Check for unmapped cells
  UNMAPPED=$(grep -c "UNMAP\|\\$_.*_\$" "$REPORT" 2>/dev/null || echo 0)
  echo "Unmapped cells: $UNMAPPED"
  echo "Netlist: $NETLIST"
fi

echo "Exit:     $EXIT_CODE"
exit "$EXIT_CODE"
