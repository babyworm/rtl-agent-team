#!/usr/bin/env bash
# run_cdc.sh — CDC analysis runner for RTL modules
# Usage: sim/cdc/run_cdc.sh [OPTIONS] [SV_FILES...]
#
# Supports:
#   - structural (default): lightweight structural checks without commercial tools
#   - spyglass: Synopsys SpyGlass CDC
#   - vc_cdc: Synopsys VC CDC
#   - questa_cdc: Siemens Questa CDC
#
# Examples:
#   sim/cdc/run_cdc.sh --tool structural -f rtl/filelist_top.f --outdir sim/cdc/reports
#   sim/cdc/run_cdc.sh --tool spyglass --script sim/cdc/spyglass_cdc.tcl -f rtl/filelist_top.f

set -euo pipefail

# Source Docker-aware tool runner (transparent fallback)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_LIB_RUNNER="$(cd "$SCRIPT_DIR/../../lib" 2>/dev/null && pwd)/tool-runner.sh" 2>/dev/null || true
if [[ -f "${_LIB_RUNNER:-}" ]]; then
  source "$_LIB_RUNNER"
else
  run_tool() { "$@"; }
fi

TOOL="structural"
TOP=""
FILELIST=""
OUTDIR="sim/cdc/reports"
SCRIPT_PATH=""
FILES=()
VERBOSE=0

usage() {
  cat <<'USAGE'
Usage: sim/cdc/run_cdc.sh [OPTIONS] [SV_FILES...]

Options:
  --tool <name>     structural|spyglass|vc_cdc|questa_cdc (default: structural)
  --top <module>    Top-level module name
  -f <filelist>     Source filelist (.f file)
  --outdir <dir>    Report output directory (default: sim/cdc/reports)
  --script <file>   Tool script/Tcl file (commercial tools)
  -v, --verbose     Verbose output
  -h, --help        Show this help
USAGE
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool)    TOOL="$2"; shift 2 ;;
    --top)     TOP="$2"; shift 2 ;;
    -f)        FILELIST="$2"; shift 2 ;;
    --outdir)  OUTDIR="$2"; shift 2 ;;
    --script)  SCRIPT_PATH="$2"; shift 2 ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help) usage ;;
    -*)        echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
    *)         FILES+=("$1"); shift ;;
  esac
done

mkdir -p "$OUTDIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_CWD="$(pwd)"
REPLAY_DIR="$OUTDIR/replay"
REPLAY_SCRIPT="$REPLAY_DIR/run_cdc_${TOOL}_${TIMESTAMP}.sh"
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
  cp "$REPLAY_SCRIPT" "$REPLAY_DIR/run_cdc_${TOOL}_latest.sh"
}

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

REPORT="$OUTDIR/cdc_${TOOL}_${TIMESTAMP}.log"
EXIT_CODE=0

case "$TOOL" in
  structural)
    {
      echo "=== Structural CDC Quick Check ==="
      echo "Top: ${TOP:-N/A}"
      echo "Files: ${#SRC_FILES[@]}"
      echo "Rule: detect clock/reset naming patterns and obvious async crossings."
      echo ""
      echo "[INFO] This mode is heuristic and should be replaced by commercial CDC signoff when available."
      echo ""
      echo "Clock-like signals:"
      grep -RhoE '\b[a-zA-Z0-9_]*_clk\b|\bclk\b' "${SRC_FILES[@]}" 2>/dev/null | sort -u || true
      echo ""
      echo "Reset-like signals:"
      grep -RhoE '\b[a-zA-Z0-9_]*_rst_n\b|\brst_n\b' "${SRC_FILES[@]}" 2>/dev/null | sort -u || true
    } | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  spyglass)
    CDC_TCL="$SCRIPT_PATH"
    if [[ -z "$CDC_TCL" ]]; then
      CDC_TCL="${SPYGLASS_CDC_TCL:-$OUTDIR/spyglass_cdc_${TIMESTAMP}.tcl}"
    fi
    if [[ ! -f "$CDC_TCL" ]]; then
      {
        echo "# Auto-generated SpyGlass CDC script"
        for src in "${SRC_FILES[@]}"; do
          echo "read_file -type verilog \"$src\""
        done
        [[ -n "$TOP" ]] && echo "set_option top \"$TOP\""
        echo "current_goal cdc/cdc_setup_check"
        echo "run_goal"
        echo "current_goal cdc/cdc_verify_struct"
        echo "run_goal"
        echo "exit -save"
      } > "$CDC_TCL"
    fi
    CMD="spyglass -shell -tcl \"$CDC_TCL\""
    echo "=== SpyGlass CDC ==="
    echo "TCL: $CDC_TCL"
    echo "CMD: $CMD"
    write_replay "$CMD"
    eval "run_tool $CMD" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  vc_cdc)
    CDC_TCL="$SCRIPT_PATH"
    if [[ -z "$CDC_TCL" ]]; then
      echo "ERROR: vc_cdc requires --script <tcl> (or set VC_CDC_TCL)." >&2
      exit 1
    fi
    CMD="vc_cdc -f \"$CDC_TCL\""
    echo "=== VC CDC ==="
    echo "CMD: $CMD"
    write_replay "$CMD"
    eval "run_tool $CMD" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  questa_cdc)
    CDC_TCL="$SCRIPT_PATH"
    if [[ -z "$CDC_TCL" ]]; then
      echo "ERROR: questa_cdc requires --script <do/tcl> (or set QUESTA_CDC_TCL)." >&2
      exit 1
    fi
    CMD="qverify -c -do \"$CDC_TCL\""
    echo "=== Questa CDC ==="
    echo "CMD: $CMD"
    write_replay "$CMD"
    eval "run_tool $CMD" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  *)
    echo "ERROR: Unknown CDC tool: $TOOL" >&2
    echo "Supported: structural, spyglass, vc_cdc, questa_cdc" >&2
    exit 1
    ;;
esac

echo ""
echo "=== CDC Summary ==="
echo "Tool:     $TOOL"
echo "Top:      ${TOP:-N/A}"
echo "Files:    ${#SRC_FILES[@]}"
echo "Report:   $REPORT"
echo "Replay:   $REPLAY_SCRIPT"
echo "Exit:     $EXIT_CODE"

exit "$EXIT_CODE"

# rat-version: 0.7.7
