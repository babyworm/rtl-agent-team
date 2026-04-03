# Hook Enforcement Remaining Specs

- Date: 2026-04-03
- Status: Design spec (not yet implemented)
- Context: Plugin completeness review — 2 of 4 hook gaps addressed, 2 remaining

---

## Spec 1: Coverage Exclusion Approval Enforcement

### Problem

`rtl-p5s-coverage-policy` defines two approval tiers for coverage exclusions:
- **Auto-approved** (coverage-analyst decides): UVM/TB infrastructure, parameter guards, toggle on wide buses
- **User-approved** (AskUserQuestion required): unimplemented features, ambiguous spec applicability

Currently, no hook verifies that user approval was actually obtained before session exit.
An agent can classify a bin as "unimplemented feature", skip AskUserQuestion, and exit.
The coverage-exclusions.md will have an "approver" field but nothing validates it.

### Desired Behavior

When a Stop event fires and coverage exclusion records exist:
1. Read `reviews/phase-5-verify/*-coverage-exclusions.md` (module-level) and
   `reviews/phase-5-verify/system-coverage-exclusions.md` (system-level)
2. Parse each exclusion entry for its category
3. For non-standard categories (unimplemented features, ambiguous spec):
   - Check that `approver` field contains a user identifier (not "coverage-analyst")
   - OR check that `.rat/state/coverage-exclusion-approved` marker exists
4. If unapproved non-standard exclusions found → BLOCK exit with:
   ```
   [Coverage Exclusion Gate] N non-standard exclusions require user approval.
   Bins: {list}. Run AskUserQuestion for each, or touch .rat/state/coverage-exclusion-approved
   to acknowledge all.
   ```

### Implementation Approach

**Hook type**: Stop (alongside rtl-verify-stop-gate.sh)

**New file**: `hooks/rtl-coverage-exclusion-gate.sh`

**Logic**:
```
IF reviews/phase-5-verify/*-coverage-exclusions.md exists:
  FOR each exclusion file:
    GREP for "User.*AskUserQuestion" category entries
    IF found AND .rat/state/coverage-exclusion-approved NOT exists:
      COUNT unapproved entries
      IF count > 0:
        BLOCK with message listing unapproved bins
```

**Challenges**:
1. **Parsing markdown tables in POSIX sh** — exclusion records are markdown, not JSON.
   The hook must grep for category patterns without jq. Possible approach: grep for
   lines containing `| Unimplemented` or `| Ambiguous` and check the Approval column.
2. **Approval tracking** — AskUserQuestion doesn't leave a machine-readable trace.
   Options:
   - (A) Marker file: agent creates `.rat/state/coverage-exclusion-approved` after user responds
   - (B) Parse conversation for AskUserQuestion responses (not feasible in hooks)
   - (C) Exclusion record itself has "approved_by: user" field set by the agent
   Recommended: Option (A) — simple marker file. Agent sets it after AskUserQuestion confirmation.
3. **Team mode** — multiple modules may have exclusion files. The marker should be per-module
   or a single blanket approval for all.

**hooks.json addition**:
```json
{
  "event": "Stop",
  "hooks": [
    {
      "command": "sh hooks/rtl-coverage-exclusion-gate.sh",
      "description": "Block exit if non-standard coverage exclusions lack user approval"
    }
  ]
}
```

**Estimated complexity**: Low-medium. ~60 lines of POSIX sh. Main risk is markdown parsing robustness.

### Acceptance Criteria
- [ ] Non-standard exclusion without approval → BLOCK with bin list
- [ ] Non-standard exclusion with `.rat/state/coverage-exclusion-approved` → PASS
- [ ] Auto-approved categories (UVM/TB, parameter guards, toggle) → always PASS
- [ ] No exclusion files exist → PASS (no-op)
- [ ] Team mode: per-session marker OR leader-only check

---

## Spec 2: Specification Change Cascade Enforcement

### Problem

When upstream specification documents change (Phase 1 requirements, Phase 2 architecture,
Phase 3 uArch), downstream artifacts (RTL, testbenches, verification results) become
potentially stale. Currently:

- Phase 6 has cascade detection (rtl-p6-cascade-gate.sh): RTL change after P6 → re-review
- But NO hook detects: spec change after P4 RTL → RTL may violate updated spec

Example: user edits `docs/phase-3-uarch/rate_control.md` to change FIFO depth from 512 to 1024.
The RTL still has `DEPTH=512`. No hook warns about this inconsistency.

### Desired Behavior

When a spec document is modified (Edit/Write to `docs/phase-*/**`):
1. Identify which phase the document belongs to (P1/P2/P3)
2. Check if downstream phases have completed artifacts
3. If downstream artifacts exist → mark them as potentially stale
4. Inject WARNING about cascade impact

**Cascade rules**:
```
docs/phase-1-research/* modified → P2 architecture + P3 uArch + P4 RTL + P5 verify potentially stale
docs/phase-2-architecture/* modified → P3 uArch + P4 RTL + P5 verify potentially stale
docs/phase-3-uarch/* modified → P4 RTL + P5 verify potentially stale
```

