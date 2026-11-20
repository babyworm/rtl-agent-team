#!/usr/bin/env bash
# UVM Multi-Seed Regression Runner
# Usage:
#   bash run_regression_uvm.sh [--sim vcs|xrun|questa] [--seeds "42 123 456 789 1337"]
#                               [--parallel N] [--test UVM_TESTNAME]
#                               [--max-fail-rate 5] [--module MODULE]
#
# Runs UVM test suite with multiple seeds on commercial simulators,
# captures per-seed results, merges coverage, and generates regression report.
#
# Coverage: native databases, or explicit functional bin counts from the testbench.

set -euo pipefail

# RAT_PROJECT_ROOT (optional env) overrides the working root so relative paths
# resolve against the project root even when invoked from a different CWD.
PROJECT_ROOT="${RAT_PROJECT_ROOT:-$(pwd)}"
export RAT_PROJECT_ROOT="$PROJECT_ROOT"
export RAT_TOOL_CATEGORY=simulators
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_LIB_RUNNER="${RAT_RUNTIME_LIB:-}"
for candidate in "$SCRIPT_DIR/../../rat-init-project/templates/lib/tool-runner.sh" "$PROJECT_ROOT/lib/tool-runner.sh"; do
  if [[ -z "$_LIB_RUNNER" && -f "$candidate" ]]; then _LIB_RUNNER="$candidate"; fi
done
source "$_LIB_RUNNER"
rat_dispatch_wrapper "${BASH_SOURCE[0]}" "$@"
RAT_EVIDENCE_REQUIRED=0
[[ -f "$PROJECT_ROOT/rat_config.json" || -d "$PROJECT_ROOT/.rat" ]] && RAT_EVIDENCE_REQUIRED=1


EVIDENCE_HELPER="${RAT_RUNTIME_HELPERS:-$(dirname "$_LIB_RUNNER")}/verify_evidence.py"
[[ -f "$EVIDENCE_HELPER" ]] || EVIDENCE_HELPER="$SCRIPT_DIR/../../../scripts/verify_evidence.py"
COVERPOINT_HELPER="$(dirname "$EVIDENCE_HELPER")/merge_coverpoint_logs.py"
CAMPAIGN_SNAPSHOT=""
FUNCTIONAL_COMPLETE=0
finish_campaign() {
  local code=$? evidence_code evidence_result=0
  trap - EXIT
  if [[ -n "$CAMPAIGN_SNAPSHOT" ]]; then
    local combined="$CAMPAIGN_OUTDIR/campaign.log"
    local runtime="$CAMPAIGN_OUTDIR/runtime.log"
    find "$CAMPAIGN_OUTDIR" -type f -name sim.log -exec cat {} + > "$runtime"
    cat "$CAMPAIGN_OUTDIR/compile.log" "$runtime" > "$combined"
    evidence_code=$code
    [[ "$FUNCTIONAL_COMPLETE" != 1 ]] || evidence_code=0
    "$RAT_PYTHON" "$EVIDENCE_HELPER" finish --snapshot "$CAMPAIGN_SNAPSHOT" \
      --exit-code "$evidence_code" --log "$combined" --runtime-log "$runtime" || evidence_result=$?
    [[ "$code" -ne 0 ]] || code=$evidence_result
  fi
  exit "$code"
}

# ─── Defaults ───────────────────────────────────────────────────────────────
SEEDS="${SEEDS:-42 123 456 789 1337}"
SIM="${SIM:-}"
PARALLEL="${PARALLEL:-}"
TEST="${TEST:-}"
MODULE="${MODULE:-top}"
TB_TOP="${TB_TOP:-tb_top}"
TB_DIR="${TB_DIR:-sim/uvm}"
RESULTS_DIR="${RESULTS_DIR:-sim/uvm/regression}"
COVERAGE_DIR="${COVERAGE_DIR:-sim/uvm/coverage}"
FILELIST="${FILELIST:-rtl/filelist_top.f}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)_$$"
MAX_FAIL_RATE="${MAX_FAIL_RATE:-5}"
COVERAGE_MODE=auto
COVERAGE_TIMEOUT=60
SIM_TIMEOUT=""

