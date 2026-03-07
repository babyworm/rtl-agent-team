#!/usr/bin/env bash
# run_conformal.sh — Cadence Conformal LEC equivalence checking
# Usage: syn/scripts/run_conformal.sh [OPTIONS]
#
# Compares RTL (golden) against gate-level netlist (revised)
# to prove functional equivalence after synthesis.
#
# Examples:
#   syn/scripts/run_conformal.sh --top top_module --rtl rtl/filelist_top.f --netlist syn/reports/top_netlist.v
#   syn/scripts/run_conformal.sh --top top_module --rtl rtl/filelist_top.f --netlist syn/reports/top_netlist.v --liberty tech.lib

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
LIBERTY=""
OUTDIR="syn/reports"
SCRIPT_PATH=""
VERBOSE=0

# ─── Usage ──────────────────────────────────────────────────────────────────
usage() {
  cat <<'USAGE'
Usage: syn/scripts/run_conformal.sh [OPTIONS]

Options:
  --top <module>      Top-level module name (required)
  --rtl <filelist>    RTL source filelist (.f file, golden)
  --netlist <file>    Gate-level netlist (.v, revised)
  --liberty <file>    Liberty (.lib) technology library
  --outdir <dir>      Report output directory (default: syn/reports)
  --script <file>     Custom Conformal dofile
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
REPLAY_SCRIPT="$REPLAY_DIR/run_conformal_${TOP}_${TIMESTAMP}.sh"
REPORT="$OUTDIR/conformal_${TOP}_${TIMESTAMP}.log"

# ─── Collect RTL files ────────────────────────────────────────────────────
RTL_FILES=()
while IFS= read -r line; do
  line=$(echo "$line" | sed 's|//.*||' | xargs)
  [[ -z "$line" ]] && continue
  [[ "$line" == +* ]] && continue
  RTL_FILES+=("$line")
done < "$RTL_FILELIST"

# ─── Generate Conformal dofile ────────────────────────────────────────────
LEC_DO="$SCRIPT_PATH"
if [[ -z "$LEC_DO" ]]; then
  LEC_DO="$OUTDIR/conformal_${TOP}_${TIMESTAMP}.do"
fi

if [[ ! -f "$LEC_DO" ]] || [[ -z "$SCRIPT_PATH" ]]; then
  {
    echo "// Conformal LEC dofile for $TOP"
    echo "// Generated: $(date)"
    echo ""
    echo "// --- Golden design (RTL) ---"
    for f in "${RTL_FILES[@]}"; do
      echo "read design -golden -verilog2k \"$f\""
    done
    echo ""
    echo "// --- Revised design (netlist) ---"
    [[ -n "$LIBERTY" ]] && echo "read library -liberty \"$LIBERTY\""
    echo "read design -revised -verilog2k \"$NETLIST\""
    echo ""
    echo "set system mode lec"
    echo "set root module $TOP -golden"
    echo "set root module $TOP -revised"
    echo ""
    echo "// --- Map and verify ---"
    echo "map key points"
    echo "add compared points -all"
    echo "compare"
    echo ""
    echo "// --- Reports ---"
    echo "report compared points -all > \"$OUTDIR/conformal_compared_${TOP}.rpt\""
    echo "report uncompared points > \"$OUTDIR/conformal_uncompared_${TOP}.rpt\""
    echo "report statistics > \"$OUTDIR/conformal_stats_${TOP}.rpt\""
    echo ""
    echo "exit -force"
  } > "$LEC_DO"
fi

# ─── Execute ─────────────────────────────────────────────────────────────
CMD="lec -64bit -dofile \"$LEC_DO\""

echo "=== Conformal LEC Equivalence Check ==="
echo "Top:     $TOP"
echo "RTL:     $RTL_FILELIST (${#RTL_FILES[@]} files)"
echo "Netlist: $NETLIST"
echo "Script:  $LEC_DO"
echo "CMD:     $CMD"

cat > "$REPLAY_SCRIPT" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$RUN_CWD"
$CMD
EOF
chmod +x "$REPLAY_SCRIPT"
cp "$REPLAY_SCRIPT" "$REPLAY_DIR/run_conformal_${TOP}_latest.sh"

eval "run_tool $CMD" 2>&1 | tee "$REPORT"
EXIT_CODE=${PIPESTATUS[0]}

# ─── Summary ─────────────────────────────────────────────────────────────
echo ""
echo "=== Conformal Summary ==="
echo "Top:      $TOP"
echo "Report:   $REPORT"
echo "Replay:   $REPLAY_SCRIPT"
echo "Exit:     $EXIT_CODE"

exit "$EXIT_CODE"
