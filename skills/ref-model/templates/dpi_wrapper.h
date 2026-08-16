/**
 * dpi_wrapper.h — DPI-C interface for {{MODULE_NAME}} reference model
 *
 * Import these functions in SystemVerilog testbench:
 *   import "DPI-C" function int dpi_{{MODULE_NAME}}_init();
 *   import "DPI-C" function int dpi_{{MODULE_NAME}}_process(
 *       input  int unsigned data_in,
 *       output int unsigned data_out
 *   );
 *   import "DPI-C" function void dpi_{{MODULE_NAME}}_cleanup();
 *
 * Build:  make dpi
 *   (Makefile target DPI_TARGET — compiles with -DDPI_MODE -fPIC -shared.
 *    Do not spell the source glob out here: a literal src/ followed by *.c
 *    embeds a comment-opening sequence in this block and trips -Wcomment.)
 */

#ifndef DPI_WRAPPER_H
#define DPI_WRAPPER_H

#ifdef DPI_MODE

#include "svdpi.h"

#ifdef __cplusplus
extern "C" {
#endif

/**
 * Initialize reference model context.
 * Call once at simulation start (e.g., in initial block).
 * @return 0 on success
 */
int dpi_{{MODULE_NAME}}_init(void);

/**
 * Run one processing step.
 * @param data_in   Input data (matches RTL i_data width)
 * @param data_out  Output data (matches RTL o_result width)
 * @return 0 on success
 */
int dpi_{{MODULE_NAME}}_process(
    const svBitVecVal *data_in,
    svBitVecVal *data_out
);

/**
 * Cleanup reference model resources.
 * Call at end of simulation.
 */
void dpi_{{MODULE_NAME}}_cleanup(void);

#ifdef __cplusplus
}
#endif

#endif /* DPI_MODE */
#endif /* DPI_WRAPPER_H */
