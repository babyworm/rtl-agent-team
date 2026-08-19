#!/usr/bin/env bash
# run_syn.sh — Synthesis runner for RTL modules
# Usage: syn/scripts/run_syn.sh [OPTIONS] [SV_FILES...]
#
# Directory structure (DC-standard, adapted for all tools):
#   syn/db/      — Binary databases (.ddc, .db)
#   syn/vnet/    — Gate-level netlists (.v)
#   syn/svf/     — Setup Verification Flow files (.svf)
#   syn/scr/     — Generated synthesis scripts (.tcl, .ys)
#   syn/rpt/     — Reports (area, timing, power, qor)
#   syn/log/     — Synthesis logs
#   syn/temp/    — Synthesis cache and temporary files
#   syn/work/    — Tool work directories (alib, elaboration)
#
# Supports: yosys (default), dc_shell/design_compiler, genus, vivado
#
# Examples:
#   syn/scripts/run_syn.sh --tool yosys --top top_module -f rtl/filelist_top.f
#   syn/scripts/run_syn.sh --tool dc_shell --top my_top -f rtl/filelist_top.f --liberty sky130.lib
#   syn/scripts/run_syn.sh --tool genus --top my_top -f rtl/filelist_top.f --liberty sky130.lib

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
TOOL="yosys"
TOP=""
FILELIST=""
SYN_ROOT="syn"
LIBERTY=""
SDC_FILE=""
SCRIPT_PATH=""
FILES=()
VERBOSE=0
FLATTEN=0
SKIP_IF_UNAVAILABLE=0
# Default multicore request. Keep in sync with dc-compile-ppa.tcl `max_cores`
# default (the PPA-loop path sets it independently of this CLI default).
MAX_CORES=8
# Memory-compiler handling (DC/Genus). Behavioral SRAM wrappers are blackboxed at
# synthesis (their `synopsys translate_off` body is skipped) unless a compiled macro
# library is linked. See plugin_docs/specs/2026-05-26-synth-memory-blackbox-design.md.
MEM_PROCESS=()      # --mem-process NAME  → +define+NAME (activates wrapper `ifdef branch)
MEM_LIB=""          # --mem-lib FILE      → link compiled-macro timing library (real timing)
MEM_MODULES=()      # --mem-module a,b    → extra memory-wrapper module names beyond sram_*
MEM_STRICT=0        # --mem-strict        → blackboxed-memory warning becomes a hard error

