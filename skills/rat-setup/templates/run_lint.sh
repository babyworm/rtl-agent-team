#!/usr/bin/env bash
# run_lint.sh — Lint runner for RTL modules
# Usage: lint/scripts/run_lint.sh [OPTIONS] [SV_FILES...]
#
# Supports: verilator (default), verible, slang
# Commercial: spyglass (via --tool flag)
#
# Examples:
#   lint/scripts/run_lint.sh --tool verilator -f rtl/filelist_top.f
#   lint/scripts/run_lint.sh --tool verible rtl/entropy/entropy_coder.sv
#   lint/scripts/run_lint.sh --tool slang --top top_module -f rtl/filelist_top.f

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
TOOL="verilator"
TOP=""
FILELIST=""
OUTDIR="lint/reports"
WAIVER=""
SCRIPT_PATH=""
FILES=()
VERBOSE=0

# ─── Usage ──────────────────────────────────────────────────────────────────
usage() {
  cat <<'USAGE'
Usage: lint/scripts/run_lint.sh [OPTIONS] [SV_FILES...]

Options:
  --tool <name>     verilator|verible|slang|spyglass (default: verilator)
  --top <module>    Top-level module name (for hierarchy-aware lint)
  -f <filelist>     Source filelist (.f file)
  --outdir <dir>    Report output directory (default: lint/reports)
  --waiver <file>   Waiver file (verilator .vlt, verible .rules)
  --script <file>   Tool script/Tcl file (spyglass)
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
    --waiver)  WAIVER="$2"; shift 2 ;;
    --script)  SCRIPT_PATH="$2"; shift 2 ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help) usage ;;
    -*)        echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
    *)         FILES+=("$1"); shift ;;
  esac
done

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
REPLAY_SCRIPT="$REPLAY_DIR/run_lint_${TOOL}_${TIMESTAMP}.sh"
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
  cp "$REPLAY_SCRIPT" "$REPLAY_DIR/run_lint_${TOOL}_latest.sh"
}

# ─── Tool-specific lint ────────────────────────────────────────────────────
case "$TOOL" in
  verilator)
    CMD="verilator --lint-only -Wall -Wpedantic -sv"
    [[ -n "$TOP" ]] && CMD="$CMD --top-module $TOP"
    [[ -n "$WAIVER" ]] && CMD="$CMD $WAIVER"
    CMD="$CMD ${SRC_FILES[*]}"
    REPORT="$OUTDIR/verilator_lint_${TIMESTAMP}.log"
    echo "=== Verilator Lint ==="
    echo "CMD: $CMD"
    write_replay "$CMD"
    eval "run_tool $CMD" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  verible)
    CMD="verible-verilog-lint"
    [[ -n "$WAIVER" ]] && CMD="$CMD --rules_config=$WAIVER"
    CMD="$CMD ${SRC_FILES[*]}"
    REPORT="$OUTDIR/verible_lint_${TIMESTAMP}.log"
    echo "=== Verible Lint ==="
    echo "CMD: $CMD"
    write_replay "$CMD"
    eval "run_tool $CMD" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  slang)
    CMD="slang --color-diagnostics"
    [[ -n "$TOP" ]] && CMD="$CMD --top $TOP"
    CMD="$CMD ${SRC_FILES[*]}"
    REPORT="$OUTDIR/slang_lint_${TIMESTAMP}.log"
    echo "=== slang Lint ==="
    echo "CMD: $CMD"
    write_replay "$CMD"
    eval "run_tool $CMD" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  spyglass)
    REPORT="$OUTDIR/spyglass_lint_${TIMESTAMP}.log"
    SPYGLASS_TCL="$SCRIPT_PATH"
    if [[ -z "$SPYGLASS_TCL" ]]; then
      SPYGLASS_TCL="${SPYGLASS_LINT_TCL:-$OUTDIR/spyglass_lint_${TIMESTAMP}.tcl}"
    fi

    if [[ ! -f "$SPYGLASS_TCL" ]]; then
      {
        echo "# Auto-generated SpyGlass lint script"
        for src in "${SRC_FILES[@]}"; do
          echo "read_file -type verilog \"$src\""
        done
        [[ -n "$TOP" ]] && echo "set_option top \"$TOP\""
        [[ -n "$FILELIST" ]] && echo "read_file -type verilog \"$FILELIST\""
        echo "current_goal lint/lint_rtl"
        echo "run_goal"
        echo "exit -save"
      } > "$SPYGLASS_TCL"
    fi

    CMD="spyglass -shell -tcl \"$SPYGLASS_TCL\""
    echo "=== SpyGlass Lint ==="
    echo "TCL: $SPYGLASS_TCL"
    echo "CMD: $CMD"
    write_replay "$CMD"
    eval "run_tool $CMD" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  *)
    echo "ERROR: Unknown lint tool: $TOOL" >&2
    echo "Supported: verilator, verible, slang, spyglass" >&2
    exit 1
    ;;
esac

# ─── Summary ───────────────────────────────────────────────────────────────
ERRORS=$(grep -ci "error" "$REPORT" 2>/dev/null || echo 0)
WARNINGS=$(grep -ci "warning" "$REPORT" 2>/dev/null || echo 0)

echo ""
echo "=== Lint Summary ==="
echo "Tool:     $TOOL"
echo "Files:    ${#SRC_FILES[@]}"
echo "Errors:   $ERRORS"
echo "Warnings: $WARNINGS"
echo "Report:   $REPORT"
echo "Replay:   $REPLAY_SCRIPT"
echo "Exit:     $EXIT_CODE"

exit "$EXIT_CODE"

# rat-version: 0.7.7
