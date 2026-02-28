## Lessons Learned Quick Index

| ID | Phase | Module | Category | One-line Summary |
|----|-------|--------|----------|------------------|
| LL-001 | 5→4 | {{module}} | {{category}} | {{one_line_summary}} |

Categories: SVA | Func | CDC | Timing | Integration | Interface

---

## LL-{{NNN}}: {{Title}}

- **Date**: {{YYYY-MM-DD}}
- **Phase**: Phase {{N}} ({{phase_name}})
- **Module**: {{module_name}} (or "cross-module")
- **Severity**: Critical | Major | Minor

### Symptom
<!-- What was observed? (e.g., "Phase 5c cocotb test failed with assertion error on output valid signal") -->

### Root Cause
<!-- Why did it happen? (e.g., "FSM reset logic missed the IDLE→ACTIVE transition when back-to-back packets arrive") -->

### Fix Applied
<!-- What was changed? (e.g., "Added registered output valid with 1-cycle delay in rtl/parser/parser.sv:142") -->

### Prevention
<!-- How to avoid this in future designs? (e.g., "Always add back-to-back stimulus test case in unit TB for FSM modules") -->

### Related
| Type | Reference |
|------|-----------|
| Requirements | REQ-{{NNN}} |
| Module | {{module_name}} |
| Fix Commit | {{file:line}} |
| ADR | ADR-{{NNN}} (if applicable) |
| Phase 5 Sub-phase | {{5a/5b/5c}} |
