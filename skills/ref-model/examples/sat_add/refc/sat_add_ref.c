/* sat_add_ref.c — Phase 2 golden C reference model example: 8-bit
 * unsigned saturating adder.
 *
 * Self-testing: main() checks the model against embedded golden vectors
 * and returns 0 on pass, 1 on any mismatch. Used as the committed worked
 * example for scripts/run_ref_model.py (build via refc/Makefile, run with
 * no arguments, deterministic stdout).
 *
 * Conventions: pure functional (no clock/reset), C11, snake_case,
 * DPI-C compatible (no C++ features).
 */
#include <stdio.h>

#include "sat_add_ref.h"

uint8_t sat_add_u8(uint8_t a, uint8_t b)
{
    uint16_t sum = (uint16_t)a + (uint16_t)b;
    return (sum > 0xFFu) ? (uint8_t)0xFFu : (uint8_t)sum;
}

typedef struct {
    uint8_t a;
    uint8_t b;
    uint8_t golden;
} vector_t;

static const vector_t GOLDEN_VECTORS[] = {
    {0u,   0u,   0u},    /* zero */
    {1u,   2u,   3u},    /* small sum */
    {200u, 55u,  255u},  /* exact top of range */
    {200u, 56u,  255u},  /* first saturating sum */
    {255u, 255u, 255u},  /* full saturation */
    {128u, 127u, 255u},  /* boundary pair */
};

int main(void)
{
    const unsigned total =
        (unsigned)(sizeof(GOLDEN_VECTORS) / sizeof(GOLDEN_VECTORS[0]));
    unsigned pass = 0u;
    unsigned fail = 0u;
    unsigned i;

    printf("sat_add_ref: self-test\n");
    for (i = 0u; i < total; i++) {
        const vector_t *v = &GOLDEN_VECTORS[i];
        uint8_t actual = sat_add_u8(v->a, v->b);
        if (actual == v->golden) {
            pass++;
        } else {
            fail++;
            printf("vector %u FAIL: sat_add_u8(%u, %u) = %u, expected %u\n",
                   i, (unsigned)v->a, (unsigned)v->b,
                   (unsigned)actual, (unsigned)v->golden);
        }
    }
    printf("vectors=%u pass=%u fail=%u\n", total, pass, fail);
    if (fail == 0u) {
        printf("SELF-TEST PASS\n");
        return 0;
    }
    printf("SELF-TEST FAIL\n");
    return 1;
}
