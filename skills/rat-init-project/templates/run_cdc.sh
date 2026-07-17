#!/usr/bin/env bash
# run_cdc.sh — CDC analysis runner for RTL modules
# Usage: lint/scripts/run_cdc.sh [OPTIONS] [SV_FILES...]
#
# Supports:
#   - structural (default): grep heuristic + svlens crosscheck (if installed)
#   - svlens: unified structural analysis via svlens cdc (https://github.com/babyworm/svlens)
#   - spyglass: Synopsys SpyGlass CDC
#   - vc_cdc: Synopsys VC CDC
#   - questa_cdc: Siemens Questa CDC
#
# Examples:
#   lint/scripts/run_cdc.sh --tool structural -f rtl/filelist_top.f --outdir lint/cdc
#   lint/scripts/run_cdc.sh --tool svlens --top my_top -f rtl/filelist_top.f
#   lint/scripts/run_cdc.sh --tool spyglass --script lint/cdc/spyglass_cdc.tcl -f rtl/filelist_top.f

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

TOOL="structural"
TOP=""
FILELIST=""
OUTDIR="lint/cdc"
SCRIPT_PATH=""
FILES=()
VERBOSE=0

usage() {
  cat <<'USAGE'
Usage: lint/scripts/run_cdc.sh [OPTIONS] [SV_FILES...]

Options:
  --tool <name>     structural|svlens|spyglass|vc_cdc|questa_cdc (default: structural)
  --top <module>    Top-level module name
  -f <filelist>     Source filelist (.f file)
  --outdir <dir>    Report output directory (default: lint/cdc)
  --script <file>   Tool script/Tcl file (commercial tools)
  -v, --verbose     Verbose output
  -h, --help        Show this help
USAGE
  exit 0
}

# ─── Shell-metacharacter validation (self-contained; template is deployed standalone) ──
# Values checked here are interpolated into a tool command line that is echoed
# into a replay script and/or a generated Tcl file. Reject anything outside a
# path/identifier-safe whitelist so a hostile filelist entry or CLI arg cannot
# inject shell or Tcl commands (mirrors the run_syn.sh v0.11.3 precedent).
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

