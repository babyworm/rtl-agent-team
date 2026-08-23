#!/usr/bin/env bash
# run_conformal.sh — Cadence Conformal LEC equivalence checking
# Usage: syn/scripts/run_conformal.sh [OPTIONS]
#
# Compares RTL (golden) against gate-level netlist (revised)
# to prove functional equivalence after synthesis.
#
# Examples:
#   syn/scripts/run_conformal.sh --top top_module --rtl rtl/filelist_top.f --netlist syn/vnet/top_module.v
#   syn/scripts/run_conformal.sh --top top_module --rtl rtl/filelist_top.f --netlist syn/vnet/top_module.v --liberty tech.lib

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
# and default output dirs resolve against the project root even when invoked
# from a different CWD. Unset ⇒ cd "$(pwd)" is a no-op (behavior unchanged).
PROJECT_ROOT="${RAT_PROJECT_ROOT:-$(pwd)}"
cd "$PROJECT_ROOT"

# ─── Defaults ───────────────────────────────────────────────────────────────
TOP=""
RTL_FILELIST=""
NETLIST=""
LIBERTY=""
OUTDIR="syn/rpt"
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
  --outdir <dir>      Report output directory (default: syn/rpt)
  --script <file>     Custom Conformal dofile
  -v, --verbose       Verbose output
  -h, --help          Show this help
USAGE
  exit 0
}

# ─── Shell-metacharacter validation (self-contained; template is deployed standalone) ──
# Values checked here are interpolated into the tool command line (echoed into
# a replay script) and into the generated Conformal dofile. Reject anything
# outside a path/identifier-safe whitelist so a hostile filelist entry or CLI
# arg cannot inject shell or dofile commands (mirrors the run_syn.sh v0.11.3
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

