#!/usr/bin/env bash
# run_lint.sh — Lint runner for RTL modules
# Usage: lint/scripts/run_lint.sh [OPTIONS] [SV_FILES...]
#
# Supports: verilator (default), verible, slang
# Commercial: spyglass, hal (via --tool flag)
#
# Examples:
#   lint/scripts/run_lint.sh --tool verilator -f rtl/filelist_top.f
#   lint/scripts/run_lint.sh --tool verible rtl/entropy/entropy_coder.sv
#   lint/scripts/run_lint.sh --tool slang --top top_module -f rtl/filelist_top.f

set -euo pipefail

# ─── Defaults ───────────────────────────────────────────────────────────────
TOOL="verilator"
TOP=""
FILELIST=""
OUTDIR="lint/reports"
WAIVER=""
FILES=()
VERBOSE=0

# ─── Usage ──────────────────────────────────────────────────────────────────
usage() {
  cat <<'USAGE'
Usage: lint/scripts/run_lint.sh [OPTIONS] [SV_FILES...]

Options:
  --tool <name>     verilator|verible|slang|spyglass|hal (default: verilator)
  --top <module>    Top-level module name (for hierarchy-aware lint)
  -f <filelist>     Source filelist (.f file)
  --outdir <dir>    Report output directory (default: lint/reports)
  --waiver <file>   Waiver file (verilator .vlt, verible .rules)
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
SRC_FILES+=("${FILES[@]}")

if [[ ${#SRC_FILES[@]} -eq 0 ]]; then
  echo "ERROR: No source files specified. Use -f <filelist> or pass .sv files directly." >&2
  exit 1
fi

TIMESTAMP=$(date +%Y%m%d_%H%M%S)

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
    eval "$CMD" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  verible)
    CMD="verible-verilog-lint"
    [[ -n "$WAIVER" ]] && CMD="$CMD --rules_config=$WAIVER"
    CMD="$CMD ${SRC_FILES[*]}"
    REPORT="$OUTDIR/verible_lint_${TIMESTAMP}.log"
    echo "=== Verible Lint ==="
    echo "CMD: $CMD"
    eval "$CMD" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  slang)
    CMD="slang --color-diagnostics"
    [[ -n "$TOP" ]] && CMD="$CMD --top $TOP"
    CMD="$CMD ${SRC_FILES[*]}"
    REPORT="$OUTDIR/slang_lint_${TIMESTAMP}.log"
    echo "=== slang Lint ==="
    echo "CMD: $CMD"
    eval "$CMD" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  spyglass|hal)
    echo "ERROR: Commercial tool '$TOOL' requires project-specific configuration." >&2
    echo "Please create lint/scripts/${TOOL}_lint.tcl with your license and rule setup." >&2
    exit 1
    ;;

  *)
    echo "ERROR: Unknown lint tool: $TOOL" >&2
    echo "Supported: verilator, verible, slang, spyglass, hal" >&2
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
echo "Exit:     $EXIT_CODE"

exit "$EXIT_CODE"
