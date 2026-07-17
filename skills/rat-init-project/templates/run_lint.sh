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

# RAT_PROJECT_ROOT (optional env) overrides the working root so relative paths
# resolve against the project root even when invoked from a different CWD.
PROJECT_ROOT="${RAT_PROJECT_ROOT:-$(pwd)}"

# ─── Defaults ───────────────────────────────────────────────────────────────
TOOL="verilator"
TOP=""
FILELIST=""
OUTDIR="lint/lint"
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
  --outdir <dir>    Report output directory (default: lint/lint)
  --waiver <file>   Waiver file (verilator .vlt, verible .rules)
  --script <file>   Tool script/Tcl file (spyglass)
  -v, --verbose     Verbose output
  -h, --help        Show this help
USAGE
  exit 0
}

# ─── Shell-metacharacter validation (self-contained; template is deployed standalone) ──
# Values checked here are interpolated into a tool command line that is echoed
# into a replay script and/or a generated SpyGlass Tcl file. Reject anything
# outside a path/identifier-safe whitelist so a hostile filelist entry or CLI
# arg cannot inject shell or Tcl commands (mirrors the run_syn.sh v0.11.3
# Tcl-injection hardening precedent).
validate_shell_safe() {
  local label="$1"; shift
  local v
  for v in "$@"; do
    [ -z "$v" ] && continue
    if ! [[ "$v" =~ ^[A-Za-z0-9_./+=@:,-]+$ ]]; then
      echo "ERROR: $label contains shell-unsafe characters: '$v'" >&2
      echo "       Allowed: letters, digits, and _ . / + = @ : , -  — rename/move and retry." >&2
      exit 1
    fi
  done
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

# ─── Resolve paths to absolute (before cd) ────────────────────────────
case "$OUTDIR" in /*) ;; *) OUTDIR="$PROJECT_ROOT/$OUTDIR" ;; esac
[[ -n "$FILELIST" && "$FILELIST" != /* ]] && FILELIST="$PROJECT_ROOT/$FILELIST"
[[ -n "$WAIVER" && "$WAIVER" != /* ]] && WAIVER="$PROJECT_ROOT/$WAIVER"
[[ -n "$SCRIPT_PATH" && "$SCRIPT_PATH" != /* ]] && SCRIPT_PATH="$PROJECT_ROOT/$SCRIPT_PATH"

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

# Resolve source files to absolute paths (before cd)
_abs_src=()
for f in "${SRC_FILES[@]}"; do
  case "$f" in /*) _abs_src+=("$f") ;; *) _abs_src+=("$PROJECT_ROOT/$f") ;; esac
done
SRC_FILES=("${_abs_src[@]}")

# All values below feed the tool command line, the generated replay script,
# and/or the generated SpyGlass Tcl — validate against shell metacharacters
# before any of them is interpolated.
validate_shell_safe "--top" "$TOP"
validate_shell_safe "--waiver path" "$WAIVER"
validate_shell_safe "--outdir path" "$OUTDIR"
validate_shell_safe "--script path" "$SCRIPT_PATH"
validate_shell_safe "source file path" "${SRC_FILES[@]}"

# cd to lint directory — all tool artifacts stay contained
cd "$OUTDIR"
echo "[run_lint] Working directory: $(pwd)"

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
    # Command built as an argv array; every element validated against shell
    # metacharacters above — direct invocation, no eval.
    CMD=(verilator --lint-only -Wall -Wpedantic -sv)
    [[ -n "$TOP" ]] && CMD+=(--top-module "$TOP")
    [[ -n "$WAIVER" ]] && CMD+=("$WAIVER")
    CMD+=("${SRC_FILES[@]}")
    REPORT="$OUTDIR/verilator_lint_${TIMESTAMP}.log"
    echo "=== Verilator Lint ==="
    echo "CMD: ${CMD[*]}"
    write_replay "${CMD[*]}"
    run_tool "${CMD[@]}" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  verible)
    # Argv array; elements validated against shell metacharacters above — no eval.
    CMD=(verible-verilog-lint)
    [[ -n "$WAIVER" ]] && CMD+=("--rules_config=$WAIVER")
    CMD+=("${SRC_FILES[@]}")
    REPORT="$OUTDIR/verible_lint_${TIMESTAMP}.log"
    echo "=== Verible Lint ==="
    echo "CMD: ${CMD[*]}"
    write_replay "${CMD[*]}"
    run_tool "${CMD[@]}" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  slang)
    # Argv array; elements validated against shell metacharacters above — no eval.
    CMD=(slang --color-diagnostics)
    [[ -n "$TOP" ]] && CMD+=(--top "$TOP")

    # Strict mode for RTL: -Weverything catches multi-driver violations
    # (e.g., always_ff + initial on same signal — VCS ICPD error)
    # TB code: --allow-dup-initial-drivers relaxes this for testbenches
    IS_RTL=0
    for f in "${SRC_FILES[@]}"; do
      case "$f" in
        rtl/*|*/rtl/*) IS_RTL=1; break ;;
      esac
    done
    if [[ "$IS_RTL" -eq 1 ]]; then
      CMD+=(-Weverything)
    else
      CMD+=(--allow-dup-initial-drivers)
    fi

    CMD+=("${SRC_FILES[@]}")
    REPORT="$OUTDIR/slang_lint_${TIMESTAMP}.log"
    echo "=== slang Lint ==="
    [[ "$IS_RTL" -eq 1 ]] && echo "Mode: RTL strict (-Weverything)" || echo "Mode: TB (--allow-dup-initial-drivers)"
    echo "CMD: ${CMD[*]}"
    write_replay "${CMD[*]}"
    run_tool "${CMD[@]}" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  spyglass)
    REPORT="$OUTDIR/spyglass_lint_${TIMESTAMP}.log"
    SPYGLASS_TCL="$SCRIPT_PATH"
    if [[ -z "$SPYGLASS_TCL" ]]; then
      SPYGLASS_TCL="${SPYGLASS_LINT_TCL:-$OUTDIR/spyglass_lint_${TIMESTAMP}.tcl}"
    fi

    SPYGLASS_PROJDIR="$OUTDIR/spyglass_lint"

    if [[ ! -f "$SPYGLASS_TCL" ]]; then
      {
        echo "# Auto-generated SpyGlass lint script (sg_shell batch mode)"
        echo "new_project spyglass_lint -projectwdir \"$SPYGLASS_PROJDIR\" -force"
        for src in "${SRC_FILES[@]}"; do
          case "$src" in
            *.sv|*.svh) echo "read_file -type systemverilog \"$src\"" ;;
            *)          echo "read_file -type verilog \"$src\"" ;;
          esac
        done
        [[ -n "$TOP" ]] && echo "set_option top \"$TOP\""
        echo "current_goal lint/lint_rtl"
        echo "run_goal"
        echo "save_project"
        echo "close_project"
        echo "exit"
      } > "$SPYGLASS_TCL"
    fi

    # SPYGLASS_TCL may also come from the SPYGLASS_LINT_TCL env var — validate
    # the final value before it is interpolated into the replayed command.
    validate_shell_safe "SpyGlass Tcl path" "$SPYGLASS_TCL"

    # Use sg_shell for batch mode (not spyglass GUI binary).
    # Path validated shell-safe above — execute via argv (no eval); the quoted
    # string form is kept for display and the replay script.
    CMD_STR="sg_shell -tcl \"$SPYGLASS_TCL\""
    echo "=== SpyGlass Lint (sg_shell) ==="
    echo "TCL: $SPYGLASS_TCL"
    echo "CMD: $CMD_STR"
    write_replay "$CMD_STR"
    run_tool sg_shell -tcl "$SPYGLASS_TCL" 2>&1 | tee "$REPORT"
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
