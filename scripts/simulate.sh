#!/usr/bin/env bash
# simulate.sh — Simulator-agnostic compile + run script for RTL Agent Team
# Usage: scripts/simulate.sh [OPTIONS] [SV_FILES...]
#
# Supported simulators: iverilog, verilator, vcs, xrun, questa
# Default: iverilog

set -euo pipefail

# ─── Defaults ───────────────────────────────────────────────────────────────
SIM="iverilog"
TOP=""
FILELIST=""
OUTDIR="sim/unit"
DEFINES=()
PARAMS=()
TRACE=0
SEED=""
TIMEOUT=""
TOOL_ARGS=""
SIM_ARGS=""
COMPILE_ONLY=0
RUN_ONLY=0
DPI_LIB=""
VERBOSE=0
SV_FILES=()

# ─── Usage ──────────────────────────────────────────────────────────────────
usage() {
  cat <<'EOF'
Usage: scripts/simulate.sh [OPTIONS] [SV_FILES...]

Options:
  --sim <name>       Simulator: iverilog|verilator|vcs|xrun|questa (default: iverilog)
  --top <module>     Top-level module name (required)
  --filelist <file>  Source filelist (.f file)
  --outdir <dir>     Output directory (default: sim/unit)
  --define KEY=VAL   Preprocessor define (repeatable, -D alias)
  -D KEY=VAL         Alias for --define
  --param KEY=VAL    Parameter override (repeatable, -P alias)
  -P KEY=VAL         Alias for --param
  --trace            Enable waveform dump (VCD: iverilog, FST: verilator)
  --seed <N>         Random seed
  --timeout <cycles> Simulation timeout in cycles
  --tool-args <str>  Simulator-specific compile flags
  --sim-args <str>   Simulator-independent runtime flags
  --compile-only     Compile but do not run
  --run-only         Run only (use existing compiled binary)
  --dpi <lib.so>     DPI-C shared library path (Tier 2 ref model)
  -v, --verbose      Verbose output
  -h, --help         Show this help

Examples:
  # Basic iverilog simulation
  scripts/simulate.sh --sim iverilog --top tb_module --outdir sim/module \
    rtl/module/module.sv sim/module/tb_module.sv

  # Verilator with DPI-C reference model
  scripts/simulate.sh --sim verilator --top tb_module --dpi refc/build/libref.so \
    --filelist rtl/filelist_top.f sim/module/tb_module.sv

  # Multi-seed regression with trace
  scripts/simulate.sh --sim iverilog --top tb_module --seed 42 --trace \
    rtl/module/module.sv sim/module/tb_module.sv
EOF
  exit 0
}

# ─── Parse Arguments ────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sim)        SIM="$2"; shift 2 ;;
    --top)        TOP="$2"; shift 2 ;;
    --filelist)   FILELIST="$2"; shift 2 ;;
    -f)           FILELIST="$2"; shift 2 ;;
    --outdir)     OUTDIR="$2"; shift 2 ;;
    --define|-D)  DEFINES+=("$2"); shift 2 ;;
    --param|-P)   PARAMS+=("$2"); shift 2 ;;
    --trace)      TRACE=1; shift ;;
    --seed)       SEED="$2"; shift 2 ;;
    --timeout)    TIMEOUT="$2"; shift 2 ;;
    --tool-args)  TOOL_ARGS="$2"; shift 2 ;;
    --sim-args)   SIM_ARGS="$2"; shift 2 ;;
    --compile-only) COMPILE_ONLY=1; shift ;;
    --run-only)   RUN_ONLY=1; shift ;;
    --dpi)        DPI_LIB="$2"; shift 2 ;;
    -v|--verbose) VERBOSE=1; shift ;;
    -h|--help)    usage ;;
    -*)           echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
    *)            SV_FILES+=("$1"); shift ;;
  esac
done

# ─── Validation ─────────────────────────────────────────────────────────────
if [[ -z "$TOP" ]]; then
  echo "ERROR: --top <module> is required" >&2
  exit 1
fi

if [[ ${#SV_FILES[@]} -eq 0 && -z "$FILELIST" && $RUN_ONLY -eq 0 ]]; then
  echo "ERROR: No source files specified. Provide SV files or --filelist" >&2
  exit 1
fi

# ─── Helpers ────────────────────────────────────────────────────────────────
log() {
  if [[ $VERBOSE -eq 1 ]]; then
    echo "[simulate.sh] $*"
  fi
}

# Build define flags for the target simulator
build_defines() {
  local sim="$1"
  local result=""
  for def in "${DEFINES[@]}"; do
    case "$sim" in
      iverilog|verilator|vcs|xrun|questa)
        result+=" -D${def}"
        ;;
    esac
  done
  echo "$result"
}

# Build param override flags
build_params() {
  local sim="$1"
  local result=""
  for param in "${PARAMS[@]}"; do
    case "$sim" in
      iverilog)   result+=" -P${TOP}.${param}" ;;
      verilator)  result+=" -G${param}" ;;
      vcs)        result+=" -pvalue+${TOP}.${param}" ;;
      xrun)       result+=" -defparam ${TOP}.${param}" ;;
      questa)     result+=" -g${param}" ;;
    esac
  done
  echo "$result"
}

