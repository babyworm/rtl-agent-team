# Cascading Requirements with Iron/Open Taxonomy

**Date**: 2026-03-14
**Status**: Approved
**Scope**: Phase 1-5 requirement lifecycle, compliance enforcement, upstream challenge protocol

## Problem Statement

The current RTL agent team plugin has a flat `requirements.json` structure that does not distinguish between:
- **Settled rules** that downstream phases must never violate
- **Research topics** that the next phase must investigate and resolve

This leads to:
1. No formal mechanism to enforce upper-phase requirements in lower phases
2. No structured "homework handoff" between phases
3. No authority hierarchy — violating a P1 functional requirement triggers the same response as violating a P3 micro-architecture decision
4. No upstream feedback path when lower phases discover upper requirements are infeasible

## Design Overview

### Core Concepts

**Iron Requirements** — Settled design decisions that become absolute rules for all downstream phases. Once a requirement passes the ambiguity gate (reproducibility check) and review convergence, it is classified as iron.

**Open Requirements** — Research topics handed off to the next phase as "homework." The receiving phase must investigate, resolve, and convert each open item into iron requirements in its own `iron-requirements.json`.

**Authority Hierarchy** — Iron requirements carry an authority level based on their origin phase. Higher authority (lower number) means stricter enforcement and faster escalation on violation.

| Authority | Origin | Violation Policy |
|-----------|--------|-----------------|
| 1 | Phase 1 (Functional/Performance) | Custom budget: Primary 3 + Fallback 2 + Last-chance 1 = 6 attempts |
| 2 | Phase 2 (Architecture) | Custom budget: Primary 4 + Fallback 3 + Last-chance 1 = 8 attempts |
| 3 | Phase 3 (Micro-architecture) | Existing ladder: N=5, Primary 5 + Fallback 5 + Last-chance 1 = 11 attempts |

**Note on custom budgets:** The existing escalation ladder uses a fixed `N -> 2N -> last-chance` formula with `max_iterations=5` (total 11 attempts). Authority 1 and 2 use **custom reduced budgets** that override the default formula. This requires the `rtl-skill-completion-gate.sh` hook to accept per-authority `max_primary` and `max_fallback` overrides when processing `compliance-pass` criteria. See Section 5 for the mechanism.

**Ambiguity Score as Reproducibility** — Applied at every phase where requirements are produced (not just Phase 1). Measures: "If this process were repeated, would the same requirements emerge?" A requirement cannot become iron until its ambiguity score passes (score <= 0.5).

**Codex Cross-Review Stability** — Review is considered stable only after 2+ consecutive rounds where Codex verdict == APPROVE with no new critical/major findings, no still_disagree items, and no oscillation. Single-round agreement is insufficient.

---

## Section 1: Requirement Taxonomy — Iron vs Open Schema

### iron-requirements.json

Located at `docs/phase-N-*/iron-requirements.json` for each phase that produces requirements (P1, P2, P3).

```json
{
  "phase": "phase-1-research",
  "authority": 1,
  "requirements": [
    {
      "id": "REQ-F-001",
      "type": "functional",
      "description": "H.264 High Profile Level 4.1 decoding support",
      "priority": "must",
      "source": { "document": "spec.pdf", "section": "4.2", "line": 142 },
      "acceptance_criteria": [
        "Level 4.1 compliant bitstream decoded correctly",
        "ITU-T conformance test vector 100% pass"
      ],
      "violation_policy": "user_escalation"
    },
    {
      "id": "REQ-P-001",
      "type": "performance",
      "description": "1080p@60fps real-time processing",
      "priority": "must",
      "source": { "document": "spec.pdf", "section": "5.1", "line": 203 },
      "acceptance_criteria": [
        "throughput >= 124,416,000 pixels/sec",
        "worst-case latency <= 16.67ms per frame"
      ],
      "violation_policy": "user_escalation"
    }
  ]
}
```

**ID Prefix Convention:**
- `REQ-F-*`: Functional (Phase 1)
- `REQ-P-*`: Performance (Phase 1)
- `REQ-A-*`: Architecture (Phase 2)
- `REQ-U-*`: Micro-architecture (Phase 3)

**Schema Rules:**
- `acceptance_criteria` must be measurable — reject vague terms like "should support", "adequate", "sufficient"
- `violation_policy` is `user_escalation` for authority 1, `agent_retry` for authority 2-3
- `source` traces back to the originating document for full traceability

### open-requirements.json