# ─── Usage ──────────────────────────────────────────────────────────────────
usage() {
  cat <<'EOF'
Usage: run_regression_uvm.sh [OPTIONS]

Options:
  --sim <vcs|xrun|questa>  Commercial simulator (default: vcs)
  --seeds "42 123 ..."     Seed list (space-separated, default: 42 123 456 789 1337)
  --parallel <N>           Concurrent jobs (default: max(1, nproc-2))
  --test <name>            UVM test name (default: <module>_base_test)
  --module <name>          Module label for reports (default: top)
  --tb-top <name>          Testbench top module (default: tb_top)
  --tb-dir <path>          UVM testbench directory (default: sim/uvm)
  --filelist <path>        RTL filelist (default: rtl/filelist_top.f)
  --max-fail-rate <N>      Early-stop threshold in percent (default: 5)
  --coverage-mode <auto|native|functional-log>  Default: auto
  --coverage-timeout <seconds>  Maximum per vendor coverage command (default: 60)
  --sim-timeout <seconds>  Maximum per compile, elaborate or seed run (default: execution timeout)
  -h, --help               Show this help

Coverage reference targets (reported for downstream analysis):
  Line       ≥ 90%
  Toggle     ≥ 80%
  FSM        ≥ 70%
  Branch     ≥ 80%
  Functional ≥ 95%
EOF
}

# ─── Parse args ─────────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --sim)           SIM="$2"; shift 2 ;;
    --seeds)         SEEDS="$2"; shift 2 ;;
    --parallel)      PARALLEL="$2"; shift 2 ;;
    --test)          TEST="$2"; shift 2 ;;
    --module)        MODULE="$2"; shift 2 ;;
    --tb-top)        TB_TOP="$2"; shift 2 ;;
    --tb-dir)        TB_DIR="$2"; shift 2 ;;
    --filelist)      FILELIST="$2"; shift 2 ;;
    --max-fail-rate) MAX_FAIL_RATE="$2"; shift 2 ;;
    --coverage-mode) COVERAGE_MODE="$2"; shift 2 ;;
    --coverage-timeout) COVERAGE_TIMEOUT="$2"; shift 2 ;;
    --sim-timeout)   SIM_TIMEOUT="$2"; shift 2 ;;
    -h|--help)       usage; exit 0 ;;
    *)               echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$SIM" || "$SIM" == auto ]]; then
  SIM=$(rat_config_value preferences.simulator)
  SIM="${SIM:-vcs}"
fi
case "$SIM" in vsim) SIM=questa ;; xcelium) SIM=xrun ;; esac

# ─── Helpers ────────────────────────────────────────────────────────────────
require_uint() {
  local name="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[0-9]+$ ]]; then
    echo "ERROR: $name must be an unsigned integer, got: $value" >&2
    exit 1
  fi
}

require_identifier() {
  local name="$1"
  local value="$2"
  if [[ ! "$value" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "ERROR: $name must be a SystemVerilog identifier, got: $value" >&2
    exit 1
  fi
}

SEED_ARRAY=()
read -r -a SEED_ARRAY <<< "$SEEDS"
if [[ ${#SEED_ARRAY[@]} -eq 0 ]]; then
  echo "ERROR: --seeds must contain at least one seed" >&2
  exit 1
fi

for seed in "${SEED_ARRAY[@]}"; do
  require_uint "--seeds entry" "$seed"
done

require_uint "--max-fail-rate" "$MAX_FAIL_RATE"
if [[ "$MAX_FAIL_RATE" -gt 100 ]]; then
  echo "ERROR: --max-fail-rate must be between 0 and 100, got: $MAX_FAIL_RATE" >&2
  exit 1
fi

require_identifier "--module" "$MODULE"
require_identifier "--tb-top" "$TB_TOP"
if [[ -z "$TEST" ]]; then
  TEST="${MODULE}_base_test"
fi
require_identifier "--test" "$TEST"

case "$COVERAGE_MODE" in
  auto|native|functional-log) ;;
  *) echo "ERROR: --coverage-mode must be auto, native or functional-log" >&2; exit 1 ;;
esac
if [[ ! "$COVERAGE_TIMEOUT" =~ ^[1-9][0-9]*$ || ( -n "$SIM_TIMEOUT" && ! "$SIM_TIMEOUT" =~ ^[1-9][0-9]*$ ) ]]; then
  echo "ERROR: timeouts must be positive whole seconds" >&2
  exit 1
fi
if [[ -n "$SIM_TIMEOUT" ]]; then export RAT_TOOL_TIMEOUT_SECONDS="$SIM_TIMEOUT"; fi

detect_nproc() {
  if command -v nproc >/dev/null 2>&1; then nproc; return; fi
  if command -v getconf >/dev/null 2>&1; then getconf _NPROCESSORS_ONLN 2>/dev/null || true; return; fi
  echo "4"
}

default_parallel() {
  local np
  np=$(detect_nproc)
  if [[ ! "$np" =~ ^[1-9][0-9]*$ ]]; then
    np=4
  fi
  local p=$((np - 2))
  [[ "$p" -lt 1 ]] && p=1
  echo "$p"
}

if [[ -z "$PARALLEL" ]]; then
  PARALLEL=$(default_parallel)
fi
require_uint "--parallel" "$PARALLEL"
if [[ "$PARALLEL" -lt 1 ]]; then
  echo "ERROR: --parallel must be >= 1, got: $PARALLEL" >&2
  exit 1
fi

# ─── Simulator availability check ──────────────────────────────────────────
case "$SIM" in
  vcs)    SIM_BIN="vcs"; RUN_BIN="./simv"; MERGER="urg" ;;
  xrun)   SIM_BIN="xrun"; MERGER="imc" ;;
  questa) SIM_BIN="vsim"; MERGER="vcover" ;;
  *)      echo "ERROR: Unsupported simulator: $SIM (use vcs|xrun|questa)" >&2; exit 1 ;;
