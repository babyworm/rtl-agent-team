#!/usr/bin/env bash
# Multi-Seed Regression Runner
# Usage: bash run_regression.sh [--seeds "1 42 123 1337 65536"] [--sim icarus|verilator] [--parallel N]
#
# Runs cocotb test suite with multiple seeds, captures results per seed,
# and generates a merged regression report.

set -euo pipefail

# Defaults
SEEDS="${SEEDS:-1 42 123 1337 65536}"
SIM="${SIM:-icarus}"
PARALLEL="${PARALLEL:-1}"
TB_DIR="${TB_DIR:-sim}"
RESULTS_DIR="regression"
COVERAGE_DIR="coverage"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MAX_FAIL_RATE=5  # Halt if failure rate exceeds this %

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --seeds)   SEEDS="$2"; shift 2 ;;
    --sim)     SIM="$2"; shift 2 ;;
    --parallel) PARALLEL="$2"; shift 2 ;;
    *)         echo "Unknown option: $1"; exit 2 ;;
  esac
done

mkdir -p "$RESULTS_DIR" "$COVERAGE_DIR"

echo "=== Regression Run ==="
echo "Seeds: $SEEDS"
echo "Simulator: $SIM"
echo "Parallel: $PARALLEL"
echo "Timestamp: $TIMESTAMP"
echo ""

TOTAL=0
PASSED=0
FAILED=0
FAILED_SEEDS=""

run_seed() {
  local seed=$1
  local result_file="$RESULTS_DIR/seed_${seed}_results.json"
  local log_file="$RESULTS_DIR/seed_${seed}.log"

  echo "[seed=$seed] Starting..."

  if make -C "$TB_DIR" SIM="$SIM" SEED="$seed" COVERAGE=1 \
       > "$log_file" 2>&1; then
    echo "[seed=$seed] PASS"
    echo "{\"seed\": $seed, \"status\": \"PASS\", \"timestamp\": \"$TIMESTAMP\"}" \
      > "$result_file"
    return 0
  else
    echo "[seed=$seed] FAIL — see $log_file"
    echo "{\"seed\": $seed, \"status\": \"FAIL\", \"timestamp\": \"$TIMESTAMP\", \"log\": \"$log_file\"}" \
      > "$result_file"
    # Capture waveform if available
    if ls "$TB_DIR"/*.vcd 2>/dev/null | head -1 > /dev/null; then
      cp "$TB_DIR"/*.vcd "$RESULTS_DIR/seed_${seed}_waveform.vcd" 2>/dev/null || true
    fi
    return 1
  fi
}

# Run seeds (sequential or parallel)
for seed in $SEEDS; do
  ((TOTAL++))

  if [[ "$PARALLEL" -gt 1 ]]; then
    run_seed "$seed" &
    # Limit parallel jobs
    while [[ $(jobs -r | wc -l) -ge $PARALLEL ]]; do
      wait -n 2>/dev/null || true
    done
  else
    if run_seed "$seed"; then
      ((PASSED++))
    else
      ((FAILED++))
      FAILED_SEEDS="$FAILED_SEEDS $seed"
    fi
  fi

  # Early termination check
  if [[ $TOTAL -gt 0 && $FAILED -gt 0 ]]; then
    FAIL_RATE=$((FAILED * 100 / TOTAL))
    if [[ $FAIL_RATE -gt $MAX_FAIL_RATE ]]; then
      echo ""
      echo "HALT: Failure rate ${FAIL_RATE}% exceeds threshold ${MAX_FAIL_RATE}%"
      break
    fi
  fi
done

# Wait for parallel jobs
if [[ "$PARALLEL" -gt 1 ]]; then
  wait
  # Recount from result files
  PASSED=$(grep -l '"PASS"' "$RESULTS_DIR"/seed_*_results.json 2>/dev/null | wc -l)
  FAILED=$(grep -l '"FAIL"' "$RESULTS_DIR"/seed_*_results.json 2>/dev/null | wc -l)
  FAILED_SEEDS=$(grep -l '"FAIL"' "$RESULTS_DIR"/seed_*_results.json 2>/dev/null \
    | xargs -I{} grep -o '"seed": [0-9]*' {} | awk '{print $2}' | tr '\n' ' ')
fi

# Summary report
REPORT_FILE="$RESULTS_DIR/results_${TIMESTAMP}.json"
cat > "$REPORT_FILE" << EOF
{
  "timestamp": "$TIMESTAMP",
  "simulator": "$SIM",
  "seeds_total": $TOTAL,
  "passed": $PASSED,
  "failed": $FAILED,
  "pass_rate": "$(echo "scale=1; $PASSED * 100 / $TOTAL" | bc)%",
  "failed_seeds": [$(echo "$FAILED_SEEDS" | xargs | tr ' ' ',')],
  "results_dir": "$RESULTS_DIR"
}
EOF

echo ""
echo "=== Regression Summary ==="
echo "Seeds: $TOTAL | Passed: $PASSED | Failed: $FAILED"
echo "Pass rate: $(echo "scale=1; $PASSED * 100 / $TOTAL" | bc)%"
[[ -n "$FAILED_SEEDS" ]] && echo "Failed seeds:$FAILED_SEEDS"
echo "Report: $REPORT_FILE"

# Exit with failure if any seed failed
[[ $FAILED -eq 0 ]] && exit 0 || exit 1