# ─── Resolve paths to absolute (before cd) ────────────────────────────
case "$OUTDIR" in /*) ;; *) OUTDIR="$PROJECT_ROOT/$OUTDIR" ;; esac
[[ -n "$FILELIST" && "$FILELIST" != /* ]] && FILELIST="$PROJECT_ROOT/$FILELIST"
[[ -n "$SCRIPT_PATH" && "$SCRIPT_PATH" != /* ]] && SCRIPT_PATH="$PROJECT_ROOT/$SCRIPT_PATH"

# The script cds into OUTDIR and every branch's replay script embeds it as
# `cd "$RUN_CWD"` — a value with $()/backticks would execute at replay time
# even though live argv invocations are safe. Validate once, globally.
validate_shell_safe "--outdir path" "$OUTDIR"

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

# cd to CDC directory — all tool artifacts stay contained
cd "$OUTDIR"
RUN_CWD="$(pwd)"
echo "[run_cdc] Working directory: $(pwd)"

REPORT="$OUTDIR/cdc_${TOOL}_${TIMESTAMP}.log"
EXIT_CODE=0

case "$TOOL" in
  structural)
    {
      echo "=== Structural CDC Quick Check (grep heuristic) ==="
      echo "Top: ${TOP:-N/A}"
      echo "Files: ${#SRC_FILES[@]}"
      echo "Rule: detect clock/reset naming patterns and obvious async crossings."
      echo ""
      echo "Clock-like signals:"
      grep -RhoE '\b[a-zA-Z0-9_]*_clk\b|\bclk\b' "${SRC_FILES[@]}" 2>/dev/null | sort -u || true
      echo ""
      echo "Reset-like signals:"
      grep -RhoE '\b[a-zA-Z0-9_]*_rst_n\b|\brst_n\b' "${SRC_FILES[@]}" 2>/dev/null | sort -u || true
    } | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}

    # svlens crosscheck: run AST-based CDC analysis if available (incl. Docker fallback)
    if command -v svlens &>/dev/null || run_tool svlens --version &>/dev/null; then
      echo ""
      echo "=== svlens CDC Crosscheck (AST-based) ==="
      SVLENS_OUTDIR="$OUTDIR/svlens"
      mkdir -p "$SVLENS_OUTDIR"
      SVLENS_ARGS=(svlens cdc --format all -o "$SVLENS_OUTDIR")
      [[ -n "$TOP" ]] && SVLENS_ARGS+=(--top "$TOP")
      [[ -n "$FILELIST" ]] && SVLENS_ARGS+=(-f "$FILELIST")
      SVLENS_ARGS+=("${SRC_FILES[@]}")
      # The CMD echo and replay script serialize these argv values into shell
      # text — validate against shell metacharacters first (live invocation
      # via run_tool "${SVLENS_ARGS[@]}" is argv-safe on its own).
      validate_shell_safe "--top" "$TOP"
      validate_shell_safe "--outdir path" "$SVLENS_OUTDIR"
      validate_shell_safe "filelist path" "$FILELIST"
      validate_shell_safe "source file path" "${SRC_FILES[@]}"
      echo "CMD: ${SVLENS_ARGS[*]}"
      write_replay "${SVLENS_ARGS[*]}"
      if run_tool "${SVLENS_ARGS[@]}" 2>&1 | tee -a "$REPORT"; then
        echo "[svlens] Crosscheck complete (0 violations). Reports in $SVLENS_OUTDIR/"
      else
        SVLENS_EXIT=$?
        echo "[svlens] Crosscheck failed (exit $SVLENS_EXIT). Reports in $SVLENS_OUTDIR/"
        EXIT_CODE=$SVLENS_EXIT
      fi
    else
      echo ""
      echo "[INFO] svlens not installed. Install for AST-based CDC crosscheck:"
      echo "  git clone https://github.com/babyworm/svlens.git ~/tools/svlens"
      echo "  cd ~/tools/svlens && ./scripts/setup-deps.sh --prefix ~/.local"
      echo "  cmake -B build -DCMAKE_PREFIX_PATH=~/.local && cmake --build build -j\$(nproc)"
      echo "  cmake --install build --prefix ~/.local"
    fi
    ;;

  svlens)
    if ! command -v svlens &>/dev/null && ! run_tool svlens --version &>/dev/null; then
      echo "ERROR: svlens not found. Install:" >&2
      echo "  git clone https://github.com/babyworm/svlens.git ~/tools/svlens" >&2
      echo "  cd ~/tools/svlens && ./scripts/setup-deps.sh --prefix ~/.local" >&2
      echo "  cmake -B build -DCMAKE_PREFIX_PATH=~/.local && cmake --build build -j\$(nproc)" >&2
      echo "  cmake --install build --prefix ~/.local" >&2
      exit 1
    fi
    SVLENS_ARGS=(svlens cdc --format all -o "$OUTDIR")
    [[ -n "$TOP" ]] && SVLENS_ARGS+=(--top "$TOP")
    [[ -n "$FILELIST" ]] && SVLENS_ARGS+=(-f "$FILELIST")
    SVLENS_ARGS+=("${SRC_FILES[@]}")
    # The CMD echo and replay script serialize these argv values into shell
    # text — validate against shell metacharacters first (live invocation
    # via run_tool "${SVLENS_ARGS[@]}" is argv-safe on its own).
    validate_shell_safe "--top" "$TOP"
    validate_shell_safe "--outdir path" "$OUTDIR"
    validate_shell_safe "filelist path" "$FILELIST"
    validate_shell_safe "source file path" "${SRC_FILES[@]}"
    echo "=== svlens cdc (AST-based CDC analysis) ==="
    echo "CMD: ${SVLENS_ARGS[*]}"
    write_replay "${SVLENS_ARGS[*]}"
    run_tool "${SVLENS_ARGS[@]}" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  spyglass)
    # These values are interpolated into the generated SpyGlass Tcl and into
    # the replayed command line — validate against shell metacharacters first.
    validate_shell_safe "--top" "$TOP"
    validate_shell_safe "--outdir path" "$OUTDIR"
    validate_shell_safe "source file path" "${SRC_FILES[@]}"

    CDC_TCL="$SCRIPT_PATH"
    if [[ -z "$CDC_TCL" ]]; then
      CDC_TCL="${SPYGLASS_CDC_TCL:-$OUTDIR/spyglass_cdc_${TIMESTAMP}.tcl}"
    fi
    # CDC_TCL may come from --script or the SPYGLASS_CDC_TCL env var.
    validate_shell_safe "CDC Tcl path" "$CDC_TCL"

    SPYGLASS_PROJDIR="$OUTDIR/spyglass_cdc"

    if [[ ! -f "$CDC_TCL" ]]; then
      {
        echo "# Auto-generated SpyGlass CDC script (sg_shell batch mode)"
        echo "new_project spyglass_cdc -projectwdir \"$SPYGLASS_PROJDIR\" -force"
        for src in "${SRC_FILES[@]}"; do
          case "$src" in
            *.sv|*.svh) echo "read_file -type systemverilog \"$src\"" ;;
            *)          echo "read_file -type verilog \"$src\"" ;;
          esac
        done
        [[ -n "$TOP" ]] && echo "set_option top \"$TOP\""
        echo "current_goal cdc/cdc_setup_check"
        echo "run_goal"
        echo "current_goal cdc/cdc_verify_struct"
        echo "run_goal"
        echo "save_project"
        echo "close_project"
        echo "exit"
      } > "$CDC_TCL"
    fi

    # Use sg_shell for batch mode (not spyglass GUI binary).
    # Path validated shell-safe above — execute via argv (no eval); the quoted
    # string form is kept for display and the replay script.
    CMD="sg_shell -tcl \"$CDC_TCL\""
    echo "=== SpyGlass CDC (sg_shell) ==="
    echo "TCL: $CDC_TCL"
    echo "CMD: $CMD"
    write_replay "$CMD"
    run_tool sg_shell -tcl "$CDC_TCL" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  vc_cdc)
    CDC_TCL="$SCRIPT_PATH"
    if [[ -z "$CDC_TCL" ]]; then
      echo "ERROR: vc_cdc requires --script <tcl> (or set VC_CDC_TCL)." >&2
      exit 1
    fi
    # Path validated shell-safe below — execute via argv (no eval); the quoted
    # string form is kept for display and the replay script.
    validate_shell_safe "CDC Tcl path" "$CDC_TCL"
    CMD="vc_cdc -f \"$CDC_TCL\""
    echo "=== VC CDC ==="
    echo "CMD: $CMD"
    write_replay "$CMD"
    run_tool vc_cdc -f "$CDC_TCL" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  questa_cdc)
    CDC_TCL="$SCRIPT_PATH"
    if [[ -z "$CDC_TCL" ]]; then
      echo "ERROR: questa_cdc requires --script <do/tcl> (or set QUESTA_CDC_TCL)." >&2
      exit 1
    fi
    # Path validated shell-safe below — execute via argv (no eval); the quoted
    # string form is kept for display and the replay script.
    validate_shell_safe "CDC Tcl path" "$CDC_TCL"
    CMD="qverify -c -do \"$CDC_TCL\""
    echo "=== Questa CDC ==="
    echo "CMD: $CMD"
    write_replay "$CMD"
    run_tool qverify -c -do "$CDC_TCL" 2>&1 | tee "$REPORT"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  *)
    echo "ERROR: Unknown CDC tool: $TOOL" >&2
    echo "Supported: structural, svlens, spyglass, vc_cdc, questa_cdc" >&2
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
