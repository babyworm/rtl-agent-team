/* sat_add_ref.h — Phase 2 golden C reference model example header.
 *
 * Pure functional model: no clock, no reset, DPI-C compatible (plain C11).
 * PARALLEL_LANES kept parameterizable per ref-model conventions.
 */
#ifndef SAT_ADD_REF_H
#define SAT_ADD_REF_H

#include <stdint.h>

#ifndef PARALLEL_LANES
#define PARALLEL_LANES 1
#endif

/* 8-bit unsigned saturating add: result clamps at 0xFF. */
uint8_t sat_add_u8(uint8_t a, uint8_t b);

#endif /* SAT_ADD_REF_H */
