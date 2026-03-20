/**
 * {{MODULE_NAME}}_ref.h — Reference Model Public API
 *
 * Defines data structures and function prototypes for the
 * {{MODULE_NAME}} functional reference model.
 */

#ifndef {{MODULE_NAME_UPPER}}_REF_H
#define {{MODULE_NAME_UPPER}}_REF_H

#include <stdint.h>

/* ═══ Configuration ════════════════════════════════════════════════════════ */

/* TODO: Match RTL parameter defaults */
#define {{MODULE_NAME_UPPER}}_DATA_WIDTH  32

/* ═══ Data Structures ══════════════════════════════════════════════════════ */

/** Model context — holds persistent state between calls. */
typedef struct {
    /* TODO: Add algorithm state (lookup tables, counters, buffers) */
    uint32_t reserved;
} {{MODULE_NAME}}_ctx_t;

/** Input data — matches RTL input port widths. */
typedef struct {
    /* TODO: Add input fields matching i_* ports */
    uint32_t data;
} {{MODULE_NAME}}_input_t;

/** Output data — matches RTL output port widths. */
typedef struct {
    /* TODO: Add output fields matching o_* ports */
    uint32_t result;
} {{MODULE_NAME}}_output_t;

/* ═══ API ══════════════════════════════════════════════════════════════════ */

/**
 * Initialize model context.
 * @return 0 on success
 */
int {{MODULE_NAME}}_init({{MODULE_NAME}}_ctx_t *ctx);

/**
 * Process one input → output step (pure functional, no clock/reset).
 * Must produce bitexact output matching RTL.
 * @return 0 on success
 */
int {{MODULE_NAME}}_process(
    {{MODULE_NAME}}_ctx_t *ctx,
    const {{MODULE_NAME}}_input_t *input,
    {{MODULE_NAME}}_output_t *output);

/**
 * Cleanup model resources.
 */
void {{MODULE_NAME}}_cleanup({{MODULE_NAME}}_ctx_t *ctx);

#endif /* {{MODULE_NAME_UPPER}}_REF_H */