trim_filelist_line() {
  local line="$1"
  line="${line%%//*}"
  # Filelist tokens with whitespace are outside this wrapper's safe replay/dofile
  # policy; trim only leading/trailing whitespace before explicit validation.
  line="${line#"${line%%[![:space:]]*}"}"
  line="${line%"${line##*[![:space:]]}"}"
  printf '%s\n' "$line"
}

filelist_dirname() {
  local p="$1"
  if [[ "$p" == */* ]]; then
    printf '%s\n' "${p%/*}"
  else
    printf '%s\n' "."
  fi
}

resolve_filelist_path() {
  local base="$1"
  local entry="$2"
  if [[ "$entry" == /* ]]; then
    printf '%s\n' "$entry"
  elif [[ -e "$PROJECT_ROOT/$entry" ]]; then
    # Generated filelists use project-root-relative paths such as rtl/top.sv.
    printf '%s\n' "$PROJECT_ROOT/$entry"
  else
    # Nested filelists may use entries relative to their own directory.
    printf '%s/%s\n' "$base" "$entry"
  fi
}

resolve_incdir_option() {
  local base="$1"
  local option="$2"
  local body="${option#+incdir+}"
  local item result="+incdir+" separator=""

  [[ -n "$body" ]] || { echo "ERROR: malformed +incdir+ option" >&2; exit 1; }
  while [[ "$body" == *+* ]]; do
    item="${body%%+*}"
    [[ -n "$item" ]] || { echo "ERROR: malformed +incdir+ option" >&2; exit 1; }
    result+="${separator}$(resolve_filelist_path "$base" "$item")"
    separator="+"
    body="${body#*+}"
  done
  [[ -n "$body" ]] || { echo "ERROR: malformed +incdir+ option" >&2; exit 1; }
  result+="${separator}$(resolve_filelist_path "$base" "$body")"
  printf '%s\n' "$result"
}

collect_rtl_filelist() {
  local filelist="$1"
  local base line nested resolved stack_item

  validate_shell_safe "RTL filelist path" "$filelist"
  [[ -f "$filelist" ]] || { echo "ERROR: RTL filelist not found: $filelist" >&2; exit 1; }

  if ((${#FILELIST_STACK[@]})); then
    for stack_item in "${FILELIST_STACK[@]}"; do
      [[ "$stack_item" == "$filelist" ]] && {
        echo "ERROR: recursive RTL filelist include cycle at: $filelist" >&2
        exit 1
      }
    done
  fi

  FILELIST_STACK+=("$filelist")
  base="$(filelist_dirname "$filelist")"
  while IFS= read -r line || [[ -n "$line" ]]; do
    line="$(trim_filelist_line "$line")"
    line="${line%%#*}"
    line="${line%"${line##*[![:space:]]}"}"
    [[ -z "$line" ]] && continue
    case "$line" in
      +incdir+*)
        resolved="$(resolve_incdir_option "$base" "$line")"
        validate_shell_safe "RTL filelist option" "$resolved"
        RTL_ARGS+=("$resolved")
        ;;
      +define+*)
        validate_shell_safe "RTL filelist option" "$line"
        RTL_ARGS+=("$line")
        ;;
      -f\ *)
        nested="${line#-f }"
        nested="$(resolve_filelist_path "$base" "$nested")"
        collect_rtl_filelist "$nested"
        ;;
      -f*)
        nested="${line#-f}"
        nested="$(resolve_filelist_path "$base" "$nested")"
        collect_rtl_filelist "$nested"
        ;;
      -*)
        echo "ERROR: unsupported RTL filelist option: $line" >&2
        exit 1
        ;;
      *)
        resolved="$(resolve_filelist_path "$base" "$line")"
        validate_shell_safe "RTL file path" "$resolved"
        RTL_ARGS+=("$resolved")
        RTL_FILES+=("$resolved")
        ;;
    esac
  done < "$filelist"
  unset 'FILELIST_STACK[${#FILELIST_STACK[@]}-1]'
}

conformal_log_has_failure() {
  local log="$1"
  grep -Eiq '(^|[^A-Z])(NON[- ]?EQUIVALENT|NOT[[:space:]]+EQUIVALENT|ABORTED|COMPARE[[:space:]]+FAILED|FATAL|UNKNOWN)([^A-Z]|$)|ERRORS?[[:space:]]*(COUNT)?[[:space:]:=-]+[1-9][0-9]*|ERROR:[[:space:]]*[A-Z_]' "$log"
}

conformal_log_has_success() {
  local log="$1"
  # Accepted pass markers are intentionally narrow. Real Conformal logs should
  # contain an equivalent/comparison success line; tests may emit the explicit
  # RAT_CONFORMAL_EQUIVALENT marker from a fake tool.
  grep -Eiq '(RAT_CONFORMAL_EQUIVALENT|COMPARE[[:space:]]+RESULTS:[[:space:]]*(PASS|EQUIVALENT)|COMPARE[[:space:]]+SUCCEEDED|COMPARISON[[:space:]]+SUCCEEDED|DESIGNS?[[:space:]]+ARE[[:space:]]+EQUIVALENT|EQUIVALENCE[[:space:]]+CHECK[[:space:]]+PASSED)' "$log"
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

# --- Verbose: trace the wrapper itself -------------------------------------
# Tool output already goes through `tee`; what --verbose adds is visibility
# into what this wrapper does (path resolution, file discovery, env setup).
[[ "$VERBOSE" -eq 1 ]] && set -x

[[ -z "$TOP" ]] && { echo "ERROR: --top is required" >&2; exit 1; }
[[ -z "$RTL_FILELIST" ]] && { echo "ERROR: --rtl is required" >&2; exit 1; }
[[ -z "$NETLIST" ]] && { echo "ERROR: --netlist is required" >&2; exit 1; }

# --top is emitted into the dofile (`set root module $TOP`) and into generated
# file names — require a plain Verilog module identifier.
if ! [[ "$TOP" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "ERROR: --top must be a Verilog module identifier (got: '$TOP')" >&2
  exit 1
fi
# Paths below feed the eval-free but replayed command line and the generated
# dofile — validate against shell metacharacters first.
validate_shell_safe "--rtl path" "$RTL_FILELIST"
validate_shell_safe "--netlist path" "$NETLIST"
validate_shell_safe "--liberty path" "$LIBERTY"
validate_shell_safe "--outdir path" "$OUTDIR"
validate_shell_safe "--script path" "$SCRIPT_PATH"

mkdir -p "$OUTDIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_CWD="$(pwd)"
REPLAY_DIR="$OUTDIR/replay"
mkdir -p "$REPLAY_DIR"
REPLAY_SCRIPT="$REPLAY_DIR/run_conformal_${TOP}_${TIMESTAMP}.sh"
REPORT="$OUTDIR/conformal_${TOP}_${TIMESTAMP}.log"

# ─── Collect RTL files/options ────────────────────────────────────────────
RTL_ARGS=()
RTL_FILES=()
FILELIST_STACK=()
collect_rtl_filelist "$RTL_FILELIST"

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
    printf 'read design -golden -sv'
    for f in "${RTL_ARGS[@]}"; do
      printf ' "%s"' "$f"
    done
    printf '\n'
    echo ""
    echo "// --- Revised design (netlist) ---"
    [[ -n "$LIBERTY" ]] && echo "read library -liberty \"$LIBERTY\""
    echo "read design -revised -verilog2k \"$NETLIST\""
    echo ""
    echo "set system mode lec"
    echo "set root module $TOP -golden"
    echo "set root module $TOP -revised"
    echo ""
    echo "// --- Blackbox SRAM wrappers (behavioral vs foundry macro) ---"
    echo "// Uncomment for designs using rtl/common/ SRAM wrappers:"
    echo "// add notranslate module sram_sp -golden; add notranslate module sram_sp -revised"
    echo "// add notranslate module sram_tp -golden; add notranslate module sram_tp -revised"
    echo "// add notranslate module sram_dp -golden; add notranslate module sram_dp -revised"
    echo ""
    echo "// --- Map and verify ---"
    echo "map key points"
    echo "add compared points -all"
    echo "compare"
    echo "puts \"RAT_CONFORMAL_COMPARE_COMPLETE\""
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
# Cadence spells the 64-bit switch `-64`, not Synopsys' `-64bit`; modern Conformal
# is 64-bit only, so the switch is dropped entirely. `-nogui` is mandatory for a
# batch run — without it Conformal tries to open its GUI and a headless CI hangs.
# Cadence documents the batch form as: lec -dofile <file> -nogui
CMD="lec -nogui -dofile \"$LEC_DO\""

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

# $LEC_DO components (--script / --outdir / --top) validated against shell
# metacharacters above — execute via argv, no eval.
run_tool lec -nogui -dofile "$LEC_DO" 2>&1 | tee "$REPORT"
EXIT_CODE=${PIPESTATUS[0]}

if [[ "$EXIT_CODE" -eq 0 ]]; then
  if conformal_log_has_failure "$REPORT"; then
    echo "ERROR: Conformal reported a failing/aborted/unknown compare result" >&2
    EXIT_CODE=1
  elif ! conformal_log_has_success "$REPORT"; then
    echo "ERROR: Conformal log did not contain an accepted equivalence success marker" >&2
    echo "       Accepted markers: RAT_CONFORMAL_EQUIVALENT, Compare Results: PASS/EQUIVALENT, compare/comparison succeeded, designs are equivalent, equivalence check passed" >&2
    EXIT_CODE=1
  fi
fi

# ─── Summary ─────────────────────────────────────────────────────────────
echo ""
echo "=== Conformal Summary ==="
echo "Top:      $TOP"
echo "Report:   $REPORT"
echo "Replay:   $REPLAY_SCRIPT"
echo "Exit:     $EXIT_CODE"

exit "$EXIT_CODE"

# rat-version: 0.8.14