# Read filelist, handling iverilog (-c) vs others (-f) differences
# Also converts +incdir+ to -I for iverilog
read_filelist() {
  local sim="$1"
  local flist="$2"
  local result=""

  if [[ ! -f "$flist" ]]; then
    echo "ERROR: Filelist not found: $flist" >&2
    exit 1
  fi

  if [[ "$sim" == "iverilog" ]]; then
    # iverilog: convert +incdir+ to -I, skip comments and empty lines
    while IFS= read -r line || [[ -n "$line" ]]; do
      # Strip comments and whitespace
      line="${line%%//*}"
      line="${line#"${line%%[![:space:]]*}"}"
      line="${line%"${line##*[![:space:]]}"}"
      [[ -z "$line" ]] && continue

      if [[ "$line" == +incdir+* ]]; then
        local dir="${line#+incdir+}"
        result+=" -I${dir}"
      elif [[ "$line" == -* || "$line" == +* ]]; then
        # Skip other directives not supported by iverilog
        log "Skipping unsupported directive for iverilog: $line"
      else
        result+=" ${line}"
      fi
    done < "$flist"
  else
    # verilator/vcs/xrun/questa: use -f directly
    result=" -f ${flist}"
  fi

  echo "$result"
}

# Build plusargs for runtime
build_plusargs() {
  local sim="$1"
  local result=""

  if [[ -n "$SEED" ]]; then
    case "$sim" in
      iverilog)   result+=" +seed=${SEED}" ;;
      verilator)  result+=" +verilator+seed+${SEED}" ;;
      vcs)        result+=" +ntb_random_seed=${SEED}" ;;
      xrun)       result+=" -svseed ${SEED}" ;;
      questa)     result+=" -sv_seed ${SEED}" ;;
    esac
  fi

  if [[ -n "$TIMEOUT" ]]; then
    result+=" +timeout=${TIMEOUT}"
  fi

  if [[ -n "$SIM_ARGS" ]]; then
    result+=" ${SIM_ARGS}"
  fi

  echo "$result"
}

# ─── Setup ──────────────────────────────────────────────────────────────────
mkdir -p "$OUTDIR"

