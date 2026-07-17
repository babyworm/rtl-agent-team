#!/usr/bin/env bash
# Coverage Merge Script
# Merges per-seed coverage data into a single report.
# Usage: bash merge_coverage.sh [--format verilator|lcov] [--output sim/coverage/merged.info]

set -euo pipefail

FORMAT="${FORMAT:-verilator}"
OUTPUT="${OUTPUT:-sim/coverage/merged.info}"
COVERAGE_DIR="sim/coverage"
HTML_DIR="sim/coverage/html"

mkdir -p "$COVERAGE_DIR" "$HTML_DIR"

case "$FORMAT" in
  verilator)
    echo "Merging Verilator coverage data..."
    # Find all coverage.dat files from regression seeds. Collected into a bash
    # array and passed as argv — file names are single arguments, never
    # re-parsed by the shell (immune to metacharacters in file names).
    DAT_FILES=()
    while IFS= read -r f; do
      DAT_FILES+=("$f")
    done < <(find sim/regression/ -name "coverage.dat" 2>/dev/null | sort)
    if [[ ${#DAT_FILES[@]} -eq 0 ]]; then
      echo "No coverage.dat files found in sim/regression/"
      exit 1
    fi

    # Merge into single info file
    verilator_coverage --write-info "$OUTPUT" "${DAT_FILES[@]}"
    echo "Merged ${#DAT_FILES[@]} coverage files → $OUTPUT"

    # Annotate source
    mkdir -p "${COVERAGE_DIR}/annotated"
    verilator_coverage --annotate "${COVERAGE_DIR}/annotated/" "${DAT_FILES[@]}"

    # Generate HTML
    genhtml "$OUTPUT" -o "$HTML_DIR" --title "Regression Coverage"
    echo "HTML report: $HTML_DIR/index.html"
    ;;

  lcov)
    echo "Merging lcov coverage data..."
    INFO_FILES=()
    while IFS= read -r f; do
      INFO_FILES+=("$f")
    done < <(find sim/regression/ -name "*.info" 2>/dev/null | sort)
    if [[ ${#INFO_FILES[@]} -eq 0 ]]; then
      echo "No .info files found in sim/regression/"
      exit 1
    fi

    # Build lcov merge command as an argv array and invoke directly (no eval):
    # find results are passed as single arguments, so a hostile .info file
    # name cannot inject shell commands.
    MERGE_CMD=(lcov)
    for f in "${INFO_FILES[@]}"; do
      MERGE_CMD+=(--add-tracefile "$f")
    done
    MERGE_CMD+=(--output-file "$OUTPUT")
    "${MERGE_CMD[@]}"

    echo "Merged ${#INFO_FILES[@]} coverage files → $OUTPUT"

    # Generate HTML
    genhtml "$OUTPUT" -o "$HTML_DIR" --title "Regression Coverage"
    echo "HTML report: $HTML_DIR/index.html"
    ;;

  *)
    echo "Unknown format: $FORMAT (supported: verilator, lcov)"
    exit 2
    ;;
esac

# Print summary
echo ""
echo "=== Coverage Summary ==="
if command -v lcov &> /dev/null && [[ -f "$OUTPUT" ]]; then
  lcov --summary "$OUTPUT" 2>&1 | grep -E "lines|functions|branches"
fi
