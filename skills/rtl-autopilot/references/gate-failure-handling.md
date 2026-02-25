# Gate Failure Handling Examples

## Quality Gate FAIL → Fix and Retry

If Phase 2→3 Quality Gate fails with findings:

```
Task(subagent_type="rtl-agent-team:arch-designer",
     prompt="Quality Gate review found the following issues in architecture.md:
{paste findings from rtl-architect verdict}
Read requirements.json and architecture.md. Fix each finding while ensuring:
- No requirement from requirements.json is dropped or weakened
- All interface conventions (i_/o_ prefix, {domain}_clk/{domain}_rst_n) are maintained
Update architecture.md and block_diagram accordingly.")
```

Then re-run the Phase 2→3 Quality Gate. Maximum 2 retry cycles per gate.

## Upper-Spec Violation → Return to Upper Phase

If Phase 3→4 Quality Gate finds μArch dropped a feature from architecture.md:

1. **STOP** — do not proceed to Phase 4
2. Report to user: "μArch for block X dropped Feature Y required by architecture.md"
3. Return to Phase 2 if architecture itself needs revision, or Phase 3 to fix μArch
4. **DO NOT proceed without user approval**

## Artifact Gate FAIL → Retry Once

If a required artifact is missing after a phase completes:

1. Re-run the phase with explicit instruction to produce the missing artifact
2. If still missing after retry → escalate to user with details

## Maximum Retry Policy

| Gate Type | Max Retries | On Exhaustion |
|-----------|-------------|---------------|
| Artifact Gate | 1 retry | Escalate to user |
| Quality Gate | 2 fix-and-retry cycles | Escalate to user with all findings |
| Upper-Spec Violation | 0 retries | IMMEDIATE STOP, user approval required |
