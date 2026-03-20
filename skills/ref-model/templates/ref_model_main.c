/**
 * {{MODULE_NAME}}_ref.c — C Reference Model (Functional, No Clock/Reset)
 *
 * Purpose: Golden reference for bitexact comparison against RTL.
 * Style:   C11, no clock/reset, pure functional transforms.
 *
 * Usage:
 *   Standalone: ./build/{{MODULE_NAME}}_ref --self-test
 *   DPI-C:      Compiled as .so, called from SV testbench via dpi_wrapper
 *
 * Convention:
 *   - All functions are pure (no global state unless explicitly documented)
 *   - External memory access via abstract interface (ref_mem_read/ref_mem_write)
 *   - Fixed-point arithmetic matches RTL bit-widths exactly
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include "{{MODULE_NAME}}_ref.h"

/* ═══ Core Algorithm ═══════════════════════════════════════════════════════ */

/**
 * Main processing function — implements the core algorithm.
 * Must produce bitexact output matching RTL for all inputs.
 *
 * @param ctx   Model context (state, configuration)
 * @param input Input data structure
 * @param output Output data structure (filled by this function)
 * @return 0 on success, non-zero on error
 */
int {{MODULE_NAME}}_process(
    {{MODULE_NAME}}_ctx_t *ctx,
    const {{MODULE_NAME}}_input_t *input,
    {{MODULE_NAME}}_output_t *output)
{
    (void)ctx;
    (void)input;
    (void)output;

    /* TODO: Implement core algorithm here
     *
     * Guidelines:
     * - Match RTL datapath widths exactly (use uint32_t for 32-bit, etc.)
     * - Use masking for overflow: result & ((1U << WIDTH) - 1)
     * - Document any rounding/truncation to match RTL behavior
     * - No floating point — use fixed-point matching RTL
     */

    return 0;
}

/* ═══ Initialization / Cleanup ═════════════════════════════════════════════ */

int {{MODULE_NAME}}_init({{MODULE_NAME}}_ctx_t *ctx)
{
    memset(ctx, 0, sizeof(*ctx));
    /* TODO: Initialize parameters, lookup tables, etc. */
    return 0;
}

void {{MODULE_NAME}}_cleanup({{MODULE_NAME}}_ctx_t *ctx)
{
    (void)ctx;
    /* TODO: Free allocated resources if any */
}

/* ═══ Self-Test ════════════════════════════════════════════════════════════ */

static int self_test(void)
{
    {{MODULE_NAME}}_ctx_t ctx;
    {{MODULE_NAME}}_input_t input;
    {{MODULE_NAME}}_output_t output;
    int pass = 0, fail = 0;

    {{MODULE_NAME}}_init(&ctx);

    /* TODO: Add test vectors derived from spec
     *
     * Example:
     *   memset(&input, 0, sizeof(input));
     *   input.data = 0xDEADBEEF;
     *   {{MODULE_NAME}}_process(&ctx, &input, &output);
     *   if (output.result == EXPECTED_VALUE) { pass++; }
     *   else { fail++; printf("FAIL: expected 0x%x, got 0x%x\n", EXPECTED, output.result); }
     */

    {{MODULE_NAME}}_cleanup(&ctx);

    printf("Self-test: %d passed, %d failed\n", pass, fail);
    return (fail == 0) ? 0 : 1;
}

/* ═══ Main (standalone mode) ═══════════════════════════════════════════════ */

#ifndef DPI_MODE
int main(int argc, char *argv[])
{
    if (argc > 1 && strcmp(argv[1], "--self-test") == 0) {
        return self_test();
    }

    printf("Usage: %s --self-test\n", argv[0]);
    printf("       %s < input.bin > output.bin\n", argv[0]);
    return 0;
}
#endif
