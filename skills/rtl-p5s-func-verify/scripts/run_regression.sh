#!/usr/bin/env bash
# Multi-Seed Regression Runner
# Usage:
#   bash run_regression.sh [--seeds "1 42 123 1337 65536"] [--sim icarus|verilator]
#                          [--parallel N] [--mode local|aws-batch]
#
# Local-first policy:
#   - Default mode is local.
#   - AWS Batch mode is opt-in and should only be selected when explicitly requested.
#   - AWS execution requires explicit gate: RTL_ALLOW_AWS=1 and RTL_AWS_BATCH_RUNNER.
#
# Runs cocotb test suite with multiple seeds, captures results per seed,
# and generates a merged regression report.

set -euo pipefail

# Defaults
SEEDS="${SEEDS:-1 42 123 1337 65536}"
SIM="${SIM:-icarus}"
MODE="${MODE:-local}"
PARALLEL="${PARALLEL:-}"
TB_DIR="${TB_DIR:-sim}"
MODULE="${MODULE:-top}"
RESULTS_DIR="${RESULTS_DIR:-sim/regression}"
COVERAGE_DIR="${COVERAGE_DIR:-sim/coverage}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MAX_FAIL_RATE="${MAX_FAIL_RATE:-5}"  # Halt if failure rate exceeds this %
USER_SET_PARALLEL=0

usage() {
  cat <<'EOF'
Usage: run_regression.sh [OPTIONS]

Options:
  --seeds "1 42 123 ..."   Seed list (space-separated)
  --sim <name>             Simulator (default: icarus)
  --parallel <N>           Concurrent jobs (default: max(1, nproc-2))
  --mode <local|aws-batch> Execution mode (default: local)
  --tb-dir <path>          Testbench directory passed to make -C (default: sim)
  --module <name>          Module label for output metadata (default: top)
  --max-fail-rate <N>      Early-stop threshold in percent (default: 5)
  RTL_ALLOW_AWS=1          Required env gate for --mode aws-batch
  RTL_AWS_BATCH_RUNNER     Executable path for AWS submission handler
  -h, --help               Show this help
EOF
}

detect_nproc() {
  if command -v nproc >/dev/null 2>&1; then
    nproc
    return
  fi
  if command -v getconf >/dev/null 2>&1; then
    getconf _NPROCESSORS_ONLN 2>/dev/null || true
    return
  fi
  echo "4"
}

default_parallel() {
  local cores
  cores=$(detect_nproc)
  if ! [[ "$cores" =~ ^[0-9]+$ ]]; then
    cores=4
  fi
  local value=$((cores - 2))
  if [[ "$value" -lt 1 ]]; then
    value=1
  fi
  echo "$value"
}

calculate_pass_rate() {
  local passed="$1"
  local total="$2"
  awk -v p="$passed" -v t="$total" 'BEGIN { if (t <= 0) { printf "0.0"; } else { printf "%.1f", (p * 100.0) / t; } }'
}

count_active_jobs() {
  jobs -pr | wc -l | tr -d ' '
}

