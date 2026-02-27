/**
 * RTL Agent Team - Reference Model Template
 * Domain: Video Codec (H.264/H.265)
 *
 * Usage: Copy this template and implement the algorithm-specific functions.
 *        The reference model must produce bit-exact output matching JM/HM.
 *
 * Build: gcc -std=c11 -Wall -Wextra -Werror -O2 -o ref_model ref_model.c
 * Test:  ./ref_model --selftest
 * Conformance: ./ref_model --compare jm_output.bin model_output.bin
 */

#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>

/* ============================================================================
 * Type Definitions
 * ============================================================================ */

typedef uint8_t pixel_t;    /* 8-bit pixel value */
typedef int16_t coeff_t;    /* Transform coefficient */
typedef int16_t qcoeff_t;   /* Quantized coefficient */

typedef struct {
    pixel_t data[4][4];
} block4x4_t;

typedef struct {
    coeff_t data[4][4];
} coeff_block4x4_t;

/* ============================================================================
 * External Memory Access Abstraction (for bandwidth tracking)
 * ============================================================================ */

static uint64_t g_ext_mem_read_bytes = 0;
static uint64_t g_ext_mem_write_bytes = 0;

void ext_mem_read(uint32_t addr, void *buf, uint32_t size) {
    /* TODO: Hook to actual memory model or stub */
    (void)addr; (void)buf; (void)size;
    g_ext_mem_read_bytes += size;
}

void ext_mem_write(uint32_t addr, const void *buf, uint32_t size) {
    /* TODO: Hook to actual memory model or stub */
    (void)addr; (void)buf; (void)size;
    g_ext_mem_write_bytes += size;
}

/* ============================================================================
 * Algorithm Implementation (TODO: Implement per spec)
 * ============================================================================ */

/**
 * TODO: Implement the core algorithm here.
 *
 * Example for intra prediction:
 *   void intra_predict_4x4(
 *       int32_t mode,
 *       const pixel_t *above,     // 8 pixels above (+ above-left)
 *       const pixel_t *left,      // 4 pixels left
 *       block4x4_t *predicted
 *   );
 *
 * Requirements:
 *   - Must be bit-exact with JM/HM reference software
 *   - All intermediate calculations must use correct fixed-point precision
 *   - Edge cases (unavailable neighbors) must follow spec exactly
 *   - Use fixed-width integer types only (uint8_t, int16_t, etc.)
 *   - No floating-point arithmetic
 */

/* ============================================================================
 * Test Vector I/O
 * ============================================================================ */

static bool load_vectors(const char *path, block4x4_t *blocks, uint32_t max_count,
                         uint32_t *out_count) {
    FILE *f = fopen(path, "rb");
    if (!f) return false;

    uint32_t count = 0;
    while (count < max_count &&
           fread(&blocks[count], sizeof(block4x4_t), 1, f) == 1) {
        count++;
    }
    fclose(f);

    *out_count = count;
    return count > 0;
}

static bool save_vectors(const char *path, const block4x4_t *blocks, uint32_t count) {
    FILE *f = fopen(path, "wb");
    if (!f) return false;

    uint32_t written = (uint32_t)fwrite(blocks, sizeof(block4x4_t), count, f);
    fclose(f);

    return written == count;
}

/* ============================================================================
 * Self-Test
 * ============================================================================ */

static bool run_selftest(void) {
    printf("Running self-test...\n");

    /* TODO: Add self-test vectors here
     * These should be hand-verified against the standard
     *
     * Example:
     *   block4x4_t input = { .data = { ... } };
     *   block4x4_t expected = { .data = { ... } };
     *   block4x4_t result;
     *   intra_predict_4x4(MODE_DC, above, left, &result);
     *   assert(memcmp(&result, &expected, sizeof(block4x4_t)) == 0);
     */

    printf("Self-test PASSED\n");
    return true;
}

/* ============================================================================
 * Conformance Check (vs JM/HM output)
 * ============================================================================ */

#define MAX_VECTORS 65536

static int32_t run_conformance(const char *reference_path, const char *model_path) {
    block4x4_t *reference = (block4x4_t *)malloc(MAX_VECTORS * sizeof(block4x4_t));
    block4x4_t *model = (block4x4_t *)malloc(MAX_VECTORS * sizeof(block4x4_t));
    if (!reference || !model) {
        fprintf(stderr, "ERROR: Memory allocation failed\n");
        free(reference);
        free(model);
        return 1;
    }

    uint32_t ref_count = 0, model_count = 0;

    if (!load_vectors(reference_path, reference, MAX_VECTORS, &ref_count)) {
        fprintf(stderr, "ERROR: Cannot load reference vectors: %s\n", reference_path);
        free(reference); free(model);
        return 1;
    }
    if (!load_vectors(model_path, model, MAX_VECTORS, &model_count)) {
        fprintf(stderr, "ERROR: Cannot load model vectors: %s\n", model_path);
        free(reference); free(model);
        return 1;
    }

    if (ref_count != model_count) {
        fprintf(stderr, "ERROR: Vector count mismatch: ref=%u, model=%u\n",
                ref_count, model_count);
        free(reference); free(model);
        return 1;
    }

    int32_t mismatches = 0;
    for (uint32_t i = 0; i < ref_count; i++) {
        if (memcmp(&reference[i], &model[i], sizeof(block4x4_t)) != 0) {
            mismatches++;
            if (mismatches <= 10) {
                fprintf(stderr, "MISMATCH at vector %u\n", i);
                for (int32_t r = 0; r < 4; r++) {
                    for (int32_t c = 0; c < 4; c++) {
                        if (reference[i].data[r][c] != model[i].data[r][c]) {
                            fprintf(stderr, "  [%d][%d]: ref=%d, model=%d\n",
                                    r, c, reference[i].data[r][c], model[i].data[r][c]);
                        }
                    }
                }
            }
        }
    }

    printf("Conformance: %u vectors, %d mismatches (%.2f%% match)\n",
           ref_count, mismatches,
           100.0 * (double)(ref_count - (uint32_t)mismatches) / (double)ref_count);

    free(reference);
    free(model);
    return mismatches > 0 ? 1 : 0;
}

/* ============================================================================
 * Main
 * ============================================================================ */

int main(int argc, char *argv[]) {
    if (argc < 2) {
        printf("Usage:\n");
        printf("  %s --selftest              Run self-test\n", argv[0]);
        printf("  %s --compare <ref> <model>  Compare with reference\n", argv[0]);
        printf("  %s --generate <in> <out>    Generate vectors\n", argv[0]);
        return 1;
    }

    if (strcmp(argv[1], "--selftest") == 0) {
        return run_selftest() ? 0 : 1;
    }
    else if (strcmp(argv[1], "--compare") == 0 && argc >= 4) {
        return run_conformance(argv[2], argv[3]);
    }
    else {
        fprintf(stderr, "Unknown command: %s\n", argv[1]);
        return 1;
    }
}
