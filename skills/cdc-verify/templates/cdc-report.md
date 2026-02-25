# CDC Analysis Report: {{MODULE_NAME}}

- **Date**: {{DATE}}
- **Reviewer**: cdc-checker
- **Target**: {{TARGET_FILES}}
- **Verdict**: {{VERDICT}}

## Clock Domains Identified

| Domain | Clock Signal | Frequency | Reset Signal |
|--------|-------------|-----------|-------------|
| sys | sys_clk | {{FREQ}} MHz | sys_rst_n |
| axi | axi_clk | {{FREQ}} MHz | axi_rst_n |

## Cross-Domain Paths Summary

| Source Domain | Dest Domain | Paths | Synced | Unsynced | Caution |
|---------------|-------------|-------|--------|----------|---------|
| sys_clk | axi_clk | {{N}} | {{N}} | {{N}} | {{N}} |

## Violations (MUST fix)

| # | Severity | Source | Dest | File:Line | Signal | Description |
|---|----------|--------|------|-----------|--------|-------------|
| 1 | VIOLATION | sys_clk | axi_clk | {{FILE}}:{{LINE}} | {{SIGNAL}} | Missing 2-FF synchronizer |

## Cautions (review required)

| # | Source | Dest | File:Line | Signal | Description |
|---|--------|------|-----------|--------|-------------|
| 1 | sys_clk | axi_clk | {{FILE}}:{{LINE}} | {{BUS}} | Multi-bit bus crossing without gray code |

## Convention Violations

| # | File:Line | Found | Expected | Rule |
|---|-----------|-------|----------|------|
| 1 | {{FILE}}:{{LINE}} | clk_i | {domain}_clk | CLOCK_NAME |

## Safe Crossings (INFO)

| # | Source | Dest | Signal | Synchronization Method |
|---|--------|------|--------|----------------------|
| 1 | sys_clk | axi_clk | {{SIGNAL}} | 2-FF synchronizer (u_sync_*) |
| 2 | sys_clk | axi_clk | {{BUS}} | Gray code FIFO (u_gray_*) |

## Verdict

{{VERDICT}}: {{REASON}}

- Violations: {{VIOLATION_COUNT}} (must be 0 to pass)
- Cautions: {{CAUTION_COUNT}} (require human review)
- Convention: {{CONVENTION_COUNT}}
- Safe crossings: {{SAFE_COUNT}}