harvest_new_results() {
  shopt -s nullglob
  local result_files=("$RESULTS_DIR"/seed_*_results.json)
  shopt -u nullglob

  if [[ ${#result_files[@]} -eq 0 ]]; then
    return
  fi

  local result_file
  local seed_value
  for result_file in "${result_files[@]}"; do
    case "$PROCESSED_RESULT_FILES" in
      *"|${result_file}|"*) continue ;;
    esac
    PROCESSED_RESULT_FILES="${PROCESSED_RESULT_FILES}|${result_file}|"

    if grep -q '"status"[[:space:]]*:[[:space:]]*"PASS"' "$result_file"; then
      PASSED=$((PASSED + 1))
    elif grep -q '"status"[[:space:]]*:[[:space:]]*"FAIL"' "$result_file"; then
      FAILED=$((FAILED + 1))
      seed_value=$(sed -n 's/.*"seed"[[:space:]]*:[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$result_file" | head -n 1)
      if [[ -n "$seed_value" ]]; then
        FAILED_SEEDS="$FAILED_SEEDS $seed_value"
      fi
    fi
  done
}

terminate_active_jobs() {
  local active_pids
  active_pids=$(jobs -pr)
  if [[ -z "$active_pids" ]]; then
    return
  fi

  echo "Stopping active jobs due to early termination threshold..."
  # shellcheck disable=SC2086
  kill $active_pids 2>/dev/null || true
}

should_halt_by_fail_rate() {
  local completed=$((PASSED + FAILED))
  if [[ "$completed" -le 0 || "$FAILED" -le 0 ]]; then
    return 1
  fi
  local fail_rate=$((FAILED * 100 / completed))
  if [[ "$fail_rate" -gt "$MAX_FAIL_RATE" ]]; then
    echo ""
    echo "HALT: Failure rate ${fail_rate}% exceeds threshold ${MAX_FAIL_RATE}%"
    return 0
  fi
  return 1
}

if [[ $# -eq 0 ]]; then
  :
fi

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --seeds)
      SEEDS="$2"; shift 2 ;;
    --sim)
      SIM="$2"; shift 2 ;;
    --parallel)
      PARALLEL="$2"; USER_SET_PARALLEL=1; shift 2 ;;
    --mode)
      MODE="$2"; shift 2 ;;
    --tb-dir)
      TB_DIR="$2"; shift 2 ;;
    --module)
      MODULE="$2"; shift 2 ;;
    --max-fail-rate)
      MAX_FAIL_RATE="$2"; shift 2 ;;
    -h|--help)
      usage
      exit 0 ;;
    *)
      echo "Unknown option: $1"
      exit 2 ;;
  esac
done

if [[ "$MODE" != "local" && "$MODE" != "aws-batch" ]]; then
  echo "ERROR: Unsupported mode: $MODE (supported: local, aws-batch)"
  exit 2
fi

if ! [[ "$MAX_FAIL_RATE" =~ ^[0-9]+$ ]]; then
  echo "ERROR: --max-fail-rate must be an integer: $MAX_FAIL_RATE"
  exit 2
fi

if [[ -z "$PARALLEL" ]]; then
  PARALLEL=$(default_parallel)
fi

if ! [[ "$PARALLEL" =~ ^[0-9]+$ ]] || [[ "$PARALLEL" -lt 1 ]]; then
  echo "ERROR: --parallel must be >= 1: $PARALLEL"
  exit 2
fi

mkdir -p "$RESULTS_DIR" "$COVERAGE_DIR"

if [[ "$MODE" == "aws-batch" ]]; then
  if [[ "${RTL_ALLOW_AWS:-0}" != "1" ]]; then
    echo "ERROR: aws-batch mode requires explicit opt-in: set RTL_ALLOW_AWS=1."
    echo "If AWS was not explicitly requested, use --mode local (default)."
    exit 2
  fi

  if [[ -z "${RTL_AWS_BATCH_RUNNER:-}" ]]; then
    echo "ERROR: aws-batch mode requested but no AWS runner configured."
    echo "Set RTL_AWS_BATCH_RUNNER to an executable handler path."
    exit 2
  fi

  if [[ ! -x "$RTL_AWS_BATCH_RUNNER" ]]; then
    echo "ERROR: RTL_AWS_BATCH_RUNNER is not executable: $RTL_AWS_BATCH_RUNNER"
    exit 2
  fi

  exec "$RTL_AWS_BATCH_RUNNER" \
    --seeds "$SEEDS" \
    --sim "$SIM" \
    --parallel "$PARALLEL" \
    --tb-dir "$TB_DIR" \
    --module "$MODULE" \
    --results-dir "$RESULTS_DIR" \
    --coverage-dir "$COVERAGE_DIR" \
    --max-fail-rate "$MAX_FAIL_RATE"
fi

AUTO_PARALLEL_MSG=""
if [[ "$USER_SET_PARALLEL" -eq 0 ]]; then
  AUTO_PARALLEL_MSG=" (auto: nproc-2)"
fi

echo "=== Regression Run ==="
echo "Mode: $MODE"
echo "Module: $MODULE"
echo "Seeds: $SEEDS"
echo "Simulator: $SIM"
echo "Parallel: $PARALLEL$AUTO_PARALLEL_MSG"
echo "Timestamp: $TIMESTAMP"
echo ""