### Implementation Approach

**Hook type**: PostToolUse:Edit/Write (extend existing rtl-edit-tracker.sh)

**Extend**: `hooks/rtl-edit-tracker.sh` — add a case for `*/docs/phase-*/*`

**Logic**:
```
CASE "$FILE_PATH" in
  */docs/phase-1-research/*)
    MODIFIED_PHASE=1
    DOWNSTREAM="P2, P3, P4, P5"
    ;;
  */docs/phase-2-architecture/*)
    MODIFIED_PHASE=2
    DOWNSTREAM="P3, P4, P5"
    ;;
  */docs/phase-3-uarch/*)
    MODIFIED_PHASE=3
    DOWNSTREAM="P4, P5"
    ;;
esac

IF MODIFIED_PHASE is set:
  # Check if downstream artifacts exist
  HAS_P4_RTL = test -d "$CWD/rtl" && ls rtl/*/*.sv
  HAS_P5_REVIEWS = test -f "$CWD/reviews/phase-5-verify/final-compliance.md"

  IF downstream artifacts exist:
    touch "$STATE_DIR/spec-cascade-stale-p${MODIFIED_PHASE}"
    WARN = "[SPEC CASCADE] Phase ${MODIFIED_PHASE} document modified.
            Downstream artifacts (${DOWNSTREAM}) may be inconsistent.
            Run /rtl-agent-team:cross-phase-contract-validator to verify."
```

**State file**: `.rat/state/spec-cascade-stale-p{N}` — marker per modified phase.
Cleared when `cross-phase-contract-validator` runs and passes.

**Stop gate integration** (optional, Phase 2):
A Stop hook could block exit if `spec-cascade-stale-p{N}` exists AND downstream
phases were active in this session. This is more aggressive and should be opt-in.

**Challenges**:
1. **Granularity** — Modifying ANY file under `docs/phase-3-uarch/` triggers cascade for
   ALL P4 modules. Ideally, we'd track which module's spec changed and only flag that module's
   RTL. But mapping spec files to modules requires parsing uArch doc structure.
   Recommended: Phase 1 → coarse-grained (flag all downstream). Future: per-module tracking.

2. **Frequency** — Spec documents are modified less often than RTL. The cascade warning
   should not be noisy. Solution: only warn ONCE per spec file change (use mtime comparison
   or a "last-warned" marker).

3. **Cross-phase contract validator integration** — The warning should suggest running
   `cross-phase-contract-validator` (already implemented). After validation PASS,
   clear the stale marker.

4. **Edit-tracker already handles `*/docs/*|*/reviews/*`** — currently only for audit
   logging (artifact_write event). The cascade logic would replace `emit_post_continue`
   with a WARNING for `docs/phase-*/*` paths, while keeping audit for `docs/` and `reviews/`
   that don't match phase patterns.

5. **Iron requirements changes** — `docs/phase-*/iron-requirements.json` modifications
   are the most impactful (structured requirements). These should have HIGHER cascade
   priority than markdown doc changes. Consider:
   - `.json` under `docs/phase-*` → CRITICAL cascade warning
   - `.md` under `docs/phase-*` → WARNING cascade

**Estimated complexity**: Medium. ~40 lines in edit-tracker + ~30 lines optional Stop gate.
Main risk is avoiding false positives during normal Phase 3 → Phase 4 flow (spec changes
that are immediately followed by RTL implementation should not trigger cascade).

**Mitigation for false positives**: Only trigger cascade if downstream artifacts are NEWER
than upstream change. If `docs/phase-3-uarch/rate_control.md` (mtime T1) is modified and
`rtl/rate_control/rate_control.sv` (mtime T0 < T1) exists, that's a real cascade.
If RTL is created AFTER spec change (T0 > T1), no cascade needed.

### Acceptance Criteria
- [ ] P3 uArch doc modified → WARNING if P4 RTL exists with older mtime
- [ ] P2 arch doc modified → WARNING if P3 uArch + P4 RTL exist
- [ ] P1 requirements modified → WARNING if P2 + P3 + P4 exist
- [ ] iron-requirements.json modified → CRITICAL cascade warning
- [ ] Suggest `cross-phase-contract-validator` in warning message
- [ ] Stale marker cleared after contract validator PASS
- [ ] No false positive during normal forward flow (P3 edit → P4 create)
- [ ] Team mode: leader-only cascade tracking

---

## Implementation Priority

| Spec | Complexity | Risk | Recommended Order |
|------|-----------|------|-------------------|
| 1. Coverage Exclusion Approval | Low-medium (~60 lines) | Low (isolated Stop hook) | First |
| 2. Spec Change Cascade | Medium (~70 lines) | Medium (false positive risk) | Second |

Spec 1 is self-contained (new hook file). Spec 2 extends an existing complex hook.
Implement Spec 1 first to validate the pattern, then apply to Spec 2.