Located at `docs/phase-N-*/open-requirements.json` for phases that produce homework (P1, P2).

```json
{
  "phase": "phase-1-research",
  "target_phase": "phase-2-architecture",
  "open_items": [
    {
      "id": "OPEN-1-001",
      "topic": "CABAC vs CAVLC decoder architecture selection",
      "context": "Both support High Profile. Throughput/area trade-off analysis required",
      "candidates": ["CABAC-pipeline", "CABAC-parallel", "CAVLC-only"],
      "evaluation_criteria": ["gate_count", "throughput", "critical_path"],
      "related_iron": ["REQ-F-001", "REQ-P-001"],
      "resolution_expected": "Architecture selection finalized in iron-requirements.json"
    }
  ]
}
```

**Schema Rules:**
- `candidates` must have >= 2 entries (single candidate means it's not a research topic)
- `related_iron` links to upstream iron requirements that constrain this research
- `evaluation_criteria` specifies what metrics the next phase should use for comparison

### Iron/Open Classification Verification (Phase 1 Exit)

```
FAIL conditions:
  - acceptance_criteria contains vague terms ("should support", "adequate", "sufficient")
  - open item missing evaluation_criteria
  - open item has candidates.length <= 1
  - iron item missing violation_policy

WARN conditions:
  - iron ratio < 30% (most items pushed to open — weakens P1 value)
  - open item related_iron is empty
  - CONDITIONAL PASS ambiguity axis linked to an iron-classified REQ
```

---

## Section 2: Phase Handoff Protocol

### Flow

```
Phase 1 (Research)
  PRODUCES: iron-requirements.json (REQ-F-*, REQ-P-*)
  PRODUCES: open-requirements.json (OPEN-1-*) -> target: phase-2
  EXIT GATE: iron finalized + open items have target specified

Phase 2 (Architecture)
  RECEIVES: P1 open-requirements.json
  RESOLVES: OPEN-1-* -> architecture research/selection
    -> result -> iron-requirements.json (REQ-A-*) finalized
    -> resolution_log records rationale
  COMPLIANCE CHECK: new REQ-A-* do not violate P1 iron (REQ-F-*, REQ-P-*)
  PRODUCES: open-requirements.json (OPEN-2-*) -> target: phase-3
  EXIT GATE: all OPEN-1-* resolved + new iron finalized + compliance pass

Phase 3 (Micro-architecture)
  RECEIVES: P2 open-requirements.json
  RESOLVES: OPEN-2-* -> micro-architecture analysis/decisions
    -> result -> iron-requirements.json (REQ-U-*) finalized
    -> resolution_log records rationale
  COMPLIANCE CHECK: new REQ-U-* do not violate P1+P2 iron
  PRODUCES: NO open-requirements.json (all homework resolved)
    -> If unresolved items remain -> EXIT GATE FAIL
  EXIT GATE: all OPEN-2-* resolved + compliance pass + zero remaining opens

Phase 4+ (Implementation)
  RECEIVES: P1+P2+P3 iron-requirements.json (3 separate files)
  NO open-requirements should exist (P3 resolved everything)
  COMPLIANCE: enforced throughout implementation
```

### Resolution Log — When Open Becomes Iron

Phase 2 `iron-requirements.json` entry with resolution tracking:

```json
{
  "id": "REQ-A-001",
  "type": "architecture",
  "description": "CABAC decoder: 2-stage pipeline architecture adopted",
  "resolved_from": "OPEN-1-001",
  "resolution_rationale": "CABAC-parallel has 2.3x gate count increase for only 1.4x throughput gain. Pipeline approach meets REQ-P-001 (1080p@60fps) with better area efficiency",
  "rejected_alternatives": [
    { "candidate": "CABAC-parallel", "reason": "Insufficient performance-to-area ratio" },
    { "candidate": "CAVLC-only", "reason": "High Profile requires CABAC (REQ-F-001)" }
  ],
  "upstream_compliance": ["REQ-F-001 PASS", "REQ-P-001 PASS"],
  "violation_policy": "agent_retry",
  "acceptance_criteria": [
    "2-stage pipeline achieves 1 bin/cycle throughput",
    "Context model SRAM <= 4KB"
  ]
}
```

### Unresolved Open Item Handling

```
Phase 2 cannot resolve OPEN-1-*:
  -> Option 1: AskUserQuestion for user decision
  -> Option 2: Upstream feedback to Phase 1 (request iron redefinition)
  -> Option 3: Confirm with user if constraint relaxation is possible

Phase 3 cannot resolve OPEN-2-*:
  -> Same escalation options
  -> Additional: Phase 3 exit with remaining opens -> EXIT GATE FAIL
    (P4 requires all requirements to be iron)
```

### Graduated Escalation on Violation

All authority levels receive self-correction opportunities. Budget differs by authority:

```
P1 Functional violation (authority=1):
  Custom budget: Primary 3 + Fallback 2 + Last-chance 1 = total 6

P2 Architecture violation (authority=2):
  Custom budget: Primary 4 + Fallback 3 + Last-chance 1 = total 8

P3 Micro-architecture violation (authority=3):
  Existing ladder (N=5): Primary 5 + Fallback 5 + Last-chance 1 = total 11
```

### Dynamic Prompt Injection on Violation

```
Authority 1 (P1 Functional):
  [CRITICAL - UPSTREAM REQUIREMENT VIOLATION]
  Violated: REQ-F-001 (authority=1, Phase 1 Functional)
  Description: "H.264 High Profile Level 4.1 decoding support"
  Acceptance Criteria FAILED:
    x "ITU-T conformance test vector 100% pass"
  DO NOT proceed with other tasks until this violation is resolved.
  Re-read: docs/phase-1-research/iron-requirements.json
  Escalation: attempt N/6

Authority 2 (P2 Architecture):
  [WARNING - HIGH] tag, "Prioritize fixing this violation"

Authority 3 (P3 Micro-architecture):
  [WARNING] tag, "Address this violation in current iteration"
```

---

## Section 3: Compliance Checker Agent

### Purpose

Independent verification agent that compares downstream artifacts against upstream iron requirements. Based on superpowers spec-compliance-reviewer pattern: "Do not trust the implementer's report. Read the actual artifacts."

### Invocation Points

```
Phase 2 exit gate:  REQ-A-* finalized -> compare against P1 iron
Phase 3 exit gate:  REQ-U-* finalized -> compare against P1+P2 iron
Phase 4 per-wave:   RTL code -> compare against P1+P2+P3 iron
Phase 5 completion: Verification results -> compare against acceptance_criteria
```

### Agent Specification

```
compliance-checker agent (model: opus)

Input:
  - target_artifacts: artifact paths from current phase
  - upstream_iron: upstream iron-requirements.json paths

Step 1: Load all upstream iron requirements
Step 2: Load all target artifacts
Step 3: Per-requirement 1:1 comparison
  For each REQ in upstream_iron:
    - For each acceptance_criteria item:
      -> Search target artifacts for evidence of fulfillment
      -> Evidence found: PASS (record evidence location)
      -> Evidence not found: VIOLATION (record which criteria failed)
      -> Cannot determine: UNCERTAIN (additional verification needed)
Step 4: Generate Compliance Report
```

### Context Isolation

```
CORRECT:
  Task(compliance-checker, prompt="""
    upstream_iron: [file path list]
    target_artifacts: [file path list]
    Read only the above files and compare directly.
    Do not trust implementer explanations or session context.
  """)

INCORRECT:
  Task(compliance-checker, prompt="Review what we've done so far")
```

### Anti-Rationalization Rules

```
UNCERTAIN judgment rules:
  - UNCERTAIN allowed ONLY when artifact is not yet generated
  - "Probably fine" -> treat as VIOLATION
  - "No explicit evidence" -> treat as VIOLATION
  - UNCERTAIN ratio > 20% -> compliance check itself FAIL
```

### Compliance Report Structure

```json
{
  "phase": "phase-3-uarch",
  "checked_against": ["phase-1-research", "phase-2-architecture"],
  "timestamp": "2026-03-14T15:30:00Z",
  "summary": {
    "verdict": "FAIL",
    "total": 24,
    "pass": 21,
    "violation": 2,
    "uncertain": 1,
    "max_violation_authority": 1,
    "infeasibility_detected": false
  },
  "results": [
    {
      "req_id": "REQ-F-001",
      "authority": 1,
      "verdict": "PASS",
      "evidence": "docs/phase-3-uarch/entropy-decoder.md Section 3.2: CABAC full context model support"
    },
    {
      "req_id": "REQ-P-001",
      "authority": 1,
      "verdict": "VIOLATION",
      "failed_criteria": "throughput >= 124,416,000 pixels/sec",
      "finding": "entropy-decoder.md pipeline design at 0.8 bin/cycle — below target throughput",
      "suggested_action": "Consider expanding 2-stage pipeline to 3-stage"
    },
    {
      "req_id": "REQ-A-003",
      "authority": 2,
      "verdict": "UNCERTAIN",
      "reason": "SRAM banking structure not yet finalized, acceptance_criteria cannot be evaluated",
      "suggested_action": "Finalize clock-domain-map.md then re-verify"
    }
  ]
}
```

### Verdict-to-Escalation Flow

```
VIOLATION detected:
  1. Save compliance report to .rtl-agent-team/state/compliance-report.json
  2. Check violation_policy (per authority level)
  3. Enter escalation ladder for that authority
  4. Inject dynamic prompt with [CRITICAL]/[WARNING]

  Ladder exhausted -> user escalation with compliance report presented
```

---

## Section 4: Phase Review System Enhancement

### Convergence vs Compliance Separation

**Convergence** = "Has the quality within this phase stabilized?" (finding_delta < 0.1)
**Compliance** = "Does this phase violate any upstream iron requirements?"

Both must pass for phase exit. They are independent gates.

### Updated Review Pipeline per Phase

**Phase 1 (Research):**

Note: Step numbers match the existing p1-research-orchestrator.md numbering. Steps 1-4 (requirement clarification, solution tree, domain study, sub-domain survey) and Step 6 (ambiguity resolution + merge) are existing steps unchanged by this spec.

```
Step 5:   3-round chief review (existing, unchanged)
Step 6:   Resolve ambiguities + merge (existing, unchanged)
Step 7:   Self-verification + Ambiguity Gate (existing, unchanged)
          -> 3-axis ambiguity score: Goal(40%) + Constraint(30%) + AC(30%)
          -> <= 0.3: PASS, 0.3-0.5: CONDITIONAL PASS, > 0.5: FAIL
Step 7.5: Iron/Open Classification Verification (NEW)
          -> All REQ classified as iron or open
          -> Open items have target_phase specified
          -> Iron acceptance_criteria are measurable
          -> CONDITIONAL PASS axis items not classified as iron
Step 8:   Codex cross-review with 2+ consecutive verdict==APPROVE stability (existing, enhanced)
```

**Phase 2 (Architecture):**
```
Step 5:   Dynamic convergence review (existing, 2-5 rounds)
Step 5.5: Open Resolution Verification (NEW)
          -> All OPEN-1-* resolved
          -> Each resolution has rationale + rejected_alternatives
          -> New REQ-A-* has resolved_from tracking
Step 6:   Compliance Check (NEW)
          -> Task(compliance-checker): REQ-A-* vs P1 iron
          -> VIOLATION -> correction ladder (authority=2: 4+3+1=8 attempts)
Step 7:   Codex cross-review with compliance report as input (existing, enhanced)
```

**Phase 3 (Micro-architecture):**
```
Step 5:   Dynamic convergence review (existing, 2-5 rounds)
Step 5.5: Open Resolution Verification (NEW)
          -> All OPEN-2-* resolved
          -> Zero remaining opens (P4 entry invariant)
Step 6:   Compliance Check (NEW)
          -> Task(compliance-checker): REQ-U-* vs P1+P2 iron
          -> VIOLATION -> correction ladder (authority=3: 5+5+1=11 attempts)
Step 7:   Codex cross-review with compliance report as input (existing, enhanced)
```

**Phase 4 (Implementation) — per wave:**
```
Wave N complete:
  -> Lint + Unit test (existing)
  -> Compliance Check (NEW)
      -> Task(compliance-checker): RTL code vs P1+P2+P3 iron
      -> VIOLATION -> authority-differentiated ladder
  -> Next wave
```

**Phase 5 (Verification):**
```
Verification complete:
  -> Compliance Check (NEW)
      -> acceptance_criteria final verification against test results
```

### Codex Cross-Review Enhancement

```
Previous input:
  - Phase artifacts only

Enhanced input:
  - Phase artifacts
  - compliance-report.json (PASS/VIOLATION results)
  - iron-requirements.json (all upstream)

Additional verification:
  - Any compliance-checker PASS items that are actually violations?
  - Any implicit violations the compliance-checker missed?

Stability criterion:
  - 2+ consecutive rounds with verdict==APPROVE + no new critical/major findings + no still_disagree + no oscillation = stabilized
  - Single-round agreement is insufficient
```

### Ambiguity Scoring at Every Phase

Ambiguity score measures reproducibility: "If this process were repeated, would the same requirements emerge?"

```
Phase 1: spec -> iron/open requirements
  -> "Would re-analyzing this spec produce the same REQ-F-001?"

Phase 2: open items + research -> REQ-A-* (architecture decisions)
  -> "Would re-evaluating this architecture produce the same conclusion?"

Phase 3: open items + analysis -> REQ-U-* (micro-architecture decisions)
  -> "Would re-analyzing this micro-architecture produce the same design?"

Phase 4+: implementation/verification choices
  -> "Would re-selecting this approach produce the same method?"
```

A requirement cannot become iron until its ambiguity score passes. Ambiguous decisions cannot be iron.

---

## Section 4.5: Upstream Challenge Protocol

### Purpose

Formal protocol for lower phases to challenge upper-phase iron requirements when they are technically infeasible. Completes the closed-loop system: top-down (iron enforcement) + bottom-up (infeasibility feedback).

### Integration with Escalation Ladder

```
Compliance VIOLATION detected
  -> Primary stage: agent attempts self-correction (all violations start here)
  -> Primary exhausted, violation persists:
     -> Agent produces "infeasibility_assessment" in its output:
        - "correctable": true/false
        - If true: standard Fallback stage (strategy change, agent switching)
        - If false: must include quantitative evidence (see criteria below)
           -> compliance-checker re-invoked to validate infeasibility claim
           -> If validated: Upstream Challenge (replaces Fallback stage)
           -> If rejected (evidence insufficient): standard Fallback continues
```

**Infeasibility classification decision point:** After Primary stage exhaustion, the **orchestrator agent** (not the hook, not the compliance-checker) declares whether the violation is correctable or infeasible. This declaration is validated by a **second compliance-checker invocation** that specifically evaluates the quantitative evidence. The hook reads `infeasibility_detected: true` from the compliance report to switch from Fallback to Upstream Challenge.

This two-step validation (agent claims + checker validates) prevents agents from prematurely escaping the correction ladder by claiming infeasibility without evidence.

### Infeasibility Judgment Criteria

Agent must provide **quantitative evidence** to claim infeasibility:

```
VALID infeasibility evidence:
  "2-stage pipeline max throughput = 0.8 bin/cycle, required = 1.0 bin/cycle"
  "Gate count estimate 320K, area budget 200K — 1.6x over"
  "Critical path 2.1ns, target clock period 1.5ns — timing infeasible"

INVALID (anti-rationalization):
  "This requirement seems difficult to achieve"
  "Generally this level is unrealistic"
  "More time is needed"
```

### Challenge Report Structure

```json
{
  "type": "upstream_challenge",
  "challenged_req": "REQ-P-001",
  "authority": 1,
  "origin_phase": "phase-1-research",
  "challenger_phase": "phase-3-uarch",
  "infeasibility_evidence": {
    "metric": "throughput",
    "required": "1.0 bin/cycle",
    "achievable": "0.8 bin/cycle",
    "analysis": "Theoretical upper bound of 2-stage CABAC pipeline. 3-stage violates REQ-A-001"
  },
  "conflicting_requirements": ["REQ-P-001", "REQ-A-001"],
  "proposed_resolutions": [
    {
      "option": "A",
      "description": "Relax REQ-P-001: reduce to 1080p@30fps",
      "ppa_estimate": {
        "frequency_mhz": 300,
        "area_gate_count": 185000,
        "throughput": {
          "bin_per_cycle": 0.8,
          "pixel_rate_mpps": 62.2,
          "achievable_fps": 30
        }
      },
      "delta_from_current": { "area": "-8%", "throughput": "0%" }
    },
    {
      "option": "B",
      "description": "Modify REQ-A-001: allow 3-stage pipeline",
      "ppa_estimate": {
        "frequency_mhz": 300,
        "area_gate_count": 230000,
        "throughput": {
          "bin_per_cycle": 1.2,
          "pixel_rate_mpps": 128.5,
          "achievable_fps": 62
        }
      },
      "delta_from_current": { "area": "+15%", "throughput": "+50%" }
    },
    {
      "option": "C",
      "description": "Dual parallel CABAC engines",
      "ppa_estimate": {
        "frequency_mhz": 300,
        "area_gate_count": 360000,
        "throughput": {
          "bin_per_cycle": 1.6,
          "pixel_rate_mpps": 171.0,
          "achievable_fps": 82
        }
      },
      "delta_from_current": { "area": "+80%", "throughput": "+100%" }
    }
  ],
  "recommendation": "B",
  "recommendation_rationale": "Minimal area increase while meeting performance requirement"
}
```

### ppa_estimate Required Fields

| Field | Unit | Required | Notes |
|-------|------|----------|-------|
| `frequency_mhz` | MHz | **Required** | Target or achievable clock |
| `area_gate_count` | gates | **Required** | Estimated gate count |
| `throughput.bin_per_cycle` | bin/cycle | Domain-specific | Entropy codec etc. |
| `throughput.pixel_rate_mpps` | Mpixels/sec | **Required** | Universal throughput metric |
| `throughput.achievable_fps` | fps | **Required** | At target resolution |

**Throughput sub-field rule:** At least one throughput sub-field must be directly relevant to the challenged requirement's `acceptance_criteria`. If the challenged REQ uses bin/cycle as its metric, `bin_per_cycle` becomes required for that challenge.
| `power_mw` | mW | Optional | When estimable |
| `sram_kb` | KB | Optional | When SRAM usage changes |

### User Presentation Format

```
[UPSTREAM CHALLENGE — Iron Requirement Infeasibility]

REQ-P-001: "1080p@60fps real-time processing"
Evidence: CABAC 2-stage pipeline upper bound = 0.8 bin/cycle (required: 1.0)

Option comparison (@300MHz):
+--------+----------+-----------+-----------+----------+
| Option | Area (K) | bin/cycle  | Mpps      | fps      |
+--------+----------+-----------+-----------+----------+
| Current| 200      | 0.8       | 85.7      | 41 FAIL  |
| A relax| 185 (-8%)| 0.8       | 62.2      | 30 (tgt downarrow) |
| B 3stg | 230(+15%)| 1.2       | 128.5     | 62 PASS  |
| C dual | 360(+80%)| 1.6       | 171.0     | 82 PASS  |
+--------+----------+-----------+-----------+----------+

Recommendation: (B) — area +15% meets requirement, best cost-performance
```

### Post-Decision Flow

```
User selects Option B:
  1. Modify REQ-A-001 in Phase 2 iron-requirements.json
     -> "2-stage pipeline" -> "3-stage pipeline"
     -> challenge_resolution: "Modified per UPSTREAM-CHALLENGE-001"
  2. Re-derive REQ-U-* in Phase 3 (based on modified REQ-A-001)
  3. Compliance re-check (against modified iron)
  4. Re-convergence confirmation
```

---

## Section 5: Hook & Gate Integration

### Existing Hooks Modified (4)

**1. `rtl-phase-state-bootstrap.sh` (PreToolUse:Skill)**

Bootstraps compliance state when a phase skill is invoked:

```bash
# Added: upstream iron path injection

# P2 skill invocation:
upstream_iron='["docs/phase-1-research/iron-requirements.json"]'

# P3 skill invocation:
upstream_iron='["docs/phase-1-research/iron-requirements.json",
               "docs/phase-2-architecture/iron-requirements.json"]'

# P4+ skill invocation:
upstream_iron='["docs/phase-1-research/iron-requirements.json",
               "docs/phase-2-architecture/iron-requirements.json",
               "docs/phase-3-uarch/iron-requirements.json"]'

# Creates: .rtl-agent-team/state/compliance-state.json
```

**2. `rtl-skill-completion-gate.sh` (Stop)**

Added compliance-pass verification with authority-differentiated ladder budgets:

```bash
# When criteria includes "compliance-pass":
# 1. Read compliance-report.json
# 2. If no violations -> compliance-pass satisfied, continue
# 3. If violations exist:
#    a. Read max_violation_authority from compliance-report.json summary
#    b. Override skill-active.json ladder budget based on authority:
#       authority=1 -> set max_primary=3, max_fallback=2 in skill-active.json
#       authority=2 -> set max_primary=4, max_fallback=3 in skill-active.json
#       authority=3 -> keep defaults (max_primary=5, max_fallback=5)
#    c. Write "compliance_authority": N to skill-active.json for state tracking
#    d. Inject dynamic_prompt with [CRITICAL]/[WARNING] per authority
# 4. If compliance-report.json contains "infeasibility_detected": true
#    AND current iteration > max_primary:
#    -> Switch strategy to "upstream_challenge" (replaces fallback stage)
#    -> Set dynamic_prompt to instruct agent to produce challenge report
```

**Mechanism for authority detection:** The compliance-checker agent writes `max_violation_authority` (the highest-priority violated authority) into the compliance report's `summary` field. The hook reads this single integer to determine ladder budget. This avoids the hook needing to parse individual results.

**3. `rtl-spawn-context.sh` (PreToolUse:TaskCreate)**

Added upstream iron paths to spawn context manifest:

```bash
# Added to spawn-context.json:
# "upstream_iron": [...],
# "open_requirements": "docs/phase-N-*/open-requirements.json",
# "compliance_state": "pending"
```

**4. `rtl-orchestrator-inject.sh` (SessionStart)**

Added Iron Requirements Protocol rules (~10 lines) to session injection:

```
## Iron Requirements Protocol
- Each phase produces iron-requirements.json (absolute rules) and
  open-requirements.json (homework for next phase)
- Iron requirements from upper phases MUST NOT be violated
- Authority hierarchy: P1(functional) > P2(architecture) > P3(micro-arch)
- Violation triggers graduated escalation; infeasibility triggers
  Upstream Challenge with quantitative PPA evidence
- Phase exit requires compliance-checker PASS against all upstream iron
```

### No New Hooks

All integration achieved through modification of existing hooks. Rationale:
- Compliance check is performed at agent level (orchestrator spawns compliance-checker)
- Upstream challenge is an escalation ladder branch (within skill-completion-gate.sh)
- Ambiguity scoring is within orchestrator steps (no hook involvement needed)

Hooks remain lightweight (gate judgment only); heavy logic stays in agents.

### compliance-state.json Template Schema

```json
{
  "phase": "",
  "upstream_iron_paths": [],
  "open_requirements_path": "",
  "compliance_status": "pending",
  "compliance_authority": null,
  "challenge_count": 0,
  "last_check_timestamp": null
}
```

| Field | Type | Description |
|-------|------|-------------|
| `phase` | string | Current phase identifier (e.g., "phase-2-architecture") |
| `upstream_iron_paths` | string[] | Paths to upstream iron-requirements.json files |
| `open_requirements_path` | string | Path to received open-requirements.json (empty for P1) |
| `compliance_status` | string | "pending" / "pass" / "violation" / "challenge_pending" |
| `compliance_authority` | int\|null | Highest-priority violated authority (null if no violation) |
| `challenge_count` | int | Number of upstream challenges raised in this phase |
| `last_check_timestamp` | string\|null | ISO 8601 timestamp of last compliance check |

### State File Changes

```
.rtl-agent-team/state/
  compliance-state.json          # NEW: upstream iron paths, status tracking
  compliance-report.json         # NEW: compliance-checker results
  upstream-challenges/           # NEW: challenge report storage
    CHALLENGE-001.json
  skill-active.json              # EXISTING: unchanged
  p4-state.json                  # EXISTING: unchanged
  ... (remaining existing files unchanged)
```

### skill-completion-criteria.json Changes

```json
Before:
  "p1-spec-research":      "spec-analysis-complete|review-rounds-done|artifacts-written"
  "p2-arch-design":        "arch-review-complete|ref-model-built|artifacts-written"
  "rtl-p3-uarch-design":   "uarch-review-complete|artifacts-written"
  "rtl-p1-research-team":  "spec-analysis-complete|review-rounds-done|artifacts-written"
  "rtl-p2-arch-team":      "arch-review-complete|ref-model-built|artifacts-written"
  "rtl-p3-uarch-team":     "uarch-review-complete|artifacts-written"
  "rtl-p4-implement":      "rtl-written|lint-pass|unit-test-pass"
  "rtl-p4-implement-team": "rtl-written|lint-pass|unit-test-pass"
  "rtl-p5-verify":         "verification-pass|coverage-met|artifacts-written"
  "rtl-p5-verify-team":    "verification-pass|coverage-met|artifacts-written"

After:
  "p1-spec-research":      "spec-analysis-complete|review-rounds-done|artifacts-written|iron-open-classified|ambiguity-pass"
  "p2-arch-design":        "arch-review-complete|ref-model-built|artifacts-written|open-resolved|compliance-pass|ambiguity-pass"
  "rtl-p3-uarch-design":   "uarch-review-complete|artifacts-written|open-resolved|zero-remaining-opens|compliance-pass|ambiguity-pass"
  "rtl-p1-research-team":  "spec-analysis-complete|review-rounds-done|artifacts-written|iron-open-classified|ambiguity-pass"
  "rtl-p2-arch-team":      "arch-review-complete|ref-model-built|artifacts-written|open-resolved|compliance-pass|ambiguity-pass"
  "rtl-p3-uarch-team":     "uarch-review-complete|artifacts-written|open-resolved|zero-remaining-opens|compliance-pass|ambiguity-pass"
  "rtl-p4-implement":      "rtl-written|lint-pass|unit-test-pass|compliance-pass"
  "rtl-p4-implement-team": "rtl-written|lint-pass|unit-test-pass|compliance-pass"
  "rtl-p5-verify":         "verification-pass|coverage-met|artifacts-written|compliance-pass"
  "rtl-p5-verify-team":    "verification-pass|coverage-met|artifacts-written|compliance-pass"
```

| New Criteria | Meaning | Applies To |
|-------------|---------|------------|
| `iron-open-classified` | All REQ classified as iron or open | P1 |
| `ambiguity-pass` | Ambiguity score <= 0.5 (reproducibility) | P1, P2, P3 |
| `open-resolved` | All upstream open items resolved | P2, P3 |
| `zero-remaining-opens` | No unresolved opens remain (P4 entry invariant) | P3 |
| `compliance-pass` | Zero VIOLATION against upstream iron | P2, P3, P4, P5 |

---

## Section 6: Implementation Plan

### Change Scope

| Category | New | Modified | Total |
|----------|-----|----------|-------|
| Agent (.md) | 1 | 4 | 5 |
| Skill (SKILL.md) | 0 | 10 | 10 |
| Policy (SKILL.md) | 0 | 3 | 3 |
| Hook (.sh) | 0 | 4 | 4 |
| State template | 1 | 0 | 1 |
| Config (JSON) | 0 | 1 | 1 |
| **Total** | **2** | **22** | **24** |

Note: Skill count includes team variants (P1-team, P2-team, P3-team, P4-team, P5-team) that receive identical criteria additions as their base counterparts.

### Implementation Waves

**Wave 1: Schema + Core Agent (Foundation)**
1. `skills/p1-spec-research-policy/SKILL.md` — iron/open schema definition
2. `agents/spec-analyst.md` — iron/open classification output
3. `agents/compliance-checker.md` — new agent
4. `skill-completion-criteria.json` — new criteria registration
5. `skills/rtl-p4-rapid-impl-policy/templates/compliance-state.json` — state template

Verification: Run P1 skill standalone, confirm iron/open JSON generated correctly.

**Wave 2: Cross-Phase Connection (Handoff + Compliance)**
6. `skills/p2-arch-design-policy/SKILL.md` — open resolution + compliance protocol
7. `agents/p2-arch-orchestrator.md` — resolution step + compliance check invocation
8. `skills/rtl-p3-uarch-policy/SKILL.md` — same pattern + zero-opens invariant
9. `agents/p3-uarch-orchestrator.md` — same pattern + upstream challenge
10. `agents/p1-research-orchestrator.md` — iron/open classification verification step

Verification: Run P1->P2->P3 sequentially, confirm iron accumulation, open resolution, compliance pass.

**Wave 3: Hook Integration + Team Versions (System Connection)**
11. `hooks/rtl-phase-state-bootstrap.sh` — iron path injection
12. `hooks/rtl-skill-completion-gate.sh` — compliance gate + authority ladder
13. `hooks/rtl-spawn-context.sh` — spawn context extension
14. `hooks/rtl-orchestrator-inject.sh` — rule injection
15-17. Team version skills (P1/P2/P3): rtl-p1-research-team, rtl-p2-arch-team, rtl-p3-uarch-team
18-19. P4 team + P5 team skills: rtl-p4-implement-team, rtl-p5-verify-team
20-21. P4/P5 base skills compliance addition
22. `skills/p1-spec-research/SKILL.md` — skill modification
23. `skills/p2-arch-design/SKILL.md` — skill modification

Verification: Full P1->P5 pipeline + team mode + Stop gate behavior.

### No Impact (No Changes Needed)

- Phase 6 (Design Review) — upstream compliance applies through P5 only
- Phase 7 (Exploration) — exempt from pipeline rules
- `rtl-edit-tracker.sh` — RTL modification tracking is independent
- `rtl-verify-stop-gate.sh` — functional verification gate is independent
- `rtl-p6-cascade-gate.sh` — P6 cascade is independent
- `stop-gate.sh` (autopilot) — separate ladder
- Audit hooks (3) — logging only
- `domain-packages/` — domain expert system is independent
- Cross-review system — input expansion only (compliance report added)