esac

if ! tool_available "$SIM_BIN"; then
  echo "ERROR: Simulator '$SIM_BIN' not found in PATH" >&2
  exit 1
fi

if ! command -v "$RAT_PYTHON" >/dev/null 2>&1; then
  echo "ERROR: $RAT_PYTHON is required to write and validate regression JSON" >&2
  exit 1
fi

NATIVE_COVERAGE_STATUS="NOT_RUN"
NATIVE_CAPTURE=0
COMPILE_COVERAGE=()
if [[ "$COVERAGE_MODE" != functional-log ]]; then
  if RAT_TOOL_CATEGORY=coverage tool_available "$MERGER" || [[ "$COVERAGE_MODE" == native ]]; then
    NATIVE_CAPTURE=1
    case "$SIM" in
      vcs) COMPILE_COVERAGE=(-cm line+cond+fsm+tgl+branch) ;;
      xrun) COMPILE_COVERAGE=(-coverage all) ;;
      questa) COMPILE_COVERAGE=(+cover=bcestf) ;;
    esac
  else
    NATIVE_COVERAGE_STATUS="UNAVAILABLE"
    echo "Native coverage: $MERGER unavailable; using functional bin logs" >&2
  fi
fi

# ─── Resolve input/output paths against PROJECT_ROOT ──────────────────
# Done BEFORE source collection so the filelist/TB dir are found even when the
# invocation CWD differs from the project root (RAT_PROJECT_ROOT override).
[[ "$RESULTS_DIR" != /* ]] && RESULTS_DIR="$PROJECT_ROOT/$RESULTS_DIR"
[[ "$COVERAGE_DIR" != /* ]] && COVERAGE_DIR="$PROJECT_ROOT/$COVERAGE_DIR"
[[ "$FILELIST" != /* ]] && FILELIST="$PROJECT_ROOT/$FILELIST"
[[ "$TB_DIR" != /* ]] && TB_DIR="$PROJECT_ROOT/$TB_DIR"

# ─── Collect source inputs ──────────────────────────────────────────────────
# Preserve +incdir+, +define+, and nested -f semantics by passing the filelist
# through unchanged and compiling from PROJECT_ROOT.
SV_ARGS=()
if [[ -f "$FILELIST" ]]; then
  SV_ARGS+=("-f" "$FILELIST")
fi

# Auto-include rtl/common/ (SRAM wrappers)
if [[ -d "$PROJECT_ROOT/rtl/common" ]]; then
  while IFS= read -r f; do
    SV_ARGS+=("$f")
  done < <(find "$PROJECT_ROOT/rtl/common" \( -name '*.sv' -o -name '*.v' \) -type f 2>/dev/null | sort)
fi

# UVM TB files
if [[ -d "$TB_DIR" ]]; then
  while IFS= read -r f; do
    SV_ARGS+=("$f")
  done < <(find "$TB_DIR" -name '*.sv' -type f 2>/dev/null | sort)
fi

if [[ ${#SV_ARGS[@]} -eq 0 ]]; then
  echo "ERROR: No RTL filelist or UVM SystemVerilog sources found" >&2
  exit 1
fi

# ─── Directory setup ───────────────────────────────────────────────────────
mkdir -p "$RESULTS_DIR" "$COVERAGE_DIR"
RUN_DIR="$RESULTS_DIR/run_${TIMESTAMP}"
mkdir -p "$RUN_DIR"

# ─── Compile (once) ────────────────────────────────────────────────────────
compile_uvm() {
  local compile_log="$RUN_DIR/compile.log"
  echo "=== UVM Compile ($SIM) ==="

  case "$SIM" in
    vcs)
      (cd "$PROJECT_ROOT" && run_tool vcs -full64 -sverilog -ntb_opts uvm-1.2 \
        "${COMPILE_COVERAGE[@]}" \
        -timescale=1ns/1ps \
        "${SV_ARGS[@]}" \
        -o "$RUN_DIR/simv") \
        2>&1 | tee "$compile_log" || {
        local rc=$?
        echo "ERROR: UVM compilation failed. See $compile_log" >&2
        return "$rc"
      }
      RUN_BIN="$RUN_DIR/simv"
      ;;
    xrun)
      (cd "$PROJECT_ROOT" && run_tool xrun -sv -uvm -compile \
        "${COMPILE_COVERAGE[@]}" \
        -timescale 1ns/1ps \
        "${SV_ARGS[@]}" \
        -xmlibdirname "$RUN_DIR/xcelium") \
        2>&1 | tee "$compile_log" || {
        local rc=$?
        echo "ERROR: UVM compilation failed. See $compile_log" >&2
        return "$rc"
      }
      (cd "$PROJECT_ROOT" && run_tool xrun -sv -uvm -elaborate \
        "${COMPILE_COVERAGE[@]}" \
        -timescale 1ns/1ps \
        "${SV_ARGS[@]}" \
        -top "$TB_TOP" \
        -xmlibdirname "$RUN_DIR/xcelium") \
        2>&1 | tee -a "$compile_log" || {
        local rc=$?
        echo "ERROR: UVM elaboration failed. See $compile_log" >&2
        return "$rc"
      }
      ;;
    questa)
      run_tool vlib "$RUN_DIR/work" 2>/dev/null || true
      (cd "$PROJECT_ROOT" && run_tool vlog -sv -work "$RUN_DIR/work" \
        "${COMPILE_COVERAGE[@]}" \
        +incdir+"$TB_DIR" \
        "${SV_ARGS[@]}") \
        2>&1 | tee "$compile_log" || {
        local rc=$?
        echo "ERROR: UVM compilation failed. See $compile_log" >&2
        return "$rc"
      }
      ;;
  esac
  echo "Compile OK: $compile_log"
}

count_uvm_messages() {
  local severity="$1"
  local log="$2"
  awk -v severity="$severity" '
    $0 ~ "^[[:space:]]*" severity "[[:space:]]*:" {
      value = $0
      sub("^[^:]*:[[:space:]]*", "", value)
      sub("[[:space:]].*$", "", value)
      if (value ~ /^[0-9]+$/) {
        summary = value
        found_summary = 1
        next
      }
    }
    $0 ~ "^[[:space:]]*" severity "([[:space:]@]|$)" { events++ }
    END {
      if (found_summary) print summary + 0
      else print events + 0
    }
  ' "$log" 2>/dev/null
}

# ─── Run single seed ───────────────────────────────────────────────────────
run_seed() {
  local seed="$1"
  local seed_dir="$RUN_DIR/seed_${seed}"
  local log="$seed_dir/sim.log"
  local result_json="$RUN_DIR/seed_${seed}_results.json"
  mkdir -p "$seed_dir" || return 1

  local status="PASS"
  local rc=0
  local coverage_present="false"
  local failure_reason=""
  local coverage_args=() questa_commands="run -all; quit -f"
  if [[ "$NATIVE_CAPTURE" -eq 1 ]]; then
    case "$SIM" in
      vcs) coverage_args=(-cm line+cond+fsm+tgl+branch -cm_dir "$seed_dir/coverage.vdb") ;;
      xrun) coverage_args=(-coverage all -covworkdir "$seed_dir/cov_work" -covscope "$TB_TOP") ;;
      questa)
        coverage_args=(-coverage)
        questa_commands="coverage save -onexit $seed_dir/coverage.ucdb; $questa_commands"
        ;;
    esac
  fi

  case "$SIM" in
    vcs)
      RAT_CONTEXT_TOOL="$SIM" run_tool "$RUN_BIN" \
        +UVM_TESTNAME="$TEST" \
        +ntb_random_seed="$seed" \
        "${coverage_args[@]}" \
        +UVM_VERBOSITY=UVM_MEDIUM \
        > "$log" 2>&1 || rc=$?
      ;;
    xrun)
      run_tool xrun -R \
        +UVM_TESTNAME="$TEST" \
        -svseed "$seed" \
        "${coverage_args[@]}" \
        -xmlibdirname "$RUN_DIR/xcelium" \
        +UVM_VERBOSITY=UVM_MEDIUM \
        > "$log" 2>&1 || rc=$?
      ;;
    questa)
      run_tool vsim -c -work "$RUN_DIR/work" \
        "${coverage_args[@]}" \
        +UVM_TESTNAME="$TEST" \
        -sv_seed "$seed" \
        -do "$questa_commands" \
        "$TB_TOP" \
        > "$log" 2>&1 || rc=$?
      ;;
  esac

  local observed
  observed=$("$RAT_PYTHON" "$EVIDENCE_HELPER" classify --log "$log" --exit-code "$rc")
  if [[ "$observed" != PASS ]]; then
    status="$observed"
    failure_reason="no_functional_pass:$observed"
  fi

  # Write per-seed result JSON
  local uvm_errors=0 uvm_warnings=0 uvm_fatals=0
  uvm_errors=$(count_uvm_messages UVM_ERROR "$log")
  uvm_warnings=$(count_uvm_messages UVM_WARNING "$log")
  uvm_fatals=$(count_uvm_messages UVM_FATAL "$log")

  if [[ "$status" == PASS && ( "$uvm_errors" -ne 0 || "$uvm_fatals" -ne 0 ) ]]; then
    status="FAIL"
    failure_reason="simulation_or_uvm_error"
  fi

  case "$SIM" in
    vcs)    [[ ! -d "$seed_dir/coverage.vdb" ]] || coverage_present="true" ;;
    xrun)   [[ ! -d "$seed_dir/cov_work" ]] || coverage_present="true" ;;
    questa) [[ ! -f "$seed_dir/coverage.ucdb" ]] || coverage_present="true" ;;
  esac

  if ! "$RAT_PYTHON" - "$result_json" "$seed" "$TEST" "$SIM" "$status" "$rc" \
    "$uvm_errors" "$uvm_warnings" "$uvm_fatals" "$log" "$seed_dir" "$coverage_present" \
    "$failure_reason" <<'PY'
import json
import sys

(
    output, seed, test, simulator, status, exit_code, uvm_errors,
    uvm_warnings, uvm_fatals, log, coverage_dir, coverage_present, failure_reason,
) = sys.argv[1:]
payload = {
    "seed": int(seed),
    "test": test,
    "simulator": simulator,
    "status": status,
    "exit_code": int(exit_code),
    "uvm_errors": int(uvm_errors),
    "uvm_warnings": int(uvm_warnings),
    "uvm_fatals": int(uvm_fatals),
    "log": log,
    "coverage_dir": coverage_dir,
    "coverage_present": coverage_present == "true",
    "failure_reason": failure_reason or None,
}
with open(output, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY
  then
    return 1
  fi

  echo "  Seed $seed: $status (rc=$rc, errors=$uvm_errors)"
}

# ─── Coverage merge ────────────────────────────────────────────────────────
run_coverage_tool() {
  RAT_TOOL_CATEGORY=coverage tool_available "$1" || return 127
  RAT_TOOL_CATEGORY=coverage RAT_TOOL_TIMEOUT_SECONDS="$COVERAGE_TIMEOUT" run_tool "$@"
}

merge_native_coverage() {
  echo "=== Merging Coverage ==="
  local merged="$COVERAGE_DIR/merged_${TIMESTAMP}"
  local coverage_inputs=0

  case "$SIM" in
    vcs)
      local vdb_list=()
      for d in "$RUN_DIR"/seed_*/coverage.vdb; do
        [[ -d "$d" ]] && vdb_list+=("$d")
      done
      coverage_inputs=${#vdb_list[@]}
      [[ "$coverage_inputs" -eq "$PASSED" ]] || return 1
      run_coverage_tool urg -dir "${vdb_list[@]}" -report "$merged" -format both \
        > "$RUN_DIR/coverage-tool.log" 2>&1 || return $?
      [[ -d "$merged" && -n "$(find "$merged" -type f -size +0c -print -quit)" ]] || return 1
      echo "VCS coverage merged: $merged (text + XML)"
      ;;
    xrun)
      # Xcelium stores coverage under covworkdir/scope/ — merge all seed runs
      local imc_script="$RUN_DIR/imc_merge.tcl"
      {
        echo "merge -out \"$merged\" \\"
        for d in "$RUN_DIR"/seed_*/cov_work; do
          if [[ -d "$d" ]]; then
            coverage_inputs=$((coverage_inputs + 1))
            echo "  -run \"$d\" \\"
          fi
        done
        echo ""
        echo "report -detail -out \"${merged}_report.txt\""
        echo "exit"
      } > "$imc_script"
      [[ "$coverage_inputs" -eq "$PASSED" ]] || return 1
      run_coverage_tool imc -exec "$imc_script" > "$RUN_DIR/coverage-tool.log" 2>&1 || return $?
      [[ -s "${merged}_report.txt" ]] || return 1
      echo "Xcelium coverage merged: $merged"
      ;;
    questa)
      local ucdb_list=()
      for f in "$RUN_DIR"/seed_*/coverage.ucdb; do
        [[ -f "$f" ]] && ucdb_list+=("$f")
      done
      coverage_inputs=${#ucdb_list[@]}
      [[ "$coverage_inputs" -eq "$PASSED" ]] || return 1
      run_coverage_tool vcover merge "$merged.ucdb" "${ucdb_list[@]}" \
        > "$RUN_DIR/coverage-tool.log" 2>&1 || return $?
      run_coverage_tool vcover report -details "$merged.ucdb" > "$merged.txt" 2>&1 || return $?
      [[ -s "$merged.ucdb" && -s "$merged.txt" ]] || return 1
      echo "Questa coverage merged: $merged.ucdb"
      ;;
  esac

  [[ "$coverage_inputs" -gt 0 ]]
}

merge_functional_coverage() {
  local logs=() seed log
  for seed in "${RUN_SEEDS[@]}"; do
    log="$RUN_DIR/seed_$seed/sim.log"
    logs+=("${log#"$PROJECT_ROOT/"}")
  done
  local report="$COVERAGE_DIR/functional_${TIMESTAMP}.json"
  report="${report#"$PROJECT_ROOT/"}"
  (cd "$PROJECT_ROOT" && "$RAT_PYTHON" "$COVERPOINT_HELPER" --output "$report" "${logs[@]}") || return $?
  FUNCTIONAL_COVERAGE_REPORT="$report"
  echo "Functional coverage from seed logs: $FUNCTIONAL_COVERAGE_REPORT"
}

# ─── Harvest results ───────────────────────────────────────────────────────
PASSED=0
FAILED=0
FAILED_SEEDS=""
STOP_DISPATCH=0
PROCESSED_RESULT_FILES=""
COVERAGE_STATUS="NOT_RUN"
FUNCTIONAL_COVERAGE_REPORT=""
INFRASTRUCTURE_FAILED=0
WORKER_PIDS=()

harvest_results() {
  shopt -s nullglob
  local result_files=("$RUN_DIR"/seed_*_results.json)
  shopt -u nullglob

  if [[ ${#result_files[@]} -eq 0 ]]; then return; fi

  for result_file in "${result_files[@]}"; do
    case "$PROCESSED_RESULT_FILES" in
      *"|${result_file}|"*) continue ;;
    esac
    PROCESSED_RESULT_FILES="${PROCESSED_RESULT_FILES}|${result_file}|"

    local parsed status fseed
    if ! parsed=$("$RAT_PYTHON" - "$result_file" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    result = json.load(handle)
print(result["status"], int(result["seed"]))
PY
    ); then
      FAILED=$((FAILED + 1))
      INFRASTRUCTURE_FAILED=1
      echo "  Invalid result JSON: $result_file" >&2
      continue
    fi
    status=${parsed%% *}
    fseed=${parsed##* }

    if [[ "$status" == "PASS" ]]; then
      PASSED=$((PASSED + 1))
    else
      FAILED=$((FAILED + 1))
      FAILED_SEEDS+=" $fseed"
    fi
  done
}

mark_missing_results() {
  local seed result_file
  for seed in "${RUN_SEEDS[@]}"; do
    result_file="$RUN_DIR/seed_${seed}_results.json"
    if [[ -f "$result_file" ]]; then
      continue
    fi
    FAILED=$((FAILED + 1))
    FAILED_SEEDS+=" $seed"
    INFRASTRUCTURE_FAILED=1
    PROCESSED_RESULT_FILES="${PROCESSED_RESULT_FILES}|${result_file}|"
    echo "  Seed $seed: FAIL (missing result JSON)" >&2
  done
}

should_halt() {
  local total=$((PASSED + FAILED))
  [[ "$total" -eq 0 ]] && return 1
  [[ "$FAILED" -eq 0 ]] && return 1
  local rate=$(( (FAILED * 100) / total ))
  [[ "$rate" -ge "$MAX_FAIL_RATE" ]]
}

count_active_jobs() {
  jobs -r 2>/dev/null | wc -l
}

# ─── Main ───────────────────────────────────────────────────────────────────
echo "========================================"
echo " UVM Regression: $MODULE"
echo " Simulator: $SIM"
echo " Test: $TEST"
echo " Seeds: $SEEDS"
echo " Parallel: $PARALLEL"
echo " Max fail rate: ${MAX_FAIL_RATE}%"
echo "========================================"

if [[ "$RAT_EVIDENCE_REQUIRED" == 1 ]]; then
  CAMPAIGN_OUTDIR="$RUN_DIR"
  args=(begin --root "$PROJECT_ROOT" --outdir "$RUN_DIR" --tool "$SIM" --top "$TB_TOP" --runner-pid "$$" --context "uvm:$TEST")
  [[ ! -f "$PROJECT_ROOT/rat_config.json" ]] || args+=(--dependency "$PROJECT_ROOT/rat_config.json")
  for input in "${SV_ARGS[@]}"; do
    [[ "$input" == -f ]] && continue
    if [[ "$input" == "$FILELIST" ]]; then args+=(--filelist "$input"); else args+=(--source "$input"); fi
  done
  args+=(--include-dir "$TB_DIR")
  # Standard UVM headers are site inputs and must be locatable for hashing.
  [[ -z "${UVM_HOME:-}" ]] || args+=(--include-dir "$UVM_HOME/src")
  CAMPAIGN_SNAPSHOT=$(RAT_CONTEXT_TOOL="$SIM" rat_capture_path "$RAT_PYTHON" "$EVIDENCE_HELPER" "${args[@]}")
  trap finish_campaign EXIT
fi

compile_uvm

echo ""
echo "=== Running Seeds ==="
RUN_SEEDS=()
for seed in "${SEED_ARRAY[@]}"; do
  if [[ "$STOP_DISPATCH" -eq 1 ]]; then
    echo "  Skipping seed $seed (halt threshold reached)"
    continue
  fi

  RUN_SEEDS+=("$seed")
  if [[ "$PARALLEL" -gt 1 ]]; then
    run_seed "$seed" &
    WORKER_PIDS+=("$!")
    while [[ "$(count_active_jobs)" -ge "$PARALLEL" ]]; do
      sleep 0.2
      harvest_results
      if should_halt; then
        STOP_DISPATCH=1
        echo "  HALT: failure rate >= ${MAX_FAIL_RATE}%"
        break
      fi
    done
  else
    if ! run_seed "$seed"; then
      INFRASTRUCTURE_FAILED=1
    fi
    harvest_results
    if should_halt; then
      STOP_DISPATCH=1
      echo "  HALT: failure rate >= ${MAX_FAIL_RATE}%"
    fi
  fi
done

# Wait for remaining parallel jobs
if [[ "$PARALLEL" -gt 1 ]]; then
  while [[ "$(count_active_jobs)" -gt 0 ]]; do
    sleep 0.2
    harvest_results
  done
  for worker_pid in "${WORKER_PIDS[@]}"; do
    if ! wait "$worker_pid" 2>/dev/null; then
      INFRASTRUCTURE_FAILED=1
    fi
  done
  harvest_results
fi
mark_missing_results

# ─── Coverage merge ────────────────────────────────────────────────────────
if [[ "$FAILED" -eq 0 && "$INFRASTRUCTURE_FAILED" -eq 0 && "$PASSED" -eq "${#SEED_ARRAY[@]}" ]]; then
  FUNCTIONAL_COMPLETE=1
  COVERAGE_STATUS="FAILED"
  if [[ "$NATIVE_CAPTURE" -eq 1 ]]; then
    if merge_native_coverage; then
      NATIVE_COVERAGE_STATUS="MERGED"
      COVERAGE_STATUS="MERGED"
    else
      case "$?" in
        124) NATIVE_COVERAGE_STATUS="TIMEOUT" ;;
        125) NATIVE_COVERAGE_STATUS="STALL" ;;
        127) NATIVE_COVERAGE_STATUS="UNAVAILABLE" ;;
        *) NATIVE_COVERAGE_STATUS="FAILED" ;;
      esac
      echo "Native coverage: $NATIVE_COVERAGE_STATUS" >&2
    fi
  fi
  if [[ "$COVERAGE_STATUS" != MERGED && "$COVERAGE_MODE" != native ]] && merge_functional_coverage; then
    COVERAGE_STATUS="FUNCTIONAL_LOG"
  fi
  if [[ "$COVERAGE_STATUS" == FAILED ]]; then
    INFRASTRUCTURE_FAILED=1
    echo "ERROR: Coverage artifacts were missing or could not be merged" >&2
  fi
