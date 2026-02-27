# Protocol Compliance Report: {{MODULE_NAME}}

- **Date**: {{DATE}}
- **Reviewer**: protocol-checker
- **Protocol**: {{PROTOCOL_TYPE}} (AXI4 / AXI4-Lite / AHB-Lite / APB3)
- **Perspective**: {{PERSPECTIVE}} (master / slave)
- **Verdict**: {{VERDICT}}

## Interface Signals

| Channel | Signal | Direction | Width | Convention Check |
|---------|--------|-----------|-------|-----------------|
| AW | i_awvalid | input | 1 | OK |
| AW | o_awready | output | 1 | OK |
| AW | i_awaddr | input | {{ADDR_W}} | OK |

## Assertions Summary

| Category | Total | Bound | Passed | Failed | Not Tested |
|----------|-------|-------|--------|--------|------------|
| Handshake | {{N}} | {{N}} | {{N}} | {{N}} | {{N}} |
| Ordering | {{N}} | {{N}} | {{N}} | {{N}} | {{N}} |
| Stability | {{N}} | {{N}} | {{N}} | {{N}} | {{N}} |
| No X/Z | {{N}} | {{N}} | {{N}} | {{N}} | {{N}} |

## Violations

| # | Rule | Assertion | Cycle | Channel | Description |
|---|------|-----------|-------|---------|-------------|
| 1 | AXI-HANDSHAKE-2 | valid_hold_until_ready | {{CYCLE}} | AW | i_awvalid dropped before o_awready |

## Convention Violations

| # | File:Line | Found | Expected | Issue |
|---|-----------|-------|----------|-------|
| 1 | {{FILE}}:{{LINE}} | AWVALID | i_awvalid | Non-conformant signal name |

## Waveform Evidence

| Violation | VCD File | Start Cycle | End Cycle | Key Signals |
|-----------|----------|-------------|-----------|-------------|
| #1 | sim/waveforms/{{FILE}}.vcd | {{START}} | {{END}} | i_awvalid, o_awready |

## Verdict

{{VERDICT}}: {{REASON}}

- Total assertions: {{TOTAL}}
- Passed: {{PASSED}}
- Failed: {{FAILED}} (must be 0 to pass)
- Convention violations: {{CONV_COUNT}}
