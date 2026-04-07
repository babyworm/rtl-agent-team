# {{MODULE_NAME}}

> Auto-generated from `rtl/{{MODULE_DIR}}/{{MODULE_NAME}}.sv`
> Generated: {{DATE}}

## Overview

{{FUNCTIONAL_DESCRIPTION}}

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| {{PARAM_NAME}} | {{TYPE}} | {{DEFAULT}} | {{DESCRIPTION}} |

## Ports

| Port | Direction | Width | Clock Domain | Description |
|------|-----------|-------|--------------|-------------|
| {{DOMAIN}}_clk | input | 1 | {{DOMAIN}} | Clock |
| {{DOMAIN}}_rst_n | input | 1 | {{DOMAIN}} | Active-low async reset |
| i_{{SIGNAL}} | input | {{WIDTH}} | {{DOMAIN}} | {{DESCRIPTION}} |
| o_{{SIGNAL}} | output | {{WIDTH}} | {{DOMAIN}} | {{DESCRIPTION}} |

## Clock Domains

| Domain | Clock | Reset | Usage |
|--------|-------|-------|-------|
| {{DOMAIN}} | {{DOMAIN}}_clk | {{DOMAIN}}_rst_n | {{USAGE}} |

## FSM States

| State | Encoding | Description | Transitions To |
|-------|----------|-------------|----------------|
| {{STATE}} | {{VALUE}} | {{DESCRIPTION}} | {{NEXT_STATES}} |

## Sub-Module Instances

| Instance | Module | Purpose |
|----------|--------|---------|
| u_{{NAME}} | {{MODULE}} | {{PURPOSE}} |

## Block Diagram

```d2
# Module internal structure
{{MODULE_NAME}}: {
  # Sub-blocks
}
```

## Synthesis Summary

> Populated from `syn/rpt/{{MODULE_NAME}}_stat.rpt` if available.

| Metric | Value |
|--------|-------|
| Cell count | {{CELLS}} |
| Area (um^2) | {{AREA}} |
| Max frequency | {{FMAX}} MHz |
| Critical path | {{CRIT_PATH}} |

## Convention Compliance

| Check | Status | Notes |
|-------|--------|-------|
| Port prefix (i_/o_/io_) | {{PASS/FAIL}} | {{VIOLATIONS}} |
| Clock naming ({domain}_clk) | {{PASS/FAIL}} | {{VIOLATIONS}} |
| Reset naming ({domain}_rst_n) | {{PASS/FAIL}} | {{VIOLATIONS}} |
| Instance prefix (u_) | {{PASS/FAIL}} | {{VIOLATIONS}} |
| Generate prefix (gen_) | {{PASS/FAIL}} | {{VIOLATIONS}} |
| logic only (no reg/wire) | {{PASS/FAIL}} | {{VIOLATIONS}} |
