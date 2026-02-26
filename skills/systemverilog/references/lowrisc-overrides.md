# lowRISC Style Guide — Project Overrides

This document lists all deviations from the lowRISC SystemVerilog Coding Style Guide.
Base: https://github.com/lowRISC/style-guides/blob/master/VerilogCodingStyle.md

## Override Summary

| # | lowRISC Default | Project Override | Reason |
|---|----------------|-----------------|--------|
| 1 | Port suffix: `_i`, `_o`, `_io` | Port prefix: `i_`, `o_`, `io_` (필수) | Prefix makes direction visible at signal usage site |
| 2 | Clock: `clk_i` | Clock: `clk` (단일) or `{domain}_clk` (다중) | Multi-clock designs need domain identification |
| 3 | Reset: `rst_ni` (active-low) | Reset: `rst_n` (단일) or `{domain}_rst_n` (다중) | Consistent with clock domain naming |
| 4 | Parameter: `UpperCamelCase` | Parameter: `ALL_CAPS` | CamelCase 전면 금지 |
| 5 | Enum value: `UpperCamelCase` (`StIdle`) | Enum value: `ALL_CAPS` (`ST_IDLE`) | CamelCase 전면 금지 |
| 6 | localparam: `UpperCamelCase` or `ALL_CAPS` | localparam: `L_` prefix + `ALL_CAPS` | 외부/내부 parameter 구분 |

## Detailed Rationale

### Override 1: Port Direction Prefix (필수, clk/rst 예외)

**lowRISC**: `data_i`, `valid_o`, `sda_io` (suffix)
**Project**: `i_data`, `o_valid`, `io_sda` (prefix, 필수)

**Clock/Reset 예외**: `clk`, `sys_clk`, `rst_n`, `sys_rst_n`은 `i_` prefix 없이 사용.
클럭과 리셋은 항상 입력이므로 방향 prefix가 불필요하며, RTL 전체에서 가장 빈번하게
참조되는 신호이므로 간결성을 우선한다.

**Why prefix is mandatory (for other signals):**
- When reading `i_data` in logic, direction is immediately visible
- With suffix (`data_i`), the signal name body (`data`) comes first — direction is an afterthought
- Prefix groups signals by direction when sorted alphabetically
- Common in industry ASIC flows (ARM, Synopsys reference designs)

### Override 2: Clock Naming

**lowRISC**: Single `clk_i` input
**Project**: `clk` (단일 도메인) or `{domain}_clk` (다중 도메인) — e.g., `sys_clk`, `pixel_clk`

**Why:**
- 단일 클럭 설계는 간결하게 `clk`
- 다중 클럭 설계는 domain prefix로 cross-domain 실수 방지
- CDC 분석 도구가 naming pattern에서 도메인 자동 식별

### Override 3: Reset Naming

**lowRISC**: `rst_ni` (active-low, suffix)
**Project**: `rst_n` (단일 도메인) or `{domain}_rst_n` (다중 도메인)

**Why:**
- 클럭 naming과 일관성 유지
- `_n` suffix로 active-low 명확히 표시

### Override 4: CamelCase 전면 금지

**lowRISC**: Parameter `UpperCamelCase` (`DataWidth`), Enum value `UpperCamelCase` (`StIdle`)
**Project**: Parameter `ALL_CAPS` (`DATA_WIDTH`), Enum value `ALL_CAPS` (`ST_IDLE`)

**Why ALL_CAPS only:**
- CamelCase와 snake_case 혼용은 일관성을 깨뜨림
- `ALL_CAPS`는 상수/parameter를 변수와 시각적으로 즉시 구분 가능
- 업계 표준 (Verilog 전통: ALL_CAPS for parameters)

### Override 5: L_ Prefix for Internal localparam

**lowRISC**: localparam도 parameter와 동일한 naming
**Project**: 외부 설정 불가 localparam은 `L_` prefix + `ALL_CAPS`

**Why L_ prefix:**
- 외부 parameter (`DATA_WIDTH`)와 내부 localparam (`L_ADDR_BITS`) 즉시 구분
- 코드 리뷰 시 "이것을 외부에서 변경할 수 있는가?" 즉시 판별
- 예: `L_CNT_MAX = DEPTH - 1` — `DEPTH`는 외부, `L_CNT_MAX`는 내부 파생값

## What Stays the Same

All other lowRISC rules remain in effect:
- `logic` only (no `reg`/`wire`)
- `always_ff` / `always_comb` (no `always`)
- `typedef enum` / `typedef struct packed`
- ANSI port style
- One module per file
- Package-based type sharing
- `unique case` / `priority case`
- 2 spaces indentation, 100 char line length
- `_d` / `_q` suffix for combinational/registered pairs
