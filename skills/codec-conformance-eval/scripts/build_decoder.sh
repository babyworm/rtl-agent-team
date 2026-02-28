#!/usr/bin/env bash
# build_decoder.sh — Build ref_model C source into decoder binary
# Usage: build_decoder.sh <src_dir> <output_binary> [extra_cflags...]
#
# Builds C11 decoder from source directory using gcc.
# Note: Shares build logic with codec-rd-eval/scripts/build_encoder.sh.
# Both kept separate for standalone skill execution.
# If a Makefile exists in src_dir, uses make. Otherwise compiles all *.c files.

set -euo pipefail

usage() {
    echo "Usage: $0 <src_dir> <output_binary> [extra_cflags...]"
    echo ""
    echo "Arguments:"
    echo "  src_dir        Directory containing C source files"
    echo "  output_binary  Path for the output decoder binary"
    echo "  extra_cflags   Additional compiler flags (optional)"
    echo ""
    echo "Examples:"
    echo "  $0 ref_model/src ./build/decoder"
    echo "  $0 ref_model/src ./build/decoder -DDECODER_ONLY"
    exit "${1:-1}"
}

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    usage 0
fi

if [[ $# -lt 2 ]]; then
    echo "ERROR: src_dir and output_binary are required"
    usage
fi

SRC_DIR="$1"
OUTPUT_BINARY="$2"
shift 2
EXTRA_CFLAGS=("$@")

# Validate source directory
if [[ ! -d "$SRC_DIR" ]]; then
    echo "ERROR: Source directory does not exist: $SRC_DIR"
    exit 1
fi

# Check for C source files (flat directory only — subdirectories require a Makefile)
C_FILES=("$SRC_DIR"/*.c)
if [[ ! -e "${C_FILES[0]}" ]]; then
    echo "ERROR: No .c files found in $SRC_DIR"
    exit 1
fi

# Create output directory
OUTPUT_DIR="$(dirname "$OUTPUT_BINARY")"
mkdir -p "$OUTPUT_DIR"

# Compiler settings (C11 per CLAUDE.md conventions)
CC="${CC:-gcc}"
CFLAGS="-std=c11 -O2 -Wall -Wextra"
LDFLAGS="-lm"

# Check for include directory
INCLUDE_DIR=""
if [[ -d "${SRC_DIR}/../include" ]]; then
    INCLUDE_DIR="-I${SRC_DIR}/../include"
elif [[ -d "${SRC_DIR}/include" ]]; then
    INCLUDE_DIR="-I${SRC_DIR}/include"
fi

echo "=== codec-conformance-eval: Building decoder ==="
echo "Source:  $SRC_DIR"
echo "Output:  $OUTPUT_BINARY"
echo "CC:      $CC"
echo "CFLAGS:  $CFLAGS ${EXTRA_CFLAGS[*]:-} $INCLUDE_DIR"

# Build strategy: Makefile if available, otherwise direct gcc
if [[ -f "$SRC_DIR/Makefile" || -f "$SRC_DIR/makefile" ]]; then
    echo "Strategy: make (Makefile found)"
    make -C "$SRC_DIR" \
        CC="$CC" \
        CFLAGS="$CFLAGS ${EXTRA_CFLAGS[*]:-} $INCLUDE_DIR" \
        OUTPUT="$OUTPUT_BINARY" \
        -j"$(nproc 2>/dev/null || echo 4)"
else
    echo "Strategy: direct gcc compilation"
    echo "Files:   ${C_FILES[*]}"

    # shellcheck disable=SC2086
    $CC $CFLAGS ${EXTRA_CFLAGS[@]+"${EXTRA_CFLAGS[@]}"} ${INCLUDE_DIR:+"$INCLUDE_DIR"} \
        "${C_FILES[@]}" \
        -o "$OUTPUT_BINARY" \
        $LDFLAGS
fi

# Verify output
if [[ ! -x "$OUTPUT_BINARY" ]]; then
    echo "ERROR: Build succeeded but output binary is not executable: $OUTPUT_BINARY"
    exit 1
fi

echo "=== Build successful: $OUTPUT_BINARY ==="
echo "Size: $(du -h "$OUTPUT_BINARY" | cut -f1)"