# ─── Usage ──────────────────────────────────────────────────────────────────
usage() {
  cat <<'USAGE'
Usage: syn/scripts/run_syn.sh [OPTIONS] [SV_FILES...]

Options:
  --tool <name>     yosys|dc_shell|design_compiler|genus|vivado (default: yosys)
  --top <module>    Top-level module name (required)
  -f <filelist>     Source filelist (.f file)
  --syn-root <dir>  Synthesis root directory (default: syn)
  --liberty <file>  Liberty (.lib) file for technology mapping
  --sdc <file>      SDC constraints file (default: syn/constraints/design.sdc)
  --max-cores <n>   Max CPU cores for multicore synthesis (default: 8).
                    DC/Genus auto-limit to the licensed/physical maximum.
  --mem-process <N> Define +N for synthesis (activates an SRAM wrapper `ifdef
                    branch, e.g. RAT_MEM_TSMC_N22). Repeatable.
  --mem-lib <file>  Compiled memory-macro timing library (.db/.lib) to link.
                    Without it, SRAM wrappers are blackboxed (timing disabled).
  --mem-module <m>  Extra memory-wrapper module name(s) beyond sram_sp/tp/dp
                    (comma-separated). Repeatable.
  --mem-strict      Treat a blackboxed memory (no compiled macro) as an error.
  --script <file>   User-provided tool script/Tcl (skips auto-generation)
  --flatten         Flatten design before synthesis
  --skip-if-unavailable  Exit cleanly (exit 0) if tool not available/licensed
  -v, --verbose     Verbose output
  -h, --help        Show this help

Output directories (under --syn-root):
  db/               Binary databases (.ddc, .db)
  vnet/             Gate-level netlists (.v)
  svf/              Setup Verification Flow (.svf)
  scr/              Generated scripts (.tcl, .ys) + replay/
  rpt/              Reports (area, timing, power, qor)
  log/              Synthesis logs
  temp/             Cache and temporary files
  work/             Tool work directories
USAGE
  exit 0
}

# ─── Parse args ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool)      TOOL="$2"; shift 2 ;;
    --top)       TOP="$2"; shift 2 ;;
    -f)          FILELIST="$2"; shift 2 ;;
    --syn-root|--outdir) SYN_ROOT="$2"; shift 2 ;;
    --liberty)   LIBERTY="$2"; shift 2 ;;
    --sdc)       SDC_FILE="$2"; shift 2 ;;
    --max-cores) MAX_CORES="$2"; shift 2 ;;
    --mem-process) if [[ -n "$2" ]]; then MEM_PROCESS+=("$2"); fi; shift 2 ;;
    --mem-lib)   MEM_LIB="$2"; shift 2 ;;
    --mem-module) IFS=',' read -ra _mm <<< "$2"
                  for _t in "${_mm[@]}"; do if [[ -n "$_t" ]]; then MEM_MODULES+=("$_t"); fi; done
                  shift 2 ;;
    --mem-strict) MEM_STRICT=1; shift ;;
    --script)    SCRIPT_PATH="$2"; shift 2 ;;
    --flatten)   FLATTEN=1; shift ;;
    --skip-if-unavailable) SKIP_IF_UNAVAILABLE=1; shift ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help)   usage ;;
    -*)          echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
    *)           FILES+=("$1"); shift ;;
  esac
done

# --- Verbose: trace the wrapper itself -------------------------------------
# Tool output already goes through `tee`; what --verbose adds is visibility
# into what this wrapper does (path resolution, file discovery, env setup).
[[ "$VERBOSE" -eq 1 ]] && set -x

if [[ "$TOOL" == "design_compiler" ]]; then
  TOOL="dc_shell"
fi

if [[ -z "$TOP" ]]; then
  echo "ERROR: --top <module> is required" >&2
  exit 1
fi
# --top is emitted into Tcl (e.g. `elaborate $TOP`); require a plain module identifier.
if ! [[ "$TOP" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
  echo "ERROR: --top must be a Verilog module identifier (got: '$TOP')" >&2
  exit 1
fi

# --max-cores must be a positive integer (it is emitted verbatim into the Tcl)
if ! [[ "$MAX_CORES" =~ ^[1-9][0-9]*$ ]]; then
  echo "ERROR: --max-cores must be a positive integer (got: '$MAX_CORES')" >&2
  exit 1
fi

# --mem-process / --mem-module tokens must be plain identifiers. A blank or glob-bearing
# token would otherwise become `ref_name =~ *` in the Tcl filter and blackbox the WHOLE design.
if [[ ${#MEM_PROCESS[@]} -gt 0 ]]; then
  for _t in "${MEM_PROCESS[@]}"; do
    if ! [[ "$_t" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      echo "ERROR: --mem-process must be a Verilog identifier (got: '$_t')" >&2; exit 1
    fi
  done
fi
if [[ ${#MEM_MODULES[@]} -gt 0 ]]; then
  for _t in "${MEM_MODULES[@]}"; do
    if ! [[ "$_t" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
      echo "ERROR: --mem-module must be module identifier(s) (got: '$_t')" >&2; exit 1
    fi
  done
fi

# Default SDC path (always project-relative, not SYN_ROOT-relative)
if [[ -z "$SDC_FILE" ]]; then
  SDC_FILE="syn/constraints/design.sdc"
fi

# ─── Resolve paths to absolute (before cd to synthesis root) ──────────
case "$SYN_ROOT" in /*) ;; *) SYN_ROOT="$PROJECT_ROOT/$SYN_ROOT" ;; esac
[[ -n "$LIBERTY" && "$LIBERTY" != /* ]] && LIBERTY="$PROJECT_ROOT/$LIBERTY"
[[ -n "$SDC_FILE" && "$SDC_FILE" != /* ]] && SDC_FILE="$PROJECT_ROOT/$SDC_FILE"
[[ -n "$SCRIPT_PATH" && "$SCRIPT_PATH" != /* ]] && SCRIPT_PATH="$PROJECT_ROOT/$SCRIPT_PATH"
[[ -n "$FILELIST" && "$FILELIST" != /* ]] && FILELIST="$PROJECT_ROOT/$FILELIST"
# Memory macro library: absolutize only if it resolves to a real file (else it may be a
# logical library name the tool resolves via search_path).
[[ -n "$MEM_LIB" && "$MEM_LIB" != /* && -e "$PROJECT_ROOT/$MEM_LIB" ]] && MEM_LIB="$PROJECT_ROOT/$MEM_LIB"

# ─── Directory setup ──────────────────────────────────────────────────────
DIR_DB="${SYN_ROOT}/db"
DIR_VNET="${SYN_ROOT}/vnet"
DIR_SVF="${SYN_ROOT}/svf"
DIR_SCR="${SYN_ROOT}/scr"
DIR_RPT="${SYN_ROOT}/rpt"
DIR_LOG="${SYN_ROOT}/log"
DIR_TEMP="${SYN_ROOT}/temp"
DIR_WORK="${SYN_ROOT}/work"
DIR_REPLAY="${DIR_SCR}/replay"

mkdir -p "$DIR_DB" "$DIR_VNET" "$DIR_SVF" "$DIR_SCR" "$DIR_RPT" \
         "$DIR_LOG" "$DIR_TEMP" "$DIR_WORK" "$DIR_REPLAY"

# ─── Tool availability & license pre-check ─────────────────────────────────
_tool_bin=""
case "$TOOL" in
  yosys)    _tool_bin="yosys" ;;
  dc_shell) _tool_bin="dc_shell" ;;
  genus)    _tool_bin="genus" ;;
  *)        _tool_bin="$TOOL" ;;
esac

if ! command -v "$_tool_bin" >/dev/null 2>&1; then
  if [[ "$SKIP_IF_UNAVAILABLE" -eq 1 ]]; then
    echo "WARNING: Synthesis tool '$TOOL' not available — skipping synthesis." >&2
    echo '{"tool":"'"$TOOL"'","status":"SKIPPED","reason":"tool_not_available"}' > "${DIR_RPT}/syn_result.json" 2>/dev/null || true
    exit 0
  fi
  echo "ERROR: Synthesis tool '$_tool_bin' not found in PATH." >&2
  exit 127
fi

# License check for commercial tools
if type check_tool_licensed >/dev/null 2>&1; then
  case "$TOOL" in
    dc_shell|genus)
      if ! check_tool_licensed "$TOOL"; then
        if [[ "$SKIP_IF_UNAVAILABLE" -eq 1 ]]; then
          echo "WARNING: '$TOOL' license not available — skipping synthesis." >&2
          echo '{"tool":"'"$TOOL"'","status":"SKIPPED","reason":"license_unavailable"}' > "${DIR_RPT}/syn_result.json" 2>/dev/null || true
          exit 0
        fi
        echo "ERROR: '$TOOL' license check failed." >&2
        exit 1
      fi ;;
  esac
fi

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

# DC/Genus emit EVERY source/library/work path into Tcl double quotes (`analyze ... "$f"`,
# `read_hdl ... "$f"`, target/link library, SDC, --mem-lib). A path containing Tcl-active
# characters ([ ] { } $ ; " ` \) would break or inject into the generated script. Validate ALL
# finalized paths once, before Tcl generation, and fail with a clear message (not a cryptic Tcl
# error). Relative args that become unsafe via $PROJECT_ROOT are caught here too.
# --script (SCRIPT_PATH) is included: it becomes the dc_shell/genus -f argument, which is
# echoed into the replay script inside double quotes — the same character set ($ ` \ ") is
# shell-active there, so this single check covers both the Tcl and the replay surfaces.
# Applies to ALL tools (not just dc_shell/genus): the yosys branch embeds
# SYN_ROOT-derived paths into its generated script and into the replay shell
# script (`yosys -s "$SCRIPT"`), where the same character set is shell-active.
_tcl_paths="${PROJECT_ROOT}|${SYN_ROOT}|${LIBERTY}|${SDC_FILE}|${MEM_LIB}|${SCRIPT_PATH}"
for _p in "${SRC_FILES[@]}"; do _tcl_paths="${_tcl_paths}|${_p}"; done
if [[ -d "$PROJECT_ROOT/rtl/common" ]]; then
  for _p in "$PROJECT_ROOT"/rtl/common/*.sv "$PROJECT_ROOT"/rtl/common/*.v; do
    [[ -e "$_p" ]] && _tcl_paths="${_tcl_paths}|${_p}"
  done
fi
case "$_tcl_paths" in
  *'['* | *']'* | *'{'* | *'}'* | *'$'* | *';'* | *'"'* | *'`'* | *'\'* | *$'\n'* | *$'\r'* )
    echo "ERROR: a synthesis path (project/synth root, source file, rtl/common, --liberty," >&2
    echo "       --sdc, --script, or --mem-lib) contains Tcl-unsafe characters ([ ] { } \$ ; \" \` \\)." >&2
    echo "       DC/Genus emit paths into Tcl and Yosys embeds them into its script and" >&2
    echo "       replay shell — rename/move so paths avoid these characters." >&2
    exit 1 ;;
esac

# ─── Relative $readmemh/$readmemb ROM guard ─────────────────────────────────
# Source/SDC/filelist paths are absolutized above, but $readmemh("rel/path.mem")
# strings INSIDE the RTL are not — the tool resolves them against CWD, and we cd
# into $SYN_ROOT below. A relative ROM path then silently loads NOTHING (empty
# ROM, wrong synthesis, no error). Warn loudly so it is caught here, not in silicon.
# A bare "..." starting with '/' is absolute (fine); a `define-built or {..}-concat
# path is parameterizable (fine) and won't match this literal-relative pattern.
_relmem=$(grep -hoE '\$readmem[hb][[:space:]]*\([[:space:]]*"[^"/][^"]*"' "${SRC_FILES[@]}" 2>/dev/null | sort -u || true)
if [[ -n "$_relmem" ]]; then
  echo "WARNING: RTL uses RELATIVE \$readmemh/\$readmemb ROM paths. Synthesis runs from" >&2
  echo "         '$SYN_ROOT' (cd below), so these may load EMPTY (silent wrong synthesis)." >&2
  echo "         Fix: use absolute paths, parameterize the dir (+define+MEM_DIR=...), or" >&2
  echo "         ensure the .mem files resolve relative to \$SYN_ROOT. Offending loads:" >&2
  echo "$_relmem" | sed 's/^/           /' >&2
fi

# ─── Memory-wrapper blackbox setup (DC/Genus) ───────────────────────────────
# Behavioral SRAM wrappers (sram_sp/tp/dp + --mem-module) are blackboxed at synthesis
# unless a compiled macro library is linked (--mem-lib). The blackbox (set_dont_touch +
# set_disable_timing), the WARNING, and the --mem-strict check are emitted into the
# generated Tcl, gated on `get_cells` finding ACTUAL memory cells in the ELABORATED
# design. This is instantiation-aware: a declared-but-unused wrapper (or one defined in
# rtl/common and not instantiated by this top) is handled correctly and never false-fails.
# The behavioral 2-D array is kept under `synopsys translate_off`, so synthesis never
# elaborates it into flip-flops.
MEM_WRAP_NAMES=(sram_sp sram_tp sram_dp)
[[ ${#MEM_MODULES[@]} -gt 0 ]] && MEM_WRAP_NAMES+=("${MEM_MODULES[@]}")
# Real (non-blackboxed) memory needs BOTH: --mem-process to activate the wrapper's `ifdef
# macro branch AND --mem-lib to resolve the macro's timing. With only one (or neither), the
# wrapper resolves to its empty `synopsys translate_off behavioral `else (or an unresolved
# macro) — both are blackboxed. (--mem-lib alone does NOT instantiate the macro.)
MEM_BLACKBOX=1
[[ -n "$MEM_LIB" && ${#MEM_PROCESS[@]} -gt 0 ]] && MEM_BLACKBOX=0
# Tcl get_cells filter (ref_name glob per recognized wrapper module)
MEM_CELL_FILTER=""
for _name in "${MEM_WRAP_NAMES[@]}"; do
  [[ -n "$MEM_CELL_FILTER" ]] && MEM_CELL_FILTER+=" || "
  MEM_CELL_FILTER+="ref_name =~ ${_name}*"
done

# Verilog +define+ clause for the selected memory process(es), shared by DC/Genus
MEM_DEFINE_TOKENS=""
[[ ${#MEM_PROCESS[@]} -gt 0 ]] && MEM_DEFINE_TOKENS="${MEM_PROCESS[*]}"

# ─── cd to synthesis root — all tool artifacts stay contained ─────────
cd "$SYN_ROOT"
echo "[run_syn] Working directory: $(pwd)"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RUN_CWD="$(pwd)"

write_replay() {
  local cmd="$1"
  local replay_file="${DIR_REPLAY}/run_syn_${TOOL}_${TOP}_${TIMESTAMP}.sh"
  cat > "$replay_file" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$RUN_CWD"
$cmd
EOF
  chmod +x "$replay_file"
  cp "$replay_file" "${DIR_REPLAY}/run_syn_${TOOL}_latest.sh"
}

# ─── Tool-specific synthesis ───────────────────────────────────────────────
EXIT_CODE=0

case "$TOOL" in
  # =========================================================================
  # Yosys (open-source)
  # =========================================================================
  yosys)
    SCRIPT="${DIR_SCR}/synth_${TOP}_${TIMESTAMP}.ys"
    LOG="${DIR_LOG}/yosys_${TOP}_${TIMESTAMP}.log"
    NETLIST_JSON="${DIR_DB}/${TOP}.json"
    NETLIST_V="${DIR_VNET}/${TOP}.v"

    # sv2v conversion (SystemVerilog → Verilog for Yosys compatibility)
    SV2V_OUT="${DIR_TEMP}/${TOP}_sv2v.v"
    USE_SV2V=0
    if command -v sv2v >/dev/null 2>&1; then
      COMMON_FILES=()
      if [[ -d "$PROJECT_ROOT/rtl/common" ]]; then
        while IFS= read -r cf; do
          COMMON_FILES+=("$cf")
        done < <(find "$PROJECT_ROOT/rtl/common" -name '*.sv' -o -name '*.v' 2>/dev/null | sort)
      fi
      echo "=== sv2v Conversion ==="
      sv2v "${COMMON_FILES[@]}" "${SRC_FILES[@]}" -o "$SV2V_OUT"
      echo "Converted: $SV2V_OUT (${#SRC_FILES[@]} source + ${#COMMON_FILES[@]} common files)"
      USE_SV2V=1
    else
      echo "WARNING: sv2v not found — using read_verilog -sv (limited SV support in Yosys)"
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
        if [[ -d "$PROJECT_ROOT/rtl/common" ]]; then
          for f in "$PROJECT_ROOT"/rtl/common/*.sv "$PROJECT_ROOT"/rtl/common/*.v; do
            [[ -f "$f" ]] && echo "read_verilog -sv $f"
          done
        fi
      fi
      echo ""
      echo "hierarchy -check -top $TOP"
      echo "proc; opt; fsm; opt"
      [[ $FLATTEN -eq 1 ]] && echo "flatten"
      echo ""
      echo "# Memory handling"
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
        echo "# Generic synthesis (no technology mapping)"
        echo "techmap; opt"
        echo "stat -top $TOP"
      fi
      echo ""
      echo "# Post-synthesis checks"
      echo "scc -max_depth 10"
      echo "write_json $NETLIST_JSON"
      echo "write_verilog $NETLIST_V"
    } > "$SCRIPT"

    echo "=== Yosys Synthesis ==="
    echo "Script: $SCRIPT"
    echo "CMD: yosys -s $SCRIPT"
    write_replay "yosys -s \"$SCRIPT\""
    run_tool yosys -s "$SCRIPT" 2>&1 | tee "$LOG"
    EXIT_CODE=${PIPESTATUS[0]}

    # Extract stats to report
    if [[ -f "$LOG" ]]; then
      {
        echo "# Yosys Synthesis Report: $TOP"
        echo "# Date: $(date)"
        echo "# Liberty: ${LIBERTY:-none}"
        echo ""
        # Extract stats — try multiple markers for Yosys version compatibility
        grep -A 30 "Number of cells:\|Number of wires:\|=== $TOP ===\|Printing statistics" "$LOG" 2>/dev/null || true
      } > "${DIR_RPT}/${TOP}_stat.rpt"
    fi
    ;;

  # =========================================================================
  # Synopsys Design Compiler
  # =========================================================================
  dc_shell)
    LOG="${DIR_LOG}/dc_${TOP}_${TIMESTAMP}.log"
    SCRIPT="${SCRIPT_PATH:-${DIR_SCR}/dc_syn_${TOP}_${TIMESTAMP}.tcl}"

    NETLIST="${DIR_VNET}/${TOP}.v"
    DDC="${DIR_DB}/${TOP}.ddc"
    SVF="${DIR_SVF}/${TOP}.svf"
    AREA_RPT="${DIR_RPT}/${TOP}_area.rpt"
    TIMING_RPT="${DIR_RPT}/${TOP}_timing.rpt"
    POWER_RPT="${DIR_RPT}/${TOP}_power.rpt"
    QOR_RPT="${DIR_RPT}/${TOP}_qor.rpt"
    DC_WORK="${DIR_WORK}/dc"
    DC_TEMP="${DIR_TEMP}/dc"

    mkdir -p "$DC_WORK" "$DC_TEMP"

    # Generate .synopsys_dc.setup
    DC_SETUP="${DIR_SCR}/.synopsys_dc.setup"
    {
      echo "# Auto-generated .synopsys_dc.setup"
      echo "# Generated: $(date)"
      echo ""
      echo "set_app_var search_path [list . ${DIR_DB} ${DIR_WORK}/dc]"
      echo "set_app_var sh_command_log_file \"${DIR_LOG}/command.log\""
      if [[ -n "$LIBERTY" ]]; then
        echo "set_app_var target_library [list \"$LIBERTY\"]"
      fi
      # link_library: wildcard + target liberty + optional compiled memory macro lib
      if [[ -n "$LIBERTY" || -n "$MEM_LIB" ]]; then
        _ll="\"*\""
        [[ -n "$LIBERTY" ]] && _ll="$_ll \"$LIBERTY\""
        [[ -n "$MEM_LIB" ]] && _ll="$_ll \"$MEM_LIB\""
        echo "set_app_var link_library [list $_ll]"
      fi
      echo ""
      echo "# Work directories"
      echo "define_design_lib WORK -path \"${DC_WORK}\""
      echo "set_app_var alib_library_analysis_path \"${DC_TEMP}\""
      echo ""
      echo "# SVF for Formality verification"
      echo "set_svf \"${SVF}\""
    } > "$DC_SETUP"

    if [[ ! -f "$SCRIPT" || -z "$SCRIPT_PATH" ]]; then
      {
        echo "# Design Compiler synthesis script for $TOP"
        echo "# Generated: $(date)"
        echo ""
        echo "# --- Setup (sourced from .synopsys_dc.setup or inline) ---"
        echo "source \"${DC_SETUP}\""
        echo ""
        echo "# --- Host options (multicore) ---"
        echo "# Requests ${MAX_CORES} cores; DC auto-limits to the licensed/physical"
        echo "# maximum (graceful degradation — no error if fewer are available)."
        echo "set_host_options -max_cores ${MAX_CORES}"
        echo ""
        echo "# --- Read RTL ---"
        _dcdef=""
        [[ -n "$MEM_DEFINE_TOKENS" ]] && _dcdef=" -define {$MEM_DEFINE_TOKENS}"
        if [[ -d "$PROJECT_ROOT/rtl/common" ]]; then
          for f in "$PROJECT_ROOT"/rtl/common/*.sv "$PROJECT_ROOT"/rtl/common/*.v; do
            [[ -f "$f" ]] && echo "analyze -format sverilog${_dcdef} \"$f\""
          done
        fi
        for f in "${SRC_FILES[@]}"; do
          echo "analyze -format sverilog${_dcdef} \"$f\""
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
        echo "# --- Memory wrapper handling ---"
        if [[ $MEM_BLACKBOX -eq 0 ]]; then
          echo "# Compiled memory macro active (--mem-process + --mem-lib) — real timing/area used."
        else
          echo "# No active compiled macro: blackbox any INSTANTIATED memory wrapper cells + disable timing."
          echo "# (The wrapper's \`synopsys translate_off behavioral array is skipped by synthesis.)"
          echo "set _mem_cells [get_cells -quiet -hierarchical -filter {$MEM_CELL_FILTER}]"
          echo "if {[sizeof_collection \$_mem_cells] > 0} {"
          echo "  set_dont_touch \$_mem_cells true"
          echo "  set_disable_timing \$_mem_cells"
          echo "  puts \"WARNING: [sizeof_collection \$_mem_cells] memory wrapper cell(s) blackboxed — no compiled macro (timing disabled). Provide --mem-process + --mem-lib for real timing/area.\""
          if [[ $MEM_STRICT -eq 1 ]]; then
            echo "  puts \"ERROR: --mem-strict: memory blackboxed without a compiled macro.\""
            echo "  exit 1"
          fi
          echo "} else {"
          echo "  puts \"INFO: no memory wrapper cells instantiated — nothing to blackbox.\""
          echo "}"
        fi
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
        echo "# --- Save outputs ---"
        echo "change_names -rules verilog -hierarchy"
        echo "write -hierarchy -format ddc -output \"$DDC\""
        echo "write -hierarchy -format verilog -output \"$NETLIST\""
        echo ""
        echo "quit"
      } > "$SCRIPT"
    fi

    CMD="dc_shell -64bit -f \"$SCRIPT\""
    echo "=== Design Compiler Synthesis ==="
    echo "Script: $SCRIPT"
    echo "Setup:  $DC_SETUP"
    echo "CMD: $CMD"
    write_replay "$CMD"
    # $SCRIPT components (--script or SYN_ROOT-derived) validated against
    # Tcl/shell-unsafe characters above — execute via argv, no eval.
    run_tool dc_shell -64bit -f "$SCRIPT" 2>&1 | tee "$LOG"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  # =========================================================================
  # Cadence Genus
  # =========================================================================
  genus)
    LOG="${DIR_LOG}/genus_${TOP}_${TIMESTAMP}.log"
    SCRIPT="${SCRIPT_PATH:-${DIR_SCR}/genus_syn_${TOP}_${TIMESTAMP}.tcl}"

    NETLIST="${DIR_VNET}/${TOP}.v"
    AREA_RPT="${DIR_RPT}/${TOP}_area.rpt"
    TIMING_RPT="${DIR_RPT}/${TOP}_timing.rpt"
    POWER_RPT="${DIR_RPT}/${TOP}_power.rpt"
    QOR_RPT="${DIR_RPT}/${TOP}_qor.rpt"
    GENUS_WORK="${DIR_WORK}/genus"
    GENUS_TEMP="${DIR_TEMP}/genus"

    mkdir -p "$GENUS_WORK" "$GENUS_TEMP"

    if [[ ! -f "$SCRIPT" || -z "$SCRIPT_PATH" ]]; then
      {
        echo "# Cadence Genus synthesis script for $TOP"
        echo "# Generated: $(date)"
        echo ""
        if [[ -n "$LIBERTY" || -n "$MEM_LIB" ]]; then
          echo "set_db init_lib_search_path ."
          _gl=""
          [[ -n "$LIBERTY" ]] && _gl="$_gl \"$LIBERTY\""
          [[ -n "$MEM_LIB" ]] && _gl="$_gl \"$MEM_LIB\""
          echo "set_db library [list $_gl]"
        fi
        echo ""
        echo "# Work directory"
        echo "set_db hdl_work_directory \"${GENUS_WORK}\""
        echo "set_db log_directory \"${DIR_LOG}\""
        echo "set_db temp_directory \"${GENUS_TEMP}\""
        echo ""
        echo "# --- Host options (multicore) ---"
        echo "# Requests ${MAX_CORES} cores; Genus auto-limits to the licensed/physical"
        echo "# maximum (graceful degradation — no error if fewer are available)."
        echo "set_db max_cpus_per_server ${MAX_CORES}"
        echo ""
        echo "# --- Read RTL ---"
        _gndef=""
        [[ -n "$MEM_DEFINE_TOKENS" ]] && _gndef=" -define {$MEM_DEFINE_TOKENS}"
        if [[ -d "$PROJECT_ROOT/rtl/common" ]]; then
          for f in "$PROJECT_ROOT"/rtl/common/*.sv "$PROJECT_ROOT"/rtl/common/*.v; do
            [[ -f "$f" ]] && echo "read_hdl -sv${_gndef} \"$f\""
          done
        fi
        for f in "${SRC_FILES[@]}"; do
          echo "read_hdl -sv${_gndef} \"$f\""
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
        echo "# --- Memory wrapper handling ---"
        if [[ $MEM_BLACKBOX -eq 0 ]]; then
          echo "# Compiled memory macro active (--mem-process + --mem-lib) — real timing/area used."
        else
          echo "# No active compiled macro: blackbox any INSTANTIATED memory wrapper cells + disable timing."
          echo "# (The wrapper's \`synopsys translate_off behavioral array is skipped by synthesis.)"
          echo "if {[catch {set _mem_cells [get_cells -hierarchical -filter {$MEM_CELL_FILTER}]} _err]} {"
          echo "  puts \"WARNING: memory cell selection failed (\$_err) — adjust for your Genus version.\""
          echo "  set _mem_cells \"\""
          echo "}"
          echo "if {[sizeof_collection \$_mem_cells] > 0} {"
          echo "  set_dont_touch \$_mem_cells true"
          echo "  set_disable_timing \$_mem_cells"
          echo "  puts \"WARNING: [sizeof_collection \$_mem_cells] memory wrapper cell(s) blackboxed — no compiled macro (timing disabled). Provide --mem-process + --mem-lib.\""
          if [[ $MEM_STRICT -eq 1 ]]; then
            echo "  puts \"ERROR: --mem-strict: memory blackboxed without a compiled macro.\""
            echo "  exit 1"
          fi
          echo "}"
        fi
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
        echo "# --- Save outputs ---"
        echo "write_hdl -mapped > \"$NETLIST\""
        echo "write_db -to_file \"${DIR_DB}/${TOP}.genus_db\""
        echo ""
        echo "exit"
      } > "$SCRIPT"
    fi

    # Cadence documents the batch form as `genus -batch -files <tcl>`. Without
    # `-batch` Genus keeps its interactive shell alive after sourcing the script.
    # `-64` is an RTL-Compiler-era switch: Genus has always been 64-bit only, so
    # it is a no-op at best and rejected as unknown on newer releases.
    CMD="genus -batch -files \"$SCRIPT\""
    echo "=== Cadence Genus Synthesis ==="
    echo "Script: $SCRIPT"
    echo "CMD: $CMD"
    write_replay "$CMD"
    # $SCRIPT components (--script or SYN_ROOT-derived) validated against
    # Tcl/shell-unsafe characters above — execute via argv, no eval.
    run_tool genus -batch -files "$SCRIPT" 2>&1 | tee "$LOG"
    EXIT_CODE=${PIPESTATUS[0]}
    ;;

  # =========================================================================
  # Vivado (requires user-provided script)
  # =========================================================================
  vivado)
    # Vivado has no generic non-project synthesis recipe — part number, XDC and
    # IP handling are project-specific — so the Tcl must come from the user.
    # With one supplied, run it: AMD documents the batch form as
    # `vivado -mode batch -source <tcl>`, which exits after the script finishes.
    # -nojournal/-nolog keep vivado.jou/vivado.log out of the working directory so
    # parallel runs do not collide; this script's own log is captured via tee.
    if [[ -z "$SCRIPT_PATH" ]]; then
      echo "ERROR: Vivado requires project-specific configuration." >&2
      echo "Provide --script <tcl> containing your synth_design flow." >&2
      echo "  example: synth_design -top \$TOP -part <part>; report_utilization ..." >&2
      exit 1
    fi
    SCRIPT="$SCRIPT_PATH"
    LOG="${DIR_LOG}/vivado_syn_${TOP}_${TIMESTAMP}.log"
    CMD="vivado -mode batch -source \"$SCRIPT\" -nojournal -nolog"
    echo "=== Vivado Synthesis ==="
    echo "Script: $SCRIPT"
    echo "CMD: $CMD"
    write_replay "$CMD"
    # $SCRIPT is --script, validated against Tcl/shell-unsafe characters above —
    # execute via argv, no eval.
    run_tool vivado -mode batch -source "$SCRIPT" -nojournal -nolog 2>&1 | tee "$LOG"
    EXIT_CODE=${PIPESTATUS[0]}
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
echo "Liberty:  ${LIBERTY:-none}"
echo "SDC:      ${SDC_FILE}"
echo ""
echo "Outputs:"
echo "  Log:      ${DIR_LOG}/"
echo "  Netlist:  ${DIR_VNET}/"
[[ "$TOOL" == "dc_shell" ]] && echo "  DDC:      ${DIR_DB}/"
[[ "$TOOL" == "dc_shell" ]] && echo "  SVF:      ${DIR_SVF}/"
[[ "$TOOL" == "genus" ]]    && echo "  DB:       ${DIR_DB}/"
echo "  Reports:  ${DIR_RPT}/"
echo "  Scripts:  ${DIR_SCR}/"
echo "  Replay:   ${DIR_REPLAY}/run_syn_${TOOL}_latest.sh"
echo ""
echo "Exit:     $EXIT_CODE"
exit "$EXIT_CODE"

# rat-version: 0.11.3
