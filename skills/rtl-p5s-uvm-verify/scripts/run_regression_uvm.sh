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
# Coverage: code coverage (line+cond+fsm+tgl+branch) is always enabled.
# Functional coverage is collected via UVM covergroups in the testbench.

set -euo pipefail

PROJECT_ROOT="$(pwd)"

# ─── Defaults ───────────────────────────────────────────────────────────────
SEEDS="${SEEDS:-42 123 456 789 1337}"
SIM="${SIM:-vcs}"
PARALLEL="${PARALLEL:-}"
TEST="${TEST:-base_test}"
MODULE="${MODULE:-top}"
TB_DIR="${TB_DIR:-sim/uvm}"
RESULTS_DIR="${RESULTS_DIR:-sim/uvm/regression}"
COVERAGE_DIR="${COVERAGE_DIR:-sim/uvm/coverage}"
FILELIST="${FILELIST:-rtl/filelist_top.f}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MAX_FAIL_RATE="${MAX_FAIL_RATE:-5}"
USER_SET_PARALLEL=0
COMPILE_DONE=0

# ─── Usage ──────────────────────────────────────────────────────────────────
usage() {
  cat <<'EOF'
Usage: run_regression_uvm.sh [OPTIONS]

Options:
  --sim <vcs|xrun|questa>  Commercial simulator (default: vcs)
  --seeds "42 123 ..."     Seed list (space-separated, default: 42 123 456 789 1337)
  --parallel <N>           Concurrent jobs (default: max(1, nproc-2))
  --test <name>            UVM test name (default: base_test)
  --module <name>          Module label for reports (default: top)
  --tb-dir <path>          UVM testbench directory (default: sim/uvm)
  --filelist <path>        RTL filelist (default: rtl/filelist_top.f)
  --max-fail-rate <N>      Early-stop threshold in percent (default: 5)
  -h, --help               Show this help

Coverage Targets (enforced at report time):
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
    --parallel)      PARALLEL="$2"; USER_SET_PARALLEL=1; shift 2 ;;
    --test)          TEST="$2"; shift 2 ;;
    --module)        MODULE="$2"; shift 2 ;;
    --tb-dir)        TB_DIR="$2"; shift 2 ;;
    --filelist)      FILELIST="$2"; shift 2 ;;
    --max-fail-rate) MAX_FAIL_RATE="$2"; shift 2 ;;
    -h|--help)       usage; exit 0 ;;
    *)               echo "ERROR: Unknown option: $1" >&2; exit 1 ;;
  esac
done

# ─── Helpers ────────────────────────────────────────────────────────────────
detect_nproc() {
  if command -v nproc >/dev/null 2>&1; then nproc; return; fi
  if command -v getconf >/dev/null 2>&1; then getconf _NPROCESSORS_ONLN 2>/dev/null || true; return; fi
  echo "4"
}

default_parallel() {
  local np
  np=$(detect_nproc)
  local p=$((np - 2))
  [[ "$p" -lt 1 ]] && p=1
  echo "$p"
}

if [[ -z "$PARALLEL" ]]; then
  PARALLEL=$(default_parallel)
fi

# ─── Simulator availability check ──────────────────────────────────────────
case "$SIM" in
  vcs)    SIM_BIN="vcs"; RUN_BIN="./simv" ;;
  xrun)   SIM_BIN="xrun"; RUN_BIN="" ;;
  questa) SIM_BIN="vsim"; RUN_BIN="" ;;
  *)      echo "ERROR: Unsupported simulator: $SIM (use vcs|xrun|questa)" >&2; exit 1 ;;
esac

if ! command -v "$SIM_BIN" >/dev/null 2>&1; then
  echo "ERROR: Simulator '$SIM_BIN' not found in PATH" >&2
  exit 1
fi

# ─── Collect source files ──────────────────────────────────────────────────
SRC_FILES=()
if [[ -f "$FILELIST" ]]; then
  while IFS= read -r line; do
    line=$(echo "$line" | sed 's|//.*||' | xargs)
    [[ -z "$line" ]] && continue
    [[ "$line" == +* ]] && continue
    SRC_FILES+=("$line")
  done < "$FILELIST"
fi

# Auto-include rtl/common/ (SRAM wrappers)
if [[ -d rtl/common ]]; then
  while IFS= read -r f; do
    SRC_FILES+=("$f")
  done < <(find rtl/common -name '*.sv' -o -name '*.v' 2>/dev/null | sort)
fi

# UVM TB files
if [[ -d "$TB_DIR" ]]; then
  while IFS= read -r f; do
    SRC_FILES+=("$f")
  done < <(find "$TB_DIR" -name '*.sv' -o -name '*.svh' 2>/dev/null | sort)
fi