fi

# ─── Regression report ──────────────────────────────────────────────────────
TOTAL=$((PASSED + FAILED))
REPORT="$RESULTS_DIR/regression_${MODULE}_${TIMESTAMP}.json"
VERDICT="FAIL"
if [[ "$FUNCTIONAL_COMPLETE" -eq 1 && "$INFRASTRUCTURE_FAILED" -eq 0 ]]; then
  if [[ "$COVERAGE_STATUS" == MERGED || "$COVERAGE_MODE" == functional-log ]]; then
    VERDICT="PASS"
  else
    VERDICT="INCONCLUSIVE"
  fi
fi

"$RAT_PYTHON" - "$REPORT" "$MODULE" "$SIM" "$TEST" "$TIMESTAMP" "$TOTAL" \
  "$PASSED" "$FAILED" "$STOP_DISPATCH" "$COVERAGE_STATUS" \
  "$INFRASTRUCTURE_FAILED" "$COVERAGE_DIR" "$RUN_DIR" "$VERDICT" \
  "$FAILED_SEEDS" "$COVERAGE_MODE" "$NATIVE_COVERAGE_STATUS" "$FUNCTIONAL_COVERAGE_REPORT" "$FUNCTIONAL_COMPLETE" <<'PY'
import json
import sys

(
    output, module, simulator, test, timestamp, total, passed, failed,
    halted, coverage_status, infrastructure_failed, coverage_dir, run_dir,
    verdict, failed_seeds_text, coverage_mode, native_status, functional_report, functional_complete,
) = sys.argv[1:]
payload = {
    "module": module,
    "simulator": simulator,
    "test": test,
    "timestamp": timestamp,
    "seeds_total": int(total),
    "seeds_passed": int(passed),
    "seeds_failed": int(failed),
    "failed_seeds": [int(seed) for seed in failed_seeds_text.split()],
    "halted_early": halted == "1",
    "coverage_status": coverage_status,
    "coverage_scope": {"MERGED": "native", "FUNCTIONAL_LOG": "functional_only"}.get(coverage_status),
    "coverage_mode": coverage_mode,
    "native_coverage_status": native_status,
    "functional_coverage_report": functional_report or None,
    "functional_regression_passed": functional_complete == "1",
    "coverage_targets": {
        "line": 90,
        "toggle": 80,
        "fsm": 70,
        "branch": 80,
        "functional": 95,
    },
    "infrastructure_failed": infrastructure_failed == "1",
    "coverage_dir": coverage_dir,
    "run_dir": run_dir,
    "verdict": verdict,
}
with open(output, "w", encoding="utf-8") as handle:
    json.dump(payload, handle, indent=2)
    handle.write("\n")
PY

echo ""
echo "========================================"
echo " Regression Summary"
echo "========================================"
echo " Total:  $TOTAL"
echo " Passed: $PASSED"
echo " Failed: $FAILED"
if [[ -n "$FAILED_SEEDS" ]]; then
  echo " Failed seeds:$FAILED_SEEDS"
fi
echo " Coverage: $COVERAGE_STATUS"
echo " Report: $REPORT"
echo " Verdict: $VERDICT"
echo "========================================"

[[ "$VERDICT" == "PASS" ]] && exit 0
[[ "$VERDICT" != "INCONCLUSIVE" ]] || exit 3
exit 1

# rat-version: 2.0.4
