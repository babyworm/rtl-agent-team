#!/usr/bin/env bash
# Coverage Merge Script
# Merges per-seed coverage data into a single report.
# Usage: bash merge_coverage.sh [--format verilator|lcov] [--output coverage/merged.info]

set -euo pipefail

FORMAT="${FORMAT:-verilator}"
OUTPUT="${OUTPUT:-coverage/merged.info}"
COVERAGE_DIR="coverage"
HTML_DIR="coverage_html"

mkdir -p "$COVERAGE_DIR" "$HTML_DIR"

case "$FORMAT" in
  verilator)
    echo "Merging Verilator coverage data..."
    # Find all coverage.dat files from regression seeds
    DAT_FILES=$(find regression/ -name "coverage.dat" 2>/dev/null | sort)
    if [[ -z "$DAT_FILES" ]]; then
      echo "No coverage.dat files found in regression/"
      exit 1
    fi

    # Merge into single info file
    verilator_coverage --write-info "$OUTPUT" $DAT_FILES
    echo "Merged $(echo "$DAT_FILES" | wc -l) coverage files → $OUTPUT"

    # Annotate source
    mkdir -p "${COVERAGE_DIR}/annotated"
    verilator_coverage --annotate "${COVERAGE_DIR}/annotated/" $DAT_FILES

    # Generate HTML
    genhtml "$OUTPUT" -o "$HTML_DIR" --title "Regression Coverage"
    echo "HTML report: $HTML_DIR/index.html"
    ;;

  lcov)
    echo "Merging lcov coverage data..."
    INFO_FILES=$(find regression/ -name "*.info" 2>/dev/null | sort)
    if [[ -z "$INFO_FILES" ]]; then
      echo "No .info files found in regression/"
      exit 1
    fi

    # Build lcov merge command
    MERGE_CMD="lcov"
    for f in $INFO_FILES; do
      MERGE_CMD="$MERGE_CMD --add-tracefile $f"
    done
    MERGE_CMD="$MERGE_CMD --output-file $OUTPUT"
    eval "$MERGE_CMD"

    echo "Merged $(echo "$INFO_FILES" | wc -l) coverage files → $OUTPUT"

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