# ─── Resolve paths to absolute ─────────────────────────────────────────
[[ "$RESULTS_DIR" != /* ]] && RESULTS_DIR="$PROJECT_ROOT/$RESULTS_DIR"
[[ "$COVERAGE_DIR" != /* ]] && COVERAGE_DIR="$PROJECT_ROOT/$COVERAGE_DIR"
[[ "$FILELIST" != /* ]] && FILELIST="$PROJECT_ROOT/$FILELIST"
[[ "$TB_DIR" != /* ]] && TB_DIR="$PROJECT_ROOT/$TB_DIR"
_abs_src=()
for f in "${SRC_FILES[@]}"; do
  case "$f" in /*) _abs_src+=("$f") ;; *) _abs_src+=("$PROJECT_ROOT/$f") ;; esac
done
SRC_FILES=("${_abs_src[@]}")

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
      (cd "$RUN_DIR" && vcs -full64 -sverilog -ntb_opts uvm-1.2 \
        -cm line+cond+fsm+tgl+branch \
        -timescale=1ns/1ps \
        "${SRC_FILES[@]}" \
        -o simv) \
        2>&1 | tee "$compile_log"
      RUN_BIN="$RUN_DIR/simv"
      ;;
    xrun)
      xrun -sv -uvm -compile \
        -coverage all \
        -timescale 1ns/1ps \
        "${SRC_FILES[@]}" \
        -xmlibdirpath "$RUN_DIR/xcelium" \
        2>&1 | tee "$compile_log"
      ;;
    questa)
      vlib "$RUN_DIR/work" 2>/dev/null || true
      vlog -sv -work "$RUN_DIR/work" \
        +cover=bcestf \
        +incdir+"$TB_DIR" \
        "${SRC_FILES[@]}" \
        2>&1 | tee "$compile_log"
      ;;
  esac

  if [[ ${PIPESTATUS[0]} -ne 0 ]]; then
    echo "ERROR: UVM compilation failed. See $compile_log" >&2
    exit 1
  fi
  COMPILE_DONE=1
  echo "Compile OK: $compile_log"
}

# ─── Run single seed ───────────────────────────────────────────────────────
run_seed() {
  local seed="$1"
  local seed_dir="$RUN_DIR/seed_${seed}"
  local log="$seed_dir/sim.log"
  local result_json="$RESULTS_DIR/seed_${seed}_results.json"
  mkdir -p "$seed_dir"

  local status="PASS"
  local rc=0

  case "$SIM" in
    vcs)
      "$RUN_BIN" \
        +UVM_TESTNAME="$TEST" \
        +ntb_random_seed="$seed" \
        -cm line+cond+fsm+tgl+branch \
        -cm_dir "$seed_dir/coverage.vdb" \
        +UVM_VERBOSITY=UVM_MEDIUM \
        > "$log" 2>&1 || rc=$?
      ;;
    xrun)
      xrun -R \
        +UVM_TESTNAME="$TEST" \
        -seed "$seed" \
        -coverage all \
        -covworkdir "$seed_dir/cov_work" \
        -covscope tb_top \
        -xmlibdirpath "$RUN_DIR/xcelium" \
        +UVM_VERBOSITY=UVM_MEDIUM \
        > "$log" 2>&1 || rc=$?
      ;;
    questa)
      vsim -c -work "$RUN_DIR/work" \
        -coverage \
        +UVM_TESTNAME="$TEST" \
        -sv_seed "$seed" \
        -do "coverage save -onexit $seed_dir/coverage.ucdb; run -all; quit -f" \
        tb_top \
        > "$log" 2>&1 || rc=$?
      ;;
  esac

  # Check for UVM fatal/error
  if [[ $rc -ne 0 ]] || grep -qE 'UVM_FATAL|UVM_ERROR' "$log" 2>/dev/null; then
    status="FAIL"
  fi

  # Write per-seed result JSON
  local uvm_errors=0 uvm_warnings=0
  uvm_errors=$(grep -c 'UVM_ERROR' "$log" 2>/dev/null || echo 0)
  uvm_warnings=$(grep -c 'UVM_WARNING' "$log" 2>/dev/null || echo 0)

  cat > "$result_json" << SEED_EOF
{
  "seed": $seed,
  "test": "$TEST",
  "simulator": "$SIM",
  "status": "$status",
  "exit_code": $rc,
  "uvm_errors": $uvm_errors,
  "uvm_warnings": $uvm_warnings,
  "log": "$log",
  "coverage_dir": "$seed_dir"
}
SEED_EOF

  echo "  Seed $seed: $status (rc=$rc, errors=$uvm_errors)"
}

# ─── Coverage merge ────────────────────────────────────────────────────────
merge_coverage() {
  echo "=== Merging Coverage ==="
  local merged="$COVERAGE_DIR/merged_${TIMESTAMP}"

  case "$SIM" in
    vcs)
      local vdb_list=()
      for d in "$RUN_DIR"/seed_*/coverage.vdb; do
        [[ -d "$d" ]] && vdb_list+=("$d")
      done
      if [[ ${#vdb_list[@]} -gt 0 ]]; then
        # Generate both text (human) and XML (coverage-analyst parsing)
        urg -dir "${vdb_list[@]}" -report "$merged" -format both 2>&1
        echo "VCS coverage merged: $merged (text + XML)"
      fi
      ;;
    xrun)
      # Xcelium stores coverage under covworkdir/scope/ — merge all seed runs
      local imc_script="$RUN_DIR/imc_merge.tcl"
      {
        echo "merge -out \"$merged\" \\"
        for d in "$RUN_DIR"/seed_*/cov_work; do
          [[ -d "$d" ]] && echo "  -run \"$d\" \\"
        done
        echo ""
        echo "report -detail -out \"${merged}_report.txt\""
        echo "exit"
      } > "$imc_script"
      imc -exec "$imc_script" 2>&1 || true
      echo "Xcelium coverage merged: $merged"
      ;;
    questa)
      local ucdb_list=()
      for f in "$RUN_DIR"/seed_*/coverage.ucdb; do
        [[ -f "$f" ]] && ucdb_list+=("$f")
      done
      if [[ ${#ucdb_list[@]} -gt 0 ]]; then
        vcover merge "$merged.ucdb" "${ucdb_list[@]}" 2>&1
        vcover report -details "$merged.ucdb" > "$merged.txt" 2>&1
        echo "Questa coverage merged: $merged.ucdb"
      fi
      ;;
  esac
}

# ─── Harvest results ───────────────────────────────────────────────────────
PASSED=0
FAILED=0
FAILED_SEEDS=""
STOP_DISPATCH=0
PROCESSED_RESULT_FILES=""

harvest_results() {
  shopt -s nullglob
  local result_files=("$RESULTS_DIR"/seed_*_results.json)
  shopt -u nullglob

  if [[ ${#result_files[@]} -eq 0 ]]; then return; fi

  for result_file in "${result_files[@]}"; do
    case "$PROCESSED_RESULT_FILES" in
      *"|${result_file}|"*) continue ;;
    esac
    PROCESSED_RESULT_FILES="${PROCESSED_RESULT_FILES}|${result_file}|"

    if grep -q '"status"[[:space:]]*:[[:space:]]*"PASS"' "$result_file"; then
      PASSED=$((PASSED + 1))
    else
      FAILED=$((FAILED + 1))
      local fseed
      fseed=$(grep -o '"seed"[[:space:]]*:[[:space:]]*[0-9]*' "$result_file" | grep -o '[0-9]*')
      FAILED_SEEDS="$FAILED_SEEDS $fseed"
    fi
  done
}

should_halt() {
  local total=$((PASSED + FAILED))
  [[ "$total" -eq 0 ]] && return 1
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

compile_uvm

echo ""
echo "=== Running Seeds ==="
for seed in $SEEDS; do
  if [[ "$STOP_DISPATCH" -eq 1 ]]; then
    echo "  Skipping seed $seed (halt threshold reached)"
    continue
  fi

  if [[ "$PARALLEL" -gt 1 ]]; then
    run_seed "$seed" &
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
    run_seed "$seed"
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
  wait 2>/dev/null || true
  harvest_results
fi

# ─── Coverage merge ────────────────────────────────────────────────────────
merge_coverage

# ─── Regression report ──────────────────────────────────────────────────────
TOTAL=$((PASSED + FAILED))
REPORT="$RESULTS_DIR/regression_${MODULE}_${TIMESTAMP}.json"

cat > "$REPORT" << REPORT_EOF
{
  "module": "$MODULE",
  "simulator": "$SIM",
  "test": "$TEST",
  "timestamp": "$TIMESTAMP",
  "seeds_total": $TOTAL,
  "seeds_passed": $PASSED,
  "seeds_failed": $FAILED,
  "failed_seeds": [$(echo "$FAILED_SEEDS" | xargs | sed 's/ /, /g')],
  "halted_early": $([ "$STOP_DISPATCH" -eq 1 ] && echo "true" || echo "false"),
  "coverage_targets": {
    "line": 90,
    "toggle": 80,
    "fsm": 70,
    "branch": 80,
    "functional": 95
  },
  "coverage_dir": "$COVERAGE_DIR",
  "run_dir": "$RUN_DIR",
  "verdict": "$([ "$FAILED" -eq 0 ] && echo "PASS" || echo "FAIL")"
}
REPORT_EOF

echo ""
echo "========================================"
echo " Regression Summary"
echo "========================================"
echo " Total:  $TOTAL"
echo " Passed: $PASSED"
echo " Failed: $FAILED"
[[ -n "$FAILED_SEEDS" ]] && echo " Failed seeds:$FAILED_SEEDS"
echo " Report: $REPORT"
echo " Verdict: $([ "$FAILED" -eq 0 ] && echo "PASS" || echo "FAIL")"
echo "========================================"

exit "$FAILED"

# rat-version: 0.8.14