TOTAL=0
PASSED=0
FAILED=0
FAILED_SEEDS=""
STOP_DISPATCH=0
PROCESSED_RESULT_FILES=""

run_seed() {
  local seed="$1"
  local result_file="$RESULTS_DIR/seed_${seed}_results.json"
  local log_file="$RESULTS_DIR/seed_${seed}.log"
  local sim_build_dir="$RESULTS_DIR/build/${MODULE}/seed_${seed}"
  mkdir -p "$sim_build_dir"

  echo "[seed=$seed] Starting..."

  if make -C "$TB_DIR" sim SIM="$SIM" RANDOM_SEED="$seed" COVERAGE=1 SIM_BUILD="$sim_build_dir" \
       > "$log_file" 2>&1; then
    echo "[seed=$seed] PASS"
    cat > "$result_file" <<EOF
{"seed": $seed, "module": "$MODULE", "status": "PASS", "runner": "local", "mode": "$MODE", "timestamp": "$TIMESTAMP"}
EOF
    return 0
  else
    echo "[seed=$seed] FAIL — see $log_file"
    cat > "$result_file" <<EOF
{"seed": $seed, "module": "$MODULE", "status": "FAIL", "runner": "local", "mode": "$MODE", "timestamp": "$TIMESTAMP", "log": "$log_file"}
EOF
    # Capture waveform if available
    if ls "$TB_DIR"/*.vcd >/dev/null 2>&1; then
      cp "$TB_DIR"/*.vcd "$RESULTS_DIR/seed_${seed}_waveform.vcd" 2>/dev/null || true
    fi
    return 1
  fi
}

# Run seeds (sequential or parallel)
for seed in $SEEDS; do
  TOTAL=$((TOTAL + 1))

  if [[ "$PARALLEL" -gt 1 ]]; then
    run_seed "$seed" &
    while [[ "$(count_active_jobs)" -ge "$PARALLEL" ]]; do
      sleep 0.2
      harvest_new_results
      if should_halt_by_fail_rate; then
        STOP_DISPATCH=1
        terminate_active_jobs
        break
      fi
    done
  else
    if run_seed "$seed"; then
      PASSED=$((PASSED + 1))
    else
      FAILED=$((FAILED + 1))
      FAILED_SEEDS="$FAILED_SEEDS $seed"
    fi
    if should_halt_by_fail_rate; then
      STOP_DISPATCH=1
      break
    fi
  fi

  if [[ "$STOP_DISPATCH" -eq 1 ]]; then
    break
  fi
done

# Wait for remaining parallel jobs and recount
if [[ "$PARALLEL" -gt 1 ]]; then
  while [ "$(count_active_jobs)" -gt 0 ]; do
    sleep 0.2
    harvest_new_results
    if should_halt_by_fail_rate; then
      terminate_active_jobs
      break
    fi
  done
  wait 2>/dev/null || true
  harvest_new_results
fi

COMPLETED=$((PASSED + FAILED))
if [[ "$COMPLETED" -lt "$TOTAL" ]]; then
  TOTAL="$COMPLETED"
fi

PASS_RATE=$(calculate_pass_rate "$PASSED" "$TOTAL")

# Summary report
REPORT_FILE="$RESULTS_DIR/results_${TIMESTAMP}.json"
cat > "$REPORT_FILE" <<EOF
{
  "timestamp": "$TIMESTAMP",
  "mode": "$MODE",
  "module": "$MODULE",
  "simulator": "$SIM",
  "seeds_total": $TOTAL,
  "passed": $PASSED,
  "failed": $FAILED,
  "pass_rate": "${PASS_RATE}%",
  "failed_seeds": [$(echo "$FAILED_SEEDS" | xargs | tr ' ' ',')],
  "results_dir": "$RESULTS_DIR"
}
EOF

echo ""
echo "=== Regression Summary ==="
echo "Seeds: $TOTAL | Passed: $PASSED | Failed: $FAILED"
echo "Pass rate: ${PASS_RATE}%"
[[ -n "$FAILED_SEEDS" ]] && echo "Failed seeds:$FAILED_SEEDS"
echo "Report: $REPORT_FILE"

# Exit with failure if any seed failed
if [[ "$FAILED" -eq 0 ]]; then
  exit 0
fi
exit 1