DEFINE_FLAGS=""
if [[ ${#DEFINES[@]} -gt 0 ]]; then
  DEFINE_FLAGS=$(build_defines "$SIM")
fi

PARAM_FLAGS=""
if [[ ${#PARAMS[@]} -gt 0 ]]; then
  PARAM_FLAGS=$(build_params "$SIM")
fi

FILELIST_FLAGS=""
if [[ -n "$FILELIST" ]]; then
  FILELIST_FLAGS=$(read_filelist "$SIM" "$FILELIST")
fi

FILES="${SV_FILES[*]:-}"
PLUSARGS=$(build_plusargs "$SIM")

# ─── Per-Simulator Compile + Run ────────────────────────────────────────────

compile_iverilog() {
  local cmd="iverilog -g2012"
  cmd+=" ${DEFINE_FLAGS} ${PARAM_FLAGS} ${FILELIST_FLAGS}"
  if [[ $TRACE -eq 1 ]]; then
    cmd+=" -DTRACE_EN"
  fi
  cmd+=" ${TOOL_ARGS} -o ${OUTDIR}/${TOP} ${FILES}"

  log "Compile: $cmd"
  echo "$ $cmd"
  eval $cmd
}

run_iverilog() {
  local cmd="vvp ${OUTDIR}/${TOP}"
  if [[ $TRACE -eq 1 ]]; then
    cmd+=" -vcd"
  fi
  cmd+=" ${PLUSARGS}"

  log "Run: $cmd"
  echo "$ $cmd"
  eval $cmd
}

compile_verilator() {
  local cmd="verilator --binary -j0 --timing -sv"
  cmd+=" ${DEFINE_FLAGS} ${PARAM_FLAGS} ${FILELIST_FLAGS}"
  if [[ $TRACE -eq 1 ]]; then
    cmd+=" --trace-fst"
  fi
  if [[ -n "$DPI_LIB" ]]; then
    cmd+=" --dpi-lib ${DPI_LIB}"
  fi
  cmd+=" --top-module ${TOP} --Mdir ${OUTDIR}/vlt -o ${TOP}"
  cmd+=" ${TOOL_ARGS} ${FILES}"

  log "Compile: $cmd"
  echo "$ $cmd"
  eval $cmd
}

run_verilator() {
  local cmd="${OUTDIR}/vlt/${TOP}"
  cmd+=" ${PLUSARGS}"

  log "Run: $cmd"
  echo "$ $cmd"
  eval $cmd
}

compile_vcs() {
  local cmd="vcs -full64 -sverilog +v2k"
  cmd+=" ${DEFINE_FLAGS} ${PARAM_FLAGS} ${FILELIST_FLAGS}"
  if [[ $TRACE -eq 1 ]]; then
    cmd+=" +vcs+vcdpluson"
  fi
  if [[ -n "$DPI_LIB" ]]; then
    cmd+=" -LDFLAGS \"${DPI_LIB}\""
  fi
  cmd+=" ${TOOL_ARGS} -o ${OUTDIR}/${TOP} ${FILES}"

  log "Compile: $cmd"
  echo "$ $cmd"
  eval $cmd
}

run_vcs() {
  local cmd="${OUTDIR}/${TOP}"
  cmd+=" ${PLUSARGS}"

  log "Run: $cmd"
  echo "$ $cmd"
  eval $cmd
}

compile_xrun() {
  local cmd="xrun -compile -sv"
  cmd+=" ${DEFINE_FLAGS} ${PARAM_FLAGS} ${FILELIST_FLAGS}"
  if [[ $TRACE -eq 1 ]]; then
    cmd+=" -access +rwc"
  fi
  if [[ -n "$DPI_LIB" ]]; then
    cmd+=" -sv_lib ${DPI_LIB}"
  fi
  cmd+=" -xmlibdirname ${OUTDIR}/xlib ${TOOL_ARGS} ${FILES}"

  log "Compile: $cmd"
  echo "$ $cmd"
  eval $cmd
}

run_xrun() {
  local cmd="xrun -R -xmlibdirname ${OUTDIR}/xlib"
  if [[ $TRACE -eq 1 ]]; then
    cmd+=" -input \"database -open waves.shm -default; probe -create -all -depth all; run; exit\""
  fi
  cmd+=" ${PLUSARGS}"

  log "Run: $cmd"
  echo "$ $cmd"
  eval $cmd
}

compile_questa() {
  local cmd="vlog -sv"
  cmd+=" ${DEFINE_FLAGS} ${PARAM_FLAGS} ${FILELIST_FLAGS}"
  cmd+=" ${TOOL_ARGS} ${FILES}"

  log "Compile: $cmd"
  echo "$ $cmd"
  eval $cmd

  # Optimize
  local opt_cmd="vopt +acc ${TOP} -o ${TOP}_opt"
  if [[ -n "$DPI_LIB" ]]; then
    opt_cmd+=" -sv_lib ${DPI_LIB}"
  fi
  log "Optimize: $opt_cmd"
  echo "$ $opt_cmd"
  eval $opt_cmd
}

run_questa() {
  local do_cmds="run -all; quit -f"
  if [[ $TRACE -eq 1 ]]; then
    do_cmds="vcd file ${OUTDIR}/${TOP}.vcd; vcd add -r /*; run -all; quit -f"
  fi
  local cmd="vsim -c ${TOP}_opt -do \"${do_cmds}\""
  cmd+=" ${PLUSARGS}"

  log "Run: $cmd"
  echo "$ $cmd"
  eval $cmd
}

# ─── Main Execution ─────────────────────────────────────────────────────────
echo "=== simulate.sh: ${SIM} | top=${TOP} | outdir=${OUTDIR} ==="

EXIT_CODE=0

if [[ $RUN_ONLY -eq 0 ]]; then
  echo "--- Compile ---"
  case "$SIM" in
    iverilog)   compile_iverilog ;;
    verilator)  compile_verilator ;;
    vcs)        compile_vcs ;;
    xrun)       compile_xrun ;;
    questa)     compile_questa ;;
    *)
      echo "ERROR: Unsupported simulator: $SIM" >&2
      echo "Supported: iverilog, verilator, vcs, xrun, questa" >&2
      exit 1
      ;;
  esac
  echo "--- Compile OK ---"
fi

if [[ $COMPILE_ONLY -eq 0 ]]; then
  echo "--- Run ---"
  case "$SIM" in
    iverilog)   run_iverilog ;;
    verilator)  run_verilator ;;
    vcs)        run_vcs ;;
    xrun)       run_xrun ;;
    questa)     run_questa ;;
  esac
  EXIT_CODE=$?
  echo "--- Run complete (exit code: ${EXIT_CODE}) ---"
fi

exit $EXIT_CODE
