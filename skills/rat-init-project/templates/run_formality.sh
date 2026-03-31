#!/usr/bin/env bash
# run_formality.sh — Synopsys Formality equivalence checking
# Usage: syn/scripts/run_formality.sh [OPTIONS]
#
# Compares RTL (reference) against gate-level netlist (implementation)
# to prove functional equivalence after synthesis.
#
# Examples:
#   syn/scripts/run_formality.sh --top top_module --rtl rtl/filelist_top.f --netlist syn/reports/top_netlist.v
#   syn/scripts/run_formality.sh --top top_module --rtl rtl/filelist_top.f --netlist syn/reports/top_netlist.v --svf syn/output/top.svf

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
TOP=""
RTL_FILELIST=""
NETLIST=""
SVF=""
LIBERTY=""
OUTDIR="syn/reports"
SCRIPT_PATH=""
VERBOSE=0

# ─── Usage ──────────────────────────────────────────────────────────────────
usage() {
  cat <<'USAGE'
Usage: syn/scripts/run_formality.sh [OPTIONS]

Options:
  --top <module>      Top-level module name (required)
  --rtl <filelist>    RTL source filelist (.f file, reference)
  --netlist <file>    Gate-level netlist (.v, implementation)
  --svf <file>        SVF guidance file from DC (optional)
  --liberty <file>    Liberty (.lib) technology library
  --outdir <dir>      Report output directory (default: syn/reports)
  --script <file>     Custom Formality Tcl script
  -v, --verbose       Verbose output
  -h, --help          Show this help
USAGE
  exit 0
}

# ─── Parse args ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --top)     TOP="$2"; shift 2 ;;
    --rtl)     RTL_FILELIST="$2"; shift 2 ;;
    --netlist) NETLIST="$2"; shift 2 ;;
    --svf)     SVF="$2"; shift 2 ;;
    --liberty) LIBERTY="$2"; shift 2 ;;
    --outdir)  OUTDIR="$2"; shift 2 ;;
    --script)  SCRIPT_PATH="$2"; shift 2 ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help) usage ;;
    -*)        echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
    *)         echo "ERROR: Unexpected argument: $1" >&2; exit 1 ;;
  esac
done

[[ -z "$TOP" ]] && { echo "ERROR: --top is required" >&2; exit 1; }
[[ -z "$RTL_FILELIST" ]] && { echo "ERROR: --rtl is required" >&2; exit 1; }
[[ -z "$NETLIST" ]] && { echo "ERROR: --netlist is required" >&2; exit 1; }

mkdir -p "$OUTDIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_CWD="$(pwd)"
REPLAY_DIR="$OUTDIR/replay"
mkdir -p "$REPLAY_DIR"
REPLAY_SCRIPT="$REPLAY_DIR/run_formality_${TOP}_${TIMESTAMP}.sh"
REPORT="$OUTDIR/formality_${TOP}_${TIMESTAMP}.log"

# ─── Collect RTL files ────────────────────────────────────────────────────
RTL_FILES=()
while IFS= read -r line; do
  line=$(echo "$line" | sed 's|//.*||' | xargs)
  [[ -z "$line" ]] && continue
  [[ "$line" == +* ]] && continue
  RTL_FILES+=("$line")
done < "$RTL_FILELIST"

# ─── Generate Formality Tcl ──────────────────────────────────────────────
FM_TCL="$SCRIPT_PATH"
if [[ -z "$FM_TCL" ]]; then
  FM_TCL="$OUTDIR/formality_${TOP}_${TIMESTAMP}.tcl"
fi

if [[ ! -f "$FM_TCL" ]] || [[ -z "$SCRIPT_PATH" ]]; then
  {
    echo "# Formality equivalence checking script for $TOP"
    echo "# Generated: $(date)"
    echo ""
    [[ -n "$SVF" ]] && echo "set_svf \"$SVF\""
    echo ""
    echo "# --- Reference design (RTL) ---"
    for f in "${RTL_FILES[@]}"; do
      echo "read_verilog -container r -libname WORK -05 \"$f\""
    done
    echo "set_top r:/WORK/$TOP"
    echo ""
    echo "# --- Implementation design (netlist) ---"
    [[ -n "$LIBERTY" ]] && echo "read_db -container i \"$LIBERTY\""
    echo "read_verilog -container i -libname WORK -05 \"$NETLIST\""
    echo "set_top i:/WORK/$TOP"
    echo ""
    echo "# --- Blackbox SRAM wrappers (behavioral vs foundry macro) ---"
    echo "# Uncomment for designs using rtl/common/ SRAM wrappers:"
    echo "# set_black_box r:/WORK/sram_sp; set_black_box i:/WORK/sram_sp"
    echo "# set_black_box r:/WORK/sram_tp; set_black_box i:/WORK/sram_tp"
    echo "# set_black_box r:/WORK/sram_dp; set_black_box i:/WORK/sram_dp"
    echo ""
    echo "# --- Matching and verification ---"
    echo "match"
    echo "set result [verify]"
    echo ""
    echo "# --- Reports ---"
    echo "report_matched_points > \"$OUTDIR/formality_matched_${TOP}.rpt\""
    echo "report_unmatched_points > \"$OUTDIR/formality_unmatched_${TOP}.rpt\""
    echo "report_failing_points > \"$OUTDIR/formality_failing_${TOP}.rpt\""
    echo "report_status > \"$OUTDIR/formality_status_${TOP}.rpt\""
    echo ""
    echo "if {\$result} {"
    echo "  puts \"VERIFICATION PASSED\""
    echo "  exit 0"
    echo "} else {"
    echo "  puts \"VERIFICATION FAILED\""
    echo "  exit 1"
    echo "}"
  } > "$FM_TCL"
fi

# ─── Execute ─────────────────────────────────────────────────────────────
CMD="fm_shell -64bit -f \"$FM_TCL\""

echo "=== Formality Equivalence Check ==="
echo "Top:     $TOP"
echo "RTL:     $RTL_FILELIST (${#RTL_FILES[@]} files)"
echo "Netlist: $NETLIST"
[[ -n "$SVF" ]] && echo "SVF:     $SVF"
echo "Script:  $FM_TCL"
echo "CMD:     $CMD"

cat > "$REPLAY_SCRIPT" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$RUN_CWD"
$CMD
EOF
chmod +x "$REPLAY_SCRIPT"
cp "$REPLAY_SCRIPT" "$REPLAY_DIR/run_formality_${TOP}_latest.sh"

eval "run_tool $CMD" 2>&1 | tee "$REPORT"
EXIT_CODE=${PIPESTATUS[0]}

# ─── Summary ─────────────────────────────────────────────────────────────
echo ""
echo "=== Formality Summary ==="
echo "Top:      $TOP"
echo "Result:   $(grep -E 'PASSED|FAILED' "$REPORT" 2>/dev/null | tail -1 || echo 'UNKNOWN')"
echo "Report:   $REPORT"
echo "Replay:   $REPLAY_SCRIPT"
echo "Exit:     $EXIT_CODE"

exit "$EXIT_CODE"

# rat-version: 0.8.14
